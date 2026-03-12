# MCP 2025-03-26 Compliance Remediation Plan

## 1. Purpose

This document defines the remediation plan required to bring `ctxledger` into conformance with the MCP `2025-03-26` specification for its primary remote server surface.

It is based on two facts:

1. `docs/specification.md` explicitly requires:
   - **MCP 2025-03-26 compatible interface**
   - **Streamable HTTP (primary)**
   - `stdio` as development-only support
2. The current visible implementation appears to provide a **custom minimal JSON-RPC-over-HTTP surface** at `/mcp`, rather than a demonstrated MCP `2025-03-26` compliant Streamable HTTP server.

This plan exists to prevent the project from drifting into a locally convenient but non-compliant transport design.

---

## 2. Non-Negotiable Requirement

For `v0.1.0`, the primary HTTP transport must be treated as:

- **MCP 2025-03-26 compliant**
- **Streamable HTTP**
- **interoperable with spec-conforming MCP clients**

The following is **not acceptable** as a release endpoint on its own:

- a custom “minimal HTTP MCP interface”
- a hand-rolled JSON-RPC request/response surface that only resembles MCP
- documentation that downgrades the requirement from spec compliance to “minimal usable flow”

Therefore, remediation must restore the release target to the original requirement:

> `ctxledger` must behave as an MCP `2025-03-26` server over Streamable HTTP, not merely as a custom HTTP endpoint exposing a subset of MCP-like methods.

---

## 3. Current State Summary

Based on the current repository direction described in `docs/specification.md` and the visible implementation trajectory, the likely current state is:

- HTTP `/mcp` currently handles JSON-RPC-like requests directly
- visible method support likely includes:
  - `initialize`
  - `tools/list`
  - `tools/call`
  - possibly `resources/list`
  - possibly `resources/read`
- transport handling appears custom and endpoint-local
- current logic appears to reuse a request dispatcher originally shaped around stdio request handling
- current docs outside `specification.md` have recently drifted toward:
  - “minimal HTTP MCP path”
  - “minimal HTTP MCP surface”
  - acceptance language that weakens the original spec requirement

This means the current blocker is not simply “missing HTTP MCP endpoint.”

The blocker is now more precise:

- **the current HTTP MCP surface is not yet demonstrated to be MCP 2025-03-26 compliant**
- **the implementation strategy may itself be pointed at the wrong target**

---

## 4. Scope of This Remediation

## 4.1 In Scope

- auditing the current HTTP MCP behavior against MCP `2025-03-26`
- identifying exact protocol and transport mismatches
- replacing or restructuring custom HTTP MCP handling as needed
- implementing spec-compliant Streamable HTTP behavior
- validating tool and resource exposure through the compliant transport
- correcting repository docs that weakened the original requirement
- preserving transport-agnostic workflow and persistence logic where possible

## 4.2 Out of Scope

- changing `docs/specification.md`
- weakening the compliance requirement
- introducing a project-specific transport variant as a substitute for MCP compliance
- broad memory subsystem expansion unrelated to protocol compliance
- architecture rewrites unrelated to MCP server interoperability

---

## 5. Acceptance Standard

The release should only be treated as acceptable when the following statement is true:

> `ctxledger` exposes a primary remote MCP server surface over Streamable HTTP that is compatible with MCP 2025-03-26 clients, and its required workflow tools/resources are discoverable and invokable through that compliant transport.

Anything weaker than that should be treated as incomplete.

---

## 6. Compliance Questions

The remediation should answer these questions explicitly.

## 6.1 Transport Compliance

1. Does `/mcp` implement the MCP `2025-03-26` transport expectations for Streamable HTTP?
2. Is the server connection model stateful where the spec expects stateful behavior?
3. Are lifecycle operations handled according to the spec rather than as a local approximation?
4. Are request/response semantics aligned with the spec rather than merely JSON-RPC-compatible?

## 6.2 Feature Compliance

5. Are server capabilities negotiated correctly?
6. Are tools exposed in a spec-compatible way?
7. Are resources exposed in a spec-compatible way?
8. If prompts are not implemented, is their absence represented correctly?
9. If client-side features such as sampling are unsupported, is that represented correctly?

## 6.3 Interoperability Reality

10. Can a spec-conforming MCP client connect without relying on `ctxledger`-specific behavior?
11. Can the client initialize, inspect capabilities, list tools, and call tools without special casing?
12. Can the same be done for required resources if they remain in scope?

## 6.4 Documentation Reality

13. Do repository docs still preserve the original compliance target?
14. Have all “minimal custom HTTP MCP path” framings been removed from release-facing docs?
15. Do docs clearly distinguish:
   - compliant MCP transport
   - auxiliary workflow HTTP routes
   - operator/action routes
   - debug routes

---

## 7. Likely Gap Categories

The audit should assume the implementation may currently be deficient in one or more of the following areas.

## 7.1 Transport-Model Mismatch

Possible issue:
- HTTP handling is implemented as a stateless RPC POST endpoint instead of a spec-compliant Streamable HTTP transport.

Impact:
- even if individual methods return plausible payloads, the server may still fail interoperability with real MCP clients.

## 7.2 Lifecycle Mismatch

Possible issue:
- `initialize` and related lifecycle behavior may be treated as simple method dispatch rather than a protocol-governed session negotiation flow.

Impact:
- capability negotiation, initialization state, and subsequent request handling may be non-compliant.

## 7.3 Capability Shape Mismatch

Possible issue:
- `capabilities` payloads may be incomplete, outdated, or structurally incorrect for MCP `2025-03-26`.

Impact:
- clients may mis-detect server feature support.

## 7.4 Error-Model Mismatch

Possible issue:
- the current transport may map exceptions into generic JSON-RPC failures without preserving MCP-spec expectations for protocol-visible errors.

Impact:
- client behavior may be unstable or misleading.

## 7.5 Feature-Surface Mismatch

Possible issue:
- tools/resources may be implemented in domain terms, but not surfaced with the exact protocol semantics expected by the spec.

Impact:
- internal correctness exists, but external interoperability still fails.

## 7.6 Documentation Drift

Possible issue:
- docs outside `specification.md` now understate the requirement.

Impact:
- implementation may be steered toward the wrong success condition.

---

## 8. Remediation Strategy

The remediation should proceed in the following phases.

---

## Phase 1 — Specification-Conformance Audit

### Goal

Convert the current broad concern into a precise gap list against MCP `2025-03-26`.

### Tasks

1. Read `docs/specification.md` as the repository’s non-negotiable contract.
2. Compare current HTTP `/mcp` behavior against MCP `2025-03-26` requirements, especially:
   - Base Protocol
   - Lifecycle
   - Transports
   - Server Features
   - Tools
   - Resources
   - Utilities as relevant
3. Produce a checklist of:
   - compliant
   - partially compliant
   - non-compliant
   - unverified
4. Explicitly identify whether the current `/mcp` implementation is:
   - a custom approximation
   - a partial compliant implementation
   - fundamentally the wrong transport model

### Deliverable

A concise conformance gap matrix.

### Exit Criteria

The project has an exact statement of:
- what is compliant
- what is not
- what must be rewritten versus adjusted

---

## Phase 2 — Transport Model Decision

### Goal

Determine whether the current HTTP implementation can be incrementally corrected or must be replaced at the transport boundary.

### Decision Rule

If the current `/mcp` implementation is fundamentally based on a non-compliant transport model, then:

- do **not** keep extending it as if it were close enough
- instead replace or re-architect the transport adapter to target Streamable HTTP correctly

### Tasks

1. Identify which parts are transport-agnostic and reusable:
   - workflow service logic
   - tool handler logic
   - resource handler logic
   - validation helpers
   - serialization helpers
2. Identify which parts are transport-coupled and likely wrong:
   - lifecycle dispatch
   - connection/session state handling
   - HTTP request/stream semantics
   - custom response framing
3. Decide one of:
   - **adapt current HTTP transport**
   - **replace current HTTP transport**
   - **adopt a compliant MCP runtime/library integration for Streamable HTTP**

### Preferred Bias

Bias toward:
- preserving domain logic
- replacing incorrect transport machinery
- minimizing custom protocol implementation where a compliant runtime can handle it safely

### Deliverable

A transport decision summary.

### Exit Criteria

The team is no longer ambiguous about whether to patch or replace the HTTP adapter.

---

## Phase 3 — MCP 2025-03-26 Lifecycle Compliance

### Goal

Implement lifecycle handling exactly as required by the spec.

### Tasks

1. Ensure initialization behavior matches the spec.
2. Ensure capability negotiation is spec-compliant.
3. Ensure post-initialization request handling respects the correct lifecycle.
4. Ensure shutdown/termination-related semantics are handled appropriately if required by the chosen transport/runtime model.
5. Ensure unsupported features are represented correctly rather than silently approximated.

### Focus Areas

- `initialize`
- initialization state tracking
- declared server capabilities
- feature gating after initialization if required

### Deliverable

A lifecycle-compliant MCP server behavior for the HTTP transport.

### Exit Criteria

A conforming MCP client can complete lifecycle negotiation without special casing.

---

## Phase 4 — Streamable HTTP Compliance

### Goal

Bring the primary HTTP transport into conformance with the Streamable HTTP expectations of MCP `2025-03-26`.

### Tasks

1. Implement the correct HTTP transport behavior for the spec.
2. Eliminate custom endpoint behavior that conflicts with Streamable HTTP.
3. Ensure connection/session semantics match the spec’s intended model.
4. Ensure the transport remains the primary public interface for remote clients.

### Constraints

- no custom “close enough” HTTP mode
- no release-specific downgrade from Streamable HTTP to local JSON-RPC-over-POST
- no spec relaxation via docs

### Deliverable

A spec-compliant Streamable HTTP MCP transport at `/mcp`.

### Exit Criteria

The primary HTTP transport is no longer a custom approximation.

---

## Phase 5 — Tool Surface Compliance

### Goal

Ensure required workflow tools are exposed through the compliant MCP surface.

### Required Workflow Tools

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

### Tasks

1. Ensure `tools/list` reflects the required tools through the compliant transport.
2. Ensure tool schemas are discoverable in the spec-compatible shape.
3. Ensure `tools/call` works through the compliant transport for each required workflow tool.
4. Ensure tool errors are surfaced in a spec-compliant way.
5. Ensure memory tools are either:
   - exposed correctly, or
   - explicitly scoped/documented as partial/stubbed without violating protocol semantics

### Deliverable

A compliant tool surface over the primary HTTP MCP transport.

### Exit Criteria

A conforming client can discover and call the required workflow tools.

---

## Phase 6 — Resource Surface Compliance

### Goal

Decide and implement resource behavior through the compliant MCP transport.

### Required Resource Candidates

From `docs/specification.md`:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`

### Tasks

1. Confirm which resources are required for `v0.1.0`.
2. Ensure required workflow resources are surfaced through the compliant transport.
3. Ensure resource listing and reading match the spec.
4. Keep future-facing memory resources clearly separated from required workflow resources if they remain stubbed.

### Deliverable

A compliant resource surface for in-scope resources.

### Exit Criteria

Required resources are no longer only stronger on stdio than on HTTP.

---

## Phase 7 — Error, Logging, and Utility Compliance

### Goal

Align non-feature protocol behavior with MCP expectations.

### Tasks

1. Review protocol-visible errors for compliance.
2. Ensure generic exception mapping does not violate spec expectations.
3. Review whether relevant MCP utilities are required or should be explicitly unsupported:
   - logging
   - cancellation
   - progress
   - related utility behaviors as applicable
4. Ensure any unsupported utility surface is represented honestly.

### Deliverable

A cleaner and more interoperable protocol behavior model.

### Exit Criteria

Clients do not encounter misleading protocol behavior outside the happy path.

---

## Phase 8 — Test Remediation

### Goal

Prove spec-oriented behavior rather than merely local endpoint behavior.

### Required Test Categories

1. lifecycle negotiation tests
2. Streamable HTTP transport behavior tests
3. capability advertisement tests
4. tool discovery tests
5. tool invocation tests
6. resource discovery/read tests if resources are in scope
7. auth behavior tests
8. error-shape and invalid-request tests
9. interoperability-oriented tests where possible

### Minimum Acceptance Test Coverage

At minimum, tests should prove that a conforming MCP client can:

1. connect to `/mcp`
2. initialize correctly
3. inspect server capabilities
4. list tools
5. inspect input schemas
6. call:
   - `workspace_register`
   - `workflow_start`
   - `workflow_checkpoint`
   - `workflow_resume`
   - `workflow_complete`
7. list/read required resources if in scope

### Important Rule

Do not treat:
- custom local tests for bespoke JSON-RPC payloads
as sufficient proof of MCP `2025-03-26` compliance.

### Deliverable

A test suite whose assertions are aligned with the spec contract.

### Exit Criteria

The release claim is backed by protocol-oriented tests, not custom transport assumptions.

---

## Phase 9 — Documentation Correction

### Goal

Bring repository docs back into alignment with the non-negotiable spec requirement.

### Important Constraint

- **Do not edit `docs/specification.md`**
- treat it as the source contract

### Docs Likely Requiring Correction

- `README.md`
- `docs/mcp-api.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/CHANGELOG.md`
- `docs/imple_plan_review_0.1.0.md`
- `docs/v0.1.0_acceptance_evidence.md`
- this remediation plan itself as work progresses

### Required Corrections

1. Remove wording that treats a custom minimal HTTP MCP path as acceptable.
2. Restore wording that:
   - MCP `2025-03-26` compatibility is required
   - Streamable HTTP is primary
3. Clearly distinguish:
   - MCP transport
   - workflow-specific HTTP routes
   - operator/action routes
   - debug routes
4. Ensure stdio is described only as development/supporting surface if it remains.

### Deliverable

A documentation set that no longer weakens the original requirement.

### Exit Criteria

The docs once again push implementation toward true MCP compliance.

---

## Phase 10 — Closeout Re-Evaluation

### Goal

Re-score release readiness only after compliance remediation is complete.

### Required Outputs

1. updated implementation review
2. updated acceptance evidence
3. compliance verdict:
   - compliant
   - partially compliant / not releasable
   - non-compliant

### Decision Standard

`v0.1.0` should only be considered acceptable if:

- the primary HTTP transport is Streamable HTTP compliant with MCP `2025-03-26`
- required tools are discoverable and callable through that transport
- required resources are correctly handled if in scope
- release-facing docs do not understate the requirement

### Explicit Non-Acceptance Case

The release must remain open if the result is only:

- a custom HTTP endpoint exposing some MCP-like methods

---

## 9. Immediate Next Actions

The next work loop should do this in order:

1. produce a spec-to-implementation conformance matrix
2. classify the current `/mcp` implementation as:
   - compliant
   - partially compliant
   - custom/non-compliant
3. decide whether to adapt or replace the transport adapter
4. implement spec-compliant lifecycle and Streamable HTTP behavior
5. re-test tools/resources through that transport
6. correct all non-specification docs that weakened the requirement

---

## 10. Practical Summary

The key repository contract is already clear in `docs/specification.md`:

- MCP `2025-03-26` compatibility is required
- Streamable HTTP is primary
- stdio is development-only support

Therefore, the remediation priority is also clear:

- **do not optimize for a custom minimal HTTP MCP endpoint**
- **implement a real MCP 2025-03-26 Streamable HTTP server**
- **preserve domain logic, replace non-compliant transport behavior as needed**
- **treat documentation drift as a secondary but important remediation stream**

The current question is not:

- “Does `/mcp` respond to a few JSON-RPC methods?”

The current question is:

- “Is `/mcp` a spec-conforming MCP `2025-03-26` Streamable HTTP server that real MCP clients can use without special handling?”

This plan should be considered complete only when the answer is yes.