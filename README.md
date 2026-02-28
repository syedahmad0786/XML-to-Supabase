# AI Sales & Growth Agent

Autonomous end-to-end AI agentic system for full-funnel lead generation, psychological profiling, and multi-channel outreach. Identifies high-LTV audiences from your business DNA, finds them, enriches their data, performs deep qualitative research, and executes a personalized multi-step sales sequence (LinkedIn, Email, Instagram) until a meeting is booked.

## Single-Line Flow

**BusinessDNA → ICP Analysis → Lead Sourcing → Scoring (1-10) → Deep Research → Psychological Profiling → Contact Enrichment → HITL Approval → Multi-Channel Sequence (LinkedIn → Email → IG) → Sentiment Monitoring → Objection Handling → Meeting Booking**

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   STRATEGY      │     │  INTELLIGENCE   │     │    OUTREACH     │
│                 │     │                 │     │                 │
│ ICP Analyzer    │────▶│ Deep Researcher │────▶│ Content Gen     │
│ Lead Sourcer    │     │ Psych Profiler  │     │ LinkedIn/Email  │
│ Lead Scorer     │     │ Contact Enrich  │     │ Instagram/DM    │
│                 │     │ Sentiment       │     │ Sequence Orch   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                    ┌─────────────────┐     ┌────────────▼────────┐
                    │     MEMORY      │     │      CLOSING        │
                    │                 │     │                     │
                    │ Knowledge Base  │◀───▶│ HITL Gateway        │
                    │ Conv. Memory    │     │ Appointment Setter  │
                    │ Vector Store    │     │ Booking (Calendly)  │
                    └─────────────────┘     └─────────────────────┘
```

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd ai-sales-growth-agent
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Set up Supabase
# Run supabase/migrations/001_initial_schema.sql on your Supabase project

# 4. Run the agent
npm run dev

# Or with Docker
docker-compose up -d
```

## Project Structure

```
src/
├── config/                 # Configuration and validation
├── strategy/               # Phase 1: ICP analysis, lead sourcing, scoring
│   ├── icp-analyzer.ts     # Generates ICPs from BusinessDNA
│   ├── lead-sourcer.ts     # Apollo, Clay, LinkedIn integration
│   └── lead-scorer.ts      # Scores leads 1-10 (weighted: timing, need, fit, authority, budget)
├── intelligence/           # Phase 2: Research and profiling
│   ├── deep-researcher.ts  # Company news, financials, pain points
│   ├── psychological-profiler.ts  # DISC-based behavioral profiling
│   ├── contact-enricher.ts # Verified emails, phones
│   └── sentiment-analyzer.ts     # Real-time intent detection
├── outreach/               # Phase 3: Multi-channel execution
│   ├── content-generator.ts      # Hyper-personalized message generation
│   ├── sequence-orchestrator.ts  # 14-day coordinated campaign
│   └── channels/
│       ├── linkedin.ts     # LinkedIn connection requests + messages
│       ├── email.ts        # SMTP email delivery
│       └── instagram.ts    # Instagram DM via Graph API
├── memory/                 # Persistence and retrieval
│   ├── knowledge-base.ts   # RAG over company docs for objection handling
│   ├── conversation-memory.ts    # Full conversation history + semantic search
│   └── vector-store.ts     # Pinecone integration
├── booking/
│   └── appointment-setter.ts     # Calendly + Google Calendar
├── hitl/
│   └── approval-gateway.ts       # Slack/Discord human-in-the-loop
├── orchestrator/
│   └── pipeline.ts         # Main pipeline orchestrating all phases
├── types/
│   └── index.ts            # TypeScript type definitions
└── index.ts                # Entry point
```

## Key Features

### Lead Scoring (1-10 Scale)
Not all leads are equal. The agent scores every lead across five dimensions before spending expensive API tokens:
- **Timing** (25%): Buying signals and urgency indicators
- **Need** (25%): Severity of pain points we solve
- **ICP Fit** (20%): Demographics and firmographics match
- **Authority** (15%): Decision-making power
- **Budget** (15%): Ability to pay

Only leads scoring **8+** receive deep research and personalized outreach.

### Psychological Profiling (DISC-Based)
The agent creates a behavioral profile of each decision-maker:
- **Communication Style**: Analytical, Driver, Expressive, or Amiable
- **Decision Making**: Data-driven, Intuitive, Collaborative, or Decisive
- **Response Patterns**: Best contact time, preferred message length, formality level

This directly controls the tone and structure of every outreach message.

### Human-in-the-Loop Safety
- First messages require Slack/Discord approval before sending
- High-value leads (score 9+) get human oversight
- Negative sentiment triggers immediate escalation
- All approvals are logged for compliance

### Sentiment Analysis
Real-time detection of:
- Hard stops: "not interested", "unsubscribe", "stop"
- Soft signals: "not now", "maybe later" (pause, don't stop)
- Positive signals: "tell me more", "schedule a call" (move to booking)
- Hostile responses: immediate stop + human escalation

## Multi-Channel Sequence (Default)

| Day | Channel | Type |
|-----|---------|------|
| 0 | LinkedIn | Connection request |
| 1 | Email | Primary value proposition |
| 3 | LinkedIn | Follow-up message |
| 5 | Email | Case study / social proof |
| 7 | Instagram | Casual DM (different angle) |
| 10 | Email | Address likely objection |
| 14 | Email | Breakup (graceful exit) |

## Cost Estimates

| Volume | Monthly Cost |
|--------|-------------|
| 500 leads/month | $380-$550 |
| 750 leads/month | $540-$780 |
| 1,000 leads/month | $700-$1,010 |

See [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md) for detailed breakdown.

## Tech Stack

| Layer | Tool |
|-------|------|
| LLM (Deep) | Claude Opus 4.6 |
| LLM (Content) | Claude Sonnet 4.6 |
| LLM (Fast) | Claude Haiku 4.5 |
| Vector DB | Pinecone |
| Database | Supabase (PostgreSQL) |
| Lead Data | Apollo.io + Clay |
| Email | SMTP (Nodemailer) |
| Orchestration | n8n |
| Queue | Redis + Bull |
| Booking | Calendly + Google Calendar |
| HITL | Slack / Discord |

## Documentation

- [Architecture Deep Dive](docs/ARCHITECTURE.md)
- [Cost Analysis](docs/COST_ANALYSIS.md)
