import unittest

from ai_radar import collectors, sync


class TestLures(unittest.TestCase):
    def test_cracked_software_lures_are_detected(self):
        lures = [
            ("YASIRCAMPBELL2/acrobat-pro-win", "Adobe Acrobat Pro - PDF editing and document management suite "
             "for text editing, form creation and digital signatures on Windows 10/11"),
            ("CliBranchLong/claude-code-win", "Anthropic Claude Code - AI coding assistant for natural-language "
             "code generation, terminal-based workflows and multi-file editing on Windows 10/11"),
            ("x/claude-ai-prompt-utility", "Claude AI Prompt Utility: Technical Alternative Access Framework"),
            ("y/fl-studio", "FL Studio 2026 full version free download with activator"),
            ("z/office-tool", "Microsoft Office 2024 crack + keygen"),
        ]
        for name, desc in lures:
            self.assertTrue(collectors.looks_like_lure(name, desc), name)

    def test_real_projects_are_kept(self):
        real = [
            ("backnotprop/plannotator", "The workspace to stay in the loop and on top of agents"),
            ("microsoft/terminal", "The new Windows Terminal and the original Windows console host"),
            ("anthropics/claude-code", "Claude Code is an agentic coding tool that lives in your terminal"),
            ("o/winget-mcp", "MCP server to install apps with winget on Windows 11"),
            ("nishant-tiwari24/cracked", "Skills for getting hired. Company-wise mock interviews, OAs with hidden tests"),
        ]
        for name, desc in real:
            self.assertFalse(collectors.looks_like_lure(name, desc), name)

    def test_trending_drops_lures(self):
        from pathlib import Path
        from unittest import mock
        from ai_radar.config import Config
        page = ('<article class="Box-row"><h2 class="h3"><a href="/CliBranchLong/claude-code-win">x</a></h2>'
                '<p class="col-9 color-fg-muted">Anthropic Claude Code - AI coding assistant on Windows 10/11</p>'
                '<span>12 stars today</span></article>')
        cfg = Config(home=Path("/nonexistent"))
        cfg.trending_languages = []
        with mock.patch.object(collectors, "http_get", return_value=page.encode()):
            self.assertEqual(collectors.github_trending(cfg), [])


def it(i, cat, score):
    return {"id": i, "category": cat, "score": score}


class TestDiverseTop(unittest.TestCase):
    def test_at_most_two_per_category_then_fill(self):
        items = [it(f"t{i}", "tool", 60 - i) for i in range(6)] + [it("a1", "article", 40), it("r1", "research", 39)]
        top = sync.diverse_top(items, 6, per_category=2)
        self.assertEqual([x["id"] for x in top], ["t0", "t1", "a1", "r1", "t2", "t3"])

    def test_keeps_score_order_when_already_diverse(self):
        items = [it("m", "model", 50), it("a", "article", 45), it("t", "tool", 40)]
        self.assertEqual([x["id"] for x in sync.diverse_top(items, 6)], ["m", "a", "t"])


if __name__ == "__main__":
    unittest.main()
