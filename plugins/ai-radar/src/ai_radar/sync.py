"""Optional sync of the user's state with THEIR OWN private git repository (off by default).

Enable it by pointing HARNESS_MEMORY_HOME (or [sync] memory_home) to a local clone of a private repository.
ai-radar then reads and writes only `<memory>/ai-radar/`:

    state/items.jsonl          user state per item (status, brief, lab, relevant), sorted by id
    state/notifications.jsonl  alerts already raised (so the other computer does not raise them again)
    profile.md                 copied both ways (config.toml is NOT synced: it holds per-computer paths)
    weekly/YYYY-Www.md, cfp.json
    daily/YYYY-MM-DD.json      next morning's digest, written by `run --deliver`; a scheduled workflow sends it

The radar database itself stays local: it is rebuilt by the collection.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

from .config import Config
from .store import Store, iso, now

STATE_FIELDS = ("status", "brief", "lab", "relevant")


def memory_dir(cfg: Config) -> Path | None:
    if not cfg.memory_home:
        return None
    root = Path(cfg.memory_home).expanduser()
    return root if (root / ".git").exists() else None  # .git may be a directory or a file (worktree)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Never prompts (no terminal: hook, MCP server) and never hangs forever."""
    env = os.environ | {"GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": "true"}
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, env=env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "git timed out after 120 s")


def _git_dir(root: Path) -> Path:
    out = _git(root, "rev-parse", "--absolute-git-dir").stdout.strip()
    return Path(out) if out else root / ".git"


def _pull(root: Path) -> tuple[bool, str]:
    """pull --rebase; on a conflict inside ai-radar/ (generated files), keep the remote version and continue:
    our own state is still in the local database and is exported again right after."""
    p = _git(root, "pull", "--rebase", "--autostash", "-q")
    if p.returncode == 0:
        return True, ""
    for _ in range(20):
        conflicted = _git(root, "diff", "--name-only", "--diff-filter=U").stdout.split()
        if not conflicted:
            break
        if any(not f.startswith("ai-radar/") for f in conflicted):
            _git(root, "rebase", "--abort")
            return False, "conflict outside ai-radar/: resolve it in the memory repository"
        for f in conflicted:
            _git(root, "checkout", "--ours", "--", f)  # during a rebase, "ours" is the remote side
            _git(root, "add", "--", f)
        if _git(root, "rebase", "--continue").returncode == 0:
            return True, "remote version kept for conflicting generated files"
    if (_git_dir(root) / "rebase-merge").exists() or (_git_dir(root) / "rebase-apply").exists():
        _git(root, "rebase", "--abort")
    return False, (p.stderr or p.stdout)[-300:]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


# --- import -------------------------------------------------------------------------
def import_state(store: Store, folder: Path) -> dict:
    merged = added = 0
    items_file = folder / "state" / "items.jsonl"
    if items_file.exists():
        for line in items_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            remote = json.loads(line)
            local = store.get(remote["id"])
            if local is None:
                store.upsert({k: remote.get(k, "") for k in ("id", "category", "title", "url", "source")} | {"signals": {}})
                # keep the original dates: an old item is not today's news, and it is purged on schedule
                store.conn.execute("UPDATE items SET first_seen = ?, last_seen = ? WHERE id = ?",
                                   (remote.get("first_seen") or iso(now()), remote.get("last_seen") or iso(now()),
                                    remote["id"]))
                local = store.get(remote["id"])
                added += 1
            if _merge_fields(store, local, remote):
                merged += 1
    notif_file = folder / "state" / "notifications.jsonl"
    if notif_file.exists():
        for line in notif_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                n = json.loads(line)
                store.conn.execute("INSERT OR IGNORE INTO notifications (key, sent_at, message) VALUES (?, ?, ?)",
                                   (n["key"], n["sent_at"], n.get("message", "")))
    store.commit()
    return {"items_merged": merged, "items_added": added}


def _merge_fields(store: Store, local: dict, remote: dict) -> bool:
    """Field by field: the most recent change wins (status, brief, lab and relevant each have their own time)."""
    ltimes = json.loads(local.get("state_times") or "{}")
    rtimes = remote.get("times") or {}
    if not rtimes and remote.get("updated_at"):  # older export format: one time for every field
        rtimes = {f: remote["updated_at"] for f in STATE_FIELDS if remote.get(f) not in (None, "", 0, "new")}
    changed = False
    for f in STATE_FIELDS:
        rt, lt = rtimes.get(f, ""), ltimes.get(f, "")
        if f in remote and rt and rt > lt:
            store.conn.execute(f"UPDATE items SET {f} = ? WHERE id = ?", (remote[f], remote["id"]))
            ltimes[f] = rt
            changed = True
    if changed:
        store.conn.execute("UPDATE items SET state_times = ?, state_updated = ? WHERE id = ?",
                           (json.dumps(ltimes, sort_keys=True), max(ltimes.values()), remote["id"]))
    return changed


# --- export -------------------------------------------------------------------------
def export_state(store: Store, folder: Path, retention_days: int = 30) -> None:
    (folder / "state").mkdir(parents=True, exist_ok=True)
    rows = store.conn.execute(
        "SELECT id, category, title, url, source, status, brief, lab, relevant, state_times, first_seen, last_seen"
        " FROM items WHERE (status != 'new' OR brief != '' OR lab != '' OR relevant = 1)"
        # what the purge would delete does not travel (otherwise it would bounce between the computers)
        " AND (status = 'starred' OR (status = 'ignored' AND last_seen >= ?) OR last_seen >= ?) ORDER BY id",
        (iso(now() - timedelta(days=max(90, 3 * retention_days))), iso(now() - timedelta(days=retention_days))))
    lines = [json.dumps({"id": r["id"], "category": r["category"], "title": r["title"], "url": r["url"],
                         "source": r["source"], "status": r["status"], "brief": r["brief"], "lab": r["lab"],
                         "relevant": r["relevant"], "times": json.loads(r["state_times"] or "{}"),
                         "first_seen": r["first_seen"], "last_seen": r["last_seen"]},
                        ensure_ascii=False, sort_keys=True) for r in rows]
    (folder / "state" / "items.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    limit = iso(now() - timedelta(days=120))
    notes = store.conn.execute("SELECT key, sent_at, message FROM notifications WHERE sent_at >= ? ORDER BY key", (limit,))
    nl = [json.dumps(dict(n), ensure_ascii=False, sort_keys=True) for n in notes]
    (folder / "state" / "notifications.jsonl").write_text("\n".join(nl) + ("\n" if nl else ""), encoding="utf-8")


def _copy_tree(src: Path, dst: Path) -> None:
    if src.exists():
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)


def sync_files(cfg: Config, folder: Path, last: dict) -> dict:
    """profile.md both ways, using the hash at the previous sync to see who changed.
    config.toml is never synced: it holds per-computer paths (memory_home, watchlist, export)."""
    out = {}
    for name in ("profile.md",):
        local, remote = cfg.home / name, folder / name
        lh, rh, prev = _sha(local), _sha(remote), last.get(name)
        if lh == rh:
            out[name] = "same"
        elif rh and (not lh or lh == prev or prev is None):
            if lh and prev is None:  # first sync on this computer: the shared copy wins, the local one is kept aside
                shutil.copy2(local, cfg.home / f"{name}.before-first-sync")
            shutil.copy2(remote, local); out[name] = "pulled"
        elif lh and (not rh or rh == prev):
            shutil.copy2(local, remote); out[name] = "pushed"
        else:  # both changed since the last sync: keep the local one, save the remote copy next to it
            shutil.copy2(remote, cfg.home / f"{name}.remote"); shutil.copy2(local, remote); out[name] = "conflict"
        last[name] = _sha(local)
    _copy_tree(cfg.weekly_dir, folder / "weekly")
    _copy_tree(cfg.home / "daily", folder / "daily")
    if cfg.cfp_path.exists():
        shutil.copy2(cfg.cfp_path, folder / "cfp.json")
    return out


# --- entry point --------------------------------------------------------------------
class RepoBusy(RuntimeError):
    pass


def _repo_lock(root: Path):
    """Shared lock for every harness writing to the same repository: .git/harness.lock (mkdir),
    considered stale after 10 minutes."""
    import time
    from contextlib import contextmanager

    @contextmanager
    def lock():
        path = _git_dir(root) / "harness.lock"
        for _ in range(30):
            try:
                path.mkdir()
                break
            except FileExistsError:
                try:
                    if time.time() - path.stat().st_mtime > 600:
                        path.rmdir()  # stale lock
                        continue
                except FileNotFoundError:
                    continue  # another process removed it first
                time.sleep(2)
        else:
            raise RepoBusy("another harness is committing to the memory repository")
        try:
            yield
        finally:
            try:
                path.rmdir()
            except FileNotFoundError:
                pass
    return lock()


def sync(cfg: Config, store: Store) -> dict:
    root = memory_dir(cfg)
    if root is not None:
        try:
            with _repo_lock(root):
                return _sync(cfg, store, root)
        except RepoBusy as e:
            return {"status": f"skipped: {e}"}
    return _sync(cfg, store, root)


def _sync(cfg: Config, store: Store, root: Path | None) -> dict:
    if root is None:
        return {"status": "disabled: set HARNESS_MEMORY_HOME (or [sync] memory_home) to a clone of your private repository"}
    folder = root / "ai-radar"
    folder.mkdir(parents=True, exist_ok=True)
    state_file = cfg.home / "sync-state.json"
    last = json.loads(state_file.read_text()) if state_file.exists() else {}
    report: dict = {}

    has_remote = bool(_git(root, "remote").stdout.strip())
    if has_remote:
        ok, detail = _pull(root)
        if not ok:
            return {"status": "pull failed", "detail": detail}
        if detail:
            report["pull"] = detail
    report |= import_state(store, folder)
    report["files"] = sync_files(cfg, folder, last)
    export_state(store, folder, cfg.retention_days)
    state_file.write_text(json.dumps(last, indent=2))

    _git(root, "add", "ai-radar")
    if _git(root, "diff", "--cached", "--quiet").returncode == 0:
        report["status"] = "up to date"
        return report
    c = _git(root, "commit", "-q", "-m", f"ai-radar: sync {now().date().isoformat()}")
    if c.returncode != 0:
        return report | {"status": "commit failed", "detail": (c.stdout + c.stderr)[-300:]}
    if has_remote:
        p = _git(root, "push", "-q")
        if p.returncode != 0:  # e.g. the pre-push hook refused: nothing leaves the computer
            return report | {"status": "push refused", "detail": (p.stdout + p.stderr)[-400:]}
    report["status"] = "pushed" if has_remote else "committed (no remote)"
    return report


def write_daily_digest(cfg: Config, store: Store, pushed: list[str]) -> Path:
    """The day's digest for the phone: a readable Markdown page (opened from the notification) and a small
    JSON with the notification text. Public titles, one-line summaries and links only."""
    from .pipeline import _short_summary
    local = now().astimezone()
    # dated for the morning it is delivered: after noon, that is tomorrow
    day = (local.date() + timedelta(days=1 if local.hour >= 12 else 0)).isoformat()
    top = store.query(days=1, limit=6)
    folder = cfg.home / "daily"
    folder.mkdir(parents=True, exist_ok=True)

    md = [f"# AI radar — {day}", ""]
    if pushed:
        md += ["## Alerts", ""] + [f"- {t}" for t in pushed[:6]] + [""]
    md += ["## Top of the day", ""]
    for it in top:
        md.append(f"### [{it['title']}]({it['url']})")
        md.append(f"*{it['source']} · score {it['score']:.0f}*")
        md.append("")
        md.append(it["brief"].strip() if it.get("brief") else _short_summary(it, 400) or "")
        md.append("")
    md += ["## Proposals for you", ""]
    from .repos import proposals
    for p in proposals(cfg, store, exclude_urls={it["url"] for it in top}):
        md.append(f"- **[{p['title']}]({p['url']})** — {p['why']}")
    md += ["", "*Open Claude and run `/ai-radar:morning` for the guided session.*"]
    (folder / f"{day}.md").write_text("\n".join(md), encoding="utf-8")

    counts = f"{len(top)} news" + (f", {len(pushed)} alert{'s' if len(pushed) > 1 else ''}" if pushed else "")
    lines = [f"• {it['title'][:70]}" for it in top[:3]]
    digest = {"date": day, "title": f"AI radar — {counts}", "lines": lines, "page": f"ai-radar/daily/{day}.md"}
    path = folder / f"{day}.json"
    path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def enabled(cfg: Config) -> bool:
    return memory_dir(cfg) is not None or bool(os.environ.get("HARNESS_MEMORY_HOME"))
