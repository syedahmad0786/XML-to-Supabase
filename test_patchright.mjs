import { chromium } from "patchright";

const urls = [
  { name: "Clutch AI", url: "https://clutch.co/it-services/artificial-intelligence" },
  { name: "GoodFirms AI", url: "https://www.goodfirms.co/artificial-intelligence/companies" },
  { name: "G2 AI Agents", url: "https://www.g2.com/categories/ai-agents" },
  { name: "Bitcot", url: "https://www.bitcot.com/" },
  { name: "SIERA AI", url: "https://siera.ai/" },
];

const browser = await chromium.launch({ headless: true });

for (const t of urls) {
  const page = await browser.newPage();
  try {
    console.log(`\n--- ${t.name} ---`);
    await page.goto(t.url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(3000); // Let JS render

    const title = await page.title();
    console.log(`  Title: ${title.slice(0, 80)}`);

    // Extract text content length
    const bodyLen = await page.evaluate(() => document.body?.innerText?.length || 0);
    console.log(`  Body text: ${bodyLen} chars`);

    // Extract emails
    const emails = await page.evaluate(() => {
      const text = document.body?.innerText || "";
      return [...new Set((text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || []))];
    });
    if (emails.length) console.log(`  Emails: ${emails.slice(0, 5).join(", ")}`);

    // Extract phone numbers from tel: links
    const tels = await page.evaluate(() => {
      return [...document.querySelectorAll('a[href^="tel:"]')].map(a =>
        a.href.replace("tel:", "")
      );
    });
    if (tels.length) console.log(`  Phones: ${tels.slice(0, 5).join(", ")}`);

    // Count company-like headings
    const headings = await page.evaluate(() => {
      return [...document.querySelectorAll("h2, h3, h4")]
        .map(h => h.innerText?.trim())
        .filter(t => t && t.length > 2 && t.length < 80)
        .slice(0, 5);
    });
    if (headings.length) console.log(`  Headings: ${headings.join(" | ")}`);

    // Count links
    const linkCount = await page.evaluate(() => document.querySelectorAll("a[href]").length);
    console.log(`  Links: ${linkCount}`);

  } catch (err) {
    console.log(`  ERROR: ${err.message?.slice(0, 100)}`);
  } finally {
    await page.close();
  }
}

await browser.close();
console.log("\nDone.");
