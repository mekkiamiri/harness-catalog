"""Buying rules: every trap found while buying for real, turned into a check.

Each finding has a level:
  blocker — the offer cannot meet the need (it is dropped from the ranking);
  warning — it can, but the user must know before paying;
  info    — useful context.
Messages exist in English and French so the skill can answer in the user's language.
"""

from __future__ import annotations

from . import cpu as cpu_mod
from .models import Need, Offer
from .sources import by_id


def _f(level: str, code: str, en: str, fr: str) -> dict:
    return {"level": level, "code": code, "en": en, "fr": fr}


def check(offer: Offer, need: Need) -> list[dict]:
    out: list[dict] = []
    tier = cpu_mod.classify(offer.cpu)

    if not offer.available:
        out.append(_f("blocker", "unavailable", "Out of stock.", "En rupture de stock."))

    if need.budget_max is not None and offer.price_eur > need.budget_max:
        out.append(_f("blocker", "over_budget", f"{offer.price_eur:.0f} € is above the {need.budget_max:.0f} € budget.",
                      f"{offer.price_eur:.0f} € dépasse le budget de {need.budget_max:.0f} €."))

    if need.form != "any" and offer.form != need.form:
        out.append(_f("blocker", "wrong_form", f"Form factor is {offer.form}, you asked for {need.form}.",
                      f"Format {offer.form}, tu as demandé {need.form}."))

    wants_mac = need.system == "macos"
    is_mac = tier["family"] == "apple"
    if wants_mac and not is_mac:
        out.append(_f("blocker", "not_macos", "Not a Mac.", "Ce n'est pas un Mac."))
    if need.system in ("linux", "windows") and is_mac:
        out.append(_f("warning", "mac_for_linux", "A Mac runs macOS; Linux support on Apple silicon is partial.",
                      "Un Mac tourne sous macOS ; Linux sur puce Apple reste partiel."))

    if need.condition != "any" and offer.condition != need.condition:
        out.append(_f("blocker", "wrong_condition", f"Condition is {offer.condition}.", f"État : {offer.condition}."))

    # CPU
    if tier["tier"] == 1 and need.use in ("dev", "ai"):
        out.append(_f("blocker", "cpu_too_weak", f"{offer.cpu}: too weak for {need.use}.",
                      f"{offer.cpu} : trop faible pour du {need.use}."))
    elif tier["tier"] == 0:
        out.append(_f("warning", "cpu_unknown", "CPU not identified: read the product page.",
                      "Processeur non identifié : lire la fiche produit."))
    elif tier["tier"] == 2 and need.use == "ai":
        out.append(_f("warning", "cpu_light_for_ai", "Light CPU for local AI: small models only, slowly.",
                      "Processeur léger pour l'IA locale : petits modèles seulement, lentement."))

    # RAM
    if offer.barebone:
        out.append(_f("info", "barebone", "Barebone: no RAM, no SSD, no OS. Add their cost.",
                      "Barebone : sans RAM, sans SSD, sans système. Ajoute leur prix."))
    elif offer.ram_gb is None:
        out.append(_f("warning", "ram_unknown", "RAM amount not found: check the configuration.",
                      "Quantité de RAM introuvable : vérifier la configuration."))
    elif offer.ram_gb < need.min_ram_gb:
        if offer.ram_soldered or is_mac:
            out.append(_f("blocker", "ram_soldered_below_min",
                          f"{offer.ram_gb} GB of soldered RAM, below your {need.min_ram_gb} GB minimum: it can never be upgraded.",
                          f"{offer.ram_gb} Go de RAM soudée, sous ton minimum de {need.min_ram_gb} Go : impossible de l'augmenter."))
        elif offer.ram_soldered is False:
            out.append(_f("warning", "ram_below_min_upgradable",
                          f"{offer.ram_gb} GB, below your {need.min_ram_gb} GB minimum, but upgradable (SO-DIMM): budget the extra RAM.",
                          f"{offer.ram_gb} Go, sous ton minimum de {need.min_ram_gb} Go, mais extensible (SO-DIMM) : prévoir le prix de la RAM."))
        else:
            out.append(_f("warning", "ram_below_min_unknown",
                          f"{offer.ram_gb} GB, below your minimum, and we could not tell if it is upgradable.",
                          f"{offer.ram_gb} Go, sous ton minimum, et impossible de savoir si c'est extensible."))
    if offer.ram_soldered and offer.ram_gb and offer.ram_gb >= need.min_ram_gb:
        out.append(_f("info", "ram_soldered", "Soldered RAM (LPDDR): fine today, but never upgradable.",
                      "RAM soudée (LPDDR) : suffisante aujourd'hui, mais jamais extensible."))

    # Shop-level facts
    source = by_id(offer.source)
    if source:
        if source.caution:
            out.append(_f("warning", "shop_caution", source.caution, source.caution))
        if source.country.startswith("DE") and offer.form == "laptop" and need.keyboard.upper() != "QWERTZ":
            out.append(_f("warning", "keyboard_layout", "German shop: the keyboard is probably QWERTZ.",
                          "Boutique allemande : le clavier est probablement en QWERTZ."))
        if "15%" in source.returns or "on you" in source.returns:
            out.append(_f("warning", "return_policy", f"Returns: {source.returns}.", f"Retours : {source.returns}."))

    if offer.starting_price:
        out.append(_f("info", "starting_price", "Starting price of a configurable model: check the exact configuration in the cart.",
                      "Prix de départ d'un modèle configurable : vérifier la configuration exacte au panier."))
    for note in tier["notes"]:
        out.append(_f("info", "cpu_note", note, note))
    return out


def blockers(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f["level"] == "blocker"]
