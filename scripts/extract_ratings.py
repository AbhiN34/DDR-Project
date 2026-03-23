#!/usr/bin/env python3
"""
Extract debt distress risk ratings from IMF/World Bank DSA PDFs.

Downloads PDFs listed in dsa_links_collected.csv, validates document years,
and extracts External and Overall risk ratings using regex pattern matching.

Usage:
    # Process all countries:
    python scripts/extract_ratings.py

    # Process a specific batch of countries:
    python scripts/extract_ratings.py --countries "Cameroon,Chad,Comoros"

    # Process an alphabetical range:
    python scripts/extract_ratings.py --range "Cameroon:Papua New Guinea"

Outputs:
    data/extracted_ratings.csv       Detailed per-document results
    data/extracted_wide.csv          Wide-format (one row per country, year columns)
    data/extracted_evidence.txt      Source text evidence organized by year
"""

import argparse
import os
import re
import sys
import time
import hashlib
import pandas as pd
import requests
import pdfplumber
import fitz  # PyMuPDF — fallback for PDFs where pdfplumber fails

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(REPO_ROOT, "data", "dsa_links_collected.csv")
PDF_CACHE = os.path.join(REPO_ROOT, ".pdf_cache")
YEARS = list(range(2005, 2026))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36"
    )
}


# ---------------------------------------------------------------------------
# Country selection
# ---------------------------------------------------------------------------

def select_countries(df, args):
    """Return a sorted list of countries to process based on CLI args."""
    all_countries = sorted(df["Country"].unique())

    if args.countries:
        requested = [c.strip() for c in args.countries.split(",")]
        return sorted(c for c in requested if c in all_countries)

    if args.range:
        start, end = [s.strip() for s in args.range.split(":")]
        start_idx = all_countries.index(start)
        end_idx = all_countries.index(end)
        return all_countries[start_idx : end_idx + 1]

    return all_countries


# ---------------------------------------------------------------------------
# PDF downloading
# ---------------------------------------------------------------------------

def download_pdf(url, retries=1, backoff=5):
    """Download a PDF with retry logic and local caching.

    Returns (filepath, success, note).
    """
    filename = hashlib.md5(url.encode()).hexdigest() + ".pdf"
    filepath = os.path.join(PDF_CACHE, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filepath, True, "cached"

    for attempt in range(1 + retries):
        try:
            resp = requests.get(
                url, headers=HEADERS, timeout=60, allow_redirects=True
            )
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return filepath, True, f"HTTP {resp.status_code}"
            note = f"HTTP {resp.status_code}, size={len(resp.content)}"
        except Exception as e:
            note = str(e)

        if attempt < retries:
            time.sleep(backoff)

    return None, False, note


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_pdfplumber(filepath):
    """Extract text using pdfplumber (best for natively digital PDFs)."""
    text = ""
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        pass
    return text


def extract_text_pymupdf(filepath):
    """Extract text using PyMuPDF (handles older/scanned PDFs better).

    PyMuPDF uses a different text extraction engine that is more tolerant of
    non-standard PDF encoding and malformed text layers, which is common in
    older World Bank documents.
    """
    text = ""
    try:
        doc = fitz.open(filepath)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception:
        pass
    return text


def extract_text(filepath):
    """Try pdfplumber first; fall back to PyMuPDF if text is too short."""
    text = extract_text_pdfplumber(filepath)
    if len(text.strip()) < 100:
        text = extract_text_pymupdf(filepath)
    return text


def extract_early_pages(filepath, num_pages=3):
    """Extract text from the first few pages (used for year detection)."""
    pages_plumber, pages_mupdf = [], []

    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:num_pages]:
                pages_plumber.append(page.extract_text() or "")
    except Exception:
        pass

    try:
        doc = fitz.open(filepath)
        for i in range(min(num_pages, len(doc))):
            pages_mupdf.append(doc[i].get_text())
        doc.close()
    except Exception:
        pass

    if pages_plumber and len(pages_plumber[0].strip()) > 200:
        return pages_plumber
    if pages_mupdf:
        return pages_mupdf
    return pages_plumber or []


# ---------------------------------------------------------------------------
# Year detection & validation
# ---------------------------------------------------------------------------

def detect_document_year(pages_text):
    """Detect the year a DSA document covers from its first few pages.

    Checks (in priority order):
      1. Article IV year in title (e.g. "STAFF REPORT FOR THE 2012 ARTICLE IV")
      2. Update year in title (e.g. "2013 Update")
      3. Publication date (e.g. "June 5, 2008")

    Returns (year_string, detection_method) or (None, None).
    """
    header_text = ""
    for page in pages_text:
        lines = page.split("\n")
        header_text += "\n".join(lines[:40]) + "\n"

    # Full date: "June 5, 2008"
    date_match = re.search(
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+(\d{4})",
        header_text,
    )
    if not date_match:
        # Month + year only: "October 2020"
        date_match = re.search(
            r"(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+(\d{4})",
            header_text,
        )

    article_iv = re.search(
        r"STAFF\s+REPORT\s+FOR\s+THE\s+(\d{4})\s+ARTICLE\s+IV",
        header_text,
        re.IGNORECASE,
    )

    title_year = re.search(
        r"(?:DSA|Analysis)\s*[-:]\s*(?:\w+\s+)?(\d{4})\s+Update",
        header_text,
        re.IGNORECASE,
    )
    if not title_year:
        title_year = re.search(
            r"(?:Second|First|Third)?\s*(\d{4})\s+Update",
            header_text,
            re.IGNORECASE,
        )

    candidates = []
    if article_iv:
        candidates.append(("article_iv", article_iv.group(1)))
    if title_year:
        candidates.append(("title_year", title_year.group(1)))
    if date_match:
        candidates.append(("pub_date", date_match.group(1)))

    if candidates:
        return candidates[0][1], candidates[0][0]
    return None, None


def check_year_match(pages_text, listed_year):
    """Check if the document's detected year matches the year listed in the CSV."""
    doc_year, method = detect_document_year(pages_text)
    if doc_year is None:
        return "unclear", None, "could not detect document year"
    if str(listed_year) == doc_year:
        return "yes", doc_year, f"matched via {method}"
    return (
        "no",
        doc_year,
        f"document is from {doc_year} (via {method}), listed as {listed_year}",
    )


# ---------------------------------------------------------------------------
# Risk-rating extraction
# ---------------------------------------------------------------------------

def get_surrounding_sentence(text_lower, match):
    """Extract ~1 sentence of context around a regex match."""
    start = max(0, match.start() - 80)
    end = min(len(text_lower), match.end() + 80)
    snippet = text_lower[start:end].strip()
    dot_before = snippet.rfind(".", 0, match.start() - start)
    if dot_before >= 0:
        snippet = snippet[dot_before + 1 :].strip()
    dot_after = snippet.find(".", match.end() - start)
    if dot_after >= 0:
        snippet = snippet[: dot_after + 1].strip()
    return snippet


def extract_risk_ratings(text):
    """Extract External and Overall debt distress risk ratings from PDF text.

    How External vs. Overall is determined:
      - Patterns containing "external debt distress" → External rating
      - Patterns containing "overall risk of debt distress" → Overall rating
      - Pre-2012 DSAs used a single "risk of debt distress" without qualifier;
        this is mapped to External (the Overall concept was introduced in 2012
        with the revised LIC Debt Sustainability Framework)

    Rating scale: Low, Moderate, High, In Debt Distress

    Returns (external_risk, overall_risk, external_sentence, overall_sentence).
    """
    normalized = re.sub(r"\s+", " ", text)
    text_lower = normalized.lower()

    ratings = r"(low|moderate|high|in\s+debt\s+distress)"
    qratings = r'["\u201c]?(low|moderate|high|in\s+debt\s+distress)["\u201d]?'

    # --- External risk patterns (most specific → least specific) ---
    external_patterns = [
        rf"risk\s+of\s+external\s+debt\s+distress\s*[:\.\s]\s*{ratings}",
        rf"risk\s+of\s+external\s+debt\s+distress\s+(?:is|remains|has\s+been\s+assessed\s+as|has\s+been\s+rated|increased\s+.*?to)\s+{qratings}",
        rf"at\s+{ratings}\s+risk\s+of\s+external\s+(?:and\s+overall\s+(?:public\s+)?)?debt\s+distress",
        rf"external\s+debt\s+distress\s+risk\s*[:\.\s]\s*{ratings}",
        rf"external\s+debt\s+remains\s+at\s+a?\s*{ratings}\s+risk\s+of\s+debt\s+distress",
        rf"external\s+debt\s+distress\s+(?:is|remains)\s+{ratings}",
        rf"external\s+risk\s+of\s+debt\s+distress\s+(?:is|remains)\s+{ratings}",
        rf"external\s+debt\s+indicators.*?risk\s+of\s+debt\s+distress\s+(?:in\s+\w+\s+)?remains\s+{ratings}",
    ]

    # --- Overall risk patterns ---
    overall_patterns = [
        rf"overall\s+risk\s+of\s+(?:public\s+)?debt\s+distress\s*[:\.\s]\s*{ratings}",
        rf"overall\s+risk\s+of\s+(?:public\s+)?debt\s+distress\s+(?:is|remains|has\s+been\s+assessed\s+as)\s+{ratings}",
        rf"at\s+{ratings}\s+risk\s+of\s+external\s+and\s+overall\s+(?:public\s+)?debt\s+distress",
        rf"risk\s+of\s+total\s+(?:public\s+)?debt\s+distress\s+(?:is\s+(?:also\s+)?|remains\s+){qratings}",
        rf"overall\s+(?:public\s+)?debt\s+distress\s+risk\s*[:\.\s]\s*{ratings}",
        rf"overall\s+risk\s+rating\s*[:\.\s]\s*{ratings}",
    ]

    # --- Generic patterns for pre-2012 DSAs (maps to External) ---
    generic_patterns = [
        rf"risk\s+of\s+debt\s+distress\s+(?:in\s+\w+\s+)?(?:is|remains)\s+{ratings}",
        rf"face\s+a\s+{ratings}\s+risk\s+of\s+debt\s+distress",
        rf"continues?\s+to\s+face\s+a\s+{ratings}\s+risk\s+of\s+debt\s+distress",
        rf"(?:debt\s+)?distress\s+remains\s+{ratings}",
    ]

    def search_patterns(patterns):
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                rating = match.group(1).strip().title()
                if "debt distress" in rating.lower():
                    rating = "In Debt Distress"
                sentence = get_surrounding_sentence(text_lower, match)
                return rating, sentence
        return "", ""

    external_risk, external_sentence = search_patterns(external_patterns)
    overall_risk, overall_sentence = search_patterns(overall_patterns)

    # Fall back to generic patterns for pre-2012 DSAs
    if not external_risk and not overall_risk:
        external_risk, external_sentence = search_patterns(generic_patterns)

    return external_risk, overall_risk, external_sentence, overall_sentence


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract debt distress ratings from DSA PDFs"
    )
    parser.add_argument(
        "--countries",
        help='Comma-separated list of countries (e.g. "Cameroon,Chad")',
    )
    parser.add_argument(
        "--range",
        help='Alphabetical range, inclusive (e.g. "Cameroon:Papua New Guinea")',
    )
    parser.add_argument(
        "--output-prefix",
        default="extracted",
        help="Prefix for output files (default: extracted)",
    )
    args = parser.parse_args()

    # Output paths
    output_csv = os.path.join(REPO_ROOT, "data", f"{args.output_prefix}_ratings.csv")
    wide_csv = os.path.join(REPO_ROOT, "data", f"{args.output_prefix}_wide.csv")
    evidence_txt = os.path.join(REPO_ROOT, "data", f"{args.output_prefix}_evidence.txt")

    df = pd.read_csv(INPUT_CSV)
    target_countries = select_countries(df, args)
    print(f"Processing {len(target_countries)} countries: {', '.join(target_countries)}")

    subset = df[df["Country"].isin(target_countries)].copy()
    unique_urls = [u for u in subset["PDF_URL"].unique() if pd.notna(u)]
    print(f"Total entries: {len(subset)}, unique URLs: {len(unique_urls)}")

    os.makedirs(PDF_CACHE, exist_ok=True)

    # --- Download all unique PDFs ---
    url_to_file = {}
    url_to_text = {}
    url_to_pages = {}

    for i, url in enumerate(unique_urls):
        print(f"  [{i + 1}/{len(unique_urls)}] {url[:80]}...")
        filepath, success, note = download_pdf(url)
        url_to_file[url] = (filepath, success, note)

        if success and filepath:
            text = extract_text(filepath)
            pages = extract_early_pages(filepath)
            url_to_text[url] = text
            url_to_pages[url] = pages
            print(f"    -> OK ({note}), {len(text)} chars")
        else:
            url_to_text[url] = ""
            url_to_pages[url] = []
            print(f"    -> FAILED: {note}")

        if note != "cached":
            time.sleep(1)  # rate limiting

    # --- Process each row ---
    results = []
    for _, row in subset.iterrows():
        url = row["PDF_URL"]
        year = row["Year"]
        country = row["Country"]

        if pd.isna(url) or url not in url_to_file:
            results.append({
                "Country": country, "Year": year, "PDF_URL": "",
                "Document_Title": row.get("Document_Title", ""),
                "Link_Works": "no", "Year_Correct": "", "Document_Year": "",
                "External_Risk": "", "External_Risk_Source_Text": "",
                "Overall_Risk": "", "Overall_Risk_Source_Text": "",
                "Notes": "no URL provided",
            })
            continue

        filepath, link_works, dl_note = url_to_file[url]
        text = url_to_text.get(url, "")
        pages = url_to_pages.get(url, [])

        if link_works:
            year_status, doc_year, year_note = check_year_match(pages, year)
            external, overall, ext_sent, ovr_sent = extract_risk_ratings(text)
        else:
            year_status, doc_year, year_note = "", None, ""
            external, overall, ext_sent, ovr_sent = "", "", "", ""

        notes = year_note
        if link_works and not external and not overall:
            notes += "; no explicit risk rating found in text"

        results.append({
            "Country": country,
            "Year": year,
            "PDF_URL": url,
            "Document_Title": row.get("Document_Title", ""),
            "Link_Works": "yes" if link_works else "no",
            "Year_Correct": year_status,
            "Document_Year": doc_year or "",
            "External_Risk": external,
            "External_Risk_Source_Text": ext_sent,
            "Overall_Risk": overall,
            "Overall_Risk_Source_Text": ovr_sent,
            "Notes": notes,
        })

    # --- Save detailed results ---
    result_df = pd.DataFrame(results)
    result_df.to_csv(output_csv, index=False)
    print(f"\nDetailed results → {output_csv}")

    # --- Wide-format output ---
    country_year_data = {}
    for r in results:
        key = (r["Country"], r["Year"])
        if key not in country_year_data and r["Year_Correct"] == "yes":
            country_year_data[key] = {
                "external": r["External_Risk"],
                "overall": r["Overall_Risk"],
                "link": r["PDF_URL"],
                "ext_source": r["External_Risk_Source_Text"],
                "ovr_source": r["Overall_Risk_Source_Text"],
            }

    wide_rows = []
    for country in target_countries:
        wide_row = {"Country": country}
        for yr in YEARS:
            d = country_year_data.get((country, yr), {})
            wide_row[f"{yr} External"] = d.get("external", "")
            wide_row[f"{yr} Overall"] = d.get("overall", "")
        wide_rows.append(wide_row)

    pd.DataFrame(wide_rows).to_csv(wide_csv, index=False)
    print(f"Wide-format → {wide_csv}")

    # --- Evidence file ---
    with open(evidence_txt, "w") as f:
        for yr in YEARS:
            f.write(f"{yr}:\n")
            for country in target_countries:
                d = country_year_data.get((country, yr), {})
                if d.get("link"):
                    f.write(f"{country}: {d['link']}\n")
                    if d.get("ext_source"):
                        f.write(f"  External: {d['ext_source']}\n")
                    if d.get("ovr_source"):
                        f.write(f"  Overall: {d['ovr_source']}\n")
                else:
                    f.write(f"{country}: No link\n")
            f.write("\n")
    print(f"Evidence → {evidence_txt}")

    # --- Summary ---
    filled = sum(
        1 for v in country_year_data.values()
        if v.get("external") or v.get("overall")
    )
    total = len(target_countries) * len(YEARS)
    print(f"\nSummary: {filled}/{total} country-year cells have ratings")

    print(f"\n{'Country':<35} {'Filled':>6}")
    print("-" * 43)
    for country in target_countries:
        count = sum(
            1 for yr in YEARS
            if country_year_data.get((country, yr), {}).get("external")
            or country_year_data.get((country, yr), {}).get("overall")
        )
        print(f"{country:<35} {count:>6}")


if __name__ == "__main__":
    main()
