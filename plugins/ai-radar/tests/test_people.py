import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from ai_radar import collectors, scoring
from ai_radar.config import Config


def repo(name, days_pushed, stars=0, fork=False, days_created=None):
    t = lambda d: (datetime.now(timezone.utc) - timedelta(days=d)).isoformat().replace("+00:00", "Z")
    return {"full_name": name, "html_url": f"https://github.com/{name}", "description": "Claude Code mod: route turns",
            "stargazers_count": stars, "fork": fork, "pushed_at": t(days_pushed),
            "created_at": t(days_created if days_created is not None else days_pushed), "topics": ["claude-code"],
            "language": "TypeScript"}


class TestNetwork(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(home=Path("/nonexistent"))
        self.cfg.window_days = 45

    def test_off_without_people(self):
        self.assertEqual(collectors.network_repos(self.cfg), [])

    def test_recent_repos_of_watched_accounts_even_with_zero_stars(self):
        self.cfg.people = ["shezis"]
        data = [repo("shezis/claude-model-router", 44), repo("shezis/old", 200), repo("shezis/forked", 1, fork=True)]
        with mock.patch.object(collectors, "http_get", return_value=json.dumps(data).encode()) as get:
            items = collectors.network_repos(self.cfg)
        self.assertIn("/users/shezis/repos", get.call_args[0][0])
        self.assertEqual([i["id"] for i in items], ["repo:shezis/claude-model-router"])
        it = items[0]
        self.assertEqual(it["signals"]["network"], "shezis")
        self.assertEqual(it["signals"]["stars"], 0)
        self.assertTrue(it["merge_signals"])

    def test_one_failing_account_keeps_the_others(self):
        self.cfg.people = ["gone", "shezis"]

        def fake(url, *a, **k):
            if "/gone/" in url:
                raise OSError("404")
            return json.dumps([repo("shezis/x-tool", 2)]).encode()
        with mock.patch.object(collectors, "http_get", side_effect=fake):
            self.assertEqual([i["id"] for i in collectors.network_repos(self.cfg)], ["repo:shezis/x-tool"])

    def test_network_bonus_in_score(self):
        now = datetime.now(timezone.utc)
        base = {"category": "tool", "source": "GitHub", "description": "", "published_at": now.isoformat(),
                "first_seen": now.isoformat(), "brief": ""}
        a = dict(base, id="repo:a/x", title="a/x", signals={"stars_per_day": 0})
        b = dict(base, id="repo:b/y", title="b/y", signals={"stars_per_day": 0, "network": "shezis"})
        s = {i: (sc, sig) for i, sc, sig in scoring.score_items([a, b], now)}
        self.assertEqual(round(s["repo:b/y"][0] - s["repo:a/x"][0]), 25)
        self.assertEqual(s["repo:b/y"][1]["score_detail"]["network"], 25)


if __name__ == "__main__":
    unittest.main()
