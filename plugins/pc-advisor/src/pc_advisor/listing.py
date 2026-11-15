"""Check a listing the user pasted (Leboncoin, Back Market, eBay...): pc-advisor never scrapes those sites."""

from __future__ import annotations

from . import checks, parse
from .models import Need, Offer, iso


def analyse(text: str, price_eur: float, need: Need, url: str = "") -> dict:
    offer = Offer(
        source="pasted", shop="pasted listing", title=text.strip().splitlines()[0][:120] if text.strip() else "",
        url=url, price_eur=price_eur, condition="used",
        form="laptop" if parse.looks_like_laptop(text) else need.form if need.form != "any" else "desktop",
        cpu=parse.cpu(text), ram_gb=parse.ram_gb(text), ram_soldered=parse.ram_soldered(text, parse.cpu(text)),
        storage_gb=parse.storage_gb(text), barebone=parse.is_barebone(text), fetched_at=iso(), verified=False,
    )
    relaxed = Need(**{**need.__dict__, "condition": "any", "form": "any" if need.form == "any" else need.form})
    return {"offer": offer.to_dict(), "findings": checks.check(offer, relaxed),
            "ask_the_seller": ASK_THE_SELLER, "test_on_site": TEST_ON_SITE}


ASK_THE_SELLER = [
    "Exact CPU model, RAM amount and number of RAM slots used/free?",
    "Original invoice? Is any warranty left?",
    "BIOS password or company lock (Computrace / Absolute)? Signed out of iCloud for a Mac?",
    "Battery health (laptops) and why are you selling?",
]
TEST_ON_SITE = [
    "Boot to the desktop in front of you; read CPU/RAM/SSD in the system info or BIOS.",
    "Better: boot your own Linux live USB and run `free -h` and `lsblk`.",
    "Test every USB port, the video output on a screen, Wi-Fi/Ethernet.",
    "Mac: Apple menu > About This Mac; Activation Lock must be off.",
    "Pay by hand delivery or a protected payment; never a direct bank transfer.",
]
