import "dotenv/config";
import { configSchema, type AppConfig } from "./schema.js";

function loadConfig(): AppConfig {
  const raw = {
    llm: {
      provider: process.env.LLM_PROVIDER ?? "anthropic",
      anthropicApiKey: process.env.ANTHROPIC_API_KEY ?? "",
      openaiApiKey: process.env.OPENAI_API_KEY,
      primaryModel: process.env.LLM_PRIMARY_MODEL ?? "claude-sonnet-4-6",
      researchModel: process.env.LLM_RESEARCH_MODEL ?? "claude-opus-4-6",
      fastModel: process.env.LLM_FAST_MODEL ?? "claude-haiku-4-5-20251001",
    },
    vectorStore: {
      provider: process.env.VECTOR_STORE_PROVIDER ?? "pinecone",
      pineconeApiKey: process.env.PINECONE_API_KEY,
      pineconeIndex: process.env.PINECONE_INDEX ?? "sales-agent-memory",
      pineconeEnvironment: process.env.PINECONE_ENVIRONMENT ?? "us-east-1",
    },
    supabase: {
      url: process.env.SUPABASE_URL ?? "",
      serviceKey: process.env.SUPABASE_SERVICE_KEY ?? "",
    },
    leadSourcing: {
      apolloApiKey: process.env.APOLLO_API_KEY,
      clayApiKey: process.env.CLAY_API_KEY,
      linkedInEmail: process.env.LINKEDIN_EMAIL,
      linkedInPassword: process.env.LINKEDIN_PASSWORD,
      linkedInSalesNavCookie: process.env.LINKEDIN_SALES_NAV_COOKIE,
    },
    email: {
      smtpHost: process.env.SMTP_HOST ?? "smtp.gmail.com",
      smtpPort: parseInt(process.env.SMTP_PORT ?? "587"),
      smtpUser: process.env.SMTP_USER ?? "",
      smtpPassword: process.env.SMTP_PASSWORD ?? "",
      fromName: process.env.EMAIL_FROM_NAME ?? "",
      fromAddress: process.env.EMAIL_FROM_ADDRESS ?? "",
    },
    instagram: {
      accessToken: process.env.INSTAGRAM_ACCESS_TOKEN,
      businessAccountId: process.env.INSTAGRAM_BUSINESS_ACCOUNT_ID,
    },
    booking: {
      calendlyApiKey: process.env.CALENDLY_API_KEY,
      calendlyEventTypeUri: process.env.CALENDLY_EVENT_TYPE_URI,
      googleCalendarCredentialsPath: process.env.GOOGLE_CALENDAR_CREDENTIALS_PATH,
    },
    hitl: {
      slackWebhookUrl: process.env.SLACK_WEBHOOK_URL,
      slackApprovalChannel: process.env.SLACK_APPROVAL_CHANNEL ?? "#sales-approvals",
      discordWebhookUrl: process.env.DISCORD_WEBHOOK_URL,
      requiredForFirstMessage:
        process.env.HITL_REQUIRED_FOR_FIRST_MESSAGE !== "false",
    },
    redis: {
      url: process.env.REDIS_URL ?? "redis://localhost:6379",
    },
    agent: {
      leadScoreThreshold: parseInt(process.env.LEAD_SCORE_THRESHOLD ?? "8"),
      maxLeadsPerDay: parseInt(process.env.MAX_LEADS_PER_DAY ?? "50"),
      outreachDelayMinutes: parseInt(process.env.OUTREACH_DELAY_MINUTES ?? "60"),
      deepResearchEnabled: process.env.DEEP_RESEARCH_ENABLED !== "false",
      maxSequenceSteps: parseInt(process.env.MAX_SEQUENCE_STEPS ?? "7"),
      sequenceDurationDays: parseInt(process.env.SEQUENCE_DURATION_DAYS ?? "14"),
    },
  };

  return configSchema.parse(raw);
}

export const config = loadConfig();
export type { AppConfig };
