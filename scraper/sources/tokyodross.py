"""Tokyo Dross (tokyodross.blogspot.com) - curated monthly 'Tokyo Gigs <Month> <Year>' posts.

Each gig is one line:
    **OCT 1** ARTIST, ARTIST, &c. *Venue, Area* [¥3,000](ticket-url) (night)
Read through Blogger's JSON feed. No start times or genres are given.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, NavigableString, Tag

from ..models import Gig, Source
from ..textutil import nfkc, parse_price, to_english

log = logging.getLogger(__name__)

NAME = "Tokyo Dross"
FEED = "https://tokyodross.blogspot.com/feeds/posts/default?alt=json&max-results={n}"
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
TITLE_RE = re.compile(r"Tokyo Gigs\s+([A-Za-z]+)\s+(\d{4})", re.I)
FULL_MONTH = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}

# date part: "OCT 1", "OCT 1-2", "NOV 24-25", "OCT 31-NOV 1"
DATE_RE = re.compile(r"^([A-Z]{3})\s+(\d{1,2})(?:\s*[-–]\s*(?:([A-Z]{3})\s+)?(\d{1,2}))?$")


def _marked_lines(html: str) -> list[list[tuple[str, str, str | None]]]:
    """Split post HTML into lines of (kind, text, href) runs.

    kind is 'b' (bold), 'i' (italic), 'a' (link) or 't' (plain).
    """
    soup = BeautifulSoup(html, "lxml")
    lines: list[list] = [[]]

    def walk(node, style: str | None, href: str | None):
        for ch in node.children:
            if isinstance(ch, NavigableString):
                txt = str(ch)
                if txt.strip():
                    kind = "a" if href else (style or "t")
                    lines[-1].append((kind, txt, href))
                elif "\n" in txt and lines[-1]:
                    pass
                continue
            if not isinstance(ch, Tag):
                continue
            name = ch.name
            if name == "br":
                lines.append([])
                continue
            block = name in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr")
            if block and lines[-1]:
                lines.append([])
            st = style
            if name in ("b", "strong"):
                st = "b"
            elif name in ("i", "em"):
                st = "i"
            hr = ch.get("href") if name == "a" else href
            walk(ch, st, hr)
            if block and lines[-1]:
                lines.append([])

    walk(soup.body or soup, None, None)
    return [l for l in lines if l]


def _resolve_dates(md: re.Match, year: int, post_month: int) -> tuple[str, str | None]:
    m1 = MONTHS[md.group(1)]
    d1 = int(md.group(2))
    # a December post can list a JAN gig (and vice versa) - keep months in order
    y1 = year + 1 if (post_month == 12 and m1 == 1) else year - 1 if (post_month == 1 and m1 == 12) else year
    start = date(y1, m1, d1)
    end = None
    if md.group(4):
        m2 = MONTHS.get(md.group(3) or "", m1)
        y2 = y1 + 1 if m2 < m1 else y1
        end = date(y2, m2, int(md.group(4)))
    return start.isoformat(), end.isoformat() if end else None


def parse_post(html: str, title: str, post_url: str) -> list[Gig]:
    tm = TITLE_RE.search(title or "")
    if not tm:
        return []
    month = FULL_MONTH.get(tm.group(1).lower())
    year = int(tm.group(2))
    if not month:
        return []
    gigs = []
    for runs in _marked_lines(html):
        bold = [t for k, t, _ in runs if k == "b"]
        if not bold:
            continue
        md = DATE_RE.match(nfkc(bold[0]).upper())
        if not md or md.group(1) not in MONTHS:
            continue
        try:
            day, end = _resolve_dates(md, year, month)
        except ValueError:
            continue
        # everything after the bold date and before the italic venue = artists
        artists_txt, venue_txt, price_txt, href, tail = "", "", "", None, ""
        seen_date = seen_venue = False
        for kind, txt, h in runs:
            if kind == "b" and not seen_date:
                seen_date = True
                continue
            if kind == "i" and not seen_venue:
                venue_txt += txt
                seen_venue = True
                continue
            if not seen_venue:
                artists_txt += txt
            elif kind == "a" and not price_txt:
                price_txt, href = txt, h
            else:
                tail += txt
        artists_txt = nfkc(artists_txt)
        if not artists_txt or not venue_txt:
            continue
        venue_txt = nfkc(venue_txt)
        if "," in venue_txt:
            venue, area = [x.strip() for x in venue_txt.rsplit(",", 1)]
        else:
            venue, area = venue_txt, None
        tail = nfkc(tail)
        if not price_txt:                       # price without a link
            pm = re.match(r"(¥[\d,]+(?:\s*[-/]\s*¥?[\d,]+)?|Free|¥TBC)", tail, re.I)
            if pm:
                price_txt, tail = pm.group(1), tail[pm.end():].strip()
        adv, door, ptext, free = parse_price(price_txt + (" " + tail if tail.startswith("+") else ""))
        note = None
        nm = re.search(r"\(([^)]{2,40})\)", tail)
        if nm:
            note = nm.group(1)
        artists = [a.strip() for a in re.split(r",\s*", re.sub(r",?\s*&c\.?$|amp;c\.?$", "", artists_txt)) if a.strip()]
        v_en, v_ja = to_english(venue)
        a_en, a_ja = to_english(area)
        gigs.append(Gig(
            date=day, end_date=end,
            title=re.sub(r",?\s*&c\.?$", " & more", artists_txt),
            venue=v_en or venue, venue_ja=v_ja, area=a_en, area_ja=a_ja,
            price_adv=adv, price_door=door,
            price_text=ptext if ptext and ptext.strip().lower() not in ("free",) else None,
            free=free, artists=artists, ticket_url=href, note=note,
            sources=[Source(NAME, post_url)],
        ))
    return gigs


def scrape(http, cfg: dict) -> list[Gig]:
    data = http.json(FEED.format(n=cfg.get("max_posts", 30)))
    if not data:
        log.warning("Tokyo Dross: feed not available")
        return []
    today = (cfg.get("today") or date.today()).isoformat()
    gigs: list[Gig] = []
    for e in data.get("feed", {}).get("entry", []):
        title = e.get("title", {}).get("$t", "")
        if not TITLE_RE.search(title):
            continue
        html = e.get("content", {}).get("$t", "")
        link = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "https://tokyodross.blogspot.com/")
        gigs += [g for g in parse_post(html, title, link) if (g.end_date or g.date) >= today]
    log.info("Tokyo Dross: %d upcoming gigs", len(gigs))
    return gigs
