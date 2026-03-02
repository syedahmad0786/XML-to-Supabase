#!/usr/bin/env python3
"""
Enrich leads with decision-maker names, professional emails,
LinkedIn profiles, and company social media links.

Strategy:
  1. Scrape /about, /team, /leadership pages for executive names
  2. Extract LinkedIn company page + other social links from website
  3. Generate professional email patterns from found names
  4. Build LinkedIn People Search URLs for decision makers
"""

import csv
import re
import ssl
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, quote_plus
import time

INPUT_CSV = "/home/user/XML-to-Supabase/AI_CLIENTS_1000_ENRICHED.csv"
OUTPUT_CSV = "/home/user/XML-to-Supabase/AI_CLIENTS_1000_FULL_ENRICHED.csv"
MAX_WORKERS = 15
TIMEOUT = 8

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ── Title matching ──
TITLE_KEYWORDS = {
    "CTO": ["cto", "chief technology officer", "chief tech officer"],
    "Chief Technology Officer": ["cto", "chief technology officer", "chief tech officer"],
    "VP of Technology": ["vp of technology", "vice president of technology", "vp technology",
                         "vice president, technology", "svp of technology", "svp technology"],
    "VP of Operations": ["vp of operations", "vice president of operations", "vp operations",
                         "vice president, operations", "svp of operations", "coo", "chief operating officer"],
    "Director of Technology": ["director of technology", "dir of technology", "technology director",
                               "director, technology", "it director"],
    "Director of IT": ["director of it", "it director", "director of information technology",
                       "director, it", "director, information technology"],
    "Director of Operations": ["director of operations", "operations director", "director, operations"],
    "Chief Innovation Officer": ["chief innovation officer", "cio", "chief innovation"],
    "Chief Digital Officer": ["chief digital officer", "cdo"],
    "VP of Innovation": ["vp of innovation", "vice president of innovation", "vp innovation"],
    "Director of Innovation": ["director of innovation", "innovation director"],
    "VP of Digital": ["vp of digital", "vice president of digital", "vp digital"],
    "VP of IT": ["vp of it", "vice president of it", "vp information technology"],
    "CIO": ["cio", "chief information officer"],
    "Managing Partner": ["managing partner"],
    "CEO": ["ceo", "chief executive officer"],
    "COO": ["coo", "chief operating officer"],
    "CFO": ["cfo", "chief financial officer"],
    "Founder": ["founder", "co-founder"],
    "Owner": ["owner", "principal"],
    "President": ["president"],
}

# Common name pattern near titles
# Matches "FirstName LastName" - proper capitalized names
NAME_PATTERN = re.compile(
    r'(?:^|[\s,;|>])'
    r'([A-Z][a-z]{1,15}\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,15})?)'
    r'(?:[\s,;|<]|$)'
)

# Social media URL patterns
LINKEDIN_CO_RE = re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+/?', re.I)
LINKEDIN_PERSON_RE = re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?', re.I)
TWITTER_RE = re.compile(r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?', re.I)
FACEBOOK_RE = re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9.\-]+/?', re.I)
INSTAGRAM_RE = re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?', re.I)
YOUTUBE_RE = re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|@)[a-zA-Z0-9\-_]+/?', re.I)

# Names that are NOT real person names (common false positives)
FAKE_NAMES = {
    'privacy policy', 'terms conditions', 'read more', 'learn more', 'click here',
    'united states', 'new york', 'los angeles', 'san francisco', 'san diego',
    'north america', 'south carolina', 'north carolina', 'west virginia',
    'customer service', 'human resources', 'press release', 'annual report',
    'all rights', 'view all', 'load more', 'see more', 'sign up', 'log in',
    'get started', 'contact us', 'about us', 'our team', 'join us',
    'white paper', 'case study', 'data privacy', 'font size', 'text align',
    'max width', 'line height', 'font family', 'font weight', 'background color',
    'border radius', 'box shadow', 'el paso', 'las vegas', 'santa monica',
    'fort worth', 'palm beach', 'baton rouge', 'des moines', 'grand rapids',
    'salt lake', 'costa mesa', 'santa cruz', 'long beach', 'scottsdale',
}


def clean_domain(website):
    w = website.strip()
    if not w:
        return None
    if not w.startswith('http'):
        w = 'https://' + w
    parsed = urlparse(w)
    domain = parsed.netloc or parsed.path.split('/')[0]
    domain = domain.replace('www.', '')
    return domain


def fetch_page(url):
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    req.add_header('Accept', 'text/html,application/xhtml+xml')
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        ct = resp.headers.get('Content-Type', '')
        if 'text' not in ct and 'html' not in ct:
            return ''
        raw = resp.read(800_000)
        for enc in ('utf-8', 'latin-1'):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode('utf-8', errors='ignore')


def strip_html_tags(html):
    """Remove HTML tags but keep text content."""
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S | re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def is_valid_name(name):
    """Check if extracted text is likely a real person name."""
    name_lower = name.lower().strip()
    if len(name_lower) < 4 or len(name_lower) > 40:
        return False
    for fake in FAKE_NAMES:
        if fake in name_lower:
            return False
    # Must have exactly 2-3 words
    parts = name.split()
    if len(parts) < 2 or len(parts) > 3:
        return False
    # Each part should be 2-15 chars
    for p in parts:
        clean = p.replace('.', '')
        if len(clean) < 1 or len(clean) > 15:
            return False
    # Should not contain numbers
    if any(c.isdigit() for c in name):
        return False
    return True


def find_name_near_title(text, target_title):
    """Find a person's name near a title mention in text."""
    text_lower = text.lower()
    title_keywords = TITLE_KEYWORDS.get(target_title, [target_title.lower()])

    for kw in title_keywords:
        idx = text_lower.find(kw)
        if idx == -1:
            continue

        # Search in a window around the title mention
        window_start = max(0, idx - 200)
        window_end = min(len(text), idx + len(kw) + 200)
        window = text[window_start:window_end]

        names = NAME_PATTERN.findall(window)
        for name in names:
            name = name.strip()
            if is_valid_name(name):
                return name

    return None


def extract_social_links(html):
    """Extract social media URLs from page HTML."""
    socials = {}

    li_company = LINKEDIN_CO_RE.findall(html)
    if li_company:
        url = li_company[0]
        if not url.startswith('http'):
            url = 'https://' + url
        socials['linkedin_company'] = url

    li_person = LINKEDIN_PERSON_RE.findall(html)
    if li_person:
        urls = list(set(li_person))[:3]
        socials['linkedin_people'] = [u if u.startswith('http') else 'https://' + u for u in urls]

    tw = TWITTER_RE.findall(html)
    if tw:
        url = tw[0]
        if not url.startswith('http'):
            url = 'https://' + url
        # Skip share/intent links
        if '/intent/' not in url and '/share' not in url:
            socials['twitter'] = url

    fb = FACEBOOK_RE.findall(html)
    if fb:
        url = fb[0]
        if not url.startswith('http'):
            url = 'https://' + url
        if '/sharer' not in url and '/share' not in url and '/tr?' not in url:
            socials['facebook'] = url

    ig = INSTAGRAM_RE.findall(html)
    if ig:
        url = ig[0]
        if not url.startswith('http'):
            url = 'https://' + url
        socials['instagram'] = url

    yt = YOUTUBE_RE.findall(html)
    if yt:
        url = yt[0]
        if not url.startswith('http'):
            url = 'https://' + url
        socials['youtube'] = url

    return socials


def generate_email_patterns(first_name, last_name, domain):
    """Generate common professional email patterns."""
    f = first_name.lower()
    l = last_name.lower()
    fi = f[0]  # first initial
    li = l[0]  # last initial

    patterns = [
        f"{f}.{l}@{domain}",        # john.smith@co.com
        f"{f}{l}@{domain}",          # johnsmith@co.com
        f"{fi}{l}@{domain}",         # jsmith@co.com
        f"{f}@{domain}",             # john@co.com
        f"{f}_{l}@{domain}",         # john_smith@co.com
        f"{fi}.{l}@{domain}",        # j.smith@co.com
        f"{f}{li}@{domain}",         # johns@co.com
    ]
    return patterns


def build_linkedin_search_url(name, company, title):
    """Build a LinkedIn people search URL."""
    query = f"{name} {company} {title}"
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def enrich_company(row):
    """Enrich a single company with decision-maker info and social links."""
    website = row.get('Website', '')
    domain = clean_domain(website)
    company_name = row['Company_Name']
    target_title = row['Decision_Maker_Title']

    result = {
        'DM_Name': '',
        'DM_Professional_Email': '',
        'DM_Email_Patterns': '',
        'DM_LinkedIn_Search': '',
        'LinkedIn_Company': '',
        'LinkedIn_People_Found': '',
        'Twitter': '',
        'Facebook': '',
        'Instagram': '',
        'YouTube': '',
        'Name_Source': 'none',
    }

    if not domain:
        return result

    all_html = ""
    all_text = ""

    # Fetch multiple pages
    base = f"https://{domain}"
    pages = [
        base,
        f"{base}/about",
        f"{base}/about-us",
        f"{base}/team",
        f"{base}/our-team",
        f"{base}/leadership",
        f"{base}/management",
        f"{base}/executives",
        f"{base}/about/leadership",
        f"{base}/about/team",
        f"{base}/company/leadership",
    ]

    for page_url in pages:
        try:
            html = fetch_page(page_url)
            all_html += " " + html
            all_text += " " + strip_html_tags(html)
        except Exception:
            pass

    # Extract social links
    socials = extract_social_links(all_html)
    result['LinkedIn_Company'] = socials.get('linkedin_company', '')
    result['Twitter'] = socials.get('twitter', '')
    result['Facebook'] = socials.get('facebook', '')
    result['Instagram'] = socials.get('instagram', '')
    result['YouTube'] = socials.get('youtube', '')

    if 'linkedin_people' in socials:
        result['LinkedIn_People_Found'] = '; '.join(socials['linkedin_people'][:3])

    # Find decision maker name
    dm_name = find_name_near_title(all_text, target_title)
    if dm_name:
        result['DM_Name'] = dm_name
        result['Name_Source'] = 'scraped'

        # Parse name parts
        parts = dm_name.split()
        first = parts[0]
        last = parts[-1]

        # Generate email patterns
        patterns = generate_email_patterns(first, last, domain)
        result['DM_Professional_Email'] = patterns[0]  # Most common: first.last@
        result['DM_Email_Patterns'] = '; '.join(patterns[1:4])

        # LinkedIn search URL
        result['DM_LinkedIn_Search'] = build_linkedin_search_url(dm_name, company_name, target_title)
    else:
        # Even without a name, generate a LinkedIn search URL using title + company
        result['DM_LinkedIn_Search'] = build_linkedin_search_url(target_title, company_name, "")

    return result


def main():
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    print(f"📊 Loaded {total} companies")
    print(f"🔍 Finding decision makers, emails, LinkedIn & social profiles...")
    print(f"   Workers: {MAX_WORKERS} | Pages per company: up to 11\n")

    results = [None] * total
    names_found = 0
    socials_found = 0
    done = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_company, row): i for i, row in enumerate(rows)}

        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results[idx] = result
                if result['DM_Name']:
                    names_found += 1
                if result['LinkedIn_Company'] or result['Twitter'] or result['Facebook']:
                    socials_found += 1
            except Exception as e:
                results[idx] = {
                    'DM_Name': '', 'DM_Professional_Email': '', 'DM_Email_Patterns': '',
                    'DM_LinkedIn_Search': '', 'LinkedIn_Company': '', 'LinkedIn_People_Found': '',
                    'Twitter': '', 'Facebook': '', 'Instagram': '', 'YouTube': '',
                    'Name_Source': 'error',
                }

            done += 1
            if done % 25 == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(f"   [{done:4d}/{total}] Names: {names_found} | Socials: {socials_found} | {rate:.1f}/s | ETA: {eta:.0f}s")

    # Merge results into rows
    new_fields = [
        'DM_Name', 'DM_Professional_Email', 'DM_Email_Patterns',
        'DM_LinkedIn_Search', 'LinkedIn_Company', 'LinkedIn_People_Found',
        'Twitter', 'Facebook', 'Instagram', 'YouTube', 'Name_Source'
    ]

    fieldnames = list(rows[0].keys()) + new_fields
    seen = set()
    unique_fields = []
    for f in fieldnames:
        if f not in seen:
            seen.add(f)
            unique_fields.append(f)

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=unique_fields)
        writer.writeheader()
        for row, result in zip(rows, results):
            row.update(result)
            writer.writerow(row)

    elapsed = time.time() - start

    # Stats
    li_company = len([r for r in results if r['LinkedIn_Company']])
    li_people = len([r for r in results if r['LinkedIn_People_Found']])
    twitter = len([r for r in results if r['Twitter']])
    facebook = len([r for r in results if r['Facebook']])
    instagram = len([r for r in results if r['Instagram']])
    youtube = len([r for r in results if r['YouTube']])
    emails_gen = len([r for r in results if r['DM_Professional_Email']])

    print(f"\n{'='*60}")
    print(f"✅ DECISION MAKER ENRICHMENT COMPLETE — {elapsed:.0f}s")
    print(f"{'='*60}")
    print(f"  Decision maker names found:    {names_found}")
    print(f"  Professional emails generated: {emails_gen}")
    print(f"  LinkedIn search URLs:          {total}")
    print(f"  LinkedIn company pages:        {li_company}")
    print(f"  LinkedIn people profiles:      {li_people}")
    print(f"  Twitter/X profiles:            {twitter}")
    print(f"  Facebook pages:                {facebook}")
    print(f"  Instagram profiles:            {instagram}")
    print(f"  YouTube channels:              {youtube}")
    print(f"\n📁 Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
