import { gotScraping } from "got-scraping";
import { parseHTML } from "linkedom";

const urls = [
  { name: "Clutch AI", url: "https://clutch.co/it-services/artificial-intelligence" },
  { name: "GoodFirms AI", url: "https://www.goodfirms.co/artificial-intelligence/companies" },
  { name: "G2 AI Agents", url: "https://www.g2.com/categories/ai-agents" },
  { name: "Futurepedia", url: "https://www.futurepedia.io/" },
  { name: "SaaSHub AI", url: "https://www.saashub.com/best-artificial-intelligence-software" },
  { name: "TopAI.tools", url: "https://topai.tools/" },
  { name: "SIERA AI", url: "https://siera.ai/" },
  { name: "Bitcot", url: "https://www.bitcot.com/" },
  { name: "AIO App", url: "https://www.aioapp.com/" },
  { name: "AI Genius", url: "https://www.aigeniusconsulting.com/" },
  { name: "SPG America", url: "https://www.spgamerica.com/" },
];

for (const t of urls) {
  try {
    const resp = await gotScraping({
      url: t.url,
      headerGeneratorOptions: {
        browsers: ["chrome"],
        operatingSystems: ["windows"],
        devices: ["desktop"],
      },
      timeout: { request: 15000 },
    });

    const { document } = parseHTML(resp.body);
    const title = document.querySelector("title")?.textContent?.trim().slice(0, 80) || "no title";
    const bodyText = document.body?.textContent || "";
    const bodyLen = bodyText.length;

    // Extract emails
    const emails = bodyText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];

    // Extract mailto: links
    const mailtos = [];
    document.querySelectorAll('a[href^="mailto:"]').forEach((a) => {
      mailtos.push(a.getAttribute("href").replace("mailto:", "").split("?")[0]);
    });

    // Extract tel: links
    const tels = [];
    document.querySelectorAll('a[href^="tel:"]').forEach((a) => {
      tels.push(a.getAttribute("href").replace("tel:", ""));
    });

    // Count links
    const links = document.querySelectorAll("a[href]");

    // Headings
    const headings = [];
    document.querySelectorAll("h1, h2, h3").forEach((h) => {
      const text = h.textContent?.trim().slice(0, 70);
      if (text && text.length > 3) headings.push(text);
    });

    console.log(`${t.name}: ${resp.statusCode} (${resp.body.length} bytes)`);
    console.log(`  Title: ${title}`);
    console.log(`  Body: ${bodyLen} chars | Links: ${links.length}`);
    if (headings.length > 0) console.log(`  H1-3: ${headings.slice(0, 4).join(" | ")}`);
    if (emails.length > 0) console.log(`  Emails: ${[...new Set(emails)].slice(0, 5).join(", ")}`);
    if (mailtos.length > 0) console.log(`  Mailto: ${mailtos.join(", ")}`);
    if (tels.length > 0) console.log(`  Tel: ${tels.join(", ")}`);
    console.log();
  } catch (err) {
    console.log(`${t.name}: ERROR - ${err.message?.slice(0, 100)}`);
    console.log();
  }
}
