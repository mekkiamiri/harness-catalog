#!/bin/sh
# Safety net: if the morning run did not happen (computer off, app closed), run it in the
# background when Claude Code starts. Never blocks the session. Turn off with AI_RADAR_NO_CATCHUP=1.
[ -n "$AI_RADAR_NO_CATCHUP" ] && exit 0
if ! command -v uv >/dev/null 2>&1; then
  echo "ai-radar: 'uv' is not installed, the radar cannot run. Install it: https://docs.astral.sh/uv/getting-started/installation/"
  exit 0
fi
LOG="${AI_RADAR_HOME:-$HOME/.ai-radar}/catch-up.log"
mkdir -p "$(dirname "$LOG")"
if [ -n "$CLAUDE_PLUGIN_OPTION_GITHUB_TOKEN" ]; then
  export AI_RADAR_GITHUB_TOKEN="$CLAUDE_PLUGIN_OPTION_GITHUB_TOKEN"
fi
# Same environment as the MCP server (kept in the plugin data folder, not in the plugin itself).
export UV_PROJECT_ENVIRONMENT="${CLAUDE_PLUGIN_DATA:-$HOME/.ai-radar}/venv"
nohup uv run --quiet --frozen --project "$CLAUDE_PLUGIN_ROOT" ai-radar run --if-older-than 20 >"$LOG" 2>&1 &
exit 0
