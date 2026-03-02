#!/usr/bin/env python3
"""
VIBE PROSPECTING ENGINE v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Aggressive multi-channel prospecting for companies that will pay $5K+ for AI solutions.
Targets: SMBs in USA (10-500 employees) in high-AI-need industries.

Channels:
  1. Apollo API - company + people search
  2. Apify Google Maps - local business discovery
  3. Website scraping - contact extraction
  4. DISC profiling - personality-based outreach
"""

import requests
import os
import json
import csv
import re
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

HEADERS_APOLLO = {
    "Content-Type": "application/json",
    "X-Api-Key": APOLLO_API_KEY,
}

# ═══════════════════════════════════════════════════════════════════
#  $5K BUYER TARGETING CONFIG
# ═══════════════════════════════════════════════════════════════════

# Industries where $5K AI solutions deliver massive ROI
HIGH_VALUE_INDUSTRIES = [
    # Tier 1: $10K+ deal potential (manual processes, high labor costs)
    "healthcare", "medical", "dental", "dermatology", "orthopedic",
    "legal", "law firm", "attorney",
    "financial", "wealth management", "insurance", "accounting",
    "real estate", "property management",
    # Tier 2: $5K-$10K deal potential (scaling pain, tech-forward)
    "marketing agency", "digital agency", "advertising",
    "logistics", "freight", "supply chain", "3PL",
    "manufacturing", "industrial",
    "staffing", "recruiting", "HR",
    "construction", "contractor",
    # Tier 3: $5K sweet spot (repetitive tasks, growth stage)
    "e-commerce", "retail", "restaurant chain",
    "education", "edtech", "training",
    "saas", "software", "tech startup",
    "consulting", "professional services",
]

# Apollo search batches - each targets a different $5K buyer persona
APOLLO_SEARCH_BATCHES = [
    # Healthcare - HUGE AI need (scheduling, billing, patient engagement)
    {"keywords": ["healthcare", "medical practice"], "titles": ["CEO", "COO", "Practice Manager"]},
    {"keywords": ["dental practice", "dental group"], "titles": ["CEO", "Owner", "Practice Manager"]},
    # Legal - document AI, contract review, intake automation
    {"keywords": ["law firm", "legal services"], "titles": ["Managing Partner", "COO", "Director of Operations"]},
    # Financial - client onboarding, reporting, compliance
    {"keywords": ["wealth management", "financial advisory"], "titles": ["CEO", "COO", "Chief Operating Officer"]},
    {"keywords": ["insurance agency", "insurance broker"], "titles": ["CEO", "Owner", "Agency Principal"]},
    # Marketing agencies - content AI, reporting, client management
    {"keywords": ["marketing agency", "digital agency"], "titles": ["CEO", "Founder", "Managing Director"]},
    {"keywords": ["advertising agency", "creative agency"], "titles": ["CEO", "President", "Managing Partner"]},
    # Logistics - route optimization, tracking, dispatch
    {"keywords": ["logistics company", "freight broker"], "titles": ["CEO", "COO", "VP Operations"]},
    {"keywords": ["3PL", "supply chain"], "titles": ["CEO", "CTO", "VP Technology"]},
    # Real estate - lead gen, CRM automation, property management
    {"keywords": ["real estate brokerage", "property management"], "titles": ["CEO", "Broker", "Managing Director"]},
    # Manufacturing - quality control, scheduling, predictive maintenance
    {"keywords": ["manufacturing", "industrial"], "titles": ["CEO", "COO", "VP Operations"]},
    # Staffing - candidate matching, outreach automation
    {"keywords": ["staffing agency", "recruiting firm"], "titles": ["CEO", "President", "Managing Director"]},
    # Construction - project management, estimating, scheduling
    {"keywords": ["construction company", "general contractor"], "titles": ["CEO", "President", "Owner"]},
    # E-commerce - product descriptions, customer service, inventory
    {"keywords": ["e-commerce", "online retail"], "titles": ["CEO", "Founder", "CTO"]},
    # Professional services - proposal automation, client management
    {"keywords": ["consulting firm", "professional services"], "titles": ["CEO", "Managing Partner", "Director"]},
]

# Google Maps queries for local businesses (high AI need)
GMAPS_QUERIES = [
    "medical practice group in Dallas Texas",
    "law firm in Atlanta Georgia",
    "marketing agency in Miami Florida",
    "dental practice in Houston Texas",
    "insurance agency in Chicago Illinois",
    "real estate brokerage in Phoenix Arizona",
    "logistics company in Charlotte North Carolina",
    "staffing agency in Denver Colorado",
    "manufacturing company in Nashville Tennessee",
    "construction company in Austin Texas",
    "accounting firm in San Diego California",
    "wealth management firm in New York",
    "digital marketing agency in Los Angeles",
    "IT services company in Seattle Washington",
    "dental practice in Tampa Florida",
]

# AI solution hooks per industry
AI_HOOKS = {
    "healthcare": "We build AI that automates patient scheduling, intake forms, and follow-ups — saving your staff 20+ hours/week",
    "medical": "We build AI that automates patient scheduling, intake forms, and follow-ups — saving your staff 20+ hours/week",
    "dental": "We build AI assistants that handle appointment scheduling, insurance verification, and patient reminders automatically",
    "legal": "We build AI that automates document review, client intake, and contract analysis — cutting paralegal costs by 40%",
    "law": "We build AI that automates document review, client intake, and contract analysis — cutting paralegal costs by 40%",
    "financial": "We build AI that automates client onboarding, compliance reporting, and portfolio summaries — freeing advisors for high-value work",
    "wealth": "We build AI that automates client onboarding, compliance reporting, and portfolio summaries — freeing advisors for high-value work",
    "insurance": "We build AI that automates quote comparisons, claims processing, and policy renewals — 3x faster than manual",
    "marketing": "We build AI that automates reporting, content drafts, and client communications — so your team focuses on strategy",
    "agency": "We build AI that automates reporting, content drafts, and client communications — so your team focuses on strategy",
    "logistics": "We build AI that optimizes route planning, automates dispatch, and predicts delivery times with 95% accuracy",
    "freight": "We build AI that optimizes route planning, automates dispatch, and predicts delivery times with 95% accuracy",
    "real estate": "We build AI that automates lead follow-up, property descriptions, and market analysis — closing deals 2x faster",
    "property": "We build AI that automates tenant communications, maintenance requests, and lease renewals automatically",
    "manufacturing": "We build AI for predictive maintenance, quality inspection, and production scheduling — reducing downtime 30%",
    "staffing": "We build AI that screens resumes, matches candidates, and automates outreach — filling roles 50% faster",
    "recruiting": "We build AI that screens resumes, matches candidates, and automates outreach — filling roles 50% faster",
    "construction": "We build AI that automates estimating, project scheduling, and subcontractor communications",
    "e-commerce": "We build AI that writes product descriptions, handles customer support, and optimizes inventory automatically",
    "retail": "We build AI that personalizes customer experiences, automates inventory, and predicts demand",
    "consulting": "We build AI that automates proposal generation, client reporting, and knowledge management",
    "saas": "We build AI that automates customer onboarding, support ticket routing, and churn prediction",
    "software": "We build AI copilots that accelerate development, automate testing, and handle DevOps tasks",
    "education": "We build AI tutors, automated grading systems, and personalized learning platforms",
    "restaurant": "We build AI that optimizes staffing, automates ordering, and manages inventory across locations",
    "accounting": "We build AI that automates bookkeeping, tax prep, and financial reporting — 5x faster",
}

DEFAULT_HOOK = "We build custom AI automation that eliminates repetitive tasks and scales your operations — typical ROI is 3-5x in the first 90 days"

# DISC quick profiler keywords
DISC_KEYWORDS = {
    "D": ["results", "growth", "revenue", "scale", "win", "fast", "aggressive", "dominate", "lead", "drive"],
    "I": ["team", "culture", "vision", "inspire", "community", "creative", "passion", "innovative", "fun"],
    "S": ["support", "help", "care", "trust", "reliable", "steady", "family", "serve", "loyal", "dedicated"],
    "C": ["data", "process", "system", "analysis", "quality", "precision", "detail", "research", "optimize"],
}


# ═══════════════════════════════════════════════════════════════════
#  APOLLO API
# ═══════════════════════════════════════════════════════════════════

def apollo_search_people(keywords, titles, location="United States",
                         employee_range=["11,50", "51,200", "201,500"],
                         pages=2):
    """Search Apollo for decision makers at target companies."""
    all_people = []
    seen = set()

    for page in range(1, pages + 1):
        payload = {
            "page": page,
            "per_page": 25,
            "person_titles": titles,
            "q_organization_keyword_tags": keywords,
            "person_locations": [location],
            "organization_num_employees_ranges": employee_range,
        }

        try:
            r = requests.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json=payload, headers=HEADERS_APOLLO, timeout=30,
            )
            if r.status_code != 200:
                print(f"    Apollo error {r.status_code}: {r.text[:100]}")
                break

            data = r.json()
            people = data.get("people", [])
            total = data.get("pagination", {}).get("total_entries", "?")
            print(f"    [{', '.join(keywords[:2])}] page {page}: {len(people)} people (total pool: {total})")

            for p in people:
                email = p.get("email", "") or ""
                name = p.get("name", "") or f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                org = p.get("organization", {}) or {}

                key = (name.lower(), (org.get("name") or "").lower())
                if key in seen:
                    continue
                seen.add(key)

                all_people.append({
                    "full_name": name,
                    "first_name": p.get("first_name", ""),
                    "last_name": p.get("last_name", ""),
                    "title": p.get("title", ""),
                    "email": email,
                    "email_status": p.get("email_status", ""),
                    "phone": (p.get("phone_numbers") or [{}])[0].get("sanitized_number", "") if p.get("phone_numbers") else "",
                    "linkedin": p.get("linkedin_url", ""),
                    "city": p.get("city", ""),
                    "state": p.get("state", ""),
                    "company": org.get("name", ""),
                    "company_website": org.get("website_url", ""),
                    "company_linkedin": org.get("linkedin_url", ""),
                    "company_industry": org.get("industry", ""),
                    "company_employees": org.get("estimated_num_employees", ""),
                    "company_revenue": org.get("estimated_annual_revenue", ""),
                    "company_founded": org.get("founded_year", ""),
                    "source": "apollo_people",
                })

            if len(people) < 25:
                break
            time.sleep(1)  # Rate limit

        except Exception as e:
            print(f"    Error: {e}")
            break

    return all_people


def apollo_search_companies_v2(keywords, pages=2):
    """Search Apollo for companies."""
    all_orgs = []
    seen = set()

    for page in range(1, pages + 1):
        payload = {
            "page": page,
            "per_page": 25,
            "q_organization_keyword_tags": keywords,
            "organization_locations": ["United States"],
            "organization_num_employees_ranges": ["11,50", "51,200", "201,500"],
        }

        try:
            r = requests.post(
                "https://api.apollo.io/v1/organizations/search",
                json=payload, headers=HEADERS_APOLLO, timeout=30,
            )
            if r.status_code != 200:
                break

            data = r.json()
            orgs = data.get("organizations", [])

            for o in orgs:
                name = o.get("name", "")
                domain = o.get("primary_domain") or ""
                key = domain.lower() if domain else name.lower()
                if key in seen:
                    continue
                seen.add(key)

                all_orgs.append({
                    "company": name,
                    "website": o.get("website_url", ""),
                    "linkedin": o.get("linkedin_url", ""),
                    "industry": o.get("industry", ""),
                    "employees": o.get("estimated_num_employees", ""),
                    "city": o.get("city", ""),
                    "state": o.get("state", ""),
                    "phone": o.get("phone", ""),
                    "founded_year": o.get("founded_year", ""),
                    "source": "apollo_company",
                })

            if len(orgs) < 25:
                break
            time.sleep(1)

        except Exception as e:
            print(f"    Error: {e}")
            break

    return all_orgs


# ═══════════════════════════════════════════════════════════════════
#  APIFY GOOGLE MAPS
# ═══════════════════════════════════════════════════════════════════

def apify_run_actor(actor_id, run_input, wait_secs=300):
    """Run Apify actor and get results."""
    print(f"    Starting Apify actor {actor_id.split('~')[1] if '~' in actor_id else actor_id}...")
    try:
        r = requests.post(
            f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}",
            json=run_input, timeout=30,
        )
        if r.status_code not in [200, 201]:
            print(f"    Apify start failed: {r.status_code}")
            return []

        run_data = r.json().get("data", {})
        run_id = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId")

        for i in range(wait_secs // 10):
            r2 = requests.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
            )
            status = r2.json().get("data", {}).get("status", "UNKNOWN")
            if status == "SUCCEEDED":
                print(f"    Actor completed in ~{(i+1)*10}s")
                break
            if status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                print(f"    Actor {status}")
                return []
            time.sleep(10)
        else:
            print("    Timed out")
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

        return all_items

    except Exception as e:
        print(f"    Apify error: {e}")
        return []


def google_maps_prospect(queries, max_per_query=15):
    """Scrape Google Maps for businesses."""
    run_input = {
        "searchStringsArray": queries,
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
        website = item.get("website", "")
        key = website.lower() if website else title.lower()
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "company": title,
            "phone": item.get("phone", ""),
            "website": website,
            "email": "",
            "city": item.get("city", ""),
            "state": item.get("state", ""),
            "industry": item.get("categoryName", ""),
            "rating": item.get("totalScore", ""),
            "reviews": item.get("reviewsCount", ""),
            "address": item.get("address", ""),
            "source": "google_maps",
        })

    return results


# ═══════════════════════════════════════════════════════════════════
#  WEBSITE SCRAPER (contact extraction)
# ═══════════════════════════════════════════════════════════════════

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
JUNK_EMAILS = {'noreply', 'no-reply', 'donotreply', 'mailer-daemon', 'postmaster',
               'webmaster', 'sentry', 'wixpress', 'wordpress', 'gravatar',
               'example.com', 'email.com', 'youremail', 'your@email'}


def scrape_contact_from_website(url):
    """Extract email and phone from a website."""
    if not url:
        return "", ""

    if not url.startswith("http"):
        url = f"https://{url}"

    emails_found = set()
    phones_found = set()

    for path in ["", "/contact", "/about", "/contact-us"]:
        try:
            r = requests.get(url + path, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if r.status_code != 200:
                continue

            text = r.text[:50000]  # Limit to 50KB

            for email in EMAIL_RE.findall(text):
                email_lower = email.lower()
                if not any(j in email_lower for j in JUNK_EMAILS):
                    if not email_lower.endswith(('.png', '.jpg', '.svg', '.gif', '.css', '.js')):
                        emails_found.add(email)

            for phone in PHONE_RE.findall(text):
                digits = re.sub(r'\D', '', phone)
                if 10 <= len(digits) <= 11:
                    phones_found.add(phone)

        except Exception:
            continue

    email = sorted(emails_found)[0] if emails_found else ""
    phone = sorted(phones_found)[0] if phones_found else ""
    return email, phone


# ═══════════════════════════════════════════════════════════════════
#  DISC PROFILER
# ═══════════════════════════════════════════════════════════════════

def quick_disc(text):
    """Quick DISC profile from any text (title, industry, company description)."""
    if not text:
        return "C", "Analytical"

    text_lower = text.lower()
    scores = {t: 0 for t in "DISC"}

    for disc_type, keywords in DISC_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[disc_type] += 1

    primary = max(scores, key=scores.get)
    if scores[primary] == 0:
        # Default based on title patterns
        if any(w in text_lower for w in ["ceo", "founder", "president", "owner"]):
            return "D", "Results-driven, direct, bottom-line focused"
        elif any(w in text_lower for w in ["sales", "marketing", "creative", "brand"]):
            return "I", "Enthusiastic, relationship-oriented, big-picture"
        elif any(w in text_lower for w in ["operations", "hr", "support", "manager"]):
            return "S", "Steady, supportive, team-oriented"
        else:
            return "C", "Analytical, detail-oriented, process-driven"

    profiles = {
        "D": "Results-driven, direct, bottom-line focused",
        "I": "Enthusiastic, relationship-oriented, big-picture",
        "S": "Steady, supportive, team-oriented",
        "C": "Analytical, detail-oriented, process-driven",
    }
    return primary, profiles[primary]


def disc_outreach_style(disc_type):
    """Get outreach approach per DISC type."""
    styles = {
        "D": {
            "approach": "Be direct, lead with ROI numbers, keep it short",
            "opening": "I'll get straight to it —",
            "avoid": "Don't ramble or be vague. No fluff.",
            "subject_style": "ROI-focused, numbers in subject line",
        },
        "I": {
            "approach": "Be enthusiastic, paint the vision, use social proof",
            "opening": "I love what you're building at",
            "avoid": "Don't lead with data dumps or technical specs",
            "subject_style": "Vision-oriented, exciting language",
        },
        "S": {
            "approach": "Be warm, show you care about their team, offer support",
            "opening": "I noticed your team has been doing incredible work at",
            "avoid": "Don't pressure or use urgency tactics",
            "subject_style": "Helpful, team-focused, supportive",
        },
        "C": {
            "approach": "Lead with data, specifics, and logical arguments",
            "opening": "Based on our analysis of companies like",
            "avoid": "Don't make vague claims without backing them up",
            "subject_style": "Specific, data-backed, methodical",
        },
    }
    return styles.get(disc_type, styles["C"])


# ═══════════════════════════════════════════════════════════════════
#  OUTREACH GENERATOR
# ═══════════════════════════════════════════════════════════════════

def get_ai_hook(industry):
    """Get the best AI solution hook for an industry."""
    industry_lower = (industry or "").lower()
    for key, hook in AI_HOOKS.items():
        if key in industry_lower:
            return hook
    return DEFAULT_HOOK


def generate_outreach(lead):
    """Generate personalized outreach for a lead."""
    name = lead.get("full_name") or lead.get("first_name") or ""
    first_name = name.split()[0] if name else "there"
    company = lead.get("company", "your company")
    industry = lead.get("company_industry") or lead.get("industry") or ""
    title = lead.get("title", "")

    disc_type, disc_profile = quick_disc(f"{title} {industry} {company}")
    style = disc_outreach_style(disc_type)
    hook = get_ai_hook(industry)

    # Generate personalized subject
    subjects = {
        "D": f"{company} + AI = 3x faster operations",
        "I": f"The AI vision for {company}'s next chapter",
        "S": f"Supporting {company}'s team with AI automation",
        "C": f"AI automation ROI analysis for {company}",
    }

    # Generate personalized opening
    openings = {
        "D": f"Hi {first_name}, I'll be direct — {hook.lower()}. For a company like {company}, that typically means $50K-$200K in annual savings.",
        "I": f"Hi {first_name}, {style['opening']} {company}! {hook}. I'd love to explore what's possible together.",
        "S": f"Hi {first_name}, {style['opening']} {company}. {hook}. We'd be happy to show you exactly how it works — no pressure.",
        "C": f"Hi {first_name}, {style['opening']} {company}, we've found that {hook.lower()}. Here are the specifics:",
    }

    return {
        "disc_type": disc_type,
        "disc_profile": disc_profile,
        "subject_line": subjects.get(disc_type, subjects["C"]),
        "email_opening": openings.get(disc_type, openings["C"]),
        "outreach_approach": style["approach"],
        "avoid": style["avoid"],
        "ai_hook": hook,
    }


# ═══════════════════════════════════════════════════════════════════
#  LEAD SCORING
# ═══════════════════════════════════════════════════════════════════

def score_5k_buyer(lead):
    """Score how likely this lead is to pay $5K for AI (0-100)."""
    score = 0

    # Contact quality
    if lead.get("email"):
        score += 20
        email = lead["email"].lower()
        if not any(g in email for g in ['gmail.com', 'yahoo.com', 'hotmail.com']):
            score += 5  # Business email
    if lead.get("phone"):
        score += 10
    if lead.get("linkedin"):
        score += 5

    # Decision maker quality
    title = (lead.get("title") or "").lower()
    if any(t in title for t in ["ceo", "founder", "owner", "president"]):
        score += 20  # Ultimate decision maker
    elif any(t in title for t in ["coo", "cto", "cfo", "partner", "managing"]):
        score += 15
    elif any(t in title for t in ["vp", "vice president", "director", "head of"]):
        score += 10
    elif lead.get("full_name"):
        score += 5

    # Company size (10-500 is sweet spot for $5K deals)
    employees = lead.get("company_employees") or lead.get("employees") or ""
    try:
        emp = int(str(employees).replace(",", "").split("-")[0].split("+")[0])
        if 10 <= emp <= 50:
            score += 10
        elif 50 < emp <= 200:
            score += 15  # Sweet spot
        elif 200 < emp <= 500:
            score += 12
        elif emp > 500:
            score += 8
    except (ValueError, IndexError):
        pass

    # Industry value (how much they need AI)
    industry = (lead.get("company_industry") or lead.get("industry") or "").lower()
    tier1 = ["healthcare", "medical", "dental", "legal", "law", "financial", "wealth",
             "insurance", "real estate", "property"]
    tier2 = ["marketing", "agency", "logistics", "freight", "manufacturing",
             "staffing", "recruiting", "construction", "accounting"]
    tier3 = ["consulting", "saas", "software", "e-commerce", "retail", "education"]

    if any(t in industry for t in tier1):
        score += 15
    elif any(t in industry for t in tier2):
        score += 12
    elif any(t in industry for t in tier3):
        score += 10

    return min(score, 100)


# ═══════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════

def run_vibe_prospecting():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    print("""
╔══════════════════════════════════════════════════════════════╗
║              VIBE PROSPECTING ENGINE v1.0                   ║
║         Finding $5K AI buyers across the USA                ║
╠══════════════════════════════════════════════════════════════╣
║  Channels: Apollo API + Google Maps + Web Scraping          ║
║  Target: SMBs (10-500 employees) in high-AI-need industries ║
║  Goal: 100 qualified leads with outreach hooks              ║
╚══════════════════════════════════════════════════════════════╝
""")

    all_leads = []

    # ────────────────────────────────────────────────────────────
    #  CHANNEL 1: Apollo People Search
    # ────────────────────────────────────────────────────────────
    print("━" * 60)
    print("  CHANNEL 1: APOLLO API — Decision Maker Search")
    print("━" * 60)

    apollo_leads = []
    for batch in APOLLO_SEARCH_BATCHES:
        results = apollo_search_people(
            keywords=batch["keywords"],
            titles=batch["titles"],
            pages=2,
        )
        apollo_leads.extend(results)
        time.sleep(1)

    print(f"\n  Apollo total: {len(apollo_leads)} decision makers found")
    all_leads.extend(apollo_leads)

    # ────────────────────────────────────────────────────────────
    #  CHANNEL 2: Google Maps Scraping
    # ────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  CHANNEL 2: GOOGLE MAPS — Local Business Discovery")
    print("━" * 60)

    gmaps_leads = google_maps_prospect(GMAPS_QUERIES, max_per_query=15)
    print(f"\n  Google Maps total: {len(gmaps_leads)} businesses found")

    # Enrich Google Maps leads with website scraping
    print("  Scraping websites for contacts...")
    enriched_count = 0
    for lead in gmaps_leads:
        if lead.get("website") and not lead.get("email"):
            email, phone = scrape_contact_from_website(lead["website"])
            if email:
                lead["email"] = email
                enriched_count += 1
            if phone and not lead.get("phone"):
                lead["phone"] = phone
    print(f"  Enriched {enriched_count} leads with email from websites")

    # Convert gmaps to standard format
    for lead in gmaps_leads:
        lead["full_name"] = ""
        lead["first_name"] = ""
        lead["last_name"] = ""
        lead["title"] = ""
        lead["linkedin"] = ""
        lead["company_industry"] = lead.get("industry", "")
        lead["company_employees"] = ""
        lead["company_website"] = lead.get("website", "")
    all_leads.extend(gmaps_leads)

    # ────────────────────────────────────────────────────────────
    #  CHANNEL 3: 1000-Company Enriched Database (POWER SOURCE)
    # ────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  CHANNEL 3: 1000-COMPANY DATABASE — High-Value Targets")
    print("━" * 60)

    db_count = 0
    db_path = "/home/user/XML-to-Supabase/AI_CLIENTS_1000_FULL_ENRICHED.csv"
    if os.path.exists(db_path):
        with open(db_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                state = row.get("State", "")
                city = row.get("City", "")
                if not state:
                    continue

                email = row.get("Contact_Email", "") or ""
                alt_email = row.get("Alt_Emails", "")
                phone = row.get("Contact_Phone", "") or ""
                alt_phone = row.get("Alt_Phones", "")

                # Try alt sources if primary missing
                if not email and alt_email:
                    email = alt_email.split(",")[0].strip()
                if not phone and alt_phone:
                    phone = alt_phone.split(";")[0].strip()

                lead = {
                    "full_name": row.get("DM_Name", "") or "",
                    "first_name": "",
                    "last_name": "",
                    "title": row.get("Decision_Maker_Title", ""),
                    "email": email,
                    "phone": phone,
                    "linkedin": row.get("LinkedIn_Company", ""),
                    "company": row.get("Company_Name", ""),
                    "company_website": row.get("Website", ""),
                    "company_industry": row.get("Industry_Vertical", ""),
                    "company_employees": row.get("Estimated_Employees", ""),
                    "company_revenue": row.get("Estimated_Revenue_Range", ""),
                    "industry": row.get("Industry_Vertical", ""),
                    "location": f"{city}, {state}",
                    "ai_use_case": row.get("AI_Automation_Use_Case", ""),
                    "deal_size": row.get("Estimated_Deal_Size", ""),
                    "dm_email_patterns": row.get("DM_Email_Patterns", ""),
                    "twitter": row.get("Twitter", ""),
                    "facebook": row.get("Facebook", ""),
                    "source": "1000_database",
                }
                all_leads.append(lead)
                db_count += 1
        print(f"  Loaded {db_count} leads from 1000-company database")
    else:
        print("  1000-company database not found!")

    # ────────────────────────────────────────────────────────────
    #  CHANNEL 4: Other Existing Databases
    # ────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  CHANNEL 4: EXISTING DATABASES — Mining All Sources")
    print("━" * 60)

    existing_count = 0
    for csvfile in [
        "MASTER_AI_LEADS.csv",
        "CHEERIO_ENRICHED_LEADS.csv",
    ]:
        filepath = f"/home/user/XML-to-Supabase/{csvfile}"
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    loc = (row.get("location") or "").lower()
                    # Only USA
                    us_indicators = ["us", "usa", "united states", " ca", " ny", " tx", " fl",
                                    " il", " ga", " wa", " co", " nc", " oh", " pa", " ma"]
                    if not any(ind in loc for ind in us_indicators):
                        continue

                    lead = {
                        "full_name": row.get("founder") or row.get("team_members", "").split(";")[0].strip() if row.get("team_members") else "",
                        "first_name": "",
                        "last_name": "",
                        "title": "Founder/CEO" if row.get("founder") else "",
                        "email": row.get("email") or (row.get("emails","").split(";")[0].strip() if row.get("emails") else ""),
                        "phone": row.get("phone") or (row.get("phones","").split(";")[0].strip() if row.get("phones") else ""),
                        "linkedin": row.get("linkedin", ""),
                        "company": row.get("company", ""),
                        "company_website": row.get("website", ""),
                        "company_industry": row.get("industry", ""),
                        "company_employees": "",
                        "industry": row.get("industry", ""),
                        "location": row.get("location", ""),
                        "source": f"existing_{csvfile}",
                    }
                    all_leads.append(lead)
                    existing_count += 1
        except Exception as e:
            print(f"    Error reading {csvfile}: {e}")

    print(f"  Mined {existing_count} leads from other databases")

    # ────────────────────────────────────────────────────────────
    #  CHANNEL 5: Live Website Scraping for Missing Emails
    # ────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  CHANNEL 5: LIVE SCRAPING — Extracting Fresh Emails")
    print("━" * 60)

    # Collect leads that have a website but no email
    needs_email = [l for l in all_leads if l.get("company_website") and not l.get("email")]
    # Prioritize high-value industries
    tier1_kw = ["healthcare", "medical", "dental", "legal", "law", "financial",
                "wealth", "insurance", "real estate", "property"]
    tier1_needs = [l for l in needs_email if any(k in (l.get("company_industry") or "").lower() for k in tier1_kw)]
    tier2_needs = [l for l in needs_email if l not in tier1_needs]

    # Scrape top priority leads first
    to_scrape = (tier1_needs[:60] + tier2_needs[:40])
    print(f"  Scraping {len(to_scrape)} websites for emails (Tier 1: {min(len(tier1_needs),60)}, Tier 2: {min(len(tier2_needs),40)})...")

    scraped_count = 0
    def scrape_one(lead):
        email, phone = scrape_contact_from_website(lead["company_website"])
        return lead, email, phone

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape_one, lead): lead for lead in to_scrape}
        for future in as_completed(futures):
            try:
                lead, email, phone = future.result()
                if email:
                    lead["email"] = email
                    scraped_count += 1
                if phone and not lead.get("phone"):
                    lead["phone"] = phone
            except Exception:
                pass

    print(f"  Scraped {scraped_count} fresh emails from live websites")

    # ────────────────────────────────────────────────────────────
    #  DEDUP + SCORE + RANK
    # ────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  PROCESSING: Dedup → Score → Rank → Profile")
    print("━" * 60)

    # Deduplicate
    seen = {}
    unique_leads = []
    for lead in all_leads:
        website = (lead.get("company_website") or lead.get("website") or "").lower()
        website = re.sub(r'^https?://', '', website)
        website = re.sub(r'^www\.', '', website)
        website = website.rstrip("/")

        company = (lead.get("company") or "").lower().strip()
        name = (lead.get("full_name") or "").lower().strip()
        key = f"{website or company}:{name}"

        if key in seen:
            existing = seen[key]
            for field in ["email", "phone", "linkedin", "full_name", "title",
                         "company_industry", "company_employees"]:
                if not existing.get(field) and lead.get(field):
                    existing[field] = lead[field]
        else:
            seen[key] = lead
            unique_leads.append(lead)

    print(f"  Total raw:     {len(all_leads)}")
    print(f"  After dedup:   {len(unique_leads)}")

    # Score each lead
    for lead in unique_leads:
        lead["score"] = score_5k_buyer(lead)

    # Filter: must have email or phone
    contactable = [l for l in unique_leads if l.get("email") or l.get("phone")]
    print(f"  Contactable:   {len(contactable)}")

    # Sort by score
    contactable.sort(key=lambda x: x["score"], reverse=True)

    # Take top 100
    top = contactable[:100]

    # ────────────────────────────────────────────────────────────
    #  DISC PROFILE + OUTREACH GENERATION
    # ────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  OUTREACH: DISC Profiling + Personalized Hooks")
    print("━" * 60)

    for lead in top:
        outreach = generate_outreach(lead)
        lead.update(outreach)

    # ────────────────────────────────────────────────────────────
    #  SAVE OUTPUT
    # ────────────────────────────────────────────────────────────
    output_path = f"/home/user/XML-to-Supabase/VIBE_PROSPECTS_{timestamp}.csv"

    fieldnames = [
        "rank", "score", "full_name", "title", "email", "phone", "linkedin",
        "company", "company_website", "company_industry", "company_employees",
        "location", "disc_type", "disc_profile", "subject_line",
        "email_opening", "outreach_approach", "ai_hook", "avoid", "source",
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for i, lead in enumerate(top, 1):
            lead["rank"] = i
            # Fill location if missing
            if not lead.get("location"):
                city = lead.get("city", "")
                state = lead.get("state", "")
                lead["location"] = f"{city}, {state}".strip(", ")
            writer.writerow({k: lead.get(k, "") for k in fieldnames})

    # Also save as the permanent file
    import shutil
    shutil.copy(output_path, "/home/user/XML-to-Supabase/VIBE_PROSPECTS_LATEST.csv")

    # ────────────────────────────────────────────────────────────
    #  RESULTS
    # ────────────────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               VIBE PROSPECTING COMPLETE                     ║
╠══════════════════════════════════════════════════════════════╣
║  Total leads found:        {len(all_leads):<30}║
║  Unique after dedup:       {len(unique_leads):<30}║
║  Contactable:              {len(contactable):<30}║
║  Top prospects:            {len(top):<30}║
╠══════════════════════════════════════════════════════════════╣
║  With email:               {sum(1 for l in top if l.get('email')):<30}║
║  With phone:               {sum(1 for l in top if l.get('phone')):<30}║
║  With LinkedIn:            {sum(1 for l in top if l.get('linkedin')):<30}║
║  With decision maker:      {sum(1 for l in top if l.get('full_name')):<30}║
║  Avg quality score:        {sum(l['score'] for l in top) / max(len(top),1):.1f}/100{' '*24}║
╠══════════════════════════════════════════════════════════════╣
║  Output: {output_path:<51}║
║  Also:   VIBE_PROSPECTS_LATEST.csv                          ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Print top 25 preview
    print("━" * 100)
    print(f"  {'#':<4} {'Score':<6} {'Name':<25} {'Title':<22} {'Company':<22} {'DISC':<4} {'Contact':<30}")
    print("━" * 100)

    for i, lead in enumerate(top[:25], 1):
        name = (lead.get("full_name") or "—")[:23]
        title = (lead.get("title") or "—")[:20]
        company = (lead.get("company") or "—")[:20]
        disc = lead.get("disc_type", "?")
        contact = (lead.get("email") or lead.get("phone") or "—")[:28]
        print(f"  {i:<4} {lead['score']:<6} {name:<25} {title:<22} {company:<22} {disc:<4} {contact:<30}")

    print("━" * 100)

    # Industry breakdown
    industries = {}
    for l in top:
        ind = l.get("company_industry") or l.get("industry") or "Unknown"
        industries[ind] = industries.get(ind, 0) + 1

    print("\n  INDUSTRY BREAKDOWN:")
    for ind, count in sorted(industries.items(), key=lambda x: -x[1])[:10]:
        bar = "█" * count
        print(f"    {ind[:35]:<36} {count:>3} {bar}")

    # DISC breakdown
    disc_counts = {}
    for l in top:
        d = l.get("disc_type", "?")
        disc_counts[d] = disc_counts.get(d, 0) + 1

    print("\n  DISC PERSONALITY BREAKDOWN:")
    disc_labels = {"D": "Dominant (direct, ROI)", "I": "Influential (vision, social proof)",
                   "S": "Steady (supportive, trust)", "C": "Conscientious (data, specifics)"}
    for d, label in disc_labels.items():
        count = disc_counts.get(d, 0)
        bar = "█" * count
        print(f"    {d} - {label:<40} {count:>3} {bar}")

    return output_path


if __name__ == "__main__":
    run_vibe_prospecting()
