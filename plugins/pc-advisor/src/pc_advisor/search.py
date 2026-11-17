"""From a Need to a ranked list: fetch every automatic source, check each offer, drop blockers, rank the rest.

The score is deliberately simple and returned with its parts, so the skill can explain every position.
"""

from __future__ import annotations

from . import checks, cpu as cpu_mod, http
from .connectors import apple_fr, shopify
from .models import Need, Offer
from .sources import Source, automatic, by_id

CONNECTORS = {"shopify": shopify.fetch, "apple_fr": apple_fr.fetch}


def collect(source_ids: list[str] | None = None, use_cache: bool = True) -> tuple[list[Offer], list[dict]]:
    """Return (offers, report). A failing source never blocks the others."""
    chosen: list[Source] = [s for s in (by_id(i) for i in source_ids) if s] if source_ids else automatic()
    offers: list[Offer] = []
    report: list[dict] = []
    for source in chosen:
        fetch = CONNECTORS.get(source.kind)
        if not fetch or source.status != "auto":
            report.append({"source": source.id, "status": source.status, "offers": 0,
                           "note": source.search_hint or "no connector yet"})
            continue
        try:
            found = fetch(source, use_cache)
            offers.extend(found)
            report.append({"source": source.id, "status": "ok", "offers": len(found)})
        except http.Blocked as e:
            report.append({"source": source.id, "status": "blocked", "offers": 0, "note": str(e)})
        except Exception as e:  # network error, page changed...
            report.append({"source": source.id, "status": "error", "offers": 0, "note": f"{type(e).__name__}: {e}"[:200]})
    return offers, report


def meets_need(offer: Offer, need: Need) -> bool:
    """Ready to use as delivered: enough RAM, not a barebone."""
    return not offer.barebone and bool(offer.ram_gb) and offer.ram_gb >= need.min_ram_gb


def score(offer: Offer, need: Need, reference_price: float | None = None) -> dict:
    """Bounded parts: CPU up to 100 (one tier = 20), RAM fit up to 30 (45 for AI), upgradability 5,
    budget headroom up to 40 (so price decides between machines of the same tier). No unbounded price
    ratio: a cheap weak machine must not beat a good one."""
    tier = cpu_mod.classify(offer.cpu)["tier"]
    parts = {"cpu": tier * 20.0}
    if offer.ram_gb:
        fit = min(offer.ram_gb / max(need.min_ram_gb, 1), 2.0) / 2.0   # 1.0 at twice the minimum
        parts["ram"] = fit * (45 if need.use == "ai" else 30)
    if offer.ram_soldered is False:
        parts["upgradable"] = 5.0
    ref = need.budget_max or reference_price  # no budget: compare with the most expensive candidate
    if ref:
        parts["budget_headroom"] = max(0.0, (ref - offer.price_eur) / ref) * 40
    return {"total": round(sum(parts.values()), 1), "parts": {k: round(v, 1) for k, v in parts.items()}}


def rank(offers: list[Offer], need: Need, limit: int = 15) -> tuple[list[dict], int]:
    """Ready-to-use offers first, then those that need extra RAM/SSD (barebones, upgradable below minimum)."""
    kept: list[tuple[Offer, list[dict]]] = []
    dropped = 0
    for offer in offers:
        findings = checks.check(offer, need)
        if checks.blockers(findings):
            dropped += 1
            continue
        kept.append((offer, findings))
    reference = max((o.price_eur for o, _ in kept), default=None)
    ranked = [{"offer": o.to_dict(), "score": score(o, need, reference), "findings": f,
               "cpu_tier": cpu_mod.classify(o.cpu)["tier"], "ready": meets_need(o, need)} for o, f in kept]
    ranked.sort(key=lambda r: (r["ready"], r["score"]["total"]), reverse=True)
    return ranked[:limit], dropped


def run(need: Need, source_ids: list[str] | None = None, limit: int = 15, use_cache: bool = True) -> dict:
    offers, report = collect(source_ids, use_cache)
    ranked, dropped = rank(offers, need, limit)
    return {"need": need.__dict__, "results": ranked, "dropped": dropped, "seen": len(offers), "sources": report}
