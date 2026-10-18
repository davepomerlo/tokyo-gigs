# Tokyo Gigs

One list of live music in Tokyo, gathered every morning from several gig sites, with
time, price, venue and genre — filterable by day, genre, area and price, and readable
on a phone.

| Source | What it adds | How it's read |
|---|---|---|
| [Tokyo Gig Guide](https://www.tokyogigguide.com/en/gigs) | The backbone: hundreds of livehouse gigs with doors time, advance/door price, venue, area and genre tags | "All gigs" list pages, 50 gigs each |
| [Tokyo Dross](https://tokyodross.blogspot.com/) | Curated underground/experimental/international picks with direct ticket links | Monthly "Tokyo Gigs" posts via the Blogger feed |
| [Songkick](https://www.songkick.com/metro-areas/30717-japan-tokyo) | Touring and bigger shows, start times | schema.org data on the listing pages; genres from its genre filters |
| Any venue page with schema.org Event data | Whatever you add | Put the URL in `jsonld_pages` in `config.json` |

The same gig listed on several sites is merged into one entry (same day, same venue,
overlapping artists). Times prefer Tokyo Gig Guide, ticket links prefer Tokyo Dross,
and every entry links back to each site it came from.

Not included: **Japan Gigs** only posts flyer images on Instagram/X, so there's nothing
to read reliably. **e+, Pia, Lawson Ticket** are heavily scripted and block scrapers.

## Set up (once, about 5 minutes)

1. Create a new GitHub repository (public, so Pages and Actions are free) and push this folder to it.
2. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/docs` → Save.
3. **Settings → Actions → General** → Workflow permissions: *Read and write permissions* → Save.
4. **Actions → Daily gig scan → Run workflow** for the first scan (about 15 minutes).

After that it runs by itself at 05:00 JST every day, commits the new `docs/data/gigs.json`,
and the page at `https://<your-user>.github.io/<repo>/` updates.

Until the first scan finishes the page shows sample listings built from the test fixtures.

## Use it as an app on your phone

The page is an installable web app: it gets its own home-screen icon, opens full-screen
without browser bars, and keeps the last listings for offline use (on the subway, say).

- **iPhone:** open the page in **Safari** → Share button → **Add to Home Screen** (ホーム画面に追加).
  The page shows this tip to iPhone visitors.
- **Android:** open it in **Chrome** → tap **Install app** at the top of the page
  (or ⋮ menu → *Install app* / *Add to Home screen*).
- **Mac/PC:** Chrome or Edge show an install icon in the address bar.

Long-pressing the icon (Android) offers *Tonight* and *This weekend* shortcuts.
An installed app that stays open overnight reloads itself on the next Tokyo day.

When you change anything in `docs/` (not the daily data), bump `VERSION` in `docs/sw.js`
so installed copies pick up the new version on their next launch.

### App Store / Google Play (optional)

Only worth it if you want the app listed in a store. The web app above already does
everything this project needs, and daily listing updates keep working either way.

- **Google Play:** [PWABuilder](https://www.pwabuilder.com) can wrap this site as an Android app
  (a "Trusted Web Activity") from its URL. Needs a Google Play developer account (one-off fee).
- **App Store:** wrap `docs/` with [Capacitor](https://capacitorjs.com), build in Xcode on a Mac,
  and join the Apple Developer Program (US$99/year). Apple often rejects apps that are mostly
  a website, so adding native extras (e.g. reminder notifications for saved gigs) helps.

## Being a good neighbour

- Tokyo Gig Guide's robots.txt asks for **2 minutes between requests**. The scraper reads
  robots.txt for every site and honours it, which is why the scan takes ~15 minutes.
  It reads only the list pages (≈6–8 requests a day), never the individual gig pages.
- The project is non-commercial and links back to every source. If you plan to share the
  page widely, it's worth emailing Tokyo Gig Guide (contact address is in the site footer)
  — they may be happy to offer a feed.
- If a site fails, yesterday's results for that site are kept (up to 3 days) and the page
  footer says so, so one broken site never empties the list.

## Working on it

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .    # parser tests, no network
python -m tests.make_sample                  # rebuild sample data for previewing
python -m scraper.run --only tokyodross -v   # real scan of one source
cd docs && python -m http.server             # view at http://localhost:8000
```

`config.json` options: `days_ahead` (how far ahead to list), `delay_seconds` (minimum gap
between requests to one site), `songkick_pages`, `songkick_genres`, `jsonld_pages`.

### Adding a source

Write `scraper/sources/<name>.py` with `scrape(http, cfg) -> list[Gig]`, add it to
`SOURCES` in `scraper/run.py` and to `sources` in `config.json`, and add a fixture + test.
If the site already publishes schema.org Events, just add its URL to `jsonld_pages`.

### Files

```
scraper/run.py            daily entry point, writes docs/data/gigs.json + meta.json
scraper/sources/*.py      one module per site
scraper/merge.py          joins the same gig from different sites
scraper/genres.py         maps site genre tags onto 12 filter buckets (+ venue hints)
scraper/textutil.py       prices, times, Japanese → English place names (日本語 kept alongside)
docs/                     the web page (GitHub Pages)
docs/manifest.webmanifest app name, icons, shortcuts for installing
docs/sw.js                offline support (service worker)
.github/workflows/scan.yml  the 05:00 JST job
```
