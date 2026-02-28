import axios from "axios";
import { config } from "../config/index.js";
import type { ICP, Lead, CompanyInfo } from "../types/index.js";
import { v4 as uuid } from "uuid";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("lead-sourcer");

interface ApolloSearchParams {
  person_titles: string[];
  person_seniorities: string[];
  organization_num_employees_ranges: string[];
  organization_industry_tag_ids?: string[];
  person_locations?: string[];
  revenue_range?: { min: number; max: number };
  per_page: number;
  page: number;
}

interface ApolloPersonResult {
  id: string;
  first_name: string;
  last_name: string;
  name: string;
  title: string;
  email: string;
  email_status: string;
  linkedin_url: string;
  organization: {
    name: string;
    website_url: string;
    industry: string;
    estimated_num_employees: number;
    annual_revenue: number;
    founded_year: number;
    technologies: string[];
    short_description: string;
  };
  seniority: string;
  departments: string[];
  phone_numbers: Array<{ raw_number: string; type: string }>;
}

export class LeadSourcer {
  /**
   * Search Apollo.io for leads matching the ICP.
   * Translates ICP criteria into Apollo's search filters.
   */
  async searchApollo(icp: ICP, page = 1, perPage = 25): Promise<Lead[]> {
    if (!config.leadSourcing.apolloApiKey) {
      throw new Error("Apollo API key not configured");
    }

    const sizeRange = this.toApolloSizeRange(icp.demographics.companySizeRange);
    const params: ApolloSearchParams = {
      person_titles: icp.decisionMaker.titles,
      person_seniorities: icp.decisionMaker.seniorityLevels.map((s) =>
        s.toLowerCase().replace("-", "_")
      ),
      organization_num_employees_ranges: [sizeRange],
      person_locations: icp.demographics.geographies,
      per_page: perPage,
      page,
    };

    if (icp.demographics.revenueRange) {
      params.revenue_range = {
        min: icp.demographics.revenueRange[0],
        max: icp.demographics.revenueRange[1],
      };
    }

    try {
      const response = await axios.post(
        "https://api.apollo.io/v1/mixed_people/search",
        params,
        {
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": config.leadSourcing.apolloApiKey,
          },
        }
      );

      const people: ApolloPersonResult[] = response.data.people || [];
      logger.info(`Apollo returned ${people.length} results for page ${page}`);

      return people
        .filter((person) => this.passesDisqualifiers(person, icp))
        .map((person) => this.apolloToLead(person));
    } catch (error) {
      logger.error("Apollo search failed", { error });
      throw error;
    }
  }

  /**
   * Search Clay.co tables for enriched lead data.
   * Clay acts as a data enrichment & sourcing layer.
   */
  async searchClay(icp: ICP, tableId: string): Promise<Lead[]> {
    if (!config.leadSourcing.clayApiKey) {
      throw new Error("Clay API key not configured");
    }

    try {
      const response = await axios.get(
        `https://api.clay.com/v1/tables/${tableId}/rows`,
        {
          headers: {
            Authorization: `Bearer ${config.leadSourcing.clayApiKey}`,
            "Content-Type": "application/json",
          },
          params: {
            limit: 100,
            filters: JSON.stringify({
              industry: icp.demographics.industries,
              employee_count_min: icp.demographics.companySizeRange[0],
              employee_count_max: icp.demographics.companySizeRange[1],
            }),
          },
        }
      );

      const rows = response.data.rows || [];
      logger.info(`Clay returned ${rows.length} rows from table ${tableId}`);

      return rows.map((row: Record<string, string>) => this.clayRowToLead(row));
    } catch (error) {
      logger.error("Clay search failed", { error });
      throw error;
    }
  }

  /**
   * Build a LinkedIn Sales Navigator search URL from ICP criteria.
   * Returns the URL for manual or automated extraction.
   */
  buildLinkedInSearchUrl(icp: ICP): string {
    const params = new URLSearchParams();

    if (icp.decisionMaker.titles.length > 0) {
      params.set("titleIncluded", icp.decisionMaker.titles.join(","));
    }
    if (icp.demographics.industries.length > 0) {
      params.set("industryIncluded", icp.demographics.industries.join(","));
    }
    if (icp.demographics.companySizeRange) {
      params.set("companySize", icp.demographics.companySizeRange.join("-"));
    }
    if (icp.demographics.geographies.length > 0) {
      params.set("geoIncluded", icp.demographics.geographies.join(","));
    }

    return `https://www.linkedin.com/sales/search/people?${params.toString()}`;
  }

  /**
   * Source leads from multiple channels in parallel and deduplicate.
   */
  async sourceFromAllChannels(
    icp: ICP,
    options: { apolloPages?: number; clayTableId?: string } = {}
  ): Promise<Lead[]> {
    const promises: Promise<Lead[]>[] = [];

    if (config.leadSourcing.apolloApiKey) {
      const pages = options.apolloPages ?? 2;
      for (let page = 1; page <= pages; page++) {
        promises.push(this.searchApollo(icp, page));
      }
    }

    if (config.leadSourcing.clayApiKey && options.clayTableId) {
      promises.push(this.searchClay(icp, options.clayTableId));
    }

    const results = await Promise.allSettled(promises);
    const allLeads: Lead[] = [];

    for (const result of results) {
      if (result.status === "fulfilled") {
        allLeads.push(...result.value);
      } else {
        logger.warn("Lead source channel failed", { reason: result.reason });
      }
    }

    return this.deduplicateLeads(allLeads);
  }

  private passesDisqualifiers(person: ApolloPersonResult, icp: ICP): boolean {
    const companyName = person.organization?.name?.toLowerCase() ?? "";
    for (const disqualifier of icp.qualifiers.disqualifiers) {
      if (companyName.includes(disqualifier.toLowerCase())) return false;
    }
    return true;
  }

  private apolloToLead(person: ApolloPersonResult): Lead {
    const org = person.organization;
    return {
      id: uuid(),
      status: "sourced",
      score: 0,
      source: "apollo",
      createdAt: new Date(),
      updatedAt: new Date(),
      firstName: person.first_name,
      lastName: person.last_name,
      fullName: person.name,
      email: person.email,
      emailVerified: person.email_status === "verified",
      phone: person.phone_numbers?.[0]?.raw_number,
      linkedInUrl: person.linkedin_url,
      title: person.title,
      department: person.departments?.[0] ?? "",
      seniority: person.seniority,
      company: {
        name: org?.name ?? "",
        domain: org?.website_url ?? "",
        industry: org?.industry ?? "",
        size: org?.estimated_num_employees ?? 0,
        revenue: org?.annual_revenue,
        founded: org?.founded_year,
        techStack: org?.technologies ?? [],
        recentNews: [],
        painPoints: [],
        competitors: [],
      },
      conversationHistory: [],
      tags: [],
      notes: [],
      icpMatchScore: 0,
    };
  }

  private clayRowToLead(row: Record<string, string>): Lead {
    return {
      id: uuid(),
      status: "sourced",
      score: 0,
      source: "clay",
      createdAt: new Date(),
      updatedAt: new Date(),
      firstName: row.first_name ?? "",
      lastName: row.last_name ?? "",
      fullName: `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim(),
      email: row.email,
      emailVerified: row.email_verified === "true",
      phone: row.phone,
      linkedInUrl: row.linkedin_url,
      title: row.title ?? "",
      department: row.department ?? "",
      seniority: row.seniority ?? "",
      company: {
        name: row.company_name ?? "",
        domain: row.company_domain ?? "",
        industry: row.industry ?? "",
        size: parseInt(row.employee_count ?? "0"),
        revenue: row.revenue ? parseInt(row.revenue) : undefined,
        techStack: row.technologies ? row.technologies.split(",") : [],
        recentNews: [],
        painPoints: [],
        competitors: [],
      },
      conversationHistory: [],
      tags: [],
      notes: [],
      icpMatchScore: 0,
    };
  }

  private deduplicateLeads(leads: Lead[]): Lead[] {
    const seen = new Map<string, Lead>();
    for (const lead of leads) {
      const key =
        lead.email?.toLowerCase() ??
        lead.linkedInUrl?.toLowerCase() ??
        `${lead.firstName}-${lead.lastName}-${lead.company.name}`.toLowerCase();

      if (!seen.has(key)) {
        seen.set(key, lead);
      }
    }
    return Array.from(seen.values());
  }

  private toApolloSizeRange(range: [number, number]): string {
    return `${range[0]},${range[1]}`;
  }
}
