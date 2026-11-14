"""Shared helpers for museum scrapers (stdlib only, so GitHub Actions needs no installs)."""
import html
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (museum-seats personal checker)"
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

# Seconds to wait between requests to the same site, to stay gentle on museum servers.
REQUEST_GAP = 1.0


def http(url, data=None, timeout=20, retries=2):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                charset = r.headers.get_content_charset() or "utf-8"
                return r.read().decode(charset, errors="replace")
        except Exception as e:  # network hiccup: back off and retry
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def text(s):
    """Strip tags and collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def today_kst():
    return datetime.now(KST).date()


def is_weekend(d: date):
    return d.weekday() >= 5


def day_entry(d: date, holiday=False, sessions=None, status="open"):
    return {
        "date": d.isoformat(),
        "weekday": WEEKDAY_KO[d.weekday()],
        "holiday": holiday,
        "status": status,  # open | closed | notOpen
        "sessions": sessions or [],
    }
