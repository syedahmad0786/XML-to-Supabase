import { z } from "zod";

export const configSchema = z.object({
  llm: z.object({
    provider: z.enum(["anthropic", "openai"]).default("anthropic"),
    anthropicApiKey: z.string().min(1),
    openaiApiKey: z.string().optional(),
    primaryModel: z.string().default("claude-sonnet-4-6"),
    researchModel: z.string().default("claude-opus-4-6"),
    fastModel: z.string().default("claude-haiku-4-5-20251001"),
  }),

  vectorStore: z.object({
    provider: z.enum(["pinecone", "supabase"]).default("pinecone"),
    pineconeApiKey: z.string().optional(),
    pineconeIndex: z.string().default("sales-agent-memory"),
    pineconeEnvironment: z.string().default("us-east-1"),
  }),

  supabase: z.object({
    url: z.string().url(),
    serviceKey: z.string().min(1),
  }),

  leadSourcing: z.object({
    apolloApiKey: z.string().optional(),
    clayApiKey: z.string().optional(),
    linkedInEmail: z.string().optional(),
    linkedInPassword: z.string().optional(),
    linkedInSalesNavCookie: z.string().optional(),
  }),

  email: z.object({
    smtpHost: z.string().default("smtp.gmail.com"),
    smtpPort: z.number().default(587),
    smtpUser: z.string(),
    smtpPassword: z.string(),
    fromName: z.string(),
    fromAddress: z.string().email(),
  }),

  instagram: z.object({
    accessToken: z.string().optional(),
    businessAccountId: z.string().optional(),
  }),

  booking: z.object({
    calendlyApiKey: z.string().optional(),
    calendlyEventTypeUri: z.string().optional(),
    googleCalendarCredentialsPath: z.string().optional(),
  }),

  hitl: z.object({
    slackWebhookUrl: z.string().optional(),
    slackApprovalChannel: z.string().default("#sales-approvals"),
    discordWebhookUrl: z.string().optional(),
    requiredForFirstMessage: z.boolean().default(true),
  }),

  redis: z.object({
    url: z.string().default("redis://localhost:6379"),
  }),

  agent: z.object({
    leadScoreThreshold: z.number().min(1).max(10).default(8),
    maxLeadsPerDay: z.number().default(50),
    outreachDelayMinutes: z.number().default(60),
    deepResearchEnabled: z.boolean().default(true),
    maxSequenceSteps: z.number().default(7),
    sequenceDurationDays: z.number().default(14),
  }),
});

export type AppConfig = z.infer<typeof configSchema>;
