#!/usr/bin/env python3
"""
Enrich AI_CLIENTS_1000_DATABASE.csv with contact emails and phone numbers.
Scrapes company websites (homepage + /contact) for real contact info,
and generates pattern-based emails as fallback.
"""

import csv
import re
import ssl
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import time
import os

INPUT_CSV = "/home/user/XML-to-Supabase/AI_CLIENTS_1000_DATABASE.csv"
OUTPUT_CSV = "/home/user/XML-to-Supabase/AI_CLIENTS_1000_ENRICHED.csv"
PROGRESS_FILE = "/home/user/XML-to-Supabase/.enrich_progress"
MAX_WORKERS = 20
TIMEOUT = 8

# SSL context
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Regex patterns
EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)
PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
)

# Junk emails to skip
JUNK_DOMAINS = {
    'example.com', 'sentry.io', 'wixpress.com', 'googleapis.com',
    'w3.org', 'schema.org', 'facebook.com', 'twitter.com',
    'instagram.com', 'youtube.com', 'linkedin.com', 'google.com',
    'cloudflare.com', 'wordpress.org', 'jquery.com', 'bootstrap.com',
    'amazonaws.com', 'gravatar.com', 'wp.com', 'godaddy.com',
    'squarespace.com', 'wix.com', 'shopify.com', 'hubspot.com',
}
JUNK_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'mailer-daemon', 'postmaster'}
JUNK_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js'}


def clean_domain(website):
    """Extract clean domain from website field."""
    w = website.strip()
    if not w:
        return None
    if not w.startswith('http'):
        w = 'https://' + w
    parsed = urlparse(w)
    domain = parsed.netloc or parsed.path.split('/')[0]
    domain = domain.replace('www.', '')
    return domain


def is_valid_email(email, company_domain=None):
    """Filter out junk/image/tracking emails."""
    email = email.lower().strip()
    local, _, domain = email.rpartition('@')

    # Skip image/asset references
    for ext in JUNK_EXTENSIONS:
        if ext in email:
            return False

    # Skip known junk domains
    for jd in JUNK_DOMAINS:
        if jd in domain:
            return False

    # Skip junk prefixes
    for jp in JUNK_PREFIXES:
        if local.startswith(jp):
            return False

    # Must have valid TLD
    if '.' not in domain:
        return False

    # Skip very long emails (usually encoded strings)
    if len(email) > 60:
        return False

    return True


def is_valid_phone(phone):
    """Filter out fake/junk phone numbers."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 10 or len(digits) > 11:
        return False
    # Skip obvious fakes
    if digits in ('0000000000', '1111111111', '1234567890'):
        return False
    return True


def fetch_page(url):
    """Fetch a single URL with timeout."""
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    req.add_header('Accept', 'text/html,application/xhtml+xml')
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        content_type = resp.headers.get('Content-Type', '')
        if 'text' not in content_type and 'html' not in content_type:
            return ''
        raw = resp.read(500_000)  # Max 500KB
        # Try common encodings
        for enc in ('utf-8', 'latin-1', 'ascii'):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode('utf-8', errors='ignore')


def scrape_company(website):
    """Scrape a company website for emails and phone numbers."""
    domain = clean_domain(website)
    if not domain:
        return [], [], domain

    base_url = f"https://{domain}"
    all_text = ""

    # Try homepage + common contact pages
    pages = [base_url, f"{base_url}/contact", f"{base_url}/contact-us", f"{base_url}/about"]
    for page_url in pages:
        try:
            text = fetch_page(page_url)
            all_text += " " + text
        except Exception:
            pass

    # Extract emails
    raw_emails = EMAIL_RE.findall(all_text)
    emails = []
    seen = set()
    for e in raw_emails:
        e_lower = e.lower()
        if e_lower not in seen and is_valid_email(e, domain):
            seen.add(e_lower)
            emails.append(e.lower())

    # Prioritize: company-domain emails first, then others
    company_emails = [e for e in emails if domain in e]
    other_emails = [e for e in emails if domain not in e]
    emails = company_emails + other_emails

    # Extract phones
    raw_phones = PHONE_RE.findall(all_text)
    phones = []
    seen_p = set()
    for p in raw_phones:
        digits = re.sub(r'\D', '', p)
        if digits not in seen_p and is_valid_phone(p):
            seen_p.add(digits)
            phones.append(p.strip())

    return emails[:5], phones[:3], domain


def generate_pattern_emails(domain):
    """Generate likely contact email patterns as fallback."""
    if not domain:
        return []
    return [f"info@{domain}", f"contact@{domain}"]


def enrich_row(row):
    """Enrich a single company row."""
    idx = row['ID']
    website = row.get('Website', '')

    emails, phones, domain = scrape_company(website)

    # Fallback: generate pattern emails if none found
    if not emails and domain:
        emails = generate_pattern_emails(domain)

    row['Contact_Email'] = emails[0] if emails else ''
    row['Alt_Emails'] = '; '.join(emails[1:4]) if len(emails) > 1 else ''
    row['Contact_Phone'] = phones[0] if phones else ''
    row['Alt_Phones'] = '; '.join(phones[1:3]) if len(phones) > 1 else ''
    row['Email_Source'] = 'scraped' if (emails and emails[0] not in generate_pattern_emails(domain or '')) else ('pattern' if emails else 'none')

    return row


def main():
    # Load CSV
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    print(f"📊 Loaded {total} companies from CSV")
    print(f"🔍 Enriching with emails & phone numbers ({MAX_WORKERS} parallel workers)...\n")

    enriched = [None] * total
    scraped_count = 0
    pattern_count = 0
    phone_count = 0
    done = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_row, row): i for i, row in enumerate(rows)}

        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                enriched[idx] = result

                if result['Email_Source'] == 'scraped':
                    scraped_count += 1
                elif result['Email_Source'] == 'pattern':
                    pattern_count += 1
                if result['Contact_Phone']:
                    phone_count += 1
            except Exception as e:
                enriched[idx] = rows[idx]
                enriched[idx]['Contact_Email'] = ''
                enriched[idx]['Alt_Emails'] = ''
                enriched[idx]['Contact_Phone'] = ''
                enriched[idx]['Alt_Phones'] = ''
                enriched[idx]['Email_Source'] = 'error'

            done += 1
            if done % 50 == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(f"   [{done}/{total}] Scraped emails: {scraped_count} | Pattern emails: {pattern_count} | Phones: {phone_count} | {rate:.1f}/s | ETA: {eta:.0f}s")

    # Write enriched CSV
    fieldnames = list(rows[0].keys()) + ['Contact_Email', 'Alt_Emails', 'Contact_Phone', 'Alt_Phones', 'Email_Source']
    # Deduplicate fieldnames while preserving order
    seen_fields = set()
    unique_fields = []
    for f in fieldnames:
        if f not in seen_fields:
            seen_fields.add(f)
            unique_fields.append(f)

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=unique_fields)
        writer.writeheader()
        for row in enriched:
            writer.writerow(row)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"✅ ENRICHMENT COMPLETE — {elapsed:.0f}s")
    print(f"{'='*60}")
    print(f"   Total companies:     {total}")
    print(f"   Scraped emails:      {scraped_count}")
    print(f"   Pattern emails:      {pattern_count}")
    print(f"   No email:            {total - scraped_count - pattern_count}")
    print(f"   Phone numbers found: {phone_count}")
    print(f"\n📁 Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
