"""SQLite storage: the single source of truth for the dashboard, the MCP server and the exports."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           TEXT PRIMARY KEY,         -- e.g. "repo:owner/name", "model:google/gemini-4"
    category     TEXT NOT NULL,            -- tool | model | research | article
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    source       TEXT NOT NULL,
    description  TEXT DEFAULT '',
    published_at TEXT,                     -- creation / publication date at the source
    first_seen   TEXT NOT NULL,            -- first detection by ai-radar
    last_seen    TEXT NOT NULL,
    signals      TEXT DEFAULT '{}',        -- JSON: stars, votes, points, resonance...
    score        REAL DEFAULT 0,
    status       TEXT DEFAULT 'new',       -- new | read | ignored | starred
    brief        TEXT DEFAULT '',          -- written by the host's model
    relevant     INTEGER DEFAULT 0,        -- the host's model judged it relevant (validation bonus)
    lab          TEXT DEFAULT ''           -- path and summary of the generated lab
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);

CREATE TABLE IF NOT EXISTS events (
    id             TEXT PRIMARY KEY,       -- "conf:<slug>" or "meetup:<url>"
    kind           TEXT NOT NULL,          -- conference | meetup
    name           TEXT NOT NULL,
    url            TEXT NOT NULL,
    start_at       TEXT,                   -- ISO date or datetime
    end_at         TEXT,
    location       TEXT DEFAULT '',
    country        TEXT DEFAULT '',
    online         INTEGER DEFAULT 0,
    languages      TEXT DEFAULT '[]',
    tags           TEXT DEFAULT '[]',
    cfp_url        TEXT DEFAULT '',
    cfp_open       TEXT,                   -- ISO datetime when known (cfp.dev)
    cfp_close      TEXT,                   -- ISO date, NULL if unknown
    cfp_close_prev TEXT,                   -- previous value when the date moved
    source         TEXT NOT NULL,
    first_seen     TEXT NOT NULL,
    last_seen      TEXT NOT NULL,
    watched        INTEGER DEFAULT 0       -- listed in the user's watchlist
);

CREATE TABLE IF NOT EXISTS notifications (
    key     TEXT PRIMARY KEY,              -- de-duplication key of an alert
    sent_at TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    started  TEXT NOT NULL,
    finished TEXT,
    report   TEXT DEFAULT '{}'
);
"""

ITEM_FIELDS = {"status", "brief", "lab", "relevant"}
PRESERVED_SIGNALS = ("contrib", "contrib_score", "mentioned_by", "readme")


def _later(a: str | None, b: str | None) -> str | None:
    """The later of two ISO dates (either may be missing or malformed)."""
    def parse(s):
        try:
            d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    da, db = parse(a), parse(b)
    if da is None or db is None:
        return a if db is None else b
    return b if db > da else a


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # WAL + busy timeout: the MCP server and a background run can use the database at the same time.
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(items)")}
        if "relevant" not in cols:
            self.conn.execute("ALTER TABLE items ADD COLUMN relevant INTEGER DEFAULT 0")
        if "state_updated" not in cols:
            self.conn.execute("ALTER TABLE items ADD COLUMN state_updated TEXT DEFAULT ''")
        if "state_times" not in cols:  # per-field change times, for a field-by-field sync merge
            self.conn.execute("ALTER TABLE items ADD COLUMN state_times TEXT DEFAULT '{}'")
        self.conn.commit()

    def close(self) -> None:
        # Leave the file in rollback-journal mode so that read-only readers (sqlite3 -readonly)
        # can open it; this is a no-op while another connection still uses WAL.
        try:
            self.conn.commit()
            self.conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            pass
        self.conn.close()

    def commit(self) -> None:
        self.conn.commit()

    # --- items ------------------------------------------------------------
    def upsert(self, item: dict) -> bool:
        """Insert or update an item. Returns True when it is new."""
        t = iso(now())
        exists = self.conn.execute(
            "SELECT signals, published_at, last_seen FROM items WHERE id = ?", (item["id"],)).fetchone()
        new_signals = dict(item.get("signals", {}))
        published = exists["published_at"] if exists is not None else item.get("published_at")
        if exists is not None:  # keep signals computed by later steps (contribution analysis, newsletter mentions)
            old = json.loads(exists["signals"] or "{}")
            for key in PRESERVED_SIGNALS:
                if key in old and key not in new_signals:
                    new_signals[key] = old[key]
            if item.get("merge_signals"):
                # A second view of the same item (GitHub Trending after the GitHub search): add to what
                # is known instead of replacing it, keep today's best star rate, move the date forward.
                fresh = (exists["last_seen"] or "")[:10] == t[:10]
                rate = new_signals.get("stars_per_day", 0)
                new_signals = {**old, **new_signals}
                if fresh and old.get("stars_per_day", 0) > rate:
                    new_signals["stars_per_day"] = old["stars_per_day"]
                published = _later(published, item.get("published_at"))
        signals = json.dumps(new_signals, ensure_ascii=False)
        if exists is None:
            self.conn.execute(
                "INSERT INTO items (id, category, title, url, source, description, published_at,"
                " first_seen, last_seen, signals) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item["id"], item["category"], item["title"], item["url"], item["source"],
                 item.get("description", ""), item.get("published_at"), t, t, signals),
            )
            return True
        self.conn.execute(
            "UPDATE items SET title = ?, url = ?, description = ?, last_seen = ?, signals = ?, published_at = ?"
            " WHERE id = ?",
            (item["title"], item["url"], item.get("description", ""), t, signals, published, item["id"]),
        )
        return False

    def set_score(self, item_id: str, score: float, signals: dict) -> None:
        self.conn.execute(
            "UPDATE items SET score = ?, signals = ? WHERE id = ?",
            (round(score, 2), json.dumps(signals, ensure_ascii=False), item_id),
        )

    def set_field(self, item_id: str, field: str, value) -> bool:
        if field not in ITEM_FIELDS:
            raise ValueError(f"field cannot be changed: {field}")
        t = iso(now())
        row = self.conn.execute("SELECT state_times FROM items WHERE id = ?", (item_id,)).fetchone()
        times = json.loads((row["state_times"] if row else None) or "{}")
        times[field] = t
        cur = self.conn.execute(f"UPDATE items SET {field} = ?, state_updated = ?, state_times = ? WHERE id = ?",
                                (value, t, json.dumps(times, sort_keys=True), item_id))
        self.conn.commit()
        return cur.rowcount > 0

    def purge(self, retention_days: int) -> int:
        limit = iso(now() - timedelta(days=retention_days))
        # last_seen: an item still returned by a collector is never purged (it would come back as "new").
        n = self.conn.execute("DELETE FROM items WHERE last_seen < ? AND status IN ('new', 'read')", (limit,)).rowcount
        # Ignored items are kept longer as tombstones so that they do not come back as "new".
        old = iso(now() - timedelta(days=max(90, 3 * retention_days)))
        n += self.conn.execute("DELETE FROM items WHERE first_seen < ? AND status = 'ignored'", (old,)).rowcount
        today = now().date().isoformat()
        n += self.conn.execute(
            "DELETE FROM events WHERE COALESCE(end_at, start_at) < ? AND (cfp_close IS NULL OR cfp_close < ?)",
            (today, today),
        ).rowcount
        return n

    def all_items(self) -> list[dict]:
        return [self._item(r) for r in self.conn.execute("SELECT * FROM items")]

    def get(self, item_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._item(r) if r else None

    def query(self, category: str | None = None, days: int = 30, limit: int = 50,
              status: str | None = None, without_brief: bool = False, text: str | None = None) -> list[dict]:
        sql = "SELECT * FROM items WHERE (first_seen >= ? OR status = 'starred')"
        args: list = [iso(now() - timedelta(days=days))]
        if category:
            sql += " AND category = ?"
            args.append(category)
        if status:
            sql += " AND status = ?"
            args.append(status)
        else:
            sql += " AND status != 'ignored'"
        if without_brief:
            sql += " AND brief = ''"
        if text:
            sql += " AND (title LIKE ? OR description LIKE ?)"
            args += [f"%{text}%", f"%{text}%"]
        sql += " ORDER BY score DESC, first_seen DESC LIMIT ?"
        args.append(limit)
        return [self._item(r) for r in self.conn.execute(sql, args)]

    def counts(self) -> dict:
        rows = self.conn.execute("SELECT category, COUNT(*) n FROM items WHERE status != 'ignored' GROUP BY category")
        out = {r["category"]: r["n"] for r in rows}
        out["event"] = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return out

    # --- events -----------------------------------------------------------
    def upsert_event(self, ev: dict) -> tuple[bool, bool]:
        """Insert or update an event. Returns (is_new, cfp_date_changed).

        Known CFP dates are never erased by a run that did not get them (flaky source), and dates
        from cfp.dev (the CFP platform itself) are not overridden by an agenda."""
        t = iso(now())
        row = self.conn.execute("SELECT cfp_open, cfp_close, source FROM events WHERE id = ?", (ev["id"],)).fetchone()
        langs = json.dumps(ev.get("languages", []))
        tags = json.dumps(ev.get("tags", []))
        cfp_open, cfp_close = ev.get("cfp_open"), ev.get("cfp_close")
        if row is None:
            self.conn.execute(
                "INSERT INTO events (id, kind, name, url, start_at, end_at, location, country, online, languages,"
                " tags, cfp_url, cfp_open, cfp_close, source, first_seen, last_seen, watched)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ev["id"], ev["kind"], ev["name"], ev["url"], ev.get("start_at"), ev.get("end_at"),
                 ev.get("location", ""), ev.get("country", ""), int(ev.get("online", False)), langs, tags,
                 ev.get("cfp_url", ""), cfp_open, cfp_close, ev["source"], t, t, int(ev.get("watched", False))),
            )
            return True, False
        authoritative = "cfp.dev" in (row["source"] or "") and "cfp.dev" not in ev["source"]
        if authoritative or not cfp_close:
            cfp_open, cfp_close = row["cfp_open"], row["cfp_close"]
        cfp_open = cfp_open or row["cfp_open"]
        changed = bool(row["cfp_close"] and cfp_close and row["cfp_close"] != cfp_close)
        source = row["source"] if authoritative else ev["source"]
        self.conn.execute(
            "UPDATE events SET name = ?, url = ?, start_at = ?, end_at = ?, location = ?, country = ?, online = ?,"
            " languages = ?, tags = ?, cfp_url = COALESCE(NULLIF(?, ''), cfp_url), cfp_open = ?, cfp_close = ?,"
            " cfp_close_prev = CASE WHEN ? THEN ? ELSE cfp_close_prev END, source = ?, last_seen = ?, watched = ?"
            " WHERE id = ?",
            (ev["name"], ev["url"], ev.get("start_at"), ev.get("end_at"), ev.get("location", ""), ev.get("country", ""),
             int(ev.get("online", False)), langs, tags, ev.get("cfp_url", ""), cfp_open, cfp_close,
             changed, row["cfp_close"], source, t, int(ev.get("watched", False)), ev["id"]),
        )
        return False, changed

    def events(self, kind: str | None = None, online_only: bool = False, days_ahead: int = 365) -> list[dict]:
        today = now().date().isoformat()
        horizon = (now() + timedelta(days=days_ahead)).date().isoformat()
        sql = "SELECT * FROM events WHERE substr(start_at, 1, 10) >= ? AND substr(start_at, 1, 10) <= ?"
        args: list = [today, horizon]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        if online_only:
            sql += " AND online = 1"
        sql += " ORDER BY start_at"
        return [self._event(r) for r in self.conn.execute(sql, args)]

    def upcoming_cfps(self, days: int = 60, watched_only: bool = False) -> list[dict]:
        today = now().date().isoformat()
        horizon = (now() + timedelta(days=days)).date().isoformat()
        sql = "SELECT * FROM events WHERE cfp_close >= ? AND cfp_close <= ?"
        if watched_only:
            sql += " AND watched = 1"
        sql += " ORDER BY cfp_close"
        return [self._event(r) for r in self.conn.execute(sql, (today, horizon))]

    # --- notifications ----------------------------------------------------
    def already_notified(self, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM notifications WHERE key = ?", (key,)).fetchone() is not None

    def record_notification(self, key: str, message: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO notifications (key, sent_at, message) VALUES (?, ?, ?)",
                          (key, iso(now()), message))

    def recent_notifications(self, days: int = 7) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM notifications WHERE sent_at >= ? ORDER BY sent_at DESC",
                                 (iso(now() - timedelta(days=days)),))
        return [dict(r) for r in rows]

    # --- runs -------------------------------------------------------------
    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO runs (started) VALUES (?)", (iso(now()),))
        self.conn.commit()
        return int(cur.lastrowid)

    def end_run(self, run_id: int, report: dict) -> None:
        self.conn.execute("UPDATE runs SET finished = ?, report = ? WHERE id = ?",
                          (iso(now()), json.dumps(report, ensure_ascii=False), run_id))
        self.conn.commit()

    def last_run(self) -> dict | None:
        # Only full runs count: a partial `collect --sources ...` must not hide a missed daily run.
        r = self.conn.execute(
            "SELECT * FROM runs WHERE finished IS NOT NULL AND report NOT LIKE '%\"partial\": true%'"
            " ORDER BY id DESC LIMIT 1").fetchone()
        if not r:
            return None
        return {"started": r["started"], "finished": r["finished"], "report": json.loads(r["report"] or "{}")}

    @staticmethod
    def _item(r: sqlite3.Row) -> dict:
        d = dict(r)
        d["signals"] = json.loads(d.get("signals") or "{}")
        return d

    @staticmethod
    def _event(r: sqlite3.Row) -> dict:
        d = dict(r)
        d["languages"] = json.loads(d.get("languages") or "[]")
        d["tags"] = json.loads(d.get("tags") or "[]")
        d["online"] = bool(d["online"])
        d["watched"] = bool(d["watched"])
        return d
