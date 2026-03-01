import { config } from "../config/index.js";
import type {
  Lead,
  BusinessDNA,
  Channel,
  SequenceState,
  SequenceStep,
  ConversationMessage,
  SentimentResult,
} from "../types/index.js";
import { ContentGenerator } from "./content-generator.js";
import { LinkedInChannel } from "./channels/linkedin.js";
import { EmailChannel } from "./channels/email.js";
import { InstagramChannel } from "./channels/instagram.js";
import { SentimentAnalyzer } from "../intelligence/sentiment-analyzer.js";
import { createLogger } from "../utils/logger.js";
import { v4 as uuid } from "uuid";

const logger = createLogger("sequence-orchestrator");

/**
 * The default multi-channel sequence template.
 * Designed as a 14-day coordinated campaign across LinkedIn, Email, and Instagram.
 *
 * Day 0:  LinkedIn connection request (warm touch, low commitment)
 * Day 1:  Email #1 (primary value proposition)
 * Day 3:  LinkedIn follow-up message (if connected)
 * Day 5:  Email #2 (case study / social proof)
 * Day 7:  Instagram DM (casual, different angle)
 * Day 10: Email #3 (address likely objection)
 * Day 14: Breakup email (create urgency, graceful exit)
 */
const DEFAULT_SEQUENCE: Array<{
  channel: Channel;
  type: SequenceStep["type"];
  delayDays: number;
}> = [
  { channel: "linkedin", type: "connection_request", delayDays: 0 },
  { channel: "email", type: "email", delayDays: 1 },
  { channel: "linkedin", type: "follow_up", delayDays: 3 },
  { channel: "email", type: "follow_up", delayDays: 5 },
  { channel: "instagram", type: "dm", delayDays: 7 },
  { channel: "email", type: "follow_up", delayDays: 10 },
  { channel: "email", type: "breakup", delayDays: 14 },
];

export class SequenceOrchestrator {
  private contentGenerator: ContentGenerator;
  private linkedIn: LinkedInChannel;
  private email: EmailChannel;
  private instagram: InstagramChannel;
  private sentimentAnalyzer: SentimentAnalyzer;

  constructor() {
    this.contentGenerator = new ContentGenerator();
    this.linkedIn = new LinkedInChannel();
    this.email = new EmailChannel();
    this.instagram = new InstagramChannel();
    this.sentimentAnalyzer = new SentimentAnalyzer();
  }

  /**
   * Initialize a new outreach sequence for a lead.
   * Generates personalized content for all steps upfront.
   */
  async initializeSequence(
    lead: Lead,
    businessDNA: BusinessDNA
  ): Promise<SequenceState> {
    logger.info(`Initializing sequence for ${lead.fullName}`);

    const template = this.selectSequenceTemplate(lead);
    const steps: SequenceStep[] = [];

    for (let i = 0; i < template.length; i++) {
      const stepTemplate = template[i];

      // Skip channels the lead doesn't have contact info for
      if (!this.hasChannelInfo(lead, stepTemplate.channel)) {
        logger.info(
          `Skipping ${stepTemplate.channel} step — no contact info`,
          { leadId: lead.id }
        );
        continue;
      }

      const previousMessages: ConversationMessage[] = steps
        .filter((s) => s.content)
        .map((s) => ({
          id: String(s.stepNumber),
          channel: s.channel,
          direction: "outbound" as const,
          content: s.content,
          timestamp: new Date(),
        }));

      const content = await this.contentGenerator.generateMessage({
        lead,
        businessDNA,
        channel: stepTemplate.channel,
        stepNumber: i + 1,
        totalSteps: template.length,
        stepType: stepTemplate.type,
        previousMessages,
      });

      steps.push({
        stepNumber: steps.length + 1,
        channel: stepTemplate.channel,
        type: stepTemplate.type,
        content,
        status: "pending",
        delayDays: stepTemplate.delayDays,
      });
    }

    const state: SequenceState = {
      currentStep: 0,
      totalSteps: steps.length,
      channel: steps[0]?.channel ?? "email",
      startedAt: new Date(),
      steps,
    };

    logger.info(`Sequence initialized with ${steps.length} steps for ${lead.fullName}`);
    return state;
  }

  /**
   * Execute the next pending step in the sequence.
   * Returns the updated lead with new conversation history.
   */
  async executeNextStep(
    lead: Lead,
    businessDNA: BusinessDNA
  ): Promise<{ lead: Lead; completed: boolean }> {
    const state = lead.sequenceState;
    if (!state) {
      throw new Error(`No sequence initialized for lead ${lead.id}`);
    }

    const nextStep = state.steps.find((s) => s.status === "pending");
    if (!nextStep) {
      logger.info(`Sequence complete for ${lead.fullName}`);
      return { lead, completed: true };
    }

    // Check if enough time has passed since last contact
    if (state.lastContactAt) {
      const daysSinceContact =
        (Date.now() - state.lastContactAt.getTime()) / (1000 * 60 * 60 * 24);
      const requiredDelay = nextStep.delayDays - (state.steps[0]?.delayDays ?? 0);
      if (daysSinceContact < requiredDelay) {
        logger.info(
          `Waiting ${requiredDelay - daysSinceContact} more days before next step`,
          { leadId: lead.id }
        );
        return { lead, completed: false };
      }
    }

    // Execute on the appropriate channel
    const result = await this.executeOnChannel(lead, nextStep);

    if (result.success) {
      nextStep.status = "sent";
      nextStep.sentAt = new Date();
      state.currentStep = nextStep.stepNumber;
      state.lastContactAt = new Date();
      state.channel = nextStep.channel;

      // Schedule next contact
      const followingStep = state.steps.find(
        (s) => s.stepNumber > nextStep.stepNumber && s.status === "pending"
      );
      if (followingStep) {
        const nextDate = new Date();
        nextDate.setDate(nextDate.getDate() + followingStep.delayDays);
        state.nextContactAt = nextDate;
      }

      // Add to conversation history
      lead.conversationHistory.push({
        id: uuid(),
        channel: nextStep.channel,
        direction: "outbound",
        content: nextStep.content,
        timestamp: new Date(),
      });

      logger.info(
        `Step ${nextStep.stepNumber} executed on ${nextStep.channel} for ${lead.fullName}`,
        { leadId: lead.id }
      );
    } else {
      nextStep.status = "failed";
      logger.error(`Step ${nextStep.stepNumber} failed for ${lead.fullName}`, {
        leadId: lead.id,
        error: result.error,
      });
    }

    return { lead, completed: false };
  }

  /**
   * Handle an inbound reply from a lead.
   * Analyzes sentiment, generates appropriate response, and updates the sequence.
   */
  async handleReply(
    lead: Lead,
    inboundMessage: string,
    channel: Channel,
    businessDNA: BusinessDNA,
    knowledgeContext?: string
  ): Promise<{
    reply: string | null;
    sentiment: SentimentResult;
    shouldBook: boolean;
  }> {
    // Record the inbound message
    lead.conversationHistory.push({
      id: uuid(),
      channel,
      direction: "inbound",
      content: inboundMessage,
      timestamp: new Date(),
    });

    // Analyze sentiment
    const quickResult = this.sentimentAnalyzer.quickCheck(inboundMessage);
    const sentiment =
      quickResult ??
      (await this.sentimentAnalyzer.analyze(
        inboundMessage,
        lead.conversationHistory
      ));

    lead.sentiment = sentiment;

    // If we should stop, pause the sequence
    if (sentiment.shouldStop) {
      if (lead.sequenceState) {
        lead.sequenceState.pausedReason = `Sentiment: ${sentiment.intent}`;
        for (const step of lead.sequenceState.steps) {
          if (step.status === "pending") step.status = "failed";
        }
      }
      lead.status = sentiment.intent === "angry" ? "opted_out" : "disqualified";

      return { reply: null, sentiment, shouldBook: false };
    }

    // Check if we should move to booking
    const shouldBook =
      sentiment.intent === "interested" && sentiment.score > 0.5;

    // Generate a reply
    const reply = await this.contentGenerator.generateReply({
      lead,
      businessDNA,
      inboundMessage,
      conversationHistory: lead.conversationHistory,
      knowledgeContext,
    });

    // Pause automated sequence since we're now in a conversation
    if (lead.sequenceState) {
      lead.sequenceState.pausedReason = "In active conversation";
    }
    lead.status = "replied";

    return { reply, sentiment, shouldBook };
  }

  private async executeOnChannel(
    lead: Lead,
    step: SequenceStep
  ): Promise<{ success: boolean; error?: string }> {
    switch (step.channel) {
      case "linkedin":
        return this.linkedIn.executeStep(lead, step);
      case "email":
        return this.email.executeStep(lead, step);
      case "instagram":
        return this.instagram.executeStep(lead, step);
      default:
        return { success: false, error: `Unknown channel: ${step.channel}` };
    }
  }

  /**
   * Dynamically select and adapt the sequence template based on the lead's
   * profile, available channels, and score tier.
   */
  private selectSequenceTemplate(lead: Lead): typeof DEFAULT_SEQUENCE {
    const template = [...DEFAULT_SEQUENCE];

    // Adapt based on psychological profile if available
    if (lead.profile) {
      const preferred = lead.profile.preferredContactMethod;

      // Move preferred channel earlier in the sequence
      if (preferred === "email") {
        // Swap so email comes first instead of LinkedIn
        const emailIdx = template.findIndex((s) => s.channel === "email");
        if (emailIdx > 0) {
          [template[0], template[emailIdx]] = [template[emailIdx], template[0]];
        }
      }

      // Analytical/data-driven profiles get more email (longer form content)
      if (lead.profile.communicationStyle === "analytical") {
        // Replace the Instagram step with another email (case study)
        const igIdx = template.findIndex((s) => s.channel === "instagram");
        if (igIdx >= 0) {
          template[igIdx] = { ...template[igIdx], channel: "email" };
        }
      }

      // Shorter sequences for "driver" profiles who want to get to the point
      if (lead.profile.communicationStyle === "driver") {
        return template.slice(0, 5); // Cut to 5 steps instead of 7
      }
    }

    // Lower-scored leads (6-7) get a shorter 4-step sequence
    if (lead.score >= 6 && lead.score <= 7) {
      return template.filter((_, i) => [0, 1, 3, 6].includes(i));
    }

    return template;
  }

  private hasChannelInfo(lead: Lead, channel: Channel): boolean {
    switch (channel) {
      case "linkedin":
        return !!lead.linkedInUrl;
      case "email":
        return !!(lead.email || lead.enrichment?.emails?.length);
      case "instagram":
        return !!lead.instagramHandle;
      default:
        return false;
    }
  }
}
