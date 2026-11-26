import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_radar import repos
from ai_radar.config import Config
from ai_radar.store import Store


def fake_api(url, headers=None, *a, **k):
    if "/search/issues" in url:
        return {"total_count": 1 if "good%20first%20issue" in url else 4}
    return {"full_name": "conductor-oss/conductor", "html_url": "https://github.com/conductor-oss/conductor",
            "description": "Event driven agentic workflow engine", "stargazers_count": 32514,
            "created_at": "2023-12-08T06:06:09Z", "pushed_at": "2026-11-26T18:46:23Z", "topics": ["java", "spring-boot"],
            "language": "Java", "owner": {"type": "Organization"}, "archived": False, "fork": False}


class TestWatch(unittest.TestCase):
    def test_watched_repo_is_added_and_analysed_whatever_its_age(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Config(home=Path(d))
            cfg.repos_watch = ["conductor-oss/conductor"]
            cfg.repos_focus = ["java"]
            store = Store(cfg.db_path)
            with mock.patch.object(repos, "http_json", side_effect=fake_api):
                report = repos.enrich(cfg, store)
            it = store.get("repo:conductor-oss/conductor")
            watch = repos.to_watch(store)
            store.close()
        self.assertEqual(report["watched"], 1)
        self.assertTrue(it["signals"]["watched"])
        self.assertEqual(it["signals"]["contrib"]["good_first_issues"], 1)
        self.assertEqual(it["signals"]["contrib"]["help_wanted"], 4)
        self.assertEqual(it["signals"]["contrib"]["focus_match"], ["java"])
        self.assertEqual([w["id"] for w in watch], ["repo:conductor-oss/conductor"])

    def test_watched_bonus_in_score(self):
        from datetime import datetime, timezone
        from ai_radar import scoring
        now = datetime.now(timezone.utc)
        base = {"category": "tool", "source": "Watched repo", "description": "", "published_at": now.isoformat(),
                "first_seen": now.isoformat(), "brief": "", "title": "a/b"}
        s = {i: sc for i, sc, _ in scoring.score_items([dict(base, id="repo:a/b", signals={}),
                                                         dict(base, id="repo:c/d", title="c/d", signals={"watched": True})], now)}
        self.assertEqual(round(s["repo:c/d"] - s["repo:a/b"]), 25)


if __name__ == "__main__":
    unittest.main()
