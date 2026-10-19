"""Concert Square (en.concertsquare.jp) - classical, contemporary and traditional Japanese
music concerts, in English. Tokyo list pages, plus the hōgaku (traditional Japanese music)
genre page filtered to Tokyo.

Each card: date, start time, prefecture, hall, genre tags (Orchestra, Piano, Chamber Music,
Traditional Japanese Music...), 'Free admission'. No prices on the list.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..models import Gig, Source
from ..textutil import nfkc, parse_time, to_english

log = logging.getLogger(__name__)
NAME = "Concert Square"
BASE = "https://en.concertsquare.jp"
PAGES = [BASE + "/concert/prefecture/toukyo?page={p}", BASE + "/concert/prefecture/toukyo/hougaku?page={p}"]
SKIP_TAGS = {"professional", "amateur", "student", "welcoming children", "preschool children ok", "free admission"}


def _tags(cats: list[str]) -> list[str]:
    tags = [c for c in cats if c.lower() not in SKIP_TAGS and c.lower() != "unofficial"]
    if not any("traditional" in c.lower() for c in tags):
        tags.append("Classical")          # everything else on Concert Square is classical-side
    return tags


def parse(html: str) -> list[Gig]:
    """The date-ordered result list (10 per page). The featured carousels on every page are ignored."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.select(".search-result-list li.article"):
        title = a.select_one(".article-title")
        y = a.select_one(".concert-year")
        md = a.select_one(".concert-date .mon_date")
        if not title or not y or not md:
            continue
        m = re.match(r"(\d{1,2})/(\d{1,2})", md.get_text(strip=True))
        yr = re.search(r"20\d\d", y.get_text())
        if not m or not yr:
            continue
        prefs = [c.get_text(strip=True).lower() for c in a.select("a.map-link")]
        if prefs and "tokyo" not in prefs:
            continue
        hall = a.select_one(".meta-cat a.cat-link")
        t = a.select_one(".start-time")
        cats = [nfkc(c.get_text(strip=True)) for c in a.select(".meta-tag .tag")]
        desc = a.select_one(".concert-detail p")
        link = title.find("a")
        url = BASE + link["href"] if link and link.get("href", "").startswith("/") else BASE
        name = nfkc(title.get_text(" ", strip=True))
        venue = nfkc(hall.get_text(" ", strip=True)) if hall else "Venue tbc"
        v_en, v_ja = to_english(venue)
        out.append(Gig(date=f"{yr.group(0)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}", title=name,
                       venue=v_en, venue_ja=v_ja, start_time=parse_time(t.get_text()) if t else None,
                       free=any(c.lower() == "free admission" for c in cats),
                       artists=[name], tags=_tags(cats),
                       note=nfkc(desc.get_text(" ", strip=True))[:140] if desc else None,
                       sources=[Source(NAME, url)]))
    return out


def scrape(http, cfg: dict) -> list[Gig]:
    today = cfg.get("today") or date.today()
    horizon = (today + timedelta(days=int(cfg.get("days_ahead", 60)))).isoformat()
    max_pages = int(cfg.get("concertsquare_pages", 40))
    gigs = {}
    for tmpl, limit in ((PAGES[0], max_pages), (PAGES[1], 6)):
        for p in range(1, limit + 1):
            html = http.text(tmpl.format(p=p))
            found = parse(html) if html else []
            if not found:
                break
            for g in found:
                if today.isoformat() <= g.date <= horizon:
                    gigs[g.sources[0].url] = g
            if tmpl == PAGES[0] and found[-1].date > horizon:      # date order: the rest is later
                break
    log.info("Concert Square: %d Tokyo concerts", len(gigs))
    return list(gigs.values())
