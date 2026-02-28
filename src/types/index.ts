// ─── Core Domain Types ──────────────────────────────────────────

export interface BusinessDNA {
  companyName: string;
  industry: string;
  valueProposition: string;
  targetMarkets: string[];
  pastSuccesses: CaseStudy[];
  products: Product[];
  averageDealSize: number;
  salesCycle: string;
  competitiveAdvantages: string[];
  objectionHandling: Record<string, string>;
  brandVoice: BrandVoice;
}

export interface BrandVoice {
  tone: "professional" | "casual" | "consultative" | "authoritative";
  personality: string[];
  doNots: string[];
  sampleMessages: string[];
}

export interface CaseStudy {
  client: string;
  industry: string;
  problem: string;
  solution: string;
  result: string;
  ltv: number;
}

export interface Product {
  name: string;
  description: string;
  priceRange: string;
  idealFor: string[];
}

// ─── ICP (Ideal Customer Profile) ───────────────────────────────

export interface ICP {
  id: string;
  demographics: {
    industries: string[];
    companySizeRange: [number, number];
    revenueRange: [number, number];
    geographies: string[];
    fundingStage?: string[];
  };
  firmographics: {
    techStack: string[];
    growthSignals: string[];
    painPoints: string[];
    buyingTriggers: string[];
  };
  decisionMaker: {
    titles: string[];
    departments: string[];
    seniorityLevels: string[];
    responsibilities: string[];
  };
  qualifiers: {
    mustHave: string[];
    niceToHave: string[];
    disqualifiers: string[];
  };
  estimatedLTV: number;
}

// ─── Lead ───────────────────────────────────────────────────────

export type LeadStatus =
  | "sourced"
  | "enriched"
  | "researched"
  | "scored"
  | "approved"
  | "in_sequence"
  | "replied"
  | "meeting_booked"
  | "disqualified"
  | "opted_out";

export interface Lead {
  id: string;
  status: LeadStatus;
  score: number;
  source: "apollo" | "linkedin" | "clay" | "manual";
  createdAt: Date;
  updatedAt: Date;

  // Contact info
  firstName: string;
  lastName: string;
  fullName: string;
  email?: string;
  emailVerified: boolean;
  phone?: string;
  linkedInUrl?: string;
  instagramHandle?: string;

  // Company info
  company: CompanyInfo;

  // Decision-maker context
  title: string;
  department: string;
  seniority: string;
  yearsInRole?: number;

  // Enrichment data
  research?: DeepResearch;
  profile?: PsychologicalProfile;
  enrichment?: ContactEnrichment;

  // Outreach state
  sequenceState?: SequenceState;
  conversationHistory: ConversationMessage[];
  sentiment?: SentimentResult;

  // Metadata
  tags: string[];
  notes: string[];
  icpMatchScore: number;
}

export interface CompanyInfo {
  name: string;
  domain: string;
  industry: string;
  size: number;
  revenue?: number;
  founded?: number;
  techStack: string[];
  recentFunding?: string;
  recentNews: NewsItem[];
  painPoints: string[];
  competitors: string[];
}

export interface NewsItem {
  title: string;
  url: string;
  date: string;
  summary: string;
  relevanceScore: number;
}

// ─── Intelligence Layer ─────────────────────────────────────────

export interface DeepResearch {
  companyAnalysis: {
    recentNews: NewsItem[];
    financialHealth: string;
    growthTrajectory: string;
    strategicPriorities: string[];
    challenges: string[];
  };
  personAnalysis: {
    recentActivity: string[];
    publishedContent: string[];
    sharedInterests: string[];
    careerTrajectory: string;
    decisionMakingStyle: string;
  };
  painPointMapping: {
    identified: string[];
    severity: Record<string, number>;
    ourSolution: Record<string, string>;
  };
  competitiveIntel: {
    currentVendors: string[];
    dissatisfactionSignals: string[];
    switchingCost: "low" | "medium" | "high";
  };
  researchedAt: Date;
}

export interface PsychologicalProfile {
  communicationStyle: "analytical" | "driver" | "expressive" | "amiable";
  decisionMaking: "data_driven" | "intuitive" | "collaborative" | "decisive";
  motivators: string[];
  riskTolerance: "low" | "medium" | "high";
  preferredContactMethod: "email" | "linkedin" | "phone";
  personalityTraits: string[];
  responsePatterns: {
    bestTimeToContact: string;
    preferredMessageLength: "short" | "medium" | "detailed";
    formality: "formal" | "semi_formal" | "casual";
  };
  recommendedApproach: string;
  profiledAt: Date;
}

export interface ContactEnrichment {
  emails: VerifiedContact[];
  phones: VerifiedContact[];
  socialProfiles: Record<string, string>;
  enrichedAt: Date;
}

export interface VerifiedContact {
  value: string;
  verified: boolean;
  confidence: number;
  source: string;
}

// ─── Sentiment Analysis ─────────────────────────────────────────

export interface SentimentResult {
  overall: "positive" | "neutral" | "negative" | "hostile";
  score: number; // -1 to 1
  intent: "interested" | "curious" | "objecting" | "declining" | "angry";
  shouldStop: boolean;
  shouldEscalate: boolean;
  suggestedAction: string;
  analyzedAt: Date;
}

// ─── Outreach ───────────────────────────────────────────────────

export type Channel = "linkedin" | "email" | "instagram";

export interface SequenceState {
  currentStep: number;
  totalSteps: number;
  channel: Channel;
  startedAt: Date;
  lastContactAt?: Date;
  nextContactAt?: Date;
  pausedReason?: string;
  steps: SequenceStep[];
}

export interface SequenceStep {
  stepNumber: number;
  channel: Channel;
  type: "connection_request" | "message" | "email" | "dm" | "follow_up" | "breakup";
  content: string;
  sentAt?: Date;
  deliveredAt?: Date;
  openedAt?: Date;
  repliedAt?: Date;
  status: "pending" | "sent" | "delivered" | "opened" | "replied" | "bounced" | "failed";
  delayDays: number;
}

export interface ConversationMessage {
  id: string;
  channel: Channel;
  direction: "outbound" | "inbound";
  content: string;
  timestamp: Date;
  sentiment?: SentimentResult;
}

export interface OutreachTemplate {
  id: string;
  channel: Channel;
  type: SequenceStep["type"];
  subjectLine?: string;
  bodyTemplate: string;
  variables: string[];
  abVariant?: string;
}

// ─── HITL (Human-in-the-Loop) ───────────────────────────────────

export interface ApprovalRequest {
  id: string;
  leadId: string;
  type: "first_outreach" | "escalation" | "high_value_lead" | "negative_sentiment";
  lead: Lead;
  proposedAction: {
    channel: Channel;
    content: string;
    reason: string;
  };
  researchSummary: string;
  status: "pending" | "approved" | "rejected" | "modified";
  submittedAt: Date;
  resolvedAt?: Date;
  resolvedBy?: string;
  modifiedContent?: string;
}

// ─── Booking ────────────────────────────────────────────────────

export interface BookingRequest {
  leadId: string;
  leadName: string;
  leadEmail: string;
  preferredTimes?: string[];
  meetingType: "discovery" | "demo" | "consultation";
  duration: 15 | 30 | 45 | 60;
  notes: string;
}

export interface BookingResult {
  success: boolean;
  meetingUrl?: string;
  scheduledAt?: Date;
  calendarEventId?: string;
  error?: string;
}

// ─── Pipeline Events ────────────────────────────────────────────

export type PipelineEvent =
  | { type: "lead_sourced"; lead: Lead }
  | { type: "lead_enriched"; leadId: string; enrichment: ContactEnrichment }
  | { type: "lead_researched"; leadId: string; research: DeepResearch }
  | { type: "lead_profiled"; leadId: string; profile: PsychologicalProfile }
  | { type: "lead_scored"; leadId: string; score: number }
  | { type: "approval_requested"; request: ApprovalRequest }
  | { type: "approval_resolved"; requestId: string; status: "approved" | "rejected" }
  | { type: "outreach_sent"; leadId: string; step: SequenceStep }
  | { type: "reply_received"; leadId: string; message: ConversationMessage }
  | { type: "sentiment_detected"; leadId: string; sentiment: SentimentResult }
  | { type: "meeting_booked"; leadId: string; booking: BookingResult }
  | { type: "lead_disqualified"; leadId: string; reason: string };
