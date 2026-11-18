---
name: schedule
description: Sets up the AI radar to run every morning without any action (Claude Code Desktop scheduled task, cloud task, launchd/cron or GitHub Actions). Use for "run the radar every morning", "schedule", "automate".
---

# Schedule the morning radar

Help the user choose, then guide them step by step. First ask: is their computer usually on in the morning with the Claude app open?

| Option | When |
|---|---|
| **A. Claude Code Desktop scheduled task** (recommended) | Computer on in the morning, Claude Desktop open. Local files available; if the computer was asleep, the run catches up on wake. |
| **B. Cloud scheduled task** | Computer often off. No local files: only for users who publish the dashboard to a repo. |
| **C. launchd (macOS) or cron (Linux)** | Collection, alerts and dashboard **without LLM** (no briefs). Uses no model quota. |
| **D. GitHub Actions** | Public dashboard on GitHub Pages, computer off, free. No LLM. |

## A. Desktop scheduled task

Claude Desktop → **Code** tab → **Scheduled** → new task:
- Frequency: daily, e.g. **7:05** (avoid the exact hour, which can start late).
- Prompt: `/ai-radar:morning scheduled`
- Working folder: any, e.g. `~/ai-radar-labs`.

## B. Cloud task

`/schedule` in Claude Code, prompt `/ai-radar:morning scheduled`, with the repo where the dashboard is published.

## C. launchd / cron

The plugin repository ships `examples/launchd/io.github.ai-radar.plist`: copy it to `~/Library/LaunchAgents/`, replace `UVX_PATH` with the output of `command -v uvx`, then `launchctl load ~/Library/LaunchAgents/io.github.ai-radar.plist`.
Linux: `5 7 * * * uvx --from git+https://github.com/mekkiamiri/harness-catalog@ai-radar-v0.1.0#subdirectory=plugins/ai-radar ai-radar run`.

## D. GitHub Actions

Copy `examples/github-actions/ai-radar.yml` to `.github/workflows/` in a public repo and enable Pages (source: GitHub Actions).

## Two runs a day, delivered the next morning (with a private memory repository)

Collection at 9:00 (`ai-radar run`) and at 16:30 (`ai-radar run --deliver`): the 16:30 run writes the page of the last 24 hours for the next morning and syncs it; the workflow `examples/github-actions/phone-digest.yml` in the private repository sends it at 8:00. Computer off at 16:30 = nothing sent.

## Phone

- **Push reminder**: in `~/.ai-radar/config.toml`, set `[phone] ntfy_topic` to a long random name, install the free ntfy app (iOS/Android) and subscribe to that topic. Each run sends one "radar ready" push with the top items and alerts.
- **Guided session from the phone**: Claude app → Code tab, either with Remote Control (`claude remote-control` in a folder on the computer; the computer must stay on) or Dispatch (Claude Desktop open).

In every case, the plugin's session-start hook re-runs the collection when Claude Code opens if it has not run for 20 hours (set `AI_RADAR_NO_CATCHUP=1` to turn it off). On macOS, CFP and online-event alerts also go to the notification center; on other systems they are on the dashboard and in the `alerts` tool.
