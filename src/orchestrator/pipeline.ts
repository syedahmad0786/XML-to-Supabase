import { config } from "../config/index.js";
import type { BusinessDNA, Lead, ICP, PipelineEvent } from "../types/index.js";
import { ICPAnalyzer } from "../strategy/icp-analyzer.js";
import { LeadSourcer } from "../strategy/lead-sourcer.js";
import { LeadScorer } from "../strategy/lead-scorer.js";
import { DeepResearcher } from "../intelligence/deep-researcher.js";
import { PsychologicalProfiler } from "../intelligence/psychological-profiler.js";
import { ContactEnricher } from "../intelligence/contact-enricher.js";
import { SentimentAnalyzer } from "../intelligence/sentiment-analyzer.js";
import { SequenceOrchestrator } from "../outreach/sequence-orchestrator.js";
import { KnowledgeBase } from "../memory/knowledge-base.js";
import { ConversationMemory } from "../memory/conversation-memory.js";
import { AppointmentSetter } from "../booking/appointment-setter.js";
import { ApprovalGateway } from "../hitl/approval-gateway.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("pipeline");

type EventHandler = (event: PipelineEvent) => void | Promise<void>;

/**
 * Main pipeline orchestrator.
 *
 * Single-line flow:
 * BusinessDNA → ICP Analysis → Lead Sourcing → Scoring (1-10) → [Score >= 8] →
 * Deep Research → Psychological Profiling → Contact Enrichment → HITL Approval →
 * Multi-Channel Sequence (LinkedIn → Email → IG) → Sentiment Monitoring →
 * Objection Handling (Knowledge Base) → Meeting Booking
 *
 * The pipeline maintains state in Supabase and uses Redis queues for
 * async step execution. Each lead progresses through the pipeline independently.
 */
export class SalesGrowthPipeline {
  private icpAnalyzer: ICPAnalyzer;
  private leadSourcer: LeadSourcer;
  private leadScorer: LeadScorer;
  private deepResearcher: DeepResearcher;
  private profiler: PsychologicalProfiler;
  private enricher: ContactEnricher;
  private sentimentAnalyzer: SentimentAnalyzer;
  private sequenceOrchestrator: SequenceOrchestrator;
  private knowledgeBase: KnowledgeBase;
  private conversationMemory: ConversationMemory;
  private appointmentSetter: AppointmentSetter;
  private approvalGateway: ApprovalGateway;

  private businessDNA!: BusinessDNA;
  private icps: ICP[] = [];
  private eventHandlers: EventHandler[] = [];

  constructor() {
    this.icpAnalyzer = new ICPAnalyzer();
    this.leadSourcer = new LeadSourcer();
    this.leadScorer = new LeadScorer();
    this.deepResearcher = new DeepResearcher();
    this.profiler = new PsychologicalProfiler();
    this.enricher = new ContactEnricher();
    this.sentimentAnalyzer = new SentimentAnalyzer();
    this.sequenceOrchestrator = new SequenceOrchestrator();
    this.knowledgeBase = new KnowledgeBase();
    this.conversationMemory = new ConversationMemory();
    this.appointmentSetter = new AppointmentSetter();
    this.approvalGateway = new ApprovalGateway();
  }

  /**
   * Subscribe to pipeline events for monitoring/logging.
   */
  onEvent(handler: EventHandler): void {
    this.eventHandlers.push(handler);
  }

  /**
   * Phase 0: Initialize the pipeline with business context.
   * Must be called before running any leads through.
   */
  async initialize(businessDNA: BusinessDNA): Promise<void> {
    logger.info("Initializing pipeline...");
    this.businessDNA = businessDNA;

    // Ingest business knowledge into the vector store
    await this.knowledgeBase.ingestBusinessDNA(businessDNA);

    // Generate ICPs from business DNA
    this.icps = await this.icpAnalyzer.analyzeBusinessDNA(businessDNA);
    logger.info(`Generated ${this.icps.length} ICP segments`);

    logger.info("Pipeline initialized successfully");
  }

  /**
   * Phase 1: Source and score leads.
   * Returns scored leads sorted by priority.
   */
  async sourceAndScore(
    options: { apolloPages?: number; clayTableId?: string } = {}
  ): Promise<Lead[]> {
    logger.info("Phase 1: Sourcing leads...");
    const allLeads: Lead[] = [];

    for (const icp of this.icps) {
      const leads = await this.leadSourcer.sourceFromAllChannels(icp, options);
      logger.info(`Sourced ${leads.length} leads for ICP ${icp.id}`);

      for (const lead of leads) {
        this.emit({ type: "lead_sourced", lead });
      }

      // Score all leads
      const scored = await this.leadScorer.batchScore(leads, icp);

      for (const { lead, score } of scored) {
        lead.score = score.overall;
        lead.icpMatchScore = score.scores.icpFit;
        lead.status = "scored";
        this.emit({ type: "lead_scored", leadId: lead.id, score: score.overall });
        allLeads.push(lead);
      }
    }

    // Sort by score, deduplicate across ICPs
    const deduped = this.deduplicateLeads(allLeads);
    deduped.sort((a, b) => b.score - a.score);

    logger.info(`Phase 1 complete: ${deduped.length} scored leads`);
    return deduped;
  }

  /**
   * Phase 2: Enrich, research, and profile a single lead.
   * Only runs for leads scoring >= threshold (default 8).
   */
  async enrichAndResearch(lead: Lead): Promise<Lead> {
    const tier = this.leadScorer.getResourceTier(lead.score);

    logger.info(`Phase 2: Enriching ${lead.fullName} (tier: ${tier})`);

    // Contact enrichment (all tiers)
    const enrichment = await this.enricher.enrich(lead);
    lead.enrichment = enrichment;
    lead.status = "enriched";
    this.emit({ type: "lead_enriched", leadId: lead.id, enrichment });

    // Deep or light research based on tier
    let research;
    if (tier === "tier1" && config.agent.deepResearchEnabled) {
      research = await this.deepResearcher.research(lead);
    } else if (tier === "tier2") {
      research = await this.deepResearcher.lightResearch(lead);
    } else {
      logger.info(`Skipping research for tier3 lead ${lead.fullName}`);
      return lead;
    }

    lead.research = research;
    lead.status = "researched";
    this.emit({ type: "lead_researched", leadId: lead.id, research });

    // Psychological profiling (tier 1 only)
    if (tier === "tier1" && research) {
      const profile = await this.profiler.profileLead(lead, research);
      lead.profile = profile;
      this.emit({ type: "lead_profiled", leadId: lead.id, profile });
    }

    // Save to persistent storage
    await this.conversationMemory.saveLead(lead);

    return lead;
  }

  /**
   * Phase 3: Initialize and execute outreach sequence for a lead.
   * Includes HITL approval for the first message.
   */
  async startOutreach(lead: Lead): Promise<Lead> {
    logger.info(`Phase 3: Starting outreach for ${lead.fullName}`);

    // Initialize the multi-channel sequence
    const sequenceState = await this.sequenceOrchestrator.initializeSequence(
      lead,
      this.businessDNA
    );
    lead.sequenceState = sequenceState;

    // Check if HITL approval is needed for first message
    const firstStep = sequenceState.steps[0];
    if (
      firstStep &&
      this.approvalGateway.shouldRequireApproval(lead, true)
    ) {
      const researchSummary = lead.research
        ? `${lead.research.companyAnalysis.growthTrajectory}. Pain points: ${lead.research.painPointMapping.identified.join(", ")}`
        : "No deep research available.";

      const request = await this.approvalGateway.requestApproval({
        lead,
        type: "first_outreach",
        channel: firstStep.channel,
        content: firstStep.content,
        reason: "First outreach message requires human approval",
        researchSummary,
      });

      this.emit({ type: "approval_requested", request });

      // Wait for approval (non-blocking in production — use queue)
      const result = await this.approvalGateway.waitForApproval(request.id);

      if (!result.approved) {
        logger.info(`Outreach rejected for ${lead.fullName}`);
        lead.status = "disqualified";
        lead.notes.push("First outreach rejected by human reviewer");
        this.emit({
          type: "approval_resolved",
          requestId: request.id,
          status: "rejected",
        });
        return lead;
      }

      // Use modified content if provided
      if (result.modifiedContent) {
        firstStep.content = result.modifiedContent;
      }

      this.emit({
        type: "approval_resolved",
        requestId: request.id,
        status: "approved",
      });
    }

    // Execute the first step
    lead.status = "in_sequence";
    const { lead: updatedLead } = await this.sequenceOrchestrator.executeNextStep(
      lead,
      this.businessDNA
    );

    await this.conversationMemory.saveLead(updatedLead);
    return updatedLead;
  }

  /**
   * Phase 4: Handle an inbound reply from a lead.
   * Analyzes sentiment, generates reply, and potentially books a meeting.
   */
  async handleInboundReply(
    leadId: string,
    message: string,
    channel: "linkedin" | "email" | "instagram"
  ): Promise<void> {
    const lead = await this.conversationMemory.loadLead(leadId);
    if (!lead) {
      logger.error(`Lead not found: ${leadId}`);
      return;
    }

    // Load conversation history
    lead.conversationHistory = await this.conversationMemory.getHistory(leadId);

    // Get relevant knowledge base context for objection handling
    const knowledgeContext = await this.knowledgeBase.query(message);

    // Handle the reply
    const { reply, sentiment, shouldBook } =
      await this.sequenceOrchestrator.handleReply(
        lead,
        message,
        channel,
        this.businessDNA,
        knowledgeContext
      );

    // Record the inbound message
    const inboundMsg = lead.conversationHistory[lead.conversationHistory.length - 1];
    if (inboundMsg) {
      inboundMsg.sentiment = sentiment;
      await this.conversationMemory.recordMessage(leadId, inboundMsg);
    }

    this.emit({
      type: "reply_received",
      leadId,
      message: inboundMsg,
    });
    this.emit({ type: "sentiment_detected", leadId, sentiment });

    // If sentiment says stop, respect it
    if (sentiment.shouldStop) {
      lead.status = "opted_out";
      await this.conversationMemory.saveLead(lead);
      logger.info(`Lead ${lead.fullName} opted out`);
      return;
    }

    // If positive and ready to book
    if (shouldBook) {
      const bookingResult = await this.appointmentSetter.book({
        leadId: lead.id,
        leadName: lead.fullName,
        leadEmail: lead.email ?? "",
        meetingType: "discovery",
        duration: 30,
        notes: `Converted from ${channel} outreach. Score: ${lead.score}/10`,
      });

      if (bookingResult.success) {
        lead.status = "meeting_booked";
        this.emit({ type: "meeting_booked", leadId, booking: bookingResult });
      }
    }

    // Send the generated reply (with HITL check if sentiment is tricky)
    if (reply) {
      if (sentiment.shouldEscalate) {
        await this.approvalGateway.requestApproval({
          lead,
          type: "negative_sentiment",
          channel,
          content: reply,
          reason: `Sentiment: ${sentiment.overall} (${sentiment.intent})`,
          researchSummary: `Lead responded with ${sentiment.intent} sentiment. Score: ${sentiment.score}`,
        });
      }

      // Record outbound reply
      const outboundMsg = {
        id: `reply-${Date.now()}`,
        channel,
        direction: "outbound" as const,
        content: reply,
        timestamp: new Date(),
      };
      await this.conversationMemory.recordMessage(leadId, outboundMsg);
    }

    await this.conversationMemory.saveLead(lead);
  }

  /**
   * Continue outreach sequences for all active leads.
   * Called periodically (e.g., by a cron job or n8n workflow).
   */
  async advanceAllSequences(): Promise<void> {
    logger.info("Advancing all active sequences...");

    // In production, query Supabase for all leads with status "in_sequence"
    // and nextContactAt <= now. This is a simplified version.
    logger.info("Sequence advancement would be triggered by queue/cron");
  }

  /**
   * Run the full pipeline for a batch of leads.
   * This is the main entry point for a pipeline run.
   */
  async runFullPipeline(options: {
    apolloPages?: number;
    clayTableId?: string;
    maxLeads?: number;
  } = {}): Promise<{
    sourced: number;
    qualified: number;
    outreachStarted: number;
  }> {
    const maxLeads = options.maxLeads ?? config.agent.maxLeadsPerDay;

    // Phase 1: Source and score
    const leads = await this.sourceAndScore(options);
    const sourced = leads.length;

    // Filter to qualified leads
    const qualified = leads.filter(
      (l) => l.score >= config.agent.leadScoreThreshold
    );
    logger.info(
      `${qualified.length} leads qualified out of ${sourced} sourced`
    );

    // Limit to max leads per run
    const batch = qualified.slice(0, maxLeads);

    let outreachStarted = 0;

    // Phase 2 & 3: Enrich, research, and start outreach
    for (const lead of batch) {
      try {
        const enrichedLead = await this.enrichAndResearch(lead);

        if (enrichedLead.status !== "researched" && enrichedLead.status !== "enriched") {
          continue;
        }

        await this.startOutreach(enrichedLead);
        outreachStarted++;
      } catch (error) {
        logger.error(`Pipeline failed for lead ${lead.fullName}`, { error });
        lead.status = "disqualified";
        lead.notes.push(`Pipeline error: ${error}`);
      }
    }

    logger.info("Pipeline run complete", {
      sourced,
      qualified: qualified.length,
      outreachStarted,
    });

    return { sourced, qualified: qualified.length, outreachStarted };
  }

  private emit(event: PipelineEvent): void {
    for (const handler of this.eventHandlers) {
      try {
        handler(event);
      } catch (error) {
        logger.error("Event handler error", { error });
      }
    }
  }

  private deduplicateLeads(leads: Lead[]): Lead[] {
    const seen = new Map<string, Lead>();
    for (const lead of leads) {
      const key =
        lead.email?.toLowerCase() ??
        lead.linkedInUrl?.toLowerCase() ??
        `${lead.firstName}-${lead.lastName}-${lead.company.name}`.toLowerCase();

      const existing = seen.get(key);
      if (!existing || lead.score > existing.score) {
        seen.set(key, lead);
      }
    }
    return Array.from(seen.values());
  }
}
