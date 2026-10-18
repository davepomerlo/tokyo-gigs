"""Parsing helpers: prices, times, dates and Japanese -> English names."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# ---------------------------------------------------------------- normalise

def nfkc(s: str) -> str:
    """Full-width -> half-width (ＷＷＷ -> WWW, ２０００ -> 2000), tidy spaces."""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip()


JA_CHARS = re.compile(r"[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]")


def has_japanese(s: str) -> bool:
    return bool(JA_CHARS.search(s or ""))


# ---------------------------------------------------------------- times

def parse_time(s: str | None) -> Optional[str]:
    """'1930', '19:30', '19.30', '7:30pm', '18時30分' -> '19:30'."""
    if not s:
        return None
    s = nfkc(s).lower()
    m = re.search(r"(\d{1,2})\s*[:.時]\s*(\d{2})\s*(am|pm)?", s) or \
        re.search(r"\b(\d{1,2})(\d{2})\b()", s) or \
        re.search(r"\b(\d{1,2})\s*(am|pm)\b", s)
    if not m:
        m2 = re.search(r"(\d{1,2})\s*時", s)
        if not m2:
            return None
        h, mi, ap = int(m2.group(1)), 0, None
    elif len(m.groups()) == 2:            # "7pm"
        h, mi, ap = int(m.group(1)), 0, m.group(2)
    else:
        h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3) or None
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 30 or mi > 59:                 # 25:00 = 1am next day is legal in Japan
        return None
    return f"{h:02d}:{mi:02d}"


# ---------------------------------------------------------------- prices

_YEN = r"(?:¥|￥|\\)?\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(?:円|yen|jpy)?"


def _num(x: str) -> int:
    return int(x.replace(",", ""))


def parse_price(text: str | None) -> tuple[Optional[int], Optional[int], Optional[str], bool]:
    """Return (adv, door, original_text, is_free).

    Handles '¥3,000', '6500', '¥10,000/¥12,000', '¥1,000-¥3,000',
    '前売 3000円 / 当日 3500円', 'adv 2500 door 3000', 'Free', '¥500 + tip', 'TBC'.
    """
    if not text:
        return None, None, None, False
    raw = nfkc(text)
    low = raw.lower()
    free = bool(re.search(r"\bfree\b|無料|入場無料|投げ銭|donation", low)) and not re.search(r"\d{3,}", low)
    adv = door = None
    m_adv = re.search(r"(?:adv\.?|advance|前売り?|予約)\s*[:：]?\s*" + _YEN, low)
    m_door = re.search(r"(?:door|day|当日)\s*[:：]?\s*" + _YEN, low)
    if m_adv:
        adv = _num(m_adv.group(1))
    if m_door:
        door = _num(m_door.group(1))
    if adv is None and door is None:
        nums = [_num(n) for n in re.findall(_YEN, low)]
        nums = [n for n in nums if 100 <= n <= 200000]   # ignore '1 drink', years etc.
        if nums:
            adv = nums[0]
            # '¥10,000/¥12,000' -> tiers; keep first as adv, show the rest in text
    keep_text = raw if not re.fullmatch(r"[¥￥]?\s*[\d,]+\s*(円|yen)?", raw.strip()) else None
    return adv, door, keep_text, free


# ---------------------------------------------------------------- Japanese names
# Longest keys are applied first. Keeps the Japanese original alongside the English.

PLACES = {
    "東高円寺": "Higashi-Koenji", "高円寺": "Koenji", "下北沢": "Shimokitazawa",
    "渋谷": "Shibuya", "新宿": "Shinjuku", "新大久保": "Shin-Okubo", "大久保": "Okubo",
    "吉祥寺": "Kichijoji", "池袋": "Ikebukuro", "秋葉原": "Akihabara", "六本木": "Roppongi",
    "恵比寿": "Ebisu", "代官山": "Daikanyama", "原宿": "Harajuku", "表参道": "Omotesando",
    "南青山": "Minami-Aoyama", "青山": "Aoyama", "中野": "Nakano", "西荻窪": "Nishi-Ogikubo",
    "荻窪": "Ogikubo", "阿佐ヶ谷": "Asagaya", "阿佐谷": "Asagaya", "三軒茶屋": "Sangenjaya",
    "下高井戸": "Shimo-Takaido", "自由が丘": "Jiyugaoka", "中目黒": "Nakameguro", "目黒": "Meguro",
    "五反田": "Gotanda", "品川": "Shinagawa", "豊洲": "Toyosu", "有明": "Ariake", "お台場": "Odaiba",
    "新木場": "Shin-Kiba", "赤坂": "Akasaka", "銀座": "Ginza", "神保町": "Jimbocho",
    "水道橋": "Suidobashi", "両国": "Ryogoku", "浅草": "Asakusa", "上野": "Ueno",
    "錦糸町": "Kinshicho", "小岩": "Koiwa", "早稲田": "Waseda", "落合": "Ochiai",
    "幡ヶ谷": "Hatagaya", "代々木上原": "Yoyogi-Uehara", "代々木": "Yoyogi", "千駄木": "Sendagi",
    "八丁堀": "Hatchobori", "入谷": "Iriya", "大塚": "Otsuka", "新代田": "Shindaita",
    "町田": "Machida", "八王子": "Hachioji", "立川": "Tachikawa", "国分寺": "Kokubunji",
    "横浜": "Yokohama", "川崎": "Kawasaki", "千葉": "Chiba", "本八幡": "Motoyawata",
    "西永福": "Nishi-Eifuku", "初台": "Hatsudai", "東京": "Tokyo", "日比谷": "Hibiya",
    "九段下": "Kudanshita", "竹芝": "Takeshiba", "高田馬場": "Takadanobaba", "蒲田": "Kamata",
    "西麻布": "Nishi-Azabu", "麻布": "Azabu", "四谷": "Yotsuya", "曙橋": "Akebonobashi",
    "笹塚": "Sasazuka", "下北": "Shimokita", "府中": "Fuchu", "調布": "Chofu", "三鷹": "Mitaka",
    "所沢": "Tokorozawa", "さいたま": "Saitama", "大宮": "Omiya",
}

VENUE_WORDS = {
    "日本武道館": "Nippon Budokan", "東京ドーム": "Tokyo Dome", "両国国技館": "Ryogoku Kokugikan",
    "東京国際フォーラム": "Tokyo International Forum", "東京オペラシティ": "Tokyo Opera City",
    "国際": "International", "公会堂": "Public Hall", "会館": "Hall", "ホール": "Hall",
    "劇場": "Theater", "教会": "Church", "公園": "Park", "大学": "University",
    "ライブハウス": "Live House", "スタジオ": "Studio", "ガーデン": "Garden",
    "シアター": "Theater", "アリーナ": "Arena", "クラブ": "Club", "ブルーノート": "Blue Note",
    "大ホール": "Main Hall", "小ホール": "Small Hall", "ステージ": "Stage", "カフェ": "Cafe",
    "ドーム": "Dome", "ピット": "PIT", "ロフト": "Loft", "シェルター": "Shelter",
}

_DICT = {**PLACES, **VENUE_WORDS}
_KEYS = sorted(_DICT, key=len, reverse=True)

try:                       # optional, installed in CI via requirements.txt
    import pykakasi        # type: ignore
    _kks = pykakasi.kakasi()
except Exception:          # pragma: no cover
    _kks = None


def _romanise(s: str) -> str:
    if _kks is None:
        return s
    out = []
    for item in _kks.convert(s):
        orig = item.get("orig", "")
        out.append((item.get("hepburn") or orig).capitalize() if has_japanese(orig) else orig)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def to_english(name: str | None) -> tuple[Optional[str], Optional[str]]:
    """'下北沢SHELTER' -> ('Shimokitazawa SHELTER', '下北沢SHELTER').

    Returns (english, japanese_original_or_None). If a name can't be fully
    translated, falls back to romaji (when pykakasi is available) or keeps the
    original as the display name.
    """
    if not name:
        return None, None
    name = nfkc(name)
    if not has_japanese(name):
        return name, None
    # bilingual names: 'Blue Note / ブルーノート', 'Shinjuku Loft (新宿LOFT)'
    for pat in (r"^(.+?)\s*[/／]\s*(.+)$", r"^(.+?)\s*[(（]\s*([^)）]+?)\s*[)）]\s*$"):
        m = re.match(pat, name)
        if m:
            a, b = m.group(1).strip(), m.group(2).strip()
            if has_japanese(a) != has_japanese(b):
                en, ja = (b, a) if has_japanese(a) else (a, b)
                return en, ja
    out = name
    for k in _KEYS:
        if k in out:
            out = out.replace(k, f" {_DICT[k]} ")
    out = re.sub(r"\s+", " ", out).strip(" ・/")
    if has_japanese(out):
        rom = _romanise(out)
        out = rom if not has_japanese(rom) else out
    if has_japanese(out):
        return name, name          # couldn't translate; show original
    return out, name


AREA_EN = {v.lower(): v for v in PLACES.values()}


def norm_area(area: str | None) -> tuple[Optional[str], Optional[str]]:
    if not area:
        return None, None
    en, ja = to_english(area)
    return en, ja
