# Changelog

## Unreleased

- Auctions: Agorastore, Enchères Domaine, Interencheres and Catawiki as manual sources; the listing check recognises an auction lot and adds its rules (buyer's fees, no withdrawal right, sold as is, maximum bid).
- Costco France added as a manual source (ready-made searches + listing check; membership required).

## 0.1.0 — 2026-11-15

First version.

- Skills: `need` (questions with their one-line why), `search` (ranked real offers), `listing` (pasted listing check).
- MCP server: `sources`, `search_offers`, `check_listing`, `cpu_tier`.
- Connectors: Shopify stores (GMKtec, Beelink, Minisforum, Ninkear, Chuwi, ACEMAGIC) and Apple Store France (new starting prices and certified refurbished).
- Buying checks: soldered RAM, weak CPU, form factor, system, condition, budget, shop return policy, QWERTZ keyboards, barebones.
- Polite fetching: honest user agent, robots.txt, one request per second per host, 6-hour cache, no protection bypass.
