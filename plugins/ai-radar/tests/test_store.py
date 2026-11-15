import tempfile
import unittest
from pathlib import Path

from ai_radar.store import Store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "r.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_upsert_then_brief_then_ignore(self):
        it = {"id": "repo:a/b", "category": "tool", "title": "a/b", "url": "https://x", "source": "GitHub"}
        self.assertTrue(self.store.upsert(it))
        self.assertFalse(self.store.upsert(it))
        self.store.commit()
        self.assertTrue(self.store.set_field("repo:a/b", "brief", "ok"))
        self.assertEqual(self.store.get("repo:a/b")["brief"], "ok")
        self.store.set_field("repo:a/b", "status", "ignored")
        self.assertEqual(self.store.query(), [])

    def test_forbidden_field(self):
        with self.assertRaises(ValueError):
            self.store.set_field("x", "score", "1")

    def test_event_cfp_date_change_is_detected(self):
        ev = {"id": "conf:x-2027", "kind": "conference", "name": "X 2027", "url": "https://x", "source": "t",
              "start_at": "2099-04-07", "cfp_close": "2099-01-10"}
        self.assertEqual(self.store.upsert_event(ev), (True, False))
        self.assertEqual(self.store.upsert_event(ev | {"cfp_close": "2099-01-17"}), (False, True))
        self.assertEqual(self.store.upcoming_cfps(days=100000)[0]["cfp_close_prev"], "2099-01-10")

    def test_cfp_dates_are_not_erased_or_overridden(self):
        base = {"id": "conf:y-2099", "kind": "conference", "name": "Y", "url": "https://y", "start_at": "2099-04-07"}
        self.store.upsert_event(base | {"source": "cfp.dev", "cfp_open": "2098-11-23T08:00", "cfp_close": "2099-01-10"})
        # a run where cfp.dev failed: the agenda has another date, and no opening date
        self.assertEqual(self.store.upsert_event(base | {"source": "developers.events", "cfp_close": "2099-01-03"}), (False, False))
        # a run where nobody had a date
        self.store.upsert_event(base | {"source": "developers.events", "cfp_close": None})
        ev = self.store.upcoming_cfps(days=100000)[0]
        self.assertEqual((ev["cfp_open"], ev["cfp_close"]), ("2098-11-23T08:00", "2099-01-10"))

    def test_starred_items_survive_retention_and_ignored_stay_as_tombstones(self):
        for i, status in enumerate(["new", "starred", "ignored"]):
            self.store.upsert({"id": f"repo:a/{i}", "category": "tool", "title": str(i), "url": "https://x", "source": "G"})
            self.store.set_field(f"repo:a/{i}", "status", status)
        self.store.conn.execute("UPDATE items SET first_seen = '2000-01-01T00:00:00+00:00', last_seen = '2000-01-01T00:00:00+00:00'")
        self.store.purge(30)
        left = {r["id"] for r in self.store.conn.execute("SELECT id FROM items")}
        self.assertEqual(left, {"repo:a/1"})  # ignored tombstones expire after 90 days
        self.assertEqual([i["id"] for i in self.store.query(days=30)], ["repo:a/1"])

    def test_partial_runs_do_not_count_as_the_daily_run(self):
        full = self.store.start_run(); self.store.end_run(full, {"partial": False})
        part = self.store.start_run(); self.store.end_run(part, {"partial": True})
        self.assertEqual(self.store.last_run()["report"], {"partial": False})

    def test_contribution_signals_survive_a_new_collection(self):
        it = {"id": "repo:a/b", "category": "tool", "title": "a/b", "url": "https://x", "source": "GitHub", "signals": {"stars": 1}}
        self.store.upsert(it)
        self.store.conn.execute("UPDATE items SET signals = ? WHERE id = 'repo:a/b'", ('{"stars": 1, "contrib_score": 42}',))
        self.store.upsert(it | {"signals": {"stars": 2}})
        self.assertEqual(self.store.get("repo:a/b")["signals"], {"stars": 2, "contrib_score": 42})
