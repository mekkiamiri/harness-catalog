# Changelog

## 0.1.2 (2026-11-24)

- New source: GitHub Trending (daily and weekly pages, AI repos only). The GitHub search only sees repos created inside the window, so an older repo that suddenly takes off was missed (plannotator: 11 months old, #1 of the week). Stars per day come from the stars gained over the period.
- GitHub Trending per language too (`trending_languages`, default Java, Kotlin, Python, TypeScript, Go, Rust): Java AI repos (LangChain4j, Spring AI...) rarely reach the all-languages page.
- New source: Maven Central releases of watched artifacts (`maven_watch`, default Spring AI, LangChain4j, Google ADK, MCP Java SDK, Anthropic Java SDK, A2A Java SDK, Spring AI A2A).
- Malware lures dropped by content, not only by star farms: "Adobe Acrobat Pro - ... on Windows 10/11" in a "-win" repo, cracks, keygens, "alternative access" (6 such repos had reached the daily top; GitHub deleted them days later).
- The daily "Top of the day" keeps at most 2 items per category, so six GitHub repos can no longer hide every article, paper and model.
- Repos with no real description get the first paragraph of their README (read from raw.githubusercontent.com, no API quota, 60 per run).
- "For you" verdict on every card (yes / maybe / no from `[repos] focus`, or the **For you** line of a brief), and a "For me only" filter.
- 🎧 Listen: the dashboard reads the visible cards aloud with the browser's own speech synthesis (free, offline, voice and speed selectable).
- `[people] github`: accounts you follow (colleagues, teams). Their repos created or pushed in the last 90 days always show up, even with zero stars, with a +25 score bonus and a 👥 tag.
- Alerts on the dashboard link to their events (and CFP pages); a grouped alert is shown once.
- `sync` also copies the dashboard to the private repository (`ai-radar/dashboard/index.html`), so it can be published on a private site and opened on a phone. HTTP error reasons are dropped from the dashboard (a company proxy writes its own name there).
- `[repos] watch`: repos followed by name (e.g. a project you want to contribute to) are always in the Repos tab with their contribution analysis, whatever their age or growth, with a 📌 tag and a +25 score bonus.
- New feed: Show HN about AI from 3 points, where authors announce their tools before any newsletter.

## 0.1.1 (2026-11-17)

Features shipped after the 0.1.0 tag. The version bump lets installed plugins receive them (Claude Code updates a plugin only when its version changes).
- Two runs a day (`run`, `run --deliver` at 16:30) delivered the next morning; Reddit feeds (rate-limited politely); proactive "Proposals for you" (daily page + MCP tool `proposals`).
- Optional `ai-radar sync` with your own private repository: field-by-field merge of statuses, briefs, labs, profile and raised alerts between computers; daily page and a workflow example that notifies the phone from GitHub.
- Reliability: `run --wait-network MINUTES` for scheduled runs; a run that loses the network stops quickly and is marked partial; failing RSS feeds are reported as warnings; the phone-digest example delivers at 8:00 through ntfy's `At` header instead of a GitHub cron.
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
