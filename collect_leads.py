"""
AUTOMATED LEAD COLLECTOR
=========================
Uses Google dork patterns to find decision makers on LinkedIn,
scrapes their company websites for contact info,
then feeds everything into the DISC profiling engine.

Run this script, then run lead_intelligence.py on the output.
"""

import requests
import json
import re
import csv
import time
import os
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─── GOOGLE DORK PATTERNS FOR LINKEDIN ───────────────────────────────────────

SEARCH_QUERIES = [
    # CEO/Founder of AI agencies
    'site:linkedin.com/in/ "CEO" "AI automation" agency',
    'site:linkedin.com/in/ "founder" "artificial intelligence" company',
    'site:linkedin.com/in/ "CTO" "machine learning" startup',
    'site:linkedin.com/in/ "CEO" "chatbot" company',
    'site:linkedin.com/in/ "founder" "RPA" "automation"',
    'site:linkedin.com/in/ "CEO" "AI consulting"',
    'site:linkedin.com/in/ "founder" "AI agent" company',
    'site:linkedin.com/in/ "CEO" "data science" agency',

    # Decision makers at AI companies with location
    'site:linkedin.com/in/ "founder" "AI" "New York"',
    'site:linkedin.com/in/ "CEO" "artificial intelligence" "San Francisco"',
    'site:linkedin.com/in/ "founder" "automation" "Los Angeles"',
    'site:linkedin.com/in/ "CTO" "AI" "Austin"',
    'site:linkedin.com/in/ "CEO" "machine learning" "Boston"',

    # AI company contact pages
    '"AI automation agency" contact email phone',
    '"artificial intelligence company" "contact us" CEO founder email',
    '"AI consulting" company USA phone email "get in touch"',
    '"chatbot development" company USA phone email contact',
    '"RPA agency" contact email phone founder',
]


def parse_linkedin_from_search(search_text):
    """Parse LinkedIn profile details from search result text."""
    leads = []

    # Pattern: Name - Title - Company | LinkedIn
    # or: Name | Title @ Company
    lines = search_text.split("\n")
    current_lead = {}

    for line in lines:
        line = line.strip()
        if not line:
            if current_lead.get("name"):
                leads.append(current_lead)
                current_lead = {}
            continue

        # Look for LinkedIn URLs
        linkedin_match = re.search(r'(https?://(?:www\.)?linkedin\.com/in/[^\s\)]+)', line)
        if linkedin_match:
            current_lead["linkedin"] = linkedin_match.group(1)

        # Look for names (bold or heading patterns)
        name_match = re.search(r'\*\*([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\*\*', line)
        if name_match:
            current_lead["name"] = name_match.group(1)

        # Look for titles
        title_match = re.search(r'(?:Founder|CEO|CTO|COO|Director|VP|Head|President|Owner|Partner)', line, re.IGNORECASE)
        if title_match:
            current_lead["title"] = title_match.group(0)

        # Look for company names
        company_match = re.search(r'(?:at|@|,)\s*([A-Z][^\.,\|]+)', line)
        if company_match:
            current_lead["company"] = company_match.group(1).strip()

    if current_lead.get("name"):
        leads.append(current_lead)

    return leads


def scrape_website_contacts(url):
    """Scrape a website for contact information."""
    result = {"emails": [], "phones": [], "socials": {}}

    if not url or not url.startswith("http"):
        return result

    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code >= 400:
            return result

        text = r.text

        # Extract emails
        emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
        junk_domains = {"example.com", "w3.org", "schema.org", "googleapis.com",
                        "wixpress.com", "sentry.io", "gravatar.com", "wordpress.com"}
        result["emails"] = list(set(
            e.lower() for e in emails
            if e.split("@")[1] not in junk_domains
            and not e.endswith((".png", ".jpg", ".svg", ".css", ".js"))
        ))[:5]

        # Extract phone from tel: links
        tel_matches = re.findall(r'href="tel:([^"]+)"', text)
        result["phones"] = list(set(tel_matches))[:3]

        # Also extract phone patterns from text
        if not result["phones"]:
            phone_matches = re.findall(
                r'(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text
            )
            result["phones"] = list(set(phone_matches))[:3]

        # Extract social links
        for platform, pattern in [
            ("linkedin", r'linkedin\.com/(?:company|in)/[^\s"\']+'),
            ("twitter", r'(?:twitter|x)\.com/[^\s"\']+'),
            ("facebook", r'facebook\.com/[^\s"\']+'),
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["socials"][platform] = "https://" + match.group(0)

        # Try /contact page
        contact_urls = []
        for suffix in ["/contact", "/contact-us", "/about", "/about-us"]:
            try:
                base = url.rstrip("/")
                cr = requests.get(base + suffix, headers=HEADERS, timeout=8, allow_redirects=True)
                if cr.status_code < 400:
                    ct = cr.text
                    more_emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', ct)
                    for e in more_emails:
                        e = e.lower()
                        if e.split("@")[1] not in junk_domains and e not in result["emails"]:
                            result["emails"].append(e)

                    more_tels = re.findall(r'href="tel:([^"]+)"', ct)
                    for t in more_tels:
                        if t not in result["phones"]:
                            result["phones"].append(t)
                    break  # Got one contact page, that's enough
            except Exception:
                continue

    except Exception:
        pass

    return result


def collect_from_existing_data():
    """Load leads from our existing master CSV files."""
    leads = []

    # Load from MASTER_AI_LEADS.csv
    if os.path.exists("MASTER_AI_LEADS.csv"):
        with open("MASTER_AI_LEADS.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("founder") or row.get("email"):
                    leads.append({
                        "name": row.get("founder", ""),
                        "title": "Founder/CEO",
                        "company": row.get("company", ""),
                        "website": row.get("website", ""),
                        "linkedin": row.get("linkedin", ""),
                        "phone": row.get("phone", ""),
                        "location": row.get("location", ""),
                        "email": row.get("email", ""),
                        "content": "",
                        "source": "master_csv",
                    })

    return leads


def enrich_lead_with_website(lead):
    """Enrich a lead by scraping their company website."""
    website = lead.get("website", "")
    if not website:
        return lead

    contacts = scrape_website_contacts(website)

    if contacts["emails"] and not lead.get("email"):
        lead["email"] = contacts["emails"][0]
        lead["all_emails"] = contacts["emails"]

    if contacts["phones"] and not lead.get("phone"):
        lead["phone"] = contacts["phones"][0]

    if contacts["socials"].get("linkedin") and not lead.get("linkedin"):
        lead["linkedin"] = contacts["socials"]["linkedin"]

    return lead


def main():
    print("\n" + "=" * 55)
    print("  AUTOMATED LEAD COLLECTOR")
    print("  Google Dorks + Website Scraping")
    print("=" * 55)

    # Step 1: Collect from existing data
    print("\n[1/3] Loading existing leads with founder info...")
    existing = collect_from_existing_data()
    print(f"  Found {len(existing)} leads with founder/contact info")

    # Step 2: Enrich with website scraping
    print(f"\n[2/3] Scraping company websites for contact info...")
    enriched = []
    websites_to_scrape = [l for l in existing if l.get("website")][:50]

    for i, lead in enumerate(websites_to_scrape):
        domain = lead.get("website", "").replace("https://", "").replace("http://", "").split("/")[0]
        print(f"  [{i+1}/{len(websites_to_scrape)}] {domain}... ", end="", flush=True)

        lead = enrich_lead_with_website(lead)
        enriched.append(lead)

        found = []
        if lead.get("email"):
            found.append(f"email: {lead['email']}")
        if lead.get("phone"):
            found.append(f"phone: {lead['phone']}")
        print(", ".join(found) if found else "no contact info")

        time.sleep(1)

    # Step 3: Save for intelligence processing
    print(f"\n[3/3] Saving collected leads...")

    output = []
    seen_names = set()
    for lead in enriched:
        name = lead.get("name", "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        output.append({
            "name": name,
            "title": lead.get("title", ""),
            "company": lead.get("company", ""),
            "website": lead.get("website", ""),
            "linkedin": lead.get("linkedin", ""),
            "phone": lead.get("phone", ""),
            "location": lead.get("location", ""),
            "email": lead.get("email", ""),
            "content": lead.get("content", ""),
            "source": lead.get("source", ""),
        })

    # Save as JSON for lead_intelligence.py
    with open("collected_leads.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Saved {len(output)} leads to collected_leads.json")
    print(f"  With email: {sum(1 for l in output if l.get('email'))}")
    print(f"  With phone: {sum(1 for l in output if l.get('phone'))}")
    print(f"\n  Next: python3 lead_intelligence.py collected_leads.json")
    print("=" * 55)


if __name__ == "__main__":
    main()
