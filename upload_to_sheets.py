#!/usr/bin/env python3
"""
Upload AI Clients database to Google Sheets using Service Account.
Creates a 4-sheet spreadsheet with all data and formatting.
"""

import csv
import json
import time
import jwt
import urllib.request
import ssl
from datetime import datetime, timezone

# ── Config ──
SA_FILE = "/home/user/XML-to-Supabase/service_account.json"
CSV_FILE = "/home/user/XML-to-Supabase/AI_CLIENTS_1000_DATABASE.csv"
SCOPES = "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive"

# SSL context for this environment
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get_access_token(sa_path):
    """Generate OAuth2 access token from service account JSON using JWT."""
    with open(sa_path) as f:
        sa = json.load(f)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": sa["client_email"],
        "scope": SCOPES,
        "aud": sa["token_uri"],
        "iat": now,
        "exp": now + 3600,
    }

    token = jwt.encode(payload, sa["private_key"], algorithm="RS256")

    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": token,
    }).encode()

    req = urllib.request.Request(sa["token_uri"], data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, context=ctx) as resp:
        result = json.loads(resp.read())
    return result["access_token"]


def api(url, method="GET", body=None, token=None):
    """Make an authenticated Google API request."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"❌ HTTP {e.code}: {err_body[:500]}")
        raise


import urllib.parse


def main():
    # ── Step 1: Authenticate ──
    print("🔐 Authenticating with Google...")
    token = get_access_token(SA_FILE)
    print("✅ Authenticated\n")

    # ── Step 2: Create Spreadsheet ──
    print("📄 Creating Google Spreadsheet...")
    create_body = {
        "properties": {"title": "AI Clients 1000 — Prospecting Database"},
        "sheets": [
            {"properties": {"sheetId": 0, "title": "1000 Companies Database", "index": 0,
                            "gridProperties": {"frozenRowCount": 1}}},
            {"properties": {"sheetId": 1, "title": "Prospecting Guide", "index": 1}},
            {"properties": {"sheetId": 2, "title": "Lead Sources Guide", "index": 2}},
            {"properties": {"sheetId": 3, "title": "Verticals Summary", "index": 3,
                            "gridProperties": {"frozenRowCount": 1}}},
        ],
    }
    result = api("https://sheets.googleapis.com/v4/spreadsheets", "POST", create_body, token)
    sid = result["spreadsheetId"]
    url = f"https://docs.google.com/spreadsheets/d/{sid}"
    print(f"✅ Created: {url}\n")

    # ── Step 3: Load CSV ──
    print("📊 Loading CSV data...")
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        csv_data = list(csv.reader(f))
    print(f"   {len(csv_data)} rows (header + {len(csv_data)-1} companies)\n")

    # ── Step 4: Populate Sheet 1 — Companies Database ──
    print("📝 Writing Sheet 1: 1000 Companies Database...")
    batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values:batchUpdate"
    api(batch_url, "POST", {
        "valueInputOption": "RAW",
        "data": [{"range": "'1000 Companies Database'!A1", "values": csv_data}]
    }, token)
    print("✅ Sheet 1 done\n")

    # ── Step 5: Populate Sheet 2 — Prospecting Guide ──
    print("📝 Writing Sheet 2: Prospecting Guide...")

    guide_data = []
    guide_data.append(["AI AUTOMATION SERVICES — PROSPECTING GUIDE", "", "", "", ""])
    guide_data.append([])

    # Use Cases Table
    guide_data.append(["AI AUTOMATION USE CASES PER VERTICAL", "", "", ""])
    guide_data.append(["Vertical", "Primary Use Case", "Secondary Use Case", "Tertiary Use Case"])
    use_cases = [
        ["Healthcare", "Patient scheduling AI", "Medical billing automation", "EHR integration"],
        ["Legal", "Document review AI", "Contract analysis", "Client intake automation"],
        ["Real Estate", "Lead qualification AI", "Listing automation", "Tenant screening"],
        ["Accounting", "Tax automation", "Audit AI analytics", "Client onboarding"],
        ["Construction", "Project management AI", "Estimating automation", "Safety compliance"],
        ["eCommerce", "Customer service AI", "Inventory automation", "Personalization engines"],
        ["Fitness", "Member retention AI", "Scheduling automation", "Lead nurturing"],
        ["Insurance", "Claims processing AI", "Underwriting automation", "Lead scoring"],
        ["Staffing", "Resume screening AI", "Candidate matching", "Interview scheduling"],
        ["Marketing", "Content generation AI", "Reporting automation", "Campaign optimization"],
        ["Manufacturing", "Quality control AI", "Predictive maintenance", "Supply chain automation"],
        ["Logistics", "Route optimization AI", "Shipment tracking", "Demand forecasting"],
        ["Restaurants", "Inventory AI", "Staff scheduling", "Customer feedback"],
        ["Auto Dealerships", "Lead follow-up AI", "Inventory management", "Service scheduling"],
        ["Home Services", "Dispatch AI", "Lead qualification", "Estimate automation"],
        ["SaaS", "Customer onboarding AI", "Churn prediction", "Support automation"],
        ["EdTech", "Student engagement AI", "Grading automation", "Enrollment optimization"],
        ["Veterinary", "Appointment scheduling AI", "Pet health records", "Follow-up automation"],
        ["Dental (DSO)", "Patient scheduling AI", "Treatment plan AI", "Billing automation"],
        ["Senior Care", "Caregiver scheduling AI", "Patient monitoring", "Compliance automation"],
        ["Financial Advisory", "Portfolio reporting AI", "Client communication", "Compliance automation"],
        ["Pest Control/Cleaning", "Route optimization AI", "Scheduling", "Customer retention"],
        ["Printing/Packaging", "Order processing AI", "Estimating", "Quality control"],
        ["Nonprofits", "Donor management AI", "Grant writing", "Event automation"],
        ["Telehealth", "Patient triage AI", "Scheduling", "Follow-up automation"],
    ]
    guide_data.extend(use_cases)
    guide_data.append([])

    # Pricing
    guide_data.append(["PRICING STRATEGY ($5K–$50K)", "", "", "", ""])
    guide_data.append(["Tier", "Price Range", "Target", "What's Included", "Best For"])
    guide_data.append(["Starter", "$5,000–$10,000", "Small biz, single-location, startups", "1 AI workflow, basic integration, 30-day setup + 30-day support", "Small DTC brands, single-location practices, small nonprofits"])
    guide_data.append(["Growth", "$10,000–$20,000", "Multi-location, 50-500 employees", "2-3 AI workflows, CRM/EHR integrations, 60-day impl + 90-day support, training (10 users)", "Regional CPA firms, mid-size law firms, franchise locations"])
    guide_data.append(["Professional", "$20,000–$35,000", "Large multi-location, 500-5000 employees", "5-7 AI workflows, enterprise API integrations, 90-day impl + 6-mo support, analytics dashboard", "DSO chains, auto dealer groups, property mgmt, staffing firms"])
    guide_data.append(["Enterprise", "$35,000–$50,000", "Large enterprises, national chains, F500 depts", "Custom AI architecture, full multi-platform integration, 120-day impl + 12-mo support, dedicated AM", "Healthcare systems, BigLaw, national insurers, large 3PLs"])
    guide_data.append([])

    # Lead Scoring
    guide_data.append(["LEAD SCORING METHODOLOGY", "", "", "", ""])
    guide_data.append(["Factor", "Weight", "Score 5 (Highest)", "Score 3 (Medium)", "Score 1 (Lowest)"])
    guide_data.append(["Company Size", "25%", "500+ employees, multi-location", "50-500 employees", "Under 50 employees"])
    guide_data.append(["Revenue", "20%", "$500M+", "$25M-$500M", "Under $25M"])
    guide_data.append(["Tech Readiness", "20%", "Active tech investment, CTO role", "Some tech adoption", "Minimal tech stack"])
    guide_data.append(["Pain Point Severity", "20%", "Critical operational bottleneck", "Moderate inefficiency", "Nice-to-have"])
    guide_data.append(["Decision-Maker Access", "15%", "C-suite accessible", "VP/Director level", "Owner/single DM"])
    guide_data.append([])

    # Score Distribution
    guide_data.append(["SCORE DISTRIBUTION & EXPECTED CLOSE RATES", "", "", "", ""])
    guide_data.append(["Score", "# Companies", "Action", "Expected Close Rate", "Outreach Timing"])
    guide_data.append(["5", "192", "Immediate outreach — personalized email + LinkedIn + call", "5–8%", "Week 1"])
    guide_data.append(["4", "264", "High priority — personalized email + LinkedIn", "3–5%", "Week 2"])
    guide_data.append(["3", "336", "Medium priority — nurture campaigns", "1–3%", "Month 1"])
    guide_data.append(["2", "144", "Lower priority — $5K–$10K offers", "0.5–1%", "Month 2"])
    guide_data.append(["1", "64", "Long-term — newsletter + quarterly check-in", "< 0.5%", "Ongoing"])
    guide_data.append([])

    # Follow-Up Sequences
    guide_data.append(["FOLLOW-UP SEQUENCE A: HIGH PRIORITY (Score 4–5)", "", ""])
    guide_data.append(["Day", "Channel", "Action"])
    for row in [["1","Email","Cold outreach (Template 1)"],["2","LinkedIn","Connection request + personalized note"],
                ["4","Phone","Cold call"],["7","Email","Follow-up with case study (Template 2)"],
                ["10","LinkedIn","Share relevant industry content"],["14","Email","Final follow-up (Template 3)"],
                ["21","Phone","Second call attempt"],["30","Email","Break-up email — check back in 3 months"]]:
        guide_data.append(row)
    guide_data.append([])

    guide_data.append(["FOLLOW-UP SEQUENCE B: MEDIUM PRIORITY (Score 3)", "", ""])
    guide_data.append(["Day", "Channel", "Action"])
    for row in [["1","Email","Industry-specific cold outreach"],["5","LinkedIn","Connection request"],
                ["10","Email","Follow-up with ROI calculator"],["17","Email","Case study for their vertical"],
                ["25","LinkedIn","Engage with their content"],["35","Email","Invitation to webinar or demo"],
                ["45","Email","Final follow-up"]]:
        guide_data.append(row)
    guide_data.append([])

    guide_data.append(["FOLLOW-UP SEQUENCE C: LOWER PRIORITY (Score 1–2)", "", ""])
    guide_data.append(["Day", "Channel", "Action"])
    for row in [["1","Email","Batch industry email"],["14","Email","Educational content (blog/whitepaper)"],
                ["30","Email","Webinar invitation"],["60","Email","ROI-focused case study"],
                ["90","Email","Quarterly check-in"]]:
        guide_data.append(row)
    guide_data.append([])

    # Revenue Projections
    guide_data.append(["REVENUE PROJECTIONS", ""])
    guide_data.append(["Metric", "Value"])
    for row in [["Companies contacted","1,000"],["Meetings booked (5–10%)","50–100"],
                ["Proposals sent (50% of meetings)","25–50"],["Deals closed (20–30% of proposals)","5–15"],
                ["Projected revenue","$75,000–$375,000"],["Best case w/ referrals + upsells","$500,000+"],
                ["Average deal size target","$15,000–$25,000"]]:
        guide_data.append(row)
    guide_data.append([])

    # Key Metrics
    guide_data.append(["KEY OUTREACH METRICS", ""])
    guide_data.append(["Metric", "Target"])
    for row in [["Open rate","25–35%"],["Reply rate","5–10%"],["Meeting booked rate","2–5% of total outreach"],
                ["Proposal rate","50% of meetings"],["Close rate","20–30% of proposals"],
                ["Average deal size","$15,000–$25,000"]]:
        guide_data.append(row)
    guide_data.append([])

    # Email Templates
    guide_data.append(["EMAIL OUTREACH TEMPLATES", "", ""])
    guide_data.append(["Template", "Subject Line", "Body"])
    guide_data.append(["Cold Outreach", "[Company] — Reducing [pain point] with AI",
        "Hi [First Name],\n\nI noticed [Company] has been [growing/expanding], and we've been helping similar [industry] companies automate [process] using AI.\n\nWe recently helped a [similar company] reduce their [metric] by 73% while saving 20+ hrs/week.\n\nBefore: [Pain point]\nAfter: [Solution result]\n\nWould 15 minutes make sense to explore this for [Company]?\n\nBest, [Your Name]"])
    guide_data.append(["Social Proof", "How [Similar Co] saved $180K/yr with AI",
        "Hi [First Name],\n\n[Similar Company] recently shared how they automated [process], and I thought of [Company].\n\nWithin 60 days they saw:\n• 47% reduction in response time\n• $15K/month in labor savings\n• 22% increase in CSAT\n\nI'd love to share the case study. 15 minutes this week?\n\nBest, [Your Name]"])
    guide_data.append(["Follow-Up", "Re: [Original Subject] — Quick question",
        "Hi [First Name],\n\nOne question: Is [pain point] something your team is actively trying to improve?\n\nIf so, I have a 5-minute video walkthrough for [industry] companies. Happy to send it.\n\nIf timing isn't right, no worries — I'll check back in a few months.\n\nBest, [Your Name]"])
    guide_data.append([])

    # Scripts
    guide_data.append(["LINKEDIN & COLD CALL SCRIPTS", "", ""])
    guide_data.append(["Channel", "Stage", "Script"])
    guide_data.append(["LinkedIn", "Connection Request", "Hi [First Name], I work with [industry] companies on AI automation — specifically around [use case]. Would love to connect and share insights."])
    guide_data.append(["LinkedIn", "Follow-Up", "Thanks for connecting! I noticed [Company] has been [observation]. We've been helping similar companies automate [process]. Open to a quick 15-min call?"])
    guide_data.append(["Cold Call", "Opening (10s)", "Hi [First Name], this is [Your Name] from [Company]. I help [industry] companies like [competitor] automate [process] with AI. Do you have 60 seconds?"])
    guide_data.append(["Cold Call", "Pitch (30s)", "We've helped [similar companies] solve [pain point]. [Company X] reduced [metric] by [%] in [timeframe]. Open to a 15-min discovery call?"])
    guide_data.append(["Cold Call", "Objection: Have solution", "Most of our best clients came when they outgrew current tools. Even with existing systems, there are 2-3 high-impact areas where AI layers on top. Worth 15 min?"])
    guide_data.append(["Cold Call", "Objection: Bad timing", "Totally understand. Quick question — is [pain point] something your team deals with regularly? Let me send a one-pager and follow up in [timeframe]."])

    api(batch_url, "POST", {
        "valueInputOption": "RAW",
        "data": [{"range": "'Prospecting Guide'!A1", "values": guide_data}]
    }, token)
    print("✅ Sheet 2 done\n")

    # ── Step 6: Populate Sheet 3 — Lead Sources ──
    print("📝 Writing Sheet 3: Lead Sources Guide...")

    leads_data = []
    leads_data.append(["COMPREHENSIVE LEAD SOURCES GUIDE", "", "", ""])
    leads_data.append([])

    # General Directories
    leads_data.append(["GENERAL BUSINESS DIRECTORIES — TIER 1", "", ""])
    leads_data.append(["Directory", "URL", "Notes"])
    for row in [
        ["Google Business Profile", "business.google.com", "Most important; 42% of local searchers click Map Pack"],
        ["Yelp", "yelp.com", "Reliable review system; major purchase influence"],
        ["Better Business Bureau", "bbb.org/search", "~400K accredited businesses; A+ to F ratings"],
        ["Bing Places", "bingplaces.com", "Millions of Microsoft device users"],
        ["LinkedIn Company Pages", "linkedin.com", "Essential for B2B; thought leadership"],
        ["Facebook Business", "facebook.com/business", "Broad consumer reach"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    leads_data.append(["GENERAL BUSINESS DIRECTORIES — TIER 2", "", ""])
    leads_data.append(["Directory", "URL", "Notes"])
    for row in [
        ["Manta", "manta.com", "20+ year SMB directory; free listings"],
        ["Kompass", "kompass.com", "B2B global directory; detailed company data"],
        ["Chamber of Commerce", "uschamber.com", "Local chamber web directories"],
        ["EZLocal", "ezlocalstate.com", "Focused on local SEO; integrates with Google Maps"],
        ["Clutch.co", "clutch.co", "B2B marketplace with verified client reviews"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    # Government Databases
    leads_data.append(["GOVERNMENT & PUBLIC DATABASES", "", ""])
    leads_data.append(["Database", "URL", "Notes"])
    for row in [
        ["SAM.gov", "sam.gov", "Free; US gov contract opportunities; search by NAICS, location"],
        ["SBA Small Business Search", "search.certifications.sba.gov", "Small biz registered for federal contracting; 8(a), HUBZone, SDVOSB"],
        ["SBA Open Data Portal", "data.sba.gov", "Open data, reports, tools from SBA"],
        ["EDGAR (SEC)", "sec.gov/edgar", "Free public corporate financial info for all public companies"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    # B2B Platforms
    leads_data.append(["B2B CONTACT & LEAD GENERATION — FREE/FREEMIUM", "", "", ""])
    leads_data.append(["Platform", "Free Tier", "Database Size", "Key Features"])
    for row in [
        ["Apollo.io", "50-250 contacts/mo", "275M+ contacts, 73M companies", "Email sequencing, calling, 65+ filters"],
        ["Lusha", "5 contacts/mo", "100M+ prospects", "Direct contact details; AI Prospect Playlists"],
        ["Hunter.io", "Free plan", "Large email DB", "Email finder & verifier; 95% accuracy; bulk search"],
        ["ZoomInfo Lite", "10 credits/mo", "321M+ contacts", "Chrome-based prospecting"],
        ["Seamless.AI", "Free tier", "Large database", "Email and phone finder"],
        ["RB2B", "Free forever (basic)", "Website visitor data", "Person-level website visitor identification"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    leads_data.append(["B2B CONTACT & LEAD GENERATION — PAID", "", ""])
    leads_data.append(["Platform", "Starting Price", "Key Differentiator"])
    for row in [
        ["Cognism", "Enterprise pricing", "87% phone-verified accuracy; GDPR-first"],
        ["ZoomInfo Sales", "Enterprise pricing", "321M+ contacts; intent data; org charts"],
        ["UpLead", "$99/month", "95% accuracy guarantee; 155M+ contacts"],
        ["SalesIntel", "Mid-market", "Human-verified; 12M verified decision-makers"],
        ["Saleshandy", "$25/month", "800M+ contacts; cold email automation built in"],
        ["Instantly.ai", "$37/month", "450M+ contacts; unlimited email warm-up"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    # Startup Directories
    leads_data.append(["STARTUP & GROWTH DIRECTORIES", "", ""])
    leads_data.append(["Directory", "URL", "Focus"])
    for row in [
        ["Inc. 5000", "inc.com/inc5000", "5,000 fastest-growing private US companies; $300B+ revenue"],
        ["Crunchbase", "crunchbase.com", "Startups, investors, funding rounds"],
        ["Wellfound (AngelList)", "angel.co", "Most robust early-stage startup directory"],
        ["Clutch.co", "clutch.co", "B2B marketplace; verified client reviews"],
        ["ProductHunt", "producthunt.com", "New product launches; tech-forward audience"],
        ["G2", "g2.com", "Software company reviews and comparisons"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    # Industry Directories
    leads_data.append(["INDUSTRY-SPECIFIC DIRECTORIES", "", ""])
    leads_data.append(["Industry", "Directory", "URL"])
    for row in [
        ["Healthcare", "Healthgrades", "healthgrades.com"],
        ["Healthcare", "Zocdoc", "zocdoc.com"],
        ["Legal", "Avvo", "avvo.com"],
        ["Legal", "FindLaw", "findlaw.com"],
        ["Real Estate", "Zillow", "zillow.com"],
        ["Restaurants", "OpenTable", "opentable.com"],
        ["Home Services", "Angi (Angie's List)", "angi.com"],
        ["Automotive", "AutoTrader", "autotrader.com"],
        ["Manufacturing", "ThomasNet", "thomasnet.com"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    # Strategies
    leads_data.append(["STRATEGIES FOR FINDING AI AUTOMATION CLIENTS", ""])
    leads_data.append(["Strategy", "Steps"])
    for row in [
        ["1. Direct Database Prospecting", "Apollo.io/Lusha (free) → Filter 50-500 employees → Export → Personalized outreach"],
        ["2. Growth Company Targeting", "Inc. 5000 by industry → Cross-ref Crunchbase funded → They have budget + need to scale"],
        ["3. Government Contractor Mining", "SAM.gov by NAICS → Cross-ref SBA DSBS → Need AI for compliance & contracts"],
        ["4. Industry Association Infiltration", "Directory of Associations → Access member directories → Attend events"],
        ["5. Local Business Discovery", "Google Maps scraping → Target no-website businesses → Enrich with Hunter.io"],
        ["6. Trigger-Based Prospecting", "Google Alerts + Lead411 intent data → Monitor LinkedIn for manual-process posts"],
        ["7. Website Visitor Conversion", "Leadfeeder/RB2B on your site → Create AI content → ID visiting companies"],
        ["8. Review Platform Mining", "Clutch.co agencies → G2 manual tool users → BBB complaints = AI opportunity"],
    ]:
        leads_data.append(row)
    leads_data.append([])

    # Action Plan
    leads_data.append(["4-WEEK QUICK-START ACTION PLAN", "", ""])
    leads_data.append(["Week", "Task", "Status"])
    for row in [
        ["Week 1", "Create free accounts: Apollo.io, Hunter.io, Lusha, LinkedIn", "☐"],
        ["Week 1", "Sign up for Crunchbase free tier", "☐"],
        ["Week 1", "Set up Google Alerts for target industry + automation keywords", "☐"],
        ["Week 1", "Register for D&B Hoovers free trial", "☐"],
        ["Week 2", "Search Inc. 5000 for fast-growing companies in target industries", "☐"],
        ["Week 2", "Apollo.io filters: COO/VP Ops/CTO at 50-500 employee companies", "☐"],
        ["Week 2", "Search SAM.gov / SBA DSBS by NAICS code", "☐"],
        ["Week 2", "Google Maps tools for local businesses in target verticals", "☐"],
        ["Week 3", "Verify emails with Hunter.io", "☐"],
        ["Week 3", "Create personalized outreach templates per vertical", "☐"],
        ["Week 3", "Begin multi-channel outreach (email + LinkedIn)", "☐"],
        ["Week 3", "Track responses and refine messaging", "☐"],
        ["Week 4", "Analyze which sources produced best leads", "☐"],
        ["Week 4", "Double down on highest-converting channels", "☐"],
        ["Week 4", "Set up Leadfeeder/RB2B on your website", "☐"],
        ["Week 4", "Consider upgrading to paid tiers of top tools", "☐"],
    ]:
        leads_data.append(row)

    api(batch_url, "POST", {
        "valueInputOption": "RAW",
        "data": [{"range": "'Lead Sources Guide'!A1", "values": leads_data}]
    }, token)
    print("✅ Sheet 3 done\n")

    # ── Step 7: Populate Sheet 4 — Verticals Summary ──
    print("📝 Writing Sheet 4: Verticals Summary...")

    vert_data = [["#", "Vertical", "Example Companies", "Market Size", "Primary AI Use Case", "Secondary Use Case", "Tertiary Use Case"]]
    verticals = [
        ["1", "Healthcare / Medical Practices", "Ascension, MDVIP, Duly Health, VillageMD", "$349B+ (7.6% CAGR)", "Patient scheduling AI", "Medical billing automation", "EHR integration"],
        ["2", "Legal / Law Firms", "Kirkland & Ellis, DLA Piper, Dentons", "Am Law 200: $200B+", "Document review AI", "Contract analysis", "Client intake automation"],
        ["3", "Real Estate / Property Mgmt", "Greystar, CBRE, Keller Williams, Compass", "$21.17B PM (9.6% CAGR)", "Lead qualification AI", "Listing automation", "Tenant screening"],
        ["4", "Accounting / CPA Firms", "RSM, BDO, Grant Thornton, CLA", "Large", "Tax automation", "Audit AI analytics", "Client onboarding"],
        ["5", "Construction", "Turner, DPR, Gilbane, Hensel Phelps", "Large (labor-short)", "Project management AI", "Estimating automation", "Safety compliance"],
        ["6", "eCommerce / DTC Brands", "Warby Parker, Chewy, Stitch Fix, Glossier", "Large & growing", "Customer service AI", "Inventory automation", "Personalization engines"],
        ["7", "Fitness / Gym Franchises", "Planet Fitness, Orangetheory, Equinox", "Franchise-driven", "Member retention AI", "Scheduling automation", "Lead nurturing"],
        ["8", "Insurance Agencies", "Lockton, USI, Hub International, Acrisure", "Consolidating rapidly", "Claims processing AI", "Underwriting automation", "Lead scoring"],
        ["9", "Staffing / Recruiting", "Robert Half, Randstad, Kforce, Insight Global", "$151.8B US staffing", "Resume screening AI", "Candidate matching", "Interview scheduling"],
        ["10", "Marketing / Digital Agencies", "WebFX, Wieden+Kennedy, VaynerMedia", "Users + resellers of AI", "Content generation AI", "Reporting automation", "Campaign optimization"],
        ["11", "Manufacturing (SMB)", "Protolabs, Xometry, Jabil, American Axle", "262,931 US companies", "Quality control AI", "Predictive maintenance", "Supply chain automation"],
        ["12", "Logistics / Freight / 3PL", "C.H. Robinson, XPO, J.B. Hunt, Flexport", "Thin-margin, high-vol", "Route optimization AI", "Shipment tracking", "Demand forecasting"],
        ["13", "Restaurants / Food Service", "Chipotle, Raising Cane's, Sweetgreen", "Growing 4%+ annually", "Inventory AI", "Staff scheduling", "Customer feedback"],
        ["14", "Auto Dealerships", "Lithia Motors, AutoNation, Penske, Carvana", "Top 150: 4M+ vehicles/yr", "Lead follow-up AI", "Inventory management", "Service scheduling"],
        ["15", "Home Services (HVAC, Plumbing)", "Roto-Rooter, EMCOR, Trane, Neighborly", "HVAC: $25B by 2025", "Dispatch AI", "Lead qualification", "Estimate automation"],
        ["16", "SaaS / Software", "HubSpot, CrowdStrike, Snowflake, Rippling", "Natural AI adopters", "Customer onboarding AI", "Churn prediction", "Support automation"],
        ["17", "Education / EdTech", "Coursera, Duolingo, PowerSchool", "$247B global (13.9% CAGR)", "Student engagement AI", "Grading automation", "Enrollment optimization"],
        ["18", "Veterinary / Pet Services", "Banfield, VCA, NVA, PetSmart, Zoetis", "$38.3B vet care (2023)", "Appointment scheduling AI", "Pet health records", "Follow-up automation"],
        ["19", "Dental (DSO)", "Heartland Dental, Aspen, PDS Health, MB2", "$196.5B by 2034 (17.9%)", "Patient scheduling AI", "Treatment plan AI", "Billing automation"],
        ["20", "Senior Care / Home Health", "Home Instead, Bayada, Kindred, Brookdale", "12M+ Americans, 7.1%", "Caregiver scheduling AI", "Patient monitoring", "Compliance automation"],
        ["21", "Financial Advisory", "Creative Planning, Fisher, Edward Jones", "RIA: 11% CAGR", "Portfolio reporting AI", "Client communication", "Compliance automation"],
        ["22", "Pest Control / Cleaning", "Rollins/Orkin, ABM, Cintas, Servpro", "$26.2B pest (5.1% CAGR)", "Route optimization AI", "Scheduling", "Customer retention"],
        ["23", "Printing / Signage / Packaging", "Quad/Graphics, RR Donnelley, FASTSIGNS", "$127B (2024)", "Order processing AI", "Estimating", "Quality control"],
        ["24", "Nonprofits / Associations", "Red Cross, United Way, YMCA, AARP", "Significant budgets", "Donor management AI", "Grant writing", "Event automation"],
        ["25", "Telehealth / Digital Health", "Teladoc, Amwell, Doximity, BetterHelp", "4,818 startups", "Patient triage AI", "Scheduling", "Follow-up automation"],
    ]
    vert_data.extend(verticals)

    api(batch_url, "POST", {
        "valueInputOption": "RAW",
        "data": [{"range": "'Verticals Summary'!A1", "values": vert_data}]
    }, token)
    print("✅ Sheet 4 done\n")

    # ── Step 8: Apply formatting ──
    print("🎨 Applying formatting...")
    fmt_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate"

    # Color definitions
    dark_blue = {"red": 0.106, "green": 0.165, "blue": 0.290}
    white_c = {"red": 1, "green": 1, "blue": 1}
    light_gray = {"red": 0.949, "green": 0.949, "blue": 0.949}
    green_bg = {"red": 0.784, "green": 0.902, "blue": 0.784}
    lt_green = {"red": 0.863, "green": 0.929, "blue": 0.784}
    yellow_bg = {"red": 1, "green": 0.976, "blue": 0.769}
    orange_bg = {"red": 1, "green": 0.878, "blue": 0.698}
    red_bg = {"red": 1, "green": 0.804, "blue": 0.824}

    requests = []

    # Sheet 1: Header formatting
    requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": dark_blue,
                    "textFormat": {"bold": True, "foregroundColor": white_c, "fontSize": 10},
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })

    # Sheet 1: Auto-resize columns
    requests.append({
        "autoResizeDimensions": {
            "dimensions": {"sheetId": 0, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 14}
        }
    })

    # Sheet 1: Conditional formatting for Priority Score (column M = index 12)
    for score, color in [("5", green_bg), ("4", lt_green), ("3", yellow_bg), ("2", orange_bg), ("1", red_bg)]:
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 1001, "startColumnIndex": 0, "endColumnIndex": 14}],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": f'=$M2="{score}"'}],
                        },
                        "format": {"backgroundColor": color},
                    },
                },
                "index": 0,
            }
        })

    # Sheet 4: Header formatting
    requests.append({
        "repeatCell": {
            "range": {"sheetId": 3, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": dark_blue,
                    "textFormat": {"bold": True, "foregroundColor": white_c, "fontSize": 10},
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })
    requests.append({
        "autoResizeDimensions": {
            "dimensions": {"sheetId": 3, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 7}
        }
    })

    # Sheet 2 & 3: auto-resize
    for sheet_id in [1, 2]:
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 6}
            }
        })

    api(fmt_url, "POST", {"requests": requests}, token)
    print("✅ Formatting applied\n")

    # ── Step 9: Make it publicly viewable ──
    print("🔗 Setting sharing permissions...")
    drive_url = f"https://www.googleapis.com/drive/v3/files/{sid}/permissions"
    try:
        api(drive_url, "POST", {
            "role": "writer",
            "type": "anyone",
        }, token)
        print("✅ Sheet is publicly editable\n")
    except Exception as e:
        print(f"   ⚠️  Could not set public access (may need Drive API enabled): {e}")
        print(f"   Share manually from the sheet\n")

    print("=" * 60)
    print(f"🎉 YOUR GOOGLE SHEET IS READY!")
    print(f"=" * 60)
    print(f"\n📎 {url}\n")
    print("4 Tabs:")
    print("  1. 1000 Companies Database (color-coded by priority)")
    print("  2. Prospecting Guide (pricing, templates, sequences)")
    print("  3. Lead Sources Guide (directories, tools, strategies)")
    print("  4. Verticals Summary (25 industries quick reference)")


if __name__ == "__main__":
    main()
