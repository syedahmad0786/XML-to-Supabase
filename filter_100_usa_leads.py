#!/usr/bin/env python3
"""
Filter and rank the TOP 100 USA leads most likely to pay $5K+ for AI solutions.
Merges data from all pipeline sources and scores each lead.
"""

import csv
import re
import os

# US state codes and names for filtering
US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
    'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY','DC'
}
US_STATE_NAMES = {
    'alabama','alaska','arizona','arkansas','california','colorado','connecticut',
    'delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa',
    'kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan',
    'minnesota','mississippi','missouri','montana','nebraska','nevada',
    'new hampshire','new jersey','new mexico','new york','north carolina',
    'north dakota','ohio','oklahoma','oregon','pennsylvania','rhode island',
    'south carolina','south dakota','tennessee','texas','utah','vermont',
    'virginia','washington','west virginia','wisconsin','wyoming',
    'district of columbia'
}
US_CITIES = {
    'new york','los angeles','chicago','houston','phoenix','philadelphia',
    'san antonio','san diego','dallas','san jose','austin','jacksonville',
    'fort worth','columbus','charlotte','indianapolis','san francisco',
    'seattle','denver','nashville','oklahoma city','washington','el paso',
    'boston','portland','las vegas','memphis','louisville','baltimore',
    'milwaukee','albuquerque','tucson','fresno','mesa','sacramento',
    'atlanta','kansas city','omaha','colorado springs','raleigh','long beach',
    'virginia beach','miami','oakland','minneapolis','tulsa','tampa','arlington',
    'new orleans','boca raton','orlando','detroit','pittsburgh','st louis',
    'saint louis','cleveland','cincinnati','salt lake city','silicon valley',
    'palo alto','mountain view','cupertino','menlo park','sunnyvale','santa clara',
    'redwood city','downers grove','mechanicsburg','oak brook','fort lauderdale',
    'newark','brooklyn','manhattan','queens','bronx','staten island'
}

def is_usa(location):
    """Check if a location string is in the USA."""
    if not location:
        return False
    loc = location.lower().strip()
    # Direct US indicators
    if any(x in loc for x in [', us', ',us', 'usa', 'united states', ', u.s']):
        return True
    # Check state codes (2-letter at end or after comma)
    parts = [p.strip() for p in loc.replace(',', ' ').split()]
    for p in parts:
        if p.upper() in US_STATES and len(p) == 2:
            return True
    # Check state names
    for state in US_STATE_NAMES:
        if state in loc:
            return True
    # Check major city names
    for city in US_CITIES:
        if city in loc:
            return True
    return False

def clean_phone(phone):
    """Clean and validate US phone numbers."""
    if not phone:
        return ''
    # Extract first phone number
    phone = phone.split(';')[0].strip()
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return phone if len(digits) >= 10 else ''

def score_lead(lead):
    """Score a lead 0-100 based on likelihood to pay $5K for AI solutions."""
    score = 0

    # Has email (+25)
    if lead.get('email'):
        score += 25
        # Professional domain email is better than generic
        email = lead['email'].lower()
        if not any(g in email for g in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']):
            score += 5

    # Has phone (+15)
    if lead.get('phone'):
        score += 15

    # Has decision maker name (+15)
    if lead.get('decision_maker') or lead.get('founder'):
        score += 15

    # Has LinkedIn (+5)
    if lead.get('linkedin'):
        score += 5

    # Company size scoring (+10-20)
    employees = lead.get('employees', '')
    if employees:
        try:
            emp_num = int(re.sub(r'\D', '', str(employees).split('-')[0].split('+')[0]))
            if 10 <= emp_num <= 50:
                score += 10  # Small - perfect for $5K
            elif 50 < emp_num <= 200:
                score += 15  # Medium - great for $5K
            elif 200 < emp_num <= 1000:
                score += 20  # Large enough to have budget
            elif emp_num > 1000:
                score += 12  # Enterprise - may need bigger deal
        except (ValueError, IndexError):
            pass

    # Industry relevance (+5-15)
    industry = (lead.get('industry') or '').lower()
    ai_keywords = ['ai', 'automation', 'tech', 'software', 'digital', 'consulting',
                   'marketing', 'saas', 'healthcare', 'legal', 'real estate',
                   'insurance', 'financial', 'manufacturing', 'logistics',
                   'e-commerce', 'ecommerce', 'retail']
    high_value = ['healthcare', 'legal', 'financial', 'insurance', 'real estate',
                  'manufacturing', 'logistics']

    for kw in high_value:
        if kw in industry:
            score += 15
            break
    else:
        for kw in ai_keywords:
            if kw in industry:
                score += 10
                break

    # Deal size indicator (+10)
    deal = (lead.get('deal_size') or '').lower()
    if deal:
        if any(x in deal for x in ['$5k', '$10k', '$15k', '$20k', '$25k', '$5,000', '$10,000']):
            score += 10
        elif '$' in deal:
            score += 5

    # AI use case defined (+5)
    if lead.get('ai_use_case'):
        score += 5

    return min(score, 100)

def load_1000_database():
    """Load the 1000 company enriched database."""
    leads = []
    filepath = '/home/user/XML-to-Supabase/AI_CLIENTS_1000_FULL_ENRICHED.csv'
    if not os.path.exists(filepath):
        return leads

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc = f"{row.get('City','')}, {row.get('State','')}"
            if not is_usa(loc):
                continue

            email = row.get('Contact_Email', '') or row.get('DM_Professional_Email', '')
            alt_emails = row.get('Alt_Emails', '')
            phone = row.get('Contact_Phone', '')
            alt_phones = row.get('Alt_Phones', '')

            lead = {
                'company': row.get('Company_Name', ''),
                'website': row.get('Website', ''),
                'email': email,
                'alt_emails': alt_emails,
                'phone': clean_phone(phone) or clean_phone(alt_phones),
                'industry': row.get('Industry_Vertical', ''),
                'location': loc,
                'decision_maker': row.get('DM_Name', ''),
                'dm_title': row.get('Decision_Maker_Title', ''),
                'employees': row.get('Estimated_Employees', ''),
                'revenue': row.get('Estimated_Revenue_Range', ''),
                'ai_use_case': row.get('AI_Automation_Use_Case', ''),
                'deal_size': row.get('Estimated_Deal_Size', ''),
                'linkedin': row.get('LinkedIn_Company', ''),
                'founder': '',
                'source': '1000_database'
            }
            leads.append(lead)
    return leads

def load_master_leads():
    """Load the master AI leads."""
    leads = []
    filepath = '/home/user/XML-to-Supabase/MASTER_AI_LEADS.csv'
    if not os.path.exists(filepath):
        return leads

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc = row.get('location', '')
            if not is_usa(loc):
                continue

            lead = {
                'company': row.get('company', ''),
                'website': row.get('website', ''),
                'email': row.get('email', ''),
                'alt_emails': '',
                'phone': clean_phone(row.get('phone', '')),
                'industry': row.get('industry', ''),
                'location': loc,
                'decision_maker': '',
                'dm_title': '',
                'employees': '',
                'revenue': '',
                'ai_use_case': '',
                'deal_size': '',
                'linkedin': row.get('linkedin', ''),
                'founder': row.get('founder', ''),
                'source': 'master_leads'
            }
            leads.append(lead)
    return leads

def load_cheerio_leads():
    """Load cheerio-scraped leads."""
    leads = []
    filepath = '/home/user/XML-to-Supabase/CHEERIO_ENRICHED_LEADS.csv'
    if not os.path.exists(filepath):
        return leads

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc = row.get('location', '')
            if not is_usa(loc) and not loc:
                # Include if no location (might be US)
                pass
            elif not is_usa(loc):
                continue

            emails = row.get('emails', '') or row.get('email', '')
            first_email = emails.split(';')[0].strip() if emails else ''
            phones = row.get('phones', '') or row.get('phone', '')

            lead = {
                'company': row.get('company', ''),
                'website': row.get('website', ''),
                'email': first_email,
                'alt_emails': emails,
                'phone': clean_phone(phones),
                'industry': row.get('industry', ''),
                'location': loc,
                'decision_maker': '',
                'dm_title': '',
                'employees': '',
                'revenue': '',
                'ai_use_case': '',
                'deal_size': '',
                'linkedin': row.get('linkedin', ''),
                'founder': row.get('team_members', '').split(';')[0].strip() if row.get('team_members') else '',
                'source': 'cheerio_scraper'
            }
            leads.append(lead)
    return leads

def load_prospects():
    """Load AI prospects real leads."""
    leads = []
    filepath = '/home/user/XML-to-Supabase/AI_PROSPECTS_REAL_LEADS.csv'
    if not os.path.exists(filepath):
        return leads

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc = row.get('Location', '') or row.get('location', '')
            if not is_usa(loc):
                continue

            lead = {
                'company': row.get('Company', '') or row.get('company', ''),
                'website': row.get('Website', '') or row.get('website', ''),
                'email': row.get('Email', '') or row.get('email', ''),
                'alt_emails': '',
                'phone': clean_phone(row.get('Phone', '') or row.get('phone', '')),
                'industry': row.get('Segment', '') or row.get('segment', ''),
                'location': loc,
                'decision_maker': row.get('Name', '') or row.get('name', ''),
                'dm_title': '',
                'employees': '',
                'revenue': '',
                'ai_use_case': row.get('AI_Pain_Point', ''),
                'deal_size': '',
                'linkedin': row.get('LinkedIn', '') or row.get('linkedin', ''),
                'founder': '',
                'source': 'prospects_real'
            }
            leads.append(lead)
    return leads

def deduplicate(leads):
    """Deduplicate by normalized domain, keeping highest-scored version."""
    seen = {}
    for lead in leads:
        website = (lead.get('website') or '').lower().strip()
        website = re.sub(r'^https?://', '', website)
        website = re.sub(r'^www\.', '', website)
        website = website.rstrip('/')

        company = (lead.get('company') or '').lower().strip()
        key = website if website else company
        if not key:
            continue

        if key in seen:
            existing = seen[key]
            # Merge: keep the best data from both
            for field in ['email', 'phone', 'decision_maker', 'founder', 'linkedin',
                         'dm_title', 'ai_use_case', 'deal_size', 'employees', 'revenue']:
                if not existing.get(field) and lead.get(field):
                    existing[field] = lead[field]
            # Merge sources
            if lead.get('source') and lead['source'] not in existing.get('source', ''):
                existing['source'] = existing.get('source', '') + '+' + lead['source']
        else:
            seen[key] = lead
    return list(seen.values())

def main():
    print("=" * 70)
    print("  TOP 100 USA LEADS - AI SOLUTIONS ($5K BUYERS)")
    print("  Merging all data sources...")
    print("=" * 70)

    # Load from all sources
    all_leads = []

    db_leads = load_1000_database()
    print(f"  1000 Database:     {len(db_leads)} USA leads")
    all_leads.extend(db_leads)

    master = load_master_leads()
    print(f"  Master AI Leads:   {len(master)} USA leads")
    all_leads.extend(master)

    cheerio = load_cheerio_leads()
    print(f"  Cheerio Scraped:   {len(cheerio)} leads")
    all_leads.extend(cheerio)

    prospects = load_prospects()
    print(f"  Real Prospects:    {len(prospects)} USA leads")
    all_leads.extend(prospects)

    print(f"\n  Total raw leads:   {len(all_leads)}")

    # Deduplicate
    unique = deduplicate(all_leads)
    print(f"  After dedup:       {len(unique)}")

    # Score and sort
    for lead in unique:
        lead['score'] = score_lead(lead)

    # Filter: must have at least an email OR phone
    contactable = [l for l in unique if l.get('email') or l.get('phone')]
    print(f"  With contact info: {len(contactable)}")

    # Sort by score descending
    contactable.sort(key=lambda x: x['score'], reverse=True)

    # Take top 100
    top_100 = contactable[:100]

    print(f"\n  TOP 100 LEADS (score range: {top_100[-1]['score']}-{top_100[0]['score']})")
    print("=" * 70)

    # Write to CSV
    output_path = '/home/user/XML-to-Supabase/TOP_100_USA_AI_LEADS.csv'
    fieldnames = [
        'rank', 'score', 'company', 'website', 'email', 'alt_emails', 'phone',
        'decision_maker', 'dm_title', 'founder', 'industry', 'location',
        'employees', 'revenue', 'ai_use_case', 'deal_size', 'linkedin', 'source'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, lead in enumerate(top_100, 1):
            lead['rank'] = i
            writer.writerow({k: lead.get(k, '') for k in fieldnames})

    print(f"\n  Saved to: {output_path}")

    # Print summary table
    print(f"\n{'='*70}")
    print(f"  {'#':<4} {'Score':<6} {'Company':<30} {'Contact':<35} {'Location':<20}")
    print(f"{'='*70}")

    for i, lead in enumerate(top_100, 1):
        company = (lead.get('company') or 'Unknown')[:28]
        contact = lead.get('email') or lead.get('phone') or 'N/A'
        contact = contact[:33]
        location = (lead.get('location') or '')[:18]
        print(f"  {i:<4} {lead['score']:<6} {company:<30} {contact:<35} {location:<20}")

    print(f"\n{'='*70}")
    print(f"  SUMMARY:")
    print(f"  Total leads:           {len(top_100)}")
    print(f"  With email:            {sum(1 for l in top_100 if l.get('email'))}")
    print(f"  With phone:            {sum(1 for l in top_100 if l.get('phone'))}")
    print(f"  With decision maker:   {sum(1 for l in top_100 if l.get('decision_maker') or l.get('founder'))}")
    print(f"  Avg score:             {sum(l['score'] for l in top_100) / len(top_100):.1f}/100")
    print(f"  Output:                {output_path}")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
