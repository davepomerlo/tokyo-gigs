from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Source:
    name: str          # e.g. "Tokyo Gig Guide"
    url: str           # link to the gig on that site


@dataclass
class Gig:
    date: str                              # YYYY-MM-DD (first day)
    title: str
    venue: str                             # display name, English where possible
    end_date: Optional[str] = None         # for multi-day events
    venue_ja: Optional[str] = None         # original Japanese name, if any
    area: Optional[str] = None             # neighbourhood, English
    area_ja: Optional[str] = None
    open_time: Optional[str] = None        # HH:MM, doors (開場)
    start_time: Optional[str] = None       # HH:MM, show (開演)
    price_adv: Optional[int] = None        # yen, advance (前売)
    price_door: Optional[int] = None       # yen, at the door (当日)
    price_text: Optional[str] = None       # original price text when not a plain number
    free: bool = False
    artists: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)     # raw genre tags from sources
    genres: list[str] = field(default_factory=list)   # normalised buckets
    genre_guessed: bool = False                       # genres inferred from venue only
    ticket_url: Optional[str] = None
    note: Optional[str] = None             # e.g. "night", "afternoon"
    sources: list[Source] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # drop empty values to keep the JSON small
        return {k: v for k, v in d.items() if v not in (None, [], False, "")}
