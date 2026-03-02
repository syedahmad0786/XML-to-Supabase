"""
Final Lead Builder - Combines all data sources and deduplicates
Creates one master quality CSV with the best available contact info
"""

import csv
import re
from collections import defaultdict


def normalize_domain(url):
    if not url:
        return ""
    url = url.lower().strip().rstrip("/")
    for prefix in ["https://", "http://", "www."]:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0]


def normalize_phone(phone):
    if not phone:
        return ""
    return re.sub(r"[^\d+]", "", phone)


def load_csv(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f))


def main():
    # Load all sources
    companies_v2 = load_csv("companies_enriched_20260302_0004.csv")
    companies_v1 = load_csv("companies_enriched_20260301_2356.csv")
    dm_v1 = load_csv("decision_makers_20260301_2356.csv")

    print(f"Source 1 (Apollo+GMaps run2): {len(companies_v2)} companies")
    print(f"Source 2 (Apollo+GMaps run1): {len(companies_v1)} companies")
    print(f"Source 3 (Apify leads run1):  {len(dm_v1)} people")

    # ── Build master company index by domain ──
    company_index = {}  # domain -> best company record

    for source_name, companies in [("run2", companies_v2), ("run1", companies_v1)]:
        for c in companies:
            domain = normalize_domain(c.get("website", ""))
            if not domain:
                continue

            if domain not in company_index:
                company_index[domain] = {
                    "company": c.get("company", ""),
                    "website": c.get("website", ""),
                    "phone": c.get("phone", ""),
                    "linkedin_company": c.get("linkedin_company", ""),
                    "industry": c.get("industry", "") or c.get("category", ""),
                    "employees": c.get("employees", ""),
                    "city": c.get("city", ""),
                    "state": c.get("state", ""),
                    "country": c.get("country", ""),
                    "address": c.get("address", ""),
                    "rating": c.get("rating", ""),
                    "reviews": c.get("reviews", ""),
                    "source": source_name,
                }
            else:
                # Enrich existing
                existing = company_index[domain]
                for key in ["phone", "linkedin_company", "industry", "employees",
                            "city", "state", "country", "address", "rating", "reviews"]:
                    if c.get(key) and not existing.get(key):
                        existing[key] = c[key]

    print(f"\nUnique companies by domain: {len(company_index)}")

    # ── Build decision maker index ──
    DECISION_MAKER = re.compile(
        r"\b(ceo|cto|coo|cfo|cio|cmo|cpo|founder|co-founder|cofounder|"
        r"owner|partner|president|director|vp|vice president|"
        r"head of|chief|managing director|general manager|"
        r"svp|evp|principal|manager|senior|lead|architect)\b",
        re.IGNORECASE,
    )

    decision_makers = []
    seen_people = set()

    for p in dm_v1:
        name = p.get("full_name", "").strip()
        linkedin = p.get("linkedin", "").strip()
        email = p.get("email", "").strip()
        title = p.get("title", "").strip()

        if not name or name in seen_people:
            continue
        seen_people.add(name)

        # Must have either email or linkedin
        if not email and not linkedin:
            continue

        # Prefer decision makers but keep others with email
        is_dm = bool(DECISION_MAKER.search(title))

        company_domain = normalize_domain(p.get("company_website", ""))
        company_data = company_index.get(company_domain, {})

        decision_makers.append({
            "full_name": name,
            "title": title,
            "email": email,
            "phone": p.get("phone", ""),
            "linkedin_person": linkedin,
            "company": p.get("company", "") or company_data.get("company", ""),
            "company_website": p.get("company_website", "") or company_data.get("website", ""),
            "company_phone": company_data.get("phone", ""),
            "linkedin_company": p.get("company_linkedin", "") or company_data.get("linkedin_company", ""),
            "industry": str(p.get("company_industry", "")) or company_data.get("industry", ""),
            "company_size": str(p.get("company_size", "")) or company_data.get("employees", ""),
            "location": f"{p.get('company_city', '')}, {p.get('company_state', '')}".strip(", "),
            "is_decision_maker": "yes" if is_dm else "no",
            "source": "apify_leads",
        })

    # Sort: decision makers first, then by email presence
    decision_makers.sort(key=lambda x: (
        x["is_decision_maker"] != "yes",
        not x["email"],
        not x["linkedin_person"],
    ))

    dm_count = sum(1 for d in decision_makers if d["is_decision_maker"] == "yes")
    email_count = sum(1 for d in decision_makers if d["email"])

    print(f"People with contact info: {len(decision_makers)}")
    print(f"  Decision makers: {dm_count}")
    print(f"  With email: {email_count}")

    # ── Build final master output ──
    # Part 1: People (with contact info)
    # Part 2: Companies (without people matched yet - for outreach)

    master = []

    # Add people
    for p in decision_makers:
        master.append({
            "type": "person",
            "full_name": p["full_name"],
            "title": p["title"],
            "email": p["email"],
            "phone": p["phone"] or p["company_phone"],
            "linkedin": p["linkedin_person"],
            "company": p["company"],
            "company_website": p["company_website"],
            "company_linkedin": p["linkedin_company"],
            "industry": p["industry"],
            "company_size": p["company_size"],
            "location": p["location"],
            "is_decision_maker": p["is_decision_maker"],
            "source": p["source"],
        })

    # Add companies (that don't have matched people)
    people_domains = {normalize_domain(p["company_website"]) for p in decision_makers if p["company_website"]}

    for domain, c in company_index.items():
        if domain in people_domains:
            continue
        if not c.get("website") and not c.get("phone"):
            continue

        master.append({
            "type": "company",
            "full_name": "",
            "title": "",
            "email": "",
            "phone": c.get("phone", ""),
            "linkedin": c.get("linkedin_company", ""),
            "company": c.get("company", ""),
            "company_website": c.get("website", ""),
            "company_linkedin": c.get("linkedin_company", ""),
            "industry": c.get("industry", ""),
            "company_size": c.get("employees", ""),
            "location": f"{c.get('city', '')}, {c.get('state', '')}".strip(", "),
            "is_decision_maker": "",
            "source": c.get("source", ""),
        })

    # Save
    fieldnames = [
        "type", "full_name", "title", "email", "phone", "linkedin",
        "company", "company_website", "company_linkedin", "industry",
        "company_size", "location", "is_decision_maker", "source",
    ]

    with open("FINAL_QUALITY_LEADS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(master)

    # Stats
    people_rows = [r for r in master if r["type"] == "person"]
    company_rows = [r for r in master if r["type"] == "company"]
    total_with_email = sum(1 for r in master if r["email"])
    total_with_phone = sum(1 for r in master if r["phone"])
    total_with_linkedin = sum(1 for r in master if r["linkedin"])
    total_dm = sum(1 for r in master if r["is_decision_maker"] == "yes")

    print(f"\n{'=' * 55}")
    print(f"  FINAL QUALITY LEADS SUMMARY")
    print(f"{'=' * 55}")
    print(f"  Total rows:              {len(master)}")
    print(f"  People rows:             {len(people_rows)}")
    print(f"  Company rows:            {len(company_rows)}")
    print(f"  Decision makers:         {total_dm}")
    print(f"  With email:              {total_with_email}")
    print(f"  With phone:              {total_with_phone}")
    print(f"  With LinkedIn:           {total_with_linkedin}")
    print(f"  Saved to: FINAL_QUALITY_LEADS.csv")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()
