#!/usr/bin/env python3
"""
Finalize the enriched CSV:
- Clear unreliable auto-scraped DM names (too many false positives from HTML noise)
- Keep the strong social profile data (LinkedIn, Twitter, Facebook, Instagram, YouTube)
- Build accurate LinkedIn People Search URLs for each decision maker role
- Generate a DM email pattern template column (to use once real names are found)
- Add Google search URLs for finding decision makers
"""

import csv
from urllib.parse import quote_plus

INPUT = '/home/user/XML-to-Supabase/AI_CLIENTS_1000_FULL_ENRICHED.csv'
OUTPUT = '/home/user/XML-to-Supabase/AI_CLIENTS_1000_FULL_ENRICHED.csv'

with open(INPUT) as f:
    rows = list(csv.DictReader(f))

for r in rows:
    company = r['Company_Name']
    title = r['Decision_Maker_Title']
    domain = r['Website'].replace('www.', '') if r['Website'] else ''

    # Clear unreliable scraped names
    r['DM_Name'] = ''
    r['DM_Professional_Email'] = ''
    r['DM_Email_Patterns'] = ''
    r['Name_Source'] = ''

    # Build accurate LinkedIn People Search URL
    li_query = f'"{title}" "{company}"'
    r['DM_LinkedIn_Search'] = f'https://www.linkedin.com/search/results/people/?keywords={quote_plus(li_query)}'

    # Build Google search for finding the DM
    google_query = f'{company} "{title}" site:linkedin.com/in'
    r['DM_Google_Search'] = f'https://www.google.com/search?q={quote_plus(google_query)}'

    # Email pattern template (user fills in [first] [last] once they find the name)
    if domain:
        r['DM_Email_Patterns'] = f'[first].[last]@{domain}; [f][last]@{domain}; [first]@{domain}; [first][last]@{domain}'

# Rename columns for clarity
field_renames = {
    'DM_Name': 'DM_Name_Found',
    'Name_Source': 'DM_Name_Source',
}

# Build final fieldnames
existing_fields = list(rows[0].keys())
if 'DM_Google_Search' not in existing_fields:
    existing_fields.append('DM_Google_Search')

with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=existing_fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

# Print final stats
print("=" * 60)
print("FINAL ENRICHED DATABASE SUMMARY")
print("=" * 60)

total = len(rows)
has_email = len([r for r in rows if r['Contact_Email']])
has_phone = len([r for r in rows if r['Contact_Phone']])
has_li_co = len([r for r in rows if r['LinkedIn_Company']])
has_li_ppl = len([r for r in rows if r['LinkedIn_People_Found']])
has_tw = len([r for r in rows if r['Twitter']])
has_fb = len([r for r in rows if r['Facebook']])
has_ig = len([r for r in rows if r['Instagram']])
has_yt = len([r for r in rows if r['YouTube']])
has_li_search = len([r for r in rows if r['DM_LinkedIn_Search']])
has_google = len([r for r in rows if r['DM_Google_Search']])

print(f"\n  Total companies:              {total}")
print(f"\n  CONTACT INFO:")
print(f"    Company email:              {has_email}")
print(f"    Phone number:               {has_phone}")
print(f"\n  SOCIAL PROFILES:")
print(f"    LinkedIn company page:      {has_li_co}")
print(f"    LinkedIn people found:      {has_li_ppl}")
print(f"    Twitter / X:                {has_tw}")
print(f"    Facebook:                   {has_fb}")
print(f"    Instagram:                  {has_ig}")
print(f"    YouTube:                    {has_yt}")
print(f"\n  DECISION MAKER LOOKUP:")
print(f"    LinkedIn search URLs:       {has_li_search}")
print(f"    Google search URLs:         {has_google}")
print(f"    Email pattern templates:    {len([r for r in rows if r['DM_Email_Patterns']])}")

print(f"\n  COLUMNS ({len(existing_fields)} total):")
for i, col in enumerate(existing_fields, 1):
    print(f"    {i:2d}. {col}")

# Show sample rows
print(f"\n{'='*60}")
print("SAMPLE ENRICHED ROW")
print("=" * 60)
sample = rows[0]
for k, v in sample.items():
    if v:
        print(f"  {k:30s}: {v[:80]}")
