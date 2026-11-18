import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

from ai_radar import collectors


def _timeout(*_a, **_k):
    raise urllib.error.URLError(TimeoutError("timed out"))


class NetworkBreakerTest(unittest.TestCase):
    def setUp(self):
        collectors.reset_network_state()

    def test_fails_fast_after_timeouts_in_a_row(self):
        with mock.patch("urllib.request.urlopen", side_effect=_timeout) as urlopen:
            for _ in range(collectors.NETWORK_DOWN_AFTER):
                with self.assertRaises(urllib.error.URLError):
                    collectors.http_get("https://example.org/a")
            with self.assertRaises(collectors.NetworkDown):
                collectors.http_get("https://example.org/b")
        self.assertEqual(urlopen.call_count, collectors.NETWORK_DOWN_AFTER)  # the last call did not wait

    def test_an_http_answer_resets_the_breaker(self):
        n = collectors.NETWORK_DOWN_AFTER
        http_404 = urllib.error.HTTPError("https://example.org", 404, "Not Found", {}, None)
        timeouts = [urllib.error.URLError(TimeoutError("timed out")) for _ in range(n - 1)]
        with mock.patch("urllib.request.urlopen", side_effect=timeouts + [http_404] + timeouts) as urlopen:
            for _ in range(n - 1):
                with self.assertRaises(urllib.error.URLError):
                    collectors.http_get("https://example.org")
            with self.assertRaises(urllib.error.HTTPError):
                collectors.http_get("https://example.org")
            self.assertFalse(collectors.network_down())
            for _ in range(n - 1):  # counted from 0 again: still real requests, never NetworkDown
                with self.assertRaises(urllib.error.URLError) as ctx:
                    collectors.http_get("https://example.org")
                self.assertNotIsInstance(ctx.exception, collectors.NetworkDown)
        self.assertEqual(urlopen.call_count, 2 * (n - 1) + 1)

    def test_dns_failures_count_too(self):
        import socket
        dns = urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided"))
        with mock.patch("urllib.request.urlopen", side_effect=dns):
            for _ in range(collectors.NETWORK_DOWN_AFTER):
                with self.assertRaises(urllib.error.URLError):
                    collectors.http_get("https://example.org")
        self.assertTrue(collectors.network_down())

    def test_reset_clears_breaker_and_warnings(self):
        collectors.WARNINGS["rss"] = "x"
        with mock.patch("urllib.request.urlopen", side_effect=_timeout):
            for _ in range(collectors.NETWORK_DOWN_AFTER):
                with self.assertRaises(urllib.error.URLError):
                    collectors.http_get("https://example.org")
        collectors.reset_network_state()
        self.assertEqual(collectors.WARNINGS, {})
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b"ok"
        with mock.patch("urllib.request.urlopen", return_value=ok):
            self.assertEqual(collectors.http_get("https://example.org"), b"ok")


class WaitForNetworkTest(unittest.TestCase):
    def test_up_at_once(self):
        with mock.patch("urllib.request.urlopen") as urlopen, mock.patch("time.sleep") as sleep:
            self.assertTrue(collectors.wait_for_network(tries=3, pause=5))
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_any_http_status_means_up(self):
        err = urllib.error.HTTPError("https://api.github.com", 403, "Forbidden", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            self.assertTrue(collectors.wait_for_network(tries=1, pause=0))

    def test_gives_up_after_tries(self):
        with mock.patch("urllib.request.urlopen", side_effect=_timeout) as urlopen, \
                mock.patch("time.sleep") as sleep:
            self.assertFalse(collectors.wait_for_network(tries=4, pause=7))
        self.assertEqual(urlopen.call_count, 4)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [7, 7, 7])

    def test_malformed_answer_is_retried_not_raised(self):
        import http.client
        with mock.patch("urllib.request.urlopen", side_effect=http.client.BadStatusLine("x")), \
                mock.patch("time.sleep"):
            self.assertFalse(collectors.wait_for_network(tries=2, pause=1))


class PartialRunTest(unittest.TestCase):
    def test_network_down_run_is_partial_and_not_fresh(self):
        import tempfile
        from pathlib import Path
        from ai_radar import pipeline
        from ai_radar.store import Store

        def all_sources_down(_cfg):
            for _ in range(collectors.NETWORK_DOWN_AFTER):
                try:
                    collectors.http_get("https://example.org")
                except Exception:
                    pass
            return []

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("urllib.request.urlopen", side_effect=_timeout), \
                mock.patch.dict(collectors.COLLECTORS, {k: all_sources_down for k in collectors.COLLECTORS}, clear=True), \
                mock.patch.object(pipeline.events, "enabled_collectors", return_value={}), \
                mock.patch.object(pipeline.events, "notify", return_value=False), \
                mock.patch.object(pipeline.repos, "enrich", return_value={}), \
                mock.patch.object(pipeline.trends, "language_trends", return_value={}):
            from ai_radar.config import load_config
            with mock.patch.dict("os.environ", {"AI_RADAR_HOME": tmp}):
                cfg = load_config()
            store = Store(Path(tmp) / "radar.db")
            report = pipeline.collect(cfg, store)
            self.assertTrue(report["network_down"])
            self.assertTrue(report["partial"])
            self.assertIsNone(store.last_run())  # does not count as a fresh run
            store.close()


RSS = b"""<rss><channel><item><title>Hello</title><link>https://example.org/1</link></item></channel></rss>"""


class RssWarningsTest(unittest.TestCase):
    def setUp(self):
        collectors.reset_network_state()

    def _cfg(self, feeds):
        return SimpleNamespace(feeds=feeds, window_days=7)

    def test_partial_failure_is_reported(self):
        def fake_get(url, *a, **k):
            if "bad" in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return RSS
        with mock.patch.object(collectors, "http_get", side_effect=fake_get):
            items = collectors.rss_feeds(self._cfg({"Good": "https://example.org/good", "Bad": "https://example.org/bad"}))
        self.assertEqual(len(items), 1)
        self.assertIn("Bad", collectors.WARNINGS["rss"])
        self.assertIn("404", collectors.WARNINGS["rss"])

    def test_no_warning_when_all_feeds_succeed(self):
        with mock.patch.object(collectors, "http_get", return_value=RSS):
            collectors.rss_feeds(self._cfg({"Good": "https://example.org/good"}))
        self.assertNotIn("rss", collectors.WARNINGS)


if __name__ == "__main__":
    unittest.main()
