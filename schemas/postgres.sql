-- ctxledger PostgreSQL schema
-- v0.1.0 foundation schema
--
-- Canonical state lives in PostgreSQL.
-- Repository projections and retrieval indexes are derived artifacts.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Common updated_at trigger
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Workspaces
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workspaces (
  workspace_id UUID PRIMARY KEY,
  repo_url TEXT NOT NULL,
  canonical_path TEXT NOT NULL,
  default_branch TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT workspaces_canonical_path_not_empty
    CHECK (btrim(canonical_path) <> ''),
  CONSTRAINT workspaces_repo_url_not_empty
    CHECK (btrim(repo_url) <> ''),
  CONSTRAINT workspaces_default_branch_not_empty
    CHECK (btrim(default_branch) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_canonical_path
  ON workspaces (canonical_path);

CREATE INDEX IF NOT EXISTS idx_workspaces_repo_url
  ON workspaces (repo_url);

DROP TRIGGER IF EXISTS trg_workspaces_set_updated_at ON workspaces;
CREATE TRIGGER trg_workspaces_set_updated_at
BEFORE UPDATE ON workspaces
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Workflow instances
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow_instances (
  workflow_instance_id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE RESTRICT,
  ticket_id TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT workflow_instances_ticket_id_not_empty
    CHECK (btrim(ticket_id) <> ''),
  CONSTRAINT workflow_instances_status_valid
    CHECK (status IN ('running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_instances_workspace_created_desc
  ON workflow_instances (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_instances_workspace_updated_desc
  ON workflow_instances (workspace_id, updated_at DESC);

-- Enforce at most one running workflow per workspace.
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_instances_one_running_per_workspace
  ON workflow_instances (workspace_id)
  WHERE status = 'running';

DROP TRIGGER IF EXISTS trg_workflow_instances_set_updated_at ON workflow_instances;
CREATE TRIGGER trg_workflow_instances_set_updated_at
BEFORE UPDATE ON workflow_instances
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Workflow attempts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow_attempts (
  attempt_id UUID PRIMARY KEY,
  workflow_instance_id UUID NOT NULL REFERENCES workflow_instances(workflow_instance_id) ON DELETE CASCADE,
  attempt_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  failure_reason TEXT,
  verify_status TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT workflow_attempts_attempt_number_positive
    CHECK (attempt_number > 0),
  CONSTRAINT workflow_attempts_status_valid
    CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled')),
  CONSTRAINT workflow_attempts_verify_status_valid
    CHECK (
      verify_status IS NULL OR
      verify_status IN ('pending', 'passed', 'failed', 'skipped')
    ),
  CONSTRAINT workflow_attempts_finished_at_after_started_at
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_attempts_workflow_attempt_number
  ON workflow_attempts (workflow_instance_id, attempt_number);

CREATE INDEX IF NOT EXISTS idx_workflow_attempts_workflow_started_desc
  ON workflow_attempts (workflow_instance_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_attempts_workflow_created_desc
  ON workflow_attempts (workflow_instance_id, created_at DESC);

-- Enforce at most one running attempt per workflow instance.
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_attempts_one_running_per_workflow
  ON workflow_attempts (workflow_instance_id)
  WHERE status = 'running';

DROP TRIGGER IF EXISTS trg_workflow_attempts_set_updated_at ON workflow_attempts;
CREATE TRIGGER trg_workflow_attempts_set_updated_at
BEFORE UPDATE ON workflow_attempts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Workflow checkpoints
-- ---------------------------------------------------------------------------
-- `checkpoint_json` is canonical structured checkpoint state.
-- It may carry fields such as `current_objective` and `next_intended_action`
-- that help continuation-oriented reads distinguish the main task line from
-- temporary detours. This supports task_recall heuristics, while the database
-- remains the canonical source of record and any ranking or explanation layers
-- remain derived.

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
  checkpoint_id UUID PRIMARY KEY,
  workflow_instance_id UUID NOT NULL REFERENCES workflow_instances(workflow_instance_id) ON DELETE CASCADE,
  attempt_id UUID NOT NULL REFERENCES workflow_attempts(attempt_id) ON DELETE CASCADE,
  step_name TEXT NOT NULL,
  summary TEXT,
  checkpoint_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT workflow_checkpoints_step_name_not_empty
    CHECK (btrim(step_name) <> '')
);

CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_workflow_created_desc
  ON workflow_checkpoints (workflow_instance_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_attempt_created_desc
  ON workflow_checkpoints (attempt_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Verify reports
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS verify_reports (
  verify_id UUID PRIMARY KEY,
  attempt_id UUID NOT NULL REFERENCES workflow_attempts(attempt_id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT verify_reports_status_valid
    CHECK (status IN ('pending', 'passed', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS idx_verify_reports_attempt_created_desc
  ON verify_reports (attempt_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verify_reports_attempt_verify_created_desc
  ON verify_reports (attempt_id, verify_id, created_at DESC);


-- ---------------------------------------------------------------------------
-- Artifact metadata
-- Canonical metadata only; artifact content is external to the DB.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id UUID PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  workflow_instance_id UUID REFERENCES workflow_instances(workflow_instance_id) ON DELETE CASCADE,
  attempt_id UUID REFERENCES workflow_attempts(attempt_id) ON DELETE CASCADE,
  checkpoint_id UUID REFERENCES workflow_checkpoints(checkpoint_id) ON DELETE CASCADE,
  episode_id UUID,
  memory_id UUID,
  artifact_type TEXT NOT NULL,
  artifact_role TEXT NOT NULL,
  locator TEXT NOT NULL,
  mime_type TEXT,
  provenance TEXT,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT artifacts_type_not_empty
    CHECK (btrim(artifact_type) <> ''),
  CONSTRAINT artifacts_role_not_empty
    CHECK (btrim(artifact_role) <> ''),
  CONSTRAINT artifacts_locator_not_empty
    CHECK (btrim(locator) <> '')
);

CREATE INDEX IF NOT EXISTS idx_artifacts_workflow_created_desc
  ON artifacts (workflow_instance_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_artifacts_attempt_created_desc
  ON artifacts (attempt_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_artifacts_checkpoint_created_desc
  ON artifacts (checkpoint_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Structured failures
-- Canonical durable failure metadata for operational and knowledge use.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS failures (
  failure_id UUID PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  workflow_instance_id UUID REFERENCES workflow_instances(workflow_instance_id) ON DELETE CASCADE,
  attempt_id UUID REFERENCES workflow_attempts(attempt_id) ON DELETE CASCADE,
  checkpoint_id UUID REFERENCES workflow_checkpoints(checkpoint_id) ON DELETE CASCADE,
  episode_id UUID,
  memory_id UUID,
  failure_scope TEXT NOT NULL,
  failure_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  resolution TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,

  CONSTRAINT failures_scope_valid
    CHECK (failure_scope IN ('workflow', 'attempt', 'projection', 'verification', 'episode', 'memory')),
  CONSTRAINT failures_type_not_empty
    CHECK (btrim(failure_type) <> ''),
  CONSTRAINT failures_summary_not_empty
    CHECK (btrim(summary) <> ''),
  CONSTRAINT failures_status_valid
    CHECK (status IN ('open', 'resolved', 'ignored')),
  CONSTRAINT failures_resolved_at_after_occurred_at
    CHECK (resolved_at IS NULL OR resolved_at >= occurred_at)
);

CREATE INDEX IF NOT EXISTS idx_failures_workflow_occurred_desc
  ON failures (workflow_instance_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_failures_attempt_occurred_desc
  ON failures (attempt_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_failures_scope_status
  ON failures (failure_scope, status);

-- ---------------------------------------------------------------------------
-- Episodic memory
-- v0.1.0 foundation: schema exists, features may be partially implemented.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS episodes (
  episode_id UUID PRIMARY KEY,
  workflow_instance_id UUID NOT NULL REFERENCES workflow_instances(workflow_instance_id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'recorded',
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT episodes_summary_not_empty
    CHECK (btrim(summary) <> ''),
  CONSTRAINT episodes_status_valid
    CHECK (status IN ('recorded', 'superseded', 'archived'))
);

ALTER TABLE episodes
  ADD COLUMN IF NOT EXISTS attempt_id UUID REFERENCES workflow_attempts(attempt_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_episodes_workflow_instance_created_desc
  ON episodes (workflow_instance_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_attempt_created_desc
  ON episodes (attempt_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_created_desc
  ON episodes (created_at DESC);

DROP TRIGGER IF EXISTS trg_episodes_set_updated_at ON episodes;
CREATE TRIGGER trg_episodes_set_updated_at
BEFORE UPDATE ON episodes
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS episode_events (
  episode_event_id UUID PRIMARY KEY,
  episode_id UUID NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  event_seq INTEGER NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT episode_events_type_not_empty
    CHECK (btrim(event_type) <> ''),
  CONSTRAINT episode_events_seq_positive
    CHECK (event_seq > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_events_episode_seq
  ON episode_events (episode_id, event_seq);

CREATE INDEX IF NOT EXISTS idx_episode_events_episode_created_desc
  ON episode_events (episode_id, created_at DESC);

CREATE TABLE IF NOT EXISTS episode_summaries (
  episode_summary_id UUID PRIMARY KEY,
  episode_id UUID NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  summary_scope TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT episode_summaries_scope_not_empty
    CHECK (btrim(summary_scope) <> ''),
  CONSTRAINT episode_summaries_summary_not_empty
    CHECK (btrim(summary) <> '')
);

CREATE INDEX IF NOT EXISTS idx_episode_summaries_episode_created_desc
  ON episode_summaries (episode_id, created_at DESC);

CREATE TABLE IF NOT EXISTS episode_failures (
  episode_failure_id UUID PRIMARY KEY,
  episode_id UUID NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  failure_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  resolution TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT episode_failures_type_not_empty
    CHECK (btrim(failure_type) <> ''),
  CONSTRAINT episode_failures_summary_not_empty
    CHECK (btrim(summary) <> '')
);

CREATE INDEX IF NOT EXISTS idx_episode_failures_episode_created_desc
  ON episode_failures (episode_id, created_at DESC);

CREATE TABLE IF NOT EXISTS episode_artifacts (
  episode_artifact_id UUID PRIMARY KEY,
  episode_id UUID NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
  artifact_id UUID NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT episode_artifacts_role_not_empty
    CHECK (btrim(role) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_artifacts_episode_artifact
  ON episode_artifacts (episode_id, artifact_id);

-- ---------------------------------------------------------------------------
-- Semantic / procedural memory
-- v0.1.0 foundation: schema exists, advanced retrieval may come later.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_items (
  memory_id UUID PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  episode_id UUID REFERENCES episodes(episode_id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  provenance TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_items_type_not_empty
    CHECK (btrim(type) <> ''),
  CONSTRAINT memory_items_provenance_valid
    CHECK (provenance IN ('episode', 'explicit', 'derived', 'imported', 'workflow_complete_auto')),
  CONSTRAINT memory_items_content_not_empty
    CHECK (btrim(content) <> '')
);

CREATE INDEX IF NOT EXISTS idx_memory_items_workspace_created_desc
  ON memory_items (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_items_episode_created_desc
  ON memory_items (episode_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_items_type
  ON memory_items (type);

DROP TRIGGER IF EXISTS trg_memory_items_set_updated_at ON memory_items;
CREATE TRIGGER trg_memory_items_set_updated_at
BEFORE UPDATE ON memory_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS memory_embeddings (
  memory_embedding_id UUID PRIMARY KEY,
  memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
  embedding_model TEXT NOT NULL,
  embedding VECTOR(1536),
  content_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_embeddings_model_not_empty
    CHECK (btrim(embedding_model) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_embeddings_memory_model
  ON memory_embeddings (memory_id, embedding_model);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_embedding_hnsw
  ON memory_embeddings
  USING hnsw (embedding vector_l2_ops);

CREATE TABLE IF NOT EXISTS memory_summaries (
  memory_summary_id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  episode_id UUID REFERENCES episodes(episode_id) ON DELETE CASCADE,
  summary_text TEXT NOT NULL,
  summary_kind TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_summaries_summary_text_not_empty
    CHECK (btrim(summary_text) <> ''),
  CONSTRAINT memory_summaries_summary_kind_not_empty
    CHECK (btrim(summary_kind) <> '')
);

CREATE INDEX IF NOT EXISTS idx_memory_summaries_workspace_created_desc
  ON memory_summaries (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_summaries_episode_created_desc
  ON memory_summaries (episode_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_memory_summaries_set_updated_at ON memory_summaries;
CREATE TRIGGER trg_memory_summaries_set_updated_at
BEFORE UPDATE ON memory_summaries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS memory_summary_memberships (
  memory_summary_membership_id UUID PRIMARY KEY,
  memory_summary_id UUID NOT NULL REFERENCES memory_summaries(memory_summary_id) ON DELETE CASCADE,
  memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
  membership_order INTEGER,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_summary_memberships_unique_summary_member
    UNIQUE (memory_summary_id, memory_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_summary_memberships_summary_order_created
  ON memory_summary_memberships (
    memory_summary_id,
    membership_order,
    created_at,
    memory_id
  );

CREATE INDEX IF NOT EXISTS idx_memory_summary_memberships_memory_created_desc
  ON memory_summary_memberships (memory_id, created_at DESC);

CREATE TABLE IF NOT EXISTS memory_relations (
  memory_relation_id UUID PRIMARY KEY,
  source_memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
  target_memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_relations_type_not_empty
    CHECK (btrim(relation_type) <> ''),
  CONSTRAINT memory_relations_no_self_edge
    CHECK (source_memory_id <> target_memory_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_relations_source_target_type
  ON memory_relations (source_memory_id, target_memory_id, relation_type);

CREATE INDEX IF NOT EXISTS idx_memory_relations_source
  ON memory_relations (source_memory_id);

CREATE INDEX IF NOT EXISTS idx_memory_relations_target
  ON memory_relations (target_memory_id);

COMMIT;
