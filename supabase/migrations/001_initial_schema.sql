-- ═══════════════════════════════════════════════════════════════════
-- AI Sales & Growth Agent — Database Schema
-- ═══════════════════════════════════════════════════════════════════

-- Leads table: stores all lead data and current state
CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status TEXT NOT NULL DEFAULT 'sourced'
    CHECK (status IN ('sourced','enriched','researched','scored','approved',
                      'in_sequence','replied','meeting_booked','disqualified','opted_out')),
  score INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 10),
  source TEXT NOT NULL CHECK (source IN ('apollo','linkedin','clay','manual')),

  -- Contact info
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email TEXT,
  email_verified BOOLEAN DEFAULT FALSE,
  phone TEXT,
  linkedin_url TEXT,
  instagram_handle TEXT,

  -- Role info
  title TEXT,
  department TEXT,
  seniority TEXT,

  -- Company info (JSONB for flexible schema)
  company JSONB NOT NULL DEFAULT '{}',

  -- Intelligence data (JSONB)
  research JSONB,
  profile JSONB,
  enrichment JSONB,

  -- Outreach state (JSONB)
  sequence_state JSONB,
  sentiment JSONB,

  -- Metadata
  tags TEXT[] DEFAULT '{}',
  notes TEXT[] DEFAULT '{}',
  icp_match_score NUMERIC DEFAULT 0,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conversation messages table
CREATE TABLE IF NOT EXISTS conversation_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel TEXT NOT NULL CHECK (channel IN ('linkedin','email','instagram')),
  direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
  content TEXT NOT NULL,
  sentiment_overall TEXT,
  sentiment_score NUMERIC,
  sentiment_intent TEXT,
  sentiment_should_stop BOOLEAN DEFAULT FALSE,
  sentiment_should_escalate BOOLEAN DEFAULT FALSE,
  sentiment_suggested_action TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HITL approval requests
CREATE TABLE IF NOT EXISTS approval_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('first_outreach','escalation','high_value_lead','negative_sentiment')),
  proposed_channel TEXT NOT NULL,
  proposed_content TEXT NOT NULL,
  reason TEXT,
  research_summary TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','approved','rejected','modified')),
  modified_content TEXT,
  resolved_by TEXT,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- ICP configurations
CREATE TABLE IF NOT EXISTS icp_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  config JSONB NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pipeline run logs for tracking and analytics
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running',
  leads_sourced INTEGER DEFAULT 0,
  leads_qualified INTEGER DEFAULT 0,
  outreach_started INTEGER DEFAULT 0,
  meetings_booked INTEGER DEFAULT 0,
  errors JSONB DEFAULT '[]'
);

-- ═══════════════════════════════════════════════════════════════════
-- Indexes
-- ═══════════════════════════════════════════════════════════════════

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_score ON leads(score DESC);
CREATE INDEX idx_leads_email ON leads(email);
CREATE INDEX idx_leads_source ON leads(source);
CREATE INDEX idx_leads_updated ON leads(updated_at DESC);

CREATE INDEX idx_messages_lead ON conversation_messages(lead_id);
CREATE INDEX idx_messages_created ON conversation_messages(created_at DESC);

CREATE INDEX idx_approvals_status ON approval_requests(status);
CREATE INDEX idx_approvals_lead ON approval_requests(lead_id);

-- ═══════════════════════════════════════════════════════════════════
-- Row-level security
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by the agent)
CREATE POLICY "Service role full access on leads"
  ON leads FOR ALL
  USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on messages"
  ON conversation_messages FOR ALL
  USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on approvals"
  ON approval_requests FOR ALL
  USING (auth.role() = 'service_role');

-- ═══════════════════════════════════════════════════════════════════
-- Updated_at trigger
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
