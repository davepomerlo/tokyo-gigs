"""Build docs/data/*.json from the test fixtures, so the page can be previewed
before the first real scan:   python -m tests.make_sample
The real GitHub Action overwrites these files on its first run."""
import json
from pathlib import Path

from scraper import run
from tests.test_parsers import fx

FEED = {"feed": {"entry": [
    {"title": {"$t": "Tokyo Gigs October 2026"}, "content": {"$t": fx("dross_oct_2026.html")},
     "link": [{"rel": "alternate", "href": "https://tokyodross.blogspot.com/2026/01/tokyo-gigs-october-2026.html"}]},
    {"title": {"$t": "Tokyo Gigs November 2026"}, "content": {"$t": fx("dross_nov_2026.html")},
     "link": [{"rel": "alternate", "href": "https://tokyodross.blogspot.com/2026/01/tokyo-gigs-november-2026.html"}]},
]}}
PAGES = {
    "tokyogigguide.com/en/gigs?start=0": fx("tgg_list_cards.html"),
    "japan-tokyo/genre/rock": fx("songkick.html"),
    "japan-tokyo/genre/indie": fx("songkick.html"),
    "30717-japan-tokyo": fx("songkick.html"),
}


class FixtureHttp:
    def __init__(self, *a, **kw):
        self.requests_made = 0

    def text(self, url, **kw):
        self.requests_made += 1
        if "/genre/" in url and not any(g in url for g in ("genre/rock", "genre/indie")):
            return None
        for k, v in PAGES.items():
            if k in url and "page=" not in url:
                return v
        return None

    def json(self, url, **kw):
        self.requests_made += 1
        return FEED if "feeds/posts" in url else None


if __name__ == "__main__":
    run.Http = FixtureHttp
    rc = run.main(["--only", "tokyogigguide,tokyodross,songkick"])
    meta_path = Path(run.ROOT / "docs" / "data" / "meta.json")
    meta = json.loads(meta_path.read_text())
    meta["sample"] = True
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    for f in run.ROOT.glob("data/cache/last_*.json"):
        f.unlink()       # don't let fixture data masquerade as a real 'last good' run
    raise SystemExit(rc)
