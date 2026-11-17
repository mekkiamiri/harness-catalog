"""Rough CPU tiers for buying decisions, not benchmarks.

Tier 1: office only. 2: light dev. 3: good dev machine. 4: strong dev (many containers, big builds).
5: workstation class (heavy builds, local AI on the CPU/iGPU, many VMs).
The point is to catch the classic traps (N100 sold as a "dev PC", U vs HS, old generations), not to rank
two CPUs of the same tier.
"""

from __future__ import annotations

import re

WEAK = re.compile(r"\bN(?:50|95|97|100|150|200|250)\b|Celeron|Pentium|Athlon|U300|\bCore\s+3\b", re.I)


def classify(name: str) -> dict:
    """Return {tier, family, notes}. tier 0 = unknown."""
    n = (name or "").strip()
    low = n.lower()
    notes: list[str] = []

    if not n:
        return {"tier": 0, "family": "unknown", "notes": ["CPU not found in the offer: check the product page."]}

    if WEAK.search(n):
        return {"tier": 1, "family": "entry", "notes": ["Entry-level CPU: fine for office work, too weak for dev with an IDE and Docker."]}

    m = re.search(r"apple\s+m(\d+)(?:\s+(pro|max|ultra))?", low)
    if m:
        gen, kind = int(m.group(1)), m.group(2) or ""
        tier = 5 if kind in ("max", "ultra") or (kind == "pro" and gen >= 3) else 4 if kind == "pro" or gen >= 3 else 3
        notes.append("Apple silicon: memory is unified and can never be upgraded, choose it for the machine's whole life.")
        return {"tier": tier, "family": "apple", "notes": notes}

    if "ryzen" in low:
        if re.search(r"ai\s+max", low):
            return {"tier": 5, "family": "amd", "notes": ["Ryzen AI Max: large unified memory, the best x86 option for local LLMs."]}
        if re.search(r"ai\s+9|hx\s*\d{3}", low):
            return {"tier": 5, "family": "amd", "notes": []}
        model = re.search(r"(\d)\s*(?:pro\s+)?(\d{4})([a-z]{0,3})", low)
        h_series = re.search(r"ryzen\s+(\d)\s+h\s?(\d{3})", low)
        if h_series:
            line = int(h_series.group(1))
            return {"tier": 4 if line >= 7 else 3, "family": "amd", "notes": []}
        if model:
            line, number, suffix = int(model.group(1)), int(model.group(2)), model.group(3)
            gen = number // 1000
            tier = 2
            if gen >= 6 and suffix.startswith("h"):
                tier = 5 if line == 9 or (line == 7 and number % 1000 >= 800 and gen >= 7) else 4 if line >= 7 else 3
            elif gen >= 5:
                tier = 3 if line >= 7 else 2
            if suffix == "u":
                notes.append("U = low-power chip: quiet, but slower under long loads (big builds, many containers).")
            if suffix.startswith("h"):
                notes.append("H/HS = performance chip.")
            if number in (7730, 7530, 7430, 7330):
                notes.append("7x30U is a 2021 Zen 3 design renamed: same as a 5x25U.")
            return {"tier": tier, "family": "amd", "notes": notes}
        return {"tier": 2, "family": "amd", "notes": ["Unrecognised Ryzen model: check its generation."]}

    m = re.search(r"core\s+ultra\s+x?(\d)\s+(\d)(\d{2})([a-z]{0,2})", low)
    if m:
        line, series, suffix = int(m.group(1)), int(m.group(2)), m.group(4)
        if suffix in ("h", "hx"):
            tier = 5 if line == 9 else 4
        else:
            tier = 4 if line >= 7 else 3
        if suffix in ("u", "v"):
            notes.append("U/V = efficiency chip: long battery life, less sustained power.")
        return {"tier": tier, "family": "intel", "notes": notes}

    m = re.search(r"i([3579])-(\d{4,5})([a-z]{0,2})", low)
    if m:
        line, number, suffix = int(m.group(1)), m.group(2), m.group(3)
        gen = int(number[:2]) if len(number) == 5 else int(number[0])
        if gen < 8:
            tier = 1
            notes.append("Older than 8th generation: avoid for dev, and Windows 11 does not support it.")
        elif line == 3:
            tier = 2
        elif gen <= 10:
            tier = 2 if suffix == "u" or (suffix == "t" and line == 5) else 3
        else:
            tier = 4 if (line >= 7 and suffix.startswith("h")) or line == 9 else 3
        if suffix == "t":
            notes.append("T = low-power desktop chip: quiet, about 20-30% slower than the same model without T.")
        if suffix == "u":
            notes.append("U = low-power laptop chip.")
        return {"tier": tier, "family": "intel", "notes": notes}

    if "xeon" in low:
        return {"tier": 3, "family": "intel", "notes": ["Workstation Xeon: many cores and ECC RAM, but noisy and power hungry; check the generation."]}

    return {"tier": 0, "family": "unknown", "notes": ["Unrecognised CPU: check it by hand."]}
