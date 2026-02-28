import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/index.js";
import type { BusinessDNA, ICP, CaseStudy } from "../types/index.js";
import { v4 as uuid } from "uuid";

const ICP_ANALYSIS_PROMPT = `You are an expert B2B sales strategist. Analyze the following business DNA and generate
a detailed Ideal Customer Profile (ICP) that will yield the highest LTV customers.

Business DNA:
{businessDNA}

Past Success Patterns:
{caseStudies}

Your analysis must:
1. Identify the common thread across highest-LTV past clients (industry, size, pain point, timing)
2. Determine the "buying trigger" — what event or condition makes a company suddenly need this solution
3. Map the decision-maker persona — who signs the check, and who influences the decision
4. Define disqualifiers — characteristics that signal a lead will waste time
5. Estimate the LTV range for this ICP

Return a structured JSON object matching this schema:
{
  "demographics": {
    "industries": ["string"],
    "companySizeRange": [minEmployees, maxEmployees],
    "revenueRange": [minRevenue, maxRevenue],
    "geographies": ["string"],
    "fundingStage": ["string"]
  },
  "firmographics": {
    "techStack": ["technologies they likely use"],
    "growthSignals": ["signals indicating they're ready to buy"],
    "painPoints": ["problems they face that we solve"],
    "buyingTriggers": ["events that create urgency"]
  },
  "decisionMaker": {
    "titles": ["VP of Engineering", "CTO", etc.],
    "departments": ["Engineering", "Product", etc.],
    "seniorityLevels": ["C-Level", "VP", etc.],
    "responsibilities": ["what they own that relates to our solution"]
  },
  "qualifiers": {
    "mustHave": ["non-negotiable criteria"],
    "niceToHave": ["bonus criteria"],
    "disqualifiers": ["immediate disqualifiers"]
  },
  "estimatedLTV": number
}

Return ONLY the JSON object, no other text.`;

export class ICPAnalyzer {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: config.llm.anthropicApiKey });
  }

  async analyzeBusinessDNA(businessDNA: BusinessDNA): Promise<ICP[]> {
    const caseStudySummary = this.summarizeCaseStudies(businessDNA.pastSuccesses);

    const prompt = ICP_ANALYSIS_PROMPT
      .replace("{businessDNA}", JSON.stringify(businessDNA, null, 2))
      .replace("{caseStudies}", caseStudySummary);

    const response = await this.client.messages.create({
      model: config.llm.researchModel,
      max_tokens: 4096,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from ICP analysis");
    }

    const parsed = JSON.parse(content.text);

    // Support both single ICP and array of ICPs
    const icpDataArray = Array.isArray(parsed) ? parsed : [parsed];

    return icpDataArray.map((icpData: Omit<ICP, "id">) => ({
      id: uuid(),
      ...icpData,
    }));
  }

  async refineICP(existingICP: ICP, feedback: string): Promise<ICP> {
    const prompt = `You previously generated this ICP:
${JSON.stringify(existingICP, null, 2)}

The user provided this feedback:
${feedback}

Generate an updated ICP incorporating this feedback. Return ONLY the JSON object.`;

    const response = await this.client.messages.create({
      model: config.llm.primaryModel,
      max_tokens: 4096,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from ICP refinement");
    }

    return { id: existingICP.id, ...JSON.parse(content.text) };
  }

  /**
   * Cluster past successes by industry/size/pain to find hidden ICP segments.
   * Uses the LLM to discover patterns humans might miss.
   */
  async discoverHiddenSegments(businessDNA: BusinessDNA): Promise<ICP[]> {
    const prompt = `Analyze these past client successes and identify DISTINCT customer segments
that share non-obvious commonalities. Look for patterns in timing, company stage,
tech stack adoption, or market conditions — not just industry.

Past clients:
${JSON.stringify(businessDNA.pastSuccesses, null, 2)}

Business context:
- Industry: ${businessDNA.industry}
- Value prop: ${businessDNA.valueProposition}
- Avg deal size: $${businessDNA.averageDealSize}

Return an array of 2-3 distinct ICP segments as JSON. Each segment should include
a "segmentName" field explaining why this cluster exists. Return ONLY the JSON array.`;

    const response = await this.client.messages.create({
      model: config.llm.researchModel,
      max_tokens: 8192,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type");
    }

    const segments = JSON.parse(content.text);
    return segments.map((seg: Omit<ICP, "id">) => ({
      id: uuid(),
      ...seg,
    }));
  }

  private summarizeCaseStudies(studies: CaseStudy[]): string {
    if (studies.length === 0) return "No past case studies available.";

    return studies
      .sort((a, b) => b.ltv - a.ltv)
      .map(
        (s, i) =>
          `${i + 1}. ${s.client} (${s.industry}) — Problem: ${s.problem} → Result: ${s.result} | LTV: $${s.ltv.toLocaleString()}`
      )
      .join("\n");
  }
}
