"""서울물재생체험관 개인 전시관람 (reserv.tfunkorea.co.kr, companyCode SWR / A101 / B101).

Verified 2026-11-14, no login:
  POST /company/selectBlockDateListToPossible -> possibleDateList: every bookable date with
       its own openYMD + openTime (when booking for that date opened)
  POST /company/selectScheduleEntTime         -> HTML <option>s:
       value "01/1회/10:00/12:00/<seats left>"
Museum rule: "매주 금요일 14시에 7일치 예약이 추가 오픈, 예약 가능 기간은 항상 4주".
The batch for a Tue~Sun week opens on the Friday 25 days before that Tuesday, 14:00
(e.g. 12/8~12/13 opened 11/13 14:00), which is used to label weekends not open yet.
"""
import json
import re
import time
from datetime import datetime, timedelta

from common import KST, REQUEST_GAP, day_entry, http, today_kst, wanted

BASE = "https://reserv.tfunkorea.co.kr"
CODES = {"companyCode": "SWR", "productGroupCode": "A101", "productCode": "B101"}
TIME_JSP = "t-fun/sale/indivimall/swr/ajax/tfun-sale-productScheduleTimeListAjax"
OPTION_RE = re.compile(r'<option value="(\d+)/([^/"]*)/(\d{2}:\d{2})/(\d{2}:\d{2})/(\d+)"')
UPCOMING_NOT_OPEN = 2  # weekends to preview past the open window

INFO = {
    "id": "swr",
    "name": "서울물재생체험관",
    "short": "물재생체험관",
    "tab": "물재생",
    "bookingUrl": BASE + "/sale/siteDetail/SWR?indivimall=swr",
    "note": "개인 1~9명 예약 (보호자 포함) · 월요일 휴관",
    "openRule": {"text": "매주 금요일 오후 2시에 다음 1주 치 오픈 (항상 4주 앞까지)"},
}


def _opens_at(d):
    tuesday = d - timedelta(days=(d.weekday() - 1) % 7)
    t = tuesday - timedelta(days=25)
    return datetime(t.year, t.month, t.day, 14, 0, tzinfo=KST)


def _sessions(d):
    page = http(BASE + "/company/selectScheduleEntTime", {
        **CODES, "jsp": TIME_JSP,
        "scheduleDateFrom": d.isoformat(), "scheduleDateTo": d.isoformat()})
    now = datetime.now(KST)
    out = []
    for code, name, start, end, left in OPTION_RE.findall(page):
        left = int(left)
        if d == now.date() and start <= now.strftime("%H:%M"):
            status = "ended"
        else:
            status = "open" if left > 0 else "full"
        out.append({"no": int(code), "time": f"{start}~{end}",
                    "remaining": left if status == "open" else 0,
                    "capacity": None, "status": status})
    return out


def fetch(holidays=None):
    holidays = holidays or {}
    today = today_kst()
    now = datetime.now(KST)
    raw = http(BASE + "/company/selectBlockDateListToPossible", CODES)
    possible = {}
    for r in json.loads(raw).get("possibleDateList") or []:
        d = datetime.strptime(r["blockThisDate"], "%Y-%m-%d").date()
        if d >= today:
            o = r.get("openYMD") or "19700101"
            t = (r.get("openTime") or "0000").ljust(4, "0")
            possible[d] = datetime(int(o[:4]), int(o[4:6]), int(o[6:]),
                                   int(t[:2]), int(t[2:]), tzinfo=KST)

    days = []
    last = max(possible) if possible else today
    for i in range((last - today).days + 1):
        d = today + timedelta(days=i)
        keep, name = wanted(d, holidays)
        if not keep:
            continue
        if d not in possible:
            days.append(day_entry(d, holiday=name, status="closed"))
            continue
        if possible[d] > now:
            e = day_entry(d, holiday=name, status="notOpen")
            e["opensAt"] = possible[d].isoformat(timespec="minutes")
            days.append(e)
            continue
        time.sleep(REQUEST_GAP)
        days.append(day_entry(d, holiday=name, sessions=_sessions(d)))

    # Preview the next weekends that the Friday release hasn't reached yet.
    d, added = last + timedelta(days=1), 0
    while added < UPCOMING_NOT_OPEN * 2 and d <= last + timedelta(days=21):
        keep, name = wanted(d, holidays)
        if keep and d.weekday() != 0:
            e = day_entry(d, holiday=name, status="notOpen")
            e["opensAt"] = _opens_at(d).isoformat(timespec="minutes")
            days.append(e)
            added += 1
        d += timedelta(days=1)
    return {**INFO, "days": days}
