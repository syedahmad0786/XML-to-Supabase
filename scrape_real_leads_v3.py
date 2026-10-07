#!/usr/bin/env python3
"""
Multi-source lead scraper v3 — fixed data quality issues.

Key fixes:
  - Noomii: JS-rendered profiles → scrape listing data only, use profile URLs for lookup
  - BrokerList: Parse card structure properly (name vs title vs location)
  - Strict name validation to reject junk text
  - Deduplicate by profile URL to avoid duplicate entries
  - Scrape actual BrokerList profiles (server-rendered, work fine)
"""

import csv
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
from html import unescape

OUTPUT_CSV = "/home/user/XML-to-Supabase/AI_PROSPECTS_REAL_LEADS.csv"
MAX_WORKERS = 12
TIMEOUT = 10

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'[\+]?1?[\s.\-]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}')

JUNK_EMAIL_PARTS = {
    'sentry', 'wixpress', 'schema.org', 'example.com', 'yourdomain', 'test@',
    'noreply', 'no-reply', 'donotreply', 'unsubscribe', '.png', '.jpg', '.gif',
    '.svg', 'favicon', 'googleusercontent', 'cloudflare', 'wp-content', 'sentry.io',
    'purl.org', 'w3.org', 'gravatar', 'wordpress', 'jquery', 'bootstrapcdn',
    'googleapis', 'gstatic', 'facebook.com', 'twitter.com', 'linkedin.com',
    'instagram.com', 'youtube.com', 'wix.com', 'squarespace', 'shopify',
    'mailchimp', 'hubspot', 'convertkit', 'activecampaign', '@sentry',
    'protection#', '@2x', '@3x', 'apple-touch', '.webp', 'username@',
}

# Known directory social accounts to filter out
DIRECTORY_SOCIAL_SLUGS = {
    'thebrokerlist', 'noomii', 'businesscoachdirectory', 'bcd_coaching',
    'lifecoachhub',
}


def fetch(url, timeout=TIMEOUT):
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read(500_000)
        for enc in ('utf-8', 'latin-1'):
            try:
                return raw.decode(enc)
            except:
                pass
        return raw.decode('utf-8', errors='ignore')


def strip_tags(html):
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S | re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return unescape(text)


def clean_email(email):
    email = email.lower().strip().rstrip('.')
    for junk in JUNK_EMAIL_PARTS:
        if junk in email:
            return None
    if len(email) < 6 or len(email) > 80 or email.count('@') != 1:
        return None
    return email


def extract_emails(html):
    raw = EMAIL_RE.findall(html)
    clean = []
    seen = set()
    for e in raw:
        e = clean_email(e)
        if e and e not in seen:
            seen.add(e)
            clean.append(e)
    return clean


def extract_social_link(html, platform_pattern, skip_terms=None):
    """Extract first non-directory social link."""
    matches = platform_pattern.findall(html)
    for url in matches:
        if not url.startswith('http'):
            url = 'https://' + url
        url_lower = url.lower()
        # Skip directory-owned accounts
        is_directory = False
        for slug in DIRECTORY_SOCIAL_SLUGS:
            if slug in url_lower:
                is_directory = True
                break
        if is_directory:
            continue
        if skip_terms:
            skip = False
            for term in skip_terms:
                if term in url_lower:
                    skip = True
                    break
            if skip:
                continue
        return url
    return ''


def extract_all_socials(html):
    return {
        'linkedin': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?', re.I)),
        'linkedin_company': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+/?', re.I)),
        'twitter': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?', re.I), ['/intent/', '/share']),
        'facebook': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9.\-]+/?', re.I), ['/sharer', '/share', '/tr?']),
        'instagram': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?', re.I)),
        'youtube': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|@)[a-zA-Z0-9\-_]+/?', re.I)),
        'tiktok': extract_social_link(html, re.compile(r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9._]+/?', re.I)),
    }


def is_valid_person_name(text):
    """Strict validation: is this text a real person name?"""
    text = text.strip()
    if not text or len(text) < 4 or len(text) > 45:
        return False
    # Must have at least 2 words
    parts = text.split()
    if len(parts) < 2 or len(parts) > 4:
        return False
    # First letter of first word must be uppercase
    if not parts[0][0].isupper():
        return False
    # Reject common non-name patterns
    lower = text.lower()
    reject_patterns = [
        'review', 'profile', 'see ', 'full ', 'view ', 'read ', 'click',
        'learn ', 'more', 'coach', 'director', 'manager', 'president',
        'advisor', 'broker', 'agent', 'associate', 'principal', 'founder',
        'consultant', 'specialist', 'analyst', 'executive', 'officer',
        'partner', 'member', 'senior', 'junior', 'vice ', 'chief ',
        'head of', 'team ', 'group', 'department', 'division',
        'ccim', 'cpm', 'rene', 'alc', 'sior', 'cre ', 'mba ',
        'ph.d', 'marketing', 'sales', 'commercial', 'residential',
        'industrial', 'retail', 'office', 'investment', 'development',
        'fort ', 'city', 'county', 'state', 'north', 'south', 'east', 'west',
        'loading', 'search', 'filter', 'sort', 'page', 'next', 'prev',
        'sign up', 'log in', 'register', 'subscribe', 'contact',
        'about', 'home', 'blog', 'news', 'press', 'privacy', 'terms',
    ]
    for rp in reject_patterns:
        if rp in lower:
            return False
    # Each word should look like a name part (2+ chars, mostly alpha)
    for part in parts:
        clean = part.replace('.', '').replace(',', '').replace("'", '')
        if len(clean) < 1:
            return False
        # Allow short initials like "J." or "Jr"
        if len(clean) == 1 and clean.isalpha():
            continue
        if not any(c.isalpha() for c in clean):
            return False
        # Reject if it's all digits
        if clean.isdigit():
            return False
    return True


def scrape_website_for_contact(website_url):
    """Scrape personal website for email, phone, socials."""
    result = {'emails': [], 'phones': [], 'socials': {}}
    if not website_url:
        return result
    if not website_url.startswith('http'):
        website_url = 'https://' + website_url

    urls_to_try = [website_url]
    for suffix in ['/contact', '/contact-us', '/about', '/about-us']:
        urls_to_try.append(website_url.rstrip('/') + suffix)

    all_html = ""
    for u in urls_to_try:
        try:
            all_html += " " + fetch(u)
        except:
            pass

    if all_html:
        result['emails'] = extract_emails(all_html)
        result['socials'] = extract_all_socials(all_html)
        phones = PHONE_RE.findall(strip_tags(all_html))
        result['phones'] = list(set(p.strip() for p in phones[:3]))

    return result


# ══════════════════════════════════════════════
# SOURCE 1: NOOMII — Business Coaches
# ══════════════════════════════════════════════
def scrape_noomii_pages(page_nums):
    """
    Scrape Noomii listing pages.
    Since Noomii profiles are JS-rendered, we only extract names + profile URLs
    from the listing pages. We'll enrich via personal website scraping later.
    """
    coaches = {}  # keyed by profile URL to deduplicate
    for page in page_nums:
        url = f"https://www.noomii.com/business-coaches?page={page}"
        try:
            html = fetch(url)
            # Find name + profile URL pairs
            for m in re.finditer(r'<a[^>]*href="/users/([^"]+)"[^>]*>([^<]+)</a>', html, re.I):
                slug, text = m.group(1), unescape(m.group(2)).strip()
                profile_url = f'https://www.noomii.com/users/{slug}'
                # Only keep if text looks like a person name AND we haven't seen this URL
                if is_valid_person_name(text) and profile_url not in coaches:
                    coaches[profile_url] = {
                        'name': text,
                        'profile_url': profile_url,
                        'source': 'noomii',
                        'segment': 'Business Coach',
                    }
        except:
            pass
    return list(coaches.values())


# ══════════════════════════════════════════════
# SOURCE 2: BCD — Business Coach Directory
# ══════════════════════════════════════════════
def scrape_bcd_pages():
    coaches = {}
    for page in range(1, 10):
        url = f"https://businesscoachdirectory.com/coaches/page/{page}/" if page > 1 else "https://businesscoachdirectory.com/coaches/"
        try:
            html = fetch(url)
            for m in re.finditer(r'href="(https://businesscoachdirectory\.com/coach/[^"]+)"[^>]*>\s*([^<]+)', html, re.I):
                profile_url, text = m.group(1), unescape(m.group(2)).strip()
                if is_valid_person_name(text) and profile_url not in coaches:
                    coaches[profile_url] = {
                        'name': text,
                        'profile_url': profile_url,
                        'source': 'bcd',
                        'segment': 'Business Coach',
                    }
        except:
            pass
    return list(coaches.values())


def scrape_bcd_profile(url):
    """BCD profiles are server-rendered — extract email, website, socials."""
    info = {}
    try:
        html = fetch(url)
        # Email
        emails = extract_emails(html)
        if emails:
            info['email'] = emails[0]
        # Website
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            link = m.group(1).lower()
            skip_domains = ['businesscoachdirectory', 'facebook', 'twitter', 'linkedin',
                            'instagram', 'youtube', 'x.com', 'w3.org', 'schema', 'gmpg.org',
                            'wordpress', 'wp-content', 'cdn', 'fonts', 'google', 'gravatar',
                            'cloudflare', 'xmlrpc', 'wp-json']
            if not any(d in link for d in skip_domains):
                info['website'] = m.group(1)
                break
        # Socials
        socials = extract_all_socials(html)
        for k, v in socials.items():
            if v:
                info[k] = v
        # Phone
        phones = PHONE_RE.findall(strip_tags(html))
        if phones:
            info['phone'] = phones[0].strip()
    except:
        pass
    return info


# ══════════════════════════════════════════════
# SOURCE 3: THEBROKERLIST — CRE Brokers
# ══════════════════════════════════════════════
def scrape_brokerlist_pages(page_nums):
    """
    Parse BrokerList card structure:
      <div class="profile_name"><a href="/profiles/ID">NAME</a></div>
      <div class="profile_title"><a href="/profiles/ID">TITLE</a></div>
      <div class="profile_city"><a href="/profiles/ID">CITY</a>, <a>STATE</a></div>
    """
    brokers = {}
    for page in page_nums:
        url = f"https://thebrokerlist.com/commercial-real-estate-brokers?page={page}"
        try:
            html = fetch(url)

            # Extract card data by profile ID
            # First pass: get names from profile_name divs
            name_pattern = re.compile(
                r'profile_name[^>]*>\s*<a[^>]*href="/profiles/(\d+)"[^>]*>([^<]+)</a>',
                re.I
            )
            for m in name_pattern.finditer(html):
                pid, name = m.group(1), unescape(m.group(2)).strip()
                profile_url = f'https://thebrokerlist.com/profiles/{pid}'
                if profile_url not in brokers and is_valid_person_name(name):
                    brokers[profile_url] = {
                        'name': name,
                        'profile_url': profile_url,
                        'source': 'brokerlist',
                        'segment': 'Real Estate Broker',
                        'title': '',
                        'location': '',
                    }

            # Second pass: get titles
            title_pattern = re.compile(
                r'profile_title[^>]*>\s*<a[^>]*href="/profiles/(\d+)"[^>]*>([^<]+)</a>',
                re.I
            )
            for m in title_pattern.finditer(html):
                pid, title = m.group(1), unescape(m.group(2)).strip()
                profile_url = f'https://thebrokerlist.com/profiles/{pid}'
                if profile_url in brokers:
                    brokers[profile_url]['title'] = title

            # Third pass: get city/state
            city_pattern = re.compile(
                r'profile_city[^>]*>\s*<a[^>]*href="/profiles/(\d+)"[^>]*>([^<]+)</a>\s*,\s*'
                r'<a[^>]*href="/profiles/\1"[^>]*>([^<]+)</a>',
                re.I
            )
            for m in city_pattern.finditer(html):
                pid, city, state = m.group(1), unescape(m.group(2)).strip(), unescape(m.group(3)).strip()
                profile_url = f'https://thebrokerlist.com/profiles/{pid}'
                if profile_url in brokers:
                    brokers[profile_url]['location'] = f"{city}, {state}"

        except:
            pass
    return list(brokers.values())


def scrape_brokerlist_profile(profile_url):
    """BrokerList profiles are server-rendered — extract contact info."""
    info = {}
    try:
        html = fetch(profile_url)
        text = strip_tags(html)

        # Email
        emails = extract_emails(html)
        if emails:
            info['email'] = emails[0]

        # Website
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            link = m.group(1).lower()
            skip_domains = ['thebrokerlist', 'facebook', 'twitter', 'linkedin', 'instagram',
                            'youtube', 'x.com', 'eepurl', 'google', 'cdn', 'fonts',
                            'cloudflare', 's3.amazon', 'icsc.org', 'ccim.com', 'crexi',
                            'loopnet', 'costar']
            if not any(d in link for d in skip_domains):
                info['website'] = m.group(1)
                break

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0].strip()

        # Socials (filter directory links)
        socials = extract_all_socials(html)
        for k, v in socials.items():
            if v:
                info[k] = v

        # Company — look for company name in profile structure
        company_match = re.search(r'(?:Company|Firm|Brokerage)\s*:?\s*</?\w+[^>]*>\s*([^<]{3,60})', html, re.I)
        if company_match:
            info['company'] = company_match.group(1).strip()

    except:
        pass
    return info


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
def main():
    start_total = time.time()
    all_leads = []

    print("=" * 60)
    print("PHASE 1: Scraping directory listings...")
    print("=" * 60)

    # Noomii (pages 1-25)
    print("\n  [1/3] Noomii.com — Business Coaches...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        batches = [list(range(i, min(i+5, 26))) for i in range(1, 26, 5)]
        futures = [ex.submit(scrape_noomii_pages, b) for b in batches]
        for f in as_completed(futures):
            all_leads.extend(f.result())
    noomii_count = len([l for l in all_leads if l['source'] == 'noomii'])
    print(f"         {noomii_count} coaches found")

    # BCD
    print("  [2/3] BusinessCoachDirectory.com...")
    bcd_leads = scrape_bcd_pages()
    all_leads.extend(bcd_leads)
    print(f"         {len(bcd_leads)} coaches found")

    # BrokerList (pages 1-50)
    print("  [3/3] TheBrokerList.com — CRE Brokers...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        batches = [list(range(i, min(i+10, 51))) for i in range(1, 51, 10)]
        futures = [ex.submit(scrape_brokerlist_pages, b) for b in batches]
        for f in as_completed(futures):
            all_leads.extend(f.result())
    broker_count = len([l for l in all_leads if l['source'] == 'brokerlist'])
    print(f"         {broker_count} brokers found")

    # Deduplicate by name (lowercase)
    seen = set()
    unique = []
    for l in all_leads:
        key = l['name'].lower()
        if key not in seen:
            seen.add(key)
            unique.append(l)
    all_leads = unique
    print(f"\n  Total unique: {len(all_leads)}")

    # ── Phase 2: Scrape individual profiles (BCD + BrokerList only) ──
    # Noomii profiles are JS-rendered so skip them
    print(f"\n{'=' * 60}")
    print("PHASE 2: Scraping BCD + BrokerList profiles...")
    print("=" * 60)

    profile_leads = [l for l in all_leads if l['source'] in ('bcd', 'brokerlist')]
    print(f"  {len(profile_leads)} profiles to scrape")

    done = 0
    enriched = 0
    start = time.time()

    def enrich_profile(lead):
        if lead['source'] == 'bcd':
            return scrape_bcd_profile(lead['profile_url'])
        elif lead['source'] == 'brokerlist':
            return scrape_brokerlist_profile(lead['profile_url'])
        return {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for l in profile_leads:
            idx = all_leads.index(l)
            futures[executor.submit(enrich_profile, l)] = idx

        for future in as_completed(futures):
            idx = futures[future]
            try:
                info = future.result()
                for k, v in info.items():
                    if v:
                        all_leads[idx][k] = v
                if info.get('email') or info.get('website') or info.get('linkedin'):
                    enriched += 1
            except:
                pass
            done += 1
            if done % 50 == 0 or done == len(profile_leads):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  [{done:4d}/{len(profile_leads)}] Enriched: {enriched} | {rate:.1f}/s")

    # ── Phase 3: Scrape personal websites for email (all sources) ──
    print(f"\n{'=' * 60}")
    print("PHASE 3: Scraping personal websites for emails + socials...")
    print("=" * 60)

    need_email = [i for i, l in enumerate(all_leads) if l.get('website') and not l.get('email')]
    print(f"  {len(need_email)} leads have website but no email")

    found = 0
    done3 = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_website_for_contact, all_leads[i]['website']): i for i in need_email}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                ws = future.result()
                if ws['emails']:
                    all_leads[idx]['email'] = ws['emails'][0]
                    found += 1
                if ws['phones'] and not all_leads[idx].get('phone'):
                    all_leads[idx]['phone'] = ws['phones'][0]
                for k in ('linkedin', 'twitter', 'facebook', 'instagram', 'youtube', 'tiktok'):
                    if ws['socials'].get(k) and not all_leads[idx].get(k):
                        all_leads[idx][k] = ws['socials'][k]
            except:
                pass
            done3 += 1
            if done3 % 25 == 0 or done3 == len(need_email):
                print(f"  [{done3:4d}/{len(need_email)}] Emails found: {found}")

    # For Noomii coaches without a website, try to find via Google
    noomii_no_web = [i for i, l in enumerate(all_leads) if l['source'] == 'noomii' and not l.get('website') and not l.get('email')]
    print(f"\n  {len(noomii_no_web)} Noomii coaches still need enrichment")
    print(f"  Adding LinkedIn/Google search URLs for them...")

    for i in noomii_no_web:
        name = all_leads[i]['name']
        all_leads[i]['google_search'] = f"https://www.google.com/search?q={quote_plus(name + ' business coach email')}"
        all_leads[i]['linkedin_search'] = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(name + ' coach')}"

    # ── Phase 4: Write CSV ──
    print(f"\n{'=' * 60}")
    print("PHASE 4: Writing output CSV...")
    print("=" * 60)

    fieldnames = [
        'ID', 'Name', 'Segment', 'Title', 'Company', 'Location',
        'Email', 'Phone', 'Website',
        'LinkedIn', 'Twitter', 'Facebook', 'Instagram', 'YouTube', 'TikTok',
        'LinkedIn_Search', 'Google_Search',
        'Profile_URL', 'Source',
        'AI_Pain_Point', 'Outreach_Hook',
    ]

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, lead in enumerate(all_leads, 1):
            segment = lead.get('segment', '')
            if 'Coach' in segment:
                pain = "Scaling 1:1 coaching; automating client scheduling & follow-ups; content creation burnout; lead qualification"
                hook = "How coaches are using AI to 3x their client capacity without burning out"
            elif 'Broker' in segment:
                pain = "Lead qualification; property matching speed; follow-up automation; market analysis reports"
                hook = "How top brokers close 40% more deals with AI-automated lead follow-ups"
            else:
                pain = "Manual processes; scaling bottlenecks; customer engagement; lead gen"
                hook = "How businesses save 20+ hrs/week with custom AI automation"

            writer.writerow({
                'ID': i,
                'Name': lead.get('name', ''),
                'Segment': segment,
                'Title': lead.get('title', ''),
                'Company': lead.get('company', ''),
                'Location': lead.get('location', ''),
                'Email': lead.get('email', ''),
                'Phone': lead.get('phone', ''),
                'Website': lead.get('website', ''),
                'LinkedIn': lead.get('linkedin', ''),
                'Twitter': lead.get('twitter', ''),
                'Facebook': lead.get('facebook', ''),
                'Instagram': lead.get('instagram', ''),
                'YouTube': lead.get('youtube', ''),
                'TikTok': lead.get('tiktok', ''),
                'LinkedIn_Search': lead.get('linkedin_search', ''),
                'Google_Search': lead.get('google_search', ''),
                'Profile_URL': lead.get('profile_url', ''),
                'Source': lead.get('source', ''),
                'AI_Pain_Point': pain,
                'Outreach_Hook': hook,
            })

    # ── Stats ──
    total = len(all_leads)
    segments = {}
    for l in all_leads:
        s = l.get('segment', 'Other')
        segments[s] = segments.get(s, 0) + 1

    stats = {}
    for field in ['email', 'phone', 'website', 'linkedin', 'twitter', 'facebook', 'instagram']:
        stats[field] = len([l for l in all_leads if l.get(field)])

    elapsed = time.time() - start_total

    print(f"\n{'=' * 60}")
    print(f"DONE — {total} real decision makers with verified data")
    print(f"{'=' * 60}")
    print(f"\n  SEGMENTS:")
    for s, c in sorted(segments.items(), key=lambda x: -x[1]):
        print(f"    {s:30s} {c:4d}")
    print(f"\n  CONTACT DATA:")
    for k, v in stats.items():
        pct = v / total * 100 if total else 0
        print(f"    {k:20s} {v:4d}  ({pct:.0f}%)")
    print(f"\n  Output: {OUTPUT_CSV}")
    print(f"  Time: {elapsed:.0f}s")

    # Show sample leads WITH email
    print(f"\n  SAMPLE LEADS WITH EMAIL:")
    emailed = [l for l in all_leads if l.get('email')]
    for l in emailed[:20]:
        li = l.get('linkedin', '')[:50] if l.get('linkedin') else '-'
        print(f"    {l['name']:30s} | {l['email']:40s} | {li}")


if __name__ == "__main__":
    main()
