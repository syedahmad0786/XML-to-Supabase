import axios from "axios";
import { config } from "../../config/index.js";
import type { Lead, SequenceStep } from "../../types/index.js";
import { createLogger } from "../../utils/logger.js";

const logger = createLogger("channel:linkedin");

interface LinkedInSendResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * LinkedIn channel adapter.
 *
 * In production, this integrates with either:
 * 1. LinkedIn's official API (limited to connection requests and InMail)
 * 2. A third-party automation tool (e.g., Phantombuster, Dripify, Expandi)
 * 3. Direct browser automation via Puppeteer/Playwright (highest risk of ban)
 *
 * This implementation uses a webhook-based approach compatible with most
 * LinkedIn automation tools that accept incoming API calls.
 */
export class LinkedInChannel {
  private automationEndpoint: string;

  constructor(automationEndpoint?: string) {
    this.automationEndpoint =
      automationEndpoint ?? process.env.LINKEDIN_AUTOMATION_ENDPOINT ?? "";
  }

  /**
   * Send a connection request with a personalized note.
   * LinkedIn limits: 300 characters for the note, ~100 requests/week.
   */
  async sendConnectionRequest(
    lead: Lead,
    note: string
  ): Promise<LinkedInSendResult> {
    if (!lead.linkedInUrl) {
      return { success: false, error: "No LinkedIn URL for this lead" };
    }

    if (note.length > 300) {
      logger.warn(`Connection note exceeds 300 chars, truncating`, {
        leadId: lead.id,
        original: note.length,
      });
      note = note.slice(0, 297) + "...";
    }

    try {
      const response = await axios.post(
        `${this.automationEndpoint}/connect`,
        {
          profileUrl: lead.linkedInUrl,
          note,
          leadId: lead.id,
        },
        { timeout: 30000 }
      );

      logger.info(`Connection request sent to ${lead.fullName}`, {
        leadId: lead.id,
      });

      return {
        success: true,
        messageId: response.data.id,
      };
    } catch (error) {
      logger.error(`Failed to send connection request`, {
        leadId: lead.id,
        error,
      });
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Send a direct message to a connected lead.
   */
  async sendMessage(lead: Lead, message: string): Promise<LinkedInSendResult> {
    if (!lead.linkedInUrl) {
      return { success: false, error: "No LinkedIn URL for this lead" };
    }

    try {
      const response = await axios.post(
        `${this.automationEndpoint}/message`,
        {
          profileUrl: lead.linkedInUrl,
          message,
          leadId: lead.id,
        },
        { timeout: 30000 }
      );

      logger.info(`Message sent to ${lead.fullName} on LinkedIn`, {
        leadId: lead.id,
        charCount: message.length,
      });

      return {
        success: true,
        messageId: response.data.id,
      };
    } catch (error) {
      logger.error(`Failed to send LinkedIn message`, {
        leadId: lead.id,
        error,
      });
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Execute a step in the outreach sequence on LinkedIn.
   */
  async executeStep(
    lead: Lead,
    step: SequenceStep
  ): Promise<LinkedInSendResult> {
    switch (step.type) {
      case "connection_request":
        return this.sendConnectionRequest(lead, step.content);
      case "message":
      case "follow_up":
      case "breakup":
        return this.sendMessage(lead, step.content);
      default:
        return { success: false, error: `Unsupported step type: ${step.type}` };
    }
  }

  /**
   * Check if a connection request was accepted.
   */
  async checkConnectionStatus(
    lead: Lead
  ): Promise<"pending" | "accepted" | "unknown"> {
    if (!lead.linkedInUrl) return "unknown";

    try {
      const response = await axios.get(
        `${this.automationEndpoint}/connection-status`,
        {
          params: { profileUrl: lead.linkedInUrl },
          timeout: 10000,
        }
      );

      return response.data.status ?? "unknown";
    } catch {
      return "unknown";
    }
  }
}
