"""Shopify stores publish their whole catalog as JSON at /products.json (prices, variants, stock).

Used by most Chinese mini PC and laptop brands' official EU stores. Prices are in the store currency
(EUR for the stores listed in sources.py).
"""

from __future__ import annotations

import re

from .. import http, parse
from ..models import Offer, iso
from ..sources import Source

MAX_PAGES = 4
REFURB = re.compile(r"refurbished|reconditionn|renewed|open[- ]box|b-?stock", re.I)
NOT_A_COMPUTER = re.compile(
    r"motherboard|carte mère|\bdock\b|docking|keyboard|clavier|mouse|souris|backpack|sac\b|sleeve|stand|cooler|"
    r"charger|chargeur|cable|câble|adapter|hub\b|monitor|écran portable|\bNAS\b|gift|cadeau|tablet|tablette|"
    r"warranty|garantie|protection plan|\bSSD\b(?!.*(?:ryzen|intel|core))",
    re.I,
)


def products(source: Source, use_cache: bool = True) -> tuple[list[dict], float]:
    items: list[dict] = []
    fetched_at = 0.0
    for page in range(1, MAX_PAGES + 1):
        data, at = http.get_json(f"{source.url}/products.json?limit=250&page={page}", use_cache)
        fetched_at = fetched_at or at
        batch = data.get("products", []) if isinstance(data, dict) else []
        items.extend(batch)
        if len(batch) < 250:
            break
    return items, fetched_at


def offers_from(source: Source, catalog: list[dict], fetched_at: float) -> list[Offer]:
    out: list[Offer] = []
    for product in catalog:
        try:
            title = product.get("title", "")
            body = parse.text_of(product.get("body_html"))
            if NOT_A_COMPUTER.search(title) and not parse.cpu(title):
                continue
            cpu = parse.cpu(title) or parse.cpu(body)
            if not cpu:
                continue
            form = "laptop" if parse.looks_like_laptop(title + " " + product.get("product_type", "")) else "mini"
            for variant in product.get("variants", []):
                vtitle = variant.get("title", "")
                if vtitle.lower() == "default title":
                    vtitle = ""
                text = f"{title} {vtitle}"
                price = float(variant.get("price") or 0)
                if price <= 0:
                    continue
                barebone = parse.is_barebone(vtitle)
                variant_cpu = parse.cpu(vtitle) or cpu
                out.append(Offer(
                    source=source.id, shop=source.name, title=title.strip(),
                    url=f"{source.url}/products/{product.get('handle')}?variant={variant.get('id')}",
                    price_eur=price, condition="refurbished" if REFURB.search(f"{title} {vtitle}") else "new",
                    form=form, variant=vtitle.strip(),
                    available=bool(variant.get("available")),
                    cpu=variant_cpu,
                    ram_gb=None if barebone else parse.ram_gb(vtitle or text),
                    ram_soldered=parse.ram_soldered(f"{vtitle} {body}", variant_cpu),
                    storage_gb=None if barebone else parse.storage_gb(vtitle or text),
                    barebone=barebone, fetched_at=iso(fetched_at),
                ))
        except (TypeError, ValueError, AttributeError):
            continue  # one malformed product never stops the others
    return out


def fetch(source: Source, use_cache: bool = True) -> list[Offer]:
    catalog, at = products(source, use_cache)
    return offers_from(source, catalog, at)
