"""Conferences, online meetups and CFPs: collection, alerts and notifications. No LLM.

Dates come from community agendas and public CFP APIs: they are leads, never verified facts.
Every alert says so ("verify on the official site").
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

from .collectors import http_get, http_json, safe_url
from .config import Config
from .store import Store, now

CALL_FOR_SPEAKERS = re.compile(
    r"call for (speakers|papers|talks)|\bcfp\b|appel (à|a) (orateurs|oratrices|speakers|talks|conf[ée]renciers)"
    r"|proposer un talk|submit a talk|become a speaker|forms\.gle|conference-hall\.io|sessionize\.com",
    re.I,
)


def conf_id(name: str, start: str | None) -> str:
    """Same id for "Voxxed Days Amsterdam" and "VoxxedDays Amsterdam 2027"."""
    key = re.sub(r"[^a-z0-9]", "", core_name(name))
    return f"conf:{key}-{(start or '')[:4]}"


def core_name(name: str) -> str:
    """'Devoxx France 2027' -> 'devoxx france' (for fuzzy watchlist matching)."""
    return re.sub(r"\b(19|20)\d{2}\b", "", name.lower()).replace("(en)", "").strip(" -–")


def load_watchlist(cfg: Config) -> list[str]:
    """Conference names from a text file (first column of a Markdown table, or one per line). Read only."""
    if not cfg.watchlist:
        return []
    path = Path(cfg.watchlist).expanduser()
    if not path.exists():
        return []
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    table = [l for l in lines if l.startswith("|")]
    names = []
    if table:  # a Markdown table: only its first column counts (notes around it are ignored)
        for line in table:
            cells = [c.strip(" *") for c in line.strip("|").split("|")]
            first = cells[0] if cells else ""
            if first and not set(first) <= set("-: ") and first.lower() not in {"conf", "conference", "name", "nom"}:
                names.append(core_name(first))
    else:  # one conference name per line
        for line in lines:
            line = line.lstrip("-* ").strip()
            if line and not line.startswith("#") and len(line) < 60 and not any(c in line for c in ",:;"):
                names.append(core_name(line))
    return [n for n in names if len(n) >= 4]


def is_watched(name: str, watchlist: list[str]) -> bool:
    """A watchlist entry must appear in the event name ("devoxx france" in "Devoxx France 2027").
    The reverse (event name inside an entry) is only accepted for long names, so "Dev 2027" never matches."""
    core = re.sub(r"[^a-z0-9]", "", core_name(name))  # "VoxxedDays" == "Voxxed Days"
    if len(core) < 4:
        return False
    entries = [re.sub(r"[^a-z0-9]", "", w) for w in watchlist]
    return any(w and (w in core or (len(core) >= 10 and core in w)) for w in entries)


def cfp_tool(url: str) -> str:
    for host, label in (("conference-hall", "conference-hall.io"), ("cfp.dev", "cfp.dev"),
                        ("sessionize", "Sessionize"), ("papercall", "PaperCall"), ("pretalx", "pretalx")):
        if host in (url or ""):
            return label
    return ""


def _ms_to_date(ms) -> str | None:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat() if ms else None


# --- Conferences: developers.events -------------------------------------------
def developers_events(cfg: Config, watchlist: list[str]) -> list[dict]:
    data = http_json("https://developers.events/all-events.json")
    today = now().date().isoformat()
    countries = {c.lower() for c in cfg.event_countries}
    topics = {t.lower() for t in cfg.event_topics}
    keywords = [k.lower() for k in cfg.event_name_keywords]
    out = []
    for e in data:
        dates = [d for d in (e.get("date") or []) if d]
        if not dates:
            continue
        start = _ms_to_date(dates[0])
        if start < today:
            continue
        loc = f"{e.get('location', '')} {e.get('city', '')}".lower()
        online = "online" in loc
        tags = [t.get("value", "").lower() for t in e.get("tags", [])]
        langs = [t.get("value") for t in e.get("tags", []) if t.get("key") == "language"]
        name = e.get("name", "")
        watched = is_watched(name, watchlist)
        relevant_place = online or not countries or (e.get("country") or "").lower() in countries
        relevant_topic = bool(topics & set(tags)) or any(k in name.lower() for k in keywords)
        if not watched and not (relevant_place and relevant_topic):
            continue
        cfp = e.get("cfp") or {}
        out.append({
            "id": conf_id(name, start),
            "kind": "conference",
            "name": name,
            "url": safe_url(e.get("hyperlink")),
            "start_at": start,
            "end_at": _ms_to_date(dates[-1]),
            "location": "Online" if online else e.get("location", ""),
            "country": e.get("country", ""),
            "online": online,
            "languages": langs,
            "tags": tags[:10],
            "cfp_url": safe_url(cfp.get("link")),
            "cfp_close": _ms_to_date(cfp.get("untilDate")),
            "source": "developers.events",
            "watched": watched,
        })
    return out


# --- Conferences: cfp.dev public API (Devoxx, Voxxed) -- gives the CFP *opening* date ---
CFP_DEV_PATTERNS = ["devoxxfr{Y}", "devoxxuk{y}", "dvbe{y}", "dvgr{y}", "dvpl{y}", "dvma{y}",
                    "vdz{y}", "voxxedlu{Y}", "vdams{y}", "vdcern{y}", "vdticino{y}"]


def _cfp_dev_event(slug_: str) -> dict | None:
    try:
        d = json.loads(http_get(f"https://{slug_}.cfp.dev/api/public/event", tries=1, timeout=8))
    except Exception:
        return None  # the slug does not exist (yet): its appearance will be the signal
    return d if isinstance(d, dict) and d.get("name") and d.get("fromDate") else None


def cfp_dev(cfg: Config, watchlist: list[str]) -> list[dict]:
    year = now().year
    slugs = sorted({p.format(Y=y, y=str(y)[2:]) for p in CFP_DEV_PATTERNS for y in (year, year + 1)})
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = dict(zip(slugs, pool.map(_cfp_dev_event, slugs)))
    out = []
    today = now().date().isoformat()
    for s, d in found.items():
        if not d or d["fromDate"][:10] < today:
            continue
        out.append({
            "id": conf_id(d["name"], d["fromDate"]),
            "kind": "conference",
            "name": d["name"],
            "url": safe_url(d.get("website")) or f"https://{s}.cfp.dev",
            "start_at": d["fromDate"][:10],
            "end_at": (d.get("toDate") or d["fromDate"])[:10],
            "location": d.get("locationName") or "",
            "country": "",
            "online": False,
            "languages": [],
            "tags": ["java", "dev"],
            "cfp_url": f"https://{s}.cfp.dev",
            "cfp_open": (d.get("cfpOpening") or "")[:16] or None,
            "cfp_close": (d.get("cfpClosing") or "")[:10] or None,
            "source": "cfp.dev",
            "watched": is_watched(d["name"], watchlist),
        })
    return out


# --- Online meetups: Meetup.com public GraphQL -----------------------------------
MEETUP_QUERY = """query($q: String!, $lat: Float!, $lon: Float!) {
  eventSearch(first: 20, filter: {query: $q, eventType: ONLINE, lat: $lat, lon: $lon}) {
    edges { node { title description dateTime eventUrl group { name } } }
  }
}"""


def meetup_online(cfg: Config, watchlist: list[str]) -> list[dict]:
    horizon = (now() + timedelta(days=30)).isoformat()
    out, seen = [], set()
    for q in cfg.meetup_queries:
        body = json.dumps({"query": MEETUP_QUERY, "variables": {"q": q, "lat": cfg.meetup_lat, "lon": cfg.meetup_lon}})
        data = http_json("https://api.meetup.com/gql-ext", {"Content-Type": "application/json"}, body.encode())
        for edge in (data.get("data") or {}).get("eventSearch", {}).get("edges", []):
            n = edge["node"]
            url = safe_url(n.get("eventUrl"))
            when = n.get("dateTime") or ""
            if not url or url in seen or not when or when > horizon:
                continue
            seen.add(url)
            group = (n.get("group") or {}).get("name", "")
            out.append({
                "id": f"meetup:{url}",
                "kind": "meetup",
                "name": n.get("title", ""),
                "url": url,
                "start_at": when,
                "end_at": when,
                "location": group,
                "country": "",
                "online": True,
                "languages": [],
                "tags": ["call-for-speakers"] if CALL_FOR_SPEAKERS.search(n.get("description") or "") else [],
                "cfp_url": "",
                "cfp_close": None,
                "source": "Meetup",
                "watched": is_watched(group, watchlist),
            })
    return out


EVENT_COLLECTORS = {"developers_events": developers_events, "cfp_dev": cfp_dev, "meetup": meetup_online}


def enabled_collectors(cfg: Config) -> dict:
    if not cfg.events_enabled:
        return {}
    return {k: v for k, v in EVENT_COLLECTORS.items() if k != "meetup" or cfg.meetup_enabled}


def merge(events: list[dict]) -> list[dict]:
    """Same conference from several sources: cfp.dev wins for CFP dates (it has the opening date)."""
    by_id: dict[str, dict] = {}
    by_cfp: dict[str, str] = {}
    for ev in events:
        cfp = (ev.get("cfp_url") or "").rstrip("/").lower()
        if cfp and cfp in by_cfp and by_cfp[cfp] != ev["id"]:
            ev = {**ev, "id": by_cfp[cfp]}  # two names, one CFP page: same event
        elif cfp:
            by_cfp[cfp] = ev["id"]
        prev = by_id.get(ev["id"])
        if prev is None:
            by_id[ev["id"]] = ev
            continue
        primary, other = (ev, prev) if ev["source"] == "cfp.dev" else (prev, ev)
        merged = {**other, **{k: v for k, v in primary.items() if v not in (None, "", [], False)}}
        merged["watched"] = prev.get("watched") or ev.get("watched")
        merged["source"] = " + ".join(sorted({prev["source"], ev["source"]}))
        by_id[ev["id"]] = merged
    return list(by_id.values())


# --- Alerts ------------------------------------------------------------------------
def notifiable(ev: dict, cfg: Config) -> bool:
    """Push notifications only for the watchlist and well-known conferences; the rest stays on the dashboard."""
    return ev.get("watched") or any(k in ev["name"].lower() for k in cfg.cfp_notify_keywords)


def compute_alerts(store: Store, cfg: Config, events: list[dict], new_ids: set[str], changed_ids: set[str]) -> list[dict]:
    today = now().date()
    alerts = []

    def add(key: str, level: str, text: str, ev: dict | None = None) -> None:
        if store.already_notified(key):
            return
        alerts.append({"key": key, "level": level, "text": text, "url": (ev or {}).get("cfp_url") or (ev or {}).get("url", ""),
                       "push": level != "info"})

    for ev in events:
        close = ev.get("cfp_close")
        if not close or close < today.isoformat() or not notifiable(ev, cfg):
            continue  # other CFPs stay on the dashboard, without alerts
        days_left = (date.fromisoformat(close) - today).days
        star = "★ " if ev.get("watched") else ""
        tool = cfp_tool(ev.get("cfp_url", ""))
        tail = (f" ({tool})" if tool else "") + f" — from {ev['source']}, verify on the official site"
        opening = (ev.get("cfp_open") or "")[:10]
        crossed = [d for d in cfg.cfp_alert_days if days_left <= d]
        # Most urgent first; at most one alert per event per run.
        candidates = []
        if ev["id"] in changed_ids:
            candidates.append((f"{ev['id']}:changed:{close}", f"{star}CFP {ev['name']}: closing date moved to {close}"))
        if crossed:
            d = min(crossed)
            candidates.append((f"{ev['id']}:d{d}:{close}", f"{star}CFP {ev['name']} closes in {days_left} days ({close})"))
        if opening and opening > today.isoformat():
            candidates.append((f"{ev['id']}:opens:{opening}", f"{star}CFP {ev['name']} opens on {opening}, closes on {close}"))
        elif opening == today.isoformat() or ev["id"] in new_ids:
            candidates.append((f"{ev['id']}:open:{close}", f"{star}CFP {ev['name']} is open until {close} ({days_left} days)"))
        for key, text in candidates:
            if not store.already_notified(key):
                add(key, "cfp", text + tail, ev)
                break

    online_new = [ev for ev in events if ev["online"] and not store.already_notified(f"{ev['id']}:online")]
    if online_new:
        names = ", ".join(ev["name"][:50] for ev in online_new[:3])
        more = f" and {len(online_new) - 3} more" if len(online_new) > 3 else ""
        alerts.append({"key": f"online:{online_new[0]['id']}", "level": "online", "url": "", "push": True,
                       "text": f"{len(online_new)} new online events: {names}{more}",
                       "also_record": [f"{ev['id']}:online" for ev in online_new]})
    tech = re.compile(r"\b(ai|ia|llm|genai|mcp|agents?|java|jvm|spring|kotlin|python|dev|devs|developers?|software|cloud|data)\b", re.I)
    speakers = [ev for ev in events if "call-for-speakers" in ev["tags"] and ev["id"] in new_ids
                and tech.search(f"{ev['name']} {ev['location']}")]
    for ev in speakers:
        add(f"{ev['id']}:speakers", "info", f"Meetup looking for speakers: {ev['name']} ({ev['location']})", ev)
    return alerts


def notify(cfg: Config, alerts: list[dict]) -> bool:
    """macOS notification center. Silent no-op elsewhere or when disabled."""
    push = [a for a in alerts if a["push"]]
    if not push or cfg.notify == "none" or platform.system() != "Darwin":
        return False
    title = f"ai-radar: {len(push)} alert" + ("s" if len(push) > 1 else "")
    body = push[0]["text"] + (f" (+{len(push) - 1} more on the dashboard)" if len(push) > 1 else "")
    # Text is passed as arguments, never interpolated into the AppleScript source.
    script = "on run argv\ndisplay notification (item 1 of argv) with title (item 2 of argv)\nend run"
    try:
        subprocess.run(["osascript", "-e", script, body[:240], title], check=False, timeout=10, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def push_phone(cfg: Config, title: str, body: str, click: str = "", priority: str = "default") -> bool:
    """Send a push through ntfy when a topic is configured. Title and body only: no personal data."""
    if not cfg.ntfy_topic:
        return False
    headers = {"Title": title.encode("ascii", "ignore").decode() or "ai-radar", "Priority": priority, "Tags": "satellite"}
    if click:
        headers["Click"] = click
    try:
        http_get(f"{cfg.ntfy_server}/{cfg.ntfy_topic}", headers, body.encode("utf-8")[:3500], tries=1, timeout=10)
        return True
    except Exception:
        return False


def export_cfp_json(cfg: Config, store: Store) -> Path:
    """Stable file read by other tools (e.g. a speaker coach). Dates are leads: verified=false."""
    rows = []
    for ev in store.upcoming_cfps(days=365):
        rows.append({
            "name": ev["name"], "location": ev["location"], "online": ev["online"], "country": ev["country"],
            "languages": ev["languages"], "start": ev["start_at"], "end": ev["end_at"],
            "cfp_open": ev["cfp_open"], "cfp_close": ev["cfp_close"], "cfp_url": ev["cfp_url"], "cfp_tool": cfp_tool(ev["cfp_url"]),
            "source": ev["source"], "first_seen": ev["first_seen"], "changed_from": ev["cfp_close_prev"],
            "watched": ev["watched"], "verified": False,
        })
    cfg.cfp_path.write_text(json.dumps({"generated_at": now().isoformat(timespec="seconds"), "cfps": rows},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg.cfp_path
