"""
5paisa FII/DII (Cash segment) Daily Scraper
--------------------------------------------
Fetches the FII/DII Cash-segment table from:
    https://www.5paisa.com/share-market-today/fii-dii-data

and appends any NEW trading-day rows to a local CSV file
(fii_dii_cash_history.csv), skipping dates already saved.

Because the page shows the whole current month, running this once a day
(or even skipping a day) is safe -- it will simply pick up any dates it
doesn't already have, so it "self-heals" if a scheduled run is missed.

Run manually:
    python fii_dii_scraper.py

Schedule it daily using Windows Task Scheduler (see README.txt).
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
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fii_dii_cash_history.csv")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.log")

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def clean_number(text: str):
    """Convert '3,623.50' -> 3623.50 ; '-1,864.00' -> -1864.00"""
    text = text.strip().replace(",", "")
    if text in ("", "-", "--", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def extract_cash_rows(html: str):
    """
    The page repeats each date 5 times in a row (Cash, F&O-Index, F&O-Stock,
    MF Equity/Debt, FII SEBI). The FIRST occurrence of each date in table
    order is the Cash-segment row, which is what we want.
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        raise RuntimeError("No <table> elements found on the page - site layout may have changed.")

    # The first table on the page is the "current month" live table.
    table = tables[0]
    rows = table.find_all("tr")

    results = []
    last_date = None

    for tr in rows:
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        first_cell = cells[0]

        if not DATE_RE.match(first_cell):
            continue  # skip header rows / "Month till date" summary rows

        if first_cell == last_date:
            continue  # this is F&O / MF / FII-SEBI row for a date we already captured

        last_date = first_cell

        # Expect: [Date, FII GP, FII GS, FII Net, DII GP, DII GS, DII Net]
        if len(cells) < 7:
            log.warning("Row for %s has unexpected number of columns (%d): %s", first_cell, len(cells), cells)
            continue

        nums = [clean_number(c) for c in cells[1:7]]
        if any(n is None for n in nums):
            log.warning("Could not parse numbers for %s: %s", first_cell, cells[1:7])
            continue

        try:
            iso_date = datetime.strptime(first_cell, "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            log.warning("Could not parse date: %s", first_cell)
            continue

        results.append([iso_date] + nums)

    return results


def load_existing_dates():
    if not os.path.exists(CSV_FILE):
        return set()
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["Date"] for row in reader}


def append_new_rows(rows):
    existing_dates = load_existing_dates()
    new_rows = [r for r in rows if r[0] not in existing_dates]

    if not new_rows:
        log.info("No new dates to add. CSV is already up to date.")
        return 0

    write_header = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_COLUMNS)
        # keep chronological order (oldest first) within the new batch
        for row in sorted(new_rows, key=lambda r: r[0]):
            writer.writerow(row)

    log.info("Added %d new row(s): %s", len(new_rows), [r[0] for r in sorted(new_rows, key=lambda r: r[0])])
    return len(new_rows)


def main():
    log.info("Starting FII/DII cash-segment scrape...")
    try:
        html = fetch_html()
        rows = extract_cash_rows(html)
        log.info("Parsed %d date rows from page (current month table).", len(rows))
        if not rows:
            log.error("Zero rows parsed - the site's HTML structure may have changed. "
                       "Open the page manually and check the table.")
            return
        append_new_rows(rows)
    except requests.RequestException as e:
        log.error("Network/HTTP error while fetching page: %s", e)
    except Exception as e:
        log.exception("Unexpected error: %s", e)


if __name__ == "__main__":
    main()
