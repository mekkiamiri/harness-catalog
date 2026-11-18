"""Apple Store France: new desktop Macs (starting price per chip) and certified refurbished Macs.

New: the "buy" page embeds a `"prices"` object keyed by chip tier (e.g. "m6-12-12" = M6, 12 CPU cores,
12 GPU cores) and the list of standard configurations. We pair each tier with its smallest configuration
and flag the price as a starting price.
Refurbished: the listing links to product pages; each page gives the price (raw_amount), the unified memory
and the SSD size.
"""

from __future__ import annotations

import html
import re

from .. import http, parse
from ..models import Offer, iso
from ..sources import Source

BASE = "https://www.apple.com"
NEW_PAGES = {
    "Mac mini": "/fr/shop/buy-mac/mac-mini",
    "Mac Studio": "/fr/shop/buy-mac/mac-studio",
}
REFURB_PAGES = {
    "Mac mini": ("/fr/shop/refurbished/mac/mac-mini", "mac-mini", "mini"),
    "Mac Studio": ("/fr/shop/refurbished/mac/mac-studio", "mac-studio", "desktop"),
    "MacBook Air": ("/fr/shop/refurbished/mac/macbook-air", "macbook-air", "laptop"),
    "MacBook Pro": ("/fr/shop/refurbished/mac/macbook-pro", "macbook-pro", "laptop"),
}
MAX_REFURB_PER_PAGE = 25

# The display price holds escaped HTML (\"nowrap\"), so skip up to the numeric "amount" without parsing it.
_TIER_PRICE = re.compile(r'"([a-z0-9]+)-(\d+)-(\d+)":\{"comparativeDisplayPrice":(?:(?!"amount").){0,600}?"amount":([\d.]+)')
_CONFIG = re.compile(r"(Mac (?:mini|Studio)), puce (M\d+(?: Pro| Max| Ultra)?), CPU (\d+) cœurs, GPU (\d+) cœurs, "
                     r"(\d+) Go de mémoire, (\d+ (?:Go|To)) de stockage")
_PRODUCT_LINK = re.compile(r'/fr/shop/product/([a-z0-9]{5,8})/a/([^"?#\s]+)', re.I)
_RAW_PRICE = re.compile(r'"currentPrice":\{"amount":"[^"]*","raw_amount":"([\d.]+)"')
_SSD = re.compile(r"SSD de (\d+)\s?(Go|To)")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text).replace("\xa0", " ")).strip()


def new_offers(page_html: str, product: str, url: str, fetched_at: float) -> list[Offer]:
    text = _clean(page_html)
    configs = {}
    for name, chip, cpu, gpu, ram, storage in _CONFIG.findall(text):
        key = (chip.lower().replace(" ", ""), int(cpu), int(gpu))
        configs.setdefault(key, []).append((int(ram), storage, chip))
    out = []
    seen = set()
    for chip_key, cpu, gpu, amount in _TIER_PRICE.findall(page_html):
        key = (chip_key, int(cpu), int(gpu))
        if key in seen or key not in configs:
            continue
        seen.add(key)
        ram, storage, chip = min(configs[key])
        out.append(Offer(
            source="apple_fr", shop="Apple Store France", title=f"{product} {chip} ({cpu}-core CPU, {gpu}-core GPU)",
            url=url, price_eur=float(amount), condition="new",
            form="mini" if product == "Mac mini" else "desktop",
            variant=f"{ram} GB / {storage.replace('Go', 'GB').replace('To', 'TB')}",
            cpu=f"Apple {chip}", ram_gb=ram, ram_soldered=True, storage_gb=parse.storage_gb(storage + " SSD"),
            starting_price=True, fetched_at=iso(fetched_at),
            notes=[f"Configurations of this chip: {sorted(r for r, _, _ in configs[key])} GB"],
        ))
    return out


def refurb_links(listing_html: str, slug_word: str) -> list[str]:
    links, seen = [], set()
    for pid, slug in _PRODUCT_LINK.findall(listing_html):
        if pid in seen or slug_word not in slug.lower():
            continue
        seen.add(pid)
        links.append(f"{BASE}/fr/shop/product/{pid}/a/{slug}")
    return links[:MAX_REFURB_PER_PAGE]


def refurb_offer(page_html: str, url: str, form: str, fetched_at: float) -> Offer | None:
    title_m = re.search(r"<title>([^<]+)</title>", page_html)
    price_m = _RAW_PRICE.search(page_html)
    if not title_m or not price_m:
        return None
    title = _clean(title_m.group(1)).replace(" - Apple (FR)", "")
    text = _clean(page_html)
    ssd = _SSD.search(text)
    return Offer(
        source="apple_fr", shop="Apple Store France (refurbished)", title=title, url=url,
        price_eur=float(price_m.group(1)), condition="refurbished", form=form,
        cpu=parse.cpu(title), ram_gb=parse.ram_gb(text), ram_soldered=True,
        storage_gb=parse.storage_gb(f"{ssd.group(1)} {ssd.group(2)} SSD") if ssd else None,
        fetched_at=iso(fetched_at),
    )


def fetch(source: Source, use_cache: bool = True) -> list[Offer]:
    out: list[Offer] = []
    for product, path in NEW_PAGES.items():
        body, at = http.get(BASE + path, use_cache)
        out.extend(new_offers(body.decode("utf-8", "replace"), product, BASE + path, at))
    for product, (path, slug_word, form) in REFURB_PAGES.items():
        body, _ = http.get(BASE + path, use_cache)
        for link in refurb_links(body.decode("utf-8", "replace"), slug_word):
            try:
                page, at = http.get(link, use_cache)
            except http.Blocked:
                raise
            except Exception:
                continue
            offer = refurb_offer(page.decode("utf-8", "replace"), link, form, at)
            if offer:
                out.append(offer)
    return out
