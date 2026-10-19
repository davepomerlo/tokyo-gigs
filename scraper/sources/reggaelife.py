"""Reggae Life (reggaelife.jp) - reggae / dancehall events. Kantō page, Tokyo entries only.

Each block: date (with weekday), prefecture, event name, area, venue, address, TEL, times, price.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from ..models import Gig, Source
from ..textutil import to_english
from ..venue_parse import parse_schedule

log = logging.getLogger(__name__)
NAME = "Reggae Life"
URL = "https://reggaelife.jp/calendar/events.pl/area/3/"


def parse(html: str, today: date) -> list[Gig]:
    out = []
    for s in parse_schedule(html, today.replace(day=1), split_on_time=False):
        parts = [s.title] + s.lines
        if not parts or parts[0] not in ("東京", "東京都"):
            continue
        title = parts[1] if len(parts) > 1 else ""
        area_ja = parts[2] if len(parts) > 2 and len(parts[2]) <= 8 else None
        venue = parts[3] if area_ja and len(parts) > 3 else (parts[2] if len(parts) > 2 else "Venue tbc")
        if re.search(r"区|丁目|TEL|\d-\d", venue):          # no venue line, got the address
            venue = "Venue tbc"
        if len(title) < 2:
            continue
        v_en, v_ja = to_english(venue)
        a_en, a_ja = to_english(area_ja)
        out.append(Gig(date=s.date, title=title, venue=v_en, venue_ja=v_ja, area=a_en, area_ja=a_ja,
                       open_time=s.open_time, start_time=s.start_time, price_adv=s.price_adv,
                       price_door=s.price_door, free=s.free, artists=[title], tags=["Reggae"],
                       note=s.note, sources=[Source(NAME, URL)]))
    return out


def scrape(http, cfg: dict) -> list[Gig]:
    today = cfg.get("today") or date.today()
    html = http.text(URL)
    gigs = [g for g in parse(html, today) if g.date >= today.isoformat()] if html else []
    log.info("Reggae Life: %d Tokyo events", len(gigs))
    return gigs
