"""Command line: pc-advisor <command>."""

from __future__ import annotations

import argparse
import json
import sys

from . import cpu as cpu_mod
from . import listing, search
from .models import CONDITIONS, FORMS, SYSTEMS, USES, Need
from .sources import SOURCES


def _need_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--budget", type=float, help="maximum price in euros")
    p.add_argument("--min-ram", type=int, default=16, help="minimum RAM in GB (default 16)")
    p.add_argument("--form", choices=FORMS, default="any")
    p.add_argument("--system", choices=SYSTEMS, default="any")
    p.add_argument("--condition", choices=CONDITIONS, default="any")
    p.add_argument("--use", choices=USES, default="dev")


def _need(a) -> Need:
    return Need.from_dict({"budget_max": a.budget, "min_ram_gb": a.min_ram, "form": a.form, "system": a.system,
                           "condition": a.condition, "use": a.use})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pc-advisor", description="Real computer offers for a need, with verified prices.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources", help="list the sources and their status")
    s = sub.add_parser("search", help="fetch, check and rank offers")
    _need_args(s)
    s.add_argument("--sources", nargs="*", help="limit to some source ids")
    s.add_argument("--limit", type=int, default=15)
    s.add_argument("--refresh", action="store_true", help="bypass the 6-hour cache")
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help="analyse a pasted listing (text on stdin)")
    _need_args(c)
    c.add_argument("--price", type=float, required=True)
    t = sub.add_parser("cpu", help="tier of a CPU")
    t.add_argument("name", nargs="+")
    sub.add_parser("mcp", help="start the MCP server (stdio)")
    a = p.parse_args(argv)

    if a.cmd == "mcp":
        from .server import main as serve
        serve()
        return 0
    if a.cmd == "sources":
        for src in SOURCES:
            print(f"{src.status:8} {src.id:13} {src.country:6} {src.condition:12} {src.name}")
        return 0
    if a.cmd == "cpu":
        print(json.dumps(cpu_mod.classify(" ".join(a.name)), ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "check":
        print(json.dumps(listing.analyse(sys.stdin.read(), a.price, _need(a)), ensure_ascii=False, indent=2))
        return 0

    result = search.run(_need(a), a.sources, a.limit, use_cache=not a.refresh)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    for rep in result["sources"]:
        print(f"[{rep['status']}] {rep['source']}: {rep['offers']} offers" + (f" — {rep['note']}" if rep.get("note") else ""))
    print(f"\n{result['seen']} offers seen, {result['dropped']} dropped by the checks, best {len(result['results'])}:\n")
    for i, r in enumerate(result["results"], 1):
        o = r["offer"]
        warn = [f["code"] for f in r["findings"] if f["level"] == "warning"]
        ram = f"{o['ram_gb']} GB" if o["ram_gb"] else "barebone" if o["barebone"] else "? GB"
        tag = "" if r["ready"] else "  [needs RAM/SSD]"
        print(f"{i:2}. {o['price_eur']:7.0f} €  {o['title'][:52]:52}  {o['cpu'][:24]:24} {ram:9} "
              f"tier {r['cpu_tier']}  {o['shop']}{tag}")
        print(f"    {o['variant'][:70]}  {o['url']}")
        if warn:
            print(f"    ⚠ {', '.join(warn)}")
    return 0
