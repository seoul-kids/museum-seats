"""Collect weekend seat availability for every museum and write site/data.json.

Usage: python scraper/scrape.py [--out site/data.json] [--previous URL_OR_PATH]
If a museum fails, its last good data from --previous is kept and marked stale,
so one broken site never blanks the page.
"""
import argparse
import json
import os
import sys
import traceback
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import KST, day_entry, load_holidays, today_kst, wanted  # noqa: E402
from museums import ALL  # noqa: E402

UPCOMING_WEEKS = 3  # also list weekends this far ahead that aren't bookable yet


def load_previous(src):
    if not src:
        return {}
    try:
        if src.startswith("http"):
            with urllib.request.urlopen(src, timeout=15) as r:
                data = json.load(r)
        else:
            with open(src, encoding="utf-8") as f:
                data = json.load(f)
        return {m["id"]: m for m in data.get("museums", [])}
    except Exception as e:
        print(f"[warn] previous data unavailable: {e}")
        return {}


def opens_at(d, rule):
    """When booking for date d opens, as a KST ISO string (None if the rule is unknown)."""
    if not rule:
        return None
    hh, mm = map(int, rule["time"].split(":"))
    t = datetime(d.year, d.month, d.day, hh, mm, tzinfo=KST) - timedelta(days=rule["daysBefore"])
    return t.isoformat(timespec="minutes")


def add_not_open(days, holidays, rule):
    """Append upcoming weekends/holidays that the booking calendar hasn't opened yet."""
    have = {d["date"] for d in days}
    last_open = max(have) if have else ""
    start = today_kst()
    extra = []
    for i in range(UPCOMING_WEEKS * 7):
        d = start + timedelta(days=i)
        keep, name = wanted(d, holidays)
        if keep and d.isoformat() not in have and d.isoformat() > last_open:
            e = day_entry(d, holiday=name, status="notOpen")
            e["opensAt"] = opens_at(d, rule)
            extra.append(e)
    return days + extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "site", "data.json"))
    ap.add_argument("--previous")
    args = ap.parse_args()

    previous = load_previous(args.previous)
    holidays = load_holidays()
    print(f"[info] {len(holidays)} public holidays loaded")
    now = datetime.now(KST).isoformat(timespec="seconds")
    museums = []
    for mod in ALL:
        info = mod.INFO
        try:
            m = mod.fetch(holidays)
            m["days"] = add_not_open(m["days"], holidays, info.get("openRule"))
            m.update(ok=True, checkedAt=now)
            print(f"[ok] {info['name']}: {len(m['days'])} weekend days")
        except Exception as e:
            traceback.print_exc()
            prev = previous.get(info["id"])
            m = {**(prev or {}), **info, "days": (prev or {}).get("days", [])}
            m.update(ok=False, error=f"{type(e).__name__}: {e}")
            m.setdefault("checkedAt", None)
            print(f"[fail] {info['name']}: {e}")
        museums.append(m)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"updatedAt": now, "museums": museums}, f, ensure_ascii=False, indent=1)
    if not any(m["ok"] for m in museums):
        sys.exit(1)


if __name__ == "__main__":
    main()
