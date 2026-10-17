"""Songkick Tokyo metro area - strong on touring/international acts.

Listing pages embed schema.org MusicEvent JSON-LD. Genres come from walking
the per-genre filter pages and tagging the events found there.
No prices are published.
"""
from __future__ import annotations

import logging
from datetime import date

from ..models import Gig
from .jsonld import event_to_gig, extract_events

log = logging.getLogger(__name__)

NAME = "Songkick"
METRO = "https://www.songkick.com/metro-areas/30717-japan-tokyo"
GENRES = {
    "rock": "Rock", "pop": "Pop", "hip-hop": "Hip-Hop", "r-and-b": "R&B",
    "indie-alternative": "Indie & Alt", "electronic": "Electronic", "country": "Country",
    "classical": "Classical", "metal": "Metal", "latin": "Latin", "folk": "Folk & Blues",
    "jazz": "Jazz", "funk-soul": "Funk & Soul", "reggae": "Reggae",
}


def _pages(http, base: str, max_pages: int):
    seen = set()
    for page in range(1, max_pages + 1):
        html = http.text(base if page == 1 else f"{base}?page={page}")
        if not html:
            return
        evs = extract_events(html)
        new = [e for e in evs if (e.get("url") or e.get("name")) not in seen]
        if not new:
            return
        for e in new:
            seen.add(e.get("url") or e.get("name"))
            yield e


def scrape(http, cfg: dict) -> list[Gig]:
    max_pages = int(cfg.get("songkick_pages", 8))
    today = (cfg.get("today") or date.today()).isoformat()
    by_url = {}
    for ev in _pages(http, METRO, max_pages):
        g = event_to_gig(ev, NAME, METRO)
        if g and (g.end_date or g.date) >= today:
            by_url[g.sources[0].url] = g
    if cfg.get("songkick_genres", True):
        for slug, label in GENRES.items():
            for ev in _pages(http, f"{METRO}/genre/{slug}", max(2, max_pages // 3)):
                g = by_url.get(ev.get("url"))
                if g and label not in g.tags:
                    g.tags.append(label)
    log.info("Songkick: %d upcoming gigs", len(by_url))
    return list(by_url.values())
