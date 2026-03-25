# HTTP-Only MCP Acceptance Remediation Plan

## 1. Purpose

This document defines the remediation plan for the current `v0.1.0` acceptance gap around the MCP transport surface.

The goal is to align implementation work with the actual release target:

- a **minimum usable remote MCP server**
- an **MCP 2025-03-26 compatible interface**
- **Docker-based deployment**
- **HTTP as the primary and required transport**

For `v0.1.0`, the release should converge on a simpler and clearer transport scope:

- **HTTP MCP transport only**
- **Docker-backed local and remote validation**
- no `stdio` runtime surface in the `v0.1.0` deliverable

This plan exists to prevent further drift between:

- the implementation plan
- the specification
- the acceptance evidence
- the actual transport implementation

---

## 2. Why this revision is necessary

The current product goal is centered on a **remote** MCP server.

The implementation plan already states:

- Streamable HTTP as the primary runtime mode
- `stdio` mode for development and local validation

However, the practical closeout problem is now clear:

- work on `stdio` can create the appearance of MCP progress
- but `v0.1.0` acceptance depends on the **remote HTTP MCP server**
- therefore `stdio` can become a distraction rather than a useful delivery surface

For `v0.1.0`, the important question is not:

- "Does `stdio` work?"

The important question is:

- "Can a real remote MCP client connect over HTTP/HTTPS and use `ctxledger` as an MCP server?"

Given the current product goal and expected client usage, `stdio` is not required to answer that question.

In addition:

- Docker + HTTP is sufficient for development and debugging
- remote MCP client configuration in tools such as Zed is straightforward
- maintaining two transport implementations increases confusion and maintenance cost
- if transport surfaces diverge, `stdio` stops being a trustworthy debug mirror and becomes harmful

Therefore, the revised direction is:

- **remove `stdio` from the `v0.1.0` scope**
- **focus all MCP transport work on HTTP**

---

## 3. Revised objective

The revised remediation objective is:

> Deliver `v0.1.0` as a minimum usable remote MCP server over HTTP, with Docker-based deployment, where a remote MCP client can connect to `/mcp`, discover tools, understand their inputs, and invoke the required workflow operations.

This implies a deliberate narrowing of transport scope.

### Required for `v0.1.0`
- HTTP MCP transport
- Docker deployment
- required workflow tools
- required workflow resources if they remain required by the plan
- documentation and tests for the HTTP MCP path

### Explicitly removed from `v0.1.0`
- `stdio` runtime support
- `stdio`-specific MCP request handling
- `stdio`-specific tool/resource discoverability
- `stdio`-specific acceptance evidence
- `stdio` as a development/debug justification

---

## 4. Scope of this remediation

## 4.1 In scope

- confirming the actual required HTTP MCP contract
- implementing the minimum usable HTTP MCP transport
- removing `stdio` transport support from code, tests, and docs
- revising acceptance evidence to be HTTP-centered
- revising closeout language so it reflects the actual release target
- preserving shared domain/service logic where appropriate

## 4.2 Out of scope

- adding new workflow-domain capabilities beyond MCP transport needs
- memory subsystem expansion
- broader architecture rewrites unrelated to HTTP MCP delivery
- preserving `stdio` for convenience if it delays or confuses `v0.1.0`
- speculative future multi-transport support beyond `v0.1.0`

---

## 5. Revised transport policy for `v0.1.0`

For `v0.1.0`, the transport policy should be:

1. **HTTP is the only required MCP transport**
2. **Docker is the primary local development and validation environment**
3. **Remote MCP client compatibility over HTTP is the acceptance center**
4. **`stdio` is removed from scope**

This means `v0.1.0` should no longer optimize for:

- parity between `stdio` and HTTP
- keeping a separate local-only MCP transport alive
- proving MCP semantics through `stdio` first

Instead, all transport-level effort should directly improve:

- `/mcp`
- HTTP/HTTPS MCP compatibility
- remote client usability

---

## 6. Acceptance questions after revision

The revised release should be evaluated against these questions.

### 6.1 HTTP MCP reality
1. Does `/mcp` actually implement the MCP protocol over HTTP?
2. Can an MCP client initialize successfully over HTTP?
3. Can an MCP client list tools over HTTP?
4. Can an MCP client inspect tool inputs over HTTP?
5. Can an MCP client call required workflow tools over HTTP?
6. Are MCP-visible errors normalized over HTTP?

### 6.2 Deployment reality
7. Can the HTTP MCP surface be run and validated through Docker?
8. Is the deployment contract documented clearly enough for a remote client user?
9. Are auth expectations for remote HTTP MCP usage documented correctly?

### 6.3 Closeout framing
10. Do docs and evidence describe the release as HTTP-first and HTTP-only for `v0.1.0`?
11. Has all `stdio`-based closeout optimism been removed?
12. Is the release claim supportable without leaning on `stdio` at all?

---

## 7. Required acceptance target

After remediation, the repository should support this statement cleanly:

> `ctxledger v0.1.0` provides a minimum usable remote MCP server over HTTP, deployable with Docker, where an MCP client can connect to `/mcp`, discover the required workflow tools, understand required inputs, and invoke those tools successfully.

At minimum, the required workflow tool set remains:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

For these tools, the HTTP MCP surface must support:

- session initialization
- tool discovery
- input discoverability
- invocation
- visible error behavior

If that statement cannot be supported, `v0.1.0` should not be treated as acceptable.

---

## 8. Work sequence

## Phase 1 — HTTP MCP reality audit

### Goal
Establish what the current HTTP MCP implementation actually does.

### Tasks
1. Audit the code paths related to:
   - `/mcp`
   - HTTP transport startup
   - HTTP request dispatch
   - MCP initialization over HTTP
   - MCP tool discovery over HTTP
   - MCP tool invocation over HTTP
   - MCP resource behavior over HTTP if applicable
2. Determine whether the current HTTP transport is:
   - a real MCP endpoint
   - a partial MCP endpoint
   - only a placeholder plus workflow/debug routes
3. Identify whether current docs overstate the HTTP MCP reality

### Audit result
Current visible repository evidence now indicates:

- `stdio` contains explicit MCP request handling for:
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `resources/list`
  - `resources/read`
- HTTP exposes:
  - workflow-specific HTTP routes
  - projection failure operator routes
  - debug/runtime inspection routes
  - a concrete `/mcp` HTTP handler for JSON-RPC request/response flow
- `/mcp` is now evidenced as supporting, over HTTP:
  - `initialize`
  - `tools/list`
  - `tools/call`
- HTTP auth handling is also evidenced on the `/mcp` path
- current repository tests now prove a usable minimal HTTP MCP protocol flow at `/mcp` for initialization, tool discovery, and tool invocation
- `resources/list` and `resources/read` are still more strongly evidenced on the stdio side than on the HTTP side

### Deliverable
A concise factual audit result documenting:

- what `/mcp` currently supports
- what it does not yet support
- whether the original main acceptance blocker is still current

### Blocker classification
Based on the current visible code and test evidence, the prior blocker should be revised from:

- **major implementation blocker**

to:

- **substantially remediated for the minimal HTTP MCP path**
- **remaining closeout/alignment work for protocol scope and acceptance wording**

The current gap is no longer best described as “HTTP MCP endpoint missing.”

### Exit criteria
The HTTP MCP reality is now explicit enough that implementation and documentation remediation can proceed from a factual baseline.

---

## Phase 2 — Scope cleanup decision

### Goal
Turn the audit into an implementation direction and formally commit to HTTP-only delivery.

### Decision summary
The current audit supports the following decisions:

1. `stdio` is removed from `v0.1.0` scope
2. `stdio` code will be deleted or isolated out of the release path
3. all acceptance language will become HTTP-centered
4. all MCP transport work will target `/mcp`
5. workflow/debug HTTP routes must no longer be treated as evidence that the MCP HTTP transport itself is usable
6. stdio-side MCP maturity must no longer be used as release evidence for the remote HTTP MCP target

### Deliverable
A short repository-facing decision summary reflected in docs and review notes.

### Exit criteria
The repository documentation must no longer imply that `stdio` is part of the `v0.1.0` delivery contract.

---

## Phase 3 — Minimal HTTP MCP implementation

### Goal
Implement and verify the smallest viable HTTP MCP transport necessary for `v0.1.0`.

### Current status
This phase is now substantially complete for the minimal path.

Current visible repository evidence supports HTTP `/mcp` handling for:

1. `initialize`
2. `tools/list`
3. `tools/call`

This includes test-backed evidence for:

- successful initialization
- tool discovery over HTTP
- tool invocation over HTTP
- invalid request handling for missing request body
- path validation at `/mcp`
- auth behavior when HTTP auth is enabled

### Remaining work inside this phase
If required for the planned resource surface, HTTP should also support:

4. `resources/list`
5. `resources/read`

### Required qualities
- tool inputs must be discoverable through the HTTP MCP protocol surface
- required workflow tools must be callable
- error behavior must be normalized and protocol-visible
- auth handling must be coherent for remote usage
- shared domain/service logic should be reused

### Constraints
- avoid overengineering
- avoid transport-specific business logic forks
- avoid adding speculative transport features not needed for `v0.1.0`
- keep transport adapters thin and focused

### Design requirement
The HTTP MCP surface should be the canonical transport surface for `v0.1.0`.

That means:

- docs should describe HTTP MCP first
- tests should prove HTTP MCP first
- acceptance evidence should cite HTTP MCP first

---

## Phase 4 — `stdio` removal

### Goal
Remove `stdio` implementation and related scope from the release path.

### Removal targets
At minimum, review and remove or disable:

- `stdio` runtime adapters
- `stdio` request handling
- `stdio`-specific transport configuration that is no longer needed for `v0.1.0`
- `stdio` tests
- `stdio` docs and evidence language
- `stdio` examples presented as part of release readiness

### Constraints
- preserve shared workflow/service logic
- preserve reusable validation and response-shaping logic
- do not remove transport-agnostic code only because it was previously exercised through `stdio`

### Deliverable
A codebase where `v0.1.0` transport scope is clearly HTTP-only.

---

## Phase 5 — Test remediation

### Goal
Prove that the primary HTTP acceptance target is actually met.

### Current test-backed evidence
Tests now verify, over the HTTP MCP surface where applicable:

1. initialization succeeds
2. tool listing succeeds
3. tool input discovery is exposed through `tools/list`
4. `tools/call` succeeds on the HTTP MCP path
5. invalid requests return protocol-visible errors for missing request body
6. auth behavior is consistent when HTTP auth is enabled
7. `/mcp` path validation works as expected

### Remaining test expansion
Tests should still be expanded, over the HTTP MCP surface where applicable, to verify direct success cases for:

1. `workspace_register`
2. `workflow_start`
3. `workflow_checkpoint`
4. `workflow_resume`
5. `workflow_complete`

And, if required by the release scope:

6. `resources/list`
7. `resources/read`

### Test categories
- unit tests for HTTP adapter/request handling
- integration tests for HTTP MCP flow
- smoke-level proof of `/mcp` usability
- Docker-oriented validation as needed for the stated deployment path

### Exit criteria
Acceptance language may now be upgraded from “HTTP MCP not yet evidenced” to “minimal HTTP MCP path evidenced,” but stronger closeout language should still wait for the remaining required-tool and optional resource coverage decisions.

---

## Phase 6 — Documentation and evidence correction

### Goal
Bring docs into alignment with the actual HTTP acceptance state.

### Required documentation updates
Update at least:

- `README.md`
- `docs/mcp-api.md`
- `docs/deployment.md`
- `docs/specification.md`
- `docs/architecture.md`
- `docs/imple_plan_review_0.1.0.md`
- `docs/v0.1.0_acceptance_evidence.md`
- `docs/CHANGELOG.md`

### Required corrections
Docs must clearly distinguish:

- HTTP as primary and only `v0.1.0` transport
- Docker as the intended local validation path
- debug/ops HTTP routes vs the actual MCP HTTP protocol surface
- descriptive documentation vs machine-readable protocol discovery
- historical `stdio` implementation work vs current `v0.1.0` scope

### Specific evidence corrections
The following must be avoided:

- implying `v0.1.0` is effectively closeable on the strength of `stdio`
- counting `stdio`-only discoverability as sufficient remote acceptance evidence
- treating the existence of `/mcp` config or URL shape as proof of protocol usability without HTTP MCP verification
- presenting workflow/debug HTTP routes as if they were equivalent to the MCP HTTP transport itself

### Deliverable
A documentation set that matches the actual release contract and no longer overstates readiness.

---

## Phase 7 — Closeout re-evaluation

### Goal
Re-assess `v0.1.0` only after the HTTP MCP reality is corrected.

### Required outputs
1. updated acceptance matrix
2. updated implementation review
3. short final verdict:
   - acceptable
   - conditionally acceptable with explicit caveats
   - not acceptable yet

### Decision standard
`v0.1.0` should only be treated as acceptable if the primary claim is true:

- `ctxledger` is a minimum usable **remote** MCP server over HTTP

If that claim still cannot be supported, the release should remain open regardless of how polished the removed `stdio` path previously was.

---

## 9. Definition of success for this remediation

This remediation is successful when all of the following are true:

1. the actual HTTP MCP state is no longer ambiguous
2. `/mcp` is proven usable for MCP clients
3. acceptance evidence is framed around the primary HTTP target, not around `stdio`
4. docs no longer overstate remote MCP readiness
5. tests support the HTTP acceptance claim directly
6. `workspace_register` and the other required workflow tools are discoverable and callable in the primary HTTP path
7. the `v0.1.0` delivery story is simpler, clearer, and transport-consistent

---

## 10. Risks during remediation

### Risk 1 — Overcorrecting by rewriting too much transport code
Mitigation:
- prefer minimal viable HTTP MCP completion
- reuse existing domain/service logic
- separate required protocol work from optional cleanup

### Risk 2 — Confusing debug routes with MCP protocol routes
Mitigation:
- explicitly separate:
  - debug/ops HTTP endpoints
  - actual MCP HTTP endpoint behavior
- do not treat route visibility as MCP compatibility evidence by itself

### Risk 3 — Removing `stdio` but leaving its assumptions in docs/evidence
Mitigation:
- do a full transport-language audit across docs
- update acceptance/review/changelog materials in the same work stream

### Risk 4 — Repeating documentation optimism before verification
Mitigation:
- do the HTTP reality audit first
- only then update closeout claims
- use explicit test-backed statements in closeout docs

### Risk 5 — Leaving partial `stdio` code paths that still influence release behavior
Mitigation:
- remove or isolate `stdio` decisively
- ensure release-facing configuration and runtime creation do not depend on it

---

## 11. Immediate next actions

The next work loop should do exactly this:

1. audit current HTTP `/mcp` implementation behavior
2. determine whether MCP initialization/list/call exist over HTTP
3. classify the gap as:
   - docs-only
   - partial implementation
   - major implementation blocker
4. update docs/review/evidence to reflect HTTP-only scope where needed
5. only then start the smallest implementation changes required
6. remove `stdio` from code/tests/docs as part of the same remediation stream

---

## 12. Practical summary

The project has made real progress on:

- workflow logic
- internal validation and response shaping
- documentation breadth
- deployment guidance
- some MCP-adjacent transport work

But that is not yet the same as satisfying the `v0.1.0` primary promise.

The current audit result now sharpens a different problem:

- visible MCP protocol request handling is evidenced on both `stdio` and HTTP
- visible HTTP functionality includes both workflow/debug/operator routes and a minimal `/mcp` MCP path
- visible `/mcp` behavior is now evidenced as a usable minimal remote MCP protocol endpoint
- the remaining ambiguity is whether the currently proven minimal HTTP MCP path is sufficient for the exact `v0.1.0` acceptance wording

The primary promise is:

- a **minimum usable remote MCP server**
- with **HTTP as the primary runtime mode**
- and, under this revised plan, **HTTP as the only `v0.1.0` transport**

Therefore, the remediation priority is now:

- treat the original “missing HTTP MCP endpoint” blocker as substantially resolved
- align docs, evidence, and closeout language with the proven minimal `/mcp` implementation
- decide whether additional HTTP MCP scope is required beyond the currently proven minimal path
- remove `stdio` from the `v0.1.0` delivery path
- re-score acceptance using HTTP evidence only
- close out the release only if the remote MCP claim is genuinely true