# Architecture

Why things are the way they are: [design decisions](design.md).

## Principle: collection is separate from judgment

| Layer | LLM? | Where | Role |
|---|---|---|---|
| Item collection | No | `collectors.py` | Queries public sources. A failing source never blocks the others. |
| Anti-spam | No | `collectors.filter_spam` | Drops star farms (same name, same description or same name prefix on 3+ accounts). |
| Scoring | No | `scoring.py` | Freshness, popularity, cross-source resonance, emergence ("awesome-X" lists), validation. |
| Events | No | `events.py` | Conferences (developers.events, cfp.dev), online meetups (Meetup), watchlist, alerts, notifications, `cfp.json`. |
| Trends | No | `trends.py` | Languages and frameworks of new AI repos, PYPL tutorial-search shares. |
| Storage | No | `store.py` | SQLite; items kept 30 days (except starred), past events purged. |
| Outputs | No | `render.py` | Self-contained HTML dashboard, daily Markdown note. |
| Access | No | `server.py` | MCP server (stdio). |
| Judgment and teaching | **Yes, the host's model** | `skills/` | Triage, summaries, guided session, recall questions, labs, profile. |

Consequence: with no model at all you already get a ranked dashboard, CFP alerts and trends. With a weak model, only the judgment degrades.

## Data model

- `items`: `id` (prefixed by type: `repo:`, `model:`, `model-hf:`, `paper:`, `article:`), `category`, `title`, `url`, `source`, `description`, `published_at`, `first_seen`, `last_seen`, `signals` (JSON), `score`, `status` (`new`, `read`, `ignored`, `starred`), `brief`, `lab`.
- `events`: `id` (`conf:<name>-<year>` or `meetup:<url>`), `kind`, `name`, `url`, `start_at`, `end_at`, `location`, `country`, `online`, `languages`, `tags`, `cfp_url`, `cfp_open`, `cfp_close`, `cfp_close_prev`, `source`, `watched`.
- `notifications`: de-duplication key, date and text of every alert raised.
- `runs`: start, end and JSON report of every run (per source, errors, alerts, trends).

## Adding a source

1. Write `my_source(cfg) -> list[dict]` in `collectors.py` (items) or `my_source(cfg, watchlist) -> list[dict]` in `events.py` (events).
2. Register it in `COLLECTORS` or `EVENT_COLLECTORS`.
3. If it has its own popularity signal, handle it in `scoring.popularity`.
4. Add a test in `tests/`.

## MCP tools

| Tool | Role |
|---|---|
| `latest` | Ranked items, filtered by category, age, text, or only those without a summary |
| `detail` | Everything about an item |
| `save_brief` / `save_lab` | Store what the model produced (`relevant` flag for the validation bonus) |
| `mark` | `read`, `ignored` (noise), `starred` (kept beyond 30 days) |
| `upcoming_cfps` / `events` / `alerts` | Conferences, meetups, CFPs and raised alerts |
| `language_trends` | Languages and frameworks of new AI repos, PYPL |
| `profile` / `save_profile` | Skills profile in Markdown |
| `run_collection` / `rebuild_dashboard` / `status` | Control |
