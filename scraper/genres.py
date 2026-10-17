"""Map the many raw genre tags used by each site onto a dozen filterable buckets."""
from __future__ import annotations

import re

BUCKETS: list[tuple[str, list[str]]] = [
    ("Punk & Hardcore", ["punk", "hardcore", "crust", "grind", "grindcore", "oi", "emo",
                         "screamo", "powerviolence", "d-beat", "noisecore", "pop punk",
                         "ska punk", "post-hardcore", "パンク", "ハードコア"]),
    ("Metal", ["metal", "doom", "sludge", "thrash", "death metal", "black metal", "stoner",
               "metalcore", "deathcore", "djent", "メタル"]),
    ("Rock & Indie", ["rock", "indie", "alternative", "alt", "garage", "psych", "psychedelic",
                      "neo-psychedelia", "shoegaze", "post-rock", "math rock", "grunge",
                      "power pop", "new wave", "post-punk", "avant-pop", "kraut", "krautrock",
                      "surf", "rockabilly", "psychobilly", "dream pop", "lo-fi", "guitar pop",
                      "indie & alt", "ロック"]),
    ("Electronic & Club", ["electronic", "techno", "house", "dj", "djs", "edm", "club",
                           "electro", "trance", "footwork", "breakbeat", "drum and bass",
                           "drum & bass", "dnb", "jungle", "bass", "idm", "dubstep", "gabber",
                           "hardstyle", "disco", "synth", "synthpop", "technopop", "dance",
                           "テクノ", "ハウス"]),
    ("Experimental & Noise", ["experimental", "noise", "improv", "improvised", "improvisation",
                              "free improvisation", "avant-garde", "avant garde", "drone",
                              "ambient", "sound art", "electroacoustic", "musique concrete",
                              "butoh", "performance", "minimal", "contemporary music",
                              "ノイズ", "即興", "実験"]),
    ("Jazz", ["jazz", "free jazz", "bebop", "swing", "fusion", "big band", "jazz session",
              "ジャズ"]),
    ("Hip-Hop & R&B", ["hip-hop", "hip hop", "rap", "r&b", "rnb", "soul", "funk", "funk & soul",
                       "trap", "grime", "ヒップホップ"]),
    ("Pop & Idol", ["pop", "j-pop", "idol", "city pop", "anison", "anime", "vocaloid",
                    "k-pop", "アイドル"]),
    ("Folk & Acoustic", ["folk", "acoustic", "singer-songwriter", "singer songwriter", "country",
                         "bluegrass", "blues", "folk & blues", "americana", "弾き語り",
                         "フォーク"]),
    ("Classical", ["classical", "orchestra", "chamber", "opera", "baroque", "string quartet",
                   "contemporary classical", "クラシック"]),
    ("World & Traditional", ["world", "latin", "reggae", "dub", "ska", "traditional", "minyo",
                             "gagaku", "koto", "shamisen", "taiko", "african", "afro", "brazilian",
                             "bossa", "samba", "cumbia", "flamenco", "celtic", "balkan",
                             "gamelan", "民謡", "雅楽", "レゲエ"]),
    ("Jam & Open Mic", ["jam", "jam session", "open mic", "open jam", "session",
                        "セッション"]),
]

_PATTERNS = [
    (name, re.compile(r"(?<![a-z])(" + "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True)) + r")(?![a-z])", re.I))
    for name, keys in BUCKETS
]

GENRE_NAMES = [b for b, _ in BUCKETS] + ["Other"]


def bucket_tags(tags: list[str], title: str = "") -> list[str]:
    """Return matching buckets for raw tags. Title only used for jam sessions."""
    text = " | ".join(t.lower() for t in tags)
    out: list[str] = []
    for name, pat in _PATTERNS:
        if pat.search(text):
            out.append(name)
    # 'session' as a tag is too loose; only trust jam/open mic from the title
    if "Jam & Open Mic" not in out and re.search(r"\b(jam session|open mic|open jam)\b", title, re.I):
        out.append("Jam & Open Mic")
    # "pop" sneaks in from "avant-pop", "power pop" etc. — only keep Pop if it was a bare tag
    if "Pop & Idol" in out and not any(re.fullmatch(r"(j-)?pop|idol|city pop|anison|k-pop|アイドル", t.strip(), re.I) for t in tags):
        out.remove("Pop & Idol")
    # "dub", "bass" alone shouldn't make a reggae gig electronic and vice versa — fine to overlap
    return out


# Venues with a strong house style. Only used when a gig has no genre at all.
VENUE_HINTS: dict[str, list[str]] = {
    "pit inn": ["Jazz"], "blue note": ["Jazz"], "cotton club": ["Jazz"], "billboard live": ["Jazz", "Hip-Hop & R&B"],
    "body & soul": ["Jazz"], "polaris": ["Experimental & Noise", "Jazz"], "ftarri": ["Experimental & Noise"],
    "permian": ["Experimental & Noise"], "knuttel house": ["Experimental & Noise"],
    "bar isshee": ["Experimental & Noise", "Jazz"], "shichoshitsu": ["Experimental & Noise"],
    "hako gallery": ["Experimental & Noise"], "nanahari": ["Experimental & Noise"],
    "gekkasha": ["Experimental & Noise"], "otooto": ["Experimental & Noise"],
    "earthdom": ["Punk & Hardcore", "Metal"], "antiknock": ["Punk & Hardcore", "Metal"],
    "bush bash": ["Punk & Hardcore", "Experimental & Noise"], "20000v": ["Punk & Hardcore"],
    "zone-b": ["Punk & Hardcore"], "soup": ["Punk & Hardcore", "Experimental & Noise"],
    "ufo club": ["Rock & Indie"], "shelter": ["Rock & Indie"], "fever": ["Rock & Indie"],
    "basement bar": ["Rock & Indie"], "three": ["Rock & Indie"], "era": ["Rock & Indie"],
    "moonstep": ["Metal", "Punk & Hardcore"], "circus": ["Electronic & Club"],
    "vent": ["Electronic & Club"], "contact": ["Electronic & Club"], "womb": ["Electronic & Club"],
    "forestlimit": ["Electronic & Club", "Experimental & Noise"], "spread": ["Electronic & Club", "Rock & Indie"],
    "oath": ["Electronic & Club"], "pulse": ["Electronic & Club"], "zero": ["Electronic & Club"],
    "tokyo opera city": ["Classical"], "suntory hall": ["Classical"], "oji hall": ["Classical"],
    "sogetsu": ["Experimental & Noise"],
}


def guess_from_venue(venue: str) -> list[str]:
    v = (venue or "").lower()
    for key, gs in VENUE_HINTS.items():
        if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", v):
            return gs
    return []
