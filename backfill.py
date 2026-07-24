#!/usr/bin/env python3
"""
Backfill runner: scrapes every Federal Register business day from START_DATE
through yesterday. Skips dates that already have output files.
Usage: python backfill.py [start_date]   (default start: 2026-06-11)
"""

import sys
import datetime
from scraper import scrape_date

DEFAULT_START = "2026-06-11"


def iter_business_days(start_str):
    start = datetime.date.fromisoformat(start_str)
    today = datetime.date.today()
    current = start
    while current < today:
        if current.weekday() < 5:  # Monday–Friday only
            yield current.isoformat()
        current += datetime.timedelta(days=1)


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_START
    dates = list(iter_business_days(start))
    print(f"Backfilling {len(dates)} business days from {start} to yesterday...")
    for date_str in dates:
        scrape_date(date_str)
    print("Backfill complete.")
