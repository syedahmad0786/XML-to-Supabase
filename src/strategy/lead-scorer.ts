import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/index.js";
import type { Lead, ICP, DeepResearch } from "../types/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("lead-scorer");

const SCORING_PROMPT = `You are an expert B2B lead qualification analyst. Score this lead from 1-10 based on how
well they match the Ideal Customer Profile and their likelihood to convert.

ICP Criteria:
{icp}

Lead Data:
{lead}

{researchSection}

Score on these dimensions (each 1-10):
1. ICP_FIT: How well does the company match our ICP demographics and firmographics?
2. TIMING: Are there signals suggesting urgency or readiness to buy right now?
3. AUTHORITY: Is this person the actual decision-maker or strong influencer?
4. NEED: How severe is the pain point we solve for them specifically?
5. BUDGET: Based on company size/revenue/funding, can they afford our solution?

Return a JSON object:
{
  "scores": {
    "icpFit": number,
    "timing": number,
    "authority": number,
    "need": number,
    "budget": number
  },
  "overall": number (weighted average: timing 25%, need 25%, icpFit 20%, authority 15%, budget 15%),
  "reasoning": "One-paragraph explanation",
  "topSignals": ["signal1", "signal2", "signal3"],
  "risks": ["risk1", "risk2"],
  "recommendedApproach": "Brief strategy for this lead"
}

Return ONLY the JSON object.`;

interface ScoreResult {
  scores: {
    icpFit: number;
    timing: number;
    authority: number;
    need: number;
    budget: number;
  };
  overall: number;
  reasoning: string;
  topSignals: string[];
  risks: string[];
  recommendedApproach: string;
}

export class LeadScorer {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: config.llm.anthropicApiKey });
  }

  /**
   * Score a lead against the ICP. Uses the fast model for cost efficiency
   * since scoring happens for every lead.
   */
  async scoreLead(lead: Lead, icp: ICP): Promise<ScoreResult> {
    const researchSection = lead.research
      ? `Deep Research Available:\n${JSON.stringify(lead.research, null, 2)}`
      : "No deep research available yet — score based on available data.";

    const prompt = SCORING_PROMPT
      .replace("{icp}", JSON.stringify(icp, null, 2))
      .replace("{lead}", this.summarizeLead(lead))
      .replace("{researchSection}", researchSection);

    const response = await this.client.messages.create({
      model: config.llm.fastModel,
      max_tokens: 1024,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from lead scoring");
    }

    const result: ScoreResult = JSON.parse(content.text);
    logger.info(`Lead ${lead.fullName} scored ${result.overall}/10`, {
      leadId: lead.id,
      scores: result.scores,
    });

    return result;
  }

  /**
   * Batch score multiple leads — sorts by score descending.
   * Only leads scoring at or above the threshold proceed to deep research.
   */
  async batchScore(
    leads: Lead[],
    icp: ICP
  ): Promise<Array<{ lead: Lead; score: ScoreResult }>> {
    const results = await Promise.allSettled(
      leads.map(async (lead) => {
        const score = await this.scoreLead(lead, icp);
        return { lead, score };
      })
    );

    const scored: Array<{ lead: Lead; score: ScoreResult }> = [];
    for (const result of results) {
      if (result.status === "fulfilled") {
        scored.push(result.value);
      }
    }

    scored.sort((a, b) => b.score.overall - a.score.overall);

    const threshold = config.agent.leadScoreThreshold;
    const qualified = scored.filter((s) => s.score.overall >= threshold);
    const disqualified = scored.filter((s) => s.score.overall < threshold);

    logger.info(
      `Batch scoring complete: ${qualified.length} qualified (>=${threshold}), ` +
        `${disqualified.length} below threshold`
    );

    return scored;
  }

  /**
   * Re-score a lead after deep research is available.
   * This gives a more accurate score that determines whether
   * we spend high-cost API tokens on personalized outreach.
   */
  async rescoreAfterResearch(
    lead: Lead,
    icp: ICP,
    research: DeepResearch
  ): Promise<ScoreResult> {
    const enrichedLead = { ...lead, research };
    return this.scoreLead(enrichedLead, icp);
  }

  /**
   * Determine the resource allocation tier based on score.
   * - Tier 1 (8-10): Full deep research + personalized multi-channel
   * - Tier 2 (6-7): Light research + templated outreach
   * - Tier 3 (below 6): Skip or minimal outreach
   */
  getResourceTier(score: number): "tier1" | "tier2" | "tier3" {
    if (score >= 8) return "tier1";
    if (score >= 6) return "tier2";
    return "tier3";
  }

  private summarizeLead(lead: Lead): string {
    return JSON.stringify(
      {
        name: lead.fullName,
        title: lead.title,
        seniority: lead.seniority,
        company: lead.company.name,
        industry: lead.company.industry,
        companySize: lead.company.size,
        revenue: lead.company.revenue,
        techStack: lead.company.techStack,
        recentNews: lead.company.recentNews,
        linkedIn: lead.linkedInUrl,
      },
      null,
      2
    );
  }
}
