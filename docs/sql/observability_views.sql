BEGIN;

CREATE SCHEMA IF NOT EXISTS observability;

CREATE OR REPLACE VIEW observability.workflow_status_counts AS
SELECT
  status,
  COUNT(*)::bigint AS workflow_count
FROM workflow_instances
GROUP BY status;

CREATE OR REPLACE VIEW observability.workflow_attempt_status_counts AS
SELECT
  status,
  COUNT(*)::bigint AS attempt_count
FROM workflow_attempts
GROUP BY status;

CREATE OR REPLACE VIEW observability.verify_report_status_counts AS
SELECT
  status,
  COUNT(*)::bigint AS verify_report_count
FROM verify_reports
GROUP BY status;

CREATE OR REPLACE VIEW observability.workflow_recent AS
SELECT
  wi.workflow_instance_id,
  wi.workspace_id,
  w.canonical_path,
  wi.ticket_id,
  wi.status AS workflow_status,
  wi.created_at,
  wi.updated_at,
  wc.step_name AS latest_step_name,
  wc.summary AS latest_step_summary,
  wc.created_at AS latest_checkpoint_created_at,
  wa.attempt_id AS latest_attempt_id,
  wa.attempt_number AS latest_attempt_number,
  wa.status AS latest_attempt_status,
  wa.verify_status AS latest_verify_status,
  vr.created_at AS latest_verify_report_created_at
FROM workflow_instances AS wi
LEFT JOIN workspaces AS w
  ON w.workspace_id = wi.workspace_id
LEFT JOIN LATERAL (
  SELECT
    checkpoint_id,
    step_name,
    summary,
    created_at
  FROM workflow_checkpoints
  WHERE workflow_instance_id = wi.workflow_instance_id
  ORDER BY created_at DESC
  LIMIT 1
) AS wc ON TRUE
LEFT JOIN LATERAL (
  SELECT
    attempt_id,
    attempt_number,
    status,
    verify_status,
    started_at,
    updated_at
  FROM workflow_attempts
  WHERE workflow_instance_id = wi.workflow_instance_id
  ORDER BY attempt_number DESC, started_at DESC
  LIMIT 1
) AS wa ON TRUE
LEFT JOIN LATERAL (
  SELECT
    verify_id,
    created_at
  FROM verify_reports
  WHERE attempt_id = wa.attempt_id
  ORDER BY created_at DESC
  LIMIT 1
) AS vr ON TRUE;

CREATE OR REPLACE VIEW observability.workflow_overview AS
SELECT
  (SELECT COUNT(*)::bigint FROM workspaces) AS workspace_count,
  (SELECT COUNT(*)::bigint FROM workflow_instances) AS workflow_count,
  (SELECT COUNT(*)::bigint FROM workflow_attempts) AS workflow_attempt_count,
  (SELECT COUNT(*)::bigint FROM workflow_checkpoints) AS workflow_checkpoint_count,
  (SELECT COUNT(*)::bigint FROM verify_reports) AS verify_report_count,
  (SELECT MAX(updated_at) FROM workflow_instances) AS latest_workflow_updated_at,
  (SELECT MAX(created_at) FROM workflow_checkpoints) AS latest_checkpoint_created_at,
  (SELECT MAX(created_at) FROM verify_reports) AS latest_verify_report_created_at;

DROP VIEW IF EXISTS observability.memory_overview;

CREATE VIEW observability.memory_overview AS
SELECT
  (SELECT COUNT(*)::bigint FROM episodes) AS episode_count,
  (SELECT COUNT(*)::bigint FROM memory_items) AS memory_item_count,
  (SELECT COUNT(*)::bigint FROM memory_embeddings) AS memory_embedding_count,
  (SELECT COUNT(*)::bigint FROM memory_relations) AS memory_relation_count,
  (SELECT MAX(created_at) FROM episodes) AS latest_episode_created_at,
  (SELECT MAX(created_at) FROM memory_items) AS latest_memory_item_created_at,
  (SELECT MAX(created_at) FROM memory_embeddings) AS latest_memory_embedding_created_at,
  (SELECT MAX(created_at) FROM memory_relations) AS latest_memory_relation_created_at,
  (SELECT COUNT(*)::bigint FROM memory_summaries) AS memory_summary_count,
  (SELECT COUNT(*)::bigint FROM memory_summary_memberships) AS memory_summary_membership_count,
  (
    SELECT COUNT(*)::bigint
    FROM memory_items
    WHERE provenance = 'interaction'
  ) AS interaction_memory_item_count,
  (
    SELECT COUNT(*)::bigint
    FROM memory_items
    WHERE COALESCE(metadata_json ->> 'file_path', '') <> ''
       OR COALESCE(metadata_json ->> 'file_paths', '') <> ''
       OR COALESCE(metadata_json ->> 'file_work_count', '') <> ''
       OR COALESCE(metadata_json ->> 'file_work_paths', '') <> ''
  ) AS file_work_memory_item_count,
  (SELECT MAX(created_at) FROM memory_summaries) AS latest_memory_summary_created_at,
  (
    SELECT MAX(created_at)
    FROM memory_items
    WHERE provenance = 'interaction'
  ) AS latest_interaction_memory_item_created_at,
  (
    SELECT MAX(created_at)
    FROM memory_items
    WHERE COALESCE(metadata_json ->> 'file_path', '') <> ''
       OR COALESCE(metadata_json ->> 'file_paths', '') <> ''
       OR COALESCE(metadata_json ->> 'file_work_count', '') <> ''
       OR COALESCE(metadata_json ->> 'file_work_paths', '') <> ''
  ) AS latest_file_work_memory_item_created_at;

CREATE OR REPLACE VIEW observability.memory_item_provenance_counts AS
SELECT
  provenance,
  COUNT(*)::bigint AS memory_item_count
FROM memory_items
GROUP BY provenance;

CREATE OR REPLACE VIEW observability.runtime_recent_activity_summary AS
SELECT
  (
    SELECT COUNT(*)::bigint
    FROM workflow_instances
    WHERE updated_at >= now() - interval '24 hours'
  ) AS workflows_updated_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM workflow_instances
    WHERE status = 'running'
  ) AS running_workflow_count,
  (
    SELECT COUNT(*)::bigint
    FROM workflow_instances
    WHERE status NOT IN ('completed', 'failed', 'cancelled')
  ) AS non_terminal_workflow_count,
  (
    SELECT COUNT(*)::bigint
    FROM workflow_checkpoints
    WHERE created_at >= now() - interval '24 hours'
  ) AS checkpoints_created_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM verify_reports
    WHERE created_at >= now() - interval '24 hours'
  ) AS verify_reports_created_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM episodes
    WHERE created_at >= now() - interval '24 hours'
  ) AS episodes_created_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM memory_items
    WHERE created_at >= now() - interval '24 hours'
  ) AS memory_items_created_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM memory_items
    WHERE provenance = 'interaction'
      AND created_at >= now() - interval '24 hours'
  ) AS interaction_memory_items_created_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM memory_items
    WHERE (
      COALESCE(metadata_json ->> 'file_path', '') <> ''
      OR COALESCE(metadata_json ->> 'file_paths', '') <> ''
      OR COALESCE(metadata_json ->> 'file_work_count', '') <> ''
      OR COALESCE(metadata_json ->> 'file_work_paths', '') <> ''
    )
      AND created_at >= now() - interval '24 hours'
  ) AS file_work_memory_items_created_last_24h;

CREATE OR REPLACE VIEW observability.failure_recent_summary AS
SELECT
  (
    SELECT COUNT(*)::bigint
    FROM failures
    WHERE occurred_at >= now() - interval '24 hours'
  ) AS failures_created_last_24h,
  (
    SELECT COUNT(*)::bigint
    FROM failures
    WHERE occurred_at >= now() - interval '7 days'
  ) AS failures_created_last_7d,
  (
    SELECT COUNT(*)::bigint
    FROM (
      SELECT failure_type
      FROM failures
      WHERE occurred_at >= now() - interval '7 days'
      GROUP BY failure_type
      HAVING COUNT(*) >= 2
    ) AS repeated_failure_groups
  ) AS repeated_failure_groups_last_7d,
  (
    SELECT MAX(occurred_at)
    FROM failures
  ) AS latest_failure_created_at;

CREATE OR REPLACE VIEW observability.runtime_activity_timeline AS
SELECT
  'workflow_instance'::text AS event_type,
  workflow_instance_id::text AS entity_id,
  updated_at AS event_at
FROM workflow_instances
UNION ALL
SELECT
  'workflow_checkpoint'::text AS event_type,
  checkpoint_id::text AS entity_id,
  created_at AS event_at
FROM workflow_checkpoints
UNION ALL
SELECT
  'verify_report'::text AS event_type,
  verify_id::text AS entity_id,
  created_at AS event_at
FROM verify_reports
UNION ALL
SELECT
  'episode'::text AS event_type,
  episode_id::text AS entity_id,
  created_at AS event_at
FROM episodes
UNION ALL
SELECT
  'memory_item'::text AS event_type,
  memory_id::text AS entity_id,
  created_at AS event_at
FROM memory_items
UNION ALL
SELECT
  'memory_embedding'::text AS event_type,
  memory_embedding_id::text AS entity_id,
  created_at AS event_at
FROM memory_embeddings;

COMMIT;

-- Example Grafana read-only role bootstrap.
-- Replace the password before use in a real deployment.
--
-- CREATE ROLE ctxledger_grafana
-- LOGIN
-- PASSWORD 'replace-with-a-strong-secret';
--
-- GRANT CONNECT ON DATABASE ctxledger TO ctxledger_grafana;
-- GRANT USAGE ON SCHEMA observability TO ctxledger_grafana;
-- GRANT SELECT ON ALL TABLES IN SCHEMA observability TO ctxledger_grafana;
--
-- ALTER DEFAULT PRIVILEGES IN SCHEMA observability
-- GRANT SELECT ON TABLES TO ctxledger_grafana;
--
-- REVOKE ALL ON SCHEMA public FROM ctxledger_grafana;
-- REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ctxledger_grafana;
-- REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM ctxledger_grafana;
-- REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM ctxledger_grafana;
