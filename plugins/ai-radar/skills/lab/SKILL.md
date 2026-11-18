---
name: lab
description: Builds a runnable lab (starter code + validation tests) on something from the AI radar, one step above the user's level, and guides them through it. Use for "make me a lab on...", "I want to practice...", "test this framework", or when a brief suggests a lab.
---

# Adaptive lab

A lab is a small **runnable** project the user completes by making tests pass. The tests also measure their level.

## Prepare

1. Find the item: `latest(text=...)` then `detail(id)`. Read its brief and its real source (README, docs, paper). Never build a lab on an API you have not checked in the current documentation.
2. Read the `profile`. Target the step **just above** their level on that topic.
3. Pick the language from the profile and the tool's ecosystem. For a "should I switch language?" question, build the **same small task in two languages** (e.g. Java vs Python) so the user compares by doing.

## Build

Create `~/ai-radar-labs/<date>-<slug>/` (or the folder the user gives) with:

- `README.md`: one-sentence goal, why it is useful now, prerequisites, **numbered steps with hints (no solution)**, validation command, going further;
- starter code with clear `TODO`s;
- **automated tests** that fail at first and pass when the lab is done (`pytest`, `mvn test`, `npm test`...);
- a `solution/` folder only if the user asks.

Check yourself that the project installs and that the tests **fail** at first for the right reason.

## Guide

Walk the user through it step by step: explain the concept of the step in a few lines, let them code, run the tests with them, give the next hint only when needed.

## Record

`save_lab(id, ...)` with: path, goal, target level, validation command; then `rebuild_dashboard`. When the tests pass, offer to update the profile (`profile` skill).
