import nodemailer from "nodemailer";
import type { Transporter } from "nodemailer";
import { config } from "../../config/index.js";
import type { Lead, SequenceStep } from "../../types/index.js";
import { createLogger } from "../../utils/logger.js";

const logger = createLogger("channel:email");

interface EmailSendResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * Email channel adapter using SMTP.
 *
 * For production at scale, consider:
 * - SendGrid, Mailgun, or Amazon SES for deliverability
 * - Custom tracking domain for open/click tracking
 * - Warmup sequence for new sending domains
 * - SPF, DKIM, DMARC configuration
 */
export class EmailChannel {
  private transporter: Transporter | null;
  private configured: boolean;

  constructor() {
    this.configured = !!(config.email.smtpUser && config.email.smtpPassword && config.email.fromAddress);

    if (this.configured) {
      this.transporter = nodemailer.createTransport({
        host: config.email.smtpHost,
        port: config.email.smtpPort,
        secure: config.email.smtpPort === 465,
        auth: {
          user: config.email.smtpUser,
          pass: config.email.smtpPassword,
        },
      });
    } else {
      this.transporter = null;
      logger.warn(
        "SMTP not configured (SMTP_USER, SMTP_PASSWORD, or EMAIL_FROM_ADDRESS missing). " +
        "Email steps will be logged but not sent."
      );
    }
  }

  /**
   * Send a personalized email. Parses subject line from content if formatted
   * as "Subject: ...\n\n[body]"
   */
  async sendEmail(
    lead: Lead,
    content: string,
    threadId?: string
  ): Promise<EmailSendResult> {
    const email = lead.enrichment?.emails?.find((e) => e.verified)?.value ?? lead.email;

    if (!email) {
      return { success: false, error: "No verified email for this lead" };
    }

    if (!this.configured || !this.transporter) {
      const { subject } = this.parseContent(content, lead);
      logger.info(`[DRY RUN] Email to ${lead.fullName} <${email}>: ${subject}`);
      return { success: true, messageId: `dry-run-${Date.now()}` };
    }

    const { subject, body } = this.parseContent(content, lead);

    try {
      const mailOptions: nodemailer.SendMailOptions = {
        from: `"${config.email.fromName}" <${config.email.fromAddress}>`,
        to: email,
        subject,
        text: body,
        html: this.textToHtml(body),
        headers: {},
      };

      // Thread emails together using In-Reply-To
      if (threadId) {
        mailOptions.headers = {
          "In-Reply-To": threadId,
          References: threadId,
        };
      }

      const result = await this.transporter.sendMail(mailOptions);

      logger.info(`Email sent to ${lead.fullName} at ${email}`, {
        leadId: lead.id,
        messageId: result.messageId,
        subject,
      });

      return {
        success: true,
        messageId: result.messageId,
      };
    } catch (error) {
      logger.error(`Failed to send email to ${lead.fullName}`, {
        leadId: lead.id,
        email,
        error,
      });
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Execute a step in the outreach sequence via email.
   */
  async executeStep(
    lead: Lead,
    step: SequenceStep,
    threadId?: string
  ): Promise<EmailSendResult> {
    return this.sendEmail(lead, step.content, threadId);
  }

  /**
   * Verify SMTP connection is working.
   */
  async verifyConnection(): Promise<boolean> {
    try {
      await this.transporter.verify();
      logger.info("SMTP connection verified");
      return true;
    } catch (error) {
      logger.error("SMTP connection failed", { error });
      return false;
    }
  }

  private parseContent(
    content: string,
    lead: Lead
  ): { subject: string; body: string } {
    const subjectMatch = content.match(/^Subject:\s*(.+?)(?:\n\n|\r\n\r\n)/);
    if (subjectMatch) {
      return {
        subject: subjectMatch[1].trim(),
        body: content.slice(subjectMatch[0].length).trim(),
      };
    }

    // Fallback subject
    return {
      subject: `Quick question, ${lead.firstName}`,
      body: content.trim(),
    };
  }

  private textToHtml(text: string): string {
    return text
      .split("\n\n")
      .map((para) => `<p>${para.replace(/\n/g, "<br>")}</p>`)
      .join("");
  }
}
