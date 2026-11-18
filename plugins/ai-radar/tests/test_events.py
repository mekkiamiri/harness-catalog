import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from ai_radar import events
from ai_radar.config import Config
from ai_radar.store import Store, now


class TestEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(home=Path(self.tmp.name))
        self.store = Store(self.cfg.db_path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_same_conference_from_two_sources_gets_one_id(self):
        self.assertEqual(events.conf_id("Voxxed Days Amsterdam", "2027-03-31"),
                         events.conf_id("VoxxedDays Amsterdam 2027", "2027-03-30"))

    def test_watchlist_reads_first_column_of_markdown_table(self):
        path = Path(self.tmp.name) / "cal.md"
        path.write_text("| Conf | Date |\n|---|---|\n| **Devoxx France 2027** | 7/04 |\n| MiXiT 2027 | avril |\n")
        self.cfg.watchlist = str(path)
        wl = events.load_watchlist(self.cfg)
        self.assertTrue(events.is_watched("Devoxx France 2027", wl))
        self.assertFalse(events.is_watched("PyCon DE 2027", wl))

    def _cfp(self, name, days_left, watched=False):
        close = (now() + timedelta(days=days_left)).date().isoformat()
        return {"id": events.conf_id(name, "2099"), "kind": "conference", "name": name, "online": False,
                "cfp_close": close, "cfp_url": "https://conference-hall.io/x", "source": "t", "tags": [],
                "watched": watched, "location": ""}

    def test_one_alert_per_event_and_deduplicated(self):
        ev = self._cfp("DevFest Nantes 2027", 7, watched=True)
        first = events.compute_alerts(self.store, self.cfg, [ev], {ev["id"]}, set())
        self.assertEqual(len(first), 1)
        self.assertIn("closes in 7 days", first[0]["text"])
        for a in first:
            self.store.record_notification(a["key"], a["text"])
        self.assertEqual(events.compute_alerts(self.store, self.cfg, [ev], set(), set()), [])

    def test_unknown_conferences_do_not_alert(self):
        ev = self._cfp("Some Random Summit", 5)
        self.assertEqual(events.compute_alerts(self.store, self.cfg, [ev], {ev["id"]}, set()), [])


if __name__ == "__main__":
    unittest.main()


class TestWatchlistMatching(unittest.TestCase):
    def test_short_or_empty_names_never_match(self):
        wl = ["devoxx france", "mixit"]
        self.assertFalse(events.is_watched("", wl))
        self.assertFalse(events.is_watched("Dev 2027", wl))
        self.assertTrue(events.is_watched("MiXiT 2027", wl))

    def test_spacing_and_case_do_not_matter(self):
        self.assertTrue(events.is_watched("VoxxedDays Amsterdam 2027", ["voxxed days amsterdam"]))


class TestRunLock(unittest.TestCase):
    def test_second_run_is_refused_while_the_first_holds_the_lock(self):
        from ai_radar import pipeline
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(home=Path(tmp))
            with pipeline.run_lock(cfg):
                self.assertTrue(pipeline.is_running(cfg))
                with self.assertRaises(pipeline.AlreadyRunning):
                    with pipeline.run_lock(cfg):
                        pass
            self.assertFalse(pipeline.is_running(cfg))


class TestWatchlistNotes(unittest.TestCase):
    def test_notes_outside_the_table_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.md"
            p.write_text("| Conf | Date |\n|---|---|\n| MiXiT 2027 | avril |\n\nClosed: Snowcamp, Touraine Tech.\n")
            cfg = Config(home=Path(tmp), watchlist=str(p))
            wl = events.load_watchlist(cfg)
            self.assertTrue(events.is_watched("MiXiT 2027", wl))
            self.assertFalse(events.is_watched("Touraine Tech 2027", wl))
