"""Build the public demo dashboard (harness-catalog/docs/ai-radar/index.html) from FICTIONAL data only.

Never uses a real ~/.ai-radar: results stay private, only the code is public.
Usage: uv run python scripts/build_demo.py
"""

from __future__ import annotations

import json
import os
import random
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent.parent / "docs" / "ai-radar" / "index.html"  # served by GitHub Pages from the catalog

random.seed(7)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AI_RADAR_HOME"] = tmp
        from ai_radar import render, scoring
        from ai_radar.config import load_config
        from ai_radar.store import Store, iso, now

        cfg = load_config()
        store = Store(cfg.db_path)
        t = now()

        def item(id, category, title, source, desc, days, brief="", **signals):
            store.upsert({"id": id, "category": category, "title": title, "url": "https://example.com/" + id.split(":")[1],
                          "source": source, "description": desc, "published_at": iso(t - timedelta(days=days)),
                          "signals": signals})
            store.conn.execute("UPDATE items SET first_seen = ? WHERE id = ?", (iso(t - timedelta(days=days)), id))
            if brief:
                store.set_field(id, "brief", brief)
                store.set_field(id, "relevant", 1)

        item("repo:demo/orbit-agent", "tool", "demo/orbit-agent", "GitHub",
             "A self-hosted agent that writes its own skills (fictional example).", 1,
             "**What it is**: a fictional agent runtime used to show the dashboard.\n**Why it matters**: three independent "
             "sources mentioned it within two days.\n**Key ideas**: persistent memory; skills it improves itself; scheduled tasks.\n"
             "**Lab**: yes — wrap one of your scripts as a skill.",
             stars=2140, stars_per_day=356.7, topics=["agents", "mcp"], language="Python")
        item("repo:demo/mcp-lens", "tool", "demo/mcp-lens", "GitHub", "Inspect and replay MCP traffic (fictional).", 2,
             stars=640, stars_per_day=160.0, topics=["mcp"], language="TypeScript")
        item("repo:demo/awesome-lens-tools", "tool", "demo/awesome-lens-tools", "GitHub", "Curated list (fictional).", 3,
             stars=380, stars_per_day=63.3, language=None)
        item("repo:other/awesome-lens", "tool", "other/awesome-lens", "GitHub", "Another curated list (fictional).", 2,
             stars=210, stars_per_day=52.5, language=None)
        item("repo:demo/jvm-agents", "tool", "demo/jvm-agents", "GitHub", "Agents on the JVM (fictional).", 4,
             stars=190, stars_per_day=23.8, topics=["agents", "spring-ai"], language="Java")
        item("model:acme/nova-2", "model", "Acme: Nova 2", "OpenRouter", "A new long-context model (fictional).", 1,
             context=1000000, free=True)
        item("model-hf:acme/nova-2-mini", "model", "acme/nova-2-mini", "Hugging Face (trending)", "text-generation", 3, likes=820)
        item("paper:0001", "research", "Recall Beats Rereading: Spaced Questions for Agent Memory", "HF Daily Papers",
             "A fictional paper used for the demo.", 1, votes=96)
        item("paper:0002", "research", "Small Judges, Big Agents", "HF Daily Papers", "Fictional.", 2, votes=41)
        for i, (src, title) in enumerate([
            ("Example Newsletter", "Orbit Agent and Nova 2: what changed this week"),
            ("Example Blog", "Hands-on with orbit-agent"),
            ("Example News", "Nova 2 is out, with a free tier"),
            ("Example Newsletter", "Inspecting MCP traffic with mcp-lens"),
        ]):
            item(f"article:{i}", "article", title, src, "", 1, points=random.randint(60, 300))
        # Fictional contribution signals for the Repos tab.
        from ai_radar.repos import contrib_score
        for rid, contrib, mentioned in [
            ("repo:demo/orbit-agent", {"good_first_issues": 7, "help_wanted": 3, "org_backed": True, "days_since_push": 0,
                                       "focus_match": ["agents", "mcp"]}, ["Example Newsletter", "Example Blog"]),
            ("repo:demo/mcp-lens", {"good_first_issues": 2, "help_wanted": 0, "org_backed": False, "days_since_push": 3,
                                    "focus_match": ["mcp"]}, ["Example Newsletter"]),
            ("repo:demo/jvm-agents", {"good_first_issues": 4, "help_wanted": 1, "org_backed": True, "days_since_push": 1,
                                      "focus_match": ["java", "spring"]}, []),
        ]:
            sig = store.get(rid)["signals"] | {"contrib": contrib, "mentioned_by": mentioned}
            sig["contrib_score"] = contrib_score(sig)
            store.conn.execute("UPDATE items SET signals = ? WHERE id = ?", (json.dumps(sig), rid))
        store.commit()
        for item_id, score, signals in scoring.score_items(store.all_items()):
            store.set_score(item_id, score, signals)

        today = t.date()
        events = [
            ("conf:democonf-paris-2027", "conference", "DemoConf Paris 2027", False, 120, 12, "https://example.com/cfp/democonf"),
            ("conf:agentdays-2027", "conference", "AgentDays 2027", False, 160, 40, "https://example.com/cfp/agentdays"),
            ("conf:llm-summit-online", "conference", "LLM Summit Online", True, 9, None, ""),
            ("meetup:https://example.com/m/1", "meetup", "Building MCP servers (online meetup)", True, 3, None, ""),
        ]
        for id, kind, name, online, start, cfp, cfp_url in events:
            store.upsert_event({"id": id, "kind": kind, "name": name, "url": "https://example.com/event",
                                "start_at": (today + timedelta(days=start)).isoformat(), "online": online,
                                "location": "Online" if online else "Example City", "languages": ["english"],
                                "tags": ["call-for-speakers"] if kind == "meetup" else [], "cfp_url": cfp_url,
                                "cfp_close": (today + timedelta(days=cfp)).isoformat() if cfp else None,
                                "source": "demo", "watched": name.startswith("DemoConf")})
        store.record_notification("demo:1", "★ CFP DemoConf Paris 2027 closes in 12 days — demo data")
        store.record_notification("demo:2", "2 new online events: LLM Summit Online, Building MCP servers")
        run = store.start_run()
        store.end_run(run, {"new": 13, "seen": 13, "sources": {}, "errors": {}, "trends": {
            "new_ai_repos": {"window_days": 7, "has_previous_window": True, "languages": [
                {"language": "Python", "share": 44.0, "previous_share": 39.5},
                {"language": "TypeScript", "share": 33.1, "previous_share": 35.0},
                {"language": "Rust", "share": 12.4, "previous_share": 10.2},
                {"language": "Java", "share": 6.0, "previous_share": 7.1}]},
            "frameworks": [{"framework": "mcp-sdk", "stars": 1800, "repos": 4},
                           {"framework": "spring-ai", "stars": 190, "repos": 1}],
            "pypl": {"month": "demo", "languages": [
                {"language": "Python", "share": 30.0, "change_12m": 1.5},
                {"language": "Java", "share": 14.0, "change_12m": -0.4}]}}})
        store.commit()

        path = render.dashboard(cfg, store)
        banner = (
            '<h1>AI radar <small style="font-size:13px;color:var(--hot)">demo — fictional data</small></h1>'
            '<p class="meta" style="margin:6px 0 0">Open source · '
            '<a href="https://github.com/mekkiamiri/harness-catalog/tree/main/plugins/ai-radar">source on GitHub</a> · '
            'install in Claude Code: <code>/plugin marketplace add mekkiamiri/harness-catalog</code> then '
            '<code>/plugin install ai-radar@harness-catalog</code></p>'
        )
        html = path.read_text(encoding="utf-8").replace("<h1>AI radar</h1>", banner)
        store.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
