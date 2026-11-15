# Sources / Sources

Policies were read on each site's own pages on **15 November 2026**. They change: the plugin says so.
*Les conditions ont été lues sur les pages de chaque site le 15 novembre 2026. Elles changent : le plugin le rappelle.*

| Source | Status | How it is read | Returns | Warranty |
|---|---|---|---|---|
| GMKtec (gmktec.fr) | auto | Shopify catalog `/products.json` | 7 days, 15% fee on change of mind, warranty shipping on you | 2 years (commercial) |
| Beelink (eu.bee-link.com) | auto | Shopify catalog | see store | see store |
| Minisforum (minisforumpc.eu) | auto | Shopify catalog | 30 days | 2 years EU, EU warehouse |
| Ninkear (store.ninkear.com) | auto | Shopify catalog | 30 days, prepaid return label | 2 years EU |
| Chuwi (eu.chuwi.com) | auto | Shopify catalog | return shipping on you unless faulty | see store |
| ACEMAGIC (acemagic.fr) | auto | Shopify catalog | 30 days, prorated refunds after 6 months | malware incident in 2024: reinstall the OS |
| Apple Store France | auto | buy pages (starting price per chip) + certified refurbished product pages | 14 days | 1 year |
| Lapstore.de | planned | product pages (`itemprop="price"`) | 14 days, free return | 15 months; QWERTZ laptops |
| Refurbed.fr | planned | JSON-LD offers | free return label | 12 months minimum |
| Label Emmaüs | planned | catalog pages | per seller | often 1 year |
| AfB France | planned | catalog pages | change-of-mind shipping on you | see store |
| Leboncoin, Back Market, Amazon, eBay | manual | **never scraped** (protected): ready-made searches + `/pc-advisor:listing` | | |

## Add a shop / Ajouter une boutique

1. Check the site allows it: robots.txt, no anti-bot page (HTTP 403 means no).
2. If it is a Shopify store (`/products.json` answers), adding it is one line in `src/pc_advisor/sources.py`.
3. Otherwise write `src/pc_advisor/connectors/<shop>.py` with `fetch(source) -> list[Offer]`, a synthetic sample in `tests/test_connectors.py` (never a copied page), and read the shop's return and warranty pages for the `returns` / `warranty` fields.
