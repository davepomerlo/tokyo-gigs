"""Venues' own schedule pages: jazz clubs, improv spaces, livehouses, clubs and concert halls.

Each entry in VENUES says where the schedule lives (this month's and next month's page)
and how to read it. Most use the shared reader in scraper/venue_parse.py; a few sites
with clear structured markup (Squarespace, card lists) have small dedicated readers.
To add a venue: add an entry, save a sample page to tests/fixtures/venues/, add a test.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Gig, Source
from ..textutil import nfkc, parse_price, parse_time, to_english
from ..venue_parse import Show, lineup, parse_schedule, _prices, _times
from .jsonld import event_to_gig, extract_events

log = logging.getLogger(__name__)


@dataclass
class Venue:
    key: str
    name: str                      # English display name
    area: str
    urls: list[str]                # may contain {y} {m} {mm} {ym}; one page per month
    name_ja: Optional[str] = None
    tags: list[str] = field(default_factory=list)   # genre tags for every show here (empty = mixed)
    reader: str = "schedule"       # schedule | jsonld | velvetsun | clubasia | triphony
    opts: dict = field(default_factory=dict)        # passed to parse_schedule
    note: Optional[str] = None     # e.g. 'afternoon' for daytime series
    lineup_title: bool = False     # title is a format word ('trio'); build it from the line-up
    months: int = 2                # how many months of templated URLs to read
    skip_title: Optional[str] = None


IMPROV = ["Jazz", "Free Improvisation"]
VENUES: list[Venue] = [
    # --- jazz clubs ---
    Venue("pitinn", "Shinjuku Pit Inn", "Shinjuku", ["https://pit-inn.com/schedule/", "https://pit-inn.com/next-schedule/"],
          name_ja="新宿ピットイン", tags=["Jazz"], months=1),
    Venue("pitinn-day", "Shinjuku Pit Inn", "Shinjuku", ["https://pit-inn.com/schedule-day/", "https://pit-inn.com/next-schedule-day/"],
          name_ja="新宿ピットイン", tags=["Jazz"], note="afternoon", months=1),
    Venue("bluenote", "Blue Note Tokyo", "Minami-Aoyama", ["https://reserve.bluenote.co.jp/reserve/schedule/"],
          name_ja="ブルーノート東京", tags=["Jazz"], months=1),
    Venue("cottonclub", "Cotton Club", "Marunouchi", ["https://reserve.cottonclubjapan.co.jp/reserve/schedule/"],
          name_ja="コットンクラブ", tags=["Jazz"], months=1),
    Venue("jzbrat", "JZ Brat", "Shibuya", ["https://www.jzbrat.com/liveinfo/{y}/{mm}/"], tags=["Jazz"]),
    Venue("sometime", "Sometime", "Kichijoji", ["https://www.sometime.co.jp/sometime/live.html"],
          name_ja="吉祥寺サムタイム", tags=["Jazz"], months=1),
    Venue("yoyoginaru", "Naru Yoyogi", "Yoyogi", ["https://yoyogi-naru.com/live{mm}{y}/"], name_ja="代々木ナル", tags=["Jazz"]),
    Venue("ochanaru", "Naru Ochanomizu", "Ochanomizu", ["http://ocha-naru.com/schedule"], name_ja="お茶の水ナル",
          tags=["Jazz"], months=1),
    Venue("koko", "KO-KO", "Shibuya", ["https://jazz-koko.com/schedule1/", "https://jazz-koko.com/schedule2/"],
          tags=["Jazz"], months=1),
    Venue("aketa", "Aketa no Mise", "Nishi-Ogikubo", ["http://www.aketa.org/schedule.html"], name_ja="アケタの店",
          tags=["Jazz"], months=1, opts={"title_strip": r"^[「」]*(?:昼|夜中?|深夜)[」」]*"}),
    Venue("jirokichi", "JIROKICHI", "Koenji", ["https://jirokichi.net/{y}/{mm}"], name_ja="高円寺JIROKICHI"),
    # --- improvised / experimental ---
    Venue("knuttel", "Knuttel House", "Iriya", ["https://knuttelhouse.com/schedule/"], name_ja="なってるハウス",
          tags=IMPROV, months=1),
    Venue("polaris", "Polaris", "Minami-Aoyama", ["https://polaristokyo.com/schedule/"], tags=IMPROV, reader="jsonld", months=1),
    Venue("permian", "Permian", "Meguro", ["https://permian.tokyo/schedule/"], tags=["Free Improvisation", "Experimental"],
          lineup_title=True, months=1),
    Venue("nanahari", "Nanahari", "Hatchobori", ["https://ftftftf.com/"], name_ja="七針", tags=["Experimental"],
          months=1, opts={"require_weekday": False}),
    Venue("velvetsun", "Velvetsun", "Ogikubo", ["https://www.velvetsun.jp/new-events"], reader="velvetsun", months=1,
          skip_title=r"BARやってます|bar営業|^bar\b"),
    Venue("knock", "Knock", "Koenji", ["https://knockkoenji.com/schedule/"], months=1),
    Venue("rooster", "Live Cafe Rooster", "Ogikubo", ["https://www.ogikubo-rooster.com/sch/index.html"], name_ja="荻窪ルースター",
          months=1, opts={"title_strip": r"^(?:終日|.{1,14}(?:さま|様))$"}),
    # --- livehouses and clubs (mixed genres) ---
    Venue("www", "WWW", "Shibuya", ["https://www-shibuya.jp/schedule/{ym}.php"], name_ja="渋谷WWW"),
    Venue("clubasia", "clubasia", "Shibuya", ["https://clubasia.jp/events_live", "https://clubasia.jp/events"],
          reader="clubasia", months=1),
    # --- concert halls ---
    Venue("triphony", "Sumida Triphony Hall", "Kinshicho", ["https://www.triphony.com/concert/{ym}list.html"],
          name_ja="すみだトリフォニーホール", tags=["Classical"], reader="triphony"),
]


def month_urls(v: Venue, today: date) -> list[tuple[str, date]]:
    out, first = [], today.replace(day=1)
    for tmpl in v.urls:
        if "{" not in tmpl:
            out.append((tmpl, first))
            continue
        cur = first
        for _ in range(v.months):
            out.append((tmpl.format(y=cur.year, m=cur.month, mm=f"{cur.month:02d}", ym=f"{cur.year}{cur.month:02d}"), cur))
            cur = (cur + timedelta(days=32)).replace(day=1)
    # pages without a template that hold 'next month' (Pit Inn /next-schedule/) get next month's context
    fixed = []
    for i, (u, ctx) in enumerate(out):
        if re.search(r"next|schedule2|live2", u):
            ctx = (first + timedelta(days=32)).replace(day=1)
        fixed.append((u, ctx))
    return fixed


# ----------------------------------------------------------------- dedicated readers

def read_velvetsun(html: str, ctx: date) -> list[Show]:
    """Squarespace event list: <article class="eventlist-event"> with <time datetime>."""
    soup = BeautifulSoup(html, "lxml")
    shows = []
    for ev in soup.select("article.eventlist-event"):
        t = ev.select_one("time.event-date")
        title = ev.select_one(".eventlist-title")
        if not t or not title or not t.get("datetime"):
            continue
        start = ev.select_one("time.event-time-24hr-start")
        body = nfkc(" ".join(x.get_text(" ", strip=True) for x in ev.select(".eventlist-description, .eventlist-excerpt")))
        adv, door, ptext, free = _prices(body)
        op, st = _times(body)
        link = ev.select_one("a.eventlist-title-link")
        shows.append(Show(date=t["datetime"][:10], title=nfkc(title.get_text(" ", strip=True)),
                          lines=[l for l in re.split(r"\s{2,}|(?<=\))\s", body)[:6] if l],
                          open_time=op, start_time=st or (parse_time(start.get_text()) if start else None),
                          price_adv=adv, price_door=door, price_text=ptext, free=free,
                          url=link["href"] if link else None))
    return shows


def read_clubasia(html: str, ctx: date) -> list[Show]:
    """Generic blocks, but each block starts with genre labels ('Hardcore', 'IDOL') before the title."""
    shows = parse_schedule(html, ctx, split_on_time=False)
    out = []
    for s in shows:
        parts = [s.title] + s.lines
        # the title is the longest of the first few lines; shorter ones before it are genre labels
        head = parts[:4]
        title = max(head, key=len)
        tags = [p for p in head[:head.index(title)] if len(p) <= 20 and p.lower() != "live"]
        s.title = title
        s.lines = parts[head.index(title) + 1:]
        s.note = ", ".join(tags) if tags else None       # carried into Gig.tags below
        out.append(s)
    return out


def read_triphony(html: str, ctx: date) -> list[Show]:
    soup = BeautifulSoup(html, "lxml")
    # the month heading ('2026年10月') sits in an h-tag; other '20XX年X月' strings on the page are notes
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        m = re.fullmatch(r"\s*(20\d\d)年\s*(\d{1,2})月\s*", h.get_text())
        if m:
            ctx = date(int(m.group(1)), int(m.group(2)), 1)
            break
    shows = []
    for dt in soup.select("dt.boxDate"):
        dd = dt.find_next_sibling("dd")
        if not dd or "noEvent" in (dd.get("class") or []):
            continue
        day = dt.select_one(".txtDate")
        title = dd.select_one(".ttlConcert")
        if not day or not title:
            continue
        try:
            d = date(ctx.year, ctx.month, int(day.get_text(strip=True)))
        except ValueError:
            continue
        title_txt = nfkc(title.get_text(" ", strip=True))
        if re.search(r"寄席|落語|講演", title_txt):          # comedy / talks, not concerts
            continue
        info = {nfkc(x.get_text(" ", strip=True)): nfkc(x.find_next_sibling("dd").get_text(" ", strip=True))
                for x in dd.select(".boxDetail dt") if x.find_next_sibling("dd")}
        op, st = _times(info.get("時間", ""))
        price_txt = nfkc((dd.select_one(".boxConcertPrice") or dd).get_text(" ", strip=True))
        adv, door, ptext, free = _prices(price_txt)
        nums = [int(n.replace(",", "")) for n in re.findall(r"[¥￥]\s*([\d,]{3,})", price_txt)]
        if nums and (adv is None or len(nums) > 1):      # seat tiers 'S¥8,000 A¥7,000': show the cheapest
            adv, door = min(nums), None
        hall = dt.select_one(".txtHall")
        link = title.find("a")
        shows.append(Show(date=d.isoformat(), title=title_txt,
                          lines=[l for l in re.split(r"\s{2,}|、", info.get("出演", ""))[:6] if l],
                          open_time=op, start_time=st or parse_time(dt.select_one(".txtTime").get_text() if dt.select_one(".txtTime") else ""),
                          price_adv=adv, free=free or bool(re.search(r"無料|入場無料", price_txt)) and adv is None,
                          price_text=("from " + price_txt[:60]) if adv and re.search(r"S\s*[¥￥]", price_txt) else None,
                          note=nfkc(hall.get_text(strip=True)) if hall else None,
                          url=urljoin("https://www.triphony.com/", link["href"]) if link and link.get("href") else None))
    return shows


READERS: dict[str, Callable[[str, date], list[Show]]] = {
    "velvetsun": read_velvetsun, "clubasia": read_clubasia, "triphony": read_triphony,
}

FORMAT_WORD = re.compile(r"^(?:\d{1,2}(?::\d\d)?\s*[ap]m\s*)?(?:solos?|duos?|trios?|quartets?|quintets?|ensembles?|sets?)$", re.I)


# ----------------------------------------------------------------- converting

def to_gig(v: Venue, s: Show, page_url: str) -> Optional[Gig]:
    title = s.title
    names = lineup(s)
    if v.lineup_title or FORMAT_WORD.match(title):
        people = [re.sub(r"\s*\[.*?\]", "", l).strip() for l in s.lines[:4]]
        people = [p for p in people if p and not FORMAT_WORD.match(p)]
        if people:
            title = ", ".join(people)
            names = people
    title = re.sub(r"\s+", " ", title).strip(" ・/／|")
    if len(title) < 2 or (v.skip_title and re.search(v.skip_title, title, re.I)):
        return None
    if re.search(r"【?公演中止】?|中止|cancel+ed", title, re.I):
        return None
    tags = list(v.tags)
    note = s.note if v.reader != "clubasia" else None
    if v.reader == "clubasia" and s.note:
        tags += [t.strip() for t in s.note.split(",")]
    v_en, v_ja = v.name, v.name_ja
    return Gig(
        date=s.date, title=title[:160], venue=v_en, venue_ja=v_ja,
        area=v.area, open_time=s.open_time, start_time=s.start_time,
        price_adv=s.price_adv, price_door=s.price_door, price_text=s.price_text, free=s.free,
        artists=names or [title], tags=tags, note=v.note or note,
        ticket_url=s.url, sources=[Source(f"{v.name} website", s.url or page_url)],
    )


def read_page(v: Venue, html: str, ctx: date, url: str) -> list[Gig]:
    if v.reader == "jsonld":
        gigs = []
        for ev in extract_events(html):
            g = event_to_gig(ev, f"{v.name} website", url)
            if g:
                g.venue, g.venue_ja, g.area, g.tags = v.name, v.name_ja, v.area, list(v.tags)
                gigs.append(g)
        return gigs
    reader = READERS.get(v.reader)
    shows = reader(html, ctx) if reader else parse_schedule(html, ctx, **v.opts)
    out, seen = [], set()
    for s in shows:
        g = to_gig(v, s, url)
        if g and (g.date, g.title) not in seen:
            seen.add((g.date, g.title))
            out.append(g)
    return out


def scrape(http, cfg: dict) -> list[Gig]:
    today = cfg.get("today") or date.today()
    only = set(cfg.get("venues") or [])
    gigs: list[Gig] = []
    for v in VENUES:
        if only and v.key not in only:
            continue
        n = 0
        for url, ctx in month_urls(v, today):
            html = http.text(url)
            if not html:
                continue
            try:
                page = read_page(v, html, ctx, url)
            except Exception as e:                 # one odd page must not stop the rest
                log.warning("venue %s: %s on %s", v.key, e, url)
                continue
            page = [g for g in page if (g.end_date or g.date) >= today.isoformat()]
            gigs += page
            n += len(page)
        log.info("venue %-12s %3d gigs", v.key, n)
    # the same show can appear on this month's and next month's page
    uniq = {(g.date, g.venue, g.title): g for g in gigs}
    return list(uniq.values())
