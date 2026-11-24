# Changelog

## 0.1.2 (2026-11-24)

- New source: GitHub Trending (daily and weekly pages, AI repos only). The GitHub search only sees repos created inside the window, so an older repo that suddenly takes off was missed (plannotator: 11 months old, #1 of the week). Stars per day come from the stars gained over the period.

## 0.1.1 (2026-11-17)

Features shipped after the 0.1.0 tag. The version bump lets installed plugins receive them (Claude Code updates a plugin only when its version changes).
- Two runs a day (`run`, `run --deliver` at 16:30) delivered the next morning; Reddit feeds (rate-limited politely); proactive "Proposals for you" (daily page + MCP tool `proposals`).
- Optional `ai-radar sync` with your own private repository: field-by-field merge of statuses, briefs, labs, profile and raised alerts between computers; daily page and a workflow example that notifies the phone from GitHub.
- Repos tab: repositories worth watching or contributing to (newsletter mentions, growth, good-first-issue tickets, organization backing, activity, focus topics).

## 0.1.0 (2026-11-15)

First release.
- Collection without LLM: GitHub (new repos, "awesome" lists), OpenRouter, Hugging Face (trending models, daily papers), RSS and Atom feeds.
- Readable score: freshness, popularity, cross-source resonance, emergence, validation by the model; star-farm and lure-account filters; only http(s) links.
- Opt-in conferences and CFPs (developers.events, cfp.dev with opening dates), opt-in online meetups (Meetup), watchlist, de-duplicated alerts (opening, 30/14/7/2 days, date moved), macOS notifications, `cfp.json`.
- Optional phone push through ntfy (daily "radar ready" + alerts).
- Language and framework trends (new AI repos, PYPL).
- Self-contained dashboard (30 days, events, languages), daily Markdown note.
- MCP server (14 tools, one collection at a time, safe concurrent access); Claude Code plugin with 4 skills (`morning` guided session, `lab`, `profile`, `schedule`) and a session-start catch-up.
