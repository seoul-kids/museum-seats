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


def day_entry(d: date, holiday=None, sessions=None, status="open"):
    """holiday: public holiday name (str), True if flagged without a name, or None."""
    return {
        "date": d.isoformat(),
        "weekday": WEEKDAY_KO[d.weekday()],
        "holiday": holiday or None,
        "status": status,  # open | closed | notOpen
        "sessions": sessions or [],
    }


# Google's public Korean holiday calendar (no API key). Events whose DESCRIPTION is
# exactly "공휴일" are official days off, substitute holidays included; others are observances.
HOLIDAY_ICS = ("https://calendar.google.com/calendar/ical/"
               "ko.south_korea%23holiday%40group.v.calendar.google.com/public/basic.ics")


def load_holidays():
    """Return {date: name} of Korean public holidays, or {} if the calendar is unreachable."""
    try:
        ics = http(HOLIDAY_ICS)
    except Exception as e:
        print(f"[warn] holiday calendar unavailable: {e}")
        return {}
    out = {}
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics.replace("\r\n ", ""), re.S):
        d = re.search(r"DTSTART;VALUE=DATE:(\d{8})", ev)
        name = re.search(r"SUMMARY:(.*)", ev)
        desc = re.search(r"DESCRIPTION:(.*)", ev)
        if d and name and desc and desc.group(1).strip() == "공휴일":
            label = name.group(1).strip()
            if label.startswith("쉬는 날 "):  # Google's wording for 대체공휴일
                label = label[len("쉬는 날 "):] + " 대체휴일"
            out[datetime.strptime(d.group(1), "%Y%m%d").date()] = label
    return out


def wanted(d: date, holidays):
    """Weekend or public holiday -> (keep, holiday_name)."""
    name = holidays.get(d)
    return (d.weekday() >= 5 or name is not None), name
