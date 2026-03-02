#!/usr/bin/env python3
"""
Multi-source lead scraper for AI automation prospects.
Scrapes real decision-makers from public directories:
  1. Noomii.com — Business coaches (3,292 profiles)
  2. BusinessCoachDirectory.com — Business coaches
  3. TheBrokerList.com — Real estate brokers (10,642 profiles)
  4. Personal website enrichment — emails, social links
"""

import csv
import re
import ssl
import json
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin, quote_plus
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
    'Accept-Language': 'en-US,en;q=0.5',
}

# ── Regexes ──
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'[\+]?1?[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}')
LINKEDIN_RE = re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?', re.I)
LINKEDIN_CO_RE = re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+/?', re.I)
TWITTER_RE = re.compile(r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?', re.I)
FACEBOOK_RE = re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9.\-]+/?', re.I)
INSTAGRAM_RE = re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._]+/?', re.I)
YOUTUBE_RE = re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|@)[a-zA-Z0-9\-_]+/?', re.I)
TIKTOK_RE = re.compile(r'(?:https?://)?(?:www\.)?tiktok\.com/@[a-zA-Z0-9._]+/?', re.I)

JUNK_EMAILS = {'sentry@', 'wixpress', 'schema.org', 'example.com', 'email.com', 'yourdomain',
               'test@', 'noreply', 'no-reply', 'donotreply', 'unsubscribe', '.png', '.jpg',
               '.gif', '.svg', 'favicon', 'googleusercontent', 'cloudflare', 'wp-content',
               'sentry.io', 'purl.org', 'w3.org', 'gravatar', 'wordpress', 'jquery',
               'bootstrapcdn', 'googleapis', 'gstatic', 'facebook.com', 'twitter.com',
               'linkedin.com', 'instagram.com', 'youtube.com', 'wix.com', 'squarespace',
               'shopify', 'mailchimp', 'hubspot', 'convertkit', 'activecampaign',
               '@sentry', 'protection#', '@2x', '@3x', 'apple-touch', '.webp'}


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
    """Filter out junk emails."""
    email = email.lower().strip().rstrip('.')
    for junk in JUNK_EMAILS:
        if junk in email:
            return None
    if len(email) < 6 or len(email) > 80:
        return None
    if email.count('@') != 1:
        return None
    return email


def extract_emails_from_html(html):
    """Extract real email addresses from HTML."""
    raw = EMAIL_RE.findall(html)
    clean = []
    seen = set()
    for e in raw:
        e = clean_email(e)
        if e and e not in seen:
            seen.add(e)
            clean.append(e)
    return clean


def extract_socials(html):
    """Extract social media URLs from HTML."""
    socials = {}
    li = LINKEDIN_RE.findall(html)
    if li:
        url = li[0]
        if not url.startswith('http'):
            url = 'https://' + url
        socials['linkedin'] = url

    li_co = LINKEDIN_CO_RE.findall(html)
    if li_co:
        url = li_co[0]
        if not url.startswith('http'):
            url = 'https://' + url
        socials['linkedin_company'] = url

    tw = TWITTER_RE.findall(html)
    for url in tw:
        if '/intent/' not in url and '/share' not in url:
            if not url.startswith('http'):
                url = 'https://' + url
            socials['twitter'] = url
            break

    fb = FACEBOOK_RE.findall(html)
    for url in fb:
        if '/sharer' not in url and '/share' not in url and '/tr?' not in url:
            if not url.startswith('http'):
                url = 'https://' + url
            socials['facebook'] = url
            break

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

    tt = TIKTOK_RE.findall(html)
    if tt:
        url = tt[0]
        if not url.startswith('http'):
            url = 'https://' + url
        socials['tiktok'] = url

    return socials


def scrape_personal_website(website_url):
    """Scrape a personal/business website for contact info."""
    result = {'emails': [], 'phones': [], 'socials': {}}

    if not website_url:
        return result

    if not website_url.startswith('http'):
        website_url = 'https://' + website_url

    pages_to_try = [
        website_url,
        website_url.rstrip('/') + '/contact',
        website_url.rstrip('/') + '/contact-us',
        website_url.rstrip('/') + '/about',
    ]

    all_html = ""
    for page_url in pages_to_try:
        try:
            html = fetch(page_url)
            all_html += " " + html
        except:
            pass

    if all_html:
        result['emails'] = extract_emails_from_html(all_html)
        result['socials'] = extract_socials(all_html)

        phones = PHONE_RE.findall(all_html)
        if phones:
            result['phones'] = list(set(phones[:3]))

    return result


# ════════════════════════════════════════
# SOURCE 1: NOOMII.COM — Business Coaches
# ════════════════════════════════════════
def scrape_noomii_listing(page_num):
    """Scrape one listing page of Noomii business coaches."""
    url = f"https://www.noomii.com/business-coaches?page={page_num}"
    coaches = []
    try:
        html = fetch(url)
        # Extract coach profile links and names
        pattern = re.compile(r'/users/([a-zA-Z0-9\-_]+)')
        text = strip_tags(html)

        # Parse more structured data from HTML
        name_pattern = re.compile(r'<h\d[^>]*>\s*<a[^>]*href="/users/([^"]+)"[^>]*>([^<]+)</a>', re.I)
        matches = name_pattern.findall(html)

        # Also try to get location
        for slug, name in matches:
            name = unescape(name).strip()
            if len(name) > 3 and len(name) < 50:
                coaches.append({
                    'name': name,
                    'profile_url': f'https://www.noomii.com/users/{slug}',
                    'source': 'noomii',
                    'segment': 'Business Coach',
                })
    except Exception as e:
        pass
    return coaches


def scrape_noomii_profile(profile_url):
    """Scrape detailed info from a Noomii coach profile page."""
    info = {
        'website': '', 'email': '', 'phone': '',
        'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '',
        'location': '', 'bio': '', 'company': '',
    }
    try:
        html = fetch(profile_url)
        text = strip_tags(html)

        # Website
        website_match = re.search(r'href="(https?://(?!www\.noomii)[^"]+)"[^>]*>(?:website|visit|www\.|http)', html, re.I)
        if not website_match:
            website_match = re.search(r'href="(https?://(?!www\.noomii|www\.facebook|www\.twitter|www\.linkedin|www\.instagram|www\.youtube)[^"]*)"[^>]*class="[^"]*website', html, re.I)
        if website_match:
            info['website'] = website_match.group(1)

        # Emails
        emails = extract_emails_from_html(html)
        if emails:
            info['email'] = emails[0]

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0]

        # Socials
        socials = extract_socials(html)
        info['linkedin'] = socials.get('linkedin', '')
        info['twitter'] = socials.get('twitter', '')
        info['facebook'] = socials.get('facebook', '')
        info['instagram'] = socials.get('instagram', '')

        # Location
        loc_match = re.search(r'(?:located?\s+in|based\s+in|from)\s+([A-Z][^,\n<]{3,30},\s*[A-Z][a-zA-Z\s]{2,20})', text)
        if loc_match:
            info['location'] = loc_match.group(1).strip()

        # Bio snippet
        bio_match = re.search(r'(?:about\s+me|my\s+approach|overview)\s*[:\-]?\s*(.{50,300})', text, re.I)
        if bio_match:
            info['bio'] = bio_match.group(1).strip()[:300]

    except Exception as e:
        pass
    return info


# ════════════════════════════════════════
# SOURCE 2: BUSINESSCOACHDIRECTORY.COM
# ════════════════════════════════════════
def scrape_bcd_listing():
    """Scrape BusinessCoachDirectory.com coach listings."""
    coaches = []
    for page in range(1, 6):
        url = f"https://businesscoachdirectory.com/coaches/page/{page}/" if page > 1 else "https://businesscoachdirectory.com/coaches/"
        try:
            html = fetch(url)
            pattern = re.compile(r'href="(https://businesscoachdirectory\.com/coach/[^"]+)"[^>]*>([^<]*)</a>', re.I)
            matches = pattern.findall(html)
            for profile_url, name in matches:
                name = unescape(name).strip()
                if name and len(name) > 2 and len(name) < 50 and not name.lower().startswith(('view', 'read', 'click', 'learn')):
                    coaches.append({
                        'name': name,
                        'profile_url': profile_url,
                        'source': 'businesscoachdirectory',
                        'segment': 'Business Coach',
                    })
        except:
            pass
    return coaches


def scrape_bcd_profile(profile_url):
    """Scrape detailed info from a BCD coach profile."""
    info = {
        'website': '', 'email': '', 'phone': '',
        'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '',
        'location': '', 'bio': '', 'company': '',
    }
    try:
        html = fetch(profile_url)
        text = strip_tags(html)

        # Extract all emails
        emails = extract_emails_from_html(html)
        if emails:
            info['email'] = emails[0]

        # Website links (excluding social media and the directory itself)
        website_match = re.search(
            r'href="(https?://(?!businesscoachdirectory|facebook|twitter|linkedin|instagram|youtube|x\.com)[^"]+)"',
            html, re.I
        )
        if website_match:
            url = website_match.group(1)
            if '.' in url and len(url) < 100:
                info['website'] = url

        # Socials
        socials = extract_socials(html)
        info['linkedin'] = socials.get('linkedin', '')
        info['twitter'] = socials.get('twitter', '')
        info['facebook'] = socials.get('facebook', '')
        info['instagram'] = socials.get('instagram', '')

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0]

    except:
        pass
    return info


# ════════════════════════════════════════
# SOURCE 3: THEBROKERLIST.COM — RE Brokers
# ════════════════════════════════════════
def scrape_brokerlist_listing(page_num):
    """Scrape one listing page of TheBrokerList."""
    brokers = []
    url = f"https://thebrokerlist.com/commercial-real-estate-brokers?page={page_num}"
    try:
        html = fetch(url)
        # Profile links pattern: /broker-slug-name
        pattern = re.compile(r'<a[^>]*href="(https://thebrokerlist\.com/[a-z0-9\-]+)"[^>]*>\s*([A-Z][^<]{2,40})\s*</a>', re.I)
        matches = pattern.findall(html)

        # Also try simpler pattern
        if not matches:
            pattern2 = re.compile(r'href="/([a-z0-9\-]{3,50})"[^>]*>([A-Z][a-z]+ [A-Z][a-z]+)', re.I)
            for slug, name in pattern2.findall(html):
                if slug not in ('commercial-real-estate-brokers', 'login', 'register', 'about', 'contact', 'blog', 'faq'):
                    matches.append((f'https://thebrokerlist.com/{slug}', name))

        seen_urls = set()
        for profile_url, name in matches:
            name = unescape(name).strip()
            if not profile_url.startswith('http'):
                profile_url = 'https://thebrokerlist.com' + profile_url if profile_url.startswith('/') else 'https://thebrokerlist.com/' + profile_url

            if profile_url not in seen_urls and len(name) > 3 and len(name) < 40:
                seen_urls.add(profile_url)
                brokers.append({
                    'name': name,
                    'profile_url': profile_url,
                    'source': 'thebrokerlist',
                    'segment': 'Real Estate Broker',
                })
    except Exception as e:
        pass
    return brokers


def scrape_brokerlist_profile(profile_url):
    """Scrape detailed info from a BrokerList profile."""
    info = {
        'website': '', 'email': '', 'phone': '',
        'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '',
        'location': '', 'bio': '', 'company': '',
    }
    try:
        html = fetch(profile_url)
        text = strip_tags(html)

        # Emails
        emails = extract_emails_from_html(html)
        if emails:
            info['email'] = emails[0]

        # Website
        website_match = re.search(
            r'href="(https?://(?!thebrokerlist|facebook|twitter|linkedin|instagram|youtube|x\.com)[^"]+)"[^>]*>(?:[^<]*(?:website|www\.|visit))',
            html, re.I
        )
        if website_match:
            info['website'] = website_match.group(1)

        # Phone
        phones = PHONE_RE.findall(text)
        if phones:
            info['phone'] = phones[0]

        # Socials
        socials = extract_socials(html)
        info['linkedin'] = socials.get('linkedin', '')
        info['twitter'] = socials.get('twitter', '')
        info['facebook'] = socials.get('facebook', '')
        info['instagram'] = socials.get('instagram', '')

        # Company name
        company_match = re.search(r'(?:company|firm|brokerage)[:\s]+([A-Z][^<\n]{3,50})', text, re.I)
        if company_match:
            info['company'] = company_match.group(1).strip()

        # Location
        loc_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})\b', text)
        if loc_match:
            info['location'] = f"{loc_match.group(1)}, {loc_match.group(2)}"

    except:
        pass
    return info


# ════════════════════════════════════════
# SOURCE 4: LIFECOACHHUB.COM — Life/Biz Coaches
# ════════════════════════════════════════
def scrape_lifecoachhub():
    """Scrape LifeCoachHub business coaches."""
    coaches = []
    for page in range(1, 6):
        url = f"https://lifecoachhub.com/business-coach/?page={page}"
        try:
            html = fetch(url)
            pattern = re.compile(r'href="(https://lifecoachhub\.com/[^"]*coach[^"]*)"[^>]*>\s*([A-Z][^<]{2,40})', re.I)
            for profile_url, name in pattern.findall(html):
                name = unescape(name).strip()
                if len(name) > 3 and len(name) < 50:
                    coaches.append({
                        'name': name,
                        'profile_url': profile_url,
                        'source': 'lifecoachhub',
                        'segment': 'Business Coach',
                    })
        except:
            pass
    return coaches


# ════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════
def main():
    all_leads = []

    # ── Phase 1: Scrape directory listings ──
    print("=" * 60)
    print("PHASE 1: Scraping directory listings...")
    print("=" * 60)

    # Noomii coaches (pages 1-15 = ~300 coaches)
    print("\n  [1/4] Noomii.com — Business Coaches...")
    noomii_leads = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scrape_noomii_listing, p) for p in range(1, 16)]
        for f in as_completed(futures):
            noomii_leads.extend(f.result())
    print(f"         Found {len(noomii_leads)} coach profiles")
    all_leads.extend(noomii_leads)

    # BCD coaches
    print("  [2/4] BusinessCoachDirectory.com...")
    bcd_leads = scrape_bcd_listing()
    print(f"         Found {len(bcd_leads)} coach profiles")
    all_leads.extend(bcd_leads)

    # BrokerList (pages 1-15 = ~150 brokers)
    print("  [3/4] TheBrokerList.com — RE Brokers...")
    broker_leads = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scrape_brokerlist_listing, p) for p in range(1, 16)]
        for f in as_completed(futures):
            broker_leads.extend(f.result())
    print(f"         Found {len(broker_leads)} broker profiles")
    all_leads.extend(broker_leads)

    # LifeCoachHub
    print("  [4/4] LifeCoachHub.com — Business Coaches...")
    lch_leads = scrape_lifecoachhub()
    print(f"         Found {len(lch_leads)} coach profiles")
    all_leads.extend(lch_leads)

    # Deduplicate by name
    seen_names = set()
    unique_leads = []
    for lead in all_leads:
        name_key = lead['name'].lower().strip()
        if name_key not in seen_names:
            seen_names.add(name_key)
            unique_leads.append(lead)
    all_leads = unique_leads
    print(f"\n  Total unique leads: {len(all_leads)}")

    # ── Phase 2: Scrape individual profiles ──
    print(f"\n{'=' * 60}")
    print("PHASE 2: Scraping individual profiles for contact info...")
    print("=" * 60)

    done = 0
    enriched = 0
    start = time.time()

    def enrich_profile(lead):
        profile_url = lead['profile_url']
        source = lead['source']

        if source == 'noomii':
            return scrape_noomii_profile(profile_url)
        elif source == 'businesscoachdirectory':
            return scrape_bcd_profile(profile_url)
        elif source == 'thebrokerlist':
            return scrape_brokerlist_profile(profile_url)
        else:
            return {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_profile, lead): i for i, lead in enumerate(all_leads)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                info = future.result()
                all_leads[idx].update(info)
                if info.get('email') or info.get('website'):
                    enriched += 1
            except:
                pass
            done += 1
            if done % 25 == 0 or done == len(all_leads):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(all_leads) - done) / rate if rate > 0 else 0
                print(f"  [{done:4d}/{len(all_leads)}] Enriched: {enriched} | {rate:.1f}/s | ETA: {eta:.0f}s")

    # ── Phase 3: Scrape personal websites for additional contact info ──
    print(f"\n{'=' * 60}")
    print("PHASE 3: Scraping personal websites for emails & socials...")
    print("=" * 60)

    leads_with_websites = [l for l in all_leads if l.get('website') and not l.get('email')]
    print(f"  {len(leads_with_websites)} leads have websites but no email yet")

    done2 = 0
    found_emails = 0
    start2 = time.time()

    def enrich_website(lead):
        return scrape_personal_website(lead.get('website', ''))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_website, lead): i
                   for i, lead in enumerate(all_leads) if lead.get('website') and not lead.get('email')}

        idx_map = {i: lead_idx for i, (lead_idx, lead) in
                   enumerate((i, l) for i, l in enumerate(all_leads) if l.get('website') and not l.get('email'))}

        # Rebuild: map futures to original lead indices
        lead_indices = [i for i, l in enumerate(all_leads) if l.get('website') and not l.get('email')]
        futures2 = {}
        for lead_idx in lead_indices:
            lead = all_leads[lead_idx]
            f = executor.submit(enrich_website, lead)
            futures2[f] = lead_idx

        for future in as_completed(futures2):
            lead_idx = futures2[future]
            try:
                ws_info = future.result()
                if ws_info['emails']:
                    all_leads[lead_idx]['email'] = ws_info['emails'][0]
                    found_emails += 1
                if ws_info['phones'] and not all_leads[lead_idx].get('phone'):
                    all_leads[lead_idx]['phone'] = ws_info['phones'][0]
                # Fill in missing socials
                for key in ('linkedin', 'twitter', 'facebook', 'instagram', 'youtube', 'tiktok'):
                    if ws_info['socials'].get(key) and not all_leads[lead_idx].get(key):
                        all_leads[lead_idx][key] = ws_info['socials'][key]
            except:
                pass
            done2 += 1
            if done2 % 20 == 0 or done2 == len(lead_indices):
                print(f"  [{done2:4d}/{len(lead_indices)}] New emails found: {found_emails}")

    # ── Phase 4: Write output ──
    print(f"\n{'=' * 60}")
    print("PHASE 4: Writing output CSV...")
    print("=" * 60)

    fieldnames = [
        'ID', 'Name', 'Segment', 'Company', 'Location',
        'Email', 'Phone', 'Website',
        'LinkedIn', 'Twitter', 'Facebook', 'Instagram', 'YouTube', 'TikTok',
        'Bio', 'Profile_URL', 'Source',
        'AI_Pain_Point', 'Outreach_Hook',
    ]

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, lead in enumerate(all_leads, 1):
            # Map pain points by segment
            segment = lead.get('segment', '')
            if 'Coach' in segment:
                pain = "Scaling 1:1 coaching; client scheduling; lead gen; content creation"
                hook = "How coaches are using AI to 3x their client capacity without burnout"
            elif 'Broker' in segment or 'Real Estate' in segment:
                pain = "Lead qualification; property matching; follow-up automation; market analysis"
                hook = "How top brokers use AI to close 40% more deals with automated follow-ups"
            elif 'Agency' in segment:
                pain = "Client deliverables; reporting; project management; scaling without hiring"
                hook = "How agencies are cutting delivery time 50% with AI automation"
            elif 'E-commerce' in segment:
                pain = "Customer support; inventory; marketing automation; order management"
                hook = "How e-commerce brands save 20hrs/week with AI-powered operations"
            elif 'SaaS' in segment:
                pain = "Customer onboarding; support tickets; churn prediction; dev automation"
                hook = "How SaaS founders reduce churn 30% with AI-powered customer success"
            else:
                pain = "Manual processes; scaling bottleneck; lead generation; customer engagement"
                hook = "How businesses are saving 20+ hours/week with custom AI automation"

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
                'Bio': lead.get('bio', '')[:300],
                'Profile_URL': lead.get('profile_url', ''),
                'Source': lead.get('source', ''),
                'AI_Pain_Point': pain,
                'Outreach_Hook': hook,
            })

    # ── Stats ──
    total = len(all_leads)
    has_email = len([l for l in all_leads if l.get('email')])
    has_phone = len([l for l in all_leads if l.get('phone')])
    has_website = len([l for l in all_leads if l.get('website')])
    has_linkedin = len([l for l in all_leads if l.get('linkedin')])
    has_twitter = len([l for l in all_leads if l.get('twitter')])
    has_facebook = len([l for l in all_leads if l.get('facebook')])
    has_instagram = len([l for l in all_leads if l.get('instagram')])

    print(f"\n{'=' * 60}")
    print(f"COMPLETE — {total} real decision makers found")
    print(f"{'=' * 60}")

    # Segment breakdown
    segments = {}
    for l in all_leads:
        s = l.get('segment', 'Other')
        segments[s] = segments.get(s, 0) + 1
    print(f"\n  SEGMENTS:")
    for s, c in sorted(segments.items(), key=lambda x: -x[1]):
        print(f"    {s:30s} {c:4d}")

    print(f"\n  CONTACT DATA:")
    print(f"    Email addresses:          {has_email}")
    print(f"    Phone numbers:            {has_phone}")
    print(f"    Websites:                 {has_website}")
    print(f"    LinkedIn profiles:        {has_linkedin}")
    print(f"    Twitter/X:                {has_twitter}")
    print(f"    Facebook:                 {has_facebook}")
    print(f"    Instagram:                {has_instagram}")

    print(f"\n  Output: {OUTPUT_CSV}")
    total_time = time.time() - start
    print(f"  Total time: {total_time:.0f}s")


if __name__ == "__main__":
    main()
