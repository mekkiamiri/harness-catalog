"""Configuration: data directory and the user's config.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_FEEDS = {
    "Latent Space": "https://www.latent.space/feed",
    "Interconnects": "https://www.interconnects.ai/feed",
    "AINews (smol.ai)": "https://news.smol.ai/rss.xml",
    "TLDR AI": "https://tldr.tech/api/rss/ai",
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    "Hacker News (AI, 50+ points)": "https://hnrss.org/newest?q=AI+OR+LLM+OR+MCP+OR+agent&points=50",
    # Authors announce their own tools here long before newsletters (or never reach 50 points).
    "Show HN (AI, 3+ points)": "https://hnrss.org/show?q=AI+OR+LLM+OR+agent+OR+agents+OR+Claude+OR+MCP+OR+Codex&points=3",
}

DEFAULT_GITHUB_TOPICS = [
    "mcp", "mcp-server", "ai-agents", "agent", "llm", "claude-code", "agent-skills", "rag", "ai",
]
DEFAULT_GITHUB_KEYWORDS = ["mcp", "agent", "claude", "llm", "skills"]
# GitHub Trending pages read on top of the all-languages one (AI repos only are kept).
DEFAULT_TRENDING_LANGUAGES = ["java", "kotlin", "python", "typescript", "go", "rust"]
# Maven artifacts (groupId:artifactId) whose new releases become items.
DEFAULT_MAVEN_WATCH = [
    "org.springframework.ai:spring-ai-bom",
    "dev.langchain4j:langchain4j",
    "com.google.adk:google-adk",
    "io.modelcontextprotocol.sdk:mcp",
    "com.anthropic:anthropic-java",
    "io.github.a2asdk:a2a-java-sdk-client",
    "org.springaicommunity:spring-ai-a2a-server-autoconfigure",
]

# Events (opt-in): generic defaults. Region-specific lists live in examples/config-*.toml.
DEFAULT_EVENT_COUNTRIES: list[str] = []  # empty = every country
DEFAULT_EVENT_TOPICS = [
    "ai", "artificial-intelligence", "agents", "agentic-ai", "agent-based-ai", "ai-coding", "llm",
    "machine-learning", "genai", "generative-ai", "mcp",
]
DEFAULT_EVENT_NAME_KEYWORDS = ["ai engineer", "mcp", "agent", "llm", "genai"]
# Conferences whose CFP alerts are pushed as notifications, besides the watchlist. Empty by default.
DEFAULT_CFP_NOTIFY_KEYWORDS: list[str] = []
DEFAULT_MEETUP_QUERIES = ["AI agents", "LLM", "MCP"]

CONFIG_TEMPLATE = """\
# ai-radar configuration. Every key is optional.

# Detection window for new repos and models (days).
window_days = 14

# How long items stay on the dashboard (days). Starred items are kept.
retention_days = 30

# Minimum stars for a recent repo to be considered.
github_min_stars = 50
# github_topics = ["mcp", "ai-agents", "llm", "claude-code"]
# github_keywords = ["mcp", "agent", "claude", "llm", "skills"]
# GitHub Trending (daily and weekly) is read for all languages plus these ones; [] = all languages only.
# trending_languages = ["java", "kotlin", "python", "typescript", "go", "rust"]
# Maven artifacts whose new releases are reported (groupId:artifactId); [] = off.
# maven_watch = ["org.springframework.ai:spring-ai-bom", "dev.langchain4j:langchain4j"]
# GitHub token: GITHUB_TOKEN or AI_RADAR_GITHUB_TOKEN environment variable (never in this file).
# Without a token GitHub allows 10 searches per minute: collection just waits, it is slower.

# Notifications: "auto" (macOS notification center when available) or "none".
notify = "auto"

[repos]
# Topics you want to contribute to: matching repos get a bonus in the Repos tab.
# focus = ["java", "spring", "mcp", "agents"]

[people]
# GitHub accounts or organizations you follow (colleagues, teams): their new or updated repos always show up,
# even with zero stars, with a score bonus. Example: github = ["octocat", "my-company"]
# github = []

[sync]
# Optional: a local clone of YOUR OWN private git repository. ai-radar then syncs your state there
# (statuses, briefs, profile, alerts already raised, weekly digest) with `ai-radar sync`. Off when empty.
# memory_home = "~/harness-memory"

[phone]
# Push to your phone with ntfy (free, open source: https://ntfy.sh, iOS and Android apps).
# Pick a long random topic name (anyone who knows it can read it) and subscribe to it in the app.
# Each run then sends one daily "radar ready" push plus CFP and online-event alerts.
ntfy_topic = ""
# ntfy_server = "https://ntfy.sh"   # or your own server

[events]
# Conferences, online meetups and CFP alerts. Off by default.
# Ready-made example for France / JVM developers: examples/config-fr-jvm.toml in the repository.
enabled = false
# Conferences are kept when online or in one of these countries (empty = all), and matching a topic or a keyword.
# countries = ["France", "Belgium", "United Kingdom"]
# topics = ["ai", "agents", "llm", "java"]
# name_keywords = ["ai engineer", "mcp", "devoxx"]
# CFP alerts are pushed as notifications for the watchlist and these conferences; others stay on the dashboard.
# cfp_notify_keywords = ["devoxx", "devfest"]
# Alerts before a CFP closes (days).
cfp_alert_days = [30, 14, 7, 2]
# Any text file listing conferences you target (e.g. a Markdown table, first column = name). Read only.
watchlist = ""
# Online meetups from Meetup.com. Uses an undocumented public endpoint that may break or be restricted
# by Meetup's terms: off by default.
meetup = false
# meetup_queries = ["AI agents", "LLM", "MCP"]
# meetup_lat = 48.8566
# meetup_lon = 2.3522

# Extra RSS / Atom feeds (name = url).
[feeds]
# "My favourite blog" = "https://example.org/feed"

# Folder for a daily Markdown note (e.g. an Obsidian vault). Empty = disabled.
[export]
markdown = ""
"""


@dataclass
class Config:
    home: Path
    window_days: int = 14
    retention_days: int = 30
    github_min_stars: int = 50
    github_topics: list[str] = field(default_factory=lambda: list(DEFAULT_GITHUB_TOPICS))
    github_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_GITHUB_KEYWORDS))
    trending_languages: list[str] = field(default_factory=lambda: list(DEFAULT_TRENDING_LANGUAGES))
    maven_watch: list[str] = field(default_factory=lambda: list(DEFAULT_MAVEN_WATCH))
    feeds: dict[str, str | dict] = field(default_factory=lambda: dict(DEFAULT_FEEDS))
    export_markdown: str = ""
    github_token: str | None = None
    notify: str = "auto"
    event_countries: list[str] = field(default_factory=lambda: list(DEFAULT_EVENT_COUNTRIES))
    event_topics: list[str] = field(default_factory=lambda: list(DEFAULT_EVENT_TOPICS))
    event_name_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_EVENT_NAME_KEYWORDS))
    cfp_notify_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_CFP_NOTIFY_KEYWORDS))
    cfp_alert_days: list[int] = field(default_factory=lambda: [30, 14, 7, 2])
    meetup_queries: list[str] = field(default_factory=lambda: list(DEFAULT_MEETUP_QUERIES))
    meetup_lat: float = 48.8566
    meetup_lon: float = 2.3522
    watchlist: str = ""
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"
    repos_focus: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    memory_home: str = ""
    events_enabled: bool = False
    meetup_enabled: bool = False

    @property
    def db_path(self) -> Path:
        return self.home / "radar.db"

    @property
    def dashboard_path(self) -> Path:
        return self.home / "dashboard" / "index.html"

    @property
    def profile_path(self) -> Path:
        return self.home / "profile.md"

    @property
    def config_path(self) -> Path:
        return self.home / "config.toml"

    @property
    def cfp_path(self) -> Path:
        return self.home / "cfp.json"

    @property
    def weekly_dir(self) -> Path:
        return self.home / "weekly"


def home_dir() -> Path:
    return Path(os.environ.get("AI_RADAR_HOME", Path.home() / ".ai-radar")).expanduser()


def load_config() -> Config:
    home = home_dir()
    home.mkdir(parents=True, exist_ok=True)
    cfg = Config(home=home)
    if not cfg.config_path.exists():
        cfg.config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    data = tomllib.loads(cfg.config_path.read_text(encoding="utf-8"))
    cfg.window_days = int(data.get("window_days", cfg.window_days))
    cfg.retention_days = int(data.get("retention_days", cfg.retention_days))
    cfg.github_min_stars = int(data.get("github_min_stars", cfg.github_min_stars))
    cfg.github_topics = list(data.get("github_topics", cfg.github_topics))
    cfg.github_keywords = list(data.get("github_keywords", cfg.github_keywords))
    cfg.trending_languages = [str(x).strip().lower() for x in data.get("trending_languages", cfg.trending_languages)]
    cfg.maven_watch = [str(x).strip() for x in data.get("maven_watch", cfg.maven_watch)]
    cfg.notify = os.environ.get("AI_RADAR_NOTIFY") or data.get("notify", cfg.notify)
    cfg.repos_focus = list(data.get("repos", {}).get("focus", []))
    cfg.people = [str(x).strip() for x in data.get("people", {}).get("github", []) if str(x).strip()]
    cfg.memory_home = os.environ.get("HARNESS_MEMORY_HOME") or data.get("sync", {}).get("memory_home", "")
    phone = data.get("phone", {})
    cfg.ntfy_topic = os.environ.get("AI_RADAR_NTFY_TOPIC") or phone.get("ntfy_topic", "")
    cfg.ntfy_server = phone.get("ntfy_server", cfg.ntfy_server).rstrip("/")
    cfg.feeds.update(data.get("feeds", {}))
    ev = data.get("events", {})
    cfg.events_enabled = bool(ev.get("enabled", False))
    cfg.meetup_enabled = bool(ev.get("meetup", False))
    cfg.event_countries = list(ev.get("countries", cfg.event_countries))
    cfg.event_topics = list(ev.get("topics", cfg.event_topics))
    cfg.event_name_keywords = list(ev.get("name_keywords", cfg.event_name_keywords))
    cfg.cfp_notify_keywords = list(ev.get("cfp_notify_keywords", cfg.cfp_notify_keywords))
    cfg.cfp_alert_days = sorted((int(d) for d in ev.get("cfp_alert_days", cfg.cfp_alert_days)), reverse=True)
    cfg.meetup_queries = list(ev.get("meetup_queries", cfg.meetup_queries))
    cfg.meetup_lat = float(ev.get("meetup_lat", cfg.meetup_lat))
    cfg.meetup_lon = float(ev.get("meetup_lon", cfg.meetup_lon))
    cfg.watchlist = ev.get("watchlist", "") or os.environ.get("AI_RADAR_WATCHLIST", "")
    cfg.export_markdown = data.get("export", {}).get("markdown", "") or os.environ.get("AI_RADAR_EXPORT_MARKDOWN", "")
    token = os.environ.get("AI_RADAR_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    # An unset optional plugin option may arrive as an empty string or an unexpanded placeholder.
    cfg.github_token = token if token and not token.startswith("${") else None
    return cfg
