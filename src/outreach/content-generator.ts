import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/index.js";
import type {
  Lead,
  BusinessDNA,
  PsychologicalProfile,
  DeepResearch,
  Channel,
  SequenceStep,
  ConversationMessage,
} from "../types/index.js";
import { PsychologicalProfiler } from "../intelligence/psychological-profiler.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("content-generator");

const MESSAGE_GENERATION_PROMPT = `You are a world-class B2B sales copywriter who writes messages that sound like
they come from a knowledgeable peer, NOT a salesperson. Your messages must be indistinguishable
from a real human expert reaching out about a genuine opportunity.

=== CONTEXT ===
Our Company: {ourCompany}
Our Value Prop: {valueProposition}
Our Brand Voice: {brandVoice}

=== TARGET ===
Name: {leadName}
Title: {leadTitle}
Company: {companyName}
Industry: {industry}

=== RESEARCH INTEL ===
{researchIntel}

=== PSYCHOLOGICAL PROFILE ===
Communication style: {commStyle}
Tone guidelines:
- {toneGuidelines}

=== MESSAGE PARAMETERS ===
Channel: {channel}
Step in sequence: {stepNumber} of {totalSteps}
Step type: {stepType}
Previous messages in this sequence: {previousMessages}

=== ANTI-SPAM RULES ===
1. NEVER start with "I hope this finds you well" or any variant
2. NEVER use "I came across your profile" — everyone says that
3. NEVER start with "Hi {firstName}," as the very first line if this is LinkedIn — it's implied
4. DO NOT use buzzwords: "synergy", "leverage", "game-changer", "revolutionary"
5. DO NOT mention AI, automation, or that this message was generated
6. DO reference specific, verifiable details about their company or role
7. DO sound like you spent 10 minutes researching them (because the AI actually did)
8. DO ask a genuine question — not a rhetorical sales pitch disguised as a question
9. If this is a follow-up, DO NOT repeat information from previous messages
10. Keep the call-to-action low-commitment (no "let me schedule a demo" on first touch)

=== FORMAT RULES ===
{formatRules}

Generate the message now. Return ONLY the message text, no JSON wrapper, no explanations.`;

const FORMAT_RULES: Record<Channel, string> = {
  linkedin: `- Max 300 characters for connection request note
- For InMail/messages: 3-5 short sentences max
- No subject line needed for messages
- Casual but professional tone
- No links in connection requests`,

  email: `- Subject line: 5-8 words, NO CAPS, no clickbait, personalized
- Body: 3-6 short paragraphs
- Include one clear call-to-action
- Sign off with first name only
- Format: Subject: [subject]\\n\\n[body]`,

  instagram: `- Max 150 words for DMs
- Conversational and casual
- Reference something specific from their public profile/posts
- No corporate language
- Keep it brief — this is a social platform`,
};

export class ContentGenerator {
  private client: Anthropic;
  private profiler: PsychologicalProfiler;

  constructor() {
    this.client = new Anthropic({ apiKey: config.llm.anthropicApiKey });
    this.profiler = new PsychologicalProfiler();
  }

  /**
   * Generate a personalized outreach message for a specific step in the sequence.
   * Takes into account the lead's psychological profile, deep research,
   * and all previous messages to avoid repetition.
   */
  async generateMessage(params: {
    lead: Lead;
    businessDNA: BusinessDNA;
    channel: Channel;
    stepNumber: number;
    totalSteps: number;
    stepType: SequenceStep["type"];
    previousMessages: ConversationMessage[];
  }): Promise<string> {
    const { lead, businessDNA, channel, stepNumber, totalSteps, stepType, previousMessages } =
      params;

    const profile = lead.profile;
    const research = lead.research;

    const toneGuidelines = profile
      ? this.profiler.generateToneGuidelines(profile)
      : "Professional but friendly. Consultative tone.";

    const researchIntel = research
      ? this.formatResearchIntel(research)
      : "Limited research available. Use company/role info only.";

    const prevMsgSummary =
      previousMessages.length > 0
        ? previousMessages
            .map(
              (m) =>
                `[Step ${m.id}, ${m.channel}]: ${m.content.slice(0, 200)}${m.content.length > 200 ? "..." : ""}`
            )
            .join("\n")
        : "This is the first outreach.";

    const prompt = MESSAGE_GENERATION_PROMPT
      .replace("{ourCompany}", businessDNA.companyName)
      .replace("{valueProposition}", businessDNA.valueProposition)
      .replace("{brandVoice}", JSON.stringify(businessDNA.brandVoice))
      .replace("{leadName}", lead.fullName)
      .replace("{leadTitle}", lead.title)
      .replace("{companyName}", lead.company.name)
      .replace("{industry}", lead.company.industry)
      .replace("{researchIntel}", researchIntel)
      .replace("{commStyle}", profile?.communicationStyle ?? "unknown")
      .replace("{toneGuidelines}", toneGuidelines)
      .replace("{channel}", channel)
      .replace("{stepNumber}", String(stepNumber))
      .replace("{totalSteps}", String(totalSteps))
      .replace("{stepType}", stepType)
      .replace("{previousMessages}", prevMsgSummary)
      .replace("{formatRules}", FORMAT_RULES[channel])
      .replace("{firstName}", lead.firstName);

    const response = await this.client.messages.create({
      model: config.llm.primaryModel,
      max_tokens: 1024,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from content generation");
    }

    const message = content.text.trim();

    logger.info(`Generated ${channel} message for ${lead.fullName}`, {
      stepNumber,
      stepType,
      charCount: message.length,
    });

    return message;
  }

  /**
   * Generate a reply to an inbound message, using conversation history
   * and knowledge base context for objection handling.
   */
  async generateReply(params: {
    lead: Lead;
    businessDNA: BusinessDNA;
    inboundMessage: string;
    conversationHistory: ConversationMessage[];
    knowledgeContext?: string;
  }): Promise<string> {
    const { lead, businessDNA, inboundMessage, conversationHistory, knowledgeContext } =
      params;

    const historyStr = conversationHistory
      .slice(-10)
      .map((m) => `[${m.direction === "outbound" ? "Us" : "Lead"}]: ${m.content}`)
      .join("\n\n");

    const prompt = `You are responding as a sales representative for ${businessDNA.companyName}.

Conversation so far:
${historyStr}

Lead's latest message:
"${inboundMessage}"

${knowledgeContext ? `Relevant knowledge base context for handling this:\n${knowledgeContext}\n` : ""}

Brand voice: ${JSON.stringify(businessDNA.brandVoice)}
Lead's communication style: ${lead.profile?.communicationStyle ?? "unknown"}

Rules:
- Address their specific point directly — don't dodge
- If they have a technical objection, use the knowledge base context to answer precisely
- If they're interested, gently steer toward booking a call
- If they asked a question, answer it first, THEN advance the conversation
- Match their energy and tone
- Keep it concise — this is a real conversation, not a pitch

Reply as the salesperson. Return ONLY the reply text.`;

    const response = await this.client.messages.create({
      model: config.llm.primaryModel,
      max_tokens: 1024,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type");
    }

    return content.text.trim();
  }

  /**
   * Generate A/B test variants of a message.
   */
  async generateVariants(
    params: Parameters<ContentGenerator["generateMessage"]>[0],
    count = 2
  ): Promise<string[]> {
    const variants: string[] = [];
    for (let i = 0; i < count; i++) {
      const variant = await this.generateMessage(params);
      variants.push(variant);
    }
    return variants;
  }

  private formatResearchIntel(research: DeepResearch): string {
    const parts: string[] = [];

    if (research.companyAnalysis.recentNews.length > 0) {
      const topNews = research.companyAnalysis.recentNews
        .sort((a, b) => b.relevanceScore - a.relevanceScore)
        .slice(0, 3);
      parts.push(
        `Recent news: ${topNews.map((n) => n.title).join("; ")}`
      );
    }

    if (research.companyAnalysis.strategicPriorities.length > 0) {
      parts.push(
        `Strategic priorities: ${research.companyAnalysis.strategicPriorities.join(", ")}`
      );
    }

    if (research.painPointMapping.identified.length > 0) {
      const topPain = research.painPointMapping.identified.slice(0, 3);
      parts.push(`Key pain points: ${topPain.join(", ")}`);
    }

    if (research.personAnalysis.recentActivity.length > 0) {
      parts.push(
        `Person's recent activity: ${research.personAnalysis.recentActivity.slice(0, 3).join("; ")}`
      );
    }

    if (research.personAnalysis.sharedInterests.length > 0) {
      parts.push(
        `Shared interests: ${research.personAnalysis.sharedInterests.join(", ")}`
      );
    }

    parts.push(
      `Growth trajectory: ${research.companyAnalysis.growthTrajectory}`,
      `Decision-making style: ${research.personAnalysis.decisionMakingStyle}`
    );

    return parts.join("\n");
  }
}
