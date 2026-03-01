import { Pinecone } from "@pinecone-database/pinecone";
import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/index.js";
import { createLogger } from "../utils/logger.js";

const logger = createLogger("vector-store");

interface VectorDocument {
  id: string;
  content: string;
  metadata: Record<string, string | number | boolean>;
}

interface SearchResult {
  id: string;
  content: string;
  score: number;
  metadata: Record<string, string | number | boolean>;
}

/**
 * Vector store for semantic search over knowledge base docs and conversation history.
 * Uses Pinecone as the vector DB and Anthropic/OpenAI for embeddings.
 */
export class VectorStore {
  private pinecone: Pinecone;
  private indexName: string;
  private anthropic: Anthropic;

  constructor() {
    this.pinecone = new Pinecone({
      apiKey: config.vectorStore.pineconeApiKey ?? "",
    });
    this.indexName = config.vectorStore.pineconeIndex;
    this.anthropic = new Anthropic({ apiKey: config.llm.anthropicApiKey });
  }

  /**
   * Upsert documents into the vector store.
   * Generates embeddings and stores with metadata for filtering.
   */
  async upsert(documents: VectorDocument[], namespace = "default"): Promise<void> {
    const index = this.pinecone.index(this.indexName);

    const batchSize = 100;
    for (let i = 0; i < documents.length; i += batchSize) {
      const batch = documents.slice(i, i + batchSize);
      const embeddings = await this.generateEmbeddings(
        batch.map((d) => d.content)
      );

      const vectors = batch.map((doc, j) => ({
        id: doc.id,
        values: embeddings[j],
        metadata: {
          ...doc.metadata,
          content: doc.content.slice(0, 40000), // Pinecone metadata limit
        },
      }));

      await index.namespace(namespace).upsert(vectors);
    }

    logger.info(`Upserted ${documents.length} documents to namespace "${namespace}"`);
  }

  /**
   * Semantic search over the vector store.
   * Returns the top-k most relevant documents.
   */
  async search(
    query: string,
    options: {
      namespace?: string;
      topK?: number;
      filter?: Record<string, string | number | boolean>;
    } = {}
  ): Promise<SearchResult[]> {
    const { namespace = "default", topK = 5, filter } = options;
    const index = this.pinecone.index(this.indexName);

    const [queryEmbedding] = await this.generateEmbeddings([query]);

    const results = await index.namespace(namespace).query({
      vector: queryEmbedding,
      topK,
      includeMetadata: true,
      filter,
    });

    return (results.matches ?? []).map((match) => ({
      id: match.id,
      content: (match.metadata?.content as string) ?? "",
      score: match.score ?? 0,
      metadata: (match.metadata as Record<string, string | number | boolean>) ?? {},
    }));
  }

  /**
   * Delete documents by ID or filter.
   */
  async delete(ids: string[], namespace = "default"): Promise<void> {
    const index = this.pinecone.index(this.indexName);
    await index.namespace(namespace).deleteMany(ids);
    logger.info(`Deleted ${ids.length} vectors from namespace "${namespace}"`);
  }

  /**
   * Generate embeddings for vector search.
   * Prefers OpenAI's text-embedding-3-small (best quality/price for search).
   * Falls back to Anthropic LLM-based feature extraction if OpenAI unavailable.
   */
  private async generateEmbeddings(texts: string[]): Promise<number[][]> {
    if (config.llm.openaiApiKey) {
      return this.generateOpenAIEmbeddings(texts);
    }
    return this.generateAnthropicEmbeddings(texts);
  }

  private async generateOpenAIEmbeddings(texts: string[]): Promise<number[][]> {
    const { default: OpenAI } = await import("openai");
    const openai = new OpenAI({ apiKey: config.llm.openaiApiKey });

    const batchSize = 100;
    const allEmbeddings: number[][] = [];

    for (let i = 0; i < texts.length; i += batchSize) {
      const batch = texts.slice(i, i + batchSize);
      const response = await openai.embeddings.create({
        model: "text-embedding-3-small",
        input: batch,
        dimensions: 1536,
      });
      allEmbeddings.push(...response.data.map((d) => d.embedding));
    }

    return allEmbeddings;
  }

  /**
   * Generate embeddings via Anthropic by asking the LLM to produce
   * a fixed-dimension numerical feature vector. Falls back to
   * n-gram hashing if the LLM output is malformed.
   */
  private async generateAnthropicEmbeddings(texts: string[]): Promise<number[][]> {
    const embeddings: number[][] = [];
    const dimensions = 256;

    for (const text of texts) {
      try {
        const response = await this.anthropic.messages.create({
          model: config.llm.fastModel,
          max_tokens: 2048,
          messages: [
            {
              role: "user",
              content: `Produce a ${dimensions}-dimensional numerical feature vector capturing the semantic meaning of this text. Each value between -1 and 1. Return ONLY a JSON array of ${dimensions} numbers.\n\nText: "${text.slice(0, 2000)}"`,
            },
          ],
        });

        const content = response.content[0];
        if (content.type === "text") {
          const vector = JSON.parse(content.text) as number[];
          if (Array.isArray(vector) && vector.length === dimensions) {
            const magnitude = Math.sqrt(vector.reduce((sum, v) => sum + v * v, 0));
            embeddings.push(vector.map((v) => v / (magnitude || 1)));
            continue;
          }
        }
      } catch {
        logger.warn("Anthropic embedding extraction failed, using n-gram fallback");
      }

      embeddings.push(this.ngramEmbed(text, dimensions));
    }

    return embeddings;
  }

  /**
   * Deterministic n-gram hashing embedding as last-resort fallback.
   * Uses unigram + bigram + trigram character hashing for basic
   * semantic capture when no embedding API is available.
   */
  private ngramEmbed(text: string, dimensions: number): number[] {
    const vector = new Array(dimensions).fill(0);
    const lower = text.toLowerCase();

    for (let n = 1; n <= 3; n++) {
      for (let i = 0; i <= lower.length - n; i++) {
        const gram = lower.slice(i, i + n);
        let hash = 0;
        for (let j = 0; j < gram.length; j++) {
          hash = ((hash << 5) - hash + gram.charCodeAt(j)) | 0;
        }
        vector[Math.abs(hash) % dimensions] += 1.0 / (n * lower.length);
      }
    }

    const magnitude = Math.sqrt(vector.reduce((sum, v) => sum + v * v, 0));
    return vector.map((v) => v / (magnitude || 1));
  }
}
