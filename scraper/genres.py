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
                           "electro", "electronica", "trance", "footwork", "nu-disco", "bass-music", "bass music", "drumandbass", "juke", "breakbeats", "jungle", "breakbeat", "drum and bass",
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
    ("Hip-Hop & R&B", ["hip-hop", "hip hop", "hiphop", "rap", "randb", "r & b", "trap", "grime", "r&b", "rnb", "soul", "funk", "funk & soul",
                       "trap", "grime", "ヒップホップ"]),
    ("Pop & Idol", ["pop", "j-pop", "idol", "city pop", "anison", "anime", "vocaloid",
                    "k-pop", "アイドル"]),
    ("Folk & Acoustic", ["folk", "acoustic", "singer-songwriter", "singer songwriter", "country",
                         "bluegrass", "blues", "folk & blues", "americana", "弾き語り",
                         "フォーク"]),
    ("Classical", ["classical", "orchestra", "chamber", "opera", "baroque", "string quartet", "piano recital", "chamber music", "choir", "chorus", "vocal music", "brass band", "wind ensemble", "contemporary music", "organ recital",
                   "contemporary classical", "クラシック"]),
    ("World & Traditional", ["world", "latin", "reggae", "dancehall", "dub", "ska", "traditional", "traditional japanese", "hogaku", "hōgaku", "minyo", "min'yo", "noh", "kabuki", "shakuhachi", "tsugaru",
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
    "jirokichi": ["Folk & Acoustic", "Rock & Indie", "Jazz"], "rooster": ["Folk & Acoustic", "Rock & Indie"],
    "knock": ["Experimental & Noise"], "velvetsun": ["Experimental & Noise", "Folk & Acoustic"],
    "harlem": ["Hip-Hop & R&B"], "clubasia": ["Electronic & Club"], "toppan hall": ["Classical"],
    "kioi hall": ["Classical"], "hakuju hall": ["Classical"], "musicasa": ["Classical"], "triphony": ["Classical"],
    "casals hall": ["Classical"], "tokyo bunka kaikan": ["Classical"],
}


def guess_from_venue(venue: str) -> list[str]:
    v = (venue or "").lower()
    for key, gs in VENUE_HINTS.items():
        if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", v):
            return gs
    return []


# Words in a title or line-up that say what kind of gig it is (English and Japanese).
# Used only when no site gave a genre tag.
TITLE_KEYWORDS: list[tuple[str, str]] = [
    ("Jam & Open Mic", r"jam\s*session|ジャムセッション|open\s*mic|オープンマイク|(?<![ァ-ヴ])セッション(?![ァ-ヴ])"),
    ("Jazz", r"\bjazz\b|ジャズ|big\s*band|ビッグバンド|bebop|bossa\s*jazz|swing\s*night"),
    ("Hip-Hop & R&B", r"hip\s*-?hop|ヒップホップ|\brap\b|ラップ|\br&b\b|cypher|サイファー|mc\s*battle|\bsoul\s*(?:night|music)\b|\bfunk\b|ファンク"),
    ("Classical", r"recital|リサイタル|交響楽団|管弦楽|オーケストラ|orchestra|symphon|シンフォニー|philharmon|フィルハーモニ|弦楽|string\s*quartet|"
                  r"sonata|ソナタ|concerto|協奏曲|オペラ|\bopera\b|合唱|\bchoir\b|chorus|室内楽|chamber|バイオリン|ヴァイオリン|violin|チェロ|cello|"
                  r"ピアノ・?リサイタル|演奏会|定期演奏|吹奏楽|wind\s*orchestra|bach|バッハ|mozart|モーツァルト|beethoven|ベートーヴェン|ショパン|chopin|"
                  r"オルガン|organ\s*recital|声楽|ソプラノ|soprano|テノール|tenor|クラシック|classic(?:al)?\b"),
    ("World & Traditional", r"箏|(?<![ァ-ヴ])琴(?![ァ-ヴ])|尺八|三味線|三絃|三曲|津軽|民謡|雅楽|能楽|(?<![可才機])能(?=[\s・「『]|$)|狂言|邦楽|長唄|義太夫|"
                            r"浄瑠璃|和太鼓|太鼓|篠笛|琵琶|gagaku|min.?yo|shamisen|koto\b|shakuhachi|taiko|noh\b|"
                            r"flamenco|フラメンコ|tango|タンゴ|bossa|ボサノ|samba|サンバ|choro|ショーロ|brazil|ブラジル|celtic|ケルト|"
                            r"irish|アイリッシュ|fado|ファド|salsa|サルサ|cumbia|クンビア|afro|african|アフリカ|reggae|レゲエ|dancehall|"
                            r"gamelan|ガムラン|chanson|シャンソン|klezmer|クレズマー|balkan|バルカン|latin|ラテン|hawaiian|ハワイアン|"
                            r"ukulele|ウクレレ|india|インド|sitar|シタール|tabla|タブラ|okinawa|沖縄|三線|アイヌ|ainu|mongol|モンゴル|"
                            r"arab|アラブ|turkish|トルコ|persian|ペルシャ|gypsy|ジプシー|manouche|マヌーシュ|steel\s*pan|スティールパン"),
    ("Electronic & Club", r"(?<![a-z])dj(?![a-z])|techno|テクノ|\bhouse\s*(?:music|night|party)|\brave\b|レイヴ|club\s*night|electronic|エレクトロ"),
    ("Punk & Hardcore", r"punk|パンク|hardcore|ハードコア"),
    ("Metal", r"\bmetal\b|メタル|doom|sludge"),
    ("Pop & Idol", r"アイドル|idol|地下アイドル|アニソン|anison|vocaloid|ボカロ|歌謡"),
    ("Folk & Acoustic", r"弾き語り|acoustic|アコースティック|\bfolk\b|フォーク|blues|ブルース|singer.?songwriter|シンガーソングライター|カントリー|country\s*music"),
    ("Rock & Indie", r"\brock\b|ロック|\bindie\b|インディー|shoegaze|シューゲイ|post.?rock|garage"),
    ("Experimental & Noise", r"\bnoise\b|ノイズ|improvis|即興|\bdrone\b|ドローン|ambient|アンビエント|electro.?acoustic|現代音楽|contemporary\s*music|experimental|実験"),
]
_TITLE_PATS = [(b, re.compile(p, re.I)) for b, p in TITLE_KEYWORDS]


def title_genres(text: str) -> list[str]:
    out = []
    for b, pat in _TITLE_PATS:
        if pat.search(text or "") and b not in out:
            out.append(b)
    return out[:3]
