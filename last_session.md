# ctxledger last session

## Summary
This session refined workflow closeout duplicate / near-duplicate matching quality beyond plain token overlap.

The closeout matcher now extracts semantic fields from generated summaries, compares richer metadata, and uses weighted similarity that emphasizes completion summaries while further down-weighting boilerplate workflow-closeout wording.

Focused workflow-service coverage is updated for the new field-extraction and metadata-aware matching behavior. Focused PostgreSQL integration coverage is now updated as well for the new comparison dimensions.

## What is already done

### OpenAI-default embedding path
- default embedding provider is `openai`
- default embedding model is `text-embedding-3-small`
- embedding execution is still opt-in via:
  - `CTXLEDGER_EMBEDDING_ENABLED`
- OpenAI env naming is aligned around:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`
  - `OPENAI_BASE_URL`
- `docker/docker-compose.small-auth.yml` forwards `OPENAI_API_KEY`

### Validation already completed
- real PostgreSQL + OpenAI integration test passed
- broader targeted regression was previously green:
  - `485 passed, 1 skipped`

Useful command if re-running real OpenAI validation:
```/dev/null/sh#L1-1
envrcctl exec -- python -m pytest tests/test_postgres_integration.py -q -k openai
```

### Memory observability
`MemoryService.remember_episode()` surfaces embedding persistence outcomes instead of hiding failures.

Important detail fields include:
- `embedding_persistence_status`
- `embedding_generation_skipped_reason`

Possible states:
- `stored`
- `skipped`
- `failed`

### `workflow_complete` auto-memory state
The automatic workflow-completion memory path is now implemented and surfaced through:
- `warnings`
- `auto_memory_details`

Schema / persistence expectations already align with:
- `workflow_complete_auto`

## Completed Phase 2 progress

### 1. Explicit heuristic gating
`src/ctxledger/workflow/memory_bridge.py` now applies a minimum heuristic before recording closeout auto-memory.

Current behavior:
- record when latest checkpoint has explicit signal such as:
  - `next_intended_action`
  - `current_objective`
  - `decision`
  - `risk`
  - `blocker`
  - `open_question`
- also record when verification failed
- also record when workflow closed as `failed` or `cancelled`
- otherwise skip low-signal closeout memory

### 2. Skip reason split
Low-signal skips are no longer reported with only the old generic reason.

Current skip reasons now include:
- `no_completion_summary_source`
- `low_signal_checkpoint_closeout`

Intent:
- `no_completion_summary_source`
  - true missing-source case
- `low_signal_checkpoint_closeout`
  - heuristic said the closeout was too weak/noisy to record

### 3. Duplicate / near-duplicate noise control
A refined minimum noise-control pass is now in place for workflow closeout auto-memory.

Current suppression reasons include:
- `duplicate_closeout_auto_memory`
- `near_duplicate_checkpoint_closeout`

Current suppression behavior:
- suppress when the generated closeout summary is identical to recent `workflow_complete_auto` memory for the same workflow
- parse generated closeout summaries into meaningful comparison fields where available:
  - `completion_summary`
  - `latest_checkpoint_summary`
  - `next_intended_action`
  - `verify_status`
  - `workflow_status`
  - `attempt_status`
  - `failure_reason`
- keep near-duplicate matching scoped to recent auto-memory for the same workflow and same `step_name`
- require metadata-aware matching across:
  - `next_intended_action`
  - `verify_status`
  - `workflow_status`
  - `attempt_status`
  - `failure_reason`
- near-duplicate matching is limited to a recent lookback window:
  - `6 hours`
- near-duplicate matching now uses weighted field-aware similarity in addition to completion-summary token similarity
  - completion summary is weighted most heavily
  - latest checkpoint summary and next action also contribute materially
  - status fields and failure reason participate with lighter weights
- boilerplate workflow-closeout tokens are still heavily discounted before token scoring
  - examples include:
    - `workflow`
    - `completed`
    - `summary`
    - `status`
    - `verify`
    - `latest`
    - `checkpoint`
    - `line`
    - `lines`

This is still intentionally a pragmatic refinement, not a final similarity model, but the current matcher refinement is now validated in both workflow-service and PostgreSQL-focused coverage.

## Validation completed for Phase 2

### Focused workflow-service / bridge tests
`tests/test_workflow_service.py`
- high-signal record path
- low-signal skip path
- verify-failed forced record path
- duplicate suppression
- near-duplicate suppression
- old closeout outside lookback window is not treated as near-duplicate
- differing `verify_status` is not treated as near-duplicate
- high summary similarity suppresses near-duplicate closeout
- boilerplate-heavy summary overlap still suppresses when the meaningful summary content is effectively the same
- low summary similarity still records closeout
- extracted semantic closeout fields are compared directly
- differing `attempt_status` is not treated as near-duplicate
- differing `failure_reason` is not treated as near-duplicate
- weighted field-aware matching can still suppress closeouts when the meaningful completion content is effectively the same

Focused result for the closeout matching refinement subset:
```/dev/null/txt#L1-1
10 passed, 60 deselected
```

### Focused PostgreSQL integration coverage
`tests/test_postgres_integration.py`

Covered through focused integration tests:
- high-signal closeout records memory and embedding
- closeout auto-memory is searchable
- low-signal closeout skips with:
  - `low_signal_checkpoint_closeout`
- duplicate closeout suppresses with:
  - `duplicate_closeout_auto_memory`
- near-duplicate closeout suppresses with:
  - `near_duplicate_checkpoint_closeout`
- high summary similarity suppresses near-duplicate closeout
- boilerplate-heavy summary overlap still suppresses when the meaningful summary content is effectively the same
- low summary similarity still records closeout
- old closeout outside the lookback window is not treated as near-duplicate
- differing `verify_status` is not treated as near-duplicate

Focused PostgreSQL integration coverage now also includes:
- extracted semantic closeout fields can participate in near-duplicate suppression
- differing `attempt_status` is not treated as near-duplicate
- differing `failure_reason` is not treated as near-duplicate
- weighted field-aware matching can still suppress closeouts when the meaningful completion content is effectively the same

Focused result after the metadata-aware and weighted matcher refine coverage update:
```/dev/null/txt#L1-1
9 passed, 33 deselected
```

## Immediate restart point
The workflow-service and PostgreSQL-focused closeout matching refinement is now implemented and validated for extracted fields, richer metadata-aware comparison, and weighted similarity.

The next useful step is to decide whether the current weighted field-aware heuristic is sufficient or whether matcher quality should be pushed further.

## Recommended next steps
1. decide whether duplicate suppression should remain scoped only to the same workflow
   - current behavior is workflow-local
2. optionally extend operator-facing docs
   - explain auto-memory skip reasons
   - explain duplicate suppression reasons
   - explain the lookback-window behavior
   - explain weighted closeout similarity behavior
   - explain semantic field extraction and boilerplate discounting
3. if needed later, add broader regression coverage around these reasons in handler/server-level tests
4. if matcher quality still feels weak in practice, consider a stronger similarity model beyond the current weighted heuristic

## Important files
- `src/ctxledger/config.py`
- `src/ctxledger/memory/service.py`
- `src/ctxledger/workflow/memory_bridge.py`
- `src/ctxledger/workflow/service.py`
- `tests/test_workflow_service.py`
- `tests/test_postgres_integration.py`
- `docker/docker-compose.small-auth.yml`

## Known commit/history anchor
Existing commit from the OpenAI validation pass:
- `68fa351` `Validate OpenAI embedding integration end to end`

## Operational reminders
- ignore untracked cert files
- treat pasted API keys as exposed; prefer env injection / secret handling
- the focused PostgreSQL refine checks validated in this session are:
  - `python -m pytest tests/test_postgres_integration.py -q -k 'near_duplicate or old_closeout or verify_status'`
  - `python -m pytest tests/test_postgres_integration.py -q -k 'summary_similarity or near_duplicate or old_closeout or verify_status'`
  - `python -m pytest tests/test_postgres_integration.py -q -k 'boilerplate or summary_similarity or near_duplicate'`
- important implementation detail for the PostgreSQL old-closeout test:
  - persisted auto-memory episodes live in the `episodes` table, not a separate `memory_episodes` table
- important implementation details for the current closeout matching refinement:
  - near-duplicate suppression still uses a completion-summary token similarity threshold of `0.75`
  - generated closeout summaries are parsed into semantic fields when possible
  - weighted field-aware similarity currently uses a threshold of `0.7`
  - completion summary is weighted most heavily, with lighter weights for checkpoint summary, next action, statuses, and failure reason
  - a small ignored-token set reduces false similarity from boilerplate closeout wording

## Continuation note
The closeout matcher itself is now refined and validated in both workflow-service and PostgreSQL-focused coverage:
- semantic fields are extracted from generated summaries
- metadata-aware comparison now includes `workflow_status`, `attempt_status`, and `failure_reason`
- weighted similarity emphasizes completion summary content and further discounts boilerplate lines/tokens

Focused workflow-service validation is green:
- `python -m pytest tests/test_workflow_service.py -q -k 'near_duplicate or summary_similarity or boilerplate or metadata_aware or attempt_status or failure_reason or semantic_fields'`

Focused PostgreSQL integration validation is green:
- `python -m pytest tests/test_postgres_integration.py -q -k 'near_duplicate or summary_similarity or boilerplate or metadata_aware or attempt_status or failure_reason'`

If continuing next:
- decide whether the heuristic is now good enough
- otherwise pursue a stronger similarity model and/or broader operator-facing docs
