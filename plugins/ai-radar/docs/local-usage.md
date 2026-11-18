# Running ai-radar locally (development)

This guide runs the pack **from this repository**, before or without the marketplace.

## Requirements

- Python 3.11 or later, and [uv](https://docs.astral.sh/uv/)
- Claude Code 2.1 or later (for the plugin)

> **Corporate network with TLS inspection**: if uv prints `invalid peer certificate: UnknownIssuer`, export `UV_SYSTEM_CERTS=1` in your shell profile (never in the repository).

## 1. The CLI alone

```sh
git clone https://github.com/mekkiamiri/harness-catalog && cd harness-catalog/plugins/ai-radar
uv sync
uv run ai-radar run        # collect + scores + alerts + dashboard (30 to 90 s)
uv run ai-radar top        # today's best items
uv run ai-radar cfps       # CFPs closing soon
uv run ai-radar open       # open the dashboard
uv run ai-radar status     # last run, paths
```

To try it without touching your real data: `AI_RADAR_HOME=/tmp/radar-try uv run ai-radar run`.

## 2. The plugin in Claude Code, without installing it

```sh
claude --plugin-dir .
```

Then in the session: `/ai-radar:profile`, then `/ai-radar:morning`. After editing a skill, run `/reload-plugins`.

## 3. The plugin installed from the local folder (like a user)

```
/plugin marketplace add ../..   # the harness-catalog folder
/plugin install ai-radar@harness-catalog
```

To remove it: `/plugin uninstall ai-radar@harness-catalog`, then `/plugin marketplace remove harness-catalog`.

## 4. Checks before a pull request

```sh
uv run python -m unittest discover -s tests   # tests
claude plugin validate .                       # plugin and marketplace manifests
```

## 5. Run it every morning

See `/ai-radar:schedule`, or directly:

- **Claude Code Desktop** → Code tab → Scheduled → daily at 7:05 → prompt `/ai-radar:morning`.
- **launchd**: [examples/launchd/io.github.ai-radar.plist](../examples/launchd/io.github.ai-radar.plist).

## Where the data lives

| File | Content |
|---|---|
| `~/.ai-radar/radar.db` | SQLite: items, scores, briefs, labs, events, alerts, runs |
| `~/.ai-radar/dashboard/index.html` | Self-contained dashboard |
| `~/.ai-radar/cfp.json` | Upcoming CFPs, for other tools |
| `~/.ai-radar/profile.md` | Your skills profile (private) |
| `~/.ai-radar/config.toml` | Commented configuration |
| `~/.ai-radar/catch-up.log` | Output of the last session-start catch-up |
| `~/ai-radar-labs/` | Generated labs |
