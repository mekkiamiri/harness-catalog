"""Language and framework trends. No LLM.

Two independent signals:
- what new AI repos are written in, and which frameworks they use (daily, from collected items, star-weighted);
- PYPL: share of Google searches for tutorials per language (monthly, long-term interest).
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from datetime import timedelta

from .collectors import http_get
from .store import Store, iso, now

# Topics that name a framework or SDK rather than a domain.
FRAMEWORK_TOPICS = {
    "langchain", "langchain4j", "langgraph", "llamaindex", "spring-ai", "spring-boot", "adk", "google-adk",
    "crewai", "autogen", "semantic-kernel", "dspy", "pydantic-ai", "openai-agents", "agents-sdk", "mastra",
    "vercel-ai-sdk", "fastapi", "fastmcp", "mcp-sdk", "transformers", "pytorch", "jax", "mlx", "vllm",
    "ollama", "llama-cpp", "quarkus", "micronaut", "nextjs", "react", "tauri", "deno", "bun", "smolagents",
    "haystack", "langflow", "n8n", "dify", "claude-agent-sdk", "a2a", "koog",
}


def repo_languages(store: Store, days: int = 7) -> dict:
    """Star-weighted share of languages among new AI repos, current window vs the previous one."""
    def window(start_days: int, end_days: int) -> Counter:
        rows = store.conn.execute(
            "SELECT signals FROM items WHERE category = 'tool' AND first_seen >= ? AND first_seen < ? AND status != 'ignored'",
            (iso(now() - timedelta(days=start_days)), iso(now() - timedelta(days=end_days))),
        )
        c: Counter = Counter()
        for (sig,) in rows:
            s = _json(sig)
            if s.get("language"):
                c[s["language"]] += max(1, s.get("stars", 0))
        return c

    cur, prev = window(days, 0), window(2 * days, days)
    tot_c, tot_p = sum(cur.values()) or 1, sum(prev.values()) or 1
    rows = [{"language": lang, "share": round(100 * n / tot_c, 1),
             "previous_share": round(100 * prev.get(lang, 0) / tot_p, 1) if prev else None}
            for lang, n in cur.most_common(12)]
    return {"window_days": days, "has_previous_window": bool(prev), "languages": rows}


def frameworks(store: Store, days: int = 14) -> list[dict]:
    rows = store.conn.execute(
        "SELECT signals FROM items WHERE category = 'tool' AND first_seen >= ? AND status != 'ignored'",
        (iso(now() - timedelta(days=days)),),
    )
    c: Counter = Counter()
    repos: Counter = Counter()
    for (sig,) in rows:
        s = _json(sig)
        for t in s.get("topics", []):
            if t in FRAMEWORK_TOPICS:
                c[t] += max(1, s.get("stars", 0))
                repos[t] += 1
    return [{"framework": f, "stars": n, "repos": repos[f]} for f, n in c.most_common(15)]


def pypl() -> dict:
    """Latest PYPL shares and change over 12 months (percentage points)."""
    js = http_get("https://pypl.github.io/PYPL/All.js").decode("utf-8", "replace")
    header = re.search(r"\['Date',(.*?)\]", js, re.S).group(1)
    langs = re.findall(r"'([^']+)'", header)
    rows = re.findall(r"\[new Date\((\d+),(\d+),\d+\),([^\]]+)\]", js)
    if len(rows) < 13:
        raise RuntimeError("unexpected PYPL format")

    def parse(r):
        vals = ast.literal_eval("[" + r[2].replace("\n", "") + "]")
        return f"{r[0]}-{int(r[1]) + 1:02d}", dict(zip(langs, vals))

    by_month = dict(parse(r) for r in rows)  # the source repeats some months: keep the last value
    month = max(by_month)
    last = by_month[month]
    y, m = month.split("-")
    year_ago = by_month.get(f"{int(y) - 1}-{m}", {})
    ranking = sorted(last.items(), key=lambda kv: -kv[1])[:12]
    return {"month": month, "languages": [
        {"language": lang, "share": round(100 * v, 1),
         "change_12m": round(100 * (v - year_ago[lang]), 1) if lang in year_ago else None}
        for lang, v in ranking]}


def language_trends(store: Store) -> dict:
    out = {"new_ai_repos": repo_languages(store), "frameworks": frameworks(store)}
    try:
        out["pypl"] = pypl()
    except Exception as e:  # a failing source never blocks the rest
        out["pypl_error"] = str(e)[:200]
    return out


def _json(s: str) -> dict:
    import json
    try:
        return json.loads(s or "{}")
    except ValueError:
        return {}
