import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/index.js";
import type { ConversationMessage, SentimentResult } from "../types/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("sentiment-analyzer");

const SENTIMENT_PROMPT = `You are an expert at reading intent and emotion in B2B sales conversations.
Analyze the following message(s) from a lead and determine their sentiment, intent, and the
recommended action for our sales agent.

Conversation context (most recent messages):
{conversationContext}

Latest message from the lead:
"{latestMessage}"

CRITICAL RULES:
- If the lead says "no", "not interested", "remove me", "stop", "unsubscribe" → MUST flag shouldStop = true
- If the lead is angry, threatening, or hostile → MUST flag shouldStop = true AND shouldEscalate = true
- If the lead says "not now" or "maybe later" → This is NOT a stop signal, but mark intent as "declining"
- If the lead asks a question → This is a positive buying signal (intent = "curious" or "interested")
- If the lead mentions a competitor → Note this but don't panic

Return a JSON object:
{
  "overall": "positive" | "neutral" | "negative" | "hostile",
  "score": number (-1.0 to 1.0, where -1 is extremely negative, 1 is extremely positive),
  "intent": "interested" | "curious" | "objecting" | "declining" | "angry",
  "shouldStop": boolean (true = stop all outreach immediately),
  "shouldEscalate": boolean (true = notify a human immediately),
  "suggestedAction": "Brief recommendation for next action"
}

Return ONLY the JSON object.`;

export class SentimentAnalyzer {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: config.llm.anthropicApiKey });
  }

  /**
   * Analyze the sentiment of an incoming message in context of the conversation.
   * Uses the fast model since this needs to be real-time.
   */
  async analyze(
    latestMessage: string,
    conversationHistory: ConversationMessage[]
  ): Promise<SentimentResult> {
    const recentContext = conversationHistory
      .slice(-6)
      .map(
        (msg) =>
          `[${msg.direction === "outbound" ? "Us" : "Lead"}] (${msg.channel}): ${msg.content}`
      )
      .join("\n");

    const prompt = SENTIMENT_PROMPT
      .replace("{conversationContext}", recentContext || "No prior context.")
      .replace("{latestMessage}", latestMessage);

    const response = await this.client.messages.create({
      model: config.llm.fastModel,
      max_tokens: 512,
      messages: [{ role: "user", content: prompt }],
    });

    const content = response.content[0];
    if (content.type !== "text") {
      throw new Error("Unexpected response type from sentiment analysis");
    }

    const result = JSON.parse(content.text) as Omit<SentimentResult, "analyzedAt">;

    // Hard-coded safety net: always stop on explicit opt-out keywords
    const lower = latestMessage.toLowerCase();
    const stopWords = ["unsubscribe", "stop emailing", "remove me", "do not contact", "f**k off", "leave me alone"];
    if (stopWords.some((w) => lower.includes(w))) {
      result.shouldStop = true;
      result.suggestedAction = "Lead explicitly opted out. Stop all outreach immediately.";
    }

    const sentimentResult: SentimentResult = {
      ...result,
      analyzedAt: new Date(),
    };

    if (sentimentResult.shouldStop) {
      logger.warn(`STOP signal detected in message`, {
        intent: sentimentResult.intent,
        shouldEscalate: sentimentResult.shouldEscalate,
      });
    }

    if (sentimentResult.shouldEscalate) {
      logger.warn(`ESCALATION required — negative/hostile sentiment detected`);
    }

    return sentimentResult;
  }

  /**
   * Quick sentiment check using keyword matching before LLM call.
   * Returns null if uncertain (requires full LLM analysis).
   */
  quickCheck(message: string): SentimentResult | null {
    const lower = message.toLowerCase().trim();

    // Definite stop signals
    const hardStops = [
      "unsubscribe",
      "stop",
      "remove me",
      "not interested",
      "do not contact",
      "leave me alone",
    ];
    if (hardStops.some((s) => lower.includes(s))) {
      return {
        overall: "negative",
        score: -0.8,
        intent: "declining",
        shouldStop: true,
        shouldEscalate: false,
        suggestedAction: "Respect opt-out. Send a brief, polite acknowledgment and stop.",
        analyzedAt: new Date(),
      };
    }

    // Positive signals
    const positiveSignals = [
      "tell me more",
      "interested",
      "sounds good",
      "let's chat",
      "can you send",
      "schedule a call",
      "book a time",
    ];
    if (positiveSignals.some((s) => lower.includes(s))) {
      return {
        overall: "positive",
        score: 0.7,
        intent: "interested",
        shouldStop: false,
        shouldEscalate: false,
        suggestedAction: "Positive engagement detected. Move to booking.",
        analyzedAt: new Date(),
      };
    }

    // Uncertain — need full LLM analysis
    return null;
  }
}
