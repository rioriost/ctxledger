# OpenAI-Default External Embedding Integration Plan

## 1. Purpose

This document defines the implementation plan for making external embedding generation the default path for `ctxledger`, with OpenAI as the default provider, while preserving the ability to switch to other compatible providers such as Azure OpenAI.

The intended operator experience is:

- OpenAI should be the default embedding provider
- supplying only an OpenAI API key should be enough to get a working default embedding path
- the design should continue to support provider or endpoint substitution without forcing a rewrite of the embedding subsystem

This plan is intentionally focused on implementation shape, configuration behavior, testing strategy, and release implications. It is not a general product roadmap document.

---

## 2. Current Situation

At the time of writing, the embedding subsystem has these properties:

- embedding generation is disabled by default
- `local_stub` exists and is useful for deterministic development/test coverage
- `custom_http` is the only concrete external execution path
- `openai`, `voyageai`, and `cohere` exist as configuration values, but their runtime integrations are not implemented
- semantic retrieval claims for `0.3.0` are therefore stronger at the architectural/foundation level than at the default operator path level

This creates an implementation/documentation gap:

- the project can persist embeddings and use pgvector-backed similarity lookup
- but the default runtime path does not generate real embeddings
- and the provider users most naturally expect, OpenAI, is not directly wired end-to-end

This plan closes that gap.

---

## 3. Target Outcome

After this plan is implemented, the desired behavior is:

1. `ctxledger` defaults to an OpenAI embedding integration
2. operators can enable real embedding generation by setting only:
   - `CTXLEDGER_EMBEDDING_ENABLED=true`
   - `CTXLEDGER_EMBEDDING_API_KEY=...`
3. OpenAI requests are sent to the correct embeddings endpoint with the correct request shape
4. OpenAI responses are parsed into the internal `EmbeddingResult`
5. semantic retrieval can be validated end-to-end against a real external embedding API
6. endpoint override remains possible for Azure OpenAI and other compatible deployments
7. `local_stub` remains available for deterministic local and CI scenarios where external dependency is undesirable

---

## 4. Non-Goals

This plan does not aim to:

- remove `local_stub`
- remove `custom_http`
- fully implement every listed provider family at once
- redesign ranking behavior in `memory_search`
- add graph memory or hierarchical context retrieval
- claim that all external providers are equally mature
- make external embedding generation mandatory for every environment

---

## 5. Guiding Principles

## 5.1 Real embeddings should have a first-class default path

The project should not require users to discover a generic compatibility mode before they can use a mainstream provider.

## 5.2 Configuration should stay explicit but low-friction

The default provider can be OpenAI without requiring a large number of settings for the common case.

## 5.3 Endpoint override must remain possible

The implementation should not hard-code OpenAI in a way that prevents Azure OpenAI or compatible endpoint substitution.

## 5.4 Development/test determinism still matters

`local_stub` remains useful for isolated tests and should not be removed just because the default external provider changes.

## 5.5 Release claims must track actual implementation

Once this work lands, docs and changelog language should clearly distinguish:
- implemented OpenAI-default embedding execution
- compatible endpoint override support
- any remaining provider-specific gaps

---

## 6. Proposed Configuration Model

## 6.1 Default provider behavior

Change default embedding settings so that:

- `CTXLEDGER_EMBEDDING_PROVIDER` defaults to `openai`
- the default model is an OpenAI embedding model, such as:
  - `text-embedding-3-small`
- the default base URL for OpenAI remains:
  - `https://api.openai.com/v1`

Recommended default behavior:

- `CTXLEDGER_EMBEDDING_ENABLED` should remain an explicit boolean switch
- when enabled and no provider is specified, OpenAI is assumed
- when enabled and only `CTXLEDGER_EMBEDDING_API_KEY` is supplied, the default OpenAI path works

This preserves safe startup behavior while still making OpenAI the default provider.

### Recommendation

Use this default model:

- `CTXLEDGER_EMBEDDING_MODEL=text-embedding-3-small`

Rationale:
- strong default for cost/performance balance
- simple operator story
- good match for an initial external embedding baseline

---

## 6.2 Preserve endpoint override support

The OpenAI integration should allow `CTXLEDGER_EMBEDDING_BASE_URL` override.

This supports:

- Azure OpenAI
- proxy/gateway mediation
- OpenAI-compatible internal services
- future controlled vendor substitutions

The implementation should treat the base URL as the provider endpoint root or direct embeddings endpoint according to a clearly documented rule.

### Preferred rule

For `openai`, use:

- default base URL root: `https://api.openai.com/v1`
- request target: append `/embeddings` unless the implementation explicitly chooses to store the full endpoint URL instead

For compatibility-oriented providers like Azure OpenAI, prefer one of these implementation approaches:

#### Option A: full endpoint URL override
Allow `CTXLEDGER_EMBEDDING_BASE_URL` to be the exact embeddings endpoint.

Pros:
- simplest override logic
- easiest support for Azure-style paths and query strings

Cons:
- slightly less uniform than a root-url model

#### Option B: provider-specific endpoint construction
Introduce provider-specific path assembly rules.

Pros:
- cleaner abstraction for well-known providers

Cons:
- more complexity now
- likely unnecessary for the first OpenAI-default delivery

### Recommendation

Use **Option A** for initial implementation:
- for `openai`, default internally to `https://api.openai.com/v1/embeddings`
- if `CTXLEDGER_EMBEDDING_BASE_URL` is set, use it as the exact endpoint URL

This keeps Azure/OpenAI-compatible override possible with minimal additional abstraction.

---

## 7. Required Implementation Changes

## 7.1 Config defaults

Update configuration defaults in `src/ctxledger/config.py` so that:

- default provider becomes `openai`
- default model becomes `text-embedding-3-small`
- `enabled` may remain default `false` unless product policy changes otherwise

### Recommended final default values

- provider: `openai`
- model: `text-embedding-3-small`
- base URL: `None` at config level, resolved to OpenAI endpoint in integration logic
- enabled: `false`

This means:
- OpenAI is the default provider identity
- external execution is still opt-in
- only API key is needed for the common enabled case

---

## 7.2 Implement OpenAI request execution

Add a concrete runtime path for `EmbeddingProvider.OPENAI`.

The request payload should follow OpenAI embeddings API expectations, using:

- `input`
- `model`

Optional metadata should not be assumed to be accepted by the OpenAI embeddings API request schema unless explicitly verified. Internal metadata remains useful for content hashing but should not necessarily be sent upstream.

### Proposed request payload

```/dev/null/json#L1-4
{
  "input": "normalized text",
  "model": "text-embedding-3-small"
}
```

### Proposed headers

```/dev/null/http.txt#L1-3
Authorization: Bearer <API_KEY>
Content-Type: application/json
Accept: application/json
```

### Expected response parsing

Primary expected source:
- `data[0].embedding`

Optional parsed model:
- top-level `model`, if present
- otherwise requested model

---

## 7.3 Restructure external generator logic

The current `ExternalAPIEmbeddingGenerator` should evolve so that:

- `openai` uses provider-specific request/response handling
- `custom_http` continues to support the generic compatibility contract
- future providers can plug in without overloading a single generic request shape

### Recommended shape

Retain a shared external generator object if desired, but separate provider-specific methods such as:

- `_generate_openai(...)`
- `_generate_custom_http(...)`

If needed later:
- `_generate_voyageai(...)`
- `_generate_cohere(...)`
- `_generate_azure_openai(...)` or Azure-compatible handling via endpoint override

The important point is to stop routing OpenAI through the generic `custom_http` payload shape.

---

## 7.4 Clarify Azure OpenAI compatibility story

Azure OpenAI support should remain possible without requiring a separate provider enum in the first iteration.

### Initial compatibility posture

Support Azure-like configuration through:

- `CTXLEDGER_EMBEDDING_PROVIDER=openai`
- `CTXLEDGER_EMBEDDING_BASE_URL=<full Azure embeddings endpoint>`
- `CTXLEDGER_EMBEDDING_API_KEY=<Azure API key>`

This may require:
- custom header support in a later phase if Azure requires `api-key` instead of bearer auth
- or a documented note that full Azure compatibility is not complete until alternate auth/header strategy is added

### Recommendation

For the first implementation phase:
- preserve endpoint override
- document that endpoint override is intended to keep Azure compatibility reachable
- explicitly track auth/header differences as a follow-up if necessary

If Azure compatibility must be complete immediately, add configurable header mode support:
- bearer token mode
- custom API key header mode

But this is optional unless required for immediate operator use.

---

## 8. Testing Plan

## 8.1 Unit tests

Add or update unit coverage for:

- config defaults now resolving provider/model toward OpenAI defaults
- OpenAI request payload construction
- OpenAI response parsing from `data[0].embedding`
- error handling for:
  - missing API key
  - invalid JSON
  - HTTP error
  - malformed response payload
- base URL override handling

---

## 8.2 Integration tests with real external API

This is the most important addition.

At least one opt-in integration path should use a real external embedding API so that we can honestly claim:

- external embedding generation works
- pgvector-backed semantic retrieval is exercised with real embeddings

### Required environment variables for external integration tests

At minimum:

- `CTXLEDGER_OPENAI_TEST_API_KEY`

Optionally:
- `CTXLEDGER_OPENAI_TEST_MODEL`
- `CTXLEDGER_OPENAI_TEST_BASE_URL`

### Test behavior

The integration test should:

1. enable embeddings
2. configure provider as OpenAI
3. inject API key
4. record memory items / episodes
5. confirm embeddings are persisted to PostgreSQL
6. run `memory_search`
7. confirm semantic candidate generation and ranking path are actually exercised

### Important guardrail

These tests should be:
- opt-in
- skipped automatically when the API key is absent

This keeps standard CI reliable while still providing a truthful external verification path.

---

## 8.3 PostgreSQL + real embedding end-to-end

The strongest proof should combine:

- PostgreSQL persistence
- embedding generation
- pgvector similarity lookup
- `memory_search` result assembly

If only request/response mocking is used, release language should remain more cautious.

---

## 8.4 Existing deterministic tests should remain

Retain:
- `local_stub` deterministic tests
- disabled-mode tests
- generic `custom_http` parsing tests

These still provide important fast feedback and non-network coverage.

---

## 9. Documentation Changes Required After Implementation

Once implementation lands, update:

- `README.md`
- `docs/roadmap.md`
- `docs/CHANGELOG.md`
- `docs/mcp-api.md`
- any operator/deployment docs that mention embedding configuration

### Required message updates

#### README
Clarify that:
- OpenAI is the default external embedding path
- only API key is needed for the default enabled path
- endpoint override is available for compatible alternatives

#### Roadmap
Update `0.3` wording so it no longer sounds like OpenAI is only a config placeholder if real execution is now implemented.

#### Changelog
Add entries describing:
- OpenAI-default embedding execution
- real external embedding validation
- endpoint override compatibility

#### API/ops docs
Show the minimal config:

```/dev/null/sh#L1-3
export CTXLEDGER_EMBEDDING_ENABLED=true
export CTXLEDGER_EMBEDDING_API_KEY=your_openai_api_key
export CTXLEDGER_EMBEDDING_PROVIDER=openai
```

Optional override example:

```/dev/null/sh#L1-2
export CTXLEDGER_EMBEDDING_BASE_URL=https://your-compatible-endpoint.example.com/embeddings
export CTXLEDGER_EMBEDDING_API_KEY=your_provider_key
```

---

## 10. Suggested Implementation Phases

## Phase 1: OpenAI-default runtime support
- change config defaults toward OpenAI
- implement OpenAI request execution
- keep `enabled=false` default unless policy changes
- preserve `local_stub` and `custom_http`

## Phase 2: Real external integration verification
- add opt-in external API integration test
- validate PostgreSQL + pgvector + semantic search path end-to-end

## Phase 3: Compatibility hardening
- verify endpoint override story
- decide whether Azure auth/header differences require configurable header mode
- document supported compatibility boundaries honestly

## Phase 4: Release wording cleanup
- align all release-facing docs with actual implementation state
- ensure semantic claims are backed by tested execution paths

---

## 11. Risks

## 11.1 External dependency risk
Real embedding tests depend on:
- network
- API availability
- API billing/quota
- secret management

Mitigation:
- keep such tests opt-in

## 11.2 Default surprise risk
If users enable embeddings without reading docs, OpenAI default behavior may surprise them.

Mitigation:
- document clearly
- keep provider override explicit
- keep enablement explicit

## 11.3 Compatibility ambiguity risk
“Other APIs such as Azure OpenAI” can mean:
- endpoint compatibility only
- full request/auth compatibility

Mitigation:
- document the exact level of compatibility implemented
- avoid overstating Azure support until auth/header differences are validated

## 11.4 Release overclaim risk
We should not claim:
- broad provider support
- production-grade semantic quality across all providers
unless actual test evidence exists

Mitigation:
- state OpenAI-default support specifically
- state endpoint override compatibility carefully
- keep broader provider claims narrow

---

## 12. Recommended Acceptance Criteria

This plan should be considered complete when all of the following are true:

- OpenAI is the default embedding provider in configuration
- enabling embeddings with only an API key works for the default OpenAI path
- OpenAI request/response handling is implemented correctly
- endpoint override remains possible
- `local_stub` remains available
- an opt-in real external embedding integration test exists
- that integration test proves:
  - embedding generation occurred
  - embeddings were persisted
  - pgvector-backed search path was exercised
- docs and changelog are updated to match the true implementation state

---

## 13. Decision Summary

### Recommended implementation direction

- Make **OpenAI** the default provider identity
- Keep embedding execution **explicitly enabled**
- Make the common real path require only:
  - `CTXLEDGER_EMBEDDING_ENABLED=true`
  - `CTXLEDGER_EMBEDDING_API_KEY=...`
- Implement provider-specific OpenAI request/response handling
- Preserve endpoint override for compatible alternatives
- Verify the external path with opt-in integration coverage

### Recommended positioning after completion

Once implemented and externally verified, the project can honestly say:

- OpenAI is the default external embedding path
- real embedding generation is supported
- pgvector-backed semantic retrieval is validated with real external embeddings
- compatible endpoint override remains possible for alternate deployments

This is the cleanest path to making `0.3.x` semantic retrieval claims materially stronger without collapsing development ergonomics or future provider flexibility.