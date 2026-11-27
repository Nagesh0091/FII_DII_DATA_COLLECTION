"""
5paisa FII/DII (Cash segment) Daily Scraper
--------------------------------------------
Fetches the FII/DII Cash-segment table from:
    https://www.5paisa.com/share-market-today/fii-dii-data

and keeps fii_dii_cash_history.csv up to date:
  * new trading days are added
  * existing days are UPDATED if the site later shows different numbers
  * rows that fail sanity checks are skipped and reported (exit code 1)

The page only shows the CURRENT month, so run it several times on the last
days of a month (the workflow does this) - a day missed across a month
rollover cannot be recovered.
"""

import csv
import logging
import os
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://www.5paisa.com/share-market-today/fii-dii-data"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "fii_dii_cash_history.csv")
LOG_FILE = os.path.join(BASE_DIR, "scraper.log")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

DATE_RE = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$")  # e.g. 30-Jul-2026

CSV_COLUMNS = [
    "Date",
    "FII_Gross_Purchase_Cr",
    "FII_Gross_Sales_Cr",
    "FII_Net_Cr",
    "DII_Gross_Purchase_Cr",
    "DII_Gross_Sales_Cr",
    "DII_Net_Cr",
]

NET_TOLERANCE = 0.15       # Cr; site rounds each figure to 1 decimal
MAX_GROSS = 200000.0       # Cr; anything above this is surely a parsing error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def fetch_html() -> str:
    last_err = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(URL, headers=HEADERS, timeout=30)
            log.info("HTTP status: %s (attempt %d)", resp.status_code, attempt)
            if resp.status_code != 200:
                log.error("Non-200 response. First 500 chars:\n%s", resp.text[:500])
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            log.warning("Fetch attempt %d failed: %s", attempt, e)
    raise last_err


def clean_number(text: str):
    """Convert '3,623.50' -> 3623.50 ; '-1,864.00' -> -1864.00"""
    text = text.strip().replace(",", "")
    if text in ("", "-", "--", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def validate_row(iso_date, nums):
    """Return an error string if the row looks wrong, else None."""
    fgp, fgs, fnet, dgp, dgs, dnet = nums
    if min(fgp, fgs, dgp, dgs) < 0:
        return "negative gross purchase/sales value"
    if max(fgp, fgs, dgp, dgs) > MAX_GROSS:
        return "implausibly large gross value"
    if abs(fgp - fgs - fnet) > NET_TOLERANCE:
        return f"FII net {fnet} != purchase-sales {fgp - fgs:.1f}"
    if abs(dgp - dgs - dnet) > NET_TOLERANCE:
        return f"DII net {dnet} != purchase-sales {dgp - dgs:.1f}"
    return None


def extract_cash_rows(html: str):
    """
    The page repeats each date 5 times (Cash, F&O-Index, F&O-Stock,
    MF Equity/Debt, FII SEBI). The FIRST occurrence of each date in table
    order is the Cash-segment row. Returns (rows, rejected_count).
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        log.error("No <table> found. First 800 chars of HTML:\n%s", html[:800])
        raise RuntimeError(
            "No <table> elements found - site layout changed or request was blocked."
        )

    results, seen, rejected = [], set(), 0

    for tr in tables[0].find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or not DATE_RE.match(cells[0]):
            continue  # header / "Month till date" rows

        date_text = cells[0]
        if date_text in seen:
            continue  # F&O / MF / SEBI row of a date already captured
        seen.add(date_text)

        if len(cells) < 7:
            log.warning("Row %s has %d columns, expected 7: %s", date_text, len(cells), cells)
            rejected += 1
            continue

        nums = [clean_number(c) for c in cells[1:7]]
        if any(n is None for n in nums):
            log.warning("Could not parse numbers for %s: %s", date_text, cells[1:7])
            rejected += 1
            continue

        try:
            iso_date = datetime.strptime(date_text, "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            log.warning("Could not parse date: %s", date_text)
            rejected += 1
            continue

        problem = validate_row(iso_date, nums)
        if problem:
            log.warning("REJECTED %s: %s | %s", iso_date, problem, cells[1:7])
            rejected += 1
            continue

        results.append([iso_date] + nums)

    return results, rejected


def load_existing():
    """Return {date: [6 floats]} from the CSV (empty if no file)."""
    data = {}
    if not os.path.exists(CSV_FILE):
        return data
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data[row["Date"]] = [float(row[c]) for c in CSV_COLUMNS[1:]]
    return data


def save_all(data):
    """Rewrite the CSV, sorted oldest-first."""
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for d in sorted(data):
            writer.writerow([d] + data[d])


def merge_rows(rows):
    data = load_existing()
    added, updated = [], []
    for r in rows:
        d, nums = r[0], r[1:]
        if d not in data:
            data[d] = nums
            added.append(d)
        elif any(abs(a - b) > 1e-9 for a, b in zip(data[d], nums)):
            log.warning("UPDATED %s: old=%s new=%s", d, data[d], nums)
            data[d] = nums
            updated.append(d)

    if added or updated:
        save_all(data)
    if added:
        log.info("Added %d new row(s): %s", len(added), sorted(added))
    if updated:
        log.info("Updated %d existing row(s): %s", len(updated), sorted(updated))
    if not added and not updated:
        log.info("No new or changed dates. CSV is already up to date.")
    return len(added), len(updated)


def main() -> int:
    log.info("Starting FII/DII cash-segment scrape...")
    try:
        html = fetch_html()
        rows, rejected = extract_cash_rows(html)
        log.info("Parsed %d valid date rows (%d rejected).", len(rows), rejected)
        if not rows and not rejected:
            log.info("No dated rows in the current month's table yet. Normal in the "
                     "first day or two of a month. Nothing to add - not an error.")
            return 0
        if rows:
            merge_rows(rows)
        if rejected:
            log.error("%d row(s) failed validation - the site layout may have changed.", rejected)
            return 1
        return 0
    except requests.RequestException as e:
        log.error("Network/HTTP error while fetching page: %s", e)
        return 1
    except Exception as e:
        log.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
