#!/usr/bin/env python3
"""
Federal Register daily document scraper.
Fetches all documents published on a given date via the official public API.
Run with a date argument (YYYY-MM-DD) or no argument to scrape the previous business day.

Outputs per date:
  data/fed_register_YYYY-MM-DD.json   — full document records including body text
  data/fed_register_YYYY-MM-DD.csv    — flat table of key fields (no full_text), easy to open in Excel
  data/summaries/YYYY-MM-DD.json      — aggregate counts by type and agency for longitudinal tracking
"""

import os
import sys
import csv
import json
import datetime
import time
import collections
import requests
from bs4 import BeautifulSoup

API_BASE = "https://www.federalregister.gov/api/v1/documents.json"

HEADERS = {
    "User-Agent": "FedRegister-Academic-Scraper/1.0 (columbia.edu journalism research; contact: kjc2184@columbia.edu)"
}

FIELDS = [
    "document_number",
    "title",
    "type",
    "abstract",
    "action",
    "publication_date",
    "effective_on",
    "dates",
    "comments_close_on",
    "agencies",
    "docket_ids",
    "html_url",
    "pdf_url",
    "public_inspection_pdf_url",
    "excerpts",
    "body_html_url",
]

# Columns written to the CSV — excludes full_text (too large) and nested objects
CSV_COLUMNS = [
    "document_number",
    "title",
    "type",
    "action",
    "publication_date",
    "effective_on",
    "comments_close_on",
    "agencies",
    "docket_ids",
    "html_url",
    "pdf_url",
    "has_full_text",
]


def fetch_document_listing(date_str):
    """Page through the API and return all document records for the given date."""
    docs = []
    page = 1
    while True:
        params = {
            "per_page": 200,
            "page": page,
            "order": "document_number",
            "conditions[publication_date][is]": date_str,
            "fields[]": FIELDS,
        }
        resp = requests.get(API_BASE, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("results", [])
        if not batch:
            break
        docs.extend(batch)
        print(f"    page {page}: {len(batch)} docs (running total: {len(docs)})")
        if page >= payload.get("total_pages", 1):
            break
        page += 1
        time.sleep(0.5)
    return docs


def fetch_body_text(url):
    """Fetch a document's body HTML and return clean plain text."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as exc:
        print(f"      warning: body fetch failed ({exc})")
        return None


def write_csv(docs, path):
    """Write a flat CSV of key fields — no full_text, nested lists joined as semicolons."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for doc in docs:
            agencies = "; ".join(
                a.get("name", "") for a in doc.get("agencies", [])
            )
            dockets = "; ".join(doc.get("docket_ids") or [])
            writer.writerow({
                "document_number":  doc.get("document_number"),
                "title":            doc.get("title"),
                "type":             doc.get("type"),
                "action":           doc.get("action"),
                "publication_date": doc.get("publication_date"),
                "effective_on":     doc.get("effective_on"),
                "comments_close_on": doc.get("comments_close_on"),
                "agencies":         agencies,
                "docket_ids":       dockets,
                "html_url":         doc.get("html_url"),
                "pdf_url":          doc.get("pdf_url"),
                "has_full_text":    doc.get("full_text") is not None,
            })


def build_summary(date_str, docs):
    """
    Aggregate counts for longitudinal tracking — returned as a dict.
    Captures what the full JSON files capture but without loading them.
    """
    type_counts = collections.Counter(d.get("type") for d in docs)
    agency_counts = collections.Counter()
    for doc in docs:
        for agency in doc.get("agencies", []):
            name = agency.get("name")
            if name:
                agency_counts[name] += 1

    return {
        "date": date_str,
        "total_documents": len(docs),
        "by_type": dict(type_counts.most_common()),
        "top_agencies": [
            {"agency": name, "count": count}
            for name, count in agency_counts.most_common(15)
        ],
        "with_effective_date": sum(1 for d in docs if d.get("effective_on")),
        "with_comment_deadline": sum(1 for d in docs if d.get("comments_close_on")),
        "body_text_fetched": sum(1 for d in docs if d.get("full_text") is not None),
    }


def scrape_date(date_str, output_dir="data"):
    """
    Scrape all Federal Register documents published on date_str.
    Skips if the JSON output already exists (idempotent reruns).
    Writes: JSON, CSV, and a summary file.
    """
    json_path = os.path.join(output_dir, f"fed_register_{date_str}.json")
    if os.path.exists(json_path):
        print(f"[{date_str}] already scraped — skipping.")
        return

    print(f"[{date_str}] fetching document listing...")
    docs = fetch_document_listing(date_str)

    if not docs:
        print(f"[{date_str}] no documents (non-publication day or holiday).")
        return

    print(f"[{date_str}] {len(docs)} documents — fetching body text (1 req/sec)...")

    for i, doc in enumerate(docs, 1):
        doc_num = doc.get("document_number", "?")
        body_url = doc.get("body_html_url")
        if body_url:
            print(f"  [{i}/{len(docs)}] {doc_num}")
            doc["full_text"] = fetch_body_text(body_url)
            time.sleep(1)
        else:
            doc["full_text"] = None

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "summaries"), exist_ok=True)

    csv_path = os.path.join(output_dir, f"fed_register_{date_str}.csv")
    summary_path = os.path.join(output_dir, "summaries", f"{date_str}.json")

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(docs, fh, indent=2, ensure_ascii=False)

    write_csv(docs, csv_path)

    summary = build_summary(date_str, docs)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    errors = sum(1 for d in docs if d.get("body_html_url") and d.get("full_text") is None)
    print(f"[{date_str}] done — {len(docs)} docs | JSON + CSV written"
          + (f" | {errors} body-fetch errors" if errors else ""))


def prev_business_day():
    """Return the most recent completed business day."""
    today = datetime.date.today()
    days_back = 1
    while True:
        candidate = today - datetime.timedelta(days=days_back)
        if candidate.weekday() < 5:
            return candidate.isoformat()
        days_back += 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else prev_business_day()
    scrape_date(target)
