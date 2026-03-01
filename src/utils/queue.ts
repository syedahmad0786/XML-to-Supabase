import Bull from "bull";
import { config } from "../config/index.js";
import { createLogger } from "./logger.js";

const logger = createLogger("queue");

export type JobType =
  | "enrich_and_research"
  | "start_outreach"
  | "advance_sequence"
  | "handle_reply";

interface JobPayload {
  enrich_and_research: { leadId: string };
  start_outreach: { leadId: string };
  advance_sequence: { leadId: string };
  handle_reply: { leadId: string; message: string; channel: string };
}

/**
 * Bull-based job queue for async pipeline operations.
 * Enables rate limiting, retries, and parallel processing of
 * long-running tasks like deep research and outreach execution.
 */
export class JobQueue {
  private queues: Map<JobType, Bull.Queue> = new Map();

  constructor() {
    const jobTypes: JobType[] = [
      "enrich_and_research",
      "start_outreach",
      "advance_sequence",
      "handle_reply",
    ];

    for (const type of jobTypes) {
      const queue = new Bull(type, config.redis.url, {
        defaultJobOptions: {
          attempts: 3,
          backoff: { type: "exponential", delay: 5000 },
          removeOnComplete: 100,
          removeOnFail: 200,
        },
        limiter: {
          max: type === "start_outreach" ? 10 : 20, // Rate limit outreach more aggressively
          duration: 60000, // per minute
        },
      });

      queue.on("failed", (job, err) => {
        logger.error(`Job ${type}:${job.id} failed`, {
          leadId: job.data.leadId,
          error: err.message,
          attempt: job.attemptsMade,
        });
      });

      queue.on("completed", (job) => {
        logger.info(`Job ${type}:${job.id} completed`, {
          leadId: job.data.leadId,
        });
      });

      this.queues.set(type, queue);
    }
  }

  /**
   * Add a job to the queue.
   */
  async add<T extends JobType>(
    type: T,
    data: JobPayload[T],
    options?: Bull.JobOptions
  ): Promise<Bull.Job<JobPayload[T]>> {
    const queue = this.queues.get(type);
    if (!queue) throw new Error(`Unknown job type: ${type}`);
    return queue.add(data, options);
  }

  /**
   * Register a processor for a job type.
   */
  process<T extends JobType>(
    type: T,
    concurrency: number,
    handler: (job: Bull.Job<JobPayload[T]>) => Promise<void>
  ): void {
    const queue = this.queues.get(type);
    if (!queue) throw new Error(`Unknown job type: ${type}`);
    queue.process(concurrency, handler);
  }

  /**
   * Get counts for all queues.
   */
  async getStats(): Promise<Record<JobType, Bull.JobCounts>> {
    const stats: Partial<Record<JobType, Bull.JobCounts>> = {};
    for (const [type, queue] of this.queues) {
      stats[type] = await queue.getJobCounts();
    }
    return stats as Record<JobType, Bull.JobCounts>;
  }

  /**
   * Graceful shutdown — wait for active jobs to complete.
   */
  async shutdown(): Promise<void> {
    for (const [type, queue] of this.queues) {
      logger.info(`Closing queue: ${type}`);
      await queue.close();
    }
  }
}
