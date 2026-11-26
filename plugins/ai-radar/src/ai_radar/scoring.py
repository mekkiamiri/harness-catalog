"""Item scoring, without any LLM.

score = freshness (0-30) + popularity (0-25) + resonance (0-45) + emergence (0-10)
        + validation (15 when the host's model judged the item relevant when writing its brief)

Resonance counts *independent* sources mentioning the same name (repo or model) in the
last days: the "everyone talks about it and I have never heard of it" signal.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone

# Words too generic to be searched as a proper name.
GENERIC = {
    "agent", "agents", "ai", "llm", "llms", "mcp", "skills", "skill", "awesome", "server",
    "claude", "chat", "code", "model", "models", "tools", "tool", "app", "api", "sdk", "cli",
    "free", "preview", "instruct", "base", "chat", "mini", "flash", "pro", "turbo", "lite",
    "rag", "demo", "test", "open", "openai", "google", "anthropic", "meta", "the", "and",
}


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[-_/.:]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def search_name(item: dict) -> str | None:
    """Distinctive name to look for elsewhere, or None when too generic."""
    if item["category"] == "tool":
        raw = item["title"].split("/")[-1]
    elif item["category"] == "model":
        raw = item["id"].split(":", 1)[1].split("/")[-1]
    else:
        return None
    name = normalize(raw)
    words = [w for w in name.split() if w not in GENERIC]
    if not words or len(name) < 4 or all(len(w) < 3 for w in words):
        return None
    if name.startswith("awesome "):
        return None
    return name


def model_key(item_id: str) -> str | None:
    """'model:google/gemini-4' and 'model-hf:google/Gemini-4' -> 'gemini 4'; None for non-models."""
    if not item_id.startswith(("model:", "model-hf:")):
        return None
    return normalize(item_id.split(":", 1)[1].split("/")[-1])


def age_days(item: dict, now: datetime) -> float:
    ref = item.get("published_at") or item["first_seen"]
    try:
        dt = datetime.fromisoformat(ref.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return 0.0
    return max(0.0, (now - dt).total_seconds() / 86400)


def popularity(item: dict) -> float:
    s = item.get("signals", {})
    cat = item["category"]
    if cat == "tool":
        return 25 * min(1.0, math.log10(1 + s.get("stars_per_day", 0)) / 2.5)
    if cat == "model":
        if item["source"] == "OpenRouter":
            return 15 + (5 if s.get("free") else 0)
        return 25 * min(1.0, math.log10(1 + s.get("likes", 0)) / 3)
    if cat == "research":
        return 25 * min(1.0, math.log10(1 + s.get("votes", 0)) / 2)
    return 10 + 15 * min(1.0, math.log10(1 + s.get("points", 0)) / 3)


def awesome_theme(item: dict) -> str | None:
    name = normalize(item["title"].split("/")[-1])
    if not name.startswith("awesome "):
        return None
    rest = [w for w in name.split()[1:] if w not in GENERIC]
    return rest[0] if rest else None


def score_items(items: list[dict], now: datetime | None = None) -> list[tuple[str, float, dict]]:
    """Return [(id, score, enriched signals)] for every item."""
    now = now or datetime.now(timezone.utc)

    # Corpus: (source, id, normalized text) of the items of the last 7 days.
    corpus = [
        (it["source"], it["id"], " " + normalize(f"{it['title']} {it.get('description', '')}") + " ")
        for it in items
        if age_days(it, now) <= 7 or it["category"] in {"article", "research"}
    ]

    # Emergence: several "awesome-X" lists on the same theme X.
    themes = defaultdict(list)
    for it in items:
        t = awesome_theme(it)
        if t:
            themes[t].append(it["id"])

    results = []
    for it in items:
        signals = dict(it.get("signals", {}))
        sources = set()
        name = search_name(it)
        if name:
            pattern = " " + name + " "
            key = model_key(it["id"])
            for source, iid, text in corpus:
                if key and model_key(iid) == key:
                    continue  # the same model listed in another catalogue is not an independent mention
                if iid != it["id"] and source != it["source"] and pattern in text:
                    sources.add(source)
        signals["resonance"] = sorted(sources)

        t = awesome_theme(it)
        emergence = 10 if t and len(themes[t]) >= 2 else 0
        if emergence:
            signals["emergence"] = f"{len(themes[t])} recent \"awesome {t}\" lists"

        f = 30 * math.exp(-age_days(it, now) / 7)
        p = popularity(it)
        r = min(45, 15 * len(sources))
        v = 15 if it.get("relevant") else 0
        n = 25 if signals.get("network") or signals.get("watched") else 0  # someone or a repo you follow
        score = f + p + r + emergence + v + n
        signals["score_detail"] = {
            "freshness": round(f, 1), "popularity": round(p, 1),
            "resonance": r, "emergence": emergence, "validation": v,
        }
        if n:
            signals["score_detail"]["network"] = n
        results.append((it["id"], score, signals))
    return results
