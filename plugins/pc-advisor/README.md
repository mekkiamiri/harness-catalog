<div align="center">

# pc-advisor

**Buy the right computer for dev and local AI, with real prices, not guesses.**

Describe your need. pc-advisor reads the shops now (new and refurbished, France and EU),
drops the offers that cannot meet it, and ranks the rest with the traps already checked:
soldered RAM, weak CPU, short return windows, QWERTZ keyboards.

[Install](#install-in-two-commands) · [How a session goes](#how-a-session-goes) · [Sources](docs/sources.md) · [Rules](#the-buying-rules) · [Français](README.fr.md) · [Contributing](../../.github/CONTRIBUTING.md)

[![MIT License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)
[![Tests](https://github.com/mekkiamiri/harness-catalog/actions/workflows/tests.yml/badge.svg)](https://github.com/mekkiamiri/harness-catalog/actions/workflows/tests.yml)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-orange)](https://code.claude.com/docs/en/plugins)
[![MCP](https://img.shields.io/badge/MCP-server-0969DA)](https://modelcontextprotocol.io)

</div>

---

## Why

Asking an AI "which PC should I buy?" gives you prices from its memory: often a year old, sometimes wrong
by a factor of two. And the traps that hurt are in the details: a mini PC whose 16 GB are soldered and can never
become 32, an "AI laptop" with an entry-level CPU, a shop that keeps 15% if you return it.

pc-advisor fixes both:

- **Real prices**: every price is read on the shop's page at search time, with its link and date.
- **Buying rules as code**: every trap met while buying for real became a check (see [the rules](#the-buying-rules)).
- **Starts from your need**, not from a product you already picked.
- **No affiliate links, no paid API.** It runs on your machine and uses your own model.

## Install in two commands

Requirements: [Claude Code](https://code.claude.com) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```
/plugin marketplace add mekkiamiri/harness-catalog
/plugin install pc-advisor@harness-catalog
```

Then just say *"I want a PC for dev and local AI, around 800 €"* or run `/pc-advisor:need`.

## How a session goes

1. **`/pc-advisor:need`**: a few questions, each with one line saying why it is asked (budget, minimum RAM, form factor, system, new or refurbished).
2. **`/pc-advisor:search`**: the MCP server reads the shops, checks every offer and ranks those that fit. You get one table with links, prices, dates and what to watch out for, then one clear recommendation.
3. **`/pc-advisor:listing`**: paste a Leboncoin, Back Market or eBay listing; you get the specs found, the red flags, the questions to ask the seller and the tests to run on site.

Example, live run on 15 November 2026, need = mini PC, 32 GB minimum, 900 € maximum:

| # | Price | Machine | CPU (tier) | RAM | Watch out |
|---|---|---|---|---|---|
| 1 | 830 € | GMKtec K8 Plus | Ryzen 7 8845HS (5) | 32 GB, upgradable | 7-day returns, 15% fee |
| 2 | 859 € | Minisforum UM790 Pro | Ryzen 9 7940HS (5) | 32 GB | |
| 4 | 570 € | GMKtec K16 | Ryzen 7 7735HS (4) | 32 GB | 7-day returns, 15% fee |

488 offers read from 7 shops, 426 dropped by the checks (soldered RAM under 32 GB, out of stock, over budget, weak CPU...).

## The buying rules

| Check | Why it exists |
|---|---|
| **Soldered RAM below your minimum = rejected** | LPDDR memory, Apple silicon, Ryzen AI Max and Intel Core Ultra 200V can never be upgraded. |
| **Weak CPU rejected for dev** | N100/N150, Celeron, Core 3, U300 are sold as "dev PCs"; they are office machines. |
| **CPU traps explained** | U vs HS vs T suffixes; "7730U" is a 2021 Zen 3 chip renamed. |
| **Barebones and upgradable machines listed apart** | Their price does not include RAM, SSD or the OS. |
| **Shop policy warnings** | 7-day returns with a 15% fee, return shipping on you, prorated refunds. |
| **QWERTZ warning** | German refurbishers often sell German-layout laptops. |
| **Refurbished vs new** | In 2026 some refurbished Macs cost more than the newer model new. |
| **Honesty** | Prices not read by the tools are never presented as verified; missing or blocked sources are named. |

## Sources

Read automatically: GMKtec, Beelink, Minisforum, Ninkear, Chuwi, ACEMAGIC (official EU stores) and the Apple Store France (new and certified refurbished).
Planned: Lapstore, Refurbed, Label Emmaüs, AfB. Never scraped (protected against bots): Leboncoin, Back Market, Amazon, eBay, plus Costco France (no public catalog to read yet, membership required). For those you get ready-made searches and the listing check.
Details, methods and return policies: [docs/sources.md](docs/sources.md).

pc-advisor fetches politely: an honest user agent, robots.txt respected, one request per second per site, a 6-hour cache, and it **never tries to get around a protection**.

## Command line

```sh
uv run pc-advisor search --budget 900 --min-ram 32 --form mini
uv run pc-advisor search --system macos --min-ram 32 --json
echo "ThinkCentre M920q i5-8500T 16 Go DDR4 SSD 256 Go" | uv run pc-advisor check --price 150 --min-ram 32
uv run pc-advisor cpu "Ryzen 7 7730U"
uv run pc-advisor sources
```

## Limits

- Prices move. Always check the exact configuration in the cart.
- The CPU tiers are buying guidance, not benchmarks.
- A shop that changes its page can break its connector: the run reports it, the others continue.

## License

MIT. Not affiliated with any shop or brand.
