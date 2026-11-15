# Contributing to ai-radar

Thank you! The most useful contributions:

- **a new source** that spots AI news, conferences or CFPs early;
- **a better signal**: resonance, emergence, anti-spam, trends;
- **a lab type** or better skills (guided session, recall questions);
- **support for another harness** (Hermes, OpenClaw, Cursor...).

## How

1. Open an issue first for any significant change.
2. Follow [docs/local-usage.md](../plugins/ai-radar/docs/local-usage.md) to run the project.
3. Before the pull request (from `plugins/<harness>/`):
   ```sh
   uv run python -m unittest discover -s tests
   claude plugin validate .
   ```
4. Add a test for every new source or scoring change.

## Rules

- **No LLM in collection, scoring, alerts or trends**: they must work without a model. Judgment and teaching go through the skills and the host's model.
- **No dependency without a reason**: collection uses the standard library only.
- **No personal data or secrets** in the repository (profile, database, tokens).
- **A failing source must never block the others.**
- **Never present a CFP date as verified.**
