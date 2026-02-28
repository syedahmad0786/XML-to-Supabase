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
   * Generate embeddings using a lightweight approach.
   * In production, use a dedicated embeddings model (e.g., text-embedding-3-small).
   *
   * Here we use a summarization-to-vector approach with the fast model
   * and a fixed-dimension output. For better results, integrate OpenAI's
   * embeddings API or Cohere's embed endpoint.
   */
  private async generateEmbeddings(texts: string[]): Promise<number[][]> {
    // Use OpenAI embeddings if available (better for vector search)
    if (config.llm.openaiApiKey) {
      return this.generateOpenAIEmbeddings(texts);
    }

    // Fallback: generate pseudo-embeddings via Anthropic summarization
    // This is a simplified approach — in production, always use a real embeddings model
    return this.generateFallbackEmbeddings(texts);
  }

  private async generateOpenAIEmbeddings(texts: string[]): Promise<number[][]> {
    const { default: OpenAI } = await import("openai");
    const openai = new OpenAI({ apiKey: config.llm.openaiApiKey });

    const response = await openai.embeddings.create({
      model: "text-embedding-3-small",
      input: texts,
      dimensions: 1536,
    });

    return response.data.map((d) => d.embedding);
  }

  private async generateFallbackEmbeddings(texts: string[]): Promise<number[][]> {
    // Simple hash-based embeddings as fallback — NOT suitable for production
    // This is a placeholder to make the system functional without OpenAI
    return texts.map((text) => {
      const hash = new Array(1536).fill(0);
      for (let i = 0; i < text.length; i++) {
        hash[i % 1536] += text.charCodeAt(i) / 1000;
      }
      // Normalize
      const magnitude = Math.sqrt(hash.reduce((sum, v) => sum + v * v, 0));
      return hash.map((v) => v / (magnitude || 1));
    });
  }
}
