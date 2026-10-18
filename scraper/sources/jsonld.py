"""Generic schema.org Event reader.

Many venue and listing sites embed <script type="application/ld+json"> with
Event / MusicEvent objects (Songkick does on its listing pages). Any such URL
can be added to `jsonld_pages` in config.json without writing a new scraper.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from ..models import Gig, Source
from ..textutil import nfkc, parse_time, to_english

log = logging.getLogger(__name__)

EVENT_TYPES = {"Event", "MusicEvent", "Festival", "ComedyEvent", "DanceEvent", "TheaterEvent"}


def _walk(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _walk(x)
    elif isinstance(obj, dict):
        t = obj.get("@type")
        types = set(t if isinstance(t, list) else [t])
        if types & EVENT_TYPES:
            yield obj
        for k in ("@graph", "itemListElement", "item", "subEvent"):
            if k in obj:
                yield from _walk(obj[k])


def extract_events(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        raw = s.string or s.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw.strip())
        except ValueError:
            # some sites put several objects or trailing commas in one block
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw.strip()))
            except ValueError:
                continue
        out.extend(_walk(data))
    return out


def _names(x) -> list[str]:
    if not x:
        return []
    if isinstance(x, (str, dict)):
        x = [x]
    out = []
    for p in x:
        n = p.get("name") if isinstance(p, dict) else p
        if n:
            out.append(nfkc(str(n)))
    return out


def _split_dt(s: str | None) -> tuple[str | None, str | None]:
    if not s:
        return None, None
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", s)
    if not m:
        return None, None
    t = m.group(2)
    return m.group(1), (t if t and t != "00:00" else None)


def event_to_gig(ev: dict, source_name: str, page_url: str) -> Gig | None:
    day, start = _split_dt(ev.get("startDate"))
    if not day:
        return None
    end_day, _ = _split_dt(ev.get("endDate"))
    door = _split_dt(ev.get("doorTime"))[1] if ev.get("doorTime") and "T" in str(ev.get("doorTime")) else parse_time(ev.get("doorTime"))
    loc = ev.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    venue = nfkc(loc.get("name", "")) if isinstance(loc, dict) else nfkc(str(loc))
    addr = loc.get("address", {}) if isinstance(loc, dict) else {}
    area = None
    if isinstance(addr, dict):
        area = addr.get("addressLocality") or None
    if area and area.lower() in ("tokyo", "東京", "東京都", "tokyo-to"):
        area = None
    performers = _names(ev.get("performer"))
    name = nfkc(ev.get("name", "")) or ", ".join(performers)
    # Songkick names look like "Artist @ Venue" - trim the venue off
    name = re.sub(r"\s+@\s+.*$", "", name)
    price = None
    offers = ev.get("offers")
    if isinstance(offers, dict):
        offers = [offers]
    if isinstance(offers, list):
        ps = []
        for o in offers:
            try:
                ps.append(int(float(o.get("price") or o.get("lowPrice"))))
            except (TypeError, ValueError):
                pass
        ps = [p for p in ps if p > 0]
        price = min(ps) if ps else None
    url = ev.get("url") or page_url
    if isinstance(url, list):
        url = url[0]
    if not venue or venue.lower() in ("tokyo", "tokyo, japan", "unknown venue", "東京"):
        venue = "Venue tbc"
    v_en, v_ja = to_english(venue)
    a_en, a_ja = to_english(area)
    tags = []
    for k in ("genre", "keywords"):
        val = ev.get(k)
        if isinstance(val, str):
            tags += [t.strip() for t in val.split(",") if t.strip()]
        elif isinstance(val, list):
            tags += [str(t) for t in val]
    return Gig(
        date=day, end_date=end_day if end_day and end_day != day else None,
        title=name, venue=v_en, venue_ja=v_ja, area=a_en, area_ja=a_ja,
        open_time=door, start_time=start, price_adv=price,
        artists=performers or [name], tags=tags,
        sources=[Source(source_name, url)],
    )


def scrape(http, cfg: dict) -> list[Gig]:
    today = (cfg.get("today") or date.today()).isoformat()
    gigs = []
    for page in cfg.get("jsonld_pages", []):
        url, name = (page["url"], page.get("name", page["url"])) if isinstance(page, dict) else (page, page)
        html = http.text(url)
        if not html:
            continue
        for ev in extract_events(html):
            g = event_to_gig(ev, name, url)
            if g and (g.end_date or g.date) >= today:
                gigs.append(g)
    log.info("JSON-LD pages: %d gigs", len(gigs))
    return gigs
