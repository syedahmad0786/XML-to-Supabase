/**
 * Cheerio-based Lead Scraper
 *
 * 1. Scrapes AI company directories (Clutch, GoodFirms, etc.)
 * 2. Scrapes company websites for contact info (emails, phones, team)
 * 3. Combines everything into a quality leads CSV
 *
 * Zero API costs - pure web scraping
 */

const cheerio = require("cheerio");
const axios = require("axios");
const fs = require("fs");
const { parse } = require("csv-parse/sync");
const { stringify } = require("csv-stringify/sync");

const DELAY_MS = 1500;
const TIMEOUT_MS = 15000;
const MAX_RETRIES = 2;

const USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
];

// ─── HTTP Helper ─────────────────────────────────────────────────────────────

async function fetchPage(url, retries = MAX_RETRIES) {
  for (let i = 0; i <= retries; i++) {
    try {
      const resp = await axios.get(url, {
        timeout: TIMEOUT_MS,
        headers: {
          "User-Agent": USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)],
          Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Language": "en-US,en;q=0.9",
        },
        maxRedirects: 5,
      });
      return resp.data;
    } catch (err) {
      if (i < retries) {
        await sleep(2000 * (i + 1));
        continue;
      }
      return null;
    }
  }
  return null;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ─── Email / Phone Extractors ────────────────────────────────────────────────

const EMAIL_RE = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;
const PHONE_RE = /(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}/g;
const INTL_PHONE_RE = /\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{0,4}/g;

const JUNK_EMAIL_DOMAINS = new Set([
  "example.com", "test.com", "sentry.io", "wixpress.com", "w3.org",
  "schema.org", "googleapis.com", "google.com", "facebook.com",
  "twitter.com", "instagram.com", "youtube.com", "linkedin.com",
  "apple.com", "microsoft.com", "amazon.com", "cloudflare.com",
  "gravatar.com", "wordpress.com", "wp.com", "squarespace.com",
  "wix.com", "shopify.com", "mailchimp.com", "hubspot.com",
  "googleusercontent.com", "gstatic.com",
]);

function extractEmails(text) {
  const raw = text.match(EMAIL_RE) || [];
  return [...new Set(
    raw
      .map((e) => e.toLowerCase().trim())
      .filter((e) => {
        const domain = e.split("@")[1];
        if (JUNK_EMAIL_DOMAINS.has(domain)) return false;
        if (e.includes("..") || e.startsWith(".")) return false;
        if (/\.(png|jpg|svg|gif|css|js|webp)$/i.test(e)) return false;
        return true;
      })
  )];
}

function extractPhones(text) {
  const us = text.match(PHONE_RE) || [];
  const intl = text.match(INTL_PHONE_RE) || [];
  return [...new Set([...us, ...intl].map((p) => p.trim()))].slice(0, 5);
}

// ─── Social Links Extractor ──────────────────────────────────────────────────

function extractSocials($) {
  const socials = { linkedin: "", twitter: "", facebook: "" };
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href") || "";
    if (href.includes("linkedin.com/company") || href.includes("linkedin.com/in/"))
      socials.linkedin = socials.linkedin || href;
    if (href.includes("twitter.com/") || href.includes("x.com/"))
      socials.twitter = socials.twitter || href;
    if (href.includes("facebook.com/"))
      socials.facebook = socials.facebook || href;
  });
  return socials;
}

// ─── Team Page Finder & Scraper ──────────────────────────────────────────────

const TEAM_PAGE_PATTERNS = [
  /\b(about|team|leadership|people|our-team|about-us|management|staff|founders)\b/i,
];

function findTeamPageLinks($, baseUrl) {
  const links = [];
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href") || "";
    const text = $(el).text().trim().toLowerCase();
    const fullText = text + " " + href;

    if (TEAM_PAGE_PATTERNS.some((p) => p.test(fullText))) {
      try {
        const resolved = new URL(href, baseUrl).href;
        if (resolved.startsWith("http")) links.push(resolved);
      } catch {}
    }
  });
  return [...new Set(links)].slice(0, 3);
}

function extractTeamMembers($) {
  const members = [];

  // Common team member patterns
  const selectors = [
    ".team-member", ".member", ".staff-member", ".person",
    ".leadership-card", ".bio", ".team-card", ".team-item",
    '[class*="team"]', '[class*="member"]', '[class*="person"]',
    '[class*="staff"]', '[class*="leader"]',
  ];

  for (const sel of selectors) {
    $(sel).each((_, el) => {
      const block = $(el);
      const name = block.find("h2, h3, h4, .name, .title, strong").first().text().trim();
      const title = block.find("p, .position, .role, .job-title, span, em").first().text().trim();
      if (name && name.length > 2 && name.length < 60) {
        members.push({ name, title: title.length < 80 ? title : "" });
      }
    });
    if (members.length > 0) break;
  }

  return members.slice(0, 10);
}

// ─── Directory Scrapers ──────────────────────────────────────────────────────

async function scrapeClutch(category, pages = 3) {
  const results = [];
  console.log(`  Scraping Clutch.co: ${category}...`);

  for (let page = 0; page < pages; page++) {
    const url = page === 0
      ? `https://clutch.co/${category}`
      : `https://clutch.co/${category}?page=${page}`;

    const html = await fetchPage(url);
    if (!html) { console.log(`    Page ${page} failed`); continue; }

    const $ = cheerio.load(html);

    $(".provider-row, .provider-info, [data-provider], .directory-list .provider, li[class*='provider']").each((_, el) => {
      const block = $(el);
      const name = block.find("h3 a, h2 a, .company_info a, a.company_name, .directory-provider-title a").first().text().trim();
      const website = block.find("a.website-link, a[data-link-type='website']").attr("href") || "";
      const location = block.find(".locality, .location, [class*='location']").first().text().trim();
      const tagline = block.find(".tagline, .company_info__wrap p, .provider-info__description").first().text().trim();

      if (name && name.length > 1) {
        results.push({
          company: name,
          website,
          location,
          tagline,
          source: "clutch.co",
        });
      }
    });

    console.log(`    Page ${page}: ${results.length} total companies`);
    await sleep(DELAY_MS);
  }

  return results;
}

async function scrapeGoodFirms(category, pages = 3) {
  const results = [];
  console.log(`  Scraping GoodFirms: ${category}...`);

  for (let page = 1; page <= pages; page++) {
    const url = page === 1
      ? `https://www.goodfirms.co/${category}`
      : `https://www.goodfirms.co/${category}?page=${page}`;

    const html = await fetchPage(url);
    if (!html) { console.log(`    Page ${page} failed`); continue; }

    const $ = cheerio.load(html);

    $(".firm-detail, .profile-list-body, .agency-list-item, [class*='firm']").each((_, el) => {
      const block = $(el);
      const name = block.find("h3 a, h2 a, .firm-name a, .profile-name a").first().text().trim();
      const website = block.find("a.visit-website, a[class*='website']").attr("href") || "";
      const location = block.find(".firm-location, .location, [class*='location']").first().text().trim();

      if (name && name.length > 1) {
        results.push({
          company: name,
          website,
          location,
          tagline: "",
          source: "goodfirms.co",
        });
      }
    });

    console.log(`    Page ${page}: ${results.length} total companies`);
    await sleep(DELAY_MS);
  }

  return results;
}

// ─── Website Contact Scraper ─────────────────────────────────────────────────

async function scrapeCompanyWebsite(url) {
  const result = {
    emails: [],
    phones: [],
    socials: {},
    teamMembers: [],
    description: "",
  };

  if (!url || !url.startsWith("http")) return result;

  // Scrape homepage
  const html = await fetchPage(url);
  if (!html) return result;

  const $ = cheerio.load(html);

  // Extract from homepage
  const pageText = $("body").text();
  result.emails = extractEmails(pageText);
  result.phones = extractPhones(pageText);
  result.socials = extractSocials($);

  // Meta description
  result.description = $('meta[name="description"]').attr("content") || "";

  // Find and scrape contact page
  const contactLinks = [];
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href") || "";
    const text = $(el).text().trim().toLowerCase();
    if (/\b(contact|get-in-touch|reach-us|connect)\b/i.test(text + " " + href)) {
      try {
        contactLinks.push(new URL(href, url).href);
      } catch {}
    }
  });

  // Scrape contact page
  for (const contactUrl of [...new Set(contactLinks)].slice(0, 2)) {
    await sleep(800);
    const contactHtml = await fetchPage(contactUrl);
    if (!contactHtml) continue;

    const $c = cheerio.load(contactHtml);
    const contactText = $c("body").text();
    result.emails.push(...extractEmails(contactText));
    result.phones.push(...extractPhones(contactText));

    // Merge socials
    const newSocials = extractSocials($c);
    for (const [k, v] of Object.entries(newSocials)) {
      if (v && !result.socials[k]) result.socials[k] = v;
    }
  }

  // Find and scrape team/about page
  const teamLinks = findTeamPageLinks($, url);
  for (const teamUrl of teamLinks.slice(0, 1)) {
    await sleep(800);
    const teamHtml = await fetchPage(teamUrl);
    if (!teamHtml) continue;

    const $t = cheerio.load(teamHtml);
    result.teamMembers = extractTeamMembers($t);

    // Also grab emails from team page
    const teamText = $t("body").text();
    result.emails.push(...extractEmails(teamText));
  }

  // Deduplicate
  result.emails = [...new Set(result.emails)].slice(0, 10);
  result.phones = [...new Set(result.phones)].slice(0, 5);

  return result;
}

// ─── CSV Helpers ─────────────────────────────────────────────────────────────

function loadExistingCompanies() {
  const companies = [];
  const files = [
    "companies_enriched_20260302_0004.csv",
    "companies_enriched_20260301_2356.csv",
  ];

  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    const data = parse(fs.readFileSync(file, "utf-8"), { columns: true });
    companies.push(...data);
  }

  // Deduplicate by domain
  const seen = new Set();
  return companies.filter((c) => {
    const domain = normalizeDomain(c.website);
    if (!domain || seen.has(domain)) return false;
    seen.add(domain);
    return true;
  });
}

function normalizeDomain(url) {
  if (!url) return "";
  url = url.toLowerCase().trim().replace(/\/$/, "");
  for (const prefix of ["https://", "http://", "www."]) {
    if (url.startsWith(prefix)) url = url.slice(prefix.length);
  }
  return url.split("/")[0];
}

// ─── Main Pipeline ───────────────────────────────────────────────────────────

async function main() {
  console.log("\n" + "=".repeat(60));
  console.log("  CHEERIO-BASED LEAD SCRAPER");
  console.log("  Zero API costs - Pure web scraping");
  console.log("=".repeat(60));

  // ── Step 1: Scrape directories for AI companies ──
  console.log("\n[1/3] Scraping directories for AI companies...\n");

  const clutchCategories = [
    "it-services/artificial-intelligence",
    "it-services/machine-learning",
    "it-services/chatbot",
    "it-services/business-process-outsourcing",
  ];

  const goodFirmsCategories = [
    "artificial-intelligence/companies",
    "machine-learning-companies",
    "chatbot-development-companies",
  ];

  const directoryCompanies = [];

  for (const cat of clutchCategories) {
    const results = await scrapeClutch(cat, 2);
    directoryCompanies.push(...results);
  }

  for (const cat of goodFirmsCategories) {
    const results = await scrapeGoodFirms(cat, 2);
    directoryCompanies.push(...results);
  }

  console.log(`\n  Directory companies found: ${directoryCompanies.length}`);

  // ── Step 2: Load existing companies from CSV ──
  console.log("\n[2/3] Loading existing companies from earlier pipeline...");
  const existingCompanies = loadExistingCompanies();
  console.log(`  Existing companies: ${existingCompanies.length}`);

  // Merge directory companies with existing
  const allCompanies = [...existingCompanies];
  const seenDomains = new Set(existingCompanies.map((c) => normalizeDomain(c.website)));

  for (const dc of directoryCompanies) {
    const domain = normalizeDomain(dc.website);
    if (domain && !seenDomains.has(domain)) {
      seenDomains.add(domain);
      allCompanies.push({
        company: dc.company,
        website: dc.website,
        phone: "",
        linkedin_company: "",
        industry: dc.tagline || "",
        employees: "",
        city: "",
        state: "",
        country: "",
        address: dc.location || "",
        rating: "",
        reviews: "",
        source: dc.source,
      });
    }
  }

  console.log(`  Total unique companies: ${allCompanies.length}`);

  // ── Step 3: Scrape each company website for contact info ──
  console.log("\n[3/3] Scraping company websites for emails, phones, team...\n");

  const enrichedLeads = [];
  const withWebsite = allCompanies.filter((c) => c.website && c.website.startsWith("http"));
  const toScrape = withWebsite.slice(0, 200); // Limit to prevent excessive scraping

  console.log(`  Scraping ${toScrape.length} websites...\n`);

  for (let i = 0; i < toScrape.length; i++) {
    const company = toScrape[i];
    const domain = normalizeDomain(company.website);

    process.stdout.write(`  [${i + 1}/${toScrape.length}] ${company.company || domain}... `);

    const contact = await scrapeCompanyWebsite(company.website);

    const lead = {
      company: company.company || "",
      website: company.website || "",
      emails: contact.emails.join("; "),
      phones: (company.phone ? [company.phone, ...contact.phones] : contact.phones).join("; "),
      linkedin: contact.socials.linkedin || company.linkedin_company || "",
      twitter: contact.socials.twitter || "",
      facebook: contact.socials.facebook || "",
      industry: company.industry || company.category || "",
      employees: company.employees || "",
      city: company.city || "",
      state: company.state || "",
      location: company.address || `${company.city || ""}, ${company.state || ""}`.trim().replace(/^,|,$/g, ""),
      description: contact.description || "",
      team_members: contact.teamMembers.map((m) => `${m.name} (${m.title})`).join("; "),
      source: company.source || "",
    };

    enrichedLeads.push(lead);

    const found = [];
    if (contact.emails.length) found.push(`${contact.emails.length} emails`);
    if (contact.phones.length) found.push(`${contact.phones.length} phones`);
    if (contact.teamMembers.length) found.push(`${contact.teamMembers.length} team`);
    if (contact.socials.linkedin) found.push("linkedin");
    console.log(found.length ? found.join(", ") : "no contact info");

    await sleep(DELAY_MS);
  }

  // ── Save results ──
  console.log("\n" + "=".repeat(60));
  console.log("  SAVING RESULTS");
  console.log("=".repeat(60));

  const fields = [
    "company", "website", "emails", "phones", "linkedin",
    "twitter", "facebook", "industry", "employees",
    "location", "description", "team_members", "source",
  ];

  const csvOutput = stringify(enrichedLeads, { header: true, columns: fields });
  fs.writeFileSync("CHEERIO_ENRICHED_LEADS.csv", csvOutput);

  // Stats
  const withEmails = enrichedLeads.filter((l) => l.emails).length;
  const withPhones = enrichedLeads.filter((l) => l.phones).length;
  const withLinkedin = enrichedLeads.filter((l) => l.linkedin).length;
  const withTeam = enrichedLeads.filter((l) => l.team_members).length;

  console.log(`\n  Total companies scraped:  ${enrichedLeads.length}`);
  console.log(`  With emails:              ${withEmails}`);
  console.log(`  With phones:              ${withPhones}`);
  console.log(`  With LinkedIn:            ${withLinkedin}`);
  console.log(`  With team members:        ${withTeam}`);
  console.log(`\n  Saved to: CHEERIO_ENRICHED_LEADS.csv`);
  console.log("=".repeat(60));
}

main().catch(console.error);
