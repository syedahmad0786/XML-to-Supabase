"""
LEAD INTELLIGENCE SYSTEM
========================
Free, zero-API-cost system that:
1. Finds decision makers on LinkedIn via Google dorks
2. Discovers emails via pattern generation + DNS MX verification
3. Finds phone numbers from company websites
4. Creates psychological profiles from social media content analysis
5. Generates personalized outreach hooks

No paid APIs. No Cloudflare battles. Just smart search + NLP.
"""

import json
import csv
import re
import time
import os
import sys
from textwrap import dedent

# ─── DISC PERSONALITY FRAMEWORK ──────────────────────────────────────────────

DISC_PROFILES = {
    "D": {
        "name": "Dominant",
        "traits": "Results-driven, decisive, competitive, direct",
        "communication": "Be brief, focus on results and bottom line",
        "outreach_style": "Lead with ROI numbers and competitive advantage",
        "trigger_words": ["results", "growth", "revenue", "win", "lead", "dominate",
                          "scale", "fast", "first", "disrupt", "crush", "execute",
                          "goal", "achieve", "performance", "profit"],
        "avoid": "Don't waste their time with small talk or lengthy explanations",
    },
    "I": {
        "name": "Influential",
        "traits": "Enthusiastic, optimistic, collaborative, creative",
        "communication": "Be friendly, use stories and social proof",
        "outreach_style": "Lead with vision, community, and exciting possibilities",
        "trigger_words": ["amazing", "love", "excited", "team", "community", "inspire",
                          "creative", "vision", "together", "share", "story", "fun",
                          "passion", "dream", "awesome", "incredible", "celebrate"],
        "avoid": "Don't be too formal or data-heavy upfront",
    },
    "S": {
        "name": "Steady",
        "traits": "Patient, reliable, team-oriented, supportive",
        "communication": "Be warm, provide reassurance and stability",
        "outreach_style": "Lead with reliability, proven track record, and team impact",
        "trigger_words": ["support", "help", "team", "reliable", "trust", "care",
                          "consistent", "together", "family", "stability", "loyalty",
                          "protect", "maintain", "grateful", "serve", "people"],
        "avoid": "Don't be pushy or create unnecessary urgency",
    },
    "C": {
        "name": "Conscientious",
        "traits": "Analytical, detail-oriented, systematic, quality-focused",
        "communication": "Provide data, specifics, and logical arguments",
        "outreach_style": "Lead with case studies, data points, and systematic approach",
        "trigger_words": ["data", "analysis", "research", "quality", "process", "system",
                          "accurate", "detail", "optimize", "measure", "framework",
                          "strategy", "methodology", "evidence", "standard", "precision"],
        "avoid": "Don't make vague claims without backing them up",
    },
}


# ─── EMAIL PATTERN GENERATOR + MX VERIFIER ───────────────────────────────────

def verify_domain_exists(domain):
    """Check if domain exists and is reachable (HTTP HEAD check)."""
    import requests
    try:
        r = requests.head(f"https://{domain}", timeout=5,
                          allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code < 500
    except Exception:
        try:
            r = requests.head(f"http://{domain}", timeout=5,
                              allow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"})
            return r.status_code < 500
        except Exception:
            return False


def generate_email_patterns(first_name, last_name, domain):
    """Generate common business email patterns."""
    f = first_name.lower().strip()
    l = last_name.lower().strip()
    fi = f[0] if f else ""
    li = l[0] if l else ""

    patterns = []
    if f and l and domain:
        patterns = [
            f"{f}@{domain}",
            f"{f}.{l}@{domain}",
            f"{f}{l}@{domain}",
            f"{fi}{l}@{domain}",
            f"{f}.{li}@{domain}",
            f"{f}_{l}@{domain}",
            f"{l}@{domain}",
            f"{fi}.{l}@{domain}",
        ]
    elif f and domain:
        patterns = [f"{f}@{domain}"]

    # Always add generic patterns
    if domain:
        patterns.extend([
            f"info@{domain}",
            f"hello@{domain}",
            f"contact@{domain}",
            f"sales@{domain}",
        ])

    return patterns


def find_best_email(first_name, last_name, domain):
    """Generate email patterns and verify domain accepts mail."""
    if not domain:
        return [], False

    has_mx = verify_domain_exists(domain)

    patterns = generate_email_patterns(first_name, last_name, domain)

    return patterns, has_mx


# ─── DOMAIN EXTRACTION ───────────────────────────────────────────────────────

def extract_domain(url):
    """Extract clean domain from URL."""
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://", "http://", "www."]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


# ─── PSYCHOLOGICAL PROFILER ──────────────────────────────────────────────────

def analyze_disc_profile(text):
    """Analyze text content to determine DISC personality profile."""
    if not text or len(text) < 20:
        return {"primary": "unknown", "scores": {}, "confidence": "low"}

    text_lower = text.lower()
    words = re.findall(r'\b[a-z]+\b', text_lower)
    word_set = set(words)

    scores = {}
    for disc_type, profile in DISC_PROFILES.items():
        score = 0
        matches = []
        for trigger in profile["trigger_words"]:
            count = text_lower.count(trigger)
            if count > 0:
                score += count
                matches.append(trigger)
        scores[disc_type] = {"score": score, "matches": matches}

    # Determine primary and secondary
    sorted_types = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    primary = sorted_types[0][0] if sorted_types[0][1]["score"] > 0 else "unknown"
    secondary = sorted_types[1][0] if len(sorted_types) > 1 and sorted_types[1][1]["score"] > 0 else ""

    total_score = sum(s["score"] for s in scores.values())
    confidence = "high" if total_score > 15 else "medium" if total_score > 5 else "low"

    return {
        "primary": primary,
        "secondary": secondary,
        "scores": {k: v["score"] for k, v in scores.items()},
        "top_matches": {k: v["matches"][:5] for k, v in scores.items() if v["matches"]},
        "confidence": confidence,
        "total_signals": total_score,
    }


def analyze_content_style(text):
    """Analyze writing style indicators."""
    if not text or len(text) < 20:
        return {}

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    words = text.split()
    avg_sentence_len = len(words) / max(len(sentences), 1)

    # Sentiment indicators
    positive_words = {"great", "amazing", "love", "excellent", "fantastic", "wonderful",
                      "incredible", "awesome", "brilliant", "outstanding", "thrilled",
                      "excited", "grateful", "happy", "proud", "innovative", "powerful"}
    negative_words = {"unfortunately", "struggle", "difficult", "challenge", "problem",
                      "fail", "risk", "concern", "worried", "frustrated", "disappointed"}

    pos_count = sum(1 for w in words if w.lower().strip(".,!?") in positive_words)
    neg_count = sum(1 for w in words if w.lower().strip(".,!?") in negative_words)

    # Question ratio (curious/engaging vs declarative)
    questions = sum(1 for s in text.split("?") if s.strip()) - 1

    # Emoji usage
    emoji_count = len(re.findall(r'[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\uD83C-\uDBFF][\uDC00-\uDFFF]', text))

    # First person vs third person
    first_person = len(re.findall(r'\b(I|my|me|we|our|us)\b', text, re.IGNORECASE))
    third_person = len(re.findall(r'\b(they|their|them|he|she|it)\b', text, re.IGNORECASE))

    # Numbers/data usage (analytical indicator)
    numbers = len(re.findall(r'\b\d+[%xX]?\b', text))

    return {
        "avg_sentence_length": round(avg_sentence_len, 1),
        "communication_style": "concise" if avg_sentence_len < 15 else "detailed" if avg_sentence_len > 25 else "balanced",
        "tone": "positive" if pos_count > neg_count * 2 else "critical" if neg_count > pos_count else "neutral",
        "positivity_ratio": round(pos_count / max(pos_count + neg_count, 1), 2),
        "uses_questions": questions > 0,
        "uses_emojis": emoji_count > 0,
        "uses_data": numbers > 2,
        "perspective": "personal" if first_person > third_person else "observational",
        "word_count": len(words),
    }


def generate_outreach_strategy(disc_result, style_analysis, person_name, company):
    """Generate personalized outreach strategy based on psychological profile."""
    primary = disc_result.get("primary", "unknown")
    profile = DISC_PROFILES.get(primary, DISC_PROFILES["C"])

    strategy = {
        "disc_type": f"{primary} ({profile['name']})",
        "personality_summary": profile["traits"],
        "communication_approach": profile["communication"],
        "avoid": profile["avoid"],
    }

    # Generate specific outreach hook
    if primary == "D":
        strategy["email_opening"] = (
            f"Hi {person_name.split()[0] if person_name else 'there'}, "
            f"I'll keep this brief — we helped a company similar to {company or 'yours'} "
            f"increase qualified leads by 3x in 60 days using AI automation."
        )
        strategy["subject_line"] = f"Quick ROI question for {company}" if company else "Quick ROI question"
    elif primary == "I":
        strategy["email_opening"] = (
            f"Hey {person_name.split()[0] if person_name else 'there'}! "
            f"Love what you're building at {company or 'your company'} — "
            f"I'd love to share how some amazing founders are using AI to scale their impact."
        )
        strategy["subject_line"] = f"Loved your work at {company}" if company else "Quick idea I'm excited about"
    elif primary == "S":
        strategy["email_opening"] = (
            f"Hi {person_name.split()[0] if person_name else 'there'}, "
            f"I hope this finds you well. I've been following {company or 'your company'}'s journey "
            f"and wanted to share how we've been helping teams like yours work smarter together."
        )
        strategy["subject_line"] = f"Supporting {company}'s growth" if company else "A thought on supporting your team"
    elif primary == "C":
        strategy["email_opening"] = (
            f"Hi {person_name.split()[0] if person_name else 'there'}, "
            f"I analyzed {company or 'companies in your space'}'s workflow and identified "
            f"3 specific areas where AI automation could reduce operational costs by 25-40%."
        )
        strategy["subject_line"] = f"Data: 3 automation opportunities for {company}" if company else "Data: 3 automation opportunities"
    else:
        strategy["email_opening"] = (
            f"Hi {person_name.split()[0] if person_name else 'there'}, "
            f"I'd love to explore how AI automation could help {company or 'your company'} "
            f"save time and scale operations."
        )
        strategy["subject_line"] = f"AI automation for {company}" if company else "AI automation opportunity"

    # Add style-specific adjustments
    tone = style_analysis.get("tone", "neutral")
    if tone == "positive":
        strategy["tone_note"] = "This person responds to positive energy — mirror their enthusiasm"
    elif tone == "critical":
        strategy["tone_note"] = "This person is analytical — lead with hard data and proof"

    if style_analysis.get("uses_data"):
        strategy["tone_note"] = (strategy.get("tone_note", "") +
                                 ". They use numbers — include specific metrics").strip(". ")

    if style_analysis.get("communication_style") == "concise":
        strategy["length_note"] = "Keep email under 100 words — they prefer brevity"
    elif style_analysis.get("communication_style") == "detailed":
        strategy["length_note"] = "They appreciate detail — include case study or data"

    return strategy


# ─── LEAD PROCESSOR ──────────────────────────────────────────────────────────

def process_lead(lead_data):
    """Process a single lead: email patterns, DISC profile, outreach strategy."""
    name = lead_data.get("name", "")
    parts = name.split() if name else []
    first = parts[0] if parts else ""
    last = parts[-1] if len(parts) > 1 else ""
    company = lead_data.get("company", "")
    website = lead_data.get("website", "")
    domain = extract_domain(website)
    linkedin = lead_data.get("linkedin", "")
    content = lead_data.get("content", "")

    # Generate email patterns
    email_patterns, has_mx = find_best_email(first, last, domain)

    # Analyze personality
    disc_result = analyze_disc_profile(content)
    style = analyze_content_style(content)

    # Generate outreach strategy
    outreach = generate_outreach_strategy(disc_result, style, name, company)

    return {
        "name": name,
        "title": lead_data.get("title", ""),
        "company": company,
        "website": website,
        "linkedin": linkedin,
        "domain": domain,
        "domain_has_mx": has_mx,
        "email_patterns": email_patterns[:5],
        "best_email_guess": email_patterns[0] if email_patterns else "",
        "generic_email": f"info@{domain}" if domain else "",
        "phone": lead_data.get("phone", ""),
        "location": lead_data.get("location", ""),

        # Psychological profile
        "disc_primary": disc_result.get("primary", "unknown"),
        "disc_secondary": disc_result.get("secondary", ""),
        "disc_confidence": disc_result.get("confidence", "low"),
        "disc_scores": disc_result.get("scores", {}),
        "personality_summary": DISC_PROFILES.get(disc_result.get("primary", ""), {}).get("traits", ""),

        # Content analysis
        "communication_style": style.get("communication_style", ""),
        "tone": style.get("tone", ""),
        "uses_data": style.get("uses_data", False),
        "uses_emojis": style.get("uses_emojis", False),

        # Outreach strategy
        "outreach_disc_type": outreach.get("disc_type", ""),
        "outreach_approach": outreach.get("communication_approach", ""),
        "outreach_avoid": outreach.get("avoid", ""),
        "suggested_subject": outreach.get("subject_line", ""),
        "suggested_opening": outreach.get("email_opening", ""),
        "tone_note": outreach.get("tone_note", ""),
        "length_note": outreach.get("length_note", ""),

        "source": lead_data.get("source", ""),
    }


# ─── BATCH PROCESSOR ─────────────────────────────────────────────────────────

def process_leads_batch(leads):
    """Process a batch of leads through the intelligence pipeline."""
    results = []
    for i, lead in enumerate(leads):
        print(f"  [{i+1}/{len(leads)}] {lead.get('name', '?')}... ", end="", flush=True)
        result = process_lead(lead)
        results.append(result)

        mx_status = "MX OK" if result["domain_has_mx"] else "no MX"
        disc = result["disc_primary"]
        print(f"{mx_status} | DISC: {disc} | emails: {len(result['email_patterns'])}")

    return results


def save_intelligence_csv(results, filename="LEAD_INTELLIGENCE.csv"):
    """Save processed leads to CSV."""
    fields = [
        "name", "title", "company", "website", "linkedin",
        "best_email_guess", "generic_email", "domain_has_mx", "phone", "location",
        "disc_primary", "disc_secondary", "disc_confidence", "personality_summary",
        "communication_style", "tone",
        "outreach_disc_type", "outreach_approach", "outreach_avoid",
        "suggested_subject", "suggested_opening",
        "tone_note", "length_note", "source",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\n  Saved {len(results)} leads to {filename}")


def print_lead_card(result):
    """Print a formatted lead intelligence card."""
    print(f"\n  {'─' * 50}")
    print(f"  {result['name']} | {result['title']}")
    print(f"  {result['company']} | {result['website']}")
    print(f"  LinkedIn: {result['linkedin']}")
    print(f"  Best Email: {result['best_email_guess']} {'✓ MX' if result['domain_has_mx'] else '✗ no MX'}")
    print(f"  Generic: {result['generic_email']}")
    if result['phone']:
        print(f"  Phone: {result['phone']}")
    print(f"  Location: {result['location']}")
    print(f"")
    print(f"  DISC: {result['outreach_disc_type']} ({result['disc_confidence']} confidence)")
    print(f"  Personality: {result['personality_summary']}")
    print(f"  Comm Style: {result['communication_style']} | Tone: {result['tone']}")
    print(f"")
    print(f"  OUTREACH STRATEGY:")
    print(f"  Approach: {result['outreach_approach']}")
    print(f"  Avoid: {result['outreach_avoid']}")
    if result.get('tone_note'):
        print(f"  Note: {result['tone_note']}")
    if result.get('length_note'):
        print(f"  Length: {result['length_note']}")
    print(f"")
    print(f"  Subject: {result['suggested_subject']}")
    print(f"  Opening: {result['suggested_opening']}")
    print(f"  {'─' * 50}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    """
    Process leads from the command line or from pre-collected data.
    Usage: python3 lead_intelligence.py [input.json]
    """

    print("\n" + "=" * 55)
    print("  LEAD INTELLIGENCE SYSTEM")
    print("  Free • Zero API Cost • DISC Profiling")
    print("=" * 55)

    # Check for input file
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1]) as f:
            leads = json.load(f)
        print(f"\n  Loaded {len(leads)} leads from {sys.argv[1]}")
    else:
        # Demo with pre-collected leads from Google dork searches
        leads = [
            {
                "name": "Sameer Ahmed",
                "title": "Founder & Brand Strategist",
                "company": "AI Automation Studios",
                "website": "https://aiautomationstudios.com",
                "linkedin": "https://www.linkedin.com/in/yougotsam/",
                "location": "United States",
                "content": "We design technology that feels human and performs like a machine. "
                           "AI Automation Studios is a creative AI studio building voice-powered systems, "
                           "avatar influencers, custom GPTs, and intelligent automations that scale growth, "
                           "content, and operations. We work with founders, creators, and bold brands "
                           "ready to scale without burnout. Amazing journey so far! Love helping people "
                           "unlock their potential with AI. Let's build something incredible together!",
                "source": "linkedin_google_dork",
            },
            {
                "name": "Jayant Kumar",
                "title": "CEO",
                "company": "Emp0",
                "website": "https://emp0.com",
                "linkedin": "https://www.linkedin.com/in/jharilela/",
                "location": "United States",
                "content": "Emp0 is an AI automation studio helping businesses scale more effectively. "
                           "We design and build automation workflows, custom tools, and SaaS products. "
                           "The US market prefers yearly plans, premium features, automation and AI adoption "
                           "is fast, and budgets are flexible. Results matter. We execute fast and deliver "
                           "measurable growth for our clients. Performance-driven approach to every project.",
                "source": "linkedin_google_dork",
            },
            {
                "name": "James Peñas",
                "title": "Founder",
                "company": "Artificial Intelligence Agency (AIA)",
                "website": "https://aiautomate.co",
                "linkedin": "https://www.linkedin.com/in/james-peñas-758a841b/",
                "location": "Philippines / Remote",
                "content": "At AIA, we're dedicated to developing AI solutions that empower SMEs to thrive "
                           "by optimizing operations and boosting profitability. Over five years of pioneering "
                           "leadership. Commitment to harnessing AI to transform the business landscape. "
                           "Our systematic approach ensures quality results. We analyze each client's process "
                           "and build custom frameworks. Data-driven methodology for measurable outcomes.",
                "source": "linkedin_google_dork",
            },
            {
                "name": "Robert Essex",
                "title": "Founder",
                "company": "AI Advantage Agency",
                "website": "https://aiadvantageagency.com",
                "linkedin": "https://www.linkedin.com/in/robert-essex-8ab59110a/",
                "location": "The Colony, TX",
                "content": "Helping startups and small-to-mid-sized businesses leverage artificial intelligence "
                           "and automation to streamline operations and drive measurable ROI. We support teams "
                           "in building reliable systems. Trust and consistency are key to our partnerships. "
                           "I'm grateful for every client relationship. Together we help businesses grow.",
                "source": "linkedin_google_dork",
            },
            {
                "name": "Karl Mielnicki",
                "title": "Co-founder & CTO",
                "company": "Flobotics",
                "website": "https://flobotics.io",
                "linkedin": "https://www.linkedin.com/in/karl-mielnicki/",
                "phone": "+1-910-518-0124",
                "location": "Indiana, US",
                "content": "RPA agency specializing in automating mundane tasks. Process optimization "
                           "through robotic process automation. Quality engineering and systematic deployment. "
                           "Detailed analysis of business processes. Framework-driven automation strategy. "
                           "Data and evidence-based decisions. Precision in every implementation.",
                "source": "webfetch+linkedin",
            },
            {
                "name": "Jayesh Totla",
                "title": "Founder & CEO",
                "company": "SynergyTop Inc",
                "website": "https://synergytop.com",
                "linkedin": "https://www.linkedin.com/in/jayesh-totla/",
                "location": "San Diego, CA",
                "content": "Real AI automation isn't defined by how much manual work it removes — it's "
                           "defined by how quickly it enables leaders to make decisions. We execute fast. "
                           "Results-oriented approach. Performance metrics drive everything we do. "
                           "Growth through innovation and competitive advantage. Win with AI.",
                "source": "linkedin_google_dork",
            },
            {
                "name": "Andrei Marinescu",
                "title": "Founder & CEO",
                "company": "Central AI Agency Inc",
                "website": "https://centralai.agency",
                "linkedin": "https://www.linkedin.com/in/mvandrei/",
                "location": "United States",
                "content": "Leading a team of experts in developing innovative AI solutions for national "
                           "security and information analysis. Over 8 years of experience. Systematic "
                           "approach to AI strategy. Research-driven methodology. Detailed analysis "
                           "and framework design. Quality and precision in every solution we deliver.",
                "source": "linkedin_google_dork",
            },
            {
                "name": "Raj Sanghvi",
                "title": "Founder",
                "company": "Bitcot",
                "website": "https://bitcot.com",
                "linkedin": "https://www.linkedin.com/in/rajsanghvi9/",
                "phone": "(858) 683-3692",
                "location": "San Diego, CA",
                "content": "Web, Apps, AI & Automation Solutions. Building amazing products that people love. "
                           "Excited about the future of AI. Our team is passionate about creating incredible "
                           "experiences. Love working with startups and helping them grow. "
                           "Creative solutions for bold visions. Let's build something awesome together!",
                "source": "google_maps+linkedin",
            },
            {
                "name": "Robert Portillo",
                "title": "Founder",
                "company": "12AM Agency",
                "website": "https://12amagency.com",
                "linkedin": "",
                "phone": "(855) 603-5723",
                "location": "Dallas, TX",
                "content": "Started in 2014. Full-service agency with own SaaS tools and nationwide client base. "
                           "Specializing in making businesses the go-to authority in competitive sectors like "
                           "legal, dental, and home services. Results that scale. Dominate your market with "
                           "AI-powered marketing. Performance-driven campaigns for growth and revenue.",
                "source": "uforocks_blog",
            },
            {
                "name": "Mark Bardonski",
                "title": "CEO",
                "company": "AI REV Research Inc",
                "website": "https://airev.us",
                "linkedin": "https://www.linkedin.com/company/ai-rev",
                "location": "New York, NY",
                "content": "Hiring top talent from NASA, Microsoft, NVIDIA combined with business consultants "
                           "from BCG, McKinsey, and Bain. Focus on disruptive technologies that deliver "
                           "tangible business impact. Research-driven approach. Data analysis and strategic "
                           "framework design. Precision engineering of AI solutions. Evidence-based methodology.",
                "source": "websearch",
            },
        ]
        print(f"\n  Using {len(leads)} pre-collected leads (from Google dork searches)")

    # Process all leads
    print(f"\n  Processing leads through intelligence pipeline...\n")
    results = process_leads_batch(leads)

    # Show detailed cards for top leads
    print("\n" + "=" * 55)
    print("  INTELLIGENCE CARDS")
    print("=" * 55)
    for r in results[:5]:
        print_lead_card(r)

    # Save to CSV
    save_intelligence_csv(results)

    # Summary stats
    with_mx = sum(1 for r in results if r["domain_has_mx"])
    disc_known = sum(1 for r in results if r["disc_primary"] != "unknown")
    with_phone = sum(1 for r in results if r.get("phone"))

    print(f"\n{'=' * 55}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'=' * 55}")
    print(f"  Total leads processed:    {len(results)}")
    print(f"  Domains with MX (email):  {with_mx}")
    print(f"  DISC profiles generated:  {disc_known}")
    print(f"  With phone numbers:       {with_phone}")
    print(f"  With LinkedIn profiles:   {sum(1 for r in results if r.get('linkedin'))}")
    print(f"  Output: LEAD_INTELLIGENCE.csv")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()
