import unittest

from ai_radar import describe

README = """<p align="center"><img src="logo.png"></p>

[![CI](https://x/badge.svg)](https://x) [![npm](https://y.svg)](https://y)

# Plannotator

> Everything you need.

**Plannotator** is a local, browser-based review surface for AI coding agents: annotate plans, review
diffs and send the feedback to [Claude Code](https://x), Codex and others.

```bash
npm i -g plannotator
```

It plugs into your agent through hooks and commands.
"""


class TestDescribe(unittest.TestCase):
    def test_readme_summary_keeps_prose_only(self):
        s = describe.readme_summary(README)
        self.assertTrue(s.startswith("Plannotator is a local, browser-based review surface"), s)
        self.assertIn("It plugs into your agent", s)
        for noise in ("badge", "npm i", "<", "](", "Everything you need", "**"):
            self.assertNotIn(noise, s)

    def test_language_pickers_and_pointers_are_skipped(self):
        text = ("English | 简体中文 | 繁體中文 | 한국어 | Deutsch | Español | Français\n\n"
                "For more information, check out: What are skills? Using skills in agents\n\n"
                "OpenCode is an open source AI coding agent built for the terminal, with any model provider.")
        self.assertTrue(describe.readme_summary(text).startswith("OpenCode is an open source AI coding agent"))

    def test_summary_is_capped(self):
        long = ("This tool does many useful things for agents and developers alike. " * 20).strip()
        s = describe.readme_summary(long, limit=100)
        self.assertLessEqual(len(s), 101)
        self.assertTrue(s.endswith("…"))

    def test_for_you_levels(self):
        focus = ["java", "spring", "mcp", "agents", "claude"]
        it = {"title": "o/spring-mcp-server", "description": "MCP server for Spring Boot", "signals": {"language": "Java"}}
        self.assertEqual(describe.for_you(it, focus), {"level": "yes", "why": ["java", "spring", "mcp"]})
        it = {"title": "o/x", "description": "", "signals": {"readme": "A plugin for Claude users."}}
        self.assertEqual(describe.for_you(it, focus)["level"], "maybe")
        it = {"title": "o/css-tricks", "description": "CSS layouts", "signals": {}}
        self.assertEqual(describe.for_you(it, focus), {"level": "no", "why": []})


class TestAlertLinks(unittest.TestCase):
    def test_keys_point_to_events(self):
        from ai_radar.render import event_id_of
        self.assertEqual(event_id_of("online:meetup:https://m.com/g/events/1/"), "meetup:https://m.com/g/events/1/")
        self.assertEqual(event_id_of("meetup:https://m.com/g/events/1/:online"), "meetup:https://m.com/g/events/1/")
        self.assertEqual(event_id_of("conf:devoxx-2027:closes:7"), "conf:devoxx-2027")
        self.assertIsNone(event_id_of("phone:2026-11-15"))

    def test_grouped_alert_lists_each_event_once(self):
        import tempfile
        from pathlib import Path
        from ai_radar.render import alerts_with_links
        from ai_radar.store import Store, iso, now
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "r.db")
            for i in (1, 2):
                s.conn.execute("INSERT INTO events (id, kind, name, url, source, first_seen, last_seen) VALUES (?, 'meetup', ?, ?, 'Meetup', '2026-11-26', '2026-11-26')",
                               (f"meetup:https://m.com/e/{i}/", f"Event {i}", f"https://m.com/e/{i}/"))
                s.conn.execute("INSERT INTO notifications (key, sent_at, message) VALUES (?, ?, ?)",
                               (f"online:meetup:https://m.com/e/{i}/", iso(now()), "2 new online events: Event 1, Event 2"))
            s.conn.execute("INSERT INTO events (id, kind, name, url, cfp_url, source, first_seen, last_seen) VALUES ('conf:dx', 'conference', 'DX', 'https://dx.io', 'https://dx.io/cfp', 'cfp.dev', '2026-11-26', '2026-11-26')")
            s.conn.execute("INSERT INTO notifications (key, sent_at, message) VALUES ('conf:dx:closes:7', ?, 'CFP DX closes in 7 days')", (iso(now()),))
            s.commit()
            alerts = {a["message"]: a["links"] for a in alerts_with_links(s)}
            s.close()
        self.assertEqual([l["name"] for l in alerts["2 new online events: Event 1, Event 2"]], ["Event 1", "Event 2"])
        self.assertEqual([l["url"] for l in alerts["CFP DX closes in 7 days"]], ["https://dx.io", "https://dx.io/cfp"])


class TestRedact(unittest.TestCase):
    def test_http_error_reasons_are_dropped(self):
        from ai_radar.render import redact_errors
        run = {"report": {"errors": {"openrouter": "HTTP Error 403: Company-Blocking-Policy-X",
                                     "rss": "A: HTTP Error 404: Not Found; B: HTTP Error 429: Too Many Requests"}}}
        out = redact_errors(run)["report"]["errors"]
        self.assertEqual(out["openrouter"], "HTTP Error 403")
        self.assertEqual(out["rss"], "A: HTTP Error 404; B: HTTP Error 429")


if __name__ == "__main__":
    unittest.main()
