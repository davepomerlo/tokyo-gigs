"""Tokyo Gig Guide (tokyogigguide.com) - Joomla + JEM event manager.

The "All gigs" list  /en/gigs?start=0,50,100...  shows 50 upcoming gigs per
page, each card carrying title, date, time, venue, area, categories and
Advance/Door prices - everything we need, so no per-gig pages are fetched.

The site's robots.txt asks for a 120 s crawl delay; the Http client honours it,
so a full scan (~6-8 pages) takes about 15 minutes. That is fine for a daily job.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

from ..models import Gig, Source
from ..textutil import nfkc, parse_price, parse_time, to_english

log = logging.getLogger(__name__)

NAME = "Tokyo Gig Guide"
BASE = "https://www.tokyogigguide.com"
LIST_URL = BASE + "/en/gigs?start={start}"
PAGE_SIZE = 50
EVENT_RE = re.compile(r"/gigs/event/(\d+)")
VENUE_RE = re.compile(r"/gigs/venue/")
CAT_RE = re.compile(r"/categories/category/")
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                   "Sep", "Oct", "Nov", "Dec"], 1)}
DATE_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b")
# JEM can also print 2026-10-16 or 2026/10/16
ISO_RE = re.compile(r"\b(20\d\d)\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})\b")


def _year_for(month: int, today: date) -> int:
    # The list only shows upcoming gigs, so a month well before today's is next year.
    return today.year + 1 if month < today.month - 1 else today.year


def _card_for(a: Tag) -> Tag | None:
    """Smallest ancestor of a title link that holds exactly this one gig."""
    eid = EVENT_RE.search(a["href"]).group(1)
    node = a.parent
    while node is not None and node.name not in ("body", "html", "[document]"):
        ids = {EVENT_RE.search(x["href"]).group(1) for x in node.find_all("a", href=EVENT_RE)}
        if len(ids) > 1 or eid not in ids:
            return None
        if node.find("a", href=VENUE_RE):
            t = node.get_text(" ")
            if DATE_RE.search(t) or ISO_RE.search(t):
                return node
        node = node.parent
    return None


def _between(text: str, start: str, ends: list[str]) -> str | None:
    i = text.find(start)
    if i < 0:
        return None
    j = len(text)
    for e in ends:
        k = text.find(e, i + len(start))
        if k >= 0:
            j = min(j, k)
    return text[i + len(start):j].strip(" :|-") or None


def _own(el: Tag, card: Tag) -> bool:
    """True if el belongs to this card, not to a later card nested inside it.
    (The site leaves its <li> tags unclosed, so each card ends up inside the previous one.)"""
    return el.find_parent("div", class_="jem-event-details") is card


def parse_jem_cards(soup: BeautifulSoup, today: date) -> list[Gig]:
    """The real list layout: each gig is a div.jem-event-details holding an <h4> title link
    and div.jem-event-info boxes whose title attribute reads 'Label: value'."""
    gigs, seen = [], set()
    for card in soup.find_all("div", class_="jem-event-details"):
        h4 = next((h for h in card.find_all("h4") if _own(h, card)), None)
        a = h4.find("a", href=EVENT_RE) if h4 else None
        if not a:
            continue
        eid = EVENT_RE.search(a["href"]).group(1)
        if eid in seen:
            continue
        seen.add(eid)
        title = nfkc(a.get_text(" "))
        fields: dict[str, str] = {}
        cats: list[str] = []
        for box in card.find_all("div", class_="jem-event-info"):
            if not _own(box, card) or not box.get("title") or ":" not in box["title"]:
                continue
            label, value = box["title"].split(":", 1)
            label, value = label.strip(), nfkc(value)
            fields.setdefault(label, value)
            if label.startswith("Categor"):
                cats += [c.strip() for c in value.split(",") if c.strip()]

        # date: the schema.org startDate carries the year; fall back to the visible text
        meta = next((m for m in card.find_all("meta", itemprop="startDate") if _own(m, card)), None)
        day = time_ = None
        if meta and meta.get("content"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}))?", meta["content"])
            if m:
                day, time_ = m.group(1), m.group(2)
        if not day:
            m = DATE_RE.search(fields.get("Date", ""))
            if not m:
                continue
            mon = MON[m.group(1)]
            day = date(_year_for(mon, today), mon, int(m.group(2))).isoformat()
        if not time_ or time_ == "00:00":
            tm = re.search(r"(\d{1,2}[.:]\d{2})\s*$", fields.get("Date", ""))
            time_ = parse_time(tm.group(1)) if tm else None

        venue = fields.get("Live House") or "Venue tbc"
        area = fields.get("Area") or None
        adv_txt = re.sub(r"^Advance:\s*", "", fields.get("Adv. Price", "")) or None
        door_txt = re.sub(r"^Door:\s*", "", fields.get("Door Price", "")) or None
        adv, _, _, free_a = parse_price(adv_txt)
        door, _, _, free_d = parse_price(door_txt)
        price_bits = [f"{lab} {raw}" for lab, raw, val in (("Adv", adv_txt, adv), ("Door", door_txt, door))
                      if raw and (val is None or re.search(r"drink|incl|order|day only|tbc|tba|\+|\bfor\b", raw, re.I))]
        v_en, v_ja = to_english(venue)
        a_en, a_ja = to_english(area)
        url = a["href"] if a["href"].startswith("http") else BASE + a["href"]
        gigs.append(Gig(
            date=day, title=title,
            venue=v_en or venue, venue_ja=v_ja, area=a_en, area_ja=a_ja,
            open_time=time_,                    # the list shows the open (doors) time
            price_adv=adv, price_door=door,
            price_text=" / ".join(price_bits) or None,
            free=(free_a or free_d) and not (adv or door),
            artists=[x.strip() for x in re.split(r",|、", title) if x.strip()][:20],
            tags=cats, sources=[Source(NAME, url.split("?")[0])],
        ))
    return gigs


def parse_list_page(html: str, today: date) -> list[Gig]:
    soup = BeautifulSoup(html, "lxml")
    if soup.find("div", class_="jem-event-details"):
        return parse_jem_cards(soup, today)
    # older/other JEM layouts: work it out from the links around each title
    for bad in soup(["script", "style", "nav", "header", "footer", "form", "noscript"]):
        bad.decompose()
    gigs, seen = [], set()
    for a in soup.find_all("a", href=EVENT_RE):
        title = nfkc(a.get_text(" "))
        eid = EVENT_RE.search(a["href"]).group(1)
        if not title or eid in seen or "format=raw" in a["href"]:
            continue
        card = _card_for(a)
        if card is None:
            continue
        seen.add(eid)
        full = nfkc(card.get_text(" | "))
        # look for the date etc. after the title, so "Oct 31 Halloween Bash" titles can't confuse it;
        # in table layouts the date column comes first, so fall back to the text without the title
        after_title = full.split(title, 1)[1] if title in full else full
        text = after_title if (ISO_RE.search(after_title) or DATE_RE.search(after_title)) \
            else full.replace(title, " ", 1)

        # date
        m = ISO_RE.search(text)
        if m:
            day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            m = DATE_RE.search(text)
            mon = MON[m.group(1)]
            day = date(_year_for(mon, today), mon, int(m.group(2)))
        after_date = text[m.end():]
        tm = re.search(r"\b(\d{1,2}[.:]\d{2})\b", after_date)
        start_time = parse_time(tm.group(1)) if tm else None

        # venue + area: area is the text right after the venue link, before categories/prices
        va = card.find("a", href=VENUE_RE)
        venue = nfkc(va.get_text(" "))
        cats = [nfkc(c.get_text(" ")) for c in card.find_all("a", href=CAT_RE)]
        cats = [c for c in cats if c]
        area = None
        am = re.search(r"Area\s*:\s*\|?\s*([^|]+)", text)
        if am:
            area = am.group(1).strip()
        elif venue:
            after_venue = after_date[after_date.find(venue) + len(venue):] if venue in after_date else ""
            first = [s.strip(" -,@") for s in after_venue.split("|") if s.strip(" -,@")]
            if first and first[0] not in cats and not re.match(r"(Advance|Door|Live House|Categor)", first[0]):
                area = first[0]

        adv_txt = _between(text, "Advance:", ["Door:", "| Advance"])
        door_txt = _between(text, "Door:", ["Advance:"])
        adv, _, _, free_a = parse_price(adv_txt)
        door, _, _, free_d = parse_price(door_txt)    # a lone number comes back in slot 0
        price_bits = []
        for label, raw, val in (("Adv", adv_txt, adv), ("Door", door_txt, door)):
            if raw and (val is None or re.search(r"drink|incl|day only|tbc|tba|\+", raw, re.I)):
                price_bits.append(f"{label} {raw.strip(' |')}")
        v_en, v_ja = to_english(venue)
        a_en, a_ja = to_english(area)
        url = a["href"] if a["href"].startswith("http") else BASE + a["href"]
        artists = [x.strip() for x in re.split(r",|、", title) if x.strip()]
        gigs.append(Gig(
            date=day.isoformat(), title=title,
            venue=v_en or venue or "Unknown venue", venue_ja=v_ja, area=a_en, area_ja=a_ja,
            open_time=start_time,              # the list shows the open (doors) time
            price_adv=adv, price_door=door,
            price_text=" / ".join(price_bits) or None,
            free=(free_a or free_d) and not (adv or door),
            artists=artists[:20], tags=cats,
            sources=[Source(NAME, url.split("?")[0])],
        ))
    return gigs


def _save_debug(http, cfg: dict) -> None:
    """Nothing parsed from page 1: keep what the site sent so the parser can be fixed."""
    import json
    from pathlib import Path
    last = getattr(http, "last", None) or {}
    d = Path(cfg.get("cache_dir", "data/cache"))
    d.mkdir(parents=True, exist_ok=True)
    (d / "debug_tokyogigguide.json").write_text(json.dumps(
        {k: v for k, v in last.items() if k != "body"} | {"body_length": len(last.get("body") or "")}, indent=2))
    if last.get("body"):
        (d / "debug_tokyogigguide.html").write_text(last["body"])
    log.warning("TGG: page 1 gave no gigs (status %s, error %s) - saved debug copy",
                last.get("status"), last.get("error"))


def scrape(http, cfg: dict) -> list[Gig]:
    today = cfg.get("today") or date.today()
    max_pages = int(cfg.get("tgg_max_pages", 12))
    horizon = cfg.get("days_ahead", 60)
    gigs: list[Gig] = []
    for p in range(max_pages):
        url = LIST_URL.format(start=p * PAGE_SIZE)
        html = http.text(url)
        if not html and p > 0:                     # one more try after the site's crawl delay
            html = http.text(url)
        page = parse_list_page(html, today) if html else []
        log.info("TGG page %d: %d gigs", p + 1, len(page))
        last = getattr(http, "last", {}) or {}
        cfg.setdefault("_notes", {}).setdefault("tokyogigguide", []).append(
            f"page {p + 1}: {len(page)} gigs" + ("" if page else f" (status {last.get('status')}, {last.get('error')})"))
        if not page:
            if p == 0:
                _save_debug(http, cfg)
            break
        if p == 0:                       # parsing works again: drop any old debug copy
            from pathlib import Path
            for f in Path(cfg.get("cache_dir", "data/cache")).glob("debug_tokyogigguide.*"):
                f.unlink()
        gigs += page
        if len(page) < PAGE_SIZE // 2:
            break
        if (date.fromisoformat(page[-1].date) - today).days > horizon:
            break
    # de-duplicate in case pages shifted while we were reading them
    out = {g.sources[0].url: g for g in gigs if g.date >= today.isoformat()}
    log.info("TGG: %d upcoming gigs", len(out))
    return list(out.values())
