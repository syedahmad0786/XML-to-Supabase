import axios from "axios";
import { config } from "../config/index.js";
import type { Lead, ContactEnrichment, VerifiedContact } from "../types/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("contact-enricher");

export class ContactEnricher {
  /**
   * Enrich a lead with verified contact information from multiple sources.
   * Deduplicates and ranks by confidence.
   */
  async enrich(lead: Lead): Promise<ContactEnrichment> {
    logger.info(`Enriching contact data for ${lead.fullName}`);

    const [apolloEmails, apolloPhones] = await Promise.allSettled([
      this.findEmailsViaApollo(lead),
      this.findPhonesViaApollo(lead),
    ]);

    const emails: VerifiedContact[] = [];
    const phones: VerifiedContact[] = [];

    // Already-known email
    if (lead.email) {
      emails.push({
        value: lead.email,
        verified: lead.emailVerified,
        confidence: lead.emailVerified ? 0.95 : 0.6,
        source: lead.source,
      });
    }

    // Apollo results
    if (apolloEmails.status === "fulfilled") {
      emails.push(...apolloEmails.value);
    }
    if (apolloPhones.status === "fulfilled") {
      phones.push(...apolloPhones.value);
    }

    // Already-known phone
    if (lead.phone) {
      phones.push({
        value: lead.phone,
        verified: false,
        confidence: 0.5,
        source: lead.source,
      });
    }

    // Deduplicate and sort by confidence
    const uniqueEmails = this.deduplicateContacts(emails);
    const uniquePhones = this.deduplicateContacts(phones);

    const socialProfiles: Record<string, string> = {};
    if (lead.linkedInUrl) socialProfiles.linkedin = lead.linkedInUrl;
    if (lead.instagramHandle) socialProfiles.instagram = lead.instagramHandle;

    logger.info(`Enrichment complete for ${lead.fullName}`, {
      emails: uniqueEmails.length,
      phones: uniquePhones.length,
      socials: Object.keys(socialProfiles).length,
    });

    return {
      emails: uniqueEmails,
      phones: uniquePhones,
      socialProfiles,
      enrichedAt: new Date(),
    };
  }

  /**
   * Verify a specific email address using Apollo's email verification endpoint.
   */
  async verifyEmail(email: string): Promise<{ valid: boolean; confidence: number }> {
    if (!config.leadSourcing.apolloApiKey) {
      return { valid: false, confidence: 0 };
    }

    try {
      const response = await axios.post(
        "https://api.apollo.io/v1/people/match",
        { email },
        {
          headers: {
            "Content-Type": "application/json",
            "X-Api-Key": config.leadSourcing.apolloApiKey,
          },
        }
      );

      const person = response.data.person;
      if (person?.email_status === "verified") {
        return { valid: true, confidence: 0.95 };
      }
      return { valid: false, confidence: 0.3 };
    } catch {
      return { valid: false, confidence: 0 };
    }
  }

  private async findEmailsViaApollo(lead: Lead): Promise<VerifiedContact[]> {
    if (!config.leadSourcing.apolloApiKey) return [];

    try {
      const response = await axios.post(
        "https://api.apollo.io/v1/people/match",
        {
          first_name: lead.firstName,
          last_name: lead.lastName,
          organization_name: lead.company.name,
          domain: lead.company.domain,
        },
        {
          headers: {
            "Content-Type": "application/json",
            "X-Api-Key": config.leadSourcing.apolloApiKey,
          },
        }
      );

      const person = response.data.person;
      if (!person?.email) return [];

      return [
        {
          value: person.email,
          verified: person.email_status === "verified",
          confidence: person.email_status === "verified" ? 0.95 : 0.7,
          source: "apollo",
        },
      ];
    } catch (error) {
      logger.warn("Apollo email lookup failed", { error });
      return [];
    }
  }

  private async findPhonesViaApollo(lead: Lead): Promise<VerifiedContact[]> {
    if (!config.leadSourcing.apolloApiKey) return [];

    try {
      const response = await axios.post(
        "https://api.apollo.io/v1/people/match",
        {
          first_name: lead.firstName,
          last_name: lead.lastName,
          organization_name: lead.company.name,
        },
        {
          headers: {
            "Content-Type": "application/json",
            "X-Api-Key": config.leadSourcing.apolloApiKey,
          },
        }
      );

      const person = response.data.person;
      if (!person?.phone_numbers?.length) return [];

      return person.phone_numbers.map(
        (p: { raw_number: string; type: string }) => ({
          value: p.raw_number,
          verified: false,
          confidence: 0.6,
          source: "apollo",
        })
      );
    } catch {
      return [];
    }
  }

  private deduplicateContacts(contacts: VerifiedContact[]): VerifiedContact[] {
    const seen = new Map<string, VerifiedContact>();
    for (const contact of contacts) {
      const key = contact.value.toLowerCase();
      const existing = seen.get(key);
      if (!existing || contact.confidence > existing.confidence) {
        seen.set(key, contact);
      }
    }
    return Array.from(seen.values()).sort((a, b) => b.confidence - a.confidence);
  }
}
