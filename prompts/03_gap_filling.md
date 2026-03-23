# Phase 3: Gap-Filling via Web Search

> Give this prompt to an AI coding agent after Phase 2 to fill remaining gaps.
> Include a gap-fill plan (see template below) listing each country's specific
> missing years.

## Task

Fill remaining gaps in `data/DDR.csv` — country-year cells where **both**
External and Overall are still empty after automated extraction.

## Steps

### 1. Generate a gap-fill plan

Compare DDR.csv against the expected 68 × 21 grid to list each country's
missing years. Prioritize by gap count (smallest first) for highest ROI.

Example output:

```
#  Country              Gap years                                    Count
1  Papua New Guinea     2006, 2008, 2010                             3
2  Rwanda               2007, 2012, 2014, 2024-2025                  5
3  Marshall Islands     2005-2011, 2021                               8
...
```

### 2. Search for each gap

For each missing country-year:

1. **Web search:** `"[Country] debt sustainability analysis [YEAR] site:imf.org OR site:worldbank.org"`
2. **Alternative queries:**
   - `"[Country] Article IV [YEAR] DSA"` — for Article IV staff reports
   - `"[Country] HIPC [YEAR]"` — for pre-2010 HIPC documents
3. **Cross-reference:** Check `data/dsa_links_collected.csv` for candidate URLs
   that may have been mislabeled or pointed to the wrong year
4. **Download and read** each candidate PDF, searching for explicit risk rating
   statements

### 3. Update DDR.csv

- Fill **only empty cells** — never overwrite existing values
- Use the standard rating values: Low, Moderate, High, In Debt Distress

### 4. Log evidence

Append to `data/evidence.txt` for every rating added:

```
[Country] [YEAR]:
  Link: [URL]
  External: [rating]
  Overall: [rating]
  Evidence: [exact quote from document]
```

## Constraints

- **Time budget:** ~60 minutes. At ~50 min, stop starting new countries. At
  ~55 min, save all progress and report what was completed vs. what remains.
- **Quality over coverage:** It is better to do fewer countries with verified
  ratings than many countries with uncertain ones.
- **Legitimate gaps are OK:** Not every country has a DSA every year. If
  thorough searching finds no DSA, skip it — do not guess or interpolate.

## Domain notes

- **Pre-2005:** The DSA framework launched April 2005. No DSAs exist before this.
- **Pre-2012:** DSAs state only "risk of debt distress" (= External). The
  "Overall" concept was introduced in 2012 with the revised LIC-DSF. Leave
  Overall blank for pre-2012 if not explicitly stated.
- **South Sudan:** Independent only since 2011. No DSAs before then.
- **Sudan, Somalia, Zimbabwe:** Extended periods of arrears to IFIs — very
  limited DSA coverage is expected.
- **Yemen:** Conflict since 2015 — limited post-2014 DSAs.
- **IMF URL patterns:**
  - Pre-2012: `https://www.imf.org/external/pubs/ft/scr/[YYYY]/cr[YYNNN].pdf`
  - 2012–2017: `https://www.imf.org/external/pubs/ft/dsa/pdf/[YYYY]/dsacr[YYNNN].pdf`
  - 2018+: `https://www.imf.org/-/media/files/publications/cr/[YYYY]/english/...`
- **World Bank:** `https://documents1.worldbank.org/curated/en/[ID]/pdf/...`
