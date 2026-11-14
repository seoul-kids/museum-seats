"""국립민속박물관 어린이박물관 (National Folk Museum of Korea - Children's Museum).

Flow, verified 2026-11-14 without login:
  1. GET selectReserveView.do -> calendar whose bookable days carry
     fn_reservation_load('1','1','YYYYMMDD', dayOfWeek, holiday, weekday)
  2. POST reservationPopup.do with those args -> per-session "잔여 N명".
Only dates linked from the calendar are queried: asking reservationPopup.do about a
date whose booking hasn't opened yet wrongly reports every session as 잔여 60명.
"""
import re
import time
from datetime import date, datetime

from common import REQUEST_GAP, day_entry, http, text, today_kst, wanted

BASE = "https://www.nfm.go.kr"
CALENDAR_URL = BASE + "/kids/nfmkid/exhibition/selectReserveView.do"
CALENDAR_LOAD_URL = BASE + "/kids/nfmkid/exhibition/ResevationCalendarLoad.do"
POPUP_URL = BASE + "/kids/nfmkid/exhibition/reservationPopup.do"

INFO = {
    "id": "nfm-kids",
    "name": "국립민속박물관 어린이박물관",
    "short": "민속 어린이박물관",
    "bookingUrl": CALENDAR_URL,
    "note": "개인 2~9명 예약",
    # 홈페이지 안내: "매일 오전 9시에 2주 내의 예약이 가능" -> date D opens at D-14 09:00
    "openRule": {"daysBefore": 14, "time": "09:00", "text": "매일 오전 9시에 2주 뒤 날짜 오픈"},
}

LOAD_RE = re.compile(
    r"fn_reservation_load\('(\d)',\s*'(\d)',\s*'(\d{8})',\s*'(\d)',\s*'([YN])'\s*,\s*'([YN])'\)"
)
SESSION_RE = re.compile(r"<li>\s*<a([^>]*)>(.*?)</a>\s*</li>", re.S)
SPAN_RE = re.compile(r'<span class="(turn|time|personnel)">(.*?)</span>', re.S)
CREATE_RE = re.compile(r"fn_reservation_create\(([^)]*)\)")


def _open_dates():
    """All bookable dates linked from the calendar (current page + month loader)."""
    found = {}
    pages = [http(CALENDAR_URL)]
    # The month loader is what the page uses for month switching; include it so a booking
    # window spanning two months is still fully covered.
    for mode in ("1", "2"):
        try:
            time.sleep(REQUEST_GAP)
            pages.append(http(CALENDAR_LOAD_URL, {"modeMonth": mode, "hidGrpType": "1"}))
        except Exception:
            pass
    for page in pages:
        for m in LOAD_RE.finditer(page):
            view, grp, ymd, dow, holiday, weekday = m.groups()
            found[ymd] = dict(viewType=view, grpType=grp, eDate=ymd,
                              dayOfWeek=dow, holiday=holiday, weekday=weekday)
    return found


def _sessions(args):
    page = http(POPUP_URL, args)
    ul = page.split('<ul class="info">', 1)
    if len(ul) < 2:
        return []
    out = []
    for attrs, body in SESSION_RE.findall(ul[1].split("</ul>", 1)[0]):
        spans = {k: text(v) for k, v in SPAN_RE.findall(body)}
        no = re.search(r"\d+", spans.get("turn", ""))
        rem = re.search(r"잔여\s*(\d+)", spans.get("personnel", ""))
        cap = None
        c = CREATE_RE.search(attrs)
        if c:
            nums = re.findall(r"'(\d+)'", c.group(1))
            if nums:
                cap = int(nums[-1])
        remaining = int(rem.group(1)) if rem else 0
        if "possible" in attrs and remaining > 0:
            status = "open"
        elif "종료" in spans.get("personnel", ""):
            status = "ended"
        else:
            status = "full"
        out.append({
            "no": int(no.group()) if no else len(out) + 1,
            "time": spans.get("time", "").replace(" ", ""),
            "remaining": remaining if status == "open" else 0,
            "capacity": cap,
            "status": status,
        })
    return out


def fetch(holidays=None):
    holidays = holidays or {}
    today = today_kst()
    days = []
    for ymd, args in sorted(_open_dates().items()):
        d = datetime.strptime(ymd, "%Y%m%d").date()
        if d < today:
            continue
        keep, name = wanted(d, holidays)
        if args["holiday"] == "Y":
            keep, name = True, name or True
        if not keep:
            continue
        time.sleep(REQUEST_GAP)
        days.append(day_entry(d, holiday=name, sessions=_sessions(args)))
    caps = [s["capacity"] for day in days for s in day["sessions"] if s["capacity"]]
    cap = max(caps) if caps else None
    for day in days:
        for s in day["sessions"]:
            s["capacity"] = s["capacity"] or cap
    return {**INFO, "days": days}
