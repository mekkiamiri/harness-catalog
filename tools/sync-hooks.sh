#!/usr/bin/env bash
# Copy the reference pre-push hook into one or more repositories and enable it.
# Usage: tools/sync-hooks.sh <repo-path> [<repo-path>...]
# Repository-specific checks stay in each repository's .githooks/pre-push.local (never overwritten).
set -eu
src="$(cd "$(dirname "$0")" && pwd)/githooks/pre-push"
[ $# -gt 0 ] || { echo "usage: $0 <repo-path> [...]"; exit 1; }
for repo in "$@"; do
  git -C "$repo" rev-parse --show-toplevel >/dev/null 2>&1 || { echo "✗ not a git repository: $repo"; continue; }
  mkdir -p "$repo/.githooks"
  if cmp -s "$src" "$repo/.githooks/pre-push"; then echo "= $repo (already up to date)"; continue; fi
  cp "$src" "$repo/.githooks/pre-push"; chmod +x "$repo/.githooks/pre-push"
  git -C "$repo" config core.hooksPath .githooks
  echo "✓ $repo"
done
