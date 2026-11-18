"""Item collectors: fetch what is new, without any LLM call.

Each collector returns a list of dicts in the format expected by Store.upsert.
A failing source never blocks the others.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .config import Config

USER_AGENT = "ai-radar/0.1 (+https://github.com/mekkiamiri/harness-catalog/tree/main/plugins/ai-radar)"
TIMEOUT = 20


# Network breaker: after this many requests in a row without any server answer (timeout, DNS, refused),
# the rest of the run fails fast instead of waiting
# TIMEOUT seconds per request (a run started before the network was up once lasted 8 hours).
NETWORK_DOWN_AFTER = 5
_TIMEOUTS_IN_A_ROW = 0

# Partial failures of a collector that still returned items (e.g. one RSS feed out of twenty): name -> message.
WARNINGS: dict[str, str] = {}


class NetworkDown(RuntimeError):
    pass


def reset_network_state() -> None:
    global _TIMEOUTS_IN_A_ROW
    _TIMEOUTS_IN_A_ROW = 0
    WARNINGS.clear()


def network_down() -> bool:
    """True when the breaker tripped during this run: the run is incomplete and must not count as fresh."""
    return _TIMEOUTS_IN_A_ROW >= NETWORK_DOWN_AFTER


def wait_for_network(tries: int = 4, pause: float = 1200, url: str = "https://api.github.com") -> bool:
    """True as soon as `url` answers (any HTTP status counts); else up to `tries` attempts, `pause` seconds apart."""
    for attempt in range(tries):
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT}),
                                   timeout=10).close()
            return True
        except urllib.error.HTTPError:
            return True  # the server answered: the network is up
        except Exception:  # timeout, DNS, refused, captive portal sending a malformed answer...
            if attempt < tries - 1:
                time.sleep(max(pause, 0))
    return False


def http_get(url: str, headers: dict | None = None, data: bytes | None = None, tries: int = 3,
             timeout: int = TIMEOUT) -> bytes:
    global _TIMEOUTS_IN_A_ROW
    if _TIMEOUTS_IN_A_ROW >= NETWORK_DOWN_AFTER:
        raise NetworkDown(f"network unreachable ({NETWORK_DOWN_AFTER} failed requests in a row): skipped")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            _TIMEOUTS_IN_A_ROW = 0
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            if not isinstance(e, urllib.error.HTTPError):
                # no answer from a server (timeout, DNS failure, refused, TLS): counts towards "network down"
                _TIMEOUTS_IN_A_ROW += 1
                raise
            _TIMEOUTS_IN_A_ROW = 0  # the server answered
            # Retry only on rate limits (GitHub without a token: 10 searches per minute; Reddit RSS).
            rate_limited = e.code == 429 or (e.code == 403 and e.headers.get("X-RateLimit-Remaining") == "0")
            if rate_limited and attempt < tries - 1:
                time.sleep(_retry_after(e.headers))
                continue
            raise
    raise RuntimeError("unreachable: " + url)


def _retry_after(headers) -> int:
    value = headers.get("Retry-After", "")
    if value.isdigit():
        return min(int(value), 90)
    reset = headers.get("X-RateLimit-Reset", "")
    if reset.isdigit():
        return max(1, min(int(reset) - int(time.time()) + 1, 90))
    return 30


def safe_url(url: str | None) -> str:
    """Only http(s) links are stored: a feed could carry javascript: or file: URLs."""
    url = (url or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else ""


def http_json(url: str, headers: dict | None = None, data: bytes | None = None):
    return json.loads(http_get(url, headers, data))


def clean(text: str | None, limit: int = 400) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


# --- Tools: new GitHub repos gaining stars fast ------------------------------
def github_repos(cfg: Config) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=cfg.window_days)).date().isoformat()
    headers = {"Accept": "application/vnd.github+json"}
    if cfg.github_token:
        headers["Authorization"] = f"Bearer {cfg.github_token}"
    seen: dict[str, dict] = {}
    queries = [f"topic:{t}" for t in cfg.github_topics]
    # Many repos have no topics: also search names and descriptions.
    queries += [f"{k} in:name,description" for k in cfg.github_keywords]
    errors = []
    for criterion in queries:
        q = f"{criterion} created:>={since} stars:>={cfg.github_min_stars}"
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "sort": "stars", "order": "desc", "per_page": 30}
        )
        try:
            for r in http_json(url, headers).get("items", []):
                seen[r["full_name"]] = r
        except Exception as e:  # one failing query must not lose the others
            errors.append(f"{criterion}: {e}")
    if errors and not seen:
        raise RuntimeError("; ".join(errors[:3]))
    # Several recent "awesome-X" lists signal an emerging category (the REA case).
    q = f"awesome in:name created:>={since} stars:>={cfg.github_min_stars}"
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": q, "sort": "stars", "order": "desc", "per_page": 30}
    )
    try:
        for r in http_json(url, headers).get("items", []):
            seen.setdefault(r["full_name"], r)
    except Exception:
        pass

    items = []
    # Without a token the users API allows 60 calls/hour: check only the most starred owners.
    max_checks = 200 if cfg.github_token else 40
    for name, r in drop_lure_accounts(filter_spam(seen), headers, max_checks).items():
        created = r["created_at"]
        age = max(1.0, (datetime.now(timezone.utc) - _parse_iso(created)).total_seconds() / 86400)
        items.append(
            {
                "id": f"repo:{name.lower()}",
                "category": "tool",
                "title": name,
                "url": safe_url(r["html_url"]),
                "source": "GitHub",
                "description": clean(r.get("description")),
                "published_at": created,
                "signals": {
                    "stars": r["stargazers_count"],
                    "stars_per_day": round(r["stargazers_count"] / age, 1),
                    "topics": r.get("topics", [])[:8],
                    "language": r.get("language"),
                    "awesome": name.split("/")[-1].lower().startswith("awesome"),
                },
            }
        )
    return items


def filter_spam(repos: dict[str, dict]) -> dict[str, dict]:
    """Drop star farms, typical of malicious lures: at least 3 different accounts publishing
    the same repo name, the same description, or variants of one name
    ("blender-ai-copilot-flow", "blender-ai-copilot-forge"...)."""
    from collections import Counter

    def name_of(n: str) -> str:
        return n.split("/")[-1].lower()

    def prefix(n: str) -> str:
        words = re.split(r"[-_.]+", name_of(n))
        return "-".join(words[:3]) if len(words) >= 3 else ""

    names = Counter(name_of(n) for n in repos)
    prefixes = Counter(prefix(n) for n in repos)
    descs = Counter((r.get("description") or "").strip().lower() for r in repos.values())
    kept = {}
    for n, r in repos.items():
        d = (r.get("description") or "").strip().lower()
        p = prefix(n)
        if names[name_of(n)] >= 3 or (p and prefixes[p] >= 3) or (d and descs[d] >= 3):
            continue
        kept[n] = r
    return kept


def drop_lure_accounts(repos: dict[str, dict], headers: dict, max_checks: int = 40) -> dict[str, dict]:
    """Drop repos with many stars owned by a brand-new user account with no followers: organic
    projects rarely look like that, malicious lures (bought stars) often do."""
    checked: dict[str, bool] = {}
    ranked = sorted(repos.items(), key=lambda kv: -kv[1].get("stargazers_count", 0))
    kept = {}
    for name, r in ranked:
        owner = r.get("owner") or {}
        login = owner.get("login", "")
        suspicious = False
        if owner.get("type") == "User" and r.get("stargazers_count", 0) >= 30 and login:
            if login not in checked and len(checked) < max_checks:
                try:
                    u = http_json(f"https://api.github.com/users/{login}", headers)
                    created = _parse_iso(u.get("created_at", "1970-01-01T00:00:00Z"))
                    young = (datetime.now(timezone.utc) - created).days < 180
                    checked[login] = young and u.get("followers", 0) == 0
                except Exception:
                    checked[login] = False  # no data: keep the repo
            suspicious = checked.get(login, False)
        if not suspicious:
            kept[name] = r
    return kept


# --- Models: new ids on OpenRouter + Hugging Face trending ------------------
def openrouter_models(cfg: Config) -> list[dict]:
    data = http_json("https://openrouter.ai/api/v1/models").get("data", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.window_days)
    items, seen_ids = [], set()
    for m in data:
        created = datetime.fromtimestamp(m.get("created", 0), timezone.utc)
        base = m["id"].split(":")[0]  # group :free, :batch... under one model
        if created < cutoff or base in seen_ids:
            continue
        seen_ids.add(base)
        pricing = m.get("pricing", {})
        items.append(
            {
                "id": f"model:{base.lower()}",
                "category": "model",
                "title": m.get("name") or base,
                "url": f"https://openrouter.ai/{base}",
                "source": "OpenRouter",
                "description": clean(m.get("description")),
                "published_at": created.isoformat(timespec="seconds"),
                "signals": {
                    "contexte": m.get("context_length"),
                    "free": any(x["id"] == f"{base}:free" for x in data),
                    "prompt_price": pricing.get("prompt"),
                },
            }
        )
    return items


def huggingface_models(cfg: Config) -> list[dict]:
    data = http_json("https://huggingface.co/api/models?sort=trendingScore&limit=30")
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.window_days * 2)  # stays below retention
    items = []
    for m in data:
        created = m.get("createdAt")
        if created and _parse_iso(created) < cutoff:
            continue  # trending but old: not new
        items.append(
            {
                "id": f"model-hf:{m['id'].lower()}",
                "category": "model",
                "title": m["id"],
                "url": f"https://huggingface.co/{m['id']}",
                "source": "Hugging Face (trending)",
                "description": m.get("pipeline_tag") or "",
                "published_at": created,
                "signals": {
                    "likes": m.get("likes", 0),
                    "downloads": m.get("downloads", 0),
                    "trending": m.get("trendingScore", 0),
                },
            }
        )
    return items


# --- Research: Hugging Face daily papers -------------------------------------
def huggingface_papers(cfg: Config) -> list[dict]:
    data = http_json("https://huggingface.co/api/daily_papers?limit=50")
    items = []
    for p in data:
        paper = p.get("paper", {})
        pid = paper.get("id") or p.get("title")
        items.append(
            {
                "id": f"paper:{pid}",
                "category": "research",
                "title": p.get("title") or paper.get("title", ""),
                "url": f"https://huggingface.co/papers/{pid}",
                "source": "HF Daily Papers",
                "description": clean(paper.get("summary") or p.get("summary")),
                "published_at": p.get("publishedAt"),
                "signals": {"votes": paper.get("upvotes", 0)},
            }
        )
    return items


# --- Articles: RSS / Atom feeds ----------------------------------------------
ATOM = "{http://www.w3.org/2005/Atom}"


def rss_feeds(cfg: Config) -> list[dict]:
    items, errors = [], []
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.window_days)
    for name, spec in cfg.feeds.items():
        # A feed is a URL, or {url, keywords} for general news sites (only matching entries are kept).
        url = spec if isinstance(spec, str) else spec.get("url", "")
        keywords = [] if isinstance(spec, str) else [k.lower() for k in spec.get("keywords", [])]
        if urllib.parse.urlparse(url).hostname in {"www.reddit.com", "reddit.com", "old.reddit.com"}:
            # Reddit rate-limits RSS readers that go too fast (HTTP 429): keep 12 s between two requests
            global _LAST_REDDIT
            wait = 12 - (time.time() - _LAST_REDDIT)
            if wait > 0:
                time.sleep(wait)
            _LAST_REDDIT = time.time()
        try:
            root = ET.fromstring(http_get(url))
        except Exception as e:  # a failing feed never blocks the others
            errors.append(f"{name}: {e}")
            continue
        entries = root.findall(".//item") or root.findall(f".//{ATOM}entry")
        for e in entries[:40]:
            title = _txt(e, "title") or _txt(e, f"{ATOM}title")
            link = _txt(e, "link") or _atom_link(e)
            date = _txt(e, "pubDate") or _txt(e, f"{ATOM}published") or _txt(e, f"{ATOM}updated")
            dt = _parse_date(date)
            link = safe_url(link)
            if not title or not link or (dt and dt < cutoff):
                continue
            desc = _txt(e, "description") or _txt(e, f"{ATOM}summary") or _txt(e, f"{ATOM}content")
            if keywords and not _matches(f"{title} {desc}", keywords):
                continue
            points = re.search(r"Points:\s*(\d+)", desc or "")
            encoded = _txt(e, "{http://purl.org/rss/1.0/modules/content/}encoded")
            from .repos import github_repos_in
            repos = github_repos_in(f"{link} {desc} {encoded}")
            signals = {"points": int(points.group(1))} if points else {}
            if repos:
                signals["github_repos"] = repos
            items.append(
                {
                    "id": f"article:{link}",
                    "category": "article",
                    "title": clean(title, 200),
                    "url": link,
                    "source": name,
                    "description": clean(desc),
                    "published_at": dt.isoformat(timespec="seconds") if dt else None,
                    "signals": signals,
                }
            )
    if errors and not items:
        raise RuntimeError("; ".join(errors))
    if errors:  # some feeds failed (e.g. Reddit 404/429): reported as a warning instead of being lost
        WARNINGS["rss"] = "; ".join(errors)
    return items


_LAST_REDDIT = 0.0

COLLECTORS = {
    "github": github_repos,
    "openrouter": openrouter_models,
    "huggingface_models": huggingface_models,
    "huggingface_papers": huggingface_papers,
    "rss": rss_feeds,
}


# --- helpers -----------------------------------------------------------------
def _matches(text: str, keywords: list[str]) -> bool:
    text = " " + re.sub(r"[^\w]+", " ", text.lower()) + " "
    return any(f" {k} " in text or (" " in k and k in text) for k in keywords)


def _txt(el, tag: str) -> str:
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text else ""


def _atom_link(el) -> str:
    for link in el.findall(f"{ATOM}link"):
        if link.get("rel", "alternate") == "alternate":
            return link.get("href", "")
    return ""


def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return _parse_iso(s)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
