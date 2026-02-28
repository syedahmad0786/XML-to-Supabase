import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/index.js";
import type { Lead, DeepResearch, PsychologicalProfile } from "../types/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("psychological-profiler");

const PROFILING_PROMPT = `You are an expert behavioral psychologist specializing in B2B sales communication.
Based on the available data about this person, create a psychological/behavioral profile
that will inform the TONE, TIMING, and APPROACH of sales outreach.

Target Person:
Name: {name}
Title: {title}
Seniority: {seniority}
Department: {department}
Years in role: {yearsInRole}
LinkedIn: {linkedInUrl}

Research Data:
{research}

Your profile must assess:

1. COMMUNICATION STYLE (DISC-inspired):
   - Analytical: Wants data, proof, ROI calculations. Formal. Skeptical of hype.
   - Driver: Wants bottom line. Short, direct messages. Respects confidence.
   - Expressive: Wants vision, excitement, social proof. Storytelling works.
   - Amiable: Wants trust, relationships, consensus. Warm, patient approach.

2. DECISION MAKING PATTERN:
   - Data-driven: Needs case studies, metrics, comparisons
   - Intuitive: Goes with gut, values vision and potential
   - Collaborative: Needs team buy-in, will loop in others
   - Decisive: Makes fast calls, doesn't like long processes

3. MOTIVATORS: What drives this person professionally?

4. RISK TOLERANCE: How willing are they to try new solutions?

5. RESPONSE PATTERNS: When and how do they prefer to communicate?

Return a JSON object:
{
  "communicationStyle": "analytical" | "driver" | "expressive" | "amiable",
  "decisionMaking": "data_driven" | "intuitive" | "collaborative" | "decisive",
  "motivators": ["list of key professional motivators"],
  "riskTolerance": "low" | "medium" | "high",
  "preferredContactMethod": "email" | "linkedin" | "phone",
  "personalityTraits": ["trait1", "trait2", "trait3"],
  "responsePatterns": {
    "bestTimeToContact": "e.g., Tuesday-Thursday mornings",
    "preferredMessageLength": "short" | "medium" | "detailed",
    "formality": "formal" | "semi_formal" | "casual"
  },
  "recommendedApproach": "A 2-3 sentence strategy for how to approach this person"
}

Base your analysis on EVIDENCE from the data, not assumptions.
Return ONLY the JSON object.`;

export class PsychologicalProfiler {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: config.llm.anthropicApiKey });
  }

  /**
   * Build a cognitive/behavioral profile of the lead to inform outreach tone.
   * This runs after deep research, using the gathered intel to infer personality.
   */
  async profileLead(lead: Lead, research: DeepResearch): Promise<PsychologicalProfile> {
    logger.info(`Profiling ${lead.fullName}`);

    const prompt = PROFILING_PROMPT
      .replace("{name}", lead.fullName)
      .replace("{title}", lead.title)
      .replace("{seniority}", lead.seniority)
      .replace("{department}", lead.department)
      .replace("{yearsInRole}", String(lead.yearsInRole ?? "unknown"))
      .replace("{linkedInUrl}", lead.linkedInUrl ?? "not available")
      .replace("{research}", JSON.stringify(research, null, 2));

    const response = await this.client.messages.create({
      model: config.llm.primaryModel,
      max_tokens: 2048,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from profiling");
    }

    const profile = JSON.parse(content.text) as Omit<PsychologicalProfile, "profiledAt">;

    logger.info(`Profile complete for ${lead.fullName}`, {
      style: profile.communicationStyle,
      decisionMaking: profile.decisionMaking,
      approach: profile.recommendedApproach,
    });

    return { ...profile, profiledAt: new Date() };
  }

  /**
   * Generate tone guidelines from the profile for the content generator.
   * These are passed as system instructions to the message-writing LLM.
   */
  generateToneGuidelines(profile: PsychologicalProfile): string {
    const guidelines: string[] = [];

    // Communication style
    switch (profile.communicationStyle) {
      case "analytical":
        guidelines.push(
          "Use data points and specific metrics. Lead with ROI or efficiency gains.",
          "Be precise — avoid vague claims. Include evidence or reference case studies.",
          "Keep tone professional and measured. Don't use exclamation marks.",
          "Structure information logically: problem → data → solution → proof."
        );
        break;
      case "driver":
        guidelines.push(
          "Get to the point immediately. First sentence must deliver value.",
          "Be direct and confident. No hedging language ('maybe', 'possibly').",
          "Focus on outcomes and results, not process or features.",
          "Keep messages short — under 100 words for initial outreach."
        );
        break;
      case "expressive":
        guidelines.push(
          "Open with a compelling vision or story. Paint the picture of what's possible.",
          "Use social proof — name-drop relevant companies or leaders.",
          "Show enthusiasm (but authentic, not salesy). It's OK to be conversational.",
          "Connect emotionally before presenting logic."
        );
        break;
      case "amiable":
        guidelines.push(
          "Lead with genuine rapport — reference a shared connection or interest.",
          "Be warm and personal. Use their first name. Show you did your homework.",
          "Don't push for a quick decision. Offer to be helpful with no pressure.",
          "Mention how others on their team would benefit too."
        );
        break;
    }

    // Decision making
    switch (profile.decisionMaking) {
      case "data_driven":
        guidelines.push("Include a specific metric or data point in every message.");
        break;
      case "intuitive":
        guidelines.push("Focus on the vision and strategic alignment.");
        break;
      case "collaborative":
        guidelines.push("Suggest involving their team. Offer group demos.");
        break;
      case "decisive":
        guidelines.push("Present a clear next step. Make it easy to say yes.");
        break;
    }

    // Formality
    switch (profile.responsePatterns.formality) {
      case "formal":
        guidelines.push("Use Mr./Ms. or full name. Professional salutations.");
        break;
      case "semi_formal":
        guidelines.push("First name is fine. Professional but approachable.");
        break;
      case "casual":
        guidelines.push("Keep it casual and conversational. No corporate speak.");
        break;
    }

    // Message length
    switch (profile.responsePatterns.preferredMessageLength) {
      case "short":
        guidelines.push("Keep messages under 75 words. Every word must earn its place.");
        break;
      case "medium":
        guidelines.push("Target 100-150 words. Enough detail without overwhelming.");
        break;
      case "detailed":
        guidelines.push(
          "Provide thorough context — 150-250 words is fine. They want substance."
        );
        break;
    }

    return guidelines.join("\n- ");
  }
}
