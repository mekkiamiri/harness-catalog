---
name: need
description: Turn "I want a good PC for dev / local AI" into a precise buying need (budget, minimum RAM, form factor, system, new or refurbished, use, keyboard) in a few questions, each with a one-line reason. Use when the user wants to buy a computer, laptop, mini PC or Mac, says "which PC should I buy", "quel PC acheter", "je veux acheter un ordinateur", or before /pc-advisor:search when the need is unclear.
---

# Buying need

Goal: a need precise enough to search real offers, in **at most 2 rounds of questions**. Answer in the user's language (French or English).

## Rules

- Use AskUserQuestion. **Every question carries one line saying why it is asked and what it changes** (the user wants to know what each answer is for). Example: "Budget? — it filters out offers above it and tells me how much room is left for RAM or an SSD."
- Never ask what the user already said in the conversation. Never ask more than 4 questions at once.
- Offer a recommended default as the first option, marked "(Recommended)".

## The questions (skip those already answered)

| Field | Question | Why (say it in one line) | Default |
|---|---|---|---|
| `use` | Main use: dev, local AI, office? | Decides the minimum CPU tier and how much RAM matters. | dev |
| `budget_max` | Maximum budget, all taxes included? | Drops offers above it; the headroom also ranks offers. | none |
| `min_ram_gb` | Minimum RAM: 16, 32, 64 GB? | Below it an offer with soldered RAM is rejected, since it can never be upgraded. | 16 (dev), 32 (AI) |
| `form` | Desktop tower, mini PC, laptop, or any? | A mini PC takes no space but no graphics card; a laptop must carry its own screen. | any |
| `system` | macOS, Linux, Windows, or any? | macOS means Apple silicon: memory fixed for life, chosen at purchase. | any |
| `condition` | New, refurbished, used, or any? | Refurbished saves money with a warranty; used is cheapest but must be tested on site. | any |
| `keyboard` | Keyboard layout (laptops only)? | German shops often sell QWERTZ laptops. | AZERTY |

## Sizing hints to share when relevant

- Dev (IDE, Docker, a few services): 16 GB works, **32 GB is comfortable**. CPU tier 3 or more.
- Local AI: RAM (or VRAM) decides which models run. 32 GB runs 7–8B models quantized on the CPU; 64 GB+ unified memory (Apple Pro/Max, Ryzen AI Max) runs much larger ones. For model-by-model sizing, suggest [llmfit](https://github.com/AlexsJones/llmfit).
- A very small budget (< 300 €): be honest. No machine runs large models; suggest a used pro mini PC plus free cloud GPUs (Colab, Kaggle) for heavy AI.

## Output

Summarise the need in one short table, then hand over to the `search` skill with these exact fields:
`budget_max, min_ram_gb, form, system, condition, use, keyboard`.
