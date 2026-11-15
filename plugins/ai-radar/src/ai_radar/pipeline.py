"""Daily run: collect -> score -> events and alerts -> purge -> dashboard and exports."""

from __future__ import annotations

import os

try:  # POSIX
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt
from contextlib import contextmanager
from datetime import datetime, timezone

from . import collectors, events, render, repos, scoring, trends
from .config import Config
from .store import Store


class AlreadyRunning(RuntimeError):
    pass


@contextmanager
def run_lock(cfg: Config):
    """One collection at a time (session-start hook, scheduled task, MCP call, several sessions)."""
    path = cfg.home / "run.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR)
    try:
        try:
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:  # BlockingIOError on POSIX, PermissionError on Windows
            raise AlreadyRunning("a collection is already running") from None
        yield
    finally:
        os.close(fd)


def is_running(cfg: Config) -> bool:
    try:
        with run_lock(cfg):
            return False
    except AlreadyRunning:
        return True


def collect(cfg: Config, store: Store, sources: list[str] | None = None) -> dict:
    with run_lock(cfg):
        return _collect(cfg, store, sources)


def _collect(cfg: Config, store: Store, sources: list[str] | None = None) -> dict:
    run_id = store.start_run()
    report: dict = {"new": 0, "seen": 0, "sources": {}, "errors": {}, "alerts": [], "partial": bool(sources)}

    for name, fn in collectors.COLLECTORS.items():
        if sources and name not in sources:
            continue
        try:
            items = fn(cfg)
            new = sum(store.upsert(it) for it in items)
        except Exception as e:  # a failing source (or a malformed item) never blocks the others
            store.conn.rollback()
            report["errors"][name] = str(e)[:300]
            continue
        store.commit()  # never keep a write transaction open during network calls
        report["sources"][name] = {"received": len(items), "new": new}
        report["new"] += new
        report["seen"] += len(items)
    if not sources or "repos" in sources:
        try:
            report["repos"] = repos.enrich(cfg, store)
        except Exception as e:
            store.conn.rollback()
            report["errors"]["repos"] = str(e)[:300]
    for item_id, score, signals in scoring.score_items(store.all_items()):
        store.set_score(item_id, score, signals)
    store.commit()

    watchlist = events.load_watchlist(cfg)
    collected: list[dict] = []
    for name, fn in events.enabled_collectors(cfg).items():
        if sources and name not in sources:
            continue
        try:
            found = fn(cfg, watchlist)
        except Exception as e:
            report["errors"][name] = str(e)[:300]
            continue
        report["sources"][name] = {"received": len(found)}
        collected += found
    merged = events.merge(collected)
    new_ids, changed_ids = set(), set()
    for ev in merged:
        is_new, changed = store.upsert_event(ev)
        if is_new:
            new_ids.add(ev["id"])
        if changed:
            changed_ids.add(ev["id"])
    report["events_new"] = len(new_ids)

    alerts = events.compute_alerts(store, cfg, merged, new_ids, changed_ids)
    for a in alerts:
        store.record_notification(a["key"], a["text"])
        for key in a.get("also_record", []):
            store.record_notification(key, a["text"])
    store.commit()  # before notifications: osascript and ntfy can take seconds
    report["alerts"] = [a["text"] for a in alerts]
    report["pushed_alerts"] = [a["text"] for a in alerts if a["push"]]
    report["notified"] = events.notify(cfg, alerts)

    store.commit()
    report["trends"] = trends.language_trends(store)
    report["purged"] = store.purge(cfg.retention_days)
    store.commit()
    store.end_run(run_id, report)
    return report


def _phone_digest(cfg: Config, store: Store, pushed: list[str]) -> bool:
    """One "radar ready" push per day (plus the day's alerts), only when ntfy is configured."""
    if not cfg.ntfy_topic:
        return False
    key = f"phone:{datetime.now().date().isoformat()}"
    if store.already_notified(key) and not pushed:
        return False
    lines = []
    for it in store.query(days=1, limit=4):
        summary = _short_summary(it)
        lines.append(f"• {it['title'][:80]}" + (f"\n  {summary}" if summary else "") + f"\n  {it['url']}")
    lines += [f"! {text[:160]}" for text in pushed[:3]]
    body = "\n".join(lines) or "Nothing new today."
    sent = events.push_phone(cfg, "AI radar is ready", body + "\nOpen Claude and run /ai-radar:morning.")
    if sent:
        store.record_notification(key, "phone digest")
    return sent


def _short_summary(item: dict, limit: int = 130) -> str:
    """One line: the brief's "What it is" when the model wrote it, else the source description."""
    what = render.brief_line(item.get("brief", ""))
    if what:
        return what[:limit]
    text = (item.get("description") or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def publish(cfg: Config, store: Store) -> dict:
    out = {
        "dashboard": str(render.dashboard(cfg, store)),
        "cfp": str(events.export_cfp_json(cfg, store)),
        "weekly": str(render.weekly_digest(cfg, store)),
    }
    if cfg.export_markdown:
        out["markdown"] = str(render.markdown_note(cfg, store))
    return out


def run(cfg: Config, store: Store) -> dict:
    report = collect(cfg, store)  # raises AlreadyRunning if another run holds the lock
    report["outputs"] = publish(cfg, store)
    # The phone digest only after a full run whose dashboard is published. With a private memory repository,
    # its workflow sends it (nothing leaves this computer, and no double notification); otherwise direct ntfy.
    from . import sync
    if sync.memory_dir(cfg):
        report["daily_digest"] = str(sync.write_daily_digest(cfg, store, report.get("pushed_alerts", [])))
    else:
        report["phone"] = _phone_digest(cfg, store, report.get("pushed_alerts", []))
    store.commit()
    return report


def hours_since_last_run(store: Store) -> float | None:
    last = store.last_run()
    if not last:
        return None
    finished = datetime.fromisoformat(last["finished"])
    return (datetime.now(timezone.utc) - finished).total_seconds() / 3600
