# Phase 1: DSA Link Collection

> Give this prompt to an AI coding agent to build the master link index.
> Split the country list across multiple agents for parallel execution.

## Task

For each country in your assigned list, find the URL of every publicly available
IMF or World Bank Debt Sustainability Analysis (DSA) document from 2005 to 2025.
Output results to `data/dsa_links_collected.csv`.

## Search strategy

For each country-year pair, try the following searches in order:

1. `"[Country] debt sustainability analysis [YEAR] site:imf.org"`
2. `"[Country] Article IV [YEAR] site:imf.org"` — Article IV staff reports for
   LICs include a DSA appendix
3. `"[Country] debt sustainability analysis site:worldbank.org"`
4. `"[Country] HIPC [YEAR]"` — HIPC decision/completion point documents always
   include a DSA

## Known URL patterns

Use these patterns to construct candidate URLs directly, in addition to web
search:

- **IMF pre-2012:** `https://www.imf.org/external/pubs/ft/scr/[YYYY]/cr[YYNNN].pdf`
- **IMF 2012–2017:** `https://www.imf.org/external/pubs/ft/dsa/pdf/[YYYY]/dsacr[YYNNN].pdf`
- **IMF 2018+:** `https://www.imf.org/-/media/files/publications/cr/[YYYY]/english/...`
- **World Bank:** `https://documents1.worldbank.org/curated/en/[ID]/pdf/...`

## Output format

Append each finding as a row in `data/dsa_links_collected.csv`:

```
Country,Year,PDF_URL,Source,Document_Title,Status,Notes
```

- **Source:** IMF, World Bank, or World Bank/IMF (for joint DSAs)
- **Status:** Set to `Needs Verification` for all entries
- **Notes:** Include any context that helps a human verify (e.g. "HIPC completion
  point document", "may cover fiscal year rather than calendar year")
- If multiple candidate PDFs exist for the same country-year, include all of
  them — the extraction script (Phase 2) will validate which one matches

## Quality rules

- Verify that each URL points to a PDF, not a landing page
- Record the full document title so a reviewer can assess relevance at a glance
- Do not fabricate URLs — only record links you have confirmed exist
- If no DSA can be found for a country-year, leave it out (do not create a row
  with an empty URL)

## Countries

Afghanistan, Bangladesh, Benin, Bhutan, Burkina Faso, Burundi, Cabo Verde,
Cambodia, Cameroon, Central African Republic, Chad, Comoros, Congo (Democratic
Republic of), Congo (Republic of), Côte d'Ivoire, Djibouti, Dominica, Eritrea,
Ethiopia, Gambia (The), Ghana, Grenada, Guinea, Guinea-Bissau, Haiti, Honduras,
Kenya, Kiribati, Kyrgyz Republic, Lao P.D.R., Lesotho, Liberia, Madagascar,
Malawi, Maldives, Mali, Marshall Islands, Mauritania, Micronesia, Moldova,
Mozambique, Myanmar, Nepal, Nicaragua, Niger, Papua New Guinea, Rwanda, Samoa,
São Tomé and Príncipe, Senegal, Sierra Leone, Solomon Islands, Somalia, South
Sudan, St. Vincent and the Grenadines, Sudan, Tajikistan, Tanzania, Timor Leste,
Togo, Tonga, Tuvalu, Uganda, Uzbekistan, Vanuatu, Yemen (Republic of), Zambia,
Zimbabwe
