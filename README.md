# Federal Register Scraper

Daily collection of all documents published in the *Federal Register*, the U.S. government's official journal of federal agency rulemaking.

## Quick start

```bash
pip install -r requirements.txt

# Scrape the previous business day
python scraper.py

# Scrape a specific date
python scraper.py 2026-06-15

# Backfill every business day since June 11, 2026
python backfill.py
```

Output files land in `data/fed_register_YYYY-MM-DD.json`. Dates already present are skipped automatically, so reruns are safe.

## GitHub Actions

Two triggers are configured in `.github/workflows/scrape.yml`:

- **Scheduled**: runs automatically at 6 AM ET on every weekday.
- **Manual dispatch**: choose `daily`, `specific` (enter a date), or `backfill` from the GitHub Actions UI.

Scraped data is committed back to the repo automatically after each run.

---

## Methodology

### Scope

This scraper collects all documents published in the *Federal Register* starting June 11, 2026, and running forward on each weekday. Coverage includes all four document types — Rules, Proposed Rules, Notices, and Presidential Documents — across all federal agencies, with no subject-matter or geographic filter. The unit of observation is the individual document as published in a daily issue.

### Technique

Documents are retrieved exclusively through the [Federal Register public API](https://www.federalregister.gov/developers/api/v1) (v1), the official, rate-tolerant endpoint provided by the Office of the Federal Register. Using the API rather than parsing navigation HTML is both more reliable and explicitly sanctioned for programmatic access.

To minimize server load, the scraper waits one full second between each individual document body request and 0.5 seconds between API listing pages. No document is re-fetched if a local output file for that date already exists, making all reruns fully idempotent — a critical property for the GitHub Actions environment where network failures can cause partial runs.

### Data Integrity

Per document, the scraper captures: `document_number`, `title`, `type`, `subtype`, `abstract`, `action`, `publication_date`, `effective_on`, `dates`, `comment_url`, `comments_close_on`, `agencies`, `docket_numbers`, `regulation_id_number_info`, `html_url`, `pdf_url`, `public_inspection_pdf_url`, `excerpts`, `body_html_url`, `page_views`, and `full_text` (plain text extracted from the body HTML via BeautifulSoup). Documents without a `body_html_url` (some notice types) store `full_text: null` explicitly rather than omitting the field, preserving schema consistency across all records. Body-fetch failures are printed to the run log without aborting the run; the API-supplied metadata is still written for that document.

### Analysis

Key dimensions for longitudinal tracking: document-type composition over time (Rules vs. Proposed Rules vs. Notices), per-agency publication frequency and rank order, regulatory action density by week and quarter, proposed-rule-to-final-rule pipeline timing, and comment-period clustering. These support trend, seasonal, and outlier analysis as data accumulates across the collection period.
