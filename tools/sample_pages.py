"""Save one copy of each candidate source page so new scrapers can be built against real HTML.

Run by .github/workflows/sample.yml (the build workspace can't reach these sites).
Writes samples/<slug>.html (+ up to 2 followed schedule pages per site) and samples/index.json.
Uses the same polite client as the scraper: honours robots.txt and Crawl-delay.
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scraper.http import Http  # noqa: E402

OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "samples")
LIST = Path(sys.argv[1] if len(sys.argv) > 1 else "tools/sample_urls.txt")
SCHEDULE_WORDS = re.compile(r"schedule|スケジュール|calendar|カレンダー|event|イベント|live|ライブ|予定|program|出演|month|月", re.I)
MAX_BYTES = 1_500_000


def candidates(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(base).netloc
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        url = urljoin(base, a["href"]).split("#")[0]
        if urlparse(url).netloc != host or url in seen or url.rstrip("/") == base.rstrip("/"):
            continue
        seen.add(url)
        text = (a.get_text(" ", strip=True) + " " + a["href"])[:200]
        if SCHEDULE_WORDS.search(text) and not re.search(r"\.(jpg|png|gif|pdf|zip)$|mailto:|instagram|twitter|facebook", url, re.I):
            out.append(url)
    # prefer URLs that say 'schedule' outright
    out.sort(key=lambda u: (0 if re.search(r"schedule|スケジュール|calendar", u, re.I) else 1, len(u)))
    return out[:2]


def sample_site(slug: str, url: str) -> list[dict]:
    http = Http(delay=3.0, timeout=30)
    rows = []
    for i, u in enumerate([url]):
        r = http.get(u, retries=1)
        rows.append(save(slug if i == 0 else f"{slug}-{i}", u, r, http))
        if r is not None and r.text:
            for j, follow in enumerate(candidates(r.text, r.url), 1):
                r2 = http.get(follow, retries=0)
                rows.append(save(f"{slug}-follow{j}", follow, r2, http))
    return rows


def save(name: str, url: str, r, http: Http) -> dict:
    row = {"name": name, "url": url, "status": getattr(r, "status_code", None) or http.last.get("status"),
           "error": http.last.get("error"), "final_url": getattr(r, "url", None),
           "crawl_delay": http.crawl_delay(url), "bytes": 0}
    if r is not None and r.text:
        body = r.text[:MAX_BYTES]
        (OUT / f"{name}.html").write_text(body, encoding="utf-8")
        row["bytes"] = len(body)
        row["has_jsonld"] = "application/ld+json" in body
        row["title"] = (BeautifulSoup(body, "lxml").title or BeautifulSoup("", "lxml")).get_text(strip=True)[:120] if "<title" in body.lower() else ""
    return row


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for line in LIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            slug, url = line.split(None, 1)
            jobs.append((slug, url))
    # different sites in parallel; each site gets its own polite client
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = [row for rows in ex.map(lambda j: sample_site(*j), jobs) for row in rows]
    (OUT / "index.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    ok = sum(1 for r in results if r["bytes"])
    print(f"saved {ok} of {len(results)} pages")


if __name__ == "__main__":
    main()
