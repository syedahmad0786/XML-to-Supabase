import axios from "axios";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { config } from "../config/index.js";
import type { ApprovalRequest, Lead, Channel } from "../types/index.js";
import { v4 as uuid } from "uuid";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("hitl-gateway");

/**
 * Human-in-the-Loop approval gateway.
 *
 * Even the best AI can hallucinate. This module ensures that:
 * 1. First outreach messages are reviewed before sending
 * 2. High-value leads get human oversight
 * 3. Negative sentiment escalations reach a human immediately
 * 4. All approvals are logged for compliance
 *
 * Integrates with Slack/Discord for one-click approve/reject.
 */
export class ApprovalGateway {
  private supabase: SupabaseClient;

  constructor() {
    this.supabase = createClient(config.supabase.url, config.supabase.serviceKey);
  }

  /**
   * Submit an outreach message for human approval.
   * Sends a notification to Slack/Discord and waits for response.
   */
  async requestApproval(params: {
    lead: Lead;
    type: ApprovalRequest["type"];
    channel: Channel;
    content: string;
    reason: string;
    researchSummary: string;
  }): Promise<ApprovalRequest> {
    const request: ApprovalRequest = {
      id: uuid(),
      leadId: params.lead.id,
      type: params.type,
      lead: params.lead,
      proposedAction: {
        channel: params.channel,
        content: params.content,
        reason: params.reason,
      },
      researchSummary: params.researchSummary,
      status: "pending",
      submittedAt: new Date(),
    };

    // Store the request in Supabase
    await this.supabase.from("approval_requests").insert({
      id: request.id,
      lead_id: request.leadId,
      type: request.type,
      proposed_channel: request.proposedAction.channel,
      proposed_content: request.proposedAction.content,
      reason: request.proposedAction.reason,
      research_summary: request.researchSummary,
      status: "pending",
      submitted_at: request.submittedAt.toISOString(),
    });

    // Send notification to Slack or Discord
    await this.sendNotification(request);

    logger.info(`Approval requested for ${params.lead.fullName}`, {
      requestId: request.id,
      type: request.type,
    });

    return request;
  }

  /**
   * Check if an approval request has been resolved.
   * Called by the pipeline to poll for approval status.
   */
  async checkApproval(
    requestId: string
  ): Promise<ApprovalRequest["status"]> {
    const { data, error } = await this.supabase
      .from("approval_requests")
      .select("status, modified_content, resolved_by, resolved_at")
      .eq("id", requestId)
      .single();

    if (error || !data) return "pending";
    return data.status;
  }

  /**
   * Wait for approval with timeout.
   * Polls Supabase at intervals until approved, rejected, or timed out.
   */
  async waitForApproval(
    requestId: string,
    timeoutMs = 24 * 60 * 60 * 1000 // 24 hours
  ): Promise<{
    approved: boolean;
    modifiedContent?: string;
  }> {
    const startTime = Date.now();
    const pollInterval = 30_000; // 30 seconds

    while (Date.now() - startTime < timeoutMs) {
      const { data } = await this.supabase
        .from("approval_requests")
        .select("status, modified_content")
        .eq("id", requestId)
        .single();

      if (data?.status === "approved") {
        return { approved: true };
      }
      if (data?.status === "modified") {
        return { approved: true, modifiedContent: data.modified_content };
      }
      if (data?.status === "rejected") {
        return { approved: false };
      }

      await new Promise((r) => setTimeout(r, pollInterval));
    }

    logger.warn(`Approval request ${requestId} timed out`);
    return { approved: false };
  }

  /**
   * Resolve an approval request (called by webhook from Slack/Discord).
   */
  async resolve(
    requestId: string,
    status: "approved" | "rejected" | "modified",
    resolvedBy: string,
    modifiedContent?: string
  ): Promise<void> {
    await this.supabase
      .from("approval_requests")
      .update({
        status,
        resolved_by: resolvedBy,
        resolved_at: new Date().toISOString(),
        modified_content: modifiedContent,
      })
      .eq("id", requestId);

    logger.info(`Approval ${requestId} resolved: ${status}`, { resolvedBy });
  }

  /**
   * Determine if HITL approval is required for a given action.
   */
  shouldRequireApproval(lead: Lead, isFirstMessage: boolean): boolean {
    // Always require approval for first outreach if configured
    if (isFirstMessage && config.hitl.requiredForFirstMessage) {
      return true;
    }

    // High-value leads (score 9+)
    if (lead.score >= 9) {
      return true;
    }

    // Negative sentiment detected
    if (lead.sentiment?.shouldEscalate) {
      return true;
    }

    return false;
  }

  private async sendNotification(request: ApprovalRequest): Promise<void> {
    const message = this.formatSlackMessage(request);

    // Try Slack first
    if (config.hitl.slackWebhookUrl) {
      try {
        await axios.post(config.hitl.slackWebhookUrl, message, {
          timeout: 10000,
        });
        logger.info("Slack notification sent");
        return;
      } catch (error) {
        logger.warn("Slack notification failed, trying Discord", { error });
      }
    }

    // Fallback to Discord
    if (config.hitl.discordWebhookUrl) {
      try {
        await axios.post(
          config.hitl.discordWebhookUrl,
          { content: this.formatDiscordMessage(request) },
          { timeout: 10000 }
        );
        logger.info("Discord notification sent");
      } catch (error) {
        logger.error("Both Slack and Discord notifications failed", { error });
      }
    }
  }

  private formatSlackMessage(request: ApprovalRequest): Record<string, unknown> {
    const lead = request.lead;
    const emoji =
      request.type === "negative_sentiment"
        ? ":warning:"
        : request.type === "high_value_lead"
          ? ":star:"
          : ":envelope:";

    return {
      channel: config.hitl.slackApprovalChannel,
      blocks: [
        {
          type: "header",
          text: {
            type: "plain_text",
            text: `${emoji} Approval Required: ${request.type.replace(/_/g, " ")}`,
          },
        },
        {
          type: "section",
          fields: [
            { type: "mrkdwn", text: `*Lead:* ${lead.fullName}` },
            { type: "mrkdwn", text: `*Title:* ${lead.title}` },
            { type: "mrkdwn", text: `*Company:* ${lead.company.name}` },
            { type: "mrkdwn", text: `*Score:* ${lead.score}/10` },
            { type: "mrkdwn", text: `*Channel:* ${request.proposedAction.channel}` },
          ],
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*Proposed message:*\n\`\`\`${request.proposedAction.content}\`\`\``,
          },
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*Research summary:*\n${request.researchSummary.slice(0, 500)}`,
          },
        },
        {
          type: "actions",
          elements: [
            {
              type: "button",
              text: { type: "plain_text", text: "Approve" },
              style: "primary",
              action_id: `approve_${request.id}`,
            },
            {
              type: "button",
              text: { type: "plain_text", text: "Reject" },
              style: "danger",
              action_id: `reject_${request.id}`,
            },
            {
              type: "button",
              text: { type: "plain_text", text: "Edit & Approve" },
              action_id: `edit_${request.id}`,
            },
          ],
        },
      ],
    };
  }

  private formatDiscordMessage(request: ApprovalRequest): string {
    return [
      `**Approval Required: ${request.type.replace(/_/g, " ")}**`,
      `Lead: ${request.lead.fullName} (${request.lead.title} at ${request.lead.company.name})`,
      `Score: ${request.lead.score}/10 | Channel: ${request.proposedAction.channel}`,
      ``,
      `**Proposed message:**`,
      `\`\`\`${request.proposedAction.content}\`\`\``,
      ``,
      `React with :white_check_mark: to approve or :x: to reject`,
    ].join("\n");
  }
}
