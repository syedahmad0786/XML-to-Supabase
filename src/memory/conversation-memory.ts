import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { VectorStore } from "./vector-store.js";
import { config } from "../config/index.js";
import type { Lead, ConversationMessage, Channel } from "../types/index.js";
import { v4 as uuid } from "uuid";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("conversation-memory");

const CONVERSATION_NAMESPACE = "conversations";

/**
 * Conversation memory that maintains full context over multi-week outreach sequences.
 *
 * Two-tier architecture:
 * 1. Supabase (SQL): Structured conversation logs, lead state, sequence tracking
 * 2. Pinecone (Vector): Semantic search over past conversations for context retrieval
 *
 * This ensures the agent NEVER repeats itself, always references prior exchanges,
 * and can retrieve relevant context even weeks later.
 */
export class ConversationMemory {
  private supabase: SupabaseClient;
  private vectorStore: VectorStore;

  constructor() {
    this.supabase = createClient(config.supabase.url, config.supabase.serviceKey);
    this.vectorStore = new VectorStore();
  }

  /**
   * Record a new message (inbound or outbound) in both SQL and vector stores.
   */
  async recordMessage(
    leadId: string,
    message: ConversationMessage
  ): Promise<void> {
    // Store in Supabase for structured queries
    await this.supabase.from("conversation_messages").insert({
      id: message.id,
      lead_id: leadId,
      channel: message.channel,
      direction: message.direction,
      content: message.content,
      sentiment_overall: message.sentiment?.overall,
      sentiment_score: message.sentiment?.score,
      created_at: message.timestamp.toISOString(),
    });

    // Store in vector DB for semantic retrieval
    await this.vectorStore.upsert(
      [
        {
          id: message.id,
          content: `[${message.direction}] (${message.channel}): ${message.content}`,
          metadata: {
            lead_id: leadId,
            direction: message.direction,
            channel: message.channel,
            timestamp: message.timestamp.toISOString(),
          },
        },
      ],
      CONVERSATION_NAMESPACE
    );
  }

  /**
   * Get the full conversation history for a lead (from Supabase).
   */
  async getHistory(leadId: string): Promise<ConversationMessage[]> {
    const { data, error } = await this.supabase
      .from("conversation_messages")
      .select("*")
      .eq("lead_id", leadId)
      .order("created_at", { ascending: true });

    if (error) {
      logger.error("Failed to fetch conversation history", { leadId, error });
      return [];
    }

    return (data ?? []).map((row) => ({
      id: row.id,
      channel: row.channel as Channel,
      direction: row.direction as "inbound" | "outbound",
      content: row.content,
      timestamp: new Date(row.created_at),
      sentiment: row.sentiment_overall
        ? {
            overall: row.sentiment_overall,
            score: row.sentiment_score ?? 0,
            intent: "curious" as const,
            shouldStop: false,
            shouldEscalate: false,
            suggestedAction: "",
            analyzedAt: new Date(row.created_at),
          }
        : undefined,
    }));
  }

  /**
   * Semantic search over conversation history.
   * Finds messages relevant to a given context (e.g., an objection topic).
   * This prevents the agent from repeating arguments or missing context.
   */
  async searchConversations(
    leadId: string,
    query: string,
    topK = 5
  ): Promise<ConversationMessage[]> {
    const results = await this.vectorStore.search(query, {
      namespace: CONVERSATION_NAMESPACE,
      topK,
      filter: { lead_id: leadId },
    });

    return results.map((r) => ({
      id: r.id,
      channel: (r.metadata.channel as Channel) ?? "email",
      direction: (r.metadata.direction as "inbound" | "outbound") ?? "outbound",
      content: r.content,
      timestamp: new Date(r.metadata.timestamp as string),
    }));
  }

  /**
   * Build a conversation context summary for the LLM.
   * Includes recent messages plus semantically relevant older messages.
   */
  async buildContext(leadId: string, currentTopic?: string): Promise<string> {
    // Get recent messages (chronological)
    const history = await this.getHistory(leadId);
    const recent = history.slice(-6);

    // Get semantically relevant older messages if a topic is provided
    let relevantOlder: ConversationMessage[] = [];
    if (currentTopic && history.length > 6) {
      relevantOlder = await this.searchConversations(
        leadId,
        currentTopic,
        3
      );
      // Remove duplicates with recent
      const recentIds = new Set(recent.map((m) => m.id));
      relevantOlder = relevantOlder.filter((m) => !recentIds.has(m.id));
    }

    const parts: string[] = [];

    if (relevantOlder.length > 0) {
      parts.push("=== RELEVANT PRIOR CONTEXT ===");
      for (const msg of relevantOlder) {
        parts.push(
          `[${msg.direction === "outbound" ? "Us" : "Lead"}] (${msg.channel}, ${msg.timestamp.toLocaleDateString()}): ${msg.content}`
        );
      }
      parts.push("");
    }

    parts.push("=== RECENT CONVERSATION ===");
    for (const msg of recent) {
      parts.push(
        `[${msg.direction === "outbound" ? "Us" : "Lead"}] (${msg.channel}, ${msg.timestamp.toLocaleDateString()}): ${msg.content}`
      );
    }

    return parts.join("\n");
  }

  /**
   * Get summary statistics for a lead's conversation.
   */
  async getStats(leadId: string): Promise<{
    totalMessages: number;
    outbound: number;
    inbound: number;
    channels: Channel[];
    firstContact: Date | null;
    lastContact: Date | null;
  }> {
    const history = await this.getHistory(leadId);

    const channels = [...new Set(history.map((m) => m.channel))];

    return {
      totalMessages: history.length,
      outbound: history.filter((m) => m.direction === "outbound").length,
      inbound: history.filter((m) => m.direction === "inbound").length,
      channels,
      firstContact: history.length > 0 ? history[0].timestamp : null,
      lastContact: history.length > 0 ? history[history.length - 1].timestamp : null,
    };
  }

  /**
   * Save the full lead state to Supabase.
   */
  async saveLead(lead: Lead): Promise<void> {
    const { error } = await this.supabase.from("leads").upsert(
      {
        id: lead.id,
        status: lead.status,
        score: lead.score,
        source: lead.source,
        first_name: lead.firstName,
        last_name: lead.lastName,
        email: lead.email,
        email_verified: lead.emailVerified,
        phone: lead.phone,
        linkedin_url: lead.linkedInUrl,
        instagram_handle: lead.instagramHandle,
        title: lead.title,
        department: lead.department,
        seniority: lead.seniority,
        company: lead.company,
        research: lead.research,
        profile: lead.profile,
        enrichment: lead.enrichment,
        sequence_state: lead.sequenceState,
        sentiment: lead.sentiment,
        tags: lead.tags,
        notes: lead.notes,
        icp_match_score: lead.icpMatchScore,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "id" }
    );

    if (error) {
      logger.error("Failed to save lead", { leadId: lead.id, error });
      throw error;
    }
  }

  /**
   * Load a lead from Supabase.
   */
  async loadLead(leadId: string): Promise<Lead | null> {
    const { data, error } = await this.supabase
      .from("leads")
      .select("*")
      .eq("id", leadId)
      .single();

    if (error || !data) return null;

    return {
      id: data.id,
      status: data.status,
      score: data.score,
      source: data.source,
      createdAt: new Date(data.created_at),
      updatedAt: new Date(data.updated_at),
      firstName: data.first_name,
      lastName: data.last_name,
      fullName: `${data.first_name} ${data.last_name}`,
      email: data.email,
      emailVerified: data.email_verified,
      phone: data.phone,
      linkedInUrl: data.linkedin_url,
      instagramHandle: data.instagram_handle,
      title: data.title,
      department: data.department,
      seniority: data.seniority,
      company: data.company,
      research: data.research,
      profile: data.profile,
      enrichment: data.enrichment,
      sequenceState: data.sequence_state,
      conversationHistory: [],
      sentiment: data.sentiment,
      tags: data.tags ?? [],
      notes: data.notes ?? [],
      icpMatchScore: data.icp_match_score ?? 0,
    };
  }
}
