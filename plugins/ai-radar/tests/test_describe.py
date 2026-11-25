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


if __name__ == "__main__":
    unittest.main()
