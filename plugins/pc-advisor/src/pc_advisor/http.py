"""Polite HTTP: honest user agent, robots.txt respected, one request per second per host, small disk cache.

Standard library only. Sites that answer 403/429 (anti-bot protection) are reported as blocked:
we never try to get around a protection.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import urllib.robotparser
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__

USER_AGENT = f"pc-advisor/{__version__} (+https://github.com/mekkiamiri/harness-catalog/tree/main/plugins/pc-advisor)"
TIMEOUT = 20
MIN_DELAY = 1.0          # seconds between two requests to the same host
CACHE_TTL = 6 * 3600     # prices move slowly: one fetch every 6 hours is enough

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class Blocked(Exception):
    """The site refused us (robots.txt, 403, 429): report it, do not insist."""


def home() -> Path:
    path = Path(os.environ.get("PC_ADVISOR_HOME") or Path.home() / ".pc-advisor")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_file(url: str) -> Path:
    folder = home() / "cache"
    folder.mkdir(exist_ok=True)
    return folder / (sha256(url.encode()).hexdigest()[:24] + ".bin")


def _robots_allow(url: str) -> bool:
    parts = urlsplit(url)
    host = f"{parts.scheme}://{parts.netloc}"
    if host not in _robots:
        parser = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                parser.parse(resp.read().decode("utf-8", "replace").splitlines())
            _robots[host] = parser
        except Exception:
            _robots[host] = None  # no readable robots.txt: allowed
    parser = _robots[host]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def _wait_turn(url: str) -> None:
    host = urlsplit(url).netloc
    elapsed = time.monotonic() - _last_hit.get(host, 0.0)
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)
    _last_hit[host] = time.monotonic()


def get(url: str, use_cache: bool = True, ttl: int = CACHE_TTL) -> tuple[bytes, float]:
    """Return (body, fetched_at epoch). Raises Blocked when the site refuses us."""
    if not url.lower().startswith("https://"):
        raise ValueError("only https URLs are fetched: " + url)
    cache = _cache_file(url)
    if use_cache and cache.exists() and time.time() - cache.stat().st_mtime < ttl:
        return cache.read_bytes(), cache.stat().st_mtime
    if not _robots_allow(url):
        raise Blocked(f"robots.txt disallows {url}")
    _wait_turn(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429):
            raise Blocked(f"HTTP {e.code} on {url} (anti-bot protection or rate limit)") from e
        raise
    cache.write_bytes(body)
    return body, time.time()


def get_json(url: str, use_cache: bool = True) -> tuple[object, float]:
    body, at = get(url, use_cache)
    return json.loads(body), at
