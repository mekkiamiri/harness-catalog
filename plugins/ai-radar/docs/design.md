# Design decisions

| # | Decision | Why |
|---|---|---|
| 1 | **A portable pack, not another harness**: CLI + MCP server + skills plugged into existing harnesses (Claude Code, Hermes, OpenClaw) | Agent loops, schedulers, model choice and memory already exist. What nobody does is the domain: early detection, resonance, adaptive learning, CFP tracking. |
| 2 | **Bring your own model** | No vendor lock-in; free models work for collection-only use. |
| 3 | **No LLM in collection, scoring, alerts or trends** | They work with no model; a weak model only degrades judgment and teaching. |
| 4 | **Claude Code as the reference host, distributed through a plugin marketplace** | Two-command install; skills + MCP server + hooks in one package. Other hosts reuse the MCP server and the Agent Skills format. |
| 5 | **Python** for the CLI and the MCP server | Richest MCP SDK and AI ecosystem; one language for the core. |
| 6 | **SQLite** as the single source of truth, plus a self-contained HTML dashboard | Same data for the dashboard, MCP and exports; the dashboard can be published on GitHub Pages for free. |
| 7 | **Guided learning instead of links**: the model reads the sources and teaches (what we found → choice → dense summary → recall question → optional link → next step) | Reading time is the bottleneck. Good summaries carry most of the knowledge; recall makes it stick; labs turn it into skill. |
| 8 | **Labs are runnable** (starter code + tests) | Automatic validation also measures the user's level. |
| 9 | **CFP dates are leads, never facts** (`verified: false`); push notifications only for the watchlist and well-known conferences; one de-duplicated alert per event and step | A community agenda is not an official source; alert fatigue kills the tool. |
| 10 | **Never write into another tool's files**: other tools read `radar.db` (read-only) or `cfp.json` | A watchlist is read, never modified. |
| 11 | **Morning run by the host's scheduler** (Desktop scheduled task), with a session-start catch-up | Zero infrastructure; nothing is lost when the computer was off. |
| 12 | **MIT license** | Simplest for contributors; same as Hermes and OpenClaw. |
