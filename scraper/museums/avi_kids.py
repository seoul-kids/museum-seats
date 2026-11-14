"""국립항공박물관 어린이공항 체험 (National Aviation Museum - Children's Airport, gcode4).

Verified 2026-11-14, no login. The reservation page calls:
  POST /todayData.do  today=YYYYMMDD, gcode=gcode4, pcontrol=1
which returns rows for every bookable date from today up to the requested date
(currently ~15 days ahead), each with moon_ss_remain / moon_ss_total.
moon_ss_remain is seats LEFT: far-off sessions read 15/15, near ones fewer, and on the
day itself online seats drop to 0 at 10:00 when they convert to on-site tickets.
Only children (48 months ~ preschool) take part, so availability is per child.
"""
import json
import time
from datetime import datetime, timedelta

from common import KST, REQUEST_GAP, day_entry, http, today_kst, wanted

DATA_URL = "https://www.aviation.or.kr/todayData.do"
GCODE = "gcode4"

INFO = {
    "id": "avi-kids",
    "name": "국립항공박물관 어린이공항",
    "short": "항공박물관 어린이공항",
    "tab": "항공",
    "bookingUrl": "https://aviation.moonhwain.net:451/rsvc/rsv_pm.html?lang=kr&b_id=aviation&stk_idx=5",
    "note": "48개월~미취학 아동만 체험 (보호자는 대기) · 유료 · 당일 10시부터 남은 자리는 현장 발권",
    "partyType": "kids",  # seats needed = number of children, not the whole family
    "openRule": {"text": "약 2주 뒤까지 예약 가능 (오픈 시각 안내 없음)"},
}


def fetch(holidays=None):
    holidays = holidays or {}
    today = today_kst()
    rows = []
    # One call returns every open date up to `today`; ask a month ahead to get them all.
    for target in (today + timedelta(days=31), today):
        raw = http(DATA_URL, {"today": target.strftime("%Y%m%d"), "gcode": GCODE, "pcontrol": "1"})
        data = json.loads(raw)
        if str(data.get("resultCode")) != "1":
            raise RuntimeError(f"unexpected resultCode {data.get('resultCode')}")
        rows += data.get("dataList") or []
        time.sleep(REQUEST_GAP)

    now = datetime.now(KST)
    by_date = {}
    for r in rows:
        by_date.setdefault(r["moon_ss_date"], {})[r.get("moon_ss_timeNo") or r["moon_ss_time"]] = r

    days = []
    for ymd, sessions_by_no in sorted(by_date.items()):
        d = datetime.strptime(ymd, "%Y-%m-%d").date()
        keep, name = wanted(d, holidays)
        if d < today or not keep:
            continue
        sessions = []
        for r in sorted(sessions_by_no.values(), key=lambda r: r["moon_ss_time"]):
            remaining = int(r.get("moon_ss_remain") or 0)
            total = int(r.get("moon_ss_total") or 0)
            if d == today and r["moon_ss_time"] <= now.strftime("%H:%M"):
                status = "ended"
            elif remaining <= 0:
                status = "full"
            else:
                status = "open"
            sessions.append({
                "no": len(sessions) + 1,
                "time": f"{r['moon_ss_time']}~{r.get('moon_ss_timeE', '')}",
                "remaining": remaining if status == "open" else 0,
                "capacity": total or None,
                "status": status,
            })
        days.append(day_entry(d, holiday=name, sessions=sessions))
    return {**INFO, "days": days}
