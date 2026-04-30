# Competitor Analysis Workflow

## Objective
Automatically discover competitors, scrape their websites, analyze strengths/weaknesses/market gaps using Claude AI, and produce a branded PDF report for the business owner.

---

## Required Inputs

### business_profile.json (must be filled before first run)
| Field | Required | Description |
|---|---|---|
| business_name | YES | Your company name |
| description | YES | What your business does |
| industry | YES | Your industry/sector |
| target_customers | YES | Who you serve |
| location | Recommended | City, country, or region |
| website | Recommended | Your website URL (excluded from competitor results) |
| products_services | Recommended | List of what you offer |
| unique_value_proposition | Recommended | What makes you different |
| known_competitors | Optional | Manual fallback list if no search API |

### branding_config.json (optional, has safe defaults)
| Field | Description |
|---|---|
| logo_path | Absolute path to PNG/JPG logo file |
| primary_color | Hex color for headings and cover (e.g. #1A1A2E) |
| secondary_color | Hex color for table backgrounds |
| accent_color | Hex color for subheadings and dividers |
| company_name | Displayed in report header/footer |

### .env (API keys)
```
ANTHROPIC_API_KEY=     # REQUIRED — powers the analysis step
SERPAPI_API_KEY=       # Optional — auto-discovers competitors via Google Search
TAVILY_API_KEY=        # Optional — alternative search provider
```

---

## Tool Sequence

```
python run_competitor_analysis.py
```

| Step | Tool | Input | Output |
|---|---|---|---|
| 1 | tools/discover_competitors.py | business_profile.json, .env | .tmp/competitors.json |
| 2 | tools/scrape_competitor.py (×N) | URL from competitors.json | .tmp/scraped_{domain}.json |
| 3 | tools/analyze_competitors.py | business_profile.json + scraped_*.json | .tmp/analysis.json |
| 4 | tools/generate_pdf_report.py | analysis.json + branding_config.json | reports/competitor_analysis_YYYY-MM-DD.pdf |

---

## Expected Outputs

- `.tmp/competitors.json` — list of discovered competitors with name, URL, snippet
- `.tmp/scraped_{domain}.json` — one file per competitor with scraped data
- `.tmp/analysis.json` — structured AI analysis (exec summary, SWOT, gaps, actions)
- `reports/competitor_analysis_YYYY-MM-DD.pdf` — final branded PDF report

---

## PDF Report Sections

1. Cover page (logo, title, company name, date)
2. Table of contents
3. Executive Summary
4. Competitor Profiles (one per competitor)
5. SWOT Comparison table
6. Market Gaps & Opportunities
7. Recommended Actions (with priority and timeframe)

---

## Edge Cases & How They Are Handled

### No search API key
- **Behavior**: Falls back to `known_competitors` in business_profile.json
- **If known_competitors is also empty**: Tool exits with instructions to either add an API key or fill the list
- **Fix**: Add `SERPAPI_API_KEY` or `TAVILY_API_KEY` to `.env`, OR populate `known_competitors`

### Competitor website blocks scraping (403/429)
- **Behavior**: scrape_competitor.py writes `{"error": "http_403"}` and exits 0
- **Pipeline impact**: Analysis continues; Claude notes "limited data" for that competitor
- **Fix**: No fix needed — pipeline is designed to tolerate scrape failures

### JavaScript-heavy site (minimal text extracted)
- **Behavior**: `js_heavy_signal: true` written to scraped JSON
- **Pipeline impact**: Claude lowers confidence and flags partial data in the report
- **Future enhancement**: Add Playwright-based scraping for JS sites (optional dependency)

### SerpAPI rate limit (429)
- **Behavior**: Tool prints clear message and exits 1; orchestrator aborts
- **Fix**: Wait for quota reset, or switch to Tavily (`TAVILY_API_KEY`)

### Claude API failure / invalid JSON response
- **Behavior**: Retries once after 3 seconds with an explicit JSON correction prompt
- **If second attempt fails**: Saves raw response to `.tmp/analysis_raw.txt` and exits 1
- **Fix**: Check `.tmp/analysis_raw.txt`, look for truncation or refusal; adjust `MAX_TOKENS` if needed

### Missing logo file
- **Behavior**: generate_pdf_report.py falls back to a colored text-box with company_name
- **Fix**: Set valid absolute path in `branding_config.json → logo_path`

### Empty analysis.json / missing fields
- **Behavior**: PDF generator uses "N/A" / empty list fallbacks for all missing fields
- **No crash**: Workflow completes with partial data in the report

---

## Re-running Individual Steps

You can re-run any step independently without running the full workflow:

```bash
# Re-run only analysis (keeps existing scraped data)
python tools/analyze_competitors.py

# Re-run only PDF generation (keeps existing analysis)
python tools/generate_pdf_report.py

# Re-scrape a specific competitor
python tools/scrape_competitor.py https://competitor.com

# Full re-run (re-discovers, re-scrapes, re-analyzes, re-generates)
python run_competitor_analysis.py
```

`.tmp/` files are always overwritten on re-run. `reports/` accumulates dated PDFs.

---

## Learning Log

_Update this section when you discover new constraints, rate limits, or better approaches._

| Date | Discovery | Action Taken |
|---|---|---|
| — | — | — |
