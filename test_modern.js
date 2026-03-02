const { gotScraping } = require("got-scraping");
const { parseHTML } = require("linkedom");

(async () => {
  const urls = [
    { name: "Clutch AI", url: "https://clutch.co/it-services/artificial-intelligence" },
    { name: "GoodFirms AI", url: "https://www.goodfirms.co/artificial-intelligence/companies" },
    { name: "G2 AI Agents", url: "https://www.g2.com/categories/ai-agents" },
    { name: "Futurepedia", url: "https://www.futurepedia.io/" },
    { name: "ProductHunt AI", url: "https://www.producthunt.com/topics/artificial-intelligence" },
    { name: "SaaSHub AI", url: "https://www.saashub.com/best-artificial-intelligence-software" },
    { name: "TopAI.tools", url: "https://topai.tools/" },
    { name: "SIERA AI", url: "https://siera.ai/" },
    { name: "Bitcot", url: "https://www.bitcot.com/" },
    { name: "AIO App", url: "https://www.aioapp.com/" },
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
      const bodyLen = document.body?.textContent?.length || 0;

      // Extract emails
      const bodyText = document.body?.textContent || "";
      const emails = bodyText.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];

      // Count meaningful links
      const links = document.querySelectorAll("a[href]");

      // Get headings
      const headings = [];
      document.querySelectorAll("h2, h3").forEach((h) => {
        const text = h.textContent?.trim().slice(0, 60);
        if (text && text.length > 3) headings.push(text);
      });

      console.log(`${t.name}: ${resp.statusCode} (${resp.body.length} bytes)`);
      console.log(`  Title: ${title}`);
      console.log(`  Body text: ${bodyLen} chars | Links: ${links.length} | Emails: ${emails.length}`);
      if (headings.length > 0) console.log(`  Headings: ${headings.slice(0, 3).join(" | ")}`);
      if (emails.length > 0) console.log(`  Emails found: ${emails.slice(0, 3).join(", ")}`);
      console.log();
    } catch (err) {
      console.log(`${t.name}: ERROR - ${err.message?.slice(0, 80)}`);
      console.log();
    }
  }
})();
