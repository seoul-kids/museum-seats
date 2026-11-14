"""국립중앙박물관 어린이박물관 (National Museum of Korea - Children's Museum).

The reservation page calls a public JSON API (verified 2026-11-14, no login):
  GetBookPlayDate.json?play_month=YYYYMM      -> bookable dates (one row per session)
  GetBookPlaySequence.json?play_date=YYYYMMDD -> sessions with book_remain_count
Seat logic mirrors the site's own reservationTable(): book_yn '0' means closed,
<=1 left shows as 매진, and on the day itself switch_yn '1' swaps to window_remain_count.
Individual bookings are 2~5 people (product_group_code 0101).
"""
import json
import time
from datetime import datetime, timedelta

from common import KST, REQUEST_GAP, day_entry, http, today_kst, wanted

BASE = "https://www.museum.go.kr/ticket_reservation/Web/Book/"
PARAMS = {"shop_code": "102830101202", "product_group_code": "0101"}

INFO = {
    "id": "nmk-kids",
    "name": "국립중앙박물관 어린이박물관",
    "short": "국중박 어린이박물관",
    "bookingUrl": "https://www.museum.go.kr/MUSEUM/contents/M0104010000.do?schM=child&act=intro",
    "note": "개인 2~5명 예약",
    # 홈페이지 안내: "예약은 관람일 14일 전 00시부터 가능"
    "openRule": {"daysBefore": 14, "time": "00:00", "text": "매일 0시에 14일 뒤 날짜 오픈"},
}


def _get(endpoint, **params):
    query = "&".join(f"{k}={v}" for k, v in {**PARAMS, **params}.items())
    return json.loads(http(f"{BASE}{endpoint}?{query}"))["data"]


def _open_dates():
    today = today_kst()
    first_next = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    dates = set()
    for month in (today.strftime("%Y%m"), first_next.strftime("%Y%m")):
        rows = _get("GetBookPlayDate.json", play_month=month).get("bookPlayDateList") or []
        dates.update(r["play_date"] for r in rows if r.get("book_yn") == "1")
        time.sleep(REQUEST_GAP)
    return sorted(dates)


def _sessions(ymd):
    rows = _get("GetBookPlaySequence.json", play_date=ymd).get("bookPlaySequenceList") or []
    now = datetime.now(KST)
    is_today = ymd == now.strftime("%Y%m%d")
    out = []
    for r in rows:
        t = lambda s: f"{s[:2]}:{s[2:4]}"
        remaining = (r.get("window_remain_count") if (is_today and r.get("switch_yn") == "1")
                     else r.get("book_remain_count")) or 0
        if is_today and r.get("sale_time", "9999") <= now.strftime("%H%M"):
            status = "ended"
        elif r.get("book_yn") != "1" or remaining <= 1:
            status = "full"
        else:
            status = "open"
        out.append({
            "no": r.get("play_sequence", len(out) + 1),
            "time": f"{t(r['start_time'])}~{t(r['end_time'])}",
            "remaining": remaining if status == "open" else 0,
            "capacity": None,
            "status": status,
        })
    return out


def fetch(holidays=None):
    holidays = holidays or {}
    today = today_kst()
    days = []
    for ymd in _open_dates():
        d = datetime.strptime(ymd, "%Y%m%d").date()
        keep, name = wanted(d, holidays)
        if d < today or not keep:
            continue
        time.sleep(REQUEST_GAP)
        days.append(day_entry(d, holiday=name, sessions=_sessions(ymd)))
    return {**INFO, "days": days}
