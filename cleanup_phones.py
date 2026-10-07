#!/usr/bin/env python3
import csv, re

INPUT = '/home/user/XML-to-Supabase/AI_CLIENTS_1000_ENRICHED.csv'
BAD_PHONES = {'9999999999', '2147483647', '0000000000', '1111111111', '1234567890', '8888888888'}

def format_phone(p):
    if not p:
        return ''
    digits = re.sub(r'\D', '', p)
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) != 10:
        return ''
    if digits in BAD_PHONES:
        return ''
    return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'

with open(INPUT) as f:
    rows = list(csv.DictReader(f))

cleaned_phones = 0
removed_phones = 0
for r in rows:
    orig = r['Contact_Phone']
    r['Contact_Phone'] = format_phone(r['Contact_Phone'])
    if orig and not r['Contact_Phone']:
        removed_phones += 1
    elif r['Contact_Phone']:
        cleaned_phones += 1

    if r['Alt_Phones']:
        alts = [format_phone(p.strip()) for p in r['Alt_Phones'].split(';')]
        r['Alt_Phones'] = '; '.join([a for a in alts if a])

fieldnames = list(rows[0].keys())
with open(INPUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

valid = len([r for r in rows if r['Contact_Phone']])
print(f'Formatted: {cleaned_phones} | Removed invalid: {removed_phones} | Valid phones: {valid}')

print('\nSample enriched rows:')
for r in rows[:10]:
    print(f'  {r["Company_Name"]:35s} | {r["Contact_Email"]:40s} | {r["Contact_Phone"]:15s} | src={r["Email_Source"]}')
