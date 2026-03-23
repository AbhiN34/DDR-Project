# Debt Distress Ratings (DDR) Dataset

Systematic extraction of IMF/World Bank debt distress risk ratings for 68
low-income countries (2005–2025), sourced from Debt Sustainability Analysis
(DSA) documents under the LIC Debt Sustainability Framework.

## Repository structure

```
├── data/
│   ├── dsa_links_collected.csv   # Master index of ~1,500 DSA PDF URLs
│   ├── DDR.csv                   # Final ratings spreadsheet (68 countries × 21 years)
│   └── evidence.txt              # Source quotes for each rating
├── scripts/
│   └── extract_ratings.py        # Automated PDF download + rating extraction
├── prompts/
│   ├── 01_link_collection.md     # Agent prompt: build the PDF link index
│   ├── 02_batch_extraction.md    # Agent prompt: run the extraction pipeline
│   └── 03_gap_filling.md         # Agent prompt: web-search for remaining gaps
├── requirements.txt
└── README.md
```

## Data collection process

The pipeline has four phases. Each phase builds on the outputs of the previous
one. AI coding agents (Claude Code) are used to execute Phases 1–3; a human
operator reviews outputs and advances the pipeline between phases.

### Phase 1: Source identification

**Input:** List of 68 LIC-DSF countries, year range 2005–2025.
**Output:** `data/dsa_links_collected.csv`

An agent is given the country list and a set of search strategies
([`prompts/01_link_collection.md`](prompts/01_link_collection.md)). For each
country-year pair, the agent:

1. Searches IMF and World Bank archives using targeted queries
   (e.g. `"[Country] debt sustainability analysis [YEAR] site:imf.org"`)
2. Checks known IMF/WB URL patterns for that country and year
3. Records each candidate PDF URL, document title, and source in the CSV

The result is a master link index with ~1,500 entries. Multiple candidate URLs
per country-year are allowed — the extraction phase validates which one is
correct.

### Phase 2: Automated extraction

**Input:** `data/dsa_links_collected.csv`
**Output:** `data/DDR.csv` (partial), `data/evidence.txt` (partial)

An agent runs `scripts/extract_ratings.py`, which processes the link index
end-to-end:

1. **Download** — Each PDF is fetched with local caching, retry logic, and
   rate limiting to avoid overloading IMF/WB servers
2. **Text extraction** — Text is extracted via
   [pdfplumber](https://github.com/jsvine/pdfplumber). If pdfplumber returns
   fewer than 100 characters (common with older World Bank documents that have
   malformed text layers), [PyMuPDF](https://pymupdf.readthedocs.io/) is used
   as a fallback — it uses a different extraction engine that is more tolerant
   of non-standard PDF encoding
3. **Year validation** — The document's actual year is detected from the first
   few pages (Article IV title years, publication dates) and compared against
   the listed year. Only year-matched documents proceed to rating extraction
4. **Rating extraction** — Regex patterns match standard IMF/WB phrasing to
   identify External and Overall ratings separately:
   - Phrases containing "**external** debt distress" → External column
   - Phrases containing "**overall** risk of debt distress" → Overall column
   - Pre-2012 DSAs state only "risk of debt distress" (no qualifier) → mapped
     to External, since the Overall concept was introduced in 2012 with the
     revised LIC-DSF
5. **Evidence capture** — The sentence surrounding each matched rating is saved
   for auditability

The script can be run across all countries at once or in parallel batches
(see [`prompts/02_batch_extraction.md`](prompts/02_batch_extraction.md) for
the batching strategy).

### Phase 3: Gap-filling via web search

**Input:** `data/DDR.csv` (with gaps from Phase 2)
**Output:** `data/DDR.csv` (more complete), `data/evidence.txt` (extended)

After automated extraction, the agent compares DDR.csv against expected
coverage to identify remaining gaps — country-year cells where both External
and Overall are still empty. A structured gap-fill plan is generated,
prioritized by gap count (smallest first for highest ROI).

For each gap, the agent
([`prompts/03_gap_filling.md`](prompts/03_gap_filling.md)):

1. Web-searches for DSA documents not in the original link index
2. Cross-references `dsa_links_collected.csv` for candidate URLs that may have
   been mislabeled or pointed to the wrong year
3. Downloads and reads each candidate PDF, searching for explicit risk rating
   quotes
4. Updates DDR.csv — filling only empty cells, never overwriting existing values
5. Logs evidence with the exact quote, source URL, and extracted rating

Agents operate under a time budget (~60 min) with instructions to prioritize
quality over coverage. It is better to have fewer verified ratings than many
uncertain ones.

### Phase 4: Manual review

**Input:** `data/DDR.csv`, `data/evidence.txt`
**Output:** `data/DDR.csv` (final)

A human reviewer:

1. Spot-checks 1–2 years per country against the source PDFs cited in
   `evidence.txt`
2. Verifies that remaining blank cells are legitimate gaps (no DSA published
   for that country-year) rather than extraction failures
3. Marks confirmed-missing cells with a dash (`-`) to distinguish "no DSA
   exists" from "not yet searched"

## Role of AI agents

This project uses [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
agents as research assistants, orchestrated in parallel via
[Conductor](https://conductor.app). The agents operate under structured prompts
(stored in `prompts/`) that specify:

- **What to do:** search strategies, extraction rules, output formats
- **Domain knowledge:** pre-2012 vs. post-2012 DSA framework differences, known
  URL patterns, legitimate gap scenarios
- **Quality constraints:** never overwrite existing data, log evidence for every
  rating, prioritize accuracy over completeness
- **Time budgets:** agents are given finite time windows and instructed to save
  progress gracefully

The human operator's role is to:
- Advance the pipeline between phases
- Review and validate agent outputs
- Provide domain judgment on edge cases (e.g. whether a rating from a
  neighboring year's DSA should be carried forward)

The prompts in `prompts/` are the actual instructions given to agents. They are
included in this repository so the methodology is fully transparent and
reproducible.

## Domain conventions

| Convention | Detail |
|---|---|
| **Rating scale** | Low, Moderate, High, In Debt Distress |
| **Pre-2012 DSAs** | Only a single "risk of debt distress" rating → mapped to External; Overall left blank |
| **Post-2012 DSAs** | Revised LIC-DSF introduced separate External and Overall ratings |
| **Legitimate gaps** | Not every country has a DSA every year (conflict states, countries in arrears, newly independent states) |
| **Blank vs. dash** | Blank = not yet searched; dash (`-`) = confirmed no DSA exists |
| **DSA framework start** | April 2005 — no DSAs exist before this date |

## Replication

To replicate or extend this dataset:

```bash
pip install -r requirements.txt

# Step 1: Run the extraction pipeline against the link index
python scripts/extract_ratings.py

# Or process a subset of countries
python scripts/extract_ratings.py --countries "Cameroon,Chad,Comoros"
python scripts/extract_ratings.py --range "Cameroon:Papua New Guinea"

# Step 2: Review outputs in data/ and fill gaps using prompts/03_gap_filling.md
# Step 3: Manual review of results against source PDFs
```

To add new countries or extend the year range, update
`data/dsa_links_collected.csv` with new entries (using the search strategy in
`prompts/01_link_collection.md`) and re-run the pipeline.
