#!/usr/bin/env python3
"""Clean up false positive decision maker names."""
import csv
import re

INPUT = '/home/user/XML-to-Supabase/AI_CLIENTS_1000_FULL_ENRICHED.csv'

# Common first names (top ~500 US names) to validate against
COMMON_FIRST_NAMES = {
    'james', 'john', 'robert', 'michael', 'david', 'william', 'richard', 'joseph',
    'thomas', 'charles', 'christopher', 'daniel', 'matthew', 'anthony', 'mark',
    'donald', 'steven', 'paul', 'andrew', 'joshua', 'kenneth', 'kevin', 'brian',
    'george', 'timothy', 'ronald', 'edward', 'jason', 'jeffrey', 'ryan', 'jacob',
    'gary', 'nicholas', 'eric', 'jonathan', 'stephen', 'larry', 'justin', 'scott',
    'brandon', 'benjamin', 'samuel', 'raymond', 'gregory', 'frank', 'alexander',
    'patrick', 'jack', 'dennis', 'jerry', 'tyler', 'aaron', 'jose', 'adam',
    'nathan', 'henry', 'peter', 'zachary', 'douglas', 'harold', 'kyle', 'noah',
    'carl', 'gerald', 'keith', 'roger', 'arthur', 'terry', 'sean', 'austin',
    'jesse', 'ethan', 'bruce', 'ralph', 'roy', 'eugene', 'randy', 'wayne',
    'vincent', 'philip', 'russell', 'bobby', 'johnny', 'bradley', 'alex',
    'mary', 'patricia', 'jennifer', 'linda', 'barbara', 'elizabeth', 'susan',
    'jessica', 'sarah', 'karen', 'lisa', 'nancy', 'betty', 'margaret', 'sandra',
    'ashley', 'dorothy', 'kimberly', 'emily', 'donna', 'michelle', 'carol',
    'amanda', 'melissa', 'deborah', 'stephanie', 'rebecca', 'sharon', 'laura',
    'cynthia', 'kathleen', 'amy', 'angela', 'shirley', 'anna', 'brenda',
    'pamela', 'emma', 'nicole', 'helen', 'samantha', 'katherine', 'christine',
    'debra', 'rachel', 'carolyn', 'janet', 'catherine', 'maria', 'heather',
    'diane', 'ruth', 'julie', 'olivia', 'joyce', 'virginia', 'victoria',
    'kelly', 'lauren', 'christina', 'joan', 'evelyn', 'judith', 'megan',
    'andrea', 'cheryl', 'hannah', 'jacqueline', 'martha', 'gloria', 'teresa',
    'ann', 'sara', 'madison', 'frances', 'kathryn', 'janice', 'jean', 'abigail',
    'alice', 'judy', 'sophia', 'grace', 'denise', 'amber', 'doris', 'marilyn',
    'danielle', 'beverly', 'isabella', 'theresa', 'diana', 'natalie', 'brittany',
    'charlotte', 'marie', 'kayla', 'alexis', 'lori', 'matt', 'mike', 'tom',
    'bob', 'bill', 'steve', 'chris', 'dan', 'jim', 'jeff', 'dave', 'joe',
    'tony', 'greg', 'phil', 'ted', 'fred', 'ed', 'rob', 'ben', 'sam', 'ken',
    'don', 'rick', 'nick', 'chad', 'troy', 'brett', 'derek', 'lance', 'todd',
    'craig', 'alan', 'dean', 'dale', 'lloyd', 'barry', 'leon', 'neil', 'earl',
    'stuart', 'raj', 'amit', 'priya', 'deepak', 'sanjay', 'rahul', 'anand',
    'suresh', 'kumar', 'vijay', 'prakash', 'arun', 'ravi', 'naveen', 'vivek',
    'wei', 'ming', 'jun', 'yong', 'jing', 'tao', 'gang', 'lei', 'feng',
    'carlos', 'luis', 'jorge', 'miguel', 'pedro', 'juan', 'pablo', 'mario',
    'marco', 'sergio', 'roberto', 'martin', 'hans', 'stefan', 'andreas',
    'pete', 'stan', 'ray', 'max', 'ian', 'lee', 'kai', 'cole', 'luke',
    'drew', 'brad', 'doug', 'marc', 'seth', 'ross', 'kurt', 'carl', 'earl',
    'hugh', 'brent', 'blake', 'byron', 'clark', 'clint', 'clay', 'cliff',
    'cody', 'corey', 'dallas', 'darren', 'darryl', 'daryl', 'dwayne',
    'dylan', 'elijah', 'elliot', 'ernie', 'evan', 'everett', 'felix',
    'fernando', 'francisco', 'franklin', 'gabriel', 'garrett', 'gene',
    'glen', 'gordon', 'grant', 'hank', 'harvey', 'heath', 'hector',
    'herbert', 'herman', 'howard', 'irving', 'isaac', 'ivan', 'jared',
    'jerome', 'joel', 'jonah', 'jordan', 'liam', 'logan', 'mason',
    'oscar', 'owen', 'parker', 'perry', 'preston', 'quincy', 'reid',
    'rex', 'riley', 'ruben', 'salvador', 'simon', 'spencer', 'trent',
    'trevor', 'troy', 'vernon', 'victor', 'wade', 'warren', 'wesley',
    'wyatt', 'xavier', 'steph', 'neeraj', 'ash', 'arjun', 'vikram',
}

# Words that should NOT appear in a person name
BAD_WORDS = {
    'read', 'bio', 'more', 'press', 'room', 'leadership', 'team', 'about',
    'explore', 'global', 'executive', 'industry', 'industries', 'new', 'view',
    'the', 'our', 'all', 'best', 'top', 'biggest', 'most', 'world', 'premier',
    'national', 'regional', 'local', 'north', 'south', 'east', 'west',
    'award', 'awards', 'news', 'info', 'terms', 'contact', 'home', 'service',
    'services', 'solutions', 'technology', 'digital', 'data', 'health',
    'care', 'medical', 'legal', 'property', 'properties', 'real', 'estate',
    'company', 'group', 'partners', 'associates', 'management', 'consulting',
    'capital', 'financial', 'insurance', 'marketing', 'design', 'software',
    'systems', 'network', 'professional', 'dedicated', 'memorial', 'highway',
    'transaction', 'advises', 'appoints', 'launches', 'announces', 'joins',
    'named', 'elected', 'promotes', 'hires', 'welcomes', 'foot', 'athletes',
    'exceptional', 'primary', 'illuminating', 'mistakes', 'south', 'wales',
    'state', 'county', 'city', 'street', 'avenue', 'drive', 'road',
    'building', 'floor', 'suite', 'office', 'headquarters',
}


def is_real_name(name):
    """Strict validation: check if name looks like a real person."""
    if not name:
        return False

    parts = name.split()
    if len(parts) < 2 or len(parts) > 3:
        return False

    # Check for bad words
    for p in parts:
        if p.lower() in BAD_WORDS:
            return False

    # First word should be a recognizable first name
    first = parts[0].lower()
    if first not in COMMON_FIRST_NAMES and len(first) < 3:
        return False

    # If first name isn't in our list, be stricter
    if first not in COMMON_FIRST_NAMES:
        # At least the last name should look like a name (capitalized, reasonable length)
        last = parts[-1]
        if not last[0].isupper() or len(last) < 2:
            return False
        # Neither part should be all caps or have weird patterns
        for p in parts:
            if p.isupper() and len(p) > 2:
                return False

    return True


with open(INPUT) as f:
    rows = list(csv.DictReader(f))

cleaned = 0
kept = 0
for r in rows:
    if r['DM_Name']:
        if is_real_name(r['DM_Name']):
            kept += 1
        else:
            cleaned += 1
            r['DM_Name'] = ''
            r['DM_Professional_Email'] = ''
            r['DM_Email_Patterns'] = ''
            r['Name_Source'] = 'none'

fieldnames = list(rows[0].keys())
with open(INPUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print(f"Kept: {kept} real names | Removed: {cleaned} false positives")
print(f"\nValid decision maker names:")
named = [r for r in rows if r['DM_Name']]
for r in named[:20]:
    print(f"  {r['Company_Name']:30s} | {r['DM_Name']:25s} | {r['Decision_Maker_Title']:25s} | {r['DM_Professional_Email']}")

# Social stats
li_co = len([r for r in rows if r['LinkedIn_Company']])
tw = len([r for r in rows if r['Twitter']])
fb = len([r for r in rows if r['Facebook']])
ig = len([r for r in rows if r['Instagram']])
yt = len([r for r in rows if r['YouTube']])
li_ppl = len([r for r in rows if r['LinkedIn_People_Found']])
print(f"\nSocial profiles: LI-Co={li_co} | Twitter={tw} | Facebook={fb} | Instagram={ig} | YouTube={yt} | LI-People={li_ppl}")
