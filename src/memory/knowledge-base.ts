import { VectorStore } from "./vector-store.js";
import type { BusinessDNA } from "../types/index.js";
import { v4 as uuid } from "uuid";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("knowledge-base");

const KB_NAMESPACE = "knowledge-base";

interface KBDocument {
  id: string;
  title: string;
  content: string;
  category: "product" | "case_study" | "faq" | "objection" | "pricing" | "technical";
  tags: string[];
  createdAt: Date;
}

/**
 * Knowledge base for storing company documentation, case studies, FAQs,
 * and objection-handling scripts. Used by the content generator to
 * answer technical questions and handle objections with real data.
 */
export class KnowledgeBase {
  private vectorStore: VectorStore;
  private documents: Map<string, KBDocument> = new Map();

  constructor() {
    this.vectorStore = new VectorStore();
  }

  /**
   * Ingest the BusinessDNA into the knowledge base.
   * Creates searchable documents from products, case studies, and objection handling.
   */
  async ingestBusinessDNA(dna: BusinessDNA): Promise<void> {
    const docs: KBDocument[] = [];

    // Products
    for (const product of dna.products) {
      docs.push({
        id: uuid(),
        title: product.name,
        content: `Product: ${product.name}\nDescription: ${product.description}\nPrice range: ${product.priceRange}\nIdeal for: ${product.idealFor.join(", ")}`,
        category: "product",
        tags: product.idealFor,
        createdAt: new Date(),
      });
    }

    // Case studies
    for (const cs of dna.pastSuccesses) {
      docs.push({
        id: uuid(),
        title: `Case Study: ${cs.client}`,
        content: `Client: ${cs.client} (${cs.industry})\nProblem: ${cs.problem}\nSolution: ${cs.solution}\nResult: ${cs.result}\nLTV: $${cs.ltv.toLocaleString()}`,
        category: "case_study",
        tags: [cs.industry],
        createdAt: new Date(),
      });
    }

    // Objection handling scripts
    for (const [objection, response] of Object.entries(dna.objectionHandling)) {
      docs.push({
        id: uuid(),
        title: `Objection: ${objection}`,
        content: `Objection: ${objection}\nRecommended response: ${response}`,
        category: "objection",
        tags: ["objection_handling"],
        createdAt: new Date(),
      });
    }

    // Value proposition
    docs.push({
      id: uuid(),
      title: "Value Proposition",
      content: `Company: ${dna.companyName}\nIndustry: ${dna.industry}\nValue Proposition: ${dna.valueProposition}\nCompetitive Advantages: ${dna.competitiveAdvantages.join(", ")}`,
      category: "product",
      tags: ["core"],
      createdAt: new Date(),
    });

    await this.addDocuments(docs);
    logger.info(`Ingested BusinessDNA: ${docs.length} documents indexed`);
  }

  /**
   * Add documents to the knowledge base.
   */
  async addDocuments(docs: KBDocument[]): Promise<void> {
    for (const doc of docs) {
      this.documents.set(doc.id, doc);
    }

    await this.vectorStore.upsert(
      docs.map((doc) => ({
        id: doc.id,
        content: doc.content,
        metadata: {
          title: doc.title,
          category: doc.category,
          tags: doc.tags.join(","),
        },
      })),
      KB_NAMESPACE
    );
  }

  /**
   * Query the knowledge base for relevant information.
   * Used when the agent needs to handle an objection or answer a technical question.
   */
  async query(
    question: string,
    options: { category?: KBDocument["category"]; topK?: number } = {}
  ): Promise<string> {
    const { category, topK = 3 } = options;

    const filter = category ? { category } : undefined;
    const results = await this.vectorStore.search(question, {
      namespace: KB_NAMESPACE,
      topK,
      filter,
    });

    if (results.length === 0) {
      return "No relevant information found in the knowledge base.";
    }

    return results
      .map(
        (r, i) =>
          `[${i + 1}] (relevance: ${(r.score * 100).toFixed(0)}%) ${r.content}`
      )
      .join("\n\n---\n\n");
  }

  /**
   * Find the best objection-handling response for a given objection.
   */
  async handleObjection(objection: string): Promise<string> {
    return this.query(objection, { category: "objection", topK: 2 });
  }

  /**
   * Find relevant case studies for a given industry or pain point.
   */
  async findCaseStudies(context: string): Promise<string> {
    return this.query(context, { category: "case_study", topK: 3 });
  }
}
