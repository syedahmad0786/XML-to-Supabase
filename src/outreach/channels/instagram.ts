import axios from "axios";
import { config } from "../../config/index.js";
import type { Lead, SequenceStep } from "../../types/index.js";
import { createLogger } from "../../utils/logger.js";

const logger = createLogger("channel:instagram");

interface InstagramSendResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * Instagram channel adapter using the Instagram Messaging API.
 *
 * Requirements:
 * - Business/Creator Instagram account
 * - Facebook App with Instagram Messaging permission
 * - User must have interacted with the business account first (24-hour window)
 *   OR you use the Instagram API's message request feature
 *
 * For cold outreach, this channel is best used as a supplementary touch
 * after LinkedIn/Email, not as the primary channel.
 */
export class InstagramChannel {
  private accessToken: string;
  private accountId: string;

  constructor() {
    this.accessToken = config.instagram.accessToken ?? "";
    this.accountId = config.instagram.businessAccountId ?? "";
  }

  /**
   * Send a direct message on Instagram.
   * Uses the Instagram Graph API Messaging endpoint.
   */
  async sendDM(lead: Lead, message: string): Promise<InstagramSendResult> {
    if (!lead.instagramHandle) {
      return { success: false, error: "No Instagram handle for this lead" };
    }

    if (!this.accessToken || !this.accountId) {
      return { success: false, error: "Instagram API not configured" };
    }

    if (message.length > 1000) {
      logger.warn(`Instagram DM exceeds 1000 chars, truncating`, {
        leadId: lead.id,
      });
      message = message.slice(0, 997) + "...";
    }

    try {
      // First, look up the user's Instagram-scoped ID (IGSID)
      const recipientId = await this.resolveUserId(lead.instagramHandle);
      if (!recipientId) {
        return {
          success: false,
          error: `Could not resolve Instagram ID for @${lead.instagramHandle}`,
        };
      }

      const response = await axios.post(
        `https://graph.instagram.com/v21.0/${this.accountId}/messages`,
        {
          recipient: { id: recipientId },
          message: { text: message },
        },
        {
          headers: {
            Authorization: `Bearer ${this.accessToken}`,
            "Content-Type": "application/json",
          },
          timeout: 15000,
        }
      );

      logger.info(`Instagram DM sent to @${lead.instagramHandle}`, {
        leadId: lead.id,
        messageId: response.data.message_id,
      });

      return {
        success: true,
        messageId: response.data.message_id,
      };
    } catch (error) {
      logger.error(`Failed to send Instagram DM`, {
        leadId: lead.id,
        handle: lead.instagramHandle,
        error,
      });
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Execute a step in the outreach sequence on Instagram.
   */
  async executeStep(
    lead: Lead,
    step: SequenceStep
  ): Promise<InstagramSendResult> {
    return this.sendDM(lead, step.content);
  }

  /**
   * Check if the lead follows the business account (needed for DM eligibility).
   */
  async checkFollowStatus(instagramHandle: string): Promise<boolean> {
    // Instagram API doesn't directly support this check publicly
    // In practice, use a proxy service or check DM eligibility
    logger.info(`Follow status check for @${instagramHandle} — not available via API`);
    return true;
  }

  private async resolveUserId(handle: string): Promise<string | null> {
    try {
      const response = await axios.get(
        `https://graph.instagram.com/v21.0/${this.accountId}`,
        {
          params: {
            fields: "business_discovery.fields(id,username)",
            access_token: this.accessToken,
          },
          timeout: 10000,
        }
      );
      return response.data?.business_discovery?.id ?? null;
    } catch {
      return null;
    }
  }
}
