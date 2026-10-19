"""Concert Square (en.concertsquare.jp) - classical, contemporary and traditional Japanese
music concerts, in English. Tokyo list pages, plus the hōgaku (traditional Japanese music)
genre page filtered to Tokyo.

Each card: date, start time, prefecture, hall, genre tags (Orchestra, Piano, Chamber Music,
Traditional Japanese Music...), 'Free admission'. No prices on the list.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from ..models import Gig, Source
from ..textutil import nfkc, parse_time, to_english

log = logging.getLogger(__name__)
NAME = "Concert Square"
BASE = "https://en.concertsquare.jp"
PAGES = [BASE + "/concert/prefecture/toukyo?page={p}", BASE + "/concert/genre/hougaku?page={p}"]
SKIP_TAGS = {"professional", "amateur", "student", "welcoming children", "preschool children ok", "free admission"}


def _tags(cats: list[str]) -> list[str]:
    tags = [c for c in cats if c.lower() not in SKIP_TAGS and c.lower() != "unofficial"]
    if not any("traditional" in c.lower() for c in tags):
        tags.append("Classical")          # everything else on Concert Square is classical-side
    return tags


def parse(html: str) -> list[Gig]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.select(".article"):
        title = a.select_one(".article-title")
        d = a.select_one(".meta-open-date .date") or a.select_one(".date")
        if not title or not d:
            continue
        m = re.match(r"(20\d\d)/(\d{1,2})/(\d{1,2})", d.get_text(strip=True))
        if not m:
            continue
        prov = a.select_one(".prov")
        if prov and prov.get_text(strip=True).lower() not in ("tokyo",):
            continue
        hall = a.select_one(".building")
        t = a.select_one(".meta-open-date .time")
        cats = [nfkc(c.get_text(strip=True)) for c in a.select(".cat")]
        link = title.find("a")
        url = BASE + link["href"] if link and link.get("href", "").startswith("/") else BASE
        name = nfkc(title.get_text(" ", strip=True))
        venue = nfkc(hall.get_text(" ", strip=True)) if hall else "Venue tbc"
        v_en, v_ja = to_english(venue)
        out.append(Gig(date=f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", title=name,
                       venue=v_en, venue_ja=v_ja, start_time=parse_time(t.get_text()) if t else None,
                       free=any(c.lower() == "free admission" for c in cats),
                       artists=[name], tags=_tags(cats),
                       sources=[Source(NAME, url)]))
    return out


def scrape(http, cfg: dict) -> list[Gig]:
    today = (cfg.get("today") or date.today()).isoformat()
    pages = int(cfg.get("concertsquare_pages", 8))
    gigs = {}
    for tmpl in PAGES:
        for p in range(1, pages + 1):
            html = http.text(tmpl.format(p=p))
            found = parse(html) if html else []
            if not html or not BeautifulSoup(html, "lxml").select(".article"):
                break
            for g in found:
                if g.date >= today:
                    gigs[g.sources[0].url] = g
            if tmpl.endswith("hougaku?page={p}") and p >= 3:
                break
    log.info("Concert Square: %d Tokyo concerts", len(gigs))
    return list(gigs.values())
