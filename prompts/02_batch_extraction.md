# Phase 2: Batch Rating Extraction

> Give this prompt to an AI coding agent to run the extraction pipeline.
> For faster processing, split the country list across multiple agents running
> in parallel (e.g. by alphabetical range).

## Task

Run `scripts/extract_ratings.py` to download DSA PDFs and extract debt distress
risk ratings for your assigned countries. Then merge the results into the master
spreadsheet.

## Steps

### 1. Run the extraction script

```bash
# Process all countries at once
python scripts/extract_ratings.py

# Or process an alphabetical batch
python scripts/extract_ratings.py --range "Cameroon:Papua New Guinea"
```

### 2. Review output quality

Check the wide-format output for issues:

- **Countries with zero filled years** may indicate PDF format issues or regex
  gaps — investigate a sample PDF manually
- **Spot-check** a few entries in the evidence file to verify the source text
  makes sense and corresponds to the correct rating
- **Year mismatches** (document year ≠ listed year) are expected for some
  entries in the link index — the script automatically filters these out

### 3. Merge into DDR.csv

Transfer ratings from the script's wide-format output into `data/DDR.csv`:

- **Only fill empty cells** — never overwrite existing values in DDR.csv
- DDR.csv column layout: Country, then alternating (External, Overall) pairs
  for each year from 2005 to 2025

### 4. Append evidence

For each rating added to DDR.csv, append the source to `data/evidence.txt`:

```
[Country] [YEAR]:
  Link: [PDF URL]
  External: [rating]
  Overall: [rating]
  Evidence: [exact quote from document]
```

## Parallel batching strategy

To process all 68 countries efficiently, split into batches by alphabetical
range and assign each to a separate agent:

| Agent | Range                           | ~Countries |
|-------|---------------------------------|------------|
| 1     | Afghanistan → Cambodia          | ~10        |
| 2     | Cameroon → Papua New Guinea     | ~38        |
| 3     | Rwanda → Zimbabwe               | ~20        |

Each agent runs independently against the same `dsa_links_collected.csv` input.
Results are merged into DDR.csv sequentially after all agents complete.

## Domain conventions

- **Pre-2012:** Only a single "risk of debt distress" rating existed → map to
  External; leave Overall blank
- **Post-2012:** The revised LIC-DSF introduced separate External and Overall
  ratings
- **Rating scale:** Low, Moderate, High, In Debt Distress
- **Legitimate gaps:** Not every country has a DSA every year (conflict states,
  countries in arrears, newly independent states, etc.)
