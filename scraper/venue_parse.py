"""Read a live venue's own schedule page.

Most small Tokyo venue sites (jazz clubs, improv spaces, livehouses) post a month
page laid out as repeating blocks:

    10/1 Thu  |  1 (木)  |  10月2日（金）  |  2026.10.01 thu
    <act / title>
    <line-up with instruments>
    Open 19:00 / Start 19:30   ¥4,000 (1 drink)

parse_schedule() finds the date lines, splits the page into one block per show and
pulls out title, line-up, times and prices. A date only counts when the weekday printed
next to it matches the real calendar; that keeps calendar widgets, ticket-release
dates and "next month" teasers from becoming fake gigs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from bs4 import BeautifulSoup

from .textutil import nfkc, parse_price, parse_time

WD_EN = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
WD_JA = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
# A Japanese weekday only counts in brackets '(月)' or as '月曜': a bare 月 is usually 'month'
WD = (r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?(?![a-z])|"
      r"[\(（\[]\s*[月火水木金土日](?:曜日?)?(?:・?祝|・?休)?\s*[\)）\]]|[月火水木金土日]曜日?")
WD_RE = re.compile(r"^\s*(" + WD + r")", re.I)

# a date at the start of a line: M/D, M.D, M月D日, YYYY.MM.DD, or a bare day number
DATE_HEAD = re.compile(
    r"^(?:(?P<y>20\d\d)\s*[./\-年]\s*)?"
    r"(?:(?P<m>\d{1,2})\s*(?:[/.月]|\s*/\s*)\s*)?"
    r"(?P<d>\d{1,2})\s*日?"
    r"(?=$|[\s\(（\[.]|" + WD + r")", re.I)
MONTH_HEAD = re.compile(
    r"(?:(?P<y>20\d\d)\s*[./年\-]\s*(?P<m>\d{1,2})(?!\d)|(?P<m2>\d{1,2})\s*月(?!\s*\d)|"
    r"\b(?P<en>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(?P<y2>20\d\d)?)", re.I)
EN_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

CLOSED = re.compile(r"お休み|定休|休業|休み|店休|臨時休|貸切|貸し切り|private|closed|no live|ライブなし|close\b|holiday|クローズ", re.I)
NOISE = re.compile(
    r"^(?:\d\s*sets?|\d\s*st|ライブ情報|詳細(?:と予約|はこちら)?|予約(?:する|はこちら)?|reserve|reservation|members?|line\s*-?up|出演|"
    r"more|read more|チケット|tickets?|ticket info|公演終了|sold out|満席|取扱プレイガイド|[▲▼■□◆◇●○・※]|"
    r"昼の部|夜の部|朝の部|day\s*live|night|昼|夜|1部|2部|第[12一二]部)$", re.I)
TIME_WORDS = r"(?:open|start|開場|開演|開始|door|doors|show|stage|ステージ|1st|2nd|入場)"
TIME_LINE = re.compile(TIME_WORDS + r"|\d{1,2}\s*[:：時]\s*\d{0,2}\s*(?:分)?\s*(?:[〜~～\-－]|start|開演|開場|スタート)", re.I)
OPEN_RE = re.compile(r"(?:open|開場|door|doors)\s*[:：]?\s*(\d{1,2}\s*[:：.時]\s*\d{2}|\d{1,2}\s*時半?)", re.I)
START_RE = re.compile(r"(?:start|開演|開始|show|スタート|1st)\s*[:：]?\s*(\d{1,2}\s*[:：.時]\s*\d{2}|\d{1,2}\s*時半?)", re.I)
BARE_TIME = re.compile(r"(?<![\d¥￥,])(\d{1,2})\s*[:：時]\s*(\d{2})?\s*分?\s*(?:[〜~～\-－]|start|スタート|開演)", re.I)
PRICE_HINT = re.compile(r"[¥￥♪]\s*\d|\d[\d,]{2,}\s*(?:円|yen)|charge|チャージ|料金|前売|予約|当日|adv|door|music\s*c|m\.\s*charge|入場料|\bfree\b|無料|投げ銭|カンパ", re.I)
INSTRUMENT = re.compile(r"\((?:vo|p|pf|b|eb|ds|dr|g|gt|ts|as|ss|bs|sax|tp|tb|fl|vln|vn|vc|key|keys|per|perc|harp|cl|org|syn|electronics|voice|dance)[\w,./\s]*\)", re.I)


@dataclass
class Show:
    date: str
    title: str
    lines: list[str] = field(default_factory=list)
    open_time: Optional[str] = None
    start_time: Optional[str] = None
    price_adv: Optional[int] = None
    price_door: Optional[int] = None
    price_text: Optional[str] = None
    free: bool = False
    note: Optional[str] = None
    url: Optional[str] = None


def page_lines(html: str, start_after: str | None = None, stop_at: str | None = None) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg", "head", "select", "option", "nav", "footer", "form"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text("\n")
    raw = [nfkc(l) for l in text.splitlines()]
    raw = [l for l in raw if l]
    # rejoin names that the HTML split mid-bracket: 'チャリート(' + 'vo)'
    lines: list[str] = []
    for l in raw:
        if lines and lines[-1].count("(") > lines[-1].count(")") and len(lines[-1]) < 120:
            lines[-1] = lines[-1] + l
        else:
            lines.append(l)
    if start_after:
        idx = next((i for i, l in enumerate(lines) if re.search(start_after, l, re.I)), None)
        if idx is not None:
            lines = lines[idx + 1:]
    if stop_at:
        idx = next((i for i, l in enumerate(lines) if re.search(stop_at, l, re.I)), None)
        if idx is not None:
            lines = lines[:idx]
    return lines


def _wd(s: str) -> Optional[int]:
    m = WD_RE.match(s.strip())
    if not m:
        return None
    w = m.group(1).lower().strip("([（） ")
    if w[:3] in WD_EN:
        return WD_EN[w[:3]]
    return WD_JA.get(w[:1])


def _resolve(y: Optional[int], m: int, d: int, wd: int, ctx: date) -> Optional[date]:
    """Pick the year that makes (m, d) fall on weekday wd, close to the page's month."""
    years = [y] if y else [ctx.year, ctx.year + 1, ctx.year - 1]
    for yy in years:
        try:
            dt = date(yy, m, d)
        except ValueError:
            continue
        if dt.weekday() == wd and abs((dt - ctx).days) < 200:
            return dt
    return None


def find_dates(lines: list[str], ctx: date) -> list[tuple[int, int, date, str]]:
    """Return (line_index, lines_used, date, rest_of_line) for each validated date heading."""
    out = []
    month, year = ctx.month, ctx.year
    last: Optional[date] = None
    for i, line in enumerate(lines):
        mh = MONTH_HEAD.search(line)
        if mh and len(line) < 40 and not DATE_HEAD.match(line):
            mm = mh.group("m") or mh.group("m2")
            if mm and 1 <= int(mm) <= 12:
                month = int(mm)
                if mh.group("y"):
                    year = int(mh.group("y"))
            elif mh.group("en"):
                month = EN_MON[mh.group("en")[:3].lower()]
                if mh.group("y2"):
                    year = int(mh.group("y2"))
        m = DATE_HEAD.match(line)
        if not m or len(line) > 300:
            continue
        d = int(m.group("d"))
        mo = int(m.group("m")) if m.group("m") else month
        yr = int(m.group("y")) if m.group("y") else None
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            continue
        rest = line[m.end():].strip(" .")
        used = 1
        wd = _wd(rest)
        if wd is not None:
            rest = WD_RE.sub("", rest, count=1).strip(" )）]")
        else:
            # weekday on the next line ('10/1' / 'Thu'), possibly after a lone '/'
            for k in (1, 2):
                if i + k < len(lines) and len(lines[i + k]) <= 14:
                    wd = _wd(lines[i + k])
                    if wd is not None:
                        rest_next = WD_RE.sub("", lines[i + k], count=1).strip(" )）]")
                        rest = (rest + " " + rest_next).strip()
                        used = k + 1
                        break
                    if not re.fullmatch(r"[/\-.\s]*|\d{1,2}", lines[i + k]):
                        break
        if wd is None:
            continue
        if m.group("m"):
            dt = _resolve(yr, mo, d, wd, ctx)
        else:
            # a bare day number: try the month we're in, the heading's month, the page's month
            # and their neighbours; the printed weekday decides (month-nav links can't fool it)
            cands: list[date] = []
            if last:
                cur = last.replace(day=1)
                nxt = (cur + timedelta(days=32)).replace(day=1)
                cands += [nxt, cur] if d < last.day - 7 else [cur, nxt]
            hm = date(year, month, 1)
            cands += [hm, ctx.replace(day=1), (hm + timedelta(days=32)).replace(day=1), (hm - timedelta(days=1)).replace(day=1)]
            dt = None
            for strict in (True, False):          # prefer dates that keep moving forward
                for c in cands:
                    dt = _resolve(c.year, c.month, d, wd, c)
                    if dt and (not strict or not last or (dt - last).days >= 0):
                        break
                    dt = None
                if dt:
                    break
        if not dt:
            continue
        out.append((i, used, dt, rest))
        last = dt
    return out


def _times(text: str) -> tuple[Optional[str], Optional[str]]:
    o = OPEN_RE.search(text)
    s = START_RE.search(text)
    op = parse_time(o.group(1)) if o else None
    st = parse_time(s.group(1)) if s else None
    if not op and not st:
        b = BARE_TIME.search(text)
        if b:
            st = parse_time(f"{b.group(1)}:{b.group(2) or '00'}")
    # 'OPEN/START 18:30/19:00'
    if not (op and st):
        pair = re.search(r"open\s*/\s*start\s*[:：]?\s*(\d{1,2}[:：]\d{2})\s*/\s*(\d{1,2}[:：]\d{2})", text, re.I)
        if pair:
            op, st = parse_time(pair.group(1)), parse_time(pair.group(2))
    return op, st


def _prices(text: str) -> tuple[Optional[int], Optional[int], Optional[str], bool]:
    t = text.replace("♪", "¥")
    seg = [s for s in re.split(r"(?<=[\)）])\s+|\s{2,}|/(?=\s*(?:当日|door|day))", t) if PRICE_HINT.search(s)]
    joined = " ".join(seg) if seg else ""
    if not joined:
        return None, None, None, False
    adv = door = None
    m_adv = re.search(r"(?:予約|前売り?|adv\.?|advance|早割|web)\s*[:：(（]?\s*[¥￥]?\s*([\d,]{3,})", joined, re.I)
    m_door = re.search(r"(?:当日|door|day)\s*[:：(（]?\s*[¥￥]?\s*([\d,]{3,})", joined, re.I)
    if m_adv:
        adv = int(m_adv.group(1).replace(",", ""))
    if m_door:
        door = int(m_door.group(1).replace(",", ""))
    if adv is None and door is None:
        a, d, _, free = parse_price(joined)
        if a is None and not free:
            return None, None, joined[:120], False
        if free and a is None:
            return None, None, None, True
        adv, door = a, d
    # Knuttel-style '¥3,000(予約¥2,800)': the bare first price is the door price
    if m_adv and not m_door:
        first = re.search(r"[¥￥]\s*([\d,]{3,})", joined)
        if first and int(first.group(1).replace(",", "")) != adv:
            door = int(first.group(1).replace(",", ""))
    extra = re.search(r"drink|ドリンク|tax|税|オーダー|order|学生|student|配信", joined, re.I)
    return adv, door, (joined[:120] if extra else None), False


def _is_meta(line: str) -> bool:
    return bool(NOISE.match(line) or (TIME_LINE.search(line) and len(line) < 60) or
                (PRICE_HINT.search(line) and len(re.sub(r"[\d,¥￥円\s]", "", line)) < 25) or
                _wd(line) is not None and len(line) <= 12)


def parse_schedule(html: str, ctx: date, *, start_after: str | None = None, stop_at: str | None = None,
                   split_on_time: bool | None = None, max_lines: int = 14) -> list[Show]:
    lines = page_lines(html, start_after, stop_at)
    heads = find_dates(lines, ctx)
    shows: list[Show] = []
    for n, (i, used, dt, rest) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else min(len(lines), i + used + max_lines)
        block = ([rest] if rest else []) + lines[i + used:end]
        block = [b for b in block if b][:max_lines * 2]
        if not block or (CLOSED.search(" ".join(block[:2])) and len(" ".join(block[:2])) < 60):
            continue
        # several shows on one day: a time line before its act ('open 13:30 ...' / act / 'open 19:00 ...' / act)
        chunks = [block]
        first_content = next((b for b in block if not NOISE.match(b)), "")
        time_first = split_on_time if split_on_time is not None else bool(TIME_LINE.search(first_content) and len(first_content) < 80)
        if time_first:
            chunks, cur = [], []
            for b in block:
                if TIME_LINE.search(b) and len(b) < 80 and any(not _is_meta(x) for x in cur):
                    chunks.append(cur)
                    cur = []
                cur.append(b)
            chunks.append(cur)
        for ch in chunks:
            text = " ".join(ch)
            if CLOSED.search(text) and len(text) < 50:
                continue
            content = [b for b in ch if not _is_meta(b)]
            # the act often shares the date line with its price (Jirokichi: '10月2日(金)Act 予約(♪4000)')
            head = re.split(r"\s*(?:予約|前売|当日|open|開場|start|開演|charge|チャージ|料金)\s*[（(:：]?\s*[♪¥￥\d]", ch[0], flags=re.I)[0].strip(" ・/／")
            if ch is chunks[0] and rest and head and len(head) >= 2 and head == rest[:len(head)] and not _is_meta(head) and head not in content:
                content.insert(0, head)
            if not content:
                continue
            title = content[0]
            # an inline price/time on the title line (Jirokichi): keep only the act
            title = re.split(r"\s*(?:予約|前売|当日|open|開場|start|開演|charge|チャージ)\s*[（(:：]?\s*[♪¥￥\d]", title, flags=re.I)[0].strip(" ・/／")
            if len(title) < 2:
                continue
            op, st = _times(text)
            adv, door, ptext, free = _prices(text)
            note = None
            if re.search(r"昼の部|昼\b|day\s*live|afternoon|matinee", text, re.I):
                note = "afternoon"
            elif re.search(r"\bnight\b|深夜|オールナイト|all\s*night", text, re.I) and (st or op or "00:00") >= "21:00":
                note = "night"
            shows.append(Show(date=dt.isoformat(), title=title[:160], lines=content[1:8],
                              open_time=op, start_time=st, price_adv=adv, price_door=door,
                              price_text=ptext, free=free, note=note))
    return shows


def lineup(show: Show) -> list[str]:
    """Names from the title and line-up lines, without instrument tags."""
    names = []
    for l in [show.title] + show.lines[:4]:
        if PRICE_HINT.search(l) and len(l) < 60:
            continue
        for part in re.split(r"[、,/／]|\s{2,}|(?<=\))\s+|(?<=）)\s*", l):
            p = INSTRUMENT.sub("", part)
            p = re.sub(r"[\(（][^)）]{0,20}[\)）]", "", p).strip(" ・:：-")
            if 1 < len(p) <= 40 and not TIME_LINE.search(p):
                names.append(p)
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out[:12]
