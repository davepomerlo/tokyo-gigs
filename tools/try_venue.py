"""Run the generic venue parser over saved samples and print what it finds."""
import sys
from datetime import date
sys.path.insert(0, ".")
from scraper.venue_parse import parse_schedule
ctx = date(2026, 10, 1)
for f in sys.argv[1:]:
    html = open(f, encoding="utf-8", errors="replace").read()
    shows = parse_schedule(html, ctx)
    print(f"=== {f.split('/')[-1]}: {len(shows)} shows, {sum(1 for s in shows if s.price_adv or s.price_door)} priced, {sum(1 for s in shows if s.start_time or s.open_time)} timed")
    for s in shows[:5]:
        print(f"   {s.date} o={s.open_time} s={s.start_time} adv={s.price_adv} door={s.price_door} | {s.title[:55]} | {(s.lines[0] if s.lines else '')[:40]}")
