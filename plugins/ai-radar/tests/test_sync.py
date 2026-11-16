import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_radar import sync
from ai_radar.config import Config
from ai_radar.store import Store


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class TestTwoComputers(unittest.TestCase):
    """Computer A marks an item and writes a profile; computer B gets them after a sync."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        git("init", "-q", "--bare", "-b", "main", str(t / "origin.git"))
        self.pcs = []
        for name in ("a", "b"):
            clone = t / f"memory-{name}"
            git("clone", "-q", str(t / "origin.git"), str(clone))
            git("config", "user.email", "test@example.org", cwd=clone)
            git("config", "user.name", "Test", cwd=clone)
            git("config", "core.hooksPath", "/dev/null", cwd=clone)
            cfg = Config(home=t / f"home-{name}", memory_home=str(clone))
            cfg.home.mkdir()
            self.pcs.append((cfg, Store(cfg.db_path)))
        # the remote needs a first commit
        clone_a = self.pcs[0][0].memory_home
        (Path(clone_a) / "README.md").write_text("memory\n")
        git("add", ".", cwd=clone_a); git("commit", "-q", "-m", "init", cwd=clone_a); git("push", "-q", "origin", "main", cwd=clone_a)
        git("pull", "-q", "origin", "main", cwd=self.pcs[1][0].memory_home)

    def tearDown(self):
        for _, store in self.pcs:
            store.close()
        self.tmp.cleanup()

    def test_state_travels_from_one_computer_to_the_other(self):
        (cfg_a, a), (cfg_b, b) = self.pcs
        item = {"id": "repo:acme/x", "category": "tool", "title": "acme/x", "url": "https://x", "source": "GitHub"}
        a.upsert(item); a.commit()
        a.set_field("repo:acme/x", "status", "starred")
        a.set_field("repo:acme/x", "brief", "**What it is**: x")
        a.record_notification("conf:x:d7:2099-01-01", "CFP X closes in 7 days"); a.commit()
        cfg_a.profile_path.write_text("# Profile\nSession language: French + English\n")
        self.assertEqual(sync.sync(cfg_a, a)["status"], "pushed")

        report = sync.sync(cfg_b, b)
        self.assertIn(report["status"], {"pushed", "up to date"})
        got = b.get("repo:acme/x")
        self.assertEqual((got["status"], got["brief"]), ("starred", "**What it is**: x"))
        self.assertTrue(b.already_notified("conf:x:d7:2099-01-01"))
        self.assertIn("French + English", cfg_b.profile_path.read_text())

    def test_a_decision_beats_new(self):
        (cfg_a, a), (cfg_b, b) = self.pcs
        item = {"id": "paper:1", "category": "research", "title": "P", "url": "https://p", "source": "HF"}
        for s in (a, b):
            s.upsert(item); s.commit()
        a.set_field("paper:1", "status", "ignored")
        sync.sync(cfg_a, a)
        sync.sync(cfg_b, b)
        self.assertEqual(b.get("paper:1")["status"], "ignored")

    def test_disabled_without_memory_home(self):
        cfg = Config(home=Path(self.tmp.name) / "home-c")
        cfg.home.mkdir()
        store = Store(cfg.db_path)
        self.assertTrue(sync.sync(cfg, store)["status"].startswith("disabled"))
        store.close()


if __name__ == "__main__":
    unittest.main()


class TestSyncEdgeCases(TestTwoComputers):
    def test_fields_merge_independently(self):
        """A marks read, B writes a brief on the same item: both survive on both computers."""
        (cfg_a, a), (cfg_b, b) = self.pcs
        item = {"id": "paper:9", "category": "research", "title": "P9", "url": "https://p", "source": "HF"}
        for s in (a, b):
            s.upsert(item); s.commit()
        a.set_field("paper:9", "status", "read")
        sync.sync(cfg_a, a)
        b.set_field("paper:9", "brief", "**What it is**: p9")
        sync.sync(cfg_b, b)
        sync.sync(cfg_a, a)
        for s in (a, b):
            got = s.get("paper:9")
            self.assertEqual((got["status"], got["brief"]), ("read", "**What it is**: p9"))

    def test_config_is_never_synced_and_first_sync_pulls_the_shared_profile(self):
        (cfg_a, a), (cfg_b, b) = self.pcs
        cfg_a.config_path.write_text("custom = true\n")
        cfg_a.profile_path.write_text("# Real profile\n")
        sync.sync(cfg_a, a)
        cfg_b.config_path.write_text("template = true\n")
        cfg_b.profile_path.write_text("# Fresh template\n")
        sync.sync(cfg_b, b)
        self.assertEqual(cfg_b.profile_path.read_text(), "# Real profile\n")
        self.assertTrue((cfg_b.home / "profile.md.before-first-sync").exists())
        sync.sync(cfg_a, a)
        self.assertEqual(cfg_a.config_path.read_text(), "custom = true\n")
        self.assertFalse((Path(cfg_a.memory_home) / "ai-radar" / "config.toml").exists())

    def test_concurrent_pushes_do_not_break_the_next_sync(self):
        (cfg_a, a), (cfg_b, b) = self.pcs
        for s, i in ((a, "1"), (b, "2")):
            s.upsert({"id": f"repo:x/{i}", "category": "tool", "title": i, "url": "https://x", "source": "G"}); s.commit()
            s.set_field(f"repo:x/{i}", "status", "starred")
        sync.sync(cfg_a, a)
        # B committed locally on an old base (simulates a push rejected because A pushed first)
        sync.export_state(b, Path(cfg_b.memory_home) / "ai-radar")
        git("add", "ai-radar", cwd=cfg_b.memory_home); git("commit", "-q", "-m", "local", cwd=cfg_b.memory_home)
        report = sync.sync(cfg_b, b)
        self.assertEqual(report["status"], "pushed", report)
        sync.sync(cfg_a, a)
        self.assertEqual(a.get("repo:x/2")["status"], "starred")
        self.assertEqual(b.get("repo:x/1")["status"], "starred")


class TestDeliverAndProposals(TestTwoComputers):
    def test_deliver_writes_tomorrows_digest_and_pushes(self):
        from ai_radar import pipeline
        cfg, store = self.pcs[0]
        out = pipeline.deliver_digest(cfg, store)
        self.assertTrue(out["daily_digest"].endswith(".json"))
        self.assertEqual(out["sync"]["status"], "pushed")

    def test_proposals_need_ai_words_and_whole_word_focus(self):
        from ai_radar.repos import proposals
        cfg, store = self.pcs[0]
        cfg.repos_focus = ["go", "java"]
        recent = "2099-01-01T00:00:00+00:00"
        for i, (title, desc) in enumerate([("a/googly", "google agents toolkit"), ("b/mc", "Minecraft Java Edition in Rust"),
                                           ("c/jagent", "java agent framework")]):
            store.upsert({"id": f"repo:{title}", "category": "tool", "title": title, "url": f"https://x/{i}",
                          "source": "G", "description": desc, "published_at": recent, "signals": {"stars_per_day": 10}})
        store.commit()
        self.assertEqual([p["title"] for p in proposals(cfg, store)], ["c/jagent"])
