"""The two shapes every part of pc-advisor exchanges: a Need and an Offer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

FORMS = ("any", "desktop", "mini", "laptop")
CONDITIONS = ("any", "new", "refurbished", "used")
SYSTEMS = ("any", "macos", "linux", "windows")
USES = ("dev", "ai", "office")


@dataclass
class Need:
    budget_max: float | None = None      # euros, all taxes included
    min_ram_gb: int = 16
    form: str = "any"                    # any | desktop | mini | laptop
    system: str = "any"                  # any | macos | linux | windows
    condition: str = "any"               # any | new | refurbished | used
    use: str = "dev"                     # dev | ai | office
    country: str = "FR"
    keyboard: str = "AZERTY"             # what the user types on (laptops only)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Need":
        data = data or {}
        need = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__ and v is not None})
        for name, allowed in (("form", FORMS), ("condition", CONDITIONS), ("system", SYSTEMS), ("use", USES)):
            if getattr(need, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}")
        return need


@dataclass
class Offer:
    source: str                          # source id in sources.py
    shop: str
    title: str
    url: str
    price_eur: float
    condition: str = "new"               # new | refurbished | used
    form: str = "mini"                   # desktop | mini | laptop
    variant: str = ""
    available: bool = True
    cpu: str = ""
    ram_gb: int | None = None
    ram_soldered: bool | None = None     # None = unknown
    storage_gb: int | None = None
    barebone: bool = False
    starting_price: bool = False         # "from" price of a configurable product
    fetched_at: str = ""
    verified: bool = True                # read on the shop page now, not from memory
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def iso(epoch: float | None = None) -> str:
    moment = datetime.fromtimestamp(epoch, timezone.utc) if epoch else datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat()
