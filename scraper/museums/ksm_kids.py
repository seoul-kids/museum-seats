"""대한민국체육박물관(스포츠박물관) 어린이박물관.

Verified 2026-11-14, no login. The page needs a session cookie + CSRF token:
  1. GET reservationChildren.do               -> cookie + `_csrf: "<token>"` in inline JS
  2. POST /front/reservation/selectScheduleInfo.do (ymd=YYYY-MM-DD, rsvtSeCd=C, _csrf)
     -> list of sessions: hm (start), pscp (capacity), tnope (booked), rsvtOpenYmd, finishYn
An empty list means no sessions are registered for that day (closed, or not scheduled yet).
Booking opens per the museum "관람일 최대 30일 전"; in practice a whole month has opened at
once (December opened 2026-11-01), so open dates come from rsvtOpenYmd instead of a rule.
"""
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from common import KST, REQUEST_GAP, UA, day_entry, today_kst, wanted

BASE = "https://sportsmuseum.kspo.or.kr"
PAGE_URL = BASE + "/front/reservation/reservationChildren.do"
SCHEDULE_URL = BASE + "/front/reservation/selectScheduleInfo.do"
LOOKAHEAD_DAYS = 45  # a whole month opens at once, so look a bit past 30 days

INFO = {
    "id": "ksm-kids",
    "name": "스포츠박물관 어린이박물관",
    "short": "스포츠 어린이박물관",
    "tab": "스포츠",
    "bookingUrl": PAGE_URL,
    "note": "1일 5명 이하 예약 · 휴대폰 본인인증 필요",
    "openRule": {"text": "관람일 최대 30일 전 오픈 (12월분은 11/1에 한꺼번에 열렸어요)"},
}


class _Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        page = self._open(PAGE_URL)
        m = re.search(r'_csrf:\s*"([^"]+)"', page)
        if not m:
            raise RuntimeError("CSRF token not found on reservation page")
        self.csrf = m.group(1)

    def _open(self, url, data=None):
        body = urllib.parse.urlencode(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers={
            "User-Agent": UA, "X-Requested-With": "XMLHttpRequest"})
        last = None
        for attempt in range(3):
            try:
                with self.opener.open(req, timeout=20) as r:
                    return r.read().decode("utf-8", errors="replace")
            except Exception as e:
                last = e
                time.sleep(2 * (attempt + 1))
        raise last

    def schedule(self, d):
        raw = self._open(SCHEDULE_URL, {"ymd": d.isoformat(), "rsvtSeCd": "C", "_csrf": self.csrf})
        return json.loads(raw).get("list") or []


def fetch(holidays=None):
    holidays = holidays or {}
    s = _Session()
    today = today_kst()
    now_hm = datetime.now(KST).strftime("%H:%M")
    today_ymd = today.strftime("%Y%m%d")
    days, empty_dates, last_scheduled = [], [], None
    for i in range(LOOKAHEAD_DAYS + 1):
        d = today + timedelta(days=i)
        keep, name = wanted(d, holidays)
        if not keep:
            continue
        time.sleep(REQUEST_GAP)
        rows = [r for r in s.schedule(d) if r.get("useYn", "Y") == "Y"]
        if not rows:
            empty_dates.append((d, name))
            continue
        last_scheduled = d
        opened = all((r.get("rsvtOpenYmd") or "0") <= today_ymd for r in rows)
        if not opened:
            e = day_entry(d, holiday=name, status="notOpen")
            ymd = min(r["rsvtOpenYmd"] for r in rows)
            e["opensAt"] = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}T00:00+09:00"
            e["opensAtDateOnly"] = True
            days.append(e)
            continue
        sessions = []
        for r in sorted(rows, key=lambda r: r.get("seq", 0)):
            cap = int(r.get("pscp") or 0)
            remaining = max(cap - int(r.get("tnope") or 0), 0)
            if r.get("finishYn") == "Y" or (i == 0 and r.get("hm", "99:99") <= now_hm):
                status = "ended"
            elif remaining <= 0:
                status = "full"
            else:
                status = "open"
            sessions.append({
                "no": r.get("seq", len(sessions) + 1),
                "time": r.get("hm", ""),
                "remaining": remaining if status == "open" else 0,
                "capacity": cap or None,
                "status": status,
            })
        days.append(day_entry(d, holiday=name, sessions=sessions))
    # Weekends/holidays with no sessions inside the scheduled range are closures.
    for d, name in empty_dates:
        if last_scheduled and d < last_scheduled:
            days.append(day_entry(d, holiday=name, status="closed"))
    days.sort(key=lambda x: x["date"])
    return {**INFO, "days": days}
