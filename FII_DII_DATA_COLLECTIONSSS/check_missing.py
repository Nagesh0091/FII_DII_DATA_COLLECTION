"""
Missing-day alarm.

Exits with code 1 (so GitHub emails you) if a recent weekday that is not in
nse_holidays.txt has no row in fii_dii_cash_history.csv.

Looks back LOOKBACK_DAYS days. Today only counts after 19:00 IST.
"""

import csv
import os
import sys
from datetime import date, datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "fii_dii_cash_history.csv")
HOLIDAY_FILE = os.path.join(BASE_DIR, "nse_holidays.txt")
LOOKBACK_DAYS = 10
IST = timezone(timedelta(hours=5, minutes=30))


def read_holidays():
    days = set()
    if os.path.exists(HOLIDAY_FILE):
        with open(HOLIDAY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    days.add(date.fromisoformat(line.split()[0]))
                except ValueError:
                    print(f"WARNING: ignoring bad holiday line: {line}")
    return days


def read_csv_dates():
    if not os.path.exists(CSV_FILE):
        return set()
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        return {date.fromisoformat(r["Date"]) for r in csv.DictReader(f)}


def main() -> int:
    have = read_csv_dates()
    if not have:
        print("CSV is empty or missing - nothing to check.")
        return 1
    holidays = read_holidays()
    now = datetime.now(IST)
    today = now.date()
    start = max(today - timedelta(days=LOOKBACK_DAYS), min(have))

    missing, d = [], start
    while d <= today:
        is_weekday = d.weekday() < 5
        too_early = d == today and now.hour < 19
        if is_weekday and d not in holidays and d not in have and not too_early:
            missing.append(d)
        d += timedelta(days=1)

    if missing:
        print("MISSING trading-day data for: " + ", ".join(x.isoformat() for x in missing))
        print("If any of these were market holidays, add them to nse_holidays.txt.")
        print("Month-end reminder: the page only shows the current month.")
        return 1
    print(f"OK - no missing weekdays in the last {LOOKBACK_DAYS} days (latest row: {max(have)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
