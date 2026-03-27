# Changelog

All notable changes to `ctxledger` are documented in this file.

The project currently follows a lightweight, human-maintained changelog style.

---

## [Unreleased]

### Added

- validated default `small` Docker deployment path with:
  - HTTPS through Traefik
  - proxy-layer authentication
  - Grafana enabled by default
  - PostgreSQL 17 as the current validated repository-owned image base
  - Apache AGE enabled by default
  - pgvector source-built with portability-oriented build flags
  - automatic canonical schema application during startup
  - automatic AGE extension setup during startup
  - automatic bootstrap of the default constrained AGE graph:
    - `ctxledger_memory`
  - automatic Grafana observability database setup during startup
- helper scripts for default local startup automation:
  - `scripts/ensure_age_extension.py`
  - `scripts/setup_grafana_observability.py`
- constrained Apache AGE prototype substrate for hierarchical memory `0.6.0`, including:
  - a narrow `supports` target lookup boundary for distinct one-hop relation lookup
  - relational baseline implementations in in-memory and PostgreSQL repositories
  - AGE capability and graph-readiness checks
  - a PostgreSQL AGE-backed one-hop `supports` lookup path
  - a narrow derived-summary graph traversal read path for summary-member expansion
  - explicit relational fallback when AGE is disabled, unavailable, unready, or the graph-backed read fails
  - config-gated prototype controls:
    - `CTXLEDGER_DB_AGE_ENABLED`
    - `CTXLEDGER_DB_AGE_GRAPH_NAME`
  - explicit prototype graph commands:
    - `ctxledger bootstrap-age-graph`
    - `ctxledger age-graph-readiness`
    - `ctxledger refresh-age-summary-graph`
- first constrained canonical summary hierarchy slice for `0.6.0`, including:
  - canonical `memory_summaries` persistence
  - canonical `memory_summary_memberships` persistence
  - summary and summary-membership repository contracts
  - in-memory and PostgreSQL summary repository implementations
  - workflow-backed summary repository wiring
  - first `memory_summary_first` retrieval path in `memory_get_context`
  - direct summary-member memory-item expansion
  - a narrow graph-backed auxiliary summary traversal path for derived summary-member lookup
  - explicit episode-scoped summary building through:
    - `ctxledger build-episode-summary`
  - replace-or-rebuild behavior for matching episode summaries
  - PostgreSQL-backed builder-to-retrieval integration coverage
- workflow-completion summary automation refinement for `0.6.0`, including:
  - explicit workflow-completion auto-memory targeting
  - trigger/policy details surfaced in additive summary-build result fields
  - non-fatal summary build behavior preserved during workflow completion
- documentation for the constrained AGE prototype boundary, setup approach, implementation plan, graph bootstrap/population model, and derived summary mirroring/readiness behavior
- hierarchy-memory design notes for:
  - minimal hierarchy model
  - first `memory_get_context` hierarchical retrieval improvement
  - minimal hierarchy schema/repository design
  - minimal summary write/build path
  - workflow summary automation direction
  - workflow summary targeting policy
  - optional AGE summary mirroring
- README guidance for the constrained AGE prototype controls, readiness checks, summary graph refresh path, and explicit summary build flow
- objective-aware task-recall continuation signals for `0.7.0`, including:
  - latest checkpoint candidate signals for:
    - `step_name`
    - `summary`
    - `current_objective`
    - `next_intended_action`
  - normalized checkpoint objective / next-action presence flags in workflow candidate ordering details
  - objective-aware task-recall ranking that can treat explicit checkpoint objective evidence as a stronger mainline signal
  - focused detour-recovery scenario coverage for mainline selection and explicit next-action continuation signals
  - structured latest-versus-selected task-recall comparison details that can surface:
    - latest considered candidate workflow id
    - selected continuation candidate workflow id
    - latest and selected checkpoint step/summary details
    - latest and selected primary-objective / next-intended-action text
    - latest and selected detour classification
    - latest and selected return-target / task-thread basis
    - latest and selected resumability-oriented signals
  - a candidate-level comparison block as the primary surface, while preserving the older checkpoint-oriented naming as a compatibility alias
  - a bounded `memory_search` task-recall bridge for workspace-scoped searches, including:
    - top-level latest-considered and selected workflow context
    - latest-versus-selected candidate comparison details in divergent multi-candidate contexts
    - top-level comparison-summary explanations for divergent contexts
    - a small selected-continuation-target bonus in divergent multi-candidate contexts

### Changed

- the default local deployment story is now centered on the authenticated `small` stack:
  - `docker/docker-compose.yml`
  - `docker/docker-compose.small-auth.yml`
- Grafana is no longer treated as an optional observability overlay for normal local use
- AGE is no longer treated as an optional local overlay for the validated `small` stack
- unauthenticated local startup is retired from the current local deployment guidance
- the repository-owned PostgreSQL image path was validated on PostgreSQL 17 after aligning the pgvector build with the upstream portability-oriented approach:
  - `make OPTFLAGS=""`
- `memory_get_context` related-item collection can now use the narrow `supports` target lookup boundary without changing the visible retrieval contract
- `memory_get_context` can now prefer canonical summaries through the first constrained `memory_summary_first` path when canonical summaries exist and summaries are enabled
- `memory_get_context` can now use a narrow graph-backed auxiliary summary traversal path to expand summary-member memory items from derived AGE graph state when available
- AGE readiness and runtime observability now surface derived summary graph mirroring details and the current workflow summary automation policy alongside graph status
- workflow-completion summary automation details now explicitly report request, trigger, scope, replace behavior, and non-fatal policy metadata in additive summary-build results
- canonical summary-first retrieval now has focused service, serializer, MCP, HTTP, and PostgreSQL integration coverage
- constrained relation-auxiliary parity was preserved across the prototype path by keeping:
  - first-seen-by-source distinct target ordering
  - relation metadata continuity for grouped relation outputs
  - relational canonical storage as the system of record
- task-recall workflow ordering can now prefer explicit checkpoint objective / next-intended-action signals before falling back to pure recency in focused continuation-selection scenarios
- task-recall ranking details now surface richer candidate-level explanation fields, including:
  - checkpoint detour classification
  - explicit checkpoint objective presence
  - explicit checkpoint next-intended-action presence
  - explicit mainline-signal presence
- task-recall detail shaping now includes a latest-versus-selected candidate comparison surface so operators and agents can inspect:
  - whether the latest considered workflow matched the selected continuation target
  - whether the latest considered checkpoint matched the selected continuation checkpoint
  - which checkpoint/objective/next-action fields differed
  - which detour and resumability signals differed
- `memory_search` now includes a bounded task-recall bridge so search results and top-level search details can expose:
  - latest considered workflow identity
  - selected continuation workflow identity
  - divergent latest-versus-selected candidate comparison details where applicable
  - bounded comparison-summary explanations for divergent contexts
  - a small selected-continuation-target ranking bonus where the selected continuation thread should be slightly preferred

### Validation

- validated repository-owned PostgreSQL 17 image behavior for the default `small` stack:
  - `CREATE EXTENSION vector;`
  - `CREATE EXTENSION age;`
  - `LOAD 'age';`
  - graph creation and constrained graph bootstrap
- validated default startup automation for:
  - canonical schema application
  - AGE extension setup
  - constrained AGE graph bootstrap
  - Grafana observability database setup
- validated MCP smoke behavior against the authenticated HTTPS endpoint
- validated runtime/debug AGE state reporting through:
  - `/debug/runtime`
  - `ctxledger age-graph-readiness`
- focused AGE prototype validation passed:
  - `python -m pytest tests/cli/test_cli_main.py tests/cli/test_cli_schema.py tests/config/test_config.py tests/postgres/test_db_helpers.py tests/memory/test_memory_context_related_items.py -q`
  - `86 passed`
- focused hierarchy and summary-builder validation passed across:
  - memory service core
  - memory context details
  - memory serialization
  - MCP memory tool handlers
  - HTTP MCP runtime transport
  - PostgreSQL repository and integration coverage
- follow-up summary hierarchy validation passed across:
  - workflow auto-memory integration
  - runtime coverage targets
  - memory service core
  - PostgreSQL memory context integration
  - `python -m pytest tests/postgres_integration/test_workflow_auto_memory_integration.py tests/runtime/test_coverage_targets_runtime.py tests/memory/test_service_core.py tests/postgres_integration/test_memory_context_integration.py -q`
  - `116 passed`
- focused contract validation passed for narrowed summary-first transport behavior across:
  - MCP memory tool handlers
  - HTTP MCP runtime transport
  - memory context detail shaping
  - `python -m pytest tests/mcp/test_tool_handlers_memory.py tests/http/test_server_http.py tests/memory/test_service_context_details.py -q`
  - `107 passed`
- CLI-focused validation passed for readiness, summary refresh, and summary build surfaces:
  - `python -m pytest tests/cli/test_cli_main.py tests/cli/test_cli_schema.py -q`
  - `84 passed`
- full repository validation passed after the final summary hierarchy closeout, transport-contract, documentation alignment, and docs-taxonomy follow-up slices:
  - `python -m pytest -q`
  - `932 passed, 1 skipped`
- `0.6.0` acceptance review now has an explicit release-facing assessment artifact:
  - `docs/project/releases/0.6.0_acceptance_review.md`
  - current reading:
    - bounded `0.6.0` summary hierarchy slice accepted
    - targeted and full validation green
    - PostgreSQL canonical behavior preserved
    - AGE boundary documented as derived and degradable
    - `0.7.0` Mnemis-oriented evaluation remains explicitly deferred
- roadmap/planning direction has now been updated so that:
  - `0.8.0` is the remember-path strengthening milestone
  - `0.9.0` is the ctxledger-and-`.rules` strengthening milestone for resumability, bounded historical progress recall, and failure-pattern avoidance
- objective-aware task-recall continuation validation passed across:
  - memory context details
  - memory query/scope behavior
  - memory service core
  - runtime task-recall helpers
  - workflow lookup coverage
  - `python -m pytest -q`
  - `966 passed, 1 skipped`

### Notes

- the current AGE work should still be read as a constrained graph-backed prototype rather than broad graph adoption
- relational PostgreSQL tables remain canonical; AGE graph state is still derived and rebuildable
- the explicit bootstrap/refresh paths remain prototype-grade and rebuild-first rather than a full graph lifecycle or incremental sync framework
- the current `0.6.0` hierarchy work should now be read as operationally closed for its intended bounded slice:
  - canonical-relational summary ownership
  - canonical summary-membership ownership
  - first constrained summary-first retrieval
  - direct summary-member memory-item expansion
  - first explicit episode-scoped summary builder
  - replace-or-rebuild summary semantics
  - a narrow optional graph-backed auxiliary summary traversal path
  - workflow-completion-oriented summary automation remaining explicit, gated, and non-fatal
  - graph support remaining optional at the summary build/read boundary
- the current retrieval contract should also be read as explicitly bounded:
  - summary-only primary-path shaping remains a primary route, not an auxiliary-only response
  - `include_episodes = false` keeps the narrower episode-less surface and does not leak episode-oriented summary-first explanation fields as placeholders
- the validated local default is now:
  - `small`
  - HTTPS
  - proxy-layer authentication
  - Grafana enabled
  - AGE enabled
  - repository-owned PostgreSQL 17 image path
- the current operator-facing summary workflow should be read as:
  - explicit `ctxledger build-episode-summary` remains the primary write path
  - `ctxledger refresh-age-summary-graph` remains the rebuild path for derived summary graph state
  - degraded or unavailable AGE summary graph state should reduce enrichment, not invalidate canonical summary correctness
- the current `0.7.0` task-recall slice should be read as:
  - objective-aware ranking layered on top of canonical checkpoint data
  - no new canonical return-target entity yet
  - explicit checkpoint objective / next-action evidence improving continuation selection without changing the canonical system-of-record boundary
  - `memory_get_context` now also has a materially richer bounded task-recall detail surface, including:
    - return-target details
    - primary-objective details
    - task-thread details
    - latest-versus-selected continuation comparison details
    - latest detour candidate details
    - prior-mainline candidate details
  - latest-versus-selected comparison details and task-thread fields should still be read as derived explanation surfaces rather than as new canonical task-thread records
  - the newer `memory_search` task-recall bridge should also be read as a derived explanation and ranking-support surface rather than as a second workflow-truth mechanism
  - bounded prior-mainline recovery and latest-detour-versus-selected-continuation separation are now part of the implemented `0.7.0` slice, even though broader milestone closeout work still remains
  - maintainability hardening for the bounded `0.7.0` slice has now completed its oversized task-recall-related source/test split stream through semantic splitting of oversized files, including:
    - runtime task-recall source splits
    - runtime task-recall test splits
    - the completed split of the oversized visibility-focused memory-context test file into:
      - `tests/memory/test_service_context_details_visibility_basic.py`
      - `tests/memory/test_service_context_details_visibility_query_filters.py`
    - the completed split of the oversized grouping-focused memory-context test file into:
      - `tests/memory/test_service_context_details_grouping_visibility.py`
      - `tests/memory/test_service_context_details_grouping_summary_routes.py`
    - the completed split of the oversized task-recall-focused memory-context test file into:
      - `tests/memory/test_service_context_details_task_recall_basics.py`
      - `tests/memory/test_service_context_details_task_recall_ordering.py`
    - the completed split of the final oversized grouping-summary-routes memory-context test file into:
      - `tests/memory/test_service_context_details_grouping_summary_routes_multiflow.py`
      - `tests/memory/test_service_context_details_grouping_summary_routes_ordering.py`
- the current `0.7.0` closeout reading should now be:
  - implementation is further along than the older “roughly `70%` complete” planning shorthand suggested
  - the intended bounded `0.7.0` retrieval-surface scope should now be read as:
    - concept-to-task recovery centered on `memory_get_context`
    - concept-to-task recovery centered on workspace-scoped `memory_search`
    - workspace-resume-facing reasoning kept as an adjacent explanation surface, not a separate concept-routing authority
  - the main remaining `0.7.0` work is now:
    - release-facing behavior summary and acceptance/closeout alignment for the bounded `0.7.0` slice
    - explicit recording that broader concept-to-task expansion beyond the bounded current surfaces is deferred past `0.7.0`
    - explicit recording that broader task-recall rollout into other retrieval surfaces is deferred past `0.7.0` unless later justified
    - continued maintainability hardening for the remaining oversized memory-context test files after the runtime, visibility, grouping, and task-recall splits already landed
- the current roadmap should now be read as:
  - `0.8.0` focusing on strengthening the remember path so completion-centered work more reliably becomes:
    - episodes
    - memory items
    - embeddings
    - memory relations
    - graph/summarization inputs
  - `0.9.0` focusing on strengthening `ctxledger` and repository `.rules` together so:
    - interrupted work can be resumed from minimal user prompts such as `resume`
    - bounded historical progress questions can be answered from durable workflow/memory state
    - previously observed failure patterns are easier for agents to surface and avoid repeating
- the remember-path problem statement for the new `0.8.0` planning slice is:
  - the system can store workflow progress correctly while still failing to accumulate enough linked memory structure
  - `memory_relations` can remain empty in otherwise healthy deployments
  - AGE graph bootstrap/refresh is downstream of canonical relational memory creation and therefore cannot compensate for a weak remember path
  - AI-agent memory capture still depends too much on discretionary or ad hoc tool usage instead of a stronger operational contract
- the planned second deployment pattern remains:
  - `large`
  - HTTPS
  - proxy-layer authentication
  - Grafana enabled
  - Azure Database for PostgreSQL
  - not implemented yet

- planned `0.5.4` follow-up hardening work for `workflow_resume` timeout diagnosis and mitigation
- roadmap/docs updates are being prepared for:
  - timeout-aware resume-path hardening
  - clearer workflow-versus-workspace identifier guidance
  - AI-agent-facing `.rules` guidance improvements to reduce incorrect `workflow_resume` usage
  - validation of whether rule/guidance changes can prevent a meaningful share of observed timeout-triggering misuse

## [0.4.0] - 2026-03-16

### Added

- operator-facing observability CLI commands:
  - `ctxledger stats`
  - `ctxledger workflows`
  - `ctxledger memory-stats`
  - `ctxledger failures`
- text and `--format json` output support for the observability CLI surfaces
- canonical workflow aggregation and listing support for observability reporting across in-memory and PostgreSQL repositories
- canonical memory statistics reporting, including:
  - episode count
  - memory item count
  - memory embedding count
  - memory relation count
  - provenance breakdown
  - latest activity timestamps
- canonical failure inspection reporting, including:
  - failure scope/type
  - lifecycle state
  - target path
  - error code and message
  - occurred/resolved timestamps
  - retry count
  - open failure count
  - attempt id when present
- optional Grafana deployment support for runtime observability, including:
  - Compose overlay support
  - datasource provisioning
  - dashboard provisioning
  - initial runtime, memory, and failure dashboards
- observability SQL bootstrap views for PostgreSQL-backed dashboarding
- Grafana operator runbook and expanded deployment guidance for read-only PostgreSQL observability access

### Changed

- the `0.4.0` milestone is now defined around observability rather than hierarchical retrieval
- README quick start was rewritten to be more user-first and self-contained for local startup, MCP access, and Grafana bring-up
- user-facing quick-start guidance now consistently favors `localhost` examples
- stale test expectations were aligned to the active `0.4.0` version across CLI, config, and server validation paths
- Grafana dashboards were polished with clearer operator-facing labels, improved legends, and timestamp-only field overrides to prevent `NaN` and epoch-like misrendering in mixed-value tables

### Validation

- focused coverage-target suite passed:
  - `python -m pytest tests/test_coverage_targets.py -q`
  - `237 passed`
- full test suite passed:
  - `python -m pytest -q`
  - `799 passed, 1 skipped`

### Notes

- the single skipped test remains expected because real OpenAI integration requires `OPENAI_API_KEY`
- `memory_search` is now reported as available in `0.4.0` in the current runtime-visible payloads
- the strongest validated embedding/runtime paths remain:
  - `openai`
  - `local_stub`
  - `custom_http`
- `voyageai` and `cohere` configuration surfaces still exist, but full provider-specific runtime support remains incomplete
- hierarchical memory retrieval remains deferred to `0.5.0`

## [0.3.0] - 2026-03-14

### Added

- implemented `memory_search` as an initial hybrid lexical and embedding-backed retrieval surface over stored memory items
- hybrid ranking that combines lexical matches with embedding similarity for memory item search results
- ranking explanation details in `memory_search` results, including lexical component, semantic component, score mode, and semantic-only discount reporting
- embedding configuration and generation scaffolding for `disabled`, `local_stub`, `openai`, `voyageai`, `cohere`, and `custom_http` provider modes
- PostgreSQL-backed memory embedding persistence and pgvector-backed similarity lookup for memory item retrieval
- MCP handler, schema, and serialization support for `memory_search`
- unit, server, MCP handler, and PostgreSQL integration coverage for the implemented `0.3.0` memory search path

### Notes

- `memory_search` now uses the active hybrid lexical and embedding-backed retrieval path over stored memory items
- validated embedding execution paths now include `openai` in addition to `local_stub` and `custom_http`
- OpenAI embedding generation was validated end-to-end against PostgreSQL persistence and semantic retrieval
- `voyageai` and `cohere` configuration surfaces exist, but their full provider-specific runtime support remains incomplete
- `memory_get_context` remains primarily episode-oriented in `0.3.0`; richer multi-layer and relation-aware context assembly remain future work
- the roadmap now treats `0.4.0` as the observability milestone for operator-facing CLI inspection and optional deployable Grafana-based dashboard support
- hierarchical memory retrieval and summary-layer expansion are planned later in `0.5.0`

## [0.2.0] - 2026-03-14

### Added

- episodic memory capture through `memory_remember_episode`, including:
  - append-only episode recording
  - `workflow_instance_id` validation
  - optional `attempt_id` validation
  - workflow existence validation
  - canonical persistence of `attempt_id` when provided
- initial episode-oriented auxiliary context retrieval through `memory_get_context`, including:
  - direct retrieval by `workflow_instance_id`
  - workflow-linked expansion by `workspace_id`
  - workflow-linked expansion by `ticket_id`
  - `limit`
  - `include_episodes`
  - initial lightweight query-aware filtering over episode summary text and explicit metadata fields
  - explicit response details covering:
    - `query`
    - `normalized_query`
    - `lookup_scope`
    - `workspace_id`
    - `workflow_instance_id`
    - `ticket_id`
    - `limit`
    - `include_episodes`
    - `include_memory_items`
    - `include_summaries`
    - `resolved_workflow_count`
    - `resolved_workflow_ids`
    - `query_filter_applied`
    - `episodes_before_query_filter`
    - `matched_episode_count`
    - `episodes_returned`
- PostgreSQL-backed episodic memory persistence and episode-oriented context retrieval
- PostgreSQL integration coverage for episodic memory and `memory_get_context`
- local/operator-facing HTTPS deployment paths for MCP access, including:
  - authenticated HTTPS proxy path on `https://localhost:8443/mcp`
  - no-auth HTTPS proxy path on `https://localhost:8444/mcp`
  - local certificate setup guidance for Traefik-based TLS termination
  - HTTPS smoke validation support for local self-signed or untrusted certificates
- verified local Zed startup guidance for both no-auth and auth HTTPS MCP configurations

### Changed

- local/operator-facing guidance now treats HTTPS proxy access as the recommended public MCP path
- the backend application service is no longer documented as a host-exposed direct local MCP endpoint
- small-auth public access now uses HTTPS on `8443`, replacing the older public HTTP path
- the base compose backend is now private to the compose network instead of being host-exposed on `8080`
- README, deployment guidance, security guidance, MCP API docs, contributing guidance, and runbooks now align with the `0.2.0` episodic-memory and HTTPS-first operator posture

### Notes

- `memory_search` remained intentionally stubbed in `0.2.0` and was deferred to later semantic retrieval work
- `memory_get_context` remains intentionally partial and episode-oriented in `0.2.0`; broader semantic, relation-aware, and later hierarchical retrieval remain future work
- `0.2.0` closes out the episodic memory milestone and establishes an HTTPS-enabled MCP deployment path after that memory closeout work