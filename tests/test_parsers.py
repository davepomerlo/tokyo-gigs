"""Run with:  python -m unittest discover -s tests -v"""
import unittest
from datetime import date
from pathlib import Path

from scraper.genres import bucket_tags
from scraper.merge import merge
from scraper.sources import jsonld, songkick, tokyodross, tokyogigguide as tgg
from scraper.textutil import parse_price, parse_time, to_english

FX = Path(__file__).parent / "fixtures"


def fx(name):
    return (FX / name).read_text(encoding="utf-8")


class FakeHttp:
    """Serves fixtures instead of hitting the network."""
    def __init__(self, pages):
        self.pages = pages
        self.requests_made = 0

    def text(self, url, **kw):
        self.requests_made += 1
        for key, val in self.pages.items():
            if key in url:
                return val
        return None

    def json(self, url, **kw):
        return self.pages.get("__json__")


class TextUtil(unittest.TestCase):
    def test_times(self):
        self.assertEqual(parse_time("1930"), "19:30")
        self.assertEqual(parse_time("18.30"), "18:30")
        self.assertEqual(parse_time("7:30pm"), "19:30")
        self.assertEqual(parse_time("18時半"), "18:00")
        self.assertIsNone(parse_time(""))

    def test_prices(self):
        self.assertEqual(parse_price("6500")[:2], (6500, None))
        self.assertEqual(parse_price("¥10,000/¥12,000")[0], 10000)
        self.assertEqual(parse_price("前売 3,000円 / 当日 3,500円")[:2], (3000, 3500))
        self.assertEqual(parse_price("adv 2500 door 3000")[:2], (2500, 3000))
        self.assertTrue(parse_price("Free")[3])
        self.assertFalse(parse_price("¥3,000")[3])
        self.assertIsNone(parse_price("¥TBC")[0])

    def test_japanese_names(self):
        self.assertEqual(to_english("下北沢SHELTER"), ("Shimokitazawa SHELTER", "下北沢SHELTER"))
        self.assertEqual(to_english("東京国際フォーラム ホールA")[0], "Tokyo International Forum Hall A")
        self.assertEqual(to_english("WWW X"), ("WWW X", None))

    def test_bilingual_names(self):
        self.assertEqual(to_english("Blue Note / ブルーノート"), ("Blue Note", "ブルーノート"))
        self.assertEqual(to_english("Shinjuku Loft (新宿LOFT)"), ("Shinjuku Loft", "新宿LOFT"))
        self.assertEqual(to_english("Nishieifuku 西永福JAM")[1], "Nishieifuku 西永福JAM")


class TokyoGigGuide(unittest.TestCase):
    TODAY = date(2026, 10, 16)

    def setUp(self):
        self.cards = {g.title: g for g in tgg.parse_list_page(fx("tgg_list_cards.html"), self.TODAY)}

    def test_all_cards_found(self):
        self.assertEqual(len(self.cards), 7)

    def test_card_fields(self):
        g = self.cards["DMBQ, kanekoayano"]
        self.assertEqual((g.date, g.open_time), ("2026-10-22", "18:45"))
        self.assertEqual((g.venue, g.area), ("Club Quattro", "Shibuya"))
        self.assertEqual((g.price_adv, g.price_door), (6500, 7000))
        self.assertEqual(len(g.tags), 5)
        self.assertEqual(g.artists, ["DMBQ", "kanekoayano"])
        self.assertEqual(g.sources[0].url, "https://www.tokyogigguide.com/en/gigs/event/42187-dmbq-kanekoayano")

    def test_drink_and_day_only_prices(self):
        g = self.cards["emulsion, WorldWideSize, sofabed, Shreddy Pulse"]
        self.assertEqual((g.price_adv, g.price_door), (None, 3000))
        self.assertIn("day only", g.price_text)
        self.assertEqual(g.area, "Shinjuku Gyoen")
        home = self.cards["雨ノ地 晴太郎, パワーパーティー900, オモイデショケイ, MicroLlama"]
        self.assertEqual((home.price_adv, home.price_door), (3000, 3500))
        self.assertIn("drink", home.price_text)

    def test_japanese_venue_and_free(self):
        g = self.cards["ZOOBOMBS, KO-GO-NO GORAIKO-Z, LOOLOWNINGEN, DJ KOMORI"]
        self.assertEqual((g.venue, g.venue_ja), ("Shimokitazawa SHELTER", "下北沢SHELTER"))
        self.assertEqual((g.area, g.area_ja), ("Shimokitazawa", "下北沢"))
        self.assertTrue(g.free)

    def test_year_rollover_and_date_in_title(self):
        g = self.cards["Oct 31 New Year Bash"]
        self.assertEqual(g.date, "2027-01-02")

    def test_real_site_layout(self):
        """Six cards as served by the live site on 2026-10-18 (unclosed <li>s, labelled boxes)."""
        gigs = tgg.parse_list_page(fx("tgg_real_2026-10.html"), date(2026, 10, 18))
        self.assertEqual(len(gigs), 6)
        self.assertEqual(len({g.sources[0].url for g in gigs}), 6)       # nested cards not mixed up
        mona = gigs[0]
        self.assertEqual((mona.date, mona.open_time, mona.venue, mona.area), ("2026-10-18", "11:30", "Mona Records", "Shimokitazawa"))
        self.assertEqual(len(mona.tags), 5)
        loft = gigs[1]
        self.assertEqual((loft.venue, loft.price_adv, loft.price_door), ("Loft", 5000, 5500))
        self.assertIn("drink", loft.price_text)
        dj = gigs[3]
        self.assertEqual((dj.price_adv, dj.price_door, dj.tags), (None, 1000, ["DJ"]))
        fl = gigs[5]
        self.assertEqual((fl.venue, fl.price_door, fl.open_time), ("Forestlimit", 2000, "18:00"))

    def test_table_layout(self):
        rows = tgg.parse_list_page(fx("tgg_list_table.html"), self.TODAY)
        self.assertEqual(len(rows), 2)
        drank = rows[0]
        self.assertEqual((drank.venue, drank.area, drank.open_time), ("Knuttel House", "Iriya", "19:00"))
        self.assertEqual((drank.price_adv, drank.price_door), (2800, 2500))
        jam = rows[1]
        self.assertEqual((jam.price_adv, jam.price_door, jam.tags), (None, 1500, []))

    def test_scrape_stops_on_short_page(self):
        import tempfile
        http = FakeHttp({"/en/gigs?start=0": fx("tgg_list_cards.html")})
        with tempfile.TemporaryDirectory() as tmp:
            gigs = tgg.scrape(http, {"today": self.TODAY, "cache_dir": tmp})
        self.assertEqual(len(gigs), 7)
        self.assertEqual(http.requests_made, 1)


class TokyoDross(unittest.TestCase):
    def setUp(self):
        self.oct = tokyodross.parse_post(fx("dross_oct_2026.html"), "Tokyo Gigs October 2026", "https://d/oct")
        self.nov = tokyodross.parse_post(fx("dross_nov_2026.html"), "Tokyo Gigs November 2026", "https://d/nov")

    def test_counts(self):
        self.assertEqual(len(self.oct), 26)
        self.assertEqual(len(self.nov), 12)

    def test_fields(self):
        g = next(x for x in self.oct if x.title.startswith("DMBQ"))
        self.assertEqual((g.date, g.venue, g.area, g.price_adv), ("2026-10-22", "Club Quattro", "Shibuya", 6500))
        self.assertEqual(g.artists, ["DMBQ", "KANEKOAYANO"])
        self.assertTrue(g.ticket_url.startswith("https://www.club-quattro.com"))

    def test_notes_and_free(self):
        night = next(x for x in self.oct if x.title.startswith("FRANÇOIS"))
        self.assertEqual(night.note, "night")
        free = next(x for x in self.oct if x.title.startswith("DĀM-FUNK"))
        self.assertTrue(free.free)
        self.assertIsNone(free.area)
        etc = next(x for x in self.oct if x.title.startswith("PEACH"))
        self.assertEqual(etc.title, "PEACH, 9991, FUCK ON THE BEACH, NEGATIVE SUN & more")
        self.assertNotIn("&c.", etc.artists[-1])

    def test_ranges(self):
        im = next(x for x in self.nov if x.title == "IRON MAIDEN")
        self.assertEqual((im.date, im.end_date, im.price_adv), ("2026-11-24", "2026-11-25", 15000))
        cross = next(x for x in self.nov if x.title.startswith("TEST ACROSS"))
        self.assertEqual((cross.date, cross.end_date, cross.price_adv), ("2026-11-30", "2026-12-01", 3000))

    def test_scrape_filters_past(self):
        feed = {"feed": {"entry": [
            {"title": {"$t": "Tokyo Gigs October 2026"}, "content": {"$t": fx("dross_oct_2026.html")},
             "link": [{"rel": "alternate", "href": "https://d/oct"}]},
            {"title": {"$t": "New (and old) music from Japan"}, "content": {"$t": "<p>review</p>"}, "link": []},
        ]}}
        gigs = tokyodross.scrape(FakeHttp({"__json__": feed}), {"today": date(2026, 10, 17)})
        self.assertTrue(all(g.date >= "2026-10-17" for g in gigs))
        self.assertEqual(len(gigs), 24)


class SongkickJsonLd(unittest.TestCase):
    def test_extract(self):
        evs = jsonld.extract_events(fx("songkick.html"))
        self.assertEqual(len(evs), 4)
        g = jsonld.event_to_gig(evs[0], "Songkick", "u")
        self.assertEqual((g.title, g.start_time, g.area), ("DMBQ", "19:30", "Shibuya"))
        dc = jsonld.event_to_gig(evs[1], "Songkick", "u")
        self.assertIsNone(dc.start_time)
        self.assertEqual((dc.venue, dc.venue_ja), ("Toyosu Pit", "豊洲ピット"))
        fest = jsonld.event_to_gig(evs[2], "Songkick", "u")
        self.assertEqual(fest.end_date, "2026-11-23")

    def test_scrape_genres(self):
        html = fx("songkick.html")
        http = FakeHttp({"/genre/rock": html, "japan-tokyo": html})
        gigs = songkick.scrape(http, {"songkick_pages": 1, "today": date(2026, 10, 17)})
        self.assertEqual(len(gigs), 3)               # past show dropped
        self.assertIn("Rock", gigs[0].tags)


class Merging(unittest.TestCase):
    def test_three_sources_one_gig(self):
        a = next(g for g in tgg.parse_list_page(fx("tgg_list_cards.html"), date(2026, 10, 16))
                 if g.title.startswith("DMBQ"))
        b = next(x for x in tokyodross.parse_post(fx("dross_oct_2026.html"), "Tokyo Gigs October 2026", "https://d")
                 if x.title.startswith("DMBQ"))
        c = jsonld.event_to_gig(jsonld.extract_events(fx("songkick.html"))[0], "Songkick", "u")
        out = merge([c, b, a])
        self.assertEqual(len(out), 1)
        g = out[0]
        self.assertEqual(g.title, "DMBQ, kanekoayano")          # TGG wins on title
        self.assertEqual((g.open_time, g.start_time), ("18:45", "19:30"))   # doors from TGG, start from Songkick
        self.assertEqual(g.price_adv, 6500)
        self.assertEqual([s.name for s in g.sources], ["Tokyo Gig Guide", "Tokyo Dross", "Songkick"])
        self.assertIn("club-quattro.com", g.ticket_url)          # Dross ticket link preferred
        self.assertEqual(g.genres, ["Rock & Indie"])
        self.assertEqual(len(g.artists), 2)                     # kanekoayano / Kaneko Ayano de-duplicated

    def test_different_venues_not_merged(self):
        oct_ = tokyodross.parse_post(fx("dross_oct_2026.html"), "Tokyo Gigs October 2026", "https://d")
        out = merge(oct_)
        self.assertEqual(len(out), len(oct_))

    def test_venue_genre_guess(self):
        g = next(x for x in tokyodross.parse_post(fx("dross_oct_2026.html"), "Tokyo Gigs October 2026", "d")
                 if x.title.startswith("PHEEROAN"))
        out = merge([g])[0]
        self.assertEqual(out.genres, ["Jazz"])
        self.assertTrue(out.genre_guessed)


class Genres(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual(bucket_tags(["Hardcore", "Crust"]), ["Punk & Hardcore"])
        self.assertEqual(bucket_tags(["Avant-pop", "Indie-Rock"]), ["Rock & Indie"])
        self.assertIn("Experimental & Noise", bucket_tags(["Free Improvisation", "Noise"]))
        self.assertEqual(bucket_tags([], "Open Jam Session"), ["Jam & Open Mic"])
        self.assertIn("Pop & Idol", bucket_tags(["Idol"]))


if __name__ == "__main__":
    unittest.main()


class RunFallback(unittest.TestCase):
    def test_failed_source_reuses_last_good(self):
        import json, tempfile
        from scraper import run
        from tests import make_sample

        class Broken(make_sample.FixtureHttp):
            def json(self, url, **kw):
                raise RuntimeError("site down")

        with tempfile.TemporaryDirectory() as tmp:
            cfgp = Path(tmp) / "c.json"
            cfgp.write_text(json.dumps({"sources": ["tokyodross"], "cache_dir": tmp, "days_ahead": 400}))
            orig_root, orig_http = run.ROOT, run.Http
            try:
                run.ROOT = Path(tmp)
                run.Http = make_sample.FixtureHttp
                run.main(["--config", str(cfgp)])
                good = json.loads((Path(tmp) / "docs/data/gigs.json").read_text())["gigs"]
                run.Http = Broken
                run.main(["--config", str(cfgp)])
                meta = json.loads((Path(tmp) / "docs/data/meta.json").read_text())
                again = json.loads((Path(tmp) / "docs/data/gigs.json").read_text())["gigs"]
            finally:
                run.ROOT, run.Http = orig_root, orig_http
            self.assertTrue(good)
            self.assertEqual(len(again), len(good))
            s = meta["sources"]["tokyodross"]
            self.assertTrue(s["used_previous_results"])
            self.assertIn("site down", s["error"])
