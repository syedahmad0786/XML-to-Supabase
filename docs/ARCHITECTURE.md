# AI Sales & Growth Agent — Technical Architecture

## Single-Line Logic Flow

**BusinessDNA → ICP Analysis → Lead Sourcing (Apollo/Clay/LinkedIn) → Lead Scoring (1-10) → [Score ≥ 8] → Deep Research + Psychological Profiling + Contact Enrichment → HITL Approval (Slack/Discord) → Multi-Channel Sequence (LinkedIn Day 0 → Email Day 1 → LinkedIn Day 3 → Email Day 5 → Instagram Day 7 → Email Day 10 → Breakup Day 14) → Sentiment Monitoring (stop/escalate/continue) → Objection Handling (Knowledge Base RAG) → Meeting Booking (Calendly/Google Calendar)**

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        n8n / Cron Orchestration Layer                        │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │ Daily 8AM   │  │ Hourly Sequence  │  │ Inbound Reply Webhook        │    │
│  │ Pipeline Run│  │ Advancement      │  │ (Email/LinkedIn/IG)          │    │
│  └──────┬──────┘  └────────┬─────────┘  └──────────────┬───────────────┘    │
└─────────┼──────────────────┼───────────────────────────┼────────────────────┘
          │                  │                           │
          ▼                  ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE ORCHESTRATOR                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │ Phase 1: STRATEGY & DISCOVERY                                       │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │     │
│  │  │ ICP Analyzer │→│ Lead Sourcer │→│ Lead Scorer  │             │     │
│  │  │ (Opus 4.6)   │  │ (Apollo/Clay)│  │ (Haiku 4.5)  │             │     │
│  │  └──────────────┘  └──────────────┘  └──────┬───────┘             │     │
│  └─────────────────────────────────────────────┼───────────────────────┘     │
│                                                 │                            │
│                                    Score ≥ 8 ───┤─── Score < 8 → Skip       │
│                                                 │                            │
│  ┌─────────────────────────────────────────────┼───────────────────────┐     │
│  │ Phase 2: INTELLIGENCE & ENRICHMENT          │                       │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │     │
│  │  │ Deep         │  │ Psychological│  │ Contact      │             │     │
│  │  │ Researcher   │  │ Profiler     │  │ Enricher     │             │     │
│  │  │ (Opus 4.6)   │  │ (Sonnet 4.6) │  │ (Apollo API) │             │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                 │                            │
│  ┌─────────────────────────────────────────────┼───────────────────────┐     │
│  │ Phase 3: HITL APPROVAL GATEWAY              │                       │     │
│  │  ┌──────────────────────────────────────────┐                      │     │
│  │  │ Slack/Discord Notification → One-Click Approve/Reject/Edit     │     │
│  │  └──────────────────────────────────────────┘                      │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                 │                            │
│  ┌─────────────────────────────────────────────┼───────────────────────┐     │
│  │ Phase 4: OUTREACH & EXECUTION               │                       │     │
│  │  ┌──────────────┐  ┌──────────────────────────────────────────┐   │     │
│  │  │ Content      │  │ Channel Adapters                          │   │     │
│  │  │ Generator    │→│  LinkedIn │ Email (SMTP) │ Instagram      │   │     │
│  │  │ (Sonnet 4.6) │  └──────────────────────────────────────────┘   │     │
│  │  └──────────────┘                                                  │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                 │                            │
│                                    Reply? ──────┤                            │
│                                                 │                            │
│  ┌─────────────────────────────────────────────┼───────────────────────┐     │
│  │ Phase 5: RESPONSE HANDLING                  │                       │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │     │
│  │  │ Sentiment    │→│ Knowledge    │→│ Appointment  │             │     │
│  │  │ Analyzer     │  │ Base (RAG)   │  │ Setter       │             │     │
│  │  │ (Haiku 4.5)  │  │ (Pinecone)   │  │ (Calendly)   │             │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────┘
                              │                    │
                ┌─────────────┼────────────────────┼───────────┐
                │             ▼                    ▼           │
                │  ┌──────────────┐  ┌──────────────────┐     │
                │  │  Supabase    │  │   Pinecone       │     │
                │  │  (SQL + Auth)│  │   (Vector Store) │     │
                │  └──────────────┘  └──────────────────┘     │
                │              PERSISTENCE LAYER               │
                └──────────────────────────────────────────────┘
```

---

## Module Breakdown

### 1. Strategy & Discovery Engine

| Module | Purpose | LLM Model |
|--------|---------|-----------|
| `ICP Analyzer` | Analyzes BusinessDNA to generate Ideal Customer Profiles | Opus 4.6 (high reasoning) |
| `Lead Sourcer` | Searches Apollo, Clay, LinkedIn Sales Nav for matching leads | N/A (API calls) |
| `Lead Scorer` | Scores leads 1-10 on ICP fit, timing, authority, need, budget | Haiku 4.5 (fast, cheap) |

**Lead Scoring Weights:**
- Timing: 25% (are they ready to buy now?)
- Need: 25% (how severe is the pain we solve?)
- ICP Fit: 20% (demographics/firmographics match)
- Authority: 15% (is this the decision-maker?)
- Budget: 15% (can they afford our solution?)

### 2. Intelligence & Enrichment

| Module | Purpose | LLM Model |
|--------|---------|-----------|
| `Deep Researcher` | Company news, financial health, pain points, competitive intel | Opus 4.6 (deep analysis) |
| `Psychological Profiler` | DISC-based communication style, decision patterns, motivators | Sonnet 4.6 |
| `Contact Enricher` | Verified emails, phones, social profiles | N/A (Apollo API) |
| `Sentiment Analyzer` | Real-time intent detection on inbound messages | Haiku 4.5 (fast) |

**Tiered Resource Allocation:**
- **Tier 1 (Score 8-10):** Full deep research + psychological profiling + personalized multi-channel
- **Tier 2 (Score 6-7):** Light research + templated outreach
- **Tier 3 (Score < 6):** Skip — don't waste API tokens

### 3. Outreach & Execution

**Default 14-Day Multi-Channel Sequence:**

| Day | Channel | Type | Rationale |
|-----|---------|------|-----------|
| 0 | LinkedIn | Connection request | Warm touch, low commitment, social proof |
| 1 | Email | Cold email #1 | Primary value proposition |
| 3 | LinkedIn | Follow-up message | If connected, deepen relationship |
| 5 | Email | Follow-up #1 | Case study / social proof angle |
| 7 | Instagram | DM | Casual, different channel, shows persistence |
| 10 | Email | Follow-up #2 | Address likely objection |
| 14 | Email | Breakup | Create urgency, graceful exit |

### 4. Memory & Persistence

**Two-tier architecture:**
1. **Supabase (PostgreSQL):** Structured data — leads, conversations, approvals, pipeline runs
2. **Pinecone (Vector):** Semantic search — knowledge base, conversation context retrieval

**Conversation Memory ensures:**
- Agent never repeats arguments across a 14-day sequence
- Relevant context from older messages is surfaced when topics recur
- Full conversation history is available for human review

### 5. HITL Safety Net

Approval is required for:
- First outreach message (configurable)
- Leads scoring 9+ (high value, don't risk it)
- Negative sentiment detected (human judgment needed)
- Escalation triggers (angry/hostile responses)

---

## Technology Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| **LLM (Reasoning)** | Claude Opus 4.6 | ICP analysis, deep research |
| **LLM (Content)** | Claude Sonnet 4.6 | Message generation, profiling |
| **LLM (Fast)** | Claude Haiku 4.5 | Scoring, sentiment analysis |
| **Embeddings** | OpenAI text-embedding-3-small | Vector representations |
| **Vector DB** | Pinecone | Semantic search (KB + conversations) |
| **Database** | Supabase (PostgreSQL) | Lead state, conversations, approvals |
| **Lead Data** | Apollo.io + Clay | Sourcing and enrichment |
| **Email** | Nodemailer (SMTP) | Email delivery |
| **Orchestration** | n8n | Cron jobs, webhooks, workflow automation |
| **Queue** | Redis + Bull | Async job processing |
| **Booking** | Calendly + Google Calendar | Meeting scheduling |
| **HITL** | Slack / Discord webhooks | Human approval flow |
| **Hosting** | Docker + any cloud | Self-contained deployment |

---

## Data Flow

```
BusinessDNA (manual input)
    │
    ▼
ICP Analyzer ──→ 2-3 ICP segments
    │
    ▼
Lead Sourcer ──→ ~500-1000 raw leads/month
    │
    ▼
Lead Scorer ──→ Scored 1-10 (Haiku — $0.001/lead)
    │
    ├── Score < 6 → discard
    ├── Score 6-7 → light research → templated outreach
    └── Score 8-10 → full pipeline ↓
         │
         ▼
    Deep Research (Opus — $0.15/lead) + Psychological Profile (Sonnet — $0.03/lead)
         │
         ▼
    Contact Enrichment (Apollo — included in subscription)
         │
         ▼
    HITL Approval (Slack notification → human approve/reject)
         │
         ▼
    Multi-Channel Sequence (7 touchpoints over 14 days)
         │
         ├── No reply after 14 days → archive
         └── Reply received ↓
              │
              ▼
         Sentiment Analysis (Haiku — $0.0005/analysis)
              │
              ├── Negative → stop + optional escalation
              ├── Neutral → continue sequence
              └── Positive → generate reply + attempt booking
                   │
                   ▼
              Knowledge Base RAG (for objection handling)
                   │
                   ▼
              Appointment Setter (Calendly link or Google Calendar)
```
