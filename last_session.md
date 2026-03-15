# ctxledger last session

## Session summary
This work loop finished the OpenAI-default embedding integration validation and cleanup pass for `ctxledger`, and a follow-up doc-alignment pass corrected stale repository docs that still understated current memory and embedding support. It also recovered and extended an interrupted uncommitted workstream for automatic workflow-completion memory capture.

Main outcomes:
- OpenAI remains the default embedding provider in config.
- Real OpenAI embedding generation was validated end-to-end against PostgreSQL persistence and semantic retrieval.
- `remember_episode` now exposes embedding persistence outcomes instead of hiding failures.
- OpenAI-related environment variable naming was standardized toward common OpenAI conventions where appropriate.
- The broader targeted regression suite is green.
- `README.md`, `docs/CHANGELOG.md`, `docs/deployment.md`, and `docs/roadmap.md` now reflect the current implemented state for `memory_search`, semantic retrieval, and validated OpenAI embedding support.
- An interrupted, uncommitted `workflow_complete` auto-memory workstream was identified from the working tree, recovered to a targeted-pass state, and extended with explicit auto-memory failure surfacing plus retrieval proof through `memory_search`.

---

## Recently completed

### `memory_get_context` / context assembly state retained
The previously completed `memory_get_context` work remains in place:

- improved explanation / narrowing / candidate ordering
- token-aware query matching
- workspace / ticket intersection narrowing
- workflow candidate ordering based on `workflow_freshness_signals`
- expanded detail contract for:
  - `include_memory_items`
  - `include_summaries`
- serializer default backfill behavior for detail fields

### OpenAI embedding integration completed and validated
Implemented and validated:

- config default provider is `openai`
- default embedding model is `text-embedding-3-small`
- embedding execution is still explicitly opt-in through:
  - `CTXLEDGER_EMBEDDING_ENABLED`
- OpenAI runtime request path targets:
  - `https://api.openai.com/v1/embeddings`
- OpenAI request payload uses:
  - `input`
  - `model`
- OpenAI response parsing reads:
  - `data[0].embedding`

### Observability improvement added
`src/ctxledger/memory/service.py`

`MemoryService.remember_episode()` no longer hides embedding-generation failures silently.

`_maybe_store_embedding()` now returns structured outcome details.

Current remembered-episode embedding detail contract:
- always includes:
  - `embedding_persistence_status`
  - `embedding_generation_skipped_reason`
- on success also includes:
  - `embedding_provider`
  - `embedding_model`
  - `embedding_vector_dimensions`
  - `embedding_content_hash`
- on failure also includes:
  - `embedding_generation_failure`
    - `provider`
    - `message`
    - `details`

Current outcome states:
- `stored`
- `skipped`
- `failed`

Current non-configured skip reason:
- `embedding_persistence_not_configured`

Current provider failure reason shape:
- `embedding_generation_failed:{provider}`

Why this mattered:
- episode persistence can still succeed even if embedding generation fails
- memory item persistence can still succeed even if embedding generation fails
- now the failure is visible and debuggable instead of silent

---

## Environment variable unification

### Standardized names now in use
OpenAI-related credentials / external-test env names were standardized where applicable:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`

### Intentionally unchanged app-specific settings
These remain `ctxledger`-specific and are not meant to be renamed:

- `CTXLEDGER_EMBEDDING_ENABLED`
- `CTXLEDGER_EMBEDDING_PROVIDER`
- `CTXLEDGER_EMBEDDING_MODEL`
- `CTXLEDGER_EMBEDDING_BASE_URL`

Rationale:
- vendor credential / endpoint naming uses common OpenAI conventions
- application feature flags and provider-selection controls remain namespaced to `ctxledger`

### Places updated
The env naming cleanup touched:

- `src/ctxledger/config.py`
- `tests/test_config.py`
- `tests/test_postgres_integration.py`
- `docker/docker-compose.small-auth.yml`
- `docs/plans/openai_default_embedding_integration_plan.md`
- this `last_session.md`

---

## Container / env propagation findings

### What was confirmed
There was an earlier session-phase where the shell environment and runtime container environment were not aligned.

After cleanup and restart, the following was confirmed:

- `OPENAI_API_KEY` is visible when commands are run under the env-injection wrapper
- `OPENAI_API_KEY` is now also present inside the running `ctxledger-server-private` container

That required explicit compose wiring.

### Compose wiring added
`docker/docker-compose.small-auth.yml`

`ctxledger-private` now forwards:

- `OPENAI_API_KEY: ${OPENAI_API_KEY}`

### Important operational lesson
Having a variable visible in the shell used to launch compose does **not** by itself prove that the container runtime environment receives it.
The compose service must explicitly forward the variable.

---

## How to verify real embedding generation and PostgreSQL persistence

### Primary verification command
Use the existing real integration test:

```/dev/null/sh#L1-1
envrcctl exec -- python -m pytest tests/test_postgres_integration.py -q -k openai
```

What this test validates:
1. workflow / episode / memory item persistence
2. real OpenAI embedding generation
3. `memory_embeddings` rows are stored in PostgreSQL
4. `memory_search` exercises the semantic / hybrid retrieval path

### Expected successful result
Typical success shape:

```/dev/null/txt#L1-2
.
1 passed
```

### Broader targeted regression command
For the broader targeted suite:

```/dev/null/sh#L1-1
python -m pytest tests/test_config.py tests/test_coverage_targets.py tests/test_server.py tests/test_mcp_tool_handlers.py tests/test_postgres_integration.py -q
```

Known result from this session:

- `485 passed, 1 skipped`

### Optional direct DB verification
If you want to inspect rows manually in the running PostgreSQL container:

```/dev/null/sh#L1-1
docker exec -it ctxledger-postgres psql -U ctxledger -d ctxledger
```

Example query:

```/dev/null/sql#L1-3
SELECT memory_id, embedding_model, created_at
FROM memory_embeddings
ORDER BY created_at DESC
LIMIT 20;
```

Caution:
- the integration tests use temporary schemas
- some test-created data may be cleaned up automatically
- if manual inspection is the goal, prefer a fixed-schema/manual-flow or a temporary helper script

---

## Ordering / details still in effect

`src/ctxledger/memory/service.py`

When `workflow_instance_id` is specified:
- `ordering_basis = "workflow_instance_id_priority"`

Otherwise:
- `ordering_basis = "workflow_freshness_signals"`

Current `signal_priority`:
1. `workflow_is_terminal`
2. `latest_attempt_is_terminal`
3. `has_latest_attempt`
4. `has_latest_checkpoint`
5. `latest_checkpoint_created_at`
6. `latest_verify_report_created_at`
7. `latest_projection_canonical_update_at`
8. `latest_projection_successful_write_at`
9. `projection_open_failure_count`
10. `latest_episode_created_at`
11. `latest_attempt_started_at`
12. `workflow_updated_at`
13. `resolver_order`

Visible in `candidate_signals`:
- `workflow_status`
- `workflow_is_terminal`
- `latest_attempt_status`
- `latest_attempt_is_terminal`
- `has_latest_attempt`
- `latest_attempt_verify_status`
- `has_latest_checkpoint`
- `latest_checkpoint_created_at`
- `latest_verify_report_created_at`
- `latest_projection_canonical_update_at`
- `latest_projection_successful_write_at`
- `projection_open_failure_count`
- `latest_episode_created_at`
- `latest_attempt_started_at`
- `workflow_updated_at`

Notes:
- behavior still prioritizes non-terminal workflows / non-terminal latest attempts over terminal ones
- `projection_open_failure_count` is still a tie-break key after projection freshness and before episode recency
- returned episodes remain globally ordered by descending `created_at`

---

## Context detail / serializer contract still covered

`src/ctxledger/memory/service.py`

- `include_episodes=False`
  - returns:
    - `episode_explanations: []`
    - `memory_items: []`
    - `memory_item_counts_by_episode: {}`
    - `summaries: []`

- `include_memory_items=True`, `include_summaries=True`
  - returns full `memory_items`
  - returns per-episode `memory_item_counts_by_episode`
  - returns `summaries`

- `include_memory_items=False`, `include_summaries=False`
  - still returns:
    - `memory_items: []`
    - `memory_item_counts_by_episode` with per-episode counts
    - `summaries: []`

- `include_memory_items=False`, `include_summaries=True`
  - returns:
    - `memory_items: []`
    - populated `memory_item_counts_by_episode`
    - populated `summaries`

- `include_memory_items=True`, `include_summaries=False`
  - returns:
    - populated `memory_items`
    - populated `memory_item_counts_by_episode`
    - `summaries: []`

`src/ctxledger/runtime/serializers.py`

- `serialize_get_context_response()` still backfills default empty collections when missing from `response.details`:
  - `memory_items`
  - `memory_item_counts_by_episode`
  - `summaries`

---

## Test coverage updated / relevant

### `tests/test_config.py`
- defaults expect:
  - `provider = openai`
  - `model = text-embedding-3-small`
- external embedding provider validation now references:
  - `OPENAI_API_KEY`

### `tests/test_coverage_targets.py`
- OpenAI generator construction coverage added
- OpenAI request/response payload coverage added
- memory-service-level persistence coverage updated for external embedding path
- one assertion was updated to reflect the new embedding observability fields in `remember_episode.details`

### `tests/test_postgres_integration.py`
Real external OpenAI integration fixtures now use:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`

Real end-to-end test present:
- `test_postgres_memory_remember_episode_and_search_with_real_openai_embeddings`

---

## Validation status

### Focused validations completed
- `tests/test_coverage_targets.py -k "persists_openai_embedding_after_memory_item_ingest or persists_local_stub_embedding_after_memory_item_ingest"`
- `tests/test_postgres_integration.py -k "local_stub_embedding or custom_http_embedding"`

Result:
- passed

### Real external OpenAI validation completed
- `python -m pytest tests/test_postgres_integration.py -q -k openai`

Result:
- passed

### Broader targeted regression completed
- `tests/test_config.py`
- `tests/test_coverage_targets.py`
- `tests/test_server.py`
- `tests/test_mcp_tool_handlers.py`
- `tests/test_postgres_integration.py`

Result:
- `485 passed, 1 skipped`

---

## Commit created
Working set was committed as:

- `68fa351` `Validate OpenAI embedding integration end to end`

This commit included:
- OpenAI integration validation
- embedding observability improvement
- env-name unification
- compose wiring for `OPENAI_API_KEY`
- doc / handoff cleanup

---

## Current repo state
At session close:

- main implementation work is committed
- follow-up doc alignment updated:
  - `README.md`
  - `docs/CHANGELOG.md`
  - `docs/deployment.md`
  - `docs/roadmap.md`
- interrupted auto-memory work has now been recovered and extended in the current implementation:
  - `src/ctxledger/workflow/memory_bridge.py`
  - `src/ctxledger/workflow/service.py`
  - `src/ctxledger/runtime/server_factory.py`
  - `src/ctxledger/mcp/tool_handlers.py`
  - `tests/test_coverage_targets.py`
  - `tests/test_server.py`
  - `tests/test_mcp_tool_handlers.py`
  - `tests/test_postgres_integration.py`
  - `schemas/postgres.sql`
- current recovered state:
  - fixed targeted test wiring away from env-dependent service construction for the targeted integration path
  - aligned schema provenance constraint with `workflow_complete_auto`
  - aligned the targeted PostgreSQL integration test with the actual local-stub bridge wiring used there
  - added structured `workflow_complete` auto-memory surfacing through:
    - `warnings`
    - `auto_memory_details`
  - added targeted PostgreSQL proof that `workflow_complete_auto` memory is retrievable through `memory_search`
- workflow is complete in canonical tracking
- untracked cert files are still ignorable:
  - `docker/traefik/certs/localhost.crt`
  - `docker/traefik/certs/localhost.key`

If more work appears after this, start a new workflow rather than continuing the completed one.

---

## Security note
A real OpenAI API key was pasted during this session.

Status:
- the user later stated the key was rotated

Still worth remembering:
- treat any key pasted into chat/session logs as exposed
- prefer env injection / secret manager paths over manual inline values

---

## Natural next candidates
1. Decide whether the `workflow_complete` auto-memory integration path should keep the current local-stub-focused targeted test shape or be rewritten to validate the default OpenAI runtime path explicitly.
2. If desired, add a tiny operator-facing helper script or docs snippet for:
   - running the real OpenAI integration test
   - manually inspecting `memory_embeddings`
3. Review any remaining docs outside `README.md`, `docs/CHANGELOG.md`, `docs/deployment.md`, `docs/roadmap.md`, and the updated plan file for outdated embedding-support wording or env names.
4. If another embedding provider is next, extend the same provider-specific pattern used for OpenAI.
5. If Azure/OpenAI-compatible support matters soon, clarify header/auth compatibility explicitly.
6. For Phase 2 of `automatic_multilayer_memory_plan.md`, design checkpoint auto-memory heuristics and noise controls before implementation.

---

## Shortest restart memo for next time
- OpenAI is the default embedding provider in config, while embedding execution is still explicitly opt-in
- OpenAI runtime request handling is implemented against `/v1/embeddings`
- `remember_episode` now surfaces embedding persistence outcome details instead of silently hiding failures
- OpenAI env naming was standardized where appropriate:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`
  - `OPENAI_BASE_URL`
- `ctxledger-private` compose wiring now forwards `OPENAI_API_KEY`
- real PostgreSQL + OpenAI integration test passes
- broader targeted regression is green:
  - `485 passed, 1 skipped`
- stale doc wording was aligned with current implementation in:
  - `README.md`
  - `docs/CHANGELOG.md`
  - `docs/deployment.md`
  - `docs/roadmap.md`
- `workflow_complete` auto-memory work is now recovered and extended:
  - target files:
    - `src/ctxledger/workflow/memory_bridge.py`
    - `src/ctxledger/workflow/service.py`
    - `src/ctxledger/runtime/server_factory.py`
    - `src/ctxledger/mcp/tool_handlers.py`
    - `tests/test_coverage_targets.py`
    - `tests/test_server.py`
    - `tests/test_mcp_tool_handlers.py`
    - `tests/test_postgres_integration.py`
    - `schemas/postgres.sql`
  - targeted recovery and extension points confirmed:
    - schema allows `workflow_complete_auto` provenance
    - targeted PostgreSQL integration test for `workflow_complete_auto` passes
    - targeted workflow bridge / factory coverage passes
    - `workflow_complete` success payload now surfaces:
      - `warnings`
      - `auto_memory_details`
    - targeted handler tests for workflow completion surfacing pass
    - targeted PostgreSQL proof that `workflow_complete_auto` memory is retrievable through `memory_search` passes
- commit created:
  - `68fa351 Validate OpenAI embedding integration end to end`
- if testing real persistence again, use:
  - `envrcctl exec -- python -m pytest tests/test_postgres_integration.py -q -k openai`
- ignore untracked cert files

embedding 生成トリガー一覧
### 生成する
- `memory_remember_episode`
  - 内部的には `MemoryService.remember_episode()`
  - その中で:
    - memory item 作成
    - `_maybe_store_embedding()`
    - `memory_embeddings` への保存
  - まで進みます

### 生成しない
以下は embedding 生成トリガーではありません。

- `workspace_register`
- `workflow_start`
- `workflow_resume`
- `workflow_checkpoint`
- `workflow_complete`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_get_context`
- `memory_search`

---

## `memory_search` は生成しないの？
少しだけ補足すると、**保存用 embedding は生成しません**。  
ただし `memory_search` は semantic search 用に **クエリ embedding** をその場で生成することがあります。

つまり:

- `memory_remember_episode`
  - **memory item の embedding を保存**
- `memory_search`
  - **検索クエリ用 embedding を一時生成**
  - でも通常は DB に保存しない

---

## 2種類の embedding
整理すると、今の `ctxledger` には embedding の使い方が 2 つあります。

### 1. 永続化される embedding
用途:
- memory item の意味検索用 index

トリガー:
- `memory_remember_episode`

保存先:
- PostgreSQL の `memory_embeddings`

### 2. 一時的な query embedding
用途:
- `memory_search` の semantic / hybrid retrieval

トリガー:
- `memory_search`

保存:
- 通常しない

---

## `.rules` 運用で重要なこと
`.rules` は memory tool 利用を推奨していますが、embedding 蓄積という観点では次が重要です。

### embedding を蓄積したいなら
AI エージェントは、作業知見を残すときに **`memory_remember_episode` を使う必要があります**。

### workflow だけでは足りない
たとえば以下だけでは embedding は増えません。

- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

この場合、workflow の canonical state は残るけど、semantic memory index は増えないです。

---

## 運用上の実務的な見方
もしあなたが
> AI エージェントが ctxledger を使うだけで記憶がどんどん semantic search 対応になるのか

を気にしているなら、答えは:

- **workflow tool だけではならない**
- **memory_remember_episode をちゃんと使う運用ならなる**

です。

---

## 望ましいエージェント行動
embedding 蓄積まで含めて `.rules` をうまく活かすなら、各 work loop で例えばこういう流れが理想です。

1. `workspace_register`
2. `workflow_resume` or `workflow_start`
3. `workflow_checkpoint`
4. 実作業
5. 学びや判断を `memory_remember_episode`
6. 検証
7. `workflow_checkpoint`
8. `workflow_complete`

この 5 があると semantic memory が育ちます。

---

## 今後の改善余地
もし「workflow checkpoint からも自動で embedding を残したい」という思想なら、将来はこういう設計もありえます。

- `workflow_checkpoint` 完了時に自動 episode 化
- checkpoint summary から memory item を派生生成
- projection 書き込み時に memory 更新
- workflow closeout 時に自動 summary memory を作成

ただし **現状はそうなっていません**。  
今は明示的に `memory_remember_episode` を使ったときが主トリガーです。

---

必要なら次に、  
**「AI エージェントが `.rules` に従って embedding を確実に残すための実践プロンプト指針」** をまとめます。
