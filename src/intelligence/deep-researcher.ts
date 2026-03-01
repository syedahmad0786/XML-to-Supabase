import Anthropic from "@anthropic-ai/sdk";
import axios from "axios";
import * as cheerio from "cheerio";
import { config } from "../config/index.js";
import type { Lead, DeepResearch, NewsItem } from "../types/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("deep-researcher");

const RESEARCH_SYNTHESIS_PROMPT = `You are a senior sales intelligence analyst. Synthesize the following raw data
about a company and decision-maker into actionable sales intelligence.

Target Lead: {leadName}, {leadTitle} at {companyName}
Industry: {industry}
Company Size: {companySize} employees

Raw Data Collected:
{rawData}

Produce a comprehensive research brief in this JSON format:
{
  "companyAnalysis": {
    "recentNews": [{"title": "string", "url": "string", "date": "string", "summary": "string", "relevanceScore": 0-10}],
    "financialHealth": "assessment of financial health based on available data",
    "growthTrajectory": "growing/stable/declining with evidence",
    "strategicPriorities": ["what the company is focused on right now"],
    "challenges": ["specific challenges they face"]
  },
  "personAnalysis": {
    "recentActivity": ["recent LinkedIn posts, talks, publications"],
    "publishedContent": ["articles, podcasts, conference talks"],
    "sharedInterests": ["interests relevant to relationship building"],
    "careerTrajectory": "their career path and what it suggests about priorities",
    "decisionMakingStyle": "data-driven/intuitive/collaborative based on evidence"
  },
  "painPointMapping": {
    "identified": ["specific pain points"],
    "severity": {"painPoint": 1-10},
    "ourSolution": {"painPoint": "how we address this specifically"}
  },
  "competitiveIntel": {
    "currentVendors": ["known current solutions they use"],
    "dissatisfactionSignals": ["any signals of unhappiness with current solutions"],
    "switchingCost": "low/medium/high"
  }
}

Focus on ACTIONABLE intelligence — things a salesperson can directly reference in outreach.
Return ONLY the JSON object.`;

export class DeepResearcher {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: config.llm.anthropicApiKey });
  }

  /**
   * Perform comprehensive research on a lead and their company.
   * This is the expensive operation — only run for leads scoring 8+.
   */
  async research(lead: Lead): Promise<DeepResearch> {
    logger.info(`Starting deep research on ${lead.fullName} at ${lead.company.name}`);

    // Gather raw data from multiple sources in parallel
    const [companyNews, companyProfile, personActivity] = await Promise.allSettled([
      this.fetchCompanyNews(lead.company.name, lead.company.domain),
      this.fetchCompanyProfile(lead.company.domain),
      this.fetchPersonActivity(lead),
    ]);

    const rawData = this.aggregateRawData({
      news: companyNews.status === "fulfilled" ? companyNews.value : [],
      profile: companyProfile.status === "fulfilled" ? companyProfile.value : null,
      activity: personActivity.status === "fulfilled" ? personActivity.value : [],
    });

    // Synthesize raw data using the research-grade LLM
    const prompt = RESEARCH_SYNTHESIS_PROMPT
      .replace("{leadName}", lead.fullName)
      .replace("{leadTitle}", lead.title)
      .replace("{companyName}", lead.company.name)
      .replace("{industry}", lead.company.industry)
      .replace("{companySize}", String(lead.company.size))
      .replace("{rawData}", rawData);

    const response = await this.client.messages.create({
      model: config.llm.researchModel,
      max_tokens: 8192,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from deep research");
    }

    const research = JSON.parse(content.text) as Omit<DeepResearch, "researchedAt">;

    logger.info(`Deep research complete for ${lead.fullName}`, {
      newsFound: research.companyAnalysis.recentNews.length,
      painPoints: research.painPointMapping.identified.length,
    });

    return { ...research, researchedAt: new Date() };
  }

  /**
   * Light research for Tier 2 leads (score 6-7).
   * Uses the fast model and fewer data sources.
   */
  async lightResearch(lead: Lead): Promise<DeepResearch> {
    logger.info(`Starting light research on ${lead.fullName} at ${lead.company.name}`);

    const news = await this.fetchCompanyNews(lead.company.name, lead.company.domain)
      .catch(() => []);

    const prompt = `Briefly analyze this lead for sales outreach:
Name: ${lead.fullName}, ${lead.title} at ${lead.company.name}
Industry: ${lead.company.industry}, ${lead.company.size} employees
Tech stack: ${lead.company.techStack.join(", ")}
Recent news: ${JSON.stringify(news.slice(0, 3))}

Return a concise JSON research brief with companyAnalysis, personAnalysis,
painPointMapping, and competitiveIntel fields. Keep it brief but actionable.`;

    const response = await this.client.messages.create({
      model: config.llm.fastModel,
      max_tokens: 2048,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type");
    }

    return { ...JSON.parse(content.text), researchedAt: new Date() };
  }

  private async fetchCompanyNews(
    companyName: string,
    domain: string
  ): Promise<NewsItem[]> {
    try {
      // Use a news API or web scraping to find recent articles
      const query = encodeURIComponent(`"${companyName}" site:businesswire.com OR site:prnewswire.com OR site:techcrunch.com`);
      const response = await axios.get(
        `https://news.google.com/rss/search?q=${query}&hl=en-US&gl=US&ceid=US:en`,
        { timeout: 10000 }
      );

      const $ = cheerio.load(response.data, { xmlMode: true });
      const items: NewsItem[] = [];

      $("item").each((i, el) => {
        if (i >= 10) return;
        items.push({
          title: $(el).find("title").text(),
          url: $(el).find("link").text(),
          date: $(el).find("pubDate").text(),
          summary: $(el).find("description").text().slice(0, 300),
          relevanceScore: 0,
        });
      });

      return items;
    } catch (error) {
      logger.warn(`Failed to fetch news for ${companyName}`, { error });
      return [];
    }
  }

  private async fetchCompanyProfile(domain: string): Promise<Record<string, unknown> | null> {
    try {
      // Attempt to scrape company about/careers page for tech stack and priorities
      const response = await axios.get(`https://${domain}`, {
        timeout: 10000,
        headers: { "User-Agent": "Mozilla/5.0 (compatible; SalesResearchBot/1.0)" },
      });

      const $ = cheerio.load(response.data);
      return {
        title: $("title").text(),
        description: $('meta[name="description"]').attr("content"),
        ogDescription: $('meta[property="og:description"]').attr("content"),
        bodyText: $("body").text().slice(0, 5000),
      };
    } catch {
      return null;
    }
  }

  /**
   * Fetch a person's recent public activity across multiple sources:
   * - Google News for their published articles, talks, and media mentions
   * - Company about/team pages for biography and role mentions
   */
  private async fetchPersonActivity(lead: Lead): Promise<string[]> {
    const activities: string[] = [];

    if (lead.linkedInUrl) {
      activities.push(`LinkedIn profile: ${lead.linkedInUrl}`);
    }

    // Search Google News for the person's public activity and mentions
    const queries = [
      `"${lead.fullName}" "${lead.company.name}"`,
      `"${lead.fullName}" ${lead.company.industry} conference OR podcast OR article`,
    ];

    for (const query of queries) {
      try {
        const encoded = encodeURIComponent(query);
        const response = await axios.get(
          `https://news.google.com/rss/search?q=${encoded}&hl=en-US&gl=US&ceid=US:en`,
          { timeout: 8000 }
        );

        const $ = cheerio.load(response.data, { xmlMode: true });
        $("item").each((i, el) => {
          if (i >= 5) return;
          const title = $(el).find("title").text();
          const date = $(el).find("pubDate").text();
          if (title) {
            activities.push(`[${date}] ${title}`);
          }
        });
      } catch {
        logger.warn(`Person activity search failed for query: ${query}`);
      }
    }

    // Try to fetch company about/team page for biographical mentions
    if (lead.company.domain) {
      try {
        const aboutResponse = await axios.get(
          `https://${lead.company.domain}/about`,
          {
            timeout: 8000,
            headers: { "User-Agent": "Mozilla/5.0 (compatible; SalesResearchBot/1.0)" },
            validateStatus: (status) => status < 500,
          }
        );

        if (aboutResponse.status === 200) {
          const $ = cheerio.load(aboutResponse.data);
          const pageText = $("body").text().slice(0, 3000);
          const nameRegex = new RegExp(`[^.]*${lead.lastName}[^.]*\\.`, "gi");
          const mentions = pageText.match(nameRegex);
          if (mentions) {
            activities.push(
              ...mentions.slice(0, 3).map((m) => `Company page mention: ${m.trim()}`)
            );
          }
        }
      } catch {
        // About page may not exist — skip silently
      }
    }

    return activities;
  }

  private aggregateRawData(data: {
    news: NewsItem[];
    profile: Record<string, unknown> | null;
    activity: string[];
  }): string {
    const parts: string[] = [];

    if (data.news.length > 0) {
      parts.push("=== RECENT NEWS ===");
      for (const item of data.news) {
        parts.push(`- ${item.title} (${item.date}): ${item.summary}`);
      }
    }

    if (data.profile) {
      parts.push("\n=== COMPANY WEBSITE ===");
      parts.push(`Title: ${data.profile.title}`);
      parts.push(`Description: ${data.profile.description}`);
      const bodyText = data.profile.bodyText as string;
      if (bodyText) {
        parts.push(`Content excerpt: ${bodyText.slice(0, 2000)}`);
      }
    }

    if (data.activity.length > 0) {
      parts.push("\n=== PERSON ACTIVITY ===");
      for (const a of data.activity) {
        parts.push(`- ${a}`);
      }
    }

    return parts.join("\n") || "No raw data could be collected.";
  }
}
