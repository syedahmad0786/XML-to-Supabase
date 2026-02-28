import { SalesGrowthPipeline } from "./orchestrator/pipeline.js";
import type { BusinessDNA, PipelineEvent } from "./types/index.js";
import { createLogger } from "./utils/logger.js";

const logger = createLogger("main");

/**
 * AI Sales & Growth Agent — Main Entry Point
 *
 * Usage:
 *   1. Configure .env with API keys
 *   2. Define your BusinessDNA (see example below)
 *   3. Run: npm run dev
 *
 * Or use as a library:
 *   import { SalesGrowthPipeline } from 'ai-sales-growth-agent'
 */

// Example BusinessDNA — replace with your actual business data
const exampleBusinessDNA: BusinessDNA = {
  companyName: "Acme AI Solutions",
  industry: "B2B SaaS",
  valueProposition:
    "We help mid-market SaaS companies reduce customer churn by 40% using predictive AI analytics that identify at-risk accounts 90 days before they leave.",
  targetMarkets: ["SaaS", "FinTech", "HealthTech"],
  pastSuccesses: [
    {
      client: "TechCorp",
      industry: "SaaS",
      problem: "25% annual churn rate eating into growth",
      solution: "Deployed predictive churn model integrated with their CRM",
      result: "Reduced churn to 12% in 6 months, saving $2.1M ARR",
      ltv: 180000,
    },
    {
      client: "FinServe Pro",
      industry: "FinTech",
      problem: "No visibility into which enterprise accounts were at risk",
      solution: "Built real-time health scoring dashboard for CS team",
      result: "CS team intervened on 45 at-risk accounts, retained 38 (84%)",
      ltv: 250000,
    },
  ],
  products: [
    {
      name: "ChurnShield",
      description: "AI-powered churn prediction and prevention platform",
      priceRange: "$2,000-$15,000/month",
      idealFor: ["SaaS companies with 1000+ customers", "Companies with dedicated CS teams"],
    },
  ],
  averageDealSize: 8000,
  salesCycle: "30-60 days",
  competitiveAdvantages: [
    "90-day advance warning vs industry average of 30 days",
    "Integrates with 40+ CRMs and CS platforms",
    "No data science team required — fully managed",
  ],
  objectionHandling: {
    "We already use [competitor]":
      "Great — most of our clients switched from [competitor] because they only catch at-risk accounts 30 days out. We give you 90 days of warning, which is the difference between a save and a loss. Happy to show you a side-by-side comparison.",
    "It's too expensive":
      "I understand budget is a concern. Consider this: if ChurnShield saves even 5 accounts per quarter at your average ACV, that's [X] in retained revenue vs. our [Y] cost. The ROI typically hits 400% in the first year.",
    "We don't have a churn problem":
      "That's great to hear! Most companies that say that actually have hidden churn they don't see yet — like customers who've stopped expanding or reduced usage. Would a quick health audit be useful, even just to validate your retention metrics?",
    "We need to involve more stakeholders":
      "Absolutely — these decisions deserve proper evaluation. Would it be helpful if I put together a one-page ROI analysis your team can review? I can also join a call with your CS/RevOps leads to answer their specific questions.",
  },
  brandVoice: {
    tone: "consultative",
    personality: ["knowledgeable", "empathetic", "data-driven", "direct"],
    doNots: [
      "Don't be pushy or salesy",
      "Don't use jargon without context",
      "Don't make unsubstantiated claims",
      "Don't be overly casual in first touch",
    ],
    sampleMessages: [
      "Noticed TechCorp just raised Series C — congrats! With rapid scaling, churn usually creeps up between months 6-12. We helped [similar company] keep it under 10% through that phase. Worth a 15-min chat?",
    ],
  },
};

async function main() {
  logger.info("Starting AI Sales & Growth Agent");

  const pipeline = new SalesGrowthPipeline();

  // Subscribe to pipeline events
  pipeline.onEvent((event: PipelineEvent) => {
    switch (event.type) {
      case "lead_sourced":
        logger.info(`Lead sourced: ${event.lead.fullName} at ${event.lead.company.name}`);
        break;
      case "lead_scored":
        logger.info(`Lead scored: ${event.leadId} → ${event.score}/10`);
        break;
      case "approval_requested":
        logger.info(`Approval needed: ${event.request.type} for ${event.request.lead.fullName}`);
        break;
      case "meeting_booked":
        logger.info(`MEETING BOOKED for lead ${event.leadId}!`);
        break;
      case "sentiment_detected":
        if (event.sentiment.shouldStop) {
          logger.warn(`STOP: Lead ${event.leadId} — ${event.sentiment.intent}`);
        }
        break;
    }
  });

  // Initialize with business DNA
  await pipeline.initialize(exampleBusinessDNA);

  // Run the full pipeline
  const results = await pipeline.runFullPipeline({
    apolloPages: 2,
    maxLeads: 10,
  });

  logger.info("Pipeline run complete", results);
}

main().catch((error) => {
  logger.error("Fatal error", { error });
  process.exit(1);
});

// Export for library usage
export { SalesGrowthPipeline } from "./orchestrator/pipeline.js";
export { ICPAnalyzer } from "./strategy/icp-analyzer.js";
export { LeadSourcer } from "./strategy/lead-sourcer.js";
export { LeadScorer } from "./strategy/lead-scorer.js";
export { DeepResearcher } from "./intelligence/deep-researcher.js";
export { PsychologicalProfiler } from "./intelligence/psychological-profiler.js";
export { ContactEnricher } from "./intelligence/contact-enricher.js";
export { SentimentAnalyzer } from "./intelligence/sentiment-analyzer.js";
export { SequenceOrchestrator } from "./outreach/sequence-orchestrator.js";
export { ContentGenerator } from "./outreach/content-generator.js";
export { KnowledgeBase } from "./memory/knowledge-base.js";
export { ConversationMemory } from "./memory/conversation-memory.js";
export { VectorStore } from "./memory/vector-store.js";
export { AppointmentSetter } from "./booking/appointment-setter.js";
export { ApprovalGateway } from "./hitl/approval-gateway.js";
export type * from "./types/index.js";
