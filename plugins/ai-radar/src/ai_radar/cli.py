"""Command line: ai-radar <command>."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser

from . import pipeline
from .config import load_config
from .store import Store


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ai-radar", description="AI radar: tools, models, research, articles, events.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="collect + score + alerts + dashboard")
    r.add_argument("--if-older-than", type=float, metavar="HOURS", help="do nothing if the last run is more recent")
    r.add_argument("--deliver", action="store_true",
                   help="also write the digest for the next morning and sync it to your private repository")
    r.add_argument("--wait-network", type=_minutes, metavar="MINUTES",
                   help="for scheduled runs: if the network is not up yet, retry 3 times MINUTES apart, then give up")
    c = sub.add_parser("collect", help="collect and score only")
    c.add_argument("--sources", nargs="*", help="limit to some sources (github, openrouter, rss, meetup, cfp_dev...)")
    sub.add_parser("dashboard", help="rebuild the dashboard and exports")
    o = sub.add_parser("open", help="open the dashboard in the browser")
    o.add_argument("--no-rebuild", action="store_true")
    t = sub.add_parser("top", help="print the best new items")
    t.add_argument("--days", type=int, default=1)
    t.add_argument("--limit", type=int, default=15)
    t.add_argument("--category")
    e = sub.add_parser("cfps", help="print CFPs closing soon")
    e.add_argument("--days", type=int, default=60)
    sub.add_parser("status", help="last run and paths")
    sub.add_parser("sync", help="sync your state with your private repository (HARNESS_MEMORY_HOME)")
    sub.add_parser("mcp", help="start the MCP server (stdio)")
    a = p.parse_args(argv)

    if a.cmd == "mcp":
        from .server import main as serve
        serve()
        return 0

    cfg = load_config()
    store = Store(cfg.db_path)
    try:
        if a.cmd == "run":
            if a.wait_network is not None:
                from . import collectors
                if not collectors.wait_for_network(tries=4, pause=a.wait_network * 60):
                    print("✗ network still unreachable after 3 retries: run skipped.", file=sys.stderr)
                    return 1
            if a.if_older_than is not None:
                h = pipeline.hours_since_last_run(store)
                if pipeline.is_running(cfg):
                    print("A collection is already running: nothing to do.")
                    return 0
                if h is not None and h < a.if_older_than:
                    print(f"Last full run {h:.1f} h ago: collection skipped.")
                    if a.deliver:  # the digest and its sync still happen
                        print(json.dumps(pipeline.deliver_digest(cfg, store), ensure_ascii=False, indent=2))
                    return 0
            try:
                _print_report(pipeline.run(cfg, store, deliver=a.deliver))
            except pipeline.AlreadyRunning:
                print("A collection is already running: nothing to do.")
        elif a.cmd == "collect":
            try:
                _print_report(pipeline.collect(cfg, store, a.sources))
            except pipeline.AlreadyRunning:
                print("A collection is already running: nothing to do.")
        elif a.cmd == "dashboard":
            print(json.dumps(pipeline.publish(cfg, store), indent=2))
        elif a.cmd == "open":
            if not a.no_rebuild:
                pipeline.publish(cfg, store)
            webbrowser.open(cfg.dashboard_path.as_uri())
            print(cfg.dashboard_path)
        elif a.cmd == "top":
            for it in store.query(category=a.category, days=a.days, limit=a.limit):
                res = it["signals"].get("resonance") or []
                print(f"{it['score']:5.0f}  [{it['category']:8}] {it['title'][:70]}" + (f"  ← {', '.join(res)}" if res else ""))
                print(f"       {it['url']}")
        elif a.cmd == "cfps":
            for ev in store.upcoming_cfps(days=a.days):
                star = "★" if ev["watched"] else " "
                opens = f" (opens {ev['cfp_open'][:10]})" if ev.get("cfp_open") else ""
                print(f"{star} {ev['cfp_close']}  {ev['name'][:50]:50} {ev['cfp_url']}{opens}")
            print("Dates are leads from community agendas: verify on the official site.")
        elif a.cmd == "sync":
            from . import sync
            print(json.dumps(sync.sync(cfg, store), ensure_ascii=False, indent=2))
        elif a.cmd == "status":
            h = pipeline.hours_since_last_run(store)
            print(json.dumps({
                "last_run": store.last_run(), "hours_since_last_run": round(h, 1) if h is not None else None,
                "counts": store.counts(), "dashboard": str(cfg.dashboard_path), "cfp_json": str(cfg.cfp_path),
                "config": str(cfg.config_path), "profile": str(cfg.profile_path),
            }, ensure_ascii=False, indent=2))
    finally:
        store.close()
    return 0


def _minutes(value: str) -> float:
    m = float(value)
    if m < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return m


def _print_report(r: dict) -> None:
    print(f"{r['new']} new items ({r['seen']} seen), {r.get('events_new', 0)} new events.")
    for name, s in r["sources"].items():
        extra = f", {s['new']:4} new" if "new" in s else ""
        print(f"  ✓ {name:20} {s['received']:4} received{extra}")
    for name, e in r["errors"].items():
        print(f"  ✗ {name:20} {e}", file=sys.stderr)
    for name, w in r.get("warnings", {}).items():
        print(f"  ⚠ {name:20} partly failed: {w}", file=sys.stderr)
    if r.get("network_down"):
        print("  ✗ network lost during the run: marked partial, the next catch-up will collect again.",
              file=sys.stderr)
    for alert in r.get("alerts", []):
        print(f"  ! {alert}")
    for k, v in r.get("outputs", {}).items():
        print(f"  → {k}: {v}")


if __name__ == "__main__":
    sys.exit(main())
