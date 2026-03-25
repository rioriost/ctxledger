# MCP Release Acceptance Checklist

## 1. Purpose

This document defines the final release-acceptance checklist for closing out `ctxledger v0.1.0` as an MCP-compliant remote server.

It is intended to answer one final question:

> Is `ctxledger v0.1.0` actually acceptable as a remote MCP server that satisfies the repository’s stated contract?

This checklist is specifically aligned to the non-negotiable requirement established by:

- `docs/project/product/specification.md`

That requirement includes:

- **MCP 2025-03-26 compatibility**
- **Streamable HTTP as the primary transport**
- a **remote MCP server** that interoperates with spec-conforming clients

This checklist is a release gate.
It is not a design note, and it is not a partial-progress tracker.

If the required items below are not satisfied, `v0.1.0` should remain open.

---

## 2. Release Standard

`v0.1.0` should only be considered acceptable if the following statement is true:

> `ctxledger` exposes a primary remote MCP server surface at `/mcp` that is compliant with MCP 2025-03-26 over Streamable HTTP, and a spec-conforming client can initialize, negotiate capabilities, discover required tools/resources, and invoke required workflow operations without `ctxledger`-specific behavior.

Anything weaker than that is not sufficient for release closeout.

---

## 3. How to Use This Checklist

Each item should be marked one of:

- `[x]` complete / verified
- `[ ]` incomplete / unverified
- `[n/a]` explicitly not applicable, with a written justification

A release should **not** be closed if any required item remains unchecked.

---

## 4. Global Release Blockers

The release must remain blocked if any of the following are true:

- [ ] `/mcp` still behaves primarily as a custom JSON-RPC-over-HTTP endpoint rather than a spec-oriented MCP Streamable HTTP endpoint
- [ ] protocol version handling is not correct for `2025-03-26`
- [ ] lifecycle handling still uses non-spec method naming such as `initialized` instead of `notifications/initialized`
- [ ] required workflow tools are not discoverable through the compliant MCP path
- [ ] required workflow tools are not invokable through the compliant MCP path
- [ ] transport-oriented tests do not prove the compliant path
- [ ] repository docs outside `docs/project/product/specification.md` still weaken or contradict the MCP `2025-03-26` + Streamable HTTP requirement

If any of the above remain unresolved, the release is not acceptable.

---

## 5. Protocol and Lifecycle Acceptance

### 5.1 Protocol Identity

- [ ] The primary release target is still explicitly treated as **MCP 2025-03-26**
- [ ] No release-facing artifact redefines success as a “minimal MCP-like” or “custom MCP path”
- [ ] The release claim is framed in terms of MCP client interoperability, not local endpoint behavior alone

### 5.2 Initialize / Lifecycle

- [ ] `initialize` is the first required lifecycle interaction on the MCP path
- [ ] `initialize` is not accepted as part of a batch if the spec forbids that
- [ ] the server validates initialize input according to MCP expectations
- [ ] the server returns a correct initialize response shape
- [ ] the server responds with the correct negotiated `protocolVersion`
- [ ] the server uses the correct lifecycle notification name:
  - [ ] `notifications/initialized`
- [ ] request handling before initialization completion follows the spec
- [ ] request handling after initialization completion follows the spec
- [ ] lifecycle behavior is covered by tests

### 5.3 Capability Negotiation

- [ ] the server advertises capabilities in a spec-compatible structure
- [ ] `tools` capability is declared correctly if tools are supported
- [ ] `resources` capability is declared correctly if resources are supported
- [ ] optional capabilities are only declared if truly supported
- [ ] unsupported features are omitted or represented honestly
- [ ] capability negotiation behavior is covered by tests

---

## 6. Streamable HTTP Acceptance

### 6.1 Endpoint Shape

- [ ] `/mcp` is treated as the single primary MCP endpoint
- [ ] the endpoint supports the methods required by Streamable HTTP
- [ ] the endpoint is no longer implemented as merely a generic route wrapper around local request dispatch
- [ ] the compliant transport path is the release-authoritative path

### 6.2 POST Handling

- [ ] client JSON-RPC messages are accepted through POST as required
- [ ] request-category behavior is handled correctly for:
  - [ ] requests
  - [ ] notifications
  - [ ] responses
- [ ] content negotiation is handled correctly
- [ ] status handling is correct for accepted notification/response-only POSTs
- [ ] POST behavior is covered by tests

### 6.3 GET / Streaming Behavior

- [ ] GET behavior is implemented according to the intended Streamable HTTP model
- [ ] if SSE is required by the chosen transport behavior, it is implemented correctly
- [ ] if SSE is supported, server messages are emitted with correct stream behavior
- [ ] if GET is intentionally limited, that limitation is still compatible with the spec and documented honestly
- [ ] GET/stream behavior is covered by tests

### 6.4 Session / Connection Semantics

- [ ] session handling is either:
  - [ ] implemented correctly
  - [ ] explicitly not used, without violating spec expectations
- [ ] if session IDs are used, their behavior is correct
- [ ] if resumability/redelivery is implemented, it behaves correctly
- [ ] no custom session shortcut breaks client interoperability
- [ ] session/connection behavior is covered by tests where applicable

---

## 7. Security Acceptance

### 7.1 Transport Security

- [ ] `Origin` validation exists for the Streamable HTTP MCP endpoint
- [ ] the transport does not rely on unsafe local-only assumptions while being documented as remote-capable
- [ ] authentication behavior is coherent for the MCP endpoint
- [ ] production deployment guidance still recommends bearer auth and TLS where appropriate

### 7.2 Documentation Alignment for Security

- [ ] release-facing docs correctly describe authentication expectations for `/mcp`
- [ ] release-facing docs do not imply that debug/operator routes are equivalent to MCP transport
- [ ] security-sensitive transport requirements are reflected in docs other than `specification.md`

---

## 8. Required Workflow Tool Acceptance

The following workflow tools are required by the repository contract and must be available through the compliant MCP transport:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

### 8.1 Discovery

- [ ] `tools/list` exposes `workspace_register`
- [ ] `tools/list` exposes `workflow_start`
- [ ] `tools/list` exposes `workflow_checkpoint`
- [ ] `tools/list` exposes `workflow_resume`
- [ ] `tools/list` exposes `workflow_complete`

### 8.2 Schema Visibility

- [ ] each required tool exposes a correct `inputSchema`
- [ ] schema structure is spec-compatible
- [ ] schema visibility is tested through the compliant MCP path

### 8.3 Invocation

- [ ] `workspace_register` is callable through the compliant MCP path
- [ ] `workflow_start` is callable through the compliant MCP path
- [ ] `workflow_checkpoint` is callable through the compliant MCP path
- [ ] `workflow_resume` is callable through the compliant MCP path
- [ ] `workflow_complete` is callable through the compliant MCP path

### 8.4 Error Semantics

- [ ] invalid tool name is surfaced as a protocol error, not a fake success payload
- [ ] invalid parameters are surfaced as protocol errors where appropriate
- [ ] tool execution failures are surfaced as tool execution results with error semantics where appropriate
- [ ] protocol errors and execution errors are clearly separated in implementation and tests

---

## 9. Required Resource Acceptance

The repository contract lists the following workflow resources:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

These must be handled one of two ways before release closeout:

1. implemented through the compliant MCP transport, or
2. explicitly and credibly moved out of required `v0.1.0` scope through repository decision artifacts

### 9.1 Scope Decision

- [ ] required workflow resource scope for `v0.1.0` is explicitly decided
- [ ] if resources remain required, they are implemented through the compliant transport
- [ ] if resources are deferred, the deferral is explicit, documented, and reflected consistently across review/evidence docs

### 9.2 Resource Discovery

If required:

- [ ] `resources/list` exposes `workspace://{workspace_id}/resume`
- [ ] `resources/list` exposes `workspace://{workspace_id}/workflow/{workflow_instance_id}`

### 9.3 Resource Reading

If required:

- [ ] `resources/read` can read `workspace://{workspace_id}/resume`
- [ ] `resources/read` can read `workspace://{workspace_id}/workflow/{workflow_instance_id}`

### 9.4 Resource Error Semantics

If required:

- [ ] invalid resource URI handling is compliant
- [ ] resource-not-found handling is compliant
- [ ] resource read behavior is covered by tests

---

## 10. Optional / Supporting Surface Acceptance

These areas may exist without defining the release by themselves.

### 10.1 stdio

- [ ] stdio is not treated as the primary release acceptance center
- [ ] if stdio remains, its role is described as development/supporting surface only
- [ ] no acceptance claim depends on stdio maturity alone

### 10.2 Auxiliary HTTP Routes

- [ ] workflow-specific HTTP routes are clearly separated from MCP transport
- [ ] projection operator routes are clearly separated from MCP transport
- [ ] debug routes are clearly separated from MCP transport
- [ ] no acceptance artifact uses auxiliary HTTP routes as proof of MCP compliance

### 10.3 Memory Surface

- [ ] memory tools/resources are either:
  - [ ] honestly implemented through MCP
  - [ ] honestly stubbed/partial
  - [ ] explicitly outside closeout-critical scope
- [ ] optional memory work is not being mistaken for transport compliance progress

---

## 11. Testing Acceptance

### 11.1 Protocol-Oriented Tests

- [ ] tests prove lifecycle correctness
- [ ] tests prove protocol version correctness
- [ ] tests prove `notifications/initialized` correctness
- [ ] tests prove compliant `/mcp` behavior through the new transport
- [ ] tests are not merely proving local custom handler behavior

### 11.2 Feature Tests

- [ ] `tools/list` is tested through the compliant transport
- [ ] `tools/call` is tested through the compliant transport
- [ ] required workflow tools are tested through the compliant transport
- [ ] required resources are tested through the compliant transport if in scope

### 11.3 Transport Tests

- [ ] POST semantics are tested
- [ ] GET semantics are tested
- [ ] SSE behavior is tested if implemented
- [ ] status behavior such as 202 handling is tested where required
- [ ] `Origin` validation is tested
- [ ] session behavior is tested if implemented

### 11.4 Regression Safety

- [ ] workflow-specific HTTP routes still behave correctly
- [ ] debug/operator routes still behave correctly
- [ ] startup/health/readiness remain intact
- [ ] the transport rewrite did not break canonical workflow behavior

---

## 12. Documentation Acceptance

The following docs must agree with `docs/project/product/specification.md` and with the implementation reality:

- `README.md`
- `docs/project/product/mcp-api.md`
- `docs/project/product/architecture.md`
- `docs/operations/deployment/deployment.md`
- `docs/project/releases/CHANGELOG.md`
- `docs/project/history/imple_plan_review_0.1.0.md`
- `docs/v0.1.0_acceptance_evidence.md`

### 12.1 Required Documentation Conditions

- [ ] no release-facing doc weakens the MCP `2025-03-26` requirement
- [ ] no release-facing doc weakens the Streamable HTTP primary requirement
- [ ] no release-facing doc claims a custom minimal `/mcp` path is sufficient
- [ ] docs consistently describe `/mcp` as the compliant MCP endpoint
- [ ] docs consistently separate MCP transport from auxiliary HTTP surfaces
- [ ] docs consistently describe stdio as supporting/development only if it remains

### 12.2 Acceptance Evidence Conditions

- [ ] acceptance evidence is centered on the compliant HTTP transport
- [ ] acceptance evidence does not rely on stdio as primary proof
- [ ] acceptance evidence does not rely on local custom endpoint behavior as if it were MCP compliance
- [ ] implementation review and evidence docs agree on the current release state

---

## 13. Codebase Cleanliness Acceptance

Before closeout, the repository should no longer have major ambiguity around MCP ownership.

- [ ] the new MCP transport path is clearly the primary path
- [ ] the old custom `/mcp` implementation is deleted or quarantined
- [ ] `server.py` is no longer the main protocol authority
- [ ] MCP lifecycle logic lives in dedicated MCP modules
- [ ] result mapping lives in dedicated MCP modules
- [ ] feature binding lives in dedicated MCP modules or equivalent clean boundaries
- [ ] transport-agnostic workflow logic remains preserved and reusable

---

## 14. Final Release Gate

`v0.1.0` may be treated as acceptable only if all of the following are true:

- [ ] `/mcp` is implemented as an MCP `2025-03-26` primary Streamable HTTP endpoint
- [ ] required workflow tools are discoverable and invokable through that endpoint
- [ ] required workflow resources are compliant or explicitly out of scope
- [ ] lifecycle and version handling are correct
- [ ] transport-oriented tests prove the compliant path
- [ ] docs outside `specification.md` align with the requirement and actual implementation
- [ ] the old custom `/mcp` path is no longer the practical release path

If any of the above remain false:

- [ ] **Release remains blocked**

If all of the above are true:

- [ ] **Release may proceed to closeout review**

---

## 15. Final Recommendation

Use this checklist only at the end of the rewrite stream, not as a progress substitute.

The release question is simple:

- not “does `/mcp` answer a few JSON-RPC methods?”
- but “is `/mcp` a real MCP `2025-03-26` Streamable HTTP server that a conforming client can use correctly?”

This checklist should only be marked complete when the answer is yes.