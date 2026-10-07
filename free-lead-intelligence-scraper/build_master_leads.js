/**
 * Final Master Lead Builder
 * Combines all scraped data from WebSearch, WebFetch, Google Maps, Apollo, and Cheerio
 * into one definitive quality leads CSV
 */

const fs = require("fs");
const { parse } = require("csv-parse/sync");
const { stringify } = require("csv-stringify/sync");

// ─── ALL SCRAPED DATA (from WebSearch + WebFetch sessions) ───────────────────

const SCRAPED_COMPANIES = [
  // From UFO Rocks blog (phones verified)
  { company: "UFO Performance Marketing", website: "https://uforocks.com", phone: "(513) 549-7355", location: "Cincinnati, OH", email: "", founder: "", industry: "AI Automation Agency", source: "uforocks_blog" },
  { company: "GenAI-Labs", website: "https://genai-labs.io", phone: "(323) 522-4040", location: "Los Angeles, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Itransition", website: "https://itransition.com", phone: "(512) 501-3620", location: "Lakewood, CO", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "PrimeLoop", website: "https://primeloop.co", phone: "", location: "San Francisco, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "InnovvaTek", website: "https://innovvatek.com", phone: "(888) 400-5050", location: "Albuquerque, NM", email: "", founder: "", industry: "AI-Driven GTM & Automation", linkedin: "https://www.linkedin.com/company/innovvatek", source: "uforocks_blog+webfetch" },
  { company: "AppMakers USA", website: "https://appmakersla.com", phone: "(310) 388-6435", location: "Los Angeles, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Glorium Technologies", website: "https://gloriumtech.com", phone: "(888) 354-0883", location: "Princeton, NJ", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "12AM Agency", website: "https://12amagency.com", phone: "(855) 603-5723", location: "Dallas, TX", email: "", founder: "Robert Portillo", industry: "AI Automation Agency", source: "uforocks_blog" },
  { company: "AddWeb Solution", website: "https://addwebsolution.com", phone: "(864) 900-3966", location: "Greenville, SC", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Geomotiv", website: "https://geomotiv.com", phone: "(571) 559-7486", location: "Alexandria, VA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Empat", website: "https://empat.tech", phone: "(415) 712-3342", location: "San Francisco, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Unico Connect", website: "https://unicoconnect.com", phone: "(747) 296-1276", location: "Chicago, IL", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Scopic", website: "https://scopicsoftware.com", phone: "(508) 886-3240", location: "Marlborough, MA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "WEBITMD", website: "https://webitmd.com", phone: "(310) 405-0502", location: "Los Angeles, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Axe Automation", website: "https://axeautomation.co", phone: "(707) 479-7131", location: "Marina del Rey, CA", email: "", founder: "", industry: "AI Automation Agency", linkedin: "https://www.linkedin.com/company/axeautomation/", source: "uforocks_blog+webfetch" },
  { company: "Automation Agency", website: "https://automationagency.com", phone: "", location: "Remote-first", email: "", founder: "Carl Taylor", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Markovate", website: "https://markovate.com", phone: "(415) 980-3786", location: "San Francisco, CA", email: "info@markovate.com", founder: "", industry: "AI Consulting", source: "uforocks_blog+webfetch" },
  { company: "HatchWorks AI", website: "https://hatchworks.com", phone: "(800) 621-7063", location: "Atlanta, GA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Bitcot", website: "https://bitcot.com", phone: "(858) 683-3692", location: "San Diego, CA", email: "", founder: "Raj Sanghvi", industry: "Chatbot Development", source: "uforocks_blog+websearch" },
  { company: "LeewayHertz", website: "https://leewayhertz.com", phone: "(415) 301-2880", location: "San Francisco, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Aisera", website: "https://aisera.com", phone: "(650) 667-4308", location: "Santa Clara, CA", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },
  { company: "Cognizant", website: "https://cognizant.com", phone: "(888) 937-3277", location: "Teaneck, NJ", email: "", founder: "", industry: "AI Automation", source: "uforocks_blog" },

  // From WebFetch contact page scraping (verified emails + phones)
  { company: "Xcelacore", website: "https://xcelacore.com", phone: "(888) 773-2081", location: "Oak Brook, IL 60523", email: "contactus@xcelacore.com", founder: "", industry: "AI Consulting", source: "webfetch" },
  { company: "AI Automation Agency", website: "https://aiautomation.agency", phone: "", location: "", email: "hello@aiautomation.agency", founder: "", industry: "AI Automation", linkedin: "https://www.linkedin.com/company/aiautomationagency/", source: "webfetch" },
  { company: "Idealink Tech", website: "https://idealink.tech", phone: "", location: "London, UK", email: "info@idealink.tech", founder: "Rokas Jurkėnas", industry: "AI Automation Agency", source: "webfetch" },
  { company: "The AI Automation Agency", website: "https://theaiautomationagency.ai", phone: "0333 051 0634", location: "UK", email: "", founder: "Myles Robinson", industry: "AI Automation", source: "webfetch" },
  { company: "Authority AI", website: "https://authorityai.ai", phone: "+1-954-716-8740", location: "Fort Lauderdale, FL 33301", email: "info@authorityai.ai", founder: "", industry: "AI Solutions Small Business", source: "webfetch" },
  { company: "Prismetric", website: "https://prismetric.com", phone: "+1 323 825 3076", location: "Jersey City, NJ 07306", email: "sales@prismetric.com", founder: "", industry: "AI Automation Agency", source: "webfetch" },
  { company: "SmartSites", website: "https://smartsites.com", phone: "201-870-6000", location: "Paramus, NJ 07652", email: "contact@smartsites.com", founder: "", industry: "AI Marketing Automation", source: "webfetch" },
  { company: "Flobotics", website: "https://flobotics.io", phone: "+1-910-518-0124", location: "Indiana, US", email: "info@flobotics.io", founder: "Karl Mielnicki (CTO)", industry: "RPA Agency", source: "webfetch" },
  { company: "AI REV Research", website: "https://airev.us", phone: "", location: "New York, NY 10017", email: "contact@airev.us", founder: "Mark Bardonski (CEO)", industry: "AI Consulting", linkedin: "https://www.linkedin.com/company/ai-rev", source: "webfetch+websearch" },
  { company: "BotsCrew", website: "https://botscrew.com", phone: "+1(415) 941-0077", location: "San Francisco, CA 94104", email: "", founder: "", industry: "Chatbot Development", source: "webfetch" },

  // From WebSearch (Crunchbase / verified)
  { company: "Applied AI Consulting (AAIC)", website: "https://appliedaiconsulting.com", phone: "", location: "McKinney, TX", email: "", founder: "Vijay Roy (CEO)", industry: "AI Consulting", source: "crunchbase" },
  { company: "Thought AI", website: "https://thought.ai", phone: "", location: "Harrisburg, PA", email: "", founder: "Andrew J Hacker (CEO)", industry: "AI Consulting", source: "crunchbase" },
  { company: "Biz4Group", website: "https://biz4group.com", phone: "", location: "USA", email: "", founder: "Sanjeev Verma (CEO)", industry: "Chatbot Development", source: "websearch" },
  { company: "OyeLabs", website: "https://oyelabs.com", phone: "", location: "USA", email: "", founder: "Anuraag (CEO)", industry: "Chatbot Development", source: "websearch" },
  { company: "Sigmoid", website: "https://sigmoid.com", phone: "", location: "USA", email: "", founder: "Rahul Kumar Singh (CAO)", industry: "AI Consulting", source: "websearch" },
  { company: "Superside", website: "https://superside.com", phone: "", location: "USA", email: "", founder: "Fredrik Thomassen (CEO)", industry: "AI Consulting", source: "websearch" },

  // From WebSearch (more agencies)
  { company: "DevsData LLC", website: "https://devsdata.com", phone: "", location: "Brooklyn, NY", email: "", founder: "", industry: "AI Automation Agency", source: "websearch" },
  { company: "Sellozo", website: "https://sellozo.com", phone: "", location: "Kansas City, MO", email: "", founder: "", industry: "AI Automation", source: "latenode_blog" },
  { company: "NoGood", website: "https://nogood.io", phone: "", location: "New York, NY", email: "", founder: "", industry: "Growth Marketing AI", source: "latenode_blog" },
  { company: "Botsify", website: "https://botsify.com", phone: "", location: "USA", email: "", founder: "", industry: "Chatbot Development", source: "latenode_blog" },
  { company: "ProcessMaker", website: "https://processmaker.com", phone: "", location: "Durham, NC", email: "", founder: "", industry: "AI Workflow Automation", source: "latenode_blog" },
  { company: "Voypost", website: "https://voypost.com", phone: "", location: "Europe", email: "", founder: "", industry: "AI Automation", source: "latenode_blog" },
  { company: "Automation House", website: "https://automation.house", phone: "", location: "Poland", email: "", founder: "", industry: "NoCode Automation", source: "latenode_blog" },
  { company: "Tribe AI", website: "https://tribe.ai", phone: "", location: "USA", email: "", founder: "", industry: "AI Consulting", source: "websearch" },
  { company: "Every Consulting", website: "https://every.to/consulting", phone: "", location: "USA", email: "", founder: "", industry: "AI Strategy", source: "websearch" },
  { company: "Cassidy AI", website: "https://cassidyai.com", phone: "", location: "USA", email: "", founder: "", industry: "AI Agents", source: "websearch" },
  { company: "Axe Automation Agency", website: "https://axeautomation.co", phone: "(707) 479-7131", location: "Boston, MA", email: "", founder: "", industry: "AI Automation", source: "websearch" },
  { company: "RTS Labs", website: "https://rtslabs.com", phone: "", location: "USA", email: "", founder: "", industry: "AI Consulting SMB", source: "websearch" },
  { company: "Mobio Solutions", website: "https://mobiosolutions.com", phone: "", location: "USA", email: "", founder: "Hardik Shah (Co-founder)", industry: "AI Consulting SMB", source: "websearch" },

  // From Google Maps (Apify) - real AI companies with phones
  { company: "SIERA.AI", website: "https://siera.ai/", phone: "(512) 817-0702", location: "Austin, TX 78754", email: "", founder: "", industry: "Automation company", source: "google_maps" },
  { company: "AI Genius Automations", website: "https://www.aigeniusconsulting.com/", phone: "(208) 278-6469", location: "USA", email: "", founder: "", industry: "Software company", source: "google_maps" },
  { company: "SPG America", website: "https://www.spgamerica.com/", phone: "(732) 343-7688", location: "Piscataway, NJ 08854", email: "", founder: "", industry: "AI & ML Services", source: "google_maps" },
  { company: "Richtech Robotics", website: "https://www.richtechrobotics.com/", phone: "(866) 236-3835", location: "Las Vegas, NV 89115", email: "", founder: "", industry: "Automation company", source: "google_maps" },
  { company: "AIO App Inc", website: "https://www.aioapp.com/", phone: "(408) 477-4632", location: "San Jose, CA 95120", email: "", founder: "", industry: "Software company", source: "google_maps" },
  { company: "Session AI", website: "https://www.sessionai.com/", phone: "(408) 502-7077", location: "San Jose, CA 95110", email: "", founder: "", industry: "AI Software", source: "google_maps" },
  { company: "AY Consulting Inc", website: "https://www.ayconsulting.net/", phone: "(415) 702-0216", location: "San Francisco, CA", email: "", founder: "", industry: "AI Consulting", source: "google_maps" },
  { company: "Compliance.ai", website: "https://www.compliance.ai/", phone: "(415) 735-4955", location: "San Francisco, CA 94104", email: "", founder: "", industry: "AI Software", source: "google_maps" },
  { company: "Agentic AI Corporation", website: "https://www.agentic.ai/", phone: "", location: "San Francisco, CA 94105", email: "", founder: "", industry: "AI Software", source: "google_maps" },

  // Clutch.co agencies (from WebSearch)
  { company: "Aikiaa Automation Agency", website: "https://clutch.co/profile/aikiaa-automation-agency", phone: "", location: "Mumbai, India", email: "", founder: "Akhil Chandana (CEO), Rushabh Modi (CTO)", industry: "AI RevOps Automation", source: "clutch" },
  { company: "Flowmondo", website: "https://clutch.co/profile/flowmondo", phone: "", location: "UK", email: "", founder: "", industry: "AI Automation Agency", source: "clutch" },

  // From Automation Anywhere, UiPath (major RPA players)
  { company: "Automation Anywhere", website: "https://automationanywhere.com", phone: "", location: "San Jose, CA", email: "", founder: "Mihir Shukla (CEO)", industry: "RPA", source: "websearch" },
  { company: "Accelirate", website: "https://accelirate.com", phone: "", location: "USA", email: "", founder: "", industry: "RPA Services", source: "websearch" },

  // MQLFlow - with founder
  { company: "MQLFlow", website: "https://mqlflow.com", phone: "", location: "UK", email: "", founder: "Pete Hogg (Founder)", industry: "AI Automation Agency", source: "websearch" },
];

// ─── Load Google Maps data from CSV ──────────────────────────────────────────

function loadGMapsData() {
  const files = [
    "companies_enriched_20260302_0004.csv",
    "companies_enriched_20260301_2356.csv",
  ];

  const results = [];
  const seen = new Set();

  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    const data = parse(fs.readFileSync(file, "utf-8"), { columns: true });
    for (const row of data) {
      const key = (row.company || "").toLowerCase();
      if (seen.has(key) || !row.company) continue;
      seen.add(key);
      if (row.source && row.source.includes("google_maps") && row.phone) {
        results.push({
          company: row.company,
          website: row.website || "",
          phone: row.phone || "",
          location: [row.city, row.state].filter(Boolean).join(", ") || row.address || "",
          email: "",
          founder: "",
          industry: row.industry || row.category || "",
          linkedin: row.linkedin_company || "",
          source: "google_maps",
        });
      }
    }
  }
  return results;
}

// ─── Load Cheerio scraper results ────────────────────────────────────────────

function loadCheerioData() {
  if (!fs.existsSync("CHEERIO_ENRICHED_LEADS.csv")) return [];
  const data = parse(fs.readFileSync("CHEERIO_ENRICHED_LEADS.csv", "utf-8"), { columns: true });
  return data
    .filter((r) => r.emails || (r.phones && r.phones !== r.company))
    .map((r) => ({
      company: r.company || "",
      website: r.website || "",
      phone: r.phones?.split(";")[0]?.trim() || "",
      location: r.location || "",
      email: r.emails?.split(";")[0]?.trim() || "",
      founder: "",
      industry: r.industry || "",
      linkedin: r.linkedin || "",
      source: "cheerio",
    }));
}

// ─── Deduplicate and merge ───────────────────────────────────────────────────

function normalizeDomain(url) {
  if (!url) return "";
  url = url.toLowerCase().trim().replace(/\/$/, "");
  for (const p of ["https://", "http://", "www."]) {
    if (url.startsWith(p)) url = url.slice(p.length);
  }
  return url.split("/")[0];
}

function main() {
  console.log("\n" + "=".repeat(55));
  console.log("  MASTER LEAD BUILDER - ALL SOURCES");
  console.log("=".repeat(55));

  // Load additional data
  const gmapsData = loadGMapsData();
  const cheerioData = loadCheerioData();

  console.log(`\n  Scraped companies (WebSearch+WebFetch): ${SCRAPED_COMPANIES.length}`);
  console.log(`  Google Maps companies with phone:        ${gmapsData.length}`);
  console.log(`  Cheerio scraped with contact info:        ${cheerioData.length}`);

  // Merge all sources
  const all = [...SCRAPED_COMPANIES, ...gmapsData, ...cheerioData];

  // Deduplicate by domain
  const byDomain = new Map();
  for (const c of all) {
    const domain = normalizeDomain(c.website);
    const key = domain || c.company.toLowerCase();

    if (byDomain.has(key)) {
      // Merge: keep best data from each
      const existing = byDomain.get(key);
      if (c.email && !existing.email) existing.email = c.email;
      if (c.phone && !existing.phone) existing.phone = c.phone;
      if (c.founder && !existing.founder) existing.founder = c.founder;
      if (c.linkedin && !existing.linkedin) existing.linkedin = c.linkedin;
      if (c.location && !existing.location) existing.location = c.location;
      if (c.industry && !existing.industry) existing.industry = c.industry;
      existing.source += "+" + c.source;
    } else {
      byDomain.set(key, { ...c });
    }
  }

  // Convert to array and sort
  const leads = [...byDomain.values()];

  // Sort: email+phone > email > phone > neither
  leads.sort((a, b) => {
    const scoreA = (a.email ? 2 : 0) + (a.phone ? 1 : 0) + (a.founder ? 0.5 : 0);
    const scoreB = (b.email ? 2 : 0) + (b.phone ? 1 : 0) + (b.founder ? 0.5 : 0);
    return scoreB - scoreA;
  });

  // Write CSV
  const fields = [
    "company", "website", "email", "phone", "founder",
    "industry", "location", "linkedin", "source",
  ];

  const csv = stringify(leads, { header: true, columns: fields });
  fs.writeFileSync("MASTER_AI_LEADS.csv", csv);

  // Stats
  const withEmail = leads.filter((l) => l.email).length;
  const withPhone = leads.filter((l) => l.phone).length;
  const withFounder = leads.filter((l) => l.founder).length;
  const withBoth = leads.filter((l) => l.email && l.phone).length;
  const withLinkedin = leads.filter((l) => l.linkedin).length;

  console.log(`\n  Unique companies:          ${leads.length}`);
  console.log(`  With email:                ${withEmail}`);
  console.log(`  With phone:                ${withPhone}`);
  console.log(`  With email + phone:        ${withBoth}`);
  console.log(`  With founder/CEO name:     ${withFounder}`);
  console.log(`  With LinkedIn:             ${withLinkedin}`);
  console.log(`\n  Saved to: MASTER_AI_LEADS.csv`);
  console.log("=".repeat(55));

  // Show top leads
  console.log("\n  TOP LEADS (email + phone + founder):\n");
  for (const l of leads.slice(0, 15)) {
    console.log(`  ${l.company}`);
    if (l.founder) console.log(`    Founder: ${l.founder}`);
    if (l.email) console.log(`    Email:   ${l.email}`);
    if (l.phone) console.log(`    Phone:   ${l.phone}`);
    console.log(`    Web:     ${l.website}`);
    console.log(`    Loc:     ${l.location}`);
    console.log();
  }
}

main();
