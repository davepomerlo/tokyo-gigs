"""Venue websites and the new listing sites, tested on real pages saved in October 2026."""
import gzip
import unittest
from datetime import date
from pathlib import Path

from scraper.genres import bucket_tags, title_genres
from scraper.merge import fill_from_artists, merge
from scraper.models import Gig, Source
from scraper.sources import clubberia, concertsquare, reggaelife
from scraper.sources import venues as V
from scraper.venue_parse import find_dates, parse_schedule

FX = Path(__file__).parent / "fixtures" / "venues"
OCT = date(2026, 10, 1)


def fx(name):
    return gzip.open(FX / f"{name}.html.gz", "rt", encoding="utf-8").read()


def venue(key):
    return next(v for v in V.VENUES if v.key == key)


def read(key, fixture=None, ctx=OCT):
    return V.read_page(venue(key), fx(fixture or key), ctx, "https://example/")


class DateFinding(unittest.TestCase):
    def test_weekday_must_match(self):
        lines = ["10/1", "Thu", "Act A", "10/2", "Sat", "fake: Oct 2 2026 is a Friday", "10/3", "Sat", "Act C"]
        days = [d.isoformat() for _, _, d, _ in find_dates(lines, OCT)]
        self.assertEqual(days, ["2026-10-01", "2026-10-03"])

    def test_bare_month_kanji_is_not_monday(self):
        # '9' + '月' (month) must not become 'the 9th, a Monday'
        self.assertEqual(find_dates(["2026年", "9", "月", "1", "(木)", "Act"], OCT)[0][2], date(2026, 10, 1))

    def test_month_nav_link_does_not_shift_dates(self):
        lines = ["Oct 2026", "Nov", "1", "Thu", "ENCOUNTER", "2", "Fri", "Act"]
        self.assertEqual([d.isoformat() for _, _, d, _ in find_dates(lines, OCT)], ["2026-10-01", "2026-10-02"])

    def test_english_day_month(self):
        self.assertEqual(find_dates(["3 October (sat) 8pm trios"], OCT)[0][2], date(2026, 10, 3))

    def test_wraps_into_next_month(self):
        lines = ["30", "Fri", "A", "31", "Sat", "B", "1", "Sun", "C"]
        self.assertEqual(find_dates(lines, OCT)[-1][2], date(2026, 11, 1))


class JazzVenues(unittest.TestCase):
    def test_pit_inn(self):
        g = read("pitinn")
        self.assertEqual(len(g), 31)
        first = g[0]
        self.assertEqual((first.date, first.title, first.open_time, first.start_time, first.price_adv),
                         ("2026-10-01", "渋さ知らズ オーケストラ", "19:00", "19:30", 4400))
        self.assertEqual(first.venue, "Shinjuku Pit Inn")
        self.assertEqual(first.venue_ja, "新宿ピットイン")
        self.assertEqual(first.tags, ["Jazz"])

    def test_pit_inn_daytime_and_next_month(self):
        day = read("pitinn-day")
        self.assertEqual(day[0].start_time, "14:00")
        self.assertEqual(day[0].note, "afternoon")
        nxt = V.read_page(venue("pitinn"), fx("pitinn-next"), date(2026, 11, 1), "u")
        self.assertTrue(all(g.date.startswith("2026-11") for g in nxt))
        self.assertGreaterEqual(len(nxt), 28)

    def test_knuttel_house_two_shows_one_day(self):
        g = read("knuttel")
        self.assertGreaterEqual(len(g), 29)
        oct3 = [x for x in g if x.date == "2026-10-03"]
        self.assertEqual([x.start_time for x in oct3], ["14:00", "19:30"])
        self.assertEqual((oct3[0].price_adv, oct3[0].price_door), (2800, 3000))     # 予約 / door
        self.assertTrue(oct3[0].title.startswith("Sheen Trio"))

    def test_jirokichi_title_and_prices_on_date_line(self):
        g = read("jirokichi")
        harm = next(x for x in g if x.date == "2026-10-02")
        self.assertEqual((harm.title, harm.price_adv, harm.price_door, harm.start_time), ("はもにかDOJO", 4000, 4500, "19:30"))
        self.assertFalse(any(x.date == "2026-10-01" for x in g))                     # お休み (closed)

    def test_blue_note_and_cotton_club(self):
        bn = read("bluenote")
        self.assertIn("YELLOWJACKETS", [x.title for x in bn])
        cc = read("cottonclub")
        aki = next(x for x in cc if x.title.startswith("AKi LIVE 2026"))
        self.assertNotEqual(aki.price_adv, 2026)                                        # the year is not a price

    def test_other_jazz_rooms(self):
        for key, at_least in [("sometime", 30), ("yoyoginaru", 25), ("ochanaru", 25), ("koko", 15), ("aketa", 50), ("jzbrat", 40)]:
            with self.subTest(key=key):
                g = read(key)
                self.assertGreaterEqual(len(g), at_least)
                self.assertTrue(all(len(x.title) >= 2 for x in g))
        koko = read("koko")
        self.assertTrue(koko[0].title.endswith(")"))                                  # closing bracket kept

    def test_improv_spaces(self):
        perm = read("permian")
        self.assertEqual(len(perm), 9)
        self.assertTrue(perm[0].title.startswith("羽野昌二 Shoji Hano"))               # line-up, not '8pm trios'
        self.assertEqual(perm[0].start_time, "20:00")
        self.assertGreaterEqual(len(read("nanahari")), 60)
        pol = read("polaris")
        self.assertEqual(len(pol), 28)
        self.assertEqual(pol[0].venue, "Polaris")
        vs = read("velvetsun")
        self.assertGreaterEqual(len(vs), 40)
        self.assertFalse(any("BARやってます" in x.title for x in vs))                # bar nights skipped

    def test_rooster_skips_booking_names(self):
        g = read("rooster")
        self.assertFalse(any(x.title.endswith("さま") or x.title == "終日" for x in g))


class ClubsAndHalls(unittest.TestCase):
    def test_www_and_clubasia(self):
        www = read("www")
        self.assertGreaterEqual(len(www), 50)
        self.assertEqual(www[0].venue, "WWW")
        ca = read("clubasia", ctx=date(2026, 10, 1))
        growl = next(x for x in ca if x.title.startswith("GROWL PARTY"))
        self.assertIn("Game Music", growl.tags)

    def test_triphony(self):
        g = read("triphony")
        self.assertTrue(all(x.date.startswith("2026-10") for x in g))
        self.assertFalse(any("寄席" in x.title for x in g))                            # rakugo is not music
        sp = next(x for x in g if x.date == "2026-10-02")
        self.assertEqual((sp.start_time, sp.price_adv), ("18:30", 7000))

    def test_clubberia(self):
        g = clubberia.parse_week(fx("clubberia"), date(2026, 10, 18))
        self.assertEqual(len(g), 25)
        harlem = next(x for x in g if x.venue == "HARLEM")
        self.assertIn("HIPHOP", harlem.tags)
        self.assertEqual(bucket_tags(harlem.tags), ["Hip-Hop & R&B"])

    def test_reggae_life_tokyo_only(self):
        g = reggaelife.parse(fx("reggaelife"), date(2026, 10, 18))
        self.assertGreaterEqual(len(g), 10)
        self.assertTrue(all(x.tags == ["Reggae"] for x in g))
        self.assertIn("HARLEM", [x.venue for x in g])

    def test_concert_square(self):
        g = concertsquare.parse(fx("csq"))
        self.assertGreaterEqual(len(g), 15)
        fig = next(x for x in g if "Figaro" in x.title)
        self.assertEqual((fig.date, fig.start_time), ("2026-11-21", "13:00"))
        self.assertEqual(bucket_tags(fig.tags), ["Classical"])
        trad = concertsquare.parse(fx("csq-hougaku"))
        self.assertTrue(trad)
        self.assertEqual(bucket_tags(trad[0].tags), ["World & Traditional"])


class GenreGuessing(unittest.TestCase):
    def test_title_keywords(self):
        self.assertEqual(title_genres("津軽三味線ライブ"), ["World & Traditional"])
        self.assertEqual(title_genres("Open Jam Session"), ["Jam & Open Mic"])
        self.assertIn("Classical", title_genres("新日本フィルハーモニー交響楽団 定期演奏会"))
        self.assertEqual(title_genres("可能性"), [])                                      # 能 inside a word

    def test_artist_memory(self):
        tagged = Gig(date="2026-10-20", title="DMBQ, kanekoayano", venue="Club Quattro", artists=["DMBQ", "kanekoayano"],
                     genres=["Rock & Indie"], sources=[Source("Tokyo Gig Guide", "u")])
        bare = Gig(date="2026-10-30", title="KANEKOAYANO", venue="WWW X", artists=["KANEKOAYANO"],
                   genres=["Other"], sources=[Source("Tokyo Dross", "u")])
        mem = fill_from_artists([tagged, bare], {})
        self.assertEqual(bare.genres, ["Rock & Indie"])
        self.assertIn("kanekoayano", mem)

    def test_venue_site_and_guide_merge_on_time(self):
        site = read("pitinn")[0]                         # Japanese names
        guide = Gig(date=site.date, title="Shibusa Shirazu Orchestra", venue="Pit Inn", area="Shinjuku",
                    open_time="19:00", artists=["Shibusa Shirazu Orchestra"], tags=["Jazz"],
                    sources=[Source("Tokyo Gig Guide", "u")])
        out = merge([site, guide])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].title, "Shibusa Shirazu Orchestra")                 # the guide's English title
        self.assertEqual(out[0].price_adv, 4400)                                      # the venue's price


if __name__ == "__main__":
    unittest.main()
