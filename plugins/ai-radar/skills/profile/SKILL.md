---
name: profile
description: Creates or updates the user's AI skills profile (self-assessment, completed labs, preferred stack and language) used to adapt briefs, guided sessions and labs. Use for "my level", "update my profile", on first use of ai-radar, or after a lab is completed.
---

# Skills profile

The profile is a local Markdown file (`~/.ai-radar/profile.md`) read and written with the MCP tools `profile` and `save_profile`. It is never published.

## Creation (empty profile)

Ask **at most 5 questions**, one at a time (AskUserQuestion when the answer is a choice):

1. What they master (tools, frameworks, languages).
2. What they have practiced but consider basic.
3. What they want to learn first.
4. Their main stack and languages for labs.
5. The language(s) for sessions and briefs (e.g. English, French, or both: `French + English`).

Then offer the optional modules: conferences and CFP tracking (which countries and topics, which conferences they target), and online meetups. If they want them, tell them which lines to set in `~/.ai-radar/config.toml` under `[events]` (`enabled = true`, `countries`, `topics`, `cfp_notify_keywords`, `watchlist`, `meetup`); the repository ships `examples/config-fr-jvm.toml` as a model.

## Format

```markdown
# Profile

Session language: English

## Levels
| Area | Level | Evidence |
|---|---|---|
| Claude Code | advanced | self-assessment 2026-11-15 |
| Building MCP servers | basic | one tutorial server |

## Priorities
- ...

## Stack and lab languages
- ...

## History
- 2026-11-15: created.
```

Levels: `discovery`, `basic`, `intermediate`, `advanced`, `expert`.

## Update

After a completed lab (green tests), raise the matching area by one step at most, with the evidence ("lab <name> completed on <date>"). Never lower a level without the user's agreement. Add a history line, then `save_profile`.
