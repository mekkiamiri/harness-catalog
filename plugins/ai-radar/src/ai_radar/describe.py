"""Readable descriptions for repos, without any LLM.

- A repo with no (or a one-line) description gets the first real paragraph of its README, read from
  raw.githubusercontent.com (no API quota).
- Every item gets a "for you" verdict from the user's focus topics (config [repos] focus).
"""

from __future__ import annotations

import re
from datetime import timedelta

from .collectors import clean, http_get
from .config import Config
from .store import Store, iso, now

SHORT = 60          # a description shorter than this explains nothing
BUDGET = 60         # README downloads per run
README_NAMES = ("README.md", "readme.md", "Readme.md", "README.rst", "README")


def readme_summary(text: str, limit: int = 420) -> str:
    """First paragraphs of a README that read as prose: no badges, images, headings, code or tables."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    out = []
    for block in re.split(r"\n\s*\n", text):
        b = block.strip()
        if not b or b.startswith(("#", "|", ">", "---", "===", "[!", "* * *")) or re.match(r"^[-=]{3,}$", b):
            continue
        b = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", b)                 # images / badges
        b = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", " ", b)
        b = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", b)               # links -> text
        b = re.sub(r"<[^>]+>", " ", b)                               # html
        b = re.sub(r"[*_`]+", "", b)
        b = re.sub(r"^\s*[-*+]\s+", "", b, flags=re.M)
        b = clean(b, 1000)
        if len(b) < 40 or len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", b)) < 6:
            continue                                                 # badges line, a lone link, a title
        if b.count("|") >= 3 or b.count("·") >= 3 or re.match(
                r"(?i)(for more information|see also|read more|check out|table of contents|documentation:|follow |join )", b):
            continue                                                 # language picker, nav links, pointers
        out.append(b)
        if sum(len(x) for x in out) >= limit:
            break
    s = " ".join(out)
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + "…"


def fetch_readme(full_name: str) -> str:
    for name in README_NAMES:
        try:
            return http_get(f"https://raw.githubusercontent.com/{full_name}/HEAD/{name}", tries=1).decode(
                "utf-8", "replace")
        except Exception:
            continue
    return ""


def enrich_descriptions(cfg: Config, store: Store, budget: int = BUDGET) -> dict:
    """Fill signals.readme for recent repos whose description is missing or too short."""
    since = iso(now() - timedelta(days=2))
    rows = store.conn.execute(
        "SELECT id, title, description, signals FROM items WHERE id LIKE 'repo:%' AND last_seen >= ?"
        " AND status != 'ignored' ORDER BY score DESC", (since,)).fetchall()
    import json
    done = 0
    for r in rows:
        sig = json.loads(r["signals"] or "{}")
        if "readme" in sig or len(r["description"] or "") >= SHORT:
            continue
        if done >= budget:
            break
        done += 1
        sig["readme"] = readme_summary(fetch_readme(r["title"]))  # "" = looked, nothing usable
        store.conn.execute("UPDATE items SET signals = ? WHERE id = ?", (json.dumps(sig, ensure_ascii=False), r["id"]))
    store.commit()
    return {"readmes_read": done}


def for_you(item: dict, focus: list[str]) -> dict:
    """yes / maybe / no from the focus topics found in the name, description, README and topics."""
    s = item.get("signals") or {}
    text = " ".join([item.get("title", ""), item.get("description", ""), s.get("readme", ""),
                     " ".join(s.get("topics") or []), s.get("language") or ""]).lower()
    text = re.sub(r"[-_/]", " ", text)
    hits = [f for f in focus if re.search(rf"\b{re.escape(f.lower())}\b", text)]
    level = "yes" if len(hits) >= 2 else "maybe" if hits else "no"
    return {"level": level, "why": hits}
