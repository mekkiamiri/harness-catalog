"""Where offers come from, how each site is read, and what its return policy really says.

status:
  auto     — read automatically by a connector.
  planned  — readable, connector not written yet (contributions welcome).
  manual   — protected against bots (HTTP 403): pc-advisor never tries to get around it. The skill gives
             the user ready-made searches and analyses the listings they paste.

Policies were read on each site's own pages on the date in `checked`. They change: the skill must say so.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    kind: str                       # shopify | apple_fr | manual | planned
    status: str                     # auto | planned | manual
    country: str
    condition: str                  # new | refurbished | used | mixed
    returns: str = ""
    warranty: str = ""
    caution: str = ""
    checked: str = "2026-11-15"
    search_hint: str = ""           # for manual sources: what to type
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)


SOURCES: list[Source] = [
    # --- Chinese mini PC and laptop brands, official EU stores (Shopify: full catalog in /products.json) ---
    Source("gmktec", "GMKtec (FR store)", "https://gmktec.fr", "shopify", "auto", "CN/FR", "new",
           returns="7 days; 15% restocking fee on change of mind; you pay shipping for warranty repairs",
           warranty="2 years (commercial)",
           caution="Short return window: test everything the day it arrives.", tags=("mini",)),
    Source("beelink", "Beelink (EU store)", "https://eu.bee-link.com", "shopify", "auto", "CN/EU", "new",
           warranty="see store", caution="Several models have soldered LPDDR5 RAM.", tags=("mini",)),
    Source("minisforum", "Minisforum (EU store)", "https://minisforumpc.eu", "shopify", "auto", "CN/EU", "new",
           returns="30 days", warranty="2 years EU, ships from an EU warehouse", tags=("mini",)),
    Source("ninkear", "Ninkear", "https://store.ninkear.com", "shopify", "auto", "CN/EU", "new",
           returns="30 days with a prepaid return label; 14-day EU withdrawal right", warranty="2 years EU",
           tags=("laptop", "mini")),
    Source("chuwi", "Chuwi (EU store)", "https://eu.chuwi.com", "shopify", "auto", "CN/EU", "new",
           returns="you pay return shipping, including international, unless the product is faulty",
           tags=("laptop", "mini")),
    Source("acemagic", "ACEMAGIC (FR store)", "https://acemagic.fr", "shopify", "auto", "CN/FR", "new",
           returns="30 days; return shipping on you if not faulty; refunds decrease with age (80% at 7-12 months)",
           caution="Some ACEMAGIC mini PCs shipped with preinstalled malware in 2024: reinstall the OS on arrival.",
           tags=("laptop", "mini")),
    # --- Apple ---
    Source("apple_fr", "Apple Store France (new + certified refurbished)", "https://www.apple.com/fr/shop",
           "apple_fr", "auto", "FR", "mixed", returns="14 days", warranty="1 year (new and refurbished)",
           caution="In 2026 some refurbished Macs cost more than the newer model new: always compare."),
    # --- Refurbished professional machines (planned connectors) ---
    Source("lapstore", "Lapstore.de", "https://www.lapstore.de", "planned", "planned", "DE", "refurbished",
           returns="14 days, free return", warranty="15 months",
           caution="German shop: laptops often have a QWERTZ keyboard."),
    Source("refurbed", "Refurbed.fr", "https://www.refurbed.fr", "planned", "planned", "AT/EU", "refurbished",
           returns="free return label", warranty="12 months minimum, extendable"),
    Source("label_emmaus", "Label Emmaüs", "https://www.label-emmaus.co", "planned", "planned", "FR", "refurbished",
           warranty="often 1 year (per seller)"),
    Source("afb", "AfB France", "https://www.afbshop.fr", "planned", "planned", "FR", "refurbished",
           returns="change-of-mind return shipping on you", warranty="see store"),
    # --- Protected marketplaces: manual only ---
    Source("leboncoin", "Leboncoin", "https://www.leboncoin.fr", "manual", "manual", "FR", "used",
           search_hint="Hand delivery + test on site. Searches: 'OptiPlex Micro i7', 'ThinkCentre M920q', "
                       "'EliteDesk 800 G5 Mini', 'mini pc sans RAM', 'lot mini PC', 'HP Z440', 'Mac mini M2 16Go'."),
    Source("backmarket", "Back Market", "https://www.backmarket.fr", "manual", "manual", "FR", "refurbished",
           search_hint="Marketplace: check the seller's rating and the grade, not only the price."),
    Source("amazon", "Amazon.fr", "https://www.amazon.fr", "manual", "manual", "FR", "mixed",
           search_hint="Filter on 'sold by Amazon' or the brand's official store, shipped by Amazon (30-day returns)."),
    Source("ebay", "eBay.fr", "https://www.ebay.fr", "manual", "manual", "EU", "used",
           search_hint="Use eBay Money Back Guarantee; avoid direct bank transfers. Auctions: filter on "
                       "'Enchères', set your maximum before bidding, and remember shipping."),
    # --- Auctions: no withdrawal right, buyer's fees on top, sold as is. Manual: paste the lot into the listing check ---
    Source("agorastore", "Agorastore (public sector surplus auctions)", "https://www.agorastore.fr", "manual", "manual",
           "FR", "used", returns="none: auction sale, no 14-day withdrawal right",
           caution="Buyer's fees are added to the winning bid; pickup on site is often required. Ex-school or "
                   "town hall laptops: check for a BIOS lock or a company management lock.",
           checked="2026-11-17",
           search_hint="Category Informatique: 'lot ordinateurs portables', 'PC portable', 'ThinkPad', 'Latitude', "
                       "'MacBook'. Lots of several machines are cheap per unit but sold untested."),
    Source("encheres_domaine", "Enchères Domaine (French State sales)", "https://encheres-domaine.gouv.fr", "manual",
           "manual", "FR", "used", returns="none: auction sale",
           caution="Mostly vehicles and furniture; IT lots are rare and sold as is. Buyer's fees apply.",
           checked="2026-11-17", search_hint="Search 'informatique' or 'ordinateur'; check the visit dates."),
    Source("interencheres", "Interencheres (auction houses)", "https://www.interencheres.com", "manual", "manual",
           "FR", "used", returns="none: auction sale",
           caution="Protected against bots (HTTP 403). Buyer's fees often 20-30% on top of the bid, plus "
                   "shipping or pickup; liquidation lots are rarely tested.",
           checked="2026-11-17",
           search_hint="Category High-Tech / Informatique, or 'liquidation judiciaire informatique'. Judicial "
                       "sales have lower fees than voluntary ones."),
    Source("catawiki", "Catawiki", "https://www.catawiki.com", "manual", "manual", "EU", "mixed",
           returns="per lot: read the seller's terms", caution="Protected against bots (HTTP 403). "
           "Buyer's protection fee and shipping added; sellers are often outside France (keyboard layout).",
           checked="2026-11-17", search_hint="Section Électronique > ordinateurs portables."),
    # --- Warehouse club: catalog is a JavaScript app with no public product feed, so manual for now ---
    Source("costco", "Costco France", "https://www.costco.fr", "manual", "manual", "FR", "new",
           returns="read on costco.fr before buying (electronics can have shorter limits than other items)",
           warranty="see store",
           caution="Membership card needed to buy; add its yearly cost to the price when comparing.",
           checked="2026-11-17",
           search_hint="Rayon Electronique > Informatique (portables, PC de bureau, Mac). Bundles often hide "
                       "an older CPU or soldered RAM: paste the product page into /pc-advisor:listing to check it."),
]


def by_id(source_id: str) -> Source | None:
    return next((s for s in SOURCES if s.id == source_id), None)


def automatic() -> list[Source]:
    return [s for s in SOURCES if s.status == "auto"]
