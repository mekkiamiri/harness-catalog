import unittest
from datetime import datetime, timedelta, timezone

from ai_radar import scoring
from ai_radar.collectors import filter_spam, safe_url

NOW = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)


def item(id, category, title, source, description="", days=0, **signals):
    date = (NOW - timedelta(days=days)).isoformat()
    return {"id": id, "category": category, "title": title, "source": source, "description": description,
            "published_at": date, "first_seen": date, "signals": signals, "brief": ""}


class TestScoring(unittest.TestCase):
    def test_resonance_counts_independent_sources(self):
        items = [
            item("model:google/gemini-4-carbon", "model", "Google: Gemini 4 Carbon", "OpenRouter"),
            item("article:a", "article", "Gemini 4 Carbon is out", "Latent Space"),
            item("article:b", "article", "Hands-on with gemini-4-carbon", "Simon Willison"),
            item("article:c", "article", "Something else", "TLDR AI"),
        ]
        signals = {i: s for i, _, s in scoring.score_items(items, NOW)}
        self.assertEqual(signals["model:google/gemini-4-carbon"]["resonance"], ["Latent Space", "Simon Willison"])

    def test_generic_names_are_not_searched(self):
        self.assertIsNone(scoring.search_name(item("repo:x/agent", "tool", "x/agent", "GitHub")))
        self.assertEqual(scoring.search_name(item("repo:n/hermes-agent", "tool", "n/hermes-agent", "GitHub")), "hermes agent")

    def test_awesome_lists_signal_emergence(self):
        items = [item("repo:a/awesome-rea", "tool", "a/awesome-rea", "GitHub"),
                 item("repo:b/awesome-rea-tools", "tool", "b/Awesome-REA-tools", "GitHub")]
        signals = {i: s for i, _, s in scoring.score_items(items, NOW)}
        self.assertIn("emergence", signals["repo:a/awesome-rea"])

    def test_freshness_decays(self):
        s = {i: sc for i, sc, _ in scoring.score_items(
            [item("paper:1", "research", "P1", "HF", days=0, votes=10), item("paper:2", "research", "P2", "HF", days=20, votes=10)], NOW)}
        self.assertGreater(s["paper:1"], s["paper:2"])

    def test_only_relevant_briefs_get_the_validation_bonus(self):
        a = dict(item("paper:1", "research", "P1", "HF", votes=10), brief="unverified", relevant=0)
        b = dict(item("paper:2", "research", "P2", "HF", votes=10), brief="**What it is**: ...", relevant=1)
        s = {i: sc for i, sc, _ in scoring.score_items([a, b], NOW)}
        self.assertEqual(s["paper:2"] - s["paper:1"], 15)


class TestUrls(unittest.TestCase):
    def test_only_http_links_are_kept(self):
        self.assertEqual(safe_url("javascript:alert(1)"), "")
        self.assertEqual(safe_url("file:///etc/passwd"), "")
        self.assertEqual(safe_url(" https://x.org/a "), "https://x.org/a")


class TestSpam(unittest.TestCase):
    def test_star_farms_are_dropped(self):
        repos = {f"account{i}/ai--manus2.0": {"description": "x"} for i in range(4)}
        repos |= {f"c{i}/blender-ai-copilot-{i}": {"description": f"d{i}"} for i in range(3)}
        repos["NousResearch/hermes-agent"] = {"description": "The agent that grows with you"}
        self.assertEqual(list(filter_spam(repos)), ["NousResearch/hermes-agent"])


if __name__ == "__main__":
    unittest.main()


class TestModelDuplicates(unittest.TestCase):
    def test_same_model_in_two_catalogues_is_not_resonance(self):
        items = [item("model:acme/nova-2", "model", "Acme: Nova 2", "OpenRouter"),
                 item("model-hf:acme/nova-2", "model", "acme/nova-2", "Hugging Face (trending)")]
        signals = {i: s for i, _, s in scoring.score_items(items, NOW)}
        self.assertEqual(signals["model:acme/nova-2"]["resonance"], [])
        self.assertEqual(signals["model-hf:acme/nova-2"]["resonance"], [])


class TestRepos(unittest.TestCase):
    def test_github_links_are_extracted_from_newsletters(self):
        from ai_radar.repos import github_repos_in
        text = '<a href="https://github.com/acme/orbit-agent">x</a> see github.com/acme/orbit-agent.git and https://github.com/features/copilot'
        self.assertEqual(github_repos_in(text), ["acme/orbit-agent"])

    def test_contribution_score_rewards_entry_tickets_and_focus(self):
        from ai_radar.repos import contrib_score
        base = {"stars_per_day": 10, "contrib": {"good_first_issues": 0, "days_since_push": 2}}
        better = {"stars_per_day": 10, "mentioned_by": ["Latent Space"],
                  "contrib": {"good_first_issues": 6, "org_backed": True, "days_since_push": 2, "focus_match": ["mcp"]}}
        self.assertGreater(contrib_score(better), contrib_score(base) + 50)
