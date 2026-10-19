"""Clubberia (clubberia.com) - club nights in Tokyo with genre tags (hip-hop, R&B, house, techno...).

Week pages filtered to Tokyo: /ja/events/?schedule_start=YYYY-MM-DD&region_cd=tokyo
Each card: date (MM.DD + weekday), title, '@ VENUE', genre labels. No times or prices
on the list, so those stay blank and the gig links to Clubberia's event page.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..models import Gig, Source
from ..textutil import nfkc, to_english

log = logging.getLogger(__name__)
NAME = "Clubberia"
BASE = "https://clubberia.com"
WEEK = BASE + "/ja/events/?schedule_start={d}&region_cd=tokyo"


def parse_week(html: str, today: date) -> list[Gig]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for c in soup.select("article.c-post"):
        day = c.select_one(".c-post__day")
        title = c.select_one(".c-post__title")
        if not day or not title:
            continue
        m = re.match(r"(\d{1,2})\.(\d{1,2})", day.get_text(strip=True))
        if not m:
            continue
        mo, d = int(m.group(1)), int(m.group(2))
        y = today.year + (1 if mo < today.month - 2 else 0)
        try:
            dt = date(y, mo, d)
        except ValueError:
            continue
        venue = nfkc((c.select_one(".c-post__venue").get_text(" ", strip=True) if c.select_one(".c-post__venue") else "")).lstrip("@ ").strip()
        v_en, v_ja = to_english(venue or "Venue tbc")
        genres = [nfkc(g.get_text(strip=True)) for g in c.select(".c-post__genre")]
        link = c.select_one("a[href*='/events/']")
        url = BASE + link["href"] if link and link["href"].startswith("/") else (link["href"] if link else BASE)
        t = nfkc(title.get_text(" ", strip=True))
        out.append(Gig(date=dt.isoformat(), title=t, venue=v_en, venue_ja=v_ja,
                       artists=[t], tags=genres, sources=[Source(NAME, url)]))
    return out


def scrape(http, cfg: dict) -> list[Gig]:
    today = cfg.get("today") or date.today()
    weeks = int(cfg.get("clubberia_weeks", 6))
    start = today - timedelta(days=(today.weekday() + 1) % 7)       # the site's weeks start on Sunday
    gigs = {}
    for w in range(weeks):
        html = http.text(WEEK.format(d=(start + timedelta(days=7 * w)).isoformat()))
        if not html:
            continue
        for g in parse_week(html, today):
            if g.date >= today.isoformat():
                gigs[g.sources[0].url] = g
    log.info("Clubberia: %d club nights", len(gigs))
    return list(gigs.values())
