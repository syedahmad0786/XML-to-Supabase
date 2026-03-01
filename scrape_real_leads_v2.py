#!/usr/bin/env python3
"""
Multi-source lead scraper v2 — fixed profile extraction.
Scrapes real decision-makers from public directories:
  1. Noomii.com — Business coaches
  2. BusinessCoachDirectory.com — Business coaches
  3. TheBrokerList.com — Real estate brokers
  4. Personal websites — email enrichment
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
MAX_WORKERS = 10
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

# Social links belonging to the directories themselves (to filter out)
DIRECTORY_SOCIALS = {
    'twitter.com/bcd_coaching', 'linkedin.com/company/business-coach-directory',
    'facebook.com/businesscoachdirectory', 'facebook.com/thebrokerlist',
    'instagram.com/thebrokerlist', 'linkedin.com/company/thebrokerlist',
    'twitter.com/thebrokerlist', 'twitter.com/noomii', 'facebook.com/noomii',
    'linkedin.com/company/noomii', 'youtube.com/thebrokerlist',
    'youtube.com/businesscoachdirectory',
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


def is_directory_social(url):
    url_lower = url.lower()
    for ds in DIRECTORY_SOCIALS:
        if ds in url_lower:
            return True
    return False


def extract_social(html, pattern, skip_patterns=None):
    """Extract first social link matching pattern, skipping directory-owned links."""
    matches = pattern.findall(html)
    for url in matches:
        if not url.startswith('http'):
            url = 'https://' + url
        if is_directory_social(url):
            continue
        if skip_patterns:
            skip = False
            for sp in skip_patterns:
                if sp in url.lower():
                    skip = True
                    break
            if skip:
                continue
        return url
    return ''


def extract_all_socials(html):
    return {
        'linkedin': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?', re.I)),
        'linkedin_company': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+/?', re.I)),
        'twitter': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?', re.I), ['/intent/', '/share']),
        'facebook': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9.\-]+/?', re.I), ['/sharer', '/share', '/tr?']),
        'instagram': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?', re.I)),
        'youtube': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|@)[a-zA-Z0-9\-_]+/?', re.I)),
        'tiktok': extract_social(html, re.compile(r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9._]+/?', re.I)),
    }


def scrape_website_for_email(website_url):
    """Scrape a personal website for email, phone, socials."""
    result = {'emails': [], 'phones': [], 'socials': {}}
    if not website_url:
        return result
    if not website_url.startswith('http'):
        website_url = 'https://' + website_url

    urls = [website_url]
    for suffix in ['/contact', '/contact-us', '/about', '/about-us']:
        urls.append(website_url.rstrip('/') + suffix)

    all_html = ""
    for u in urls:
        try:
            all_html += " " + fetch(u)
        except:
            pass

    if all_html:
        result['emails'] = extract_emails(all_html)
        result['socials'] = extract_all_socials(all_html)
        phones = PHONE_RE.findall(all_html)
        result['phones'] = list(set(phones[:3]))

    return result


# ═══════════════════════════════════════════
# SOURCE 1: NOOMII — Business Coaches
# ═══════════════════════════════════════════
def scrape_noomii_listings(page_nums):
    """Scrape Noomii listing pages for coach profile links."""
    coaches = []
    for page in page_nums:
        url = f"https://www.noomii.com/business-coaches?page={page}"
        try:
            html = fetch(url)
            # Pattern: <a href="/users/slug">Name</a>
            for m in re.finditer(r'<a[^>]*href="/users/([^"]+)"[^>]*>([^<]+)</a>', html, re.I):
                slug, name = m.group(1), unescape(m.group(2)).strip()
                if len(name) > 3 and len(name) < 50 and ' ' in name:
                    coaches.append({
                        'name': name,
                        'profile_url': f'https://www.noomii.com/users/{slug}',
                        'source': 'noomii',
                        'segment': 'Business Coach',
                    })
        except:
            pass
    # Dedupe
    seen = set()
    unique = []
    for c in coaches:
        key = c['name'].lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def scrape_noomii_profile(url):
    """Scrape a single Noomii profile for website + contact info."""
    info = {'website': '', 'email': '', 'phone': '', 'location': '', 'company': '',
            'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '', 'youtube': '', 'tiktok': '', 'bio': ''}
    try:
        html = fetch(url)
        text = strip_tags(html)

        # Website — find external non-noomii links
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            link = m.group(1).lower()
            if 'noomii' not in link and 'google' not in link and 'cdn' not in link and \
               'fonts' not in link and 'facebook' not in link and 'twitter' not in link and \
               'linkedin' not in link and 'instagram' not in link and 'youtube' not in link and \
               'x.com' not in link and 'schema' not in link and 'w3.org' not in link and \
               'purl.org' not in link and 'cloudflare' not in link and 'googleapis' not in link and \
               'gstatic' not in link and 'wp-content' not in link:
                info['website'] = m.group(1)
                break

        # Socials from profile
        socials = extract_all_socials(html)
        for k in ('linkedin', 'twitter', 'facebook', 'instagram', 'youtube', 'tiktok'):
            info[k] = socials.get(k, '')

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0].strip()

        # Location
        loc = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s', text)
        if loc:
            info['location'] = f"{loc.group(1)}, {loc.group(2)}"

    except:
        pass
    return info


# ═══════════════════════════════════════════
# SOURCE 2: BCD — Business Coach Directory
# ═══════════════════════════════════════════
def scrape_bcd_listings():
    """Scrape BusinessCoachDirectory.com for coach profiles."""
    coaches = []
    for page in range(1, 8):
        url = f"https://businesscoachdirectory.com/coaches/page/{page}/" if page > 1 else "https://businesscoachdirectory.com/coaches/"
        try:
            html = fetch(url)
            for m in re.finditer(r'href="(https://businesscoachdirectory\.com/coach/[^"]+)"[^>]*>\s*([^<]+)', html, re.I):
                profile_url, name = m.group(1), unescape(m.group(2)).strip()
                if name and len(name) > 2 and len(name) < 50 and ' ' in name:
                    coaches.append({
                        'name': name,
                        'profile_url': profile_url,
                        'source': 'bcd',
                        'segment': 'Business Coach',
                    })
        except:
            pass
    # Dedupe
    seen = set()
    unique = []
    for c in coaches:
        key = c['name'].lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def scrape_bcd_profile(url):
    """Scrape a BCD coach profile for email, website, socials."""
    info = {'website': '', 'email': '', 'phone': '', 'location': '', 'company': '',
            'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '', 'youtube': '', 'tiktok': '', 'bio': ''}
    try:
        html = fetch(url)
        text = strip_tags(html)

        # Email
        emails = extract_emails(html)
        if emails:
            info['email'] = emails[0]

        # Website — find link to coach's own site
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            link = m.group(1).lower()
            if 'businesscoachdirectory' not in link and 'facebook' not in link and \
               'twitter' not in link and 'linkedin' not in link and 'instagram' not in link and \
               'youtube' not in link and 'x.com' not in link and 'w3.org' not in link and \
               'schema' not in link and 'gmpg.org' not in link and 'wordpress' not in link and \
               'wp-content' not in link and 'cdn' not in link and 'fonts' not in link and \
               'google' not in link and 'gravatar' not in link and 'cloudflare' not in link and \
               'xmlrpc' not in link and 'wp-json' not in link:
                info['website'] = m.group(1)
                break

        # Socials (filter out directory-owned links)
        socials = extract_all_socials(html)
        for k in ('linkedin', 'twitter', 'facebook', 'instagram', 'youtube', 'tiktok'):
            info[k] = socials.get(k, '')

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0].strip()

    except:
        pass
    return info


# ═══════════════════════════════════════════
# SOURCE 3: THEBROKERLIST — CRE Brokers
# ═══════════════════════════════════════════
def scrape_brokerlist_listings(page_nums):
    """Scrape TheBrokerList for broker profiles using /profiles/ID pattern."""
    brokers = []
    for page in page_nums:
        url = f"https://thebrokerlist.com/commercial-real-estate-brokers?page={page}"
        try:
            html = fetch(url)
            # Profile cards: <a href="/profiles/5390">David Perlmutter</a>
            for m in re.finditer(r'href="/profiles/(\d+)"[^>]*>([^<]{3,40})</a>', html, re.I):
                pid, text = m.group(1), unescape(m.group(2)).strip()
                # Only keep name-like text (has a space, starts with capital)
                if ' ' in text and text[0].isupper() and not any(w in text.lower() for w in ('view', 'click', 'see', 'read')):
                    brokers.append({
                        'name': text,
                        'profile_url': f'https://thebrokerlist.com/profiles/{pid}',
                        'source': 'brokerlist',
                        'segment': 'Real Estate Broker',
                    })
            # Also extract title/location info from card structure
            # Title is in second profile_title link, city/state in profile_city
            cards = re.finditer(
                r'profile_name[^>]*>.*?href="/profiles/(\d+)"[^>]*>([^<]+)</a>.*?'
                r'profile_title[^>]*>.*?href="/profiles/\1"[^>]*>([^<]+)</a>.*?'
                r'profile_city[^>]*>.*?href="/profiles/\1"[^>]*>([^<]+)</a>.*?'
                r'href="/profiles/\1"[^>]*>([^<]+)</a>',
                html, re.S | re.I
            )
            for m in cards:
                pid = m.group(1)
                # Update existing broker with title and location
                for b in brokers:
                    if b['profile_url'].endswith(f'/{pid}'):
                        b['title'] = unescape(m.group(3)).strip()
                        b['location'] = f"{unescape(m.group(4)).strip()}, {unescape(m.group(5)).strip()}"
                        break

        except Exception as e:
            pass

    # Dedupe
    seen = set()
    unique = []
    for b in brokers:
        key = b['name'].lower()
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique


def scrape_brokerlist_profile(profile_url):
    """Scrape a BrokerList profile for email, website, phone, socials."""
    info = {'website': '', 'email': '', 'phone': '', 'location': '', 'company': '',
            'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '', 'youtube': '', 'tiktok': '', 'bio': ''}

    # Try /profiles/ID URL and also slug URL
    try:
        html = fetch(profile_url)
        text = strip_tags(html)

        # Email
        emails = extract_emails(html)
        if emails:
            info['email'] = emails[0]

        # Website — external non-social links
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            link = m.group(1).lower()
            if 'thebrokerlist' not in link and 'facebook' not in link and \
               'twitter' not in link and 'linkedin' not in link and 'instagram' not in link and \
               'youtube' not in link and 'x.com' not in link and 'eepurl' not in link and \
               'icsc.org' not in link and 'google' not in link and 'cdn' not in link and \
               'fonts' not in link and 'cloudflare' not in link and 's3.amazon' not in link:
                info['website'] = m.group(1)
                break

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0].strip()

        # Socials (filter directory links)
        socials = extract_all_socials(html)
        for k in ('linkedin', 'twitter', 'facebook', 'instagram', 'youtube', 'tiktok'):
            info[k] = socials.get(k, '')

        # Company
        company = re.search(r'(?:company|firm|brokerage|organization)\s*:?\s*([A-Z][^<\n]{3,50})', text, re.I)
        if company:
            info['company'] = company.group(1).strip()

        # Location
        loc = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', text)
        if loc:
            info['location'] = f"{loc.group(1)}, {loc.group(2)}"

    except:
        pass
    return info


# ═══════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════
def main():
    all_leads = []
    start_total = time.time()

    print("=" * 60)
    print("PHASE 1: Scraping directory listings...")
    print("=" * 60)

    # 1. Noomii coaches (pages 1-20)
    print("\n  [1/3] Noomii.com — Business Coaches (20 pages)...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        page_batches = [list(range(i, min(i+4, 21))) for i in range(1, 21, 4)]
        futures = [ex.submit(scrape_noomii_listings, batch) for batch in page_batches]
        noomii_leads = []
        for f in as_completed(futures):
            noomii_leads.extend(f.result())
    # Dedupe across batches
    seen = set()
    unique_noomii = []
    for c in noomii_leads:
        k = c['name'].lower()
        if k not in seen:
            seen.add(k)
            unique_noomii.append(c)
    print(f"         Found {len(unique_noomii)} unique coaches")
    all_leads.extend(unique_noomii)

    # 2. BCD coaches
    print("  [2/3] BusinessCoachDirectory.com...")
    bcd_leads = scrape_bcd_listings()
    print(f"         Found {len(bcd_leads)} coaches")
    all_leads.extend(bcd_leads)

    # 3. BrokerList (pages 1-30)
    print("  [3/3] TheBrokerList.com — CRE Brokers (30 pages)...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        page_batches = [list(range(i, min(i+6, 31))) for i in range(1, 31, 6)]
        futures = [ex.submit(scrape_brokerlist_listings, batch) for batch in page_batches]
        broker_leads = []
        for f in as_completed(futures):
            broker_leads.extend(f.result())
    seen_brokers = set()
    unique_brokers = []
    for b in broker_leads:
        k = b['name'].lower()
        if k not in seen_brokers:
            seen_brokers.add(k)
            unique_brokers.append(b)
    print(f"         Found {len(unique_brokers)} unique brokers")
    all_leads.extend(unique_brokers)

    # Global dedup
    seen_all = set()
    unique_all = []
    for l in all_leads:
        k = l['name'].lower()
        if k not in seen_all:
            seen_all.add(k)
            unique_all.append(l)
    all_leads = unique_all
    print(f"\n  Total unique leads: {len(all_leads)}")

    # ── Phase 2: Scrape individual profiles ──
    print(f"\n{'=' * 60}")
    print("PHASE 2: Scraping profiles for contact info...")
    print("=" * 60)

    done = 0
    enriched_count = 0
    start = time.time()

    def enrich(lead):
        src = lead['source']
        url = lead['profile_url']
        if src == 'noomii':
            return scrape_noomii_profile(url)
        elif src == 'bcd':
            return scrape_bcd_profile(url)
        elif src == 'brokerlist':
            return scrape_brokerlist_profile(url)
        return {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich, l): i for i, l in enumerate(all_leads)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                info = future.result()
                all_leads[idx].update(info)
                if info.get('email') or info.get('website') or info.get('linkedin'):
                    enriched_count += 1
            except:
                pass
            done += 1
            if done % 50 == 0 or done == len(all_leads):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  [{done:4d}/{len(all_leads)}] Enriched: {enriched_count} | {rate:.1f}/s")

    # ── Phase 3: Website enrichment for leads missing email ──
    print(f"\n{'=' * 60}")
    print("PHASE 3: Scraping personal websites for emails...")
    print("=" * 60)

    need_email = [i for i, l in enumerate(all_leads) if l.get('website') and not l.get('email')]
    print(f"  {len(need_email)} leads have website but no email")

    found_emails = 0
    done3 = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_website_for_email, all_leads[i].get('website', '')): i for i in need_email}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                ws = future.result()
                if ws['emails']:
                    all_leads[idx]['email'] = ws['emails'][0]
                    found_emails += 1
                if ws['phones'] and not all_leads[idx].get('phone'):
                    all_leads[idx]['phone'] = ws['phones'][0]
                for k in ('linkedin', 'twitter', 'facebook', 'instagram', 'youtube', 'tiktok'):
                    if ws['socials'].get(k) and not all_leads[idx].get(k):
                        all_leads[idx][k] = ws['socials'][k]
            except:
                pass
            done3 += 1
            if done3 % 20 == 0 or done3 == len(need_email):
                print(f"  [{done3:4d}/{len(need_email)}] Emails found: {found_emails}")

    # ── Phase 4: Write CSV ──
    print(f"\n{'=' * 60}")
    print("PHASE 4: Writing output...")
    print("=" * 60)

    fieldnames = [
        'ID', 'Name', 'Segment', 'Company', 'Location',
        'Email', 'Phone', 'Website',
        'LinkedIn', 'Twitter', 'Facebook', 'Instagram', 'YouTube', 'TikTok',
        'Profile_URL', 'Source',
        'AI_Pain_Point', 'Outreach_Hook',
    ]

    rows_written = 0
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, lead in enumerate(all_leads, 1):
            segment = lead.get('segment', '')
            if 'Coach' in segment:
                pain = "Scaling 1:1 coaching; client scheduling; lead gen; content creation burnout"
                hook = "How coaches use AI to 3x client capacity without burnout"
            elif 'Broker' in segment or 'Real Estate' in segment:
                pain = "Lead qualification; property matching; follow-up automation; market analysis"
                hook = "How top brokers close 40% more deals with AI-automated follow-ups"
            else:
                pain = "Manual processes; scaling bottleneck; lead generation; customer engagement"
                hook = "How businesses save 20+ hrs/week with custom AI automation"

            writer.writerow({
                'ID': i,
                'Name': lead.get('name', ''),
                'Segment': segment,
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
                'Profile_URL': lead.get('profile_url', ''),
                'Source': lead.get('source', ''),
                'AI_Pain_Point': pain,
                'Outreach_Hook': hook,
            })
            rows_written += 1

    # ── Final Stats ──
    total = len(all_leads)
    stats = {
        'Email': len([l for l in all_leads if l.get('email')]),
        'Phone': len([l for l in all_leads if l.get('phone')]),
        'Website': len([l for l in all_leads if l.get('website')]),
        'LinkedIn': len([l for l in all_leads if l.get('linkedin')]),
        'Twitter': len([l for l in all_leads if l.get('twitter')]),
        'Facebook': len([l for l in all_leads if l.get('facebook')]),
        'Instagram': len([l for l in all_leads if l.get('instagram')]),
    }

    segments = {}
    for l in all_leads:
        s = l.get('segment', 'Other')
        segments[s] = segments.get(s, 0) + 1

    elapsed_total = time.time() - start_total

    print(f"\n{'=' * 60}")
    print(f"COMPLETE — {total} real decision makers")
    print(f"{'=' * 60}")
    print(f"\n  SEGMENTS:")
    for s, c in sorted(segments.items(), key=lambda x: -x[1]):
        print(f"    {s:30s} {c:4d}")
    print(f"\n  CONTACT DATA:")
    for k, v in stats.items():
        pct = (v / total * 100) if total > 0 else 0
        print(f"    {k:20s} {v:4d}  ({pct:.0f}%)")
    print(f"\n  Output: {OUTPUT_CSV}")
    print(f"  Time: {elapsed_total:.0f}s")

    # Show sample leads with email
    print(f"\n  SAMPLE LEADS WITH EMAIL:")
    emailed = [l for l in all_leads if l.get('email')]
    for l in emailed[:15]:
        print(f"    {l['name']:30s} | {l['email']:40s} | {l.get('linkedin','')[:50]}")


if __name__ == "__main__":
    main()
