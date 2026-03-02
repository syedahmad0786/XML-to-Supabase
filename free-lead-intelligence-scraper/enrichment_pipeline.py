"""
Multi-Source Lead Enrichment Pipeline
Sources: Apollo.io (companies) + Apify (Google Maps, Leads Scraper)
Output: High-quality decision maker leads with verified contact info
"""

import requests
import os
import json
import csv
import re
import time
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

HEADERS_APOLLO = {
    "Content-Type": "application/json",
    "X-Api-Key": APOLLO_API_KEY,
}

# Decision-maker title patterns for filtering
DECISION_MAKER_TITLES = re.compile(
    r"\b(ceo|cto|coo|cfo|cio|cmo|cpo|founder|co-founder|cofounder|"
    r"owner|partner|president|director|vp|vice president|"
    r"head of|chief|managing director|general manager|"
    r"svp|evp|principal)\b",
    re.IGNORECASE,
)

# Industries we want (AI/tech adjacent)
RELEVANT_INDUSTRIES = {
    "information technology & services", "computer software",
    "internet", "management consulting", "marketing & advertising",
    "computer & network security", "telecommunications",
    "financial services", "business supplies & equipment",
}


# ─── APOLLO: Company Search ──────────────────────────────────────────────────

def apollo_search_companies(keyword_batches, locations=None,
                            employee_ranges=None, pages_per_batch=2):
    """Search Apollo with multiple keyword batches for better targeting."""
    all_orgs = []
    seen = set()

    for keywords in keyword_batches:
        for page in range(1, pages_per_batch + 1):
            payload = {
                "page": page,
                "per_page": 25,
                "q_organization_keyword_tags": keywords,
            }
            if locations:
                payload["organization_locations"] = locations
            if employee_ranges:
                payload["organization_num_employees_ranges"] = employee_ranges

            r = requests.post(
                "https://api.apollo.io/v1/organizations/search",
                json=payload, headers=HEADERS_APOLLO,
            )
            if r.status_code != 200:
                print(f"  Apollo failed: {r.status_code}")
                break

            data = r.json()
            orgs = data.get("organizations", [])
            total = data.get("pagination", {}).get("total_entries", "?")
            print(f"  Apollo [{', '.join(keywords[:2])}...] page {page}: "
                  f"{len(orgs)} orgs (total: {total})")

            for o in orgs:
                name = o.get("name", "")
                domain = o.get("primary_domain") or o.get("website_url") or ""
                key = (name.lower(), domain.lower())
                if key in seen:
                    continue
                seen.add(key)

                all_orgs.append({
                    "company": name,
                    "website": o.get("website_url", ""),
                    "linkedin_company": o.get("linkedin_url", ""),
                    "industry": o.get("industry", ""),
                    "employees": o.get("estimated_num_employees", ""),
                    "city": o.get("city", ""),
                    "state": o.get("state", ""),
                    "country": o.get("country", ""),
                    "founded_year": o.get("founded_year", ""),
                    "source": "apollo",
                })

            if len(orgs) < 25:
                break
            time.sleep(1)

    return all_orgs


# ─── APIFY: Actor Runner ─────────────────────────────────────────────────────

def apify_run_actor(actor_id, run_input, wait_secs=300):
    """Run an Apify actor and wait for results."""
    print(f"  Starting Apify actor {actor_id}...")
    r = requests.post(
        f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}",
        json=run_input, timeout=30,
    )
    if r.status_code not in [200, 201]:
        print(f"  Failed to start actor: {r.status_code} - {r.text[:200]}")
        return []

    run_data = r.json().get("data", {})
    run_id = run_data.get("id")
    dataset_id = run_data.get("defaultDatasetId")
    print(f"  Run ID: {run_id}, Dataset: {dataset_id}")

    for i in range(wait_secs // 10):
        r2 = requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        )
        status = r2.json().get("data", {}).get("status", "UNKNOWN")
        if status == "SUCCEEDED":
            print(f"  Actor completed in ~{(i+1)*10}s")
            break
        if status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            print(f"  Actor {status}")
            return []
        time.sleep(10)
    else:
        print("  Timed out waiting for actor")
        return []

    all_items = []
    offset = 0
    while True:
        r3 = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={APIFY_TOKEN}&limit=100&offset={offset}"
        )
        items = r3.json()
        if not items:
            break
        all_items.extend(items)
        offset += len(items)
        if len(items) < 100:
            break

    print(f"  Got {len(all_items)} results from actor")
    return all_items


# ─── GOOGLE MAPS: Company Discovery ──────────────────────────────────────────

def google_maps_search(search_queries, max_per_query=30):
    """Search Google Maps for companies with contact details."""
    run_input = {
        "searchStringsArray": search_queries,
        "maxCrawledPlacesPerSearch": max_per_query,
        "language": "en",
        "scrapeContacts": True,
        "maxImages": 0,
        "maxReviews": 0,
    }

    items = apify_run_actor(
        "lukaskrivka~google-maps-with-contact-details",
        run_input, wait_secs=600,
    )

    results = []
    seen = set()
    for item in items:
        title = item.get("title", "")
        if not title:
            continue
        # Deduplicate by name + phone
        key = (title.lower(), item.get("phone", ""))
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "company": title,
            "phone": item.get("phone", ""),
            "website": item.get("website", ""),
            "address": item.get("address", ""),
            "city": item.get("city", ""),
            "state": item.get("state", ""),
            "country": item.get("countryCode", ""),
            "postal_code": item.get("postalCode", ""),
            "category": item.get("categoryName", ""),
            "rating": item.get("totalScore", ""),
            "reviews": item.get("reviewsCount", ""),
            "place_id": item.get("placeId", ""),
            "source": "google_maps",
        })

    return results


# ─── APIFY: Decision Maker Search ────────────────────────────────────────────

def is_decision_maker(title):
    """Check if a job title indicates a decision maker."""
    if not title:
        return False
    return bool(DECISION_MAKER_TITLES.search(title))


def apify_leads_search(queries, max_results=50):
    """Search for leads and filter to decision makers only."""
    all_leads = []
    seen_linkedin = set()

    for query in queries:
        run_input = {
            "searchQuery": query,
            "numberOfResults": max_results,
            "includeEmails": True,
        }

        items = apify_run_actor(
            "pipelinelabs~lead-scraper-apollo-zoominfo-lusha-ppe",
            run_input, wait_secs=300,
        )

        for item in items:
            name = item.get("fullName", "")
            title = item.get("position", "")
            linkedin = item.get("linkedinUrl", "")

            # Skip if no name or duplicate LinkedIn
            if not name:
                continue
            if linkedin and linkedin in seen_linkedin:
                continue
            if linkedin:
                seen_linkedin.add(linkedin)

            # Only keep decision makers
            if not is_decision_maker(title):
                continue

            all_leads.append({
                "full_name": name,
                "first_name": item.get("firstName", ""),
                "last_name": item.get("lastName", ""),
                "title": title,
                "email": item.get("email", ""),
                "phone": item.get("phone", ""),
                "linkedin": linkedin,
                "company": item.get("orgName", ""),
                "company_website": item.get("orgWebsite", ""),
                "company_industry": item.get("orgIndustry", ""),
                "company_size": item.get("orgSize", ""),
                "company_city": item.get("orgCity", ""),
                "company_state": item.get("orgState", ""),
                "company_country": item.get("orgCountry", ""),
                "company_linkedin": item.get("orgLinkedinUrl", ""),
                "company_description": item.get("orgDescription", ""),
                "company_founded": item.get("orgFoundedYear", ""),
                "source": "apify_leads",
            })

        time.sleep(2)

    return all_leads


# ─── MERGE & DEDUPLICATE ─────────────────────────────────────────────────────

def normalize_domain(url):
    """Extract clean domain from URL."""
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://", "http://", "www."]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


def merge_company_data(apollo_companies, gmaps_companies):
    """Merge companies from Apollo and Google Maps, deduplicating by domain."""
    seen_domains = {}
    merged = []

    for c in apollo_companies:
        domain = normalize_domain(c.get("website", ""))
        if domain and domain in seen_domains:
            idx = seen_domains[domain]
            for k, v in c.items():
                if v and not merged[idx].get(k):
                    merged[idx][k] = v
        else:
            if domain:
                seen_domains[domain] = len(merged)
            merged.append(c)

    for c in gmaps_companies:
        domain = normalize_domain(c.get("website", ""))
        if domain and domain in seen_domains:
            idx = seen_domains[domain]
            for k, v in c.items():
                if v and not merged[idx].get(k):
                    merged[idx][k] = v
            merged[idx]["source"] = merged[idx].get("source", "") + "+google_maps"
        else:
            if domain:
                seen_domains[domain] = len(merged)
            merged.append(c)

    return merged


def save_csv(data, filename, fieldnames=None):
    """Save list of dicts to CSV."""
    if not data:
        print(f"  No data to save for {filename}")
        return

    if not fieldnames:
        fieldnames = list(data[0].keys())

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)

    print(f"  Saved {len(data)} rows to {filename}")


# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def run_pipeline():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    print("\n" + "=" * 60)
    print("  MULTI-SOURCE LEAD ENRICHMENT PIPELINE v2")
    print("  (with decision-maker filtering)")
    print("=" * 60)

    # ── Step 1: Apollo Company Search (multiple targeted batches) ──
    print("\n[1/4] Searching Apollo for AI/automation companies...")
    apollo_companies = apollo_search_companies(
        keyword_batches=[
            ["artificial intelligence", "software company"],
            ["machine learning", "startup"],
            ["automation", "consulting"],
            ["chatbot", "AI agent"],
            ["robotic process automation"],
            ["data science", "analytics"],
            ["natural language processing"],
            ["computer vision"],
        ],
        locations=["United States"],
        employee_ranges=["11,50", "51,200", "201,500"],
        pages_per_batch=2,
    )
    print(f"  Total Apollo companies: {len(apollo_companies)}")

    # ── Step 2: Google Maps (US-specific queries) ──
    print("\n[2/4] Scraping Google Maps for AI companies (US-focused)...")
    gmaps_companies = google_maps_search(
        search_queries=[
            "AI automation agency in New York USA",
            "AI automation agency in San Francisco USA",
            "AI automation agency in Los Angeles USA",
            "AI automation agency in Chicago USA",
            "AI automation agency in Austin Texas",
            "AI consulting company in Boston USA",
            "AI consulting company in Seattle USA",
            "machine learning startup in Silicon Valley",
            "chatbot development company in USA",
            "RPA consulting firm in United States",
        ],
        max_per_query=20,
    )
    print(f"  Total Google Maps companies: {len(gmaps_companies)}")

    # ── Step 3: Merge ──
    print("\n[3/4] Merging and deduplicating...")
    all_companies = merge_company_data(apollo_companies, gmaps_companies)
    print(f"  Merged unique companies: {len(all_companies)}")

    # ── Step 4: Decision makers (with title filtering) ──
    print("\n[4/4] Finding decision makers (CEO/CTO/Founder/VP only)...")
    leads = apify_leads_search(
        queries=[
            "CEO artificial intelligence company USA",
            "CTO machine learning startup United States",
            "founder AI automation agency",
            "CEO chatbot company",
            "CTO robotic process automation",
            "founder AI consulting firm",
            "VP engineering AI company",
            "director AI solutions",
            "CEO computer vision startup",
            "CTO natural language processing company",
        ],
        max_results=50,
    )
    print(f"  Total qualified decision makers: {len(leads)}")

    # ── Save outputs ──
    print("\n" + "=" * 60)
    print("  SAVING RESULTS")
    print("=" * 60)

    company_fields = [
        "company", "website", "phone", "linkedin_company", "industry",
        "employees", "city", "state", "country", "address", "postal_code",
        "category", "rating", "reviews", "founded_year", "source",
    ]
    save_csv(all_companies, f"companies_enriched_{timestamp}.csv", company_fields)

    lead_fields = [
        "full_name", "first_name", "last_name", "title", "email", "phone",
        "linkedin", "company", "company_website", "company_industry",
        "company_size", "company_city", "company_state", "company_country",
        "company_linkedin", "company_description", "company_founded", "source",
    ]
    save_csv(leads, f"decision_makers_{timestamp}.csv", lead_fields)

    # Master file: decision makers + company-only rows
    master_leads = []
    for lead in leads:
        master_leads.append({
            "full_name": lead.get("full_name", ""),
            "title": lead.get("title", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "linkedin": lead.get("linkedin", ""),
            "company": lead.get("company", ""),
            "company_website": lead.get("company_website", ""),
            "company_industry": lead.get("company_industry", ""),
            "company_size": str(lead.get("company_size", "")),
            "location": f"{lead.get('company_city', '')}, {lead.get('company_state', '')}".strip(", "),
            "source": "decision_maker",
        })

    for company in all_companies:
        if company.get("phone") or company.get("website"):
            master_leads.append({
                "full_name": "",
                "title": "",
                "email": "",
                "phone": company.get("phone", ""),
                "linkedin": company.get("linkedin_company", ""),
                "company": company.get("company", ""),
                "company_website": company.get("website", ""),
                "company_industry": company.get("industry", "") or company.get("category", ""),
                "company_size": str(company.get("employees", "")),
                "location": f"{company.get('city', '')}, {company.get('state', '')}".strip(", "),
                "source": company.get("source", ""),
            })

    master_fields = [
        "full_name", "title", "email", "phone", "linkedin",
        "company", "company_website", "company_industry",
        "company_size", "location", "source",
    ]
    save_csv(master_leads, f"MASTER_LEADS_{timestamp}.csv", master_fields)

    # Summary
    leads_with_email = sum(1 for l in leads if l.get("email"))
    leads_with_linkedin = sum(1 for l in leads if l.get("linkedin"))
    companies_with_phone = sum(1 for c in all_companies if c.get("phone"))
    companies_with_linkedin = sum(1 for c in all_companies if c.get("linkedin_company"))

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Companies found:           {len(all_companies)}")
    print(f"    With phone:              {companies_with_phone}")
    print(f"    With LinkedIn:           {companies_with_linkedin}")
    print(f"  Decision makers found:     {len(leads)}")
    print(f"    With verified email:     {leads_with_email}")
    print(f"    With LinkedIn profile:   {leads_with_linkedin}")
    print(f"  Master file total rows:    {len(master_leads)}")
    print(f"\n  Output files:")
    print(f"    companies_enriched_{timestamp}.csv")
    print(f"    decision_makers_{timestamp}.csv")
    print(f"    MASTER_LEADS_{timestamp}.csv")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
