"""Polite HTTP client: one session, per-host delay, robots.txt, retries."""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "TokyoGigsBot/1.0 (personal non-commercial gig calendar; "
    "daily scan; +https://github.com/)"
)


def pick_encoding(r: requests.Response) -> str:
    """Japanese venue sites often declare the wrong charset (or none). Valid UTF-8 wins;
    otherwise the page's own <meta charset>, then the header, then a guess."""
    raw = r.content
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    import re as _re
    m = _re.search(rb'<meta[^>]+charset=["\']?([A-Za-z0-9_\-]+)', raw[:4000], _re.I)
    if m:
        enc = m.group(1).decode("ascii", "ignore").lower()
        enc = {"shift-jis": "cp932", "shift_jis": "cp932", "sjis": "cp932", "x-sjis": "cp932", "euc-jp": "euc_jp"}.get(enc, enc)
        try:
            raw.decode(enc)
            return enc
        except (LookupError, UnicodeDecodeError):
            pass
    if r.encoding and r.encoding.lower() not in ("iso-8859-1",):
        return r.encoding
    return r.apparent_encoding or "utf-8"


class Http:
    def __init__(self, delay: float = 1.5, timeout: float = 25, user_agent: str = USER_AGENT):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "en,ja;q=0.8",
        })
        self.delay = delay
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.requests_made = 0

    def _allowed(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        rp = self._robots[base]
        return rp.can_fetch(self.s.headers["User-Agent"], url) if rp else True

    def crawl_delay(self, url: str) -> float:
        """The larger of our default delay and the site's robots.txt Crawl-delay."""
        p = urlparse(url)
        rp = self._robots.get(f"{p.scheme}://{p.netloc}")
        cd = None
        if rp is not None:
            try:
                cd = rp.crawl_delay(self.s.headers["User-Agent"])
            except Exception:
                cd = None
        return max(self.delay, float(cd or 0))

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        delay = self.crawl_delay(url)
        last = self._last.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < delay:
                log.debug("waiting %.0fs for %s", delay - gap, host)
                time.sleep(delay - gap)
        self._last[host] = time.monotonic()

    def get(self, url: str, *, retries: int = 2, **kw) -> requests.Response | None:
        self.last = {"url": url, "status": None, "error": None, "body": None}
        if not self._allowed(url):
            log.warning("robots.txt disallows %s - skipped", url)
            self.last["error"] = "disallowed by robots.txt"
            return None
        for attempt in range(retries + 1):
            self._wait(url)
            try:
                self.requests_made += 1
                r = self.s.get(url, timeout=self.timeout, **kw)
                self.last.update(status=r.status_code, body=r.text[:200000])
                if r.status_code == 200:
                    r.encoding = pick_encoding(r)
                    return r
                if r.status_code in (404, 410):
                    return None
                log.info("HTTP %s for %s (attempt %d)", r.status_code, url, attempt + 1)
                if r.status_code in (401, 403, 429):
                    return None      # refused: don't hammer the site with retries
            except requests.RequestException as e:
                self.last["error"] = f"{type(e).__name__}: {e}"
                log.info("error %s for %s (attempt %d)", e, url, attempt + 1)
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
        return None

    def text(self, url: str, **kw) -> str | None:
        r = self.get(url, **kw)
        return r.text if r is not None else None

    def json(self, url: str, **kw):
        r = self.get(url, **kw)
        if r is None:
            return None
        try:
            return r.json()
        except ValueError:
            return None
