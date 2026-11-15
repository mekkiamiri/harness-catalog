"""Read specs out of free text (product titles, variants, descriptions, pasted listings). English and French."""

from __future__ import annotations

import html
import re

_CPU = re.compile(
    r"(Apple\s+M\d+(?:\s+(?:Pro|Max|Ultra))?"
    r"|(?:AMD\s+)?Ryzen(?:™)?\s+AI\s+Max\+?\s*(?:PRO\s*)?\d{3}"
    r"|(?:AMD\s+)?Ryzen(?:™)?\s+(?:AI\s+)?\d(?:\s+PRO)?\s+(?:HX\s*)?[A-Z]?\s?\d{3,4}[A-Z]{0,3}\d?"
    r"|(?:AMD\s+)?Ryzen(?:™)?\s+\d\s+H\s?\d{3}"
    r"|(?:Intel\s+)?Core(?:™)?\s+Ultra\s+(?:X)?\d\s+\d{3}[A-Z]{0,2}"
    r"|(?:Intel\s+)?Core(?:™)?\s+\d\s+\d{3}[A-Z]?"
    r"|(?:Intel\s+)?Core(?:™)?\s+i[3579]-\d{4,5}[A-Z]{0,2}"
    r"|\bi[3579]-\d{4,5}[A-Z]{0,2}"
    r"|(?:Intel\s+)?(?:Processor\s+)?N(?:50|95|97|100|150|200|250|305|355)\b"
    r"|Intel\s+U300|Celeron\s+\w+|Pentium\s+\w+"
    r"|Xeon\s+[\w-]+(?:\s+v\d)?)",
    re.I,
)
_RAM = re.compile(r"(?<![\d.])(\d{1,3})\s?(?:GB|Go|G)\b(?:\s*\(\d+\s?G?B?\s?[x*×]\s?\d+\))?\s*(?:of\s+)?"
                  r"(?:LP)?(?:DDR\d\w*|RAM|de\s+RAM|mémoire|memory|unified|Unified|\+)", re.I)
_RAM_FR_UNIFIED = re.compile(r"(?<!\d)(\d{1,3})\s?Go de mémoire unifiée", re.I)
_STORAGE = re.compile(r"(?<![\d.])(\d(?:[.,]\d)?|\d{3,4})\s?(TB|To|GB|Go)\s*(?:de\s+stockage\s+)?(?:PCIe\s*\d\.\d\s*)?(?:NVMe\s*)?"
                      r"(?:M\.2\s*)?(?:SSD|de stockage|storage|NVMe)", re.I)
_SOLDERED = re.compile(r"LPDDR|soldered|soudée|soude|non[- ]évolutive|non[- ]upgradable|not upgradable|on[- ]package|onboard memory",
                       re.I)
_UPGRADABLE = re.compile(r"SO-?DIMM|dual[- ]slot|\bslots?\b.*(?:up to|jusqu)|extensible|expandable|upgradable to", re.I)
_BAREBONE = re.compile(r"barebone|sans\s+(?:RAM|SSD)|ohne\s+(?:RAM|SSD)|no\s+RAM|0GB\s*\+\s*0GB", re.I)
_LAPTOP = re.compile(r"\blaptop\b|notebook|\bbook\b|portable|ordinateur portable|macbook|ultrabook|2[- ]in[- ]1", re.I)
_TAGS = re.compile(r"<[^>]+>")
_KNOWN_RAM = {4, 8, 12, 16, 18, 24, 32, 36, 48, 64, 96, 128, 192, 256}


def text_of(html_text: str | None) -> str:
    """HTML to plain text, entities decoded, whitespace squeezed."""
    if not html_text:
        return ""
    text = _TAGS.sub(" ", html.unescape(html_text))
    return re.sub(r"\s+", " ", text).strip()


def normalize(text: str | None) -> str:
    """Drop trademark signs and non-breaking spaces that break the patterns (Celeron® J3160, Apple M4)."""
    return re.sub(r"[®™]|\(R\)|\(TM\)", "", (text or "").replace("\xa0", " "))


def cpu(text: str) -> str:
    m = _CPU.search(normalize(text))
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def ram_gb(text: str) -> int | None:
    """Total RAM in GB, or None. Ignores storage sizes and VRAM."""
    text = normalize(text)
    for rx in (_RAM_FR_UNIFIED, _RAM):
        for m in rx.finditer(text):
            value = int(m.group(1))
            tail = text[m.end():m.end() + 12].lower()
            if value in _KNOWN_RAM and "vram" not in tail and "gddr" not in text[m.start():m.end() + 8].lower():
                return value
    return None


def storage_gb(text: str) -> int | None:
    m = _STORAGE.search(text or "")
    if not m:
        return None
    number = float(m.group(1).replace(",", "."))
    return int(number * 1000) if m.group(2).upper() in ("TB", "TO") else int(number)


_ALWAYS_SOLDERED_CPU = re.compile(r"Apple\s+M\d|Ryzen\s+AI\s+Max|Core\s+Ultra\s+X?\d\s+2\d\dV\b", re.I)


def ram_soldered(text: str, cpu_name: str = "") -> bool | None:
    """True if the text says the RAM is soldered (or the CPU only exists with on-package memory: Apple silicon,
    Ryzen AI Max, Intel Core Ultra 200V), False if it says it is upgradable, None if unknown."""
    text = normalize(text)
    if _ALWAYS_SOLDERED_CPU.search(normalize(cpu_name)) or _SOLDERED.search(text):
        return True
    if _UPGRADABLE.search(text) or re.search(r"(?<!LP)(?<!LP-)\bDDR[345]\b", text, re.I):
        return False  # plain DDR (not LPDDR) comes as modules: upgradable in practice
    return None


def is_barebone(text: str) -> bool:
    return bool(_BAREBONE.search(text or ""))


def looks_like_laptop(text: str) -> bool:
    return bool(_LAPTOP.search(text or ""))
