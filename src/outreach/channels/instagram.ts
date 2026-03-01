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
   * Check DM eligibility by attempting to verify the user exists via business discovery.
   * Instagram doesn't expose a direct "follows you" check, so we verify the user
   * is discoverable (public business/creator account) as a proxy for eligibility.
   */
  async checkFollowStatus(instagramHandle: string): Promise<boolean> {
    if (!this.accessToken || !this.accountId) {
      logger.warn("Instagram API not configured — cannot check follow status");
      return false;
    }

    try {
      const userId = await this.resolveUserId(instagramHandle);
      if (!userId) {
        logger.info(`@${instagramHandle} not discoverable via business_discovery — may not be eligible for DMs`);
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Resolve an Instagram handle to an Instagram-scoped user ID (IGSID)
   * using the Business Discovery API.
   */
  private async resolveUserId(handle: string): Promise<string | null> {
    // Strip @ prefix if present
    const cleanHandle = handle.startsWith("@") ? handle.slice(1) : handle;

    try {
      const response = await axios.get(
        `https://graph.instagram.com/v21.0/${this.accountId}`,
        {
          params: {
            fields: `business_discovery.fields(id,username){username:${cleanHandle}}`,
            access_token: this.accessToken,
          },
          timeout: 10000,
        }
      );

      const userId = response.data?.business_discovery?.id;
      if (!userId) {
        logger.warn(`Instagram user @${cleanHandle} not found via business_discovery`);
        return null;
      }

      return userId;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        const igError = error.response?.data?.error;

        if (status === 400 && igError?.code === 803) {
          logger.warn(`Instagram user @${cleanHandle} does not exist or is not a business/creator account`);
        } else if (status === 190) {
          logger.error("Instagram access token is invalid or expired");
        } else {
          logger.error(`Instagram API error resolving @${cleanHandle}`, {
            status,
            code: igError?.code,
            message: igError?.message,
          });
        }
      } else {
        logger.error(`Unexpected error resolving Instagram user @${cleanHandle}`, { error });
      }
      return null;
    }
  }
}
