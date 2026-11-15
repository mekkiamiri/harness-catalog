"""Repos to watch and contribute to. No LLM.

Signals per repository: mentioned by newsletters, stars per day, open "good first issue" and
"help wanted" tickets, backed by an organization, recent activity, match with the user's focus topics.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from .collectors import http_json, safe_url
from .config import Config
from .store import Store, iso, now

GITHUB_LINK = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
NOT_REPOS = {"orgs", "features", "sponsors", "topics", "marketplace", "settings", "login", "about", "pricing",
             "collections", "trending", "apps", "site", "enterprise", "readme", "security", "customer-stories"}


def github_repos_in(text: str, limit: int = 10) -> list[str]:
    """owner/name of the GitHub repositories linked in a text (HTML or Markdown)."""
    found: list[str] = []
    for owner, name in GITHUB_LINK.findall(text or ""):
        name = re.sub(r"\.git$", "", name).rstrip(".")
        if owner.lower() in NOT_REPOS or not name:
            continue
        full = f"{owner}/{name}"
        if full.lower() not in {f.lower() for f in found}:
            found.append(full)
        if len(found) >= limit:
            break
    return found


def _headers(cfg: Config) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if cfg.github_token:
        h["Authorization"] = f"Bearer {cfg.github_token}"
    return h


def _repo_item(r: dict, mentioned_by: list[str]) -> dict:
    created = r.get("created_at") or iso(now())
    age = max(1.0, (now() - datetime.fromisoformat(created.replace("Z", "+00:00"))).total_seconds() / 86400)
    return {
        "id": f"repo:{r['full_name'].lower()}",
        "category": "tool",
        "title": r["full_name"],
        "url": safe_url(r.get("html_url")),
        "source": "Newsletter mention",
        "description": (r.get("description") or "")[:400],
        "published_at": created,
        "signals": {"stars": r.get("stargazers_count", 0),
                    "stars_per_day": round(r.get("stargazers_count", 0) / age, 1),
                    "topics": (r.get("topics") or [])[:8], "language": r.get("language"),
                    "mentioned_by": mentioned_by},
    }


def enrich(cfg: Config, store: Store) -> dict:
    """Add repos mentioned by newsletters, then compute contribution signals for the best candidates."""
    since = iso(now() - timedelta(days=7))
    mentions: dict[str, set[str]] = {}
    for row in store.conn.execute("SELECT source, signals FROM items WHERE category = 'article' AND first_seen >= ?", (since,)):
        for full in json.loads(row["signals"] or "{}").get("github_repos", []):
            mentions.setdefault(full.lower(), set()).add(row["source"])

    headers = _headers(cfg)
    # Separate budgets (GitHub calls per run): newsletter repos, then contribution analysis.
    # Issue searches count against the search limit (30/min with a token): collection waits if needed.
    budget = 30 if cfg.github_token else 5
    added = 0
    for full, sources in sorted(mentions.items(), key=lambda kv: -len(kv[1])):
        item_id = f"repo:{full}"
        existing = store.get(item_id)
        if existing:
            sig = existing["signals"] | {"mentioned_by": sorted(sources)}
            store.conn.execute("UPDATE items SET signals = ? WHERE id = ?", (json.dumps(sig), item_id))
            continue
        if budget <= 0:
            break
        budget -= 1
        try:
            r = http_json(f"https://api.github.com/repos/{full}", headers)
        except Exception:
            continue
        if r.get("archived") or r.get("fork"):
            continue
        store.upsert(_repo_item(r, sorted(sources)))
        added += 1
    store.commit()

    # Contribution signals for the best recent repos (and every mentioned one).
    rows = store.conn.execute(
        "SELECT id, title, signals, score FROM items WHERE id LIKE 'repo:%' AND status != 'ignored' AND last_seen >= ?"
        " ORDER BY score DESC LIMIT 80", (iso(now() - timedelta(days=14)),)).fetchall()
    focus = [f.lower() for f in cfg.repos_focus]
    budget = 40 if cfg.github_token else 6  # 2 calls per repo

    def priority(row) -> tuple:
        sig = json.loads(row["signals"] or "{}")
        text = " ".join([row["title"], " ".join(sig.get("topics", [])), sig.get("language") or ""]).lower()
        return (-len(sig.get("mentioned_by") or []), -int(any(f in text for f in focus)), -(row["score"] or 0))

    rows = sorted(rows, key=priority)
    checked = 0
    for row in rows:
        sig = json.loads(row["signals"] or "{}")
        contrib = sig.get("contrib") or {}
        fresh = contrib.get("checked_at", "") >= iso(now() - timedelta(days=3))
        if not fresh and budget >= 2:
            budget -= 2
            full = row["title"]
            try:
                r = http_json(f"https://api.github.com/repos/{full}", headers)
                q = urllib.parse.quote(f'repo:{full} is:issue is:open label:"good first issue"')
                gfi = http_json(f"https://api.github.com/search/issues?q={q}&per_page=1", headers).get("total_count", 0)
                q = urllib.parse.quote(f'repo:{full} is:issue is:open label:"help wanted"')
                hw = http_json(f"https://api.github.com/search/issues?q={q}&per_page=1", headers).get("total_count", 0)
                pushed = r.get("pushed_at") or ""
                contrib = {
                    "good_first_issues": gfi, "help_wanted": hw,
                    "org_backed": (r.get("owner") or {}).get("type") == "Organization",
                    "days_since_push": (now() - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days if pushed else None,
                    "checked_at": iso(now()),
                }
                checked += 1
            except Exception:
                continue
        if not contrib:
            continue
        text = " ".join([row["title"], " ".join(sig.get("topics", [])), sig.get("language") or ""]).lower()
        contrib["focus_match"] = sorted({f for f in focus if f in text})
        sig["contrib"] = contrib
        sig["contrib_score"] = contrib_score(sig)
        store.conn.execute("UPDATE items SET signals = ? WHERE id = ?", (json.dumps(sig, ensure_ascii=False), row["id"]))
    store.commit()
    return {"added_from_newsletters": added, "contrib_checked": checked}


def contrib_score(sig: dict) -> float:
    """0-100: growth (25), newsletters (20), entry tickets (20), organization (10), activity (10), focus (15)."""
    import math
    c = sig.get("contrib") or {}
    growth = 25 * min(1.0, math.log10(1 + sig.get("stars_per_day", 0)) / 2.5)
    news = min(20, 10 * len(sig.get("mentioned_by") or []))
    entry = 20 * min(1.0, (c.get("good_first_issues", 0) + 0.5 * c.get("help_wanted", 0)) / 5)
    org = 10 if c.get("org_backed") else 0
    days = c.get("days_since_push")
    active = 10 if days is not None and days <= 7 else 5 if days is not None and days <= 30 else 0
    focus = 15 if c.get("focus_match") else 0
    return round(growth + news + entry + org + active + focus, 1)


def to_watch(store: Store, limit: int = 15) -> list[dict]:
    rows = store.conn.execute(
        "SELECT * FROM items WHERE id LIKE 'repo:%' AND status != 'ignored' AND signals LIKE '%contrib_score%'")
    items = [Store._item(r) for r in rows]
    items.sort(key=lambda it: -it["signals"].get("contrib_score", 0))
    return items[:limit]
