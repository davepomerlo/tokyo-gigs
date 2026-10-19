"""Merge the same gig listed on several sites into one entry."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date, timedelta

from .genres import bucket_tags, guess_from_venue, title_genres
from .models import Gig, Source
from .textutil import PLACES, nfkc

PRIORITY = {"Tokyo Gig Guide": 1, "Tokyo Dross": 2, "Concert Square": 4, "Clubberia": 4, "Reggae Life": 5, "Songkick": 6}
VENUE_SITE = 3          # a venue's own website: after the two guides (English titles), before the rest
VENUE_STOP = {"club", "the", "tokyo", "live", "house", "livehouse", "spotify", "hall", "space",
              "studio", "bar", "cafe", "and", "&", "東京"} | {p.lower() for p in PLACES.values()} \
    | {"shimokita", "minami", "higashi", "nishi", "kita"}


def _prio(g: Gig) -> int:
    if not g.sources:
        return 9
    return min(PRIORITY.get(s.name, VENUE_SITE if s.name.endswith(" website") else 8) for s in g.sources)


def venue_tokens(name: str) -> frozenset[str]:
    name = nfkc(name).split(" / ")[0].lower()
    toks = re.findall(r"[a-z0-9]+|[^\sa-z0-9\W]+", name)
    toks = [t for t in toks if t not in VENUE_STOP]
    return frozenset(toks or re.findall(r"[a-z0-9]+", name))


def same_venue(a: Gig, b: Gig) -> bool:
    ta, tb = venue_tokens(a.venue), venue_tokens(b.venue)
    if ta and tb:
        j = len(ta & tb) / len(ta | tb)
        if j >= 0.6:
            return True
    if a.venue_ja and b.venue_ja and a.venue_ja == b.venue_ja:
        return True
    return False


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", nfkc(s).lower())


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[0-9a-z぀-ヿ一-鿿]{3,}", nfkc(s).lower())
            if w not in {"and", "the", "more", "with", "feat", "vol", "live", "presents", "tour", "japan", "2026", "2027"}}


def same_time(a: Gig, b: Gig) -> bool:
    """Same venue, same day, same doors or start time: the same show even if one site writes the
    names in Japanese and the other in English."""
    for x, y in ((a.start_time, b.start_time), (a.open_time, b.open_time)):
        if x and y and x == y:
            return True
    return False


def same_show(a: Gig, b: Gig) -> bool:
    aa = {_norm(x) for x in a.artists if len(_norm(x)) >= 3}
    bb = {_norm(x) for x in b.artists if len(_norm(x)) >= 3}
    if aa & bb:
        return True
    for x in aa:
        for y in bb:
            if len(x) >= 4 and len(y) >= 4 and (x in y or y in x):
                return True
    wa, wb = _words(a.title), _words(b.title)
    if wa and wb and len(wa & wb) / min(len(wa), len(wb)) >= 0.5:
        return True
    return False


def _days(g: Gig) -> list[str]:
    d0 = date.fromisoformat(g.date)
    d1 = date.fromisoformat(g.end_date) if g.end_date else d0
    n = min((d1 - d0).days, 10)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n + 1)]


def merge(gigs: list[Gig]) -> list[Gig]:
    parent = list(range(len(gigs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_day = defaultdict(list)
    for i, g in enumerate(gigs):
        for d in _days(g):
            by_day[d].append(i)
    for idxs in by_day.values():
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                i, j = idxs[x], idxs[y]
                a, b = gigs[i], gigs[j]
                if {s.name for s in a.sources} == {s.name for s in b.sources}:
                    continue   # never merge two listings from the same site
                if same_venue(a, b) and (same_show(a, b) or same_time(a, b)):
                    parent[find(i)] = find(j)

    groups = defaultdict(list)
    for i in range(len(gigs)):
        groups[find(i)].append(gigs[i])
    return [combine(sorted(g, key=_prio)) for g in groups.values()]


def _first(gs, attr):
    for g in gs:
        v = getattr(g, attr)
        if v not in (None, "", []):
            return v
    return None


def combine(gs: list[Gig]) -> Gig:
    base = gs[0]
    out = Gig(date=min(g.date for g in gs), title=base.title, venue=base.venue)
    ends = [g.end_date for g in gs if g.end_date]
    out.end_date = max(ends) if ends else None
    for attr in ("venue_ja", "area", "area_ja", "open_time", "start_time", "price_adv",
                 "price_door", "price_text", "note"):
        setattr(out, attr, _first(gs, attr))
    out.free = any(g.free for g in gs) and not out.price_adv
    # Dross links straight to the ticket/venue page, prefer it for tickets
    out.ticket_url = _first(sorted(gs, key=lambda g: 0 if g.sources[0].name == "Tokyo Dross" else 1), "ticket_url")
    seen, artists = set(), []
    for g in gs:
        for a in g.artists:
            k = _norm(a)
            if k and k not in seen:
                seen.add(k)
                artists.append(a)
    out.artists = artists[:25]
    out.tags = sorted({t for g in gs for t in g.tags})
    srcs, seen_s = [], set()
    for g in gs:
        for s in g.sources:
            if s.name not in seen_s:
                seen_s.add(s.name)
                srcs.append(Source(s.name, s.url))
    out.sources = srcs
    out.genres = bucket_tags(out.tags, out.title)
    if not out.genres:
        out.genres = title_genres(" ".join([out.title] + out.artists[:8]))
    if not out.genres:
        out.genres = guess_from_venue(out.venue)
        out.genre_guessed = bool(out.genres)
    if not out.genres:
        out.genres = ["Other"]
    return out


def gig_id(g: Gig) -> str:
    key = f"{g.date}|{'-'.join(sorted(venue_tokens(g.venue)))}|{_norm(g.title)[:40]}"
    return hashlib.sha1(key.encode()).hexdigest()[:10]


ARTIST_STOP = {"more", "guest", "guests", "and", "others", "djs", "dj", "live", "band", "trio", "duo", "quartet",
               "solo", "special", "session", "jam", "tba", "tbc", "open", "various", "secret"}


def fill_from_artists(gigs: list[Gig], memory: dict[str, list[str]]) -> dict[str, list[str]]:
    """Give untagged gigs the genres their artists have elsewhere (today's listings or past scans).

    Returns the updated artist -> genres memory, which run.py keeps in data/cache/.
    """
    from collections import Counter, defaultdict
    seen: dict[str, Counter] = defaultdict(Counter)
    for g in gigs:
        if g.genre_guessed or g.genres in ([], ["Other"]):
            continue
        for a in g.artists[:8]:
            k = _norm(a)
            if len(k) >= 4 and k not in ARTIST_STOP:
                seen[k].update(x for x in g.genres if x != "Other")
    mem = dict(memory)
    for k, c in seen.items():
        mem[k] = [x for x, _ in c.most_common(2)]
    for g in gigs:
        if g.genres not in (["Other"], []) and not g.genre_guessed:
            continue
        votes: Counter = Counter()
        for a in g.artists[:8]:
            k = _norm(a)
            if k in mem and k not in ARTIST_STOP:
                votes.update(mem[k])
        if votes:
            g.genres = [x for x, _ in votes.most_common(2)]
            g.genre_guessed = False
    if len(mem) > 30000:                       # keep the file small
        mem = dict(list(mem.items())[-30000:])
    return mem
