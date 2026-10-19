"""Daily entry point:  python -m scraper.run  [--only tokyogigguide,tokyodross] [--days 30]

Runs every enabled source, merges duplicates and writes
  docs/data/gigs.json  - what the web page reads
  docs/data/meta.json  - when it ran and how each source did
A source that fails keeps its last good results (up to 3 days old), so one
broken site never empties the listing.
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .http import Http
from .merge import fill_from_artists, gig_id, merge
from .models import Gig, Source

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
log = logging.getLogger("scraper")

SOURCES = {
    "tokyogigguide": "Tokyo Gig Guide",
    "tokyodross": "Tokyo Dross",
    "songkick": "Songkick",
    "jsonld": "Venue pages (JSON-LD)",
    "venues": "Venue websites",
    "clubberia": "Clubberia",
    "concertsquare": "Concert Square",
    "reggaelife": "Reggae Life",
}


def _load_gigs(path: Path) -> list[Gig]:
    out = []
    for d in json.loads(path.read_text()):
        d = dict(d)
        d["sources"] = [Source(**s) for s in d.get("sources", [])]
        out.append(Gig(**{k: v for k, v in d.items() if k in Gig.__dataclass_fields__}))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--only", help="comma list of sources to run")
    ap.add_argument("--days", type=int, help="override days_ahead")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = json.loads(Path(args.config).read_text())
    if args.days:
        cfg["days_ahead"] = args.days
    today = datetime.now(JST).date()
    cfg["today"] = today
    cfg.setdefault("cache_dir", str(ROOT / "data" / "cache"))
    cache_dir = Path(cfg["cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)

    enabled = [s for s in cfg.get("sources", SOURCES) if s in SOURCES]
    if args.only:
        enabled = [s for s in args.only.split(",") if s in SOURCES]

    http = Http(delay=float(cfg.get("delay_seconds", 1.5)))
    all_gigs: list[Gig] = []
    status = {}
    for key in enabled:
        t0 = time.time()
        last_good = cache_dir / f"last_{key}.json"
        try:
            mod = importlib.import_module(f".sources.{key}", __package__)
            gigs = mod.scrape(http, cfg)
            err = None
        except Exception as e:      # one broken site must not stop the run
            log.exception("%s failed", key)
            gigs, err = [], f"{type(e).__name__}: {e}"
        used_fallback = False
        fresh_enough = last_good.exists() and (time.time() - last_good.stat().st_mtime) < 3 * 86400
        prev = [g for g in _load_gigs(last_good) if (g.end_date or g.date) >= today.isoformat()] if fresh_enough else []
        if gigs and len(gigs) >= 0.6 * len(prev):
            last_good.write_text(json.dumps([g.to_dict() for g in gigs], ensure_ascii=False))
        elif gigs and prev:
            # a partial read (a page failed): keep the previous run's gigs beyond the dates we got
            reach = max(g.date for g in gigs)
            extra = [g for g in prev if g.date > reach]
            log.warning("%s returned %d gigs (last good run: %d) - keeping %d later gigs from that run",
                        key, len(gigs), len(prev), len(extra))
            gigs += extra
            used_fallback = bool(extra)
        elif prev:
            gigs = prev
            used_fallback = True
            log.warning("%s returned nothing - reusing %d gigs from last good run", key, len(gigs))
        status[key] = {"name": SOURCES[key], "gigs": len(gigs), "seconds": round(time.time() - t0, 1),
                       "error": err, "used_previous_results": used_fallback,
                       "notes": cfg.get("_notes", {}).get(key)}
        all_gigs += gigs

    horizon = (today + timedelta(days=int(cfg.get("days_ahead", 60)))).isoformat()
    all_gigs = [g for g in all_gigs if (g.end_date or g.date) >= today.isoformat() and g.date <= horizon]
    merged = merge(all_gigs)
    mem_path = cache_dir / "artist_genres.json"
    try:
        memory = json.loads(mem_path.read_text())
    except Exception:
        memory = {}
    memory = fill_from_artists(merged, memory)
    mem_path.write_text(json.dumps(memory, ensure_ascii=False, separators=(",", ":")))
    merged.sort(key=lambda g: (g.date, g.start_time or g.open_time or "99", g.venue.lower()))

    out_dir = ROOT / "docs" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for g in merged:
        d = g.to_dict()
        d["id"] = gig_id(g)
        rows.append(d)
    now = datetime.now(JST).isoformat(timespec="minutes")
    (out_dir / "gigs.json").write_text(json.dumps({"generated": now, "gigs": rows}, ensure_ascii=False, separators=(",", ":")))
    (out_dir / "meta.json").write_text(json.dumps({
        "generated": now, "total_listings": len(all_gigs), "after_merge": len(rows),
        "requests": http.requests_made, "sources": status}, ensure_ascii=False, indent=2))
    log.info("wrote %d gigs (%d listings before merge, %d requests)", len(rows), len(all_gigs), http.requests_made)
    return 0 if any(s["gigs"] for s in status.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
