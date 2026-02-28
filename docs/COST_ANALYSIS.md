# Cost Analysis — 500-1,000 Leads/Month

## Monthly Cost Breakdown

### Scenario: 750 leads/month (midpoint)

#### LLM API Costs (Anthropic)

| Operation | Model | Calls/mo | Tokens/call | Cost/call | Monthly |
|-----------|-------|----------|-------------|-----------|---------|
| ICP Analysis | Opus 4.6 | 3 | ~4K out | $0.60 | $1.80 |
| Lead Scoring | Haiku 4.5 | 750 | ~500 out | $0.001 | $0.75 |
| Deep Research (Tier 1, ~30%) | Opus 4.6 | 225 | ~6K out | $0.90 | $202.50 |
| Light Research (Tier 2, ~20%) | Haiku 4.5 | 150 | ~1K out | $0.003 | $0.45 |
| Psychological Profiling (Tier 1) | Sonnet 4.6 | 225 | ~1.5K out | $0.04 | $9.00 |
| Content Generation (7 steps × Tier 1) | Sonnet 4.6 | 1,575 | ~800 out | $0.02 | $31.50 |
| Sentiment Analysis | Haiku 4.5 | 200 | ~300 out | $0.0005 | $0.10 |
| Reply Generation | Sonnet 4.6 | 100 | ~600 out | $0.02 | $2.00 |
| **LLM Subtotal** | | | | | **~$248** |

#### Embeddings (OpenAI)

| Operation | Model | Calls/mo | Cost | Monthly |
|-----------|-------|----------|------|---------|
| KB + Conversation indexing | text-embedding-3-small | ~5,000 | $0.00002/1K tokens | $0.50 |
| **Embeddings Subtotal** | | | | **~$1** |

#### SaaS Subscriptions

| Service | Plan | Monthly |
|---------|------|---------|
| Apollo.io | Professional | $99 |
| Clay | Explorer (1K credits) | $149 |
| Supabase | Pro | $25 |
| Pinecone | Starter (free) or Standard | $0-$70 |
| n8n | Self-hosted (free) or Cloud Starter | $0-$20 |
| Calendly | Standard | $12 |
| SendGrid/Mailgun (email delivery) | Free tier (100/day) or Essentials | $0-$20 |
| LinkedIn Sales Navigator (optional) | Core | $99 |
| Slack | Free | $0 |
| **SaaS Subtotal** | | **$284-$494** |

#### Infrastructure

| Service | Spec | Monthly |
|---------|------|---------|
| Hosting (AWS/Railway/Render) | Small instance | $10-$25 |
| Redis (managed) | Free tier or basic | $0-$15 |
| **Infra Subtotal** | | **$10-$40** |

---

### Total Monthly Cost

| Volume | Low Estimate | High Estimate |
|--------|-------------|---------------|
| **500 leads/month** | **$380** | **$550** |
| **750 leads/month** | **$540** | **$780** |
| **1,000 leads/month** | **$700** | **$1,010** |

---

## Cost Optimization Strategies

1. **Tiered resource allocation** (already implemented):
   - Score < 6: $0.001/lead (scoring only)
   - Score 6-7: ~$0.01/lead (light research)
   - Score 8-10: ~$1.10/lead (full pipeline)

2. **Batch operations**: Score all leads with Haiku before committing Opus tokens

3. **Cache research**: If two leads are at the same company, research once

4. **Prompt caching**: Anthropic's prompt caching reduces cost by 90% on repeated prefixes

5. **Fallback models**: Use Haiku for routine tasks, reserve Opus for deep analysis

---

## ROI Projection

Assuming:
- Average deal size: $8,000/month
- Conversion rate from outreach to meeting: 3-5%
- Meeting-to-close rate: 20-30%

| Metric | Conservative | Optimistic |
|--------|-------------|------------|
| Leads/month | 750 | 750 |
| Qualified (score ≥ 8) | 225 (30%) | 225 (30%) |
| Meetings booked | 7 (3%) | 11 (5%) |
| Deals closed | 1-2 (20%) | 3-4 (30%) |
| Revenue generated | $8,000-$16,000 | $24,000-$32,000 |
| Agent cost | ~$700 | ~$700 |
| **ROI** | **10-22x** | **34-45x** |
