# Free Lead Intelligence Scraper

Zero-cost lead generation + enrichment + DISC psychological profiling system.

## Scripts & What They Do

| Script | Purpose |
|---|---|
| `collect_leads.py` | Scrapes company websites for emails, phones, LinkedIn using regex extraction |
| `lead_intelligence.py` | DISC personality profiler + email pattern generator + personalized outreach |
| `enrichment_pipeline.py` | Multi-source pipeline (Apollo free tier + Apify Google Maps) |
| `cheerio_scraper.js` | Node.js Cheerio-based website contact scraper |
| `build_master_leads.js` | Merges all data sources into MASTER_AI_LEADS.csv |
| `build_final_leads.py` | Python merger/deduplicator for all CSV sources |

## How To Run

```bash
# Step 1: Collect leads from existing data + scrape websites
python3 collect_leads.py

# Step 2: Run intelligence pipeline with DISC profiling
python3 lead_intelligence.py collected_leads.json

# Output: LEAD_INTELLIGENCE.csv
```

## Key Techniques Used

- **Google Dorks** for LinkedIn: `site:linkedin.com/in/ "CEO" "AI automation"`
- **Email Pattern Generation**: firstname@domain.com, first.last@domain.com, etc.
- **Domain Verification**: HTTP HEAD check to verify domain is live
- **DISC Profiling**: NLP analysis of social media content → personality type
- **Personalized Outreach**: Custom subject lines + email openings per DISC type

## Output Files

| File | Contents |
|---|---|
| `LEAD_INTELLIGENCE.csv` | 17 leads with DISC profiles + outreach strategies |
| `MASTER_AI_LEADS.csv` | 281 AI companies with phones, emails, LinkedIn |
| `collected_leads.json` | Raw collected lead data (JSON) |

## Dependencies

```bash
pip install requests python-dotenv textblob dnspython
npm install cheerio axios csv-parse csv-stringify
```

## Cost: $0/month
