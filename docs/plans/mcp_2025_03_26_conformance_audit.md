# MCP 2025-03-26 Conformance Audit

## 1. Purpose

This document records a spec-to-implementation conformance audit for `ctxledger` against the MCP `2025-03-26` requirement established by:

- `docs/specification.md`

It is intended to answer one narrow question:

> Is the current `/mcp` implementation a real MCP `2025-03-26` Streamable HTTP server, or only a custom HTTP endpoint exposing a subset of MCP-like behavior?

This audit is based on the repository direction and currently visible implementation behavior already established in prior review work.

---

## 2. Audit Scope

This audit focuses on:

- base protocol expectations
- lifecycle requirements
- Streamable HTTP transport requirements
- server capability negotiation
- tools surface
- resources surface
- protocol-visible error behavior
- interoperability implications

This audit does **not** modify `docs/specification.md`, and it treats that document as the non-negotiable contract.

---

## 3. Status Legend

- **Compliant**  
  Strong evidence indicates the current implementation matches the MCP `2025-03-26` requirement.

- **Partially Compliant**  
  Some elements exist, but the implementation is incomplete, weaker than required, or not fully aligned with the spec.

- **Non-Compliant**  
  The current implementation behavior conflicts with the spec requirement or is aimed at the wrong model.

- **Unverified**  
  There is not enough current evidence to conclude compliance.

---

## 4. High-Level Verdict

## 4.1 Summary

Current evidence indicates that `ctxledger` is **not yet conformant** with MCP `2025-03-26` for its primary remote HTTP transport.

The repository appears to provide:

- a custom JSON-RPC-like HTTP endpoint at `/mcp`
- visible support for:
  - `initialize`
  - `tools/list`
  - `tools/call`
  - possibly `resources/list`
  - possibly `resources/read`

However, that is not sufficient to satisfy the requirement in `docs/specification.md`, which explicitly expects:

- MCP `2025-03-26`
- Streamable HTTP as primary transport
- interoperability with spec-conforming MCP clients

## 4.2 Primary Conclusion

The current `/mcp` surface should be treated as:

- **Partially Compliant** at the method level
- **Non-Compliant** at the transport-model level
- therefore **Not Releasable as MCP 2025-03-26 compliant**

---

## 5. Conformance Matrix

| Area | Spec Expectation | Current Implementation Reading | Status | Notes |
|---|---|---|---|---|
| Protocol identity | Server must behave as MCP `2025-03-26` | Current implementation has recently been treated in surrounding docs as a “minimal HTTP MCP path” rather than a demonstrated spec-conforming server | Non-Compliant | The project framing itself suggests drift from the required target. |
| JSON-RPC 2.0 base format | MCP messages use JSON-RPC 2.0 | Current implementation appears to use JSON-RPC-shaped objects and responses | Partially Compliant | JSON-RPC shape alone is necessary but not sufficient. |
| Initialization first | `initialize` must be the first interaction | Current implementation visibly handles `initialize` | Partially Compliant | Handling the method is not enough; sequencing and lifecycle rules must also hold. |
| Initialize request shape | Client sends `protocolVersion`, `capabilities`, `clientInfo` | Current implementation likely accepts `initialize`, but prior code evidence suggested weak or custom handling | Partially Compliant | Must validate and negotiate according to the spec, not merely echo a reply. |
| Protocol version negotiation | Server must respond with supported version and negotiate correctly | Prior visible implementation returned `2024-11-05` rather than `2025-03-26` | Non-Compliant | This is a direct version mismatch against the required target. |
| Initialized notification | Client must send `notifications/initialized`; server behavior must respect lifecycle | Prior visible implementation appears to use `initialized` rather than `notifications/initialized` | Non-Compliant | Method naming mismatch indicates lifecycle non-conformance. |
| Post-initialize lifecycle discipline | Client/server must limit behavior before initialization completes | No strong evidence this is enforced | Unverified | Needs explicit audit and tests. |
| Server capabilities shape | Must advertise capabilities in spec-compatible structure | Prior visible implementation likely returned a minimal capabilities object only | Partially Compliant | Likely under-declared or not aligned with actual supported features. |
| Tools capability declaration | If tools are supported, `capabilities.tools` must be declared | Current implementation appears to expose tools | Partially Compliant | Needs exact shape validation, including optional `listChanged` semantics if used. |
| Resources capability declaration | If resources are supported, `capabilities.resources` must be declared | Current implementation appears to expose resources in some form | Partially Compliant | Needs exact shape validation and scope confirmation. |
| Logging capability declaration | If logging is supported, must be declared correctly | No clear evidence of spec-level logging capability handling | Unverified | Structured logging in the app is not the same as MCP logging capability. |
| Streamable HTTP endpoint model | Single MCP endpoint supports both POST and GET | Current implementation appears centered on custom request handling at `/mcp`; GET support is not established | Non-Compliant | This is one of the most important transport gaps. |
| POST handling | Client sends JSON-RPC messages via POST with correct accept semantics | Current implementation appears to accept POST-like JSON bodies | Partially Compliant | Needs exact header/content negotiation and request category behavior. |
| GET handling for SSE | Server must support GET SSE stream or return 405 | No strong evidence that GET SSE or 405 behavior is implemented correctly | Non-Compliant | Missing or unverified core Streamable HTTP behavior. |
| Response mode for request-bearing POST | Server must return either `application/json` or `text/event-stream` appropriately | Current implementation appears to return plain JSON responses directly | Partially Compliant | This may be acceptable in some cases, but not as a substitute for full Streamable HTTP behavior. |
| SSE streaming support | Server may stream responses/notifications/requests over SSE; client must interoperate | No evidence of real SSE stream handling | Non-Compliant | Strong sign that transport implementation is incomplete. |
| Session management | Server may assign `Mcp-Session-Id`; if used, client/server must honor semantics | No strong evidence of spec-compliant session management | Unverified | If absent by design, needs explicit decision; if partially present, likely non-compliant. |
| Origin validation | Streamable HTTP servers must validate `Origin` header | No evidence this is implemented | Non-Compliant | Spec explicitly calls this out for security. |
| Local bind guidance | Local deployment should prefer localhost binding | Current local defaults appear to include `0.0.0.0` | Partially Compliant | May be acceptable operationally in containers, but spec guidance should still be addressed consciously. |
| Tool discovery | `tools/list` supported with spec-compatible result | Current implementation appears to support `tools/list` | Partially Compliant | Needs pagination semantics and exact result shape review. |
| Tool pagination | `tools/list` supports pagination with `cursor`/`nextCursor` | No evidence this is implemented | Non-Compliant | Spec-defined feature currently appears absent. |
| Tool result shape | `tools/call` returns `content` and `isError` as appropriate | Current implementation likely returns `content`, but `isError` handling is not clearly aligned | Partially Compliant | Business/tool execution errors may be mapped incorrectly. |
| Protocol vs tool execution errors | Unknown tool / invalid args should be JSON-RPC errors; execution failures should use `result.isError` | Current implementation likely collapses many failures into generic JSON-RPC errors or local conventions | Non-Compliant | Important interoperability and semantic issue. |
| Tool input schema exposure | Tools should expose JSON Schema inputSchema | Current implementation appears to expose schemas | Compliant | This is one of the stronger aligned areas. |
| Resource listing | `resources/list` supported in spec-compatible result | Current implementation appears to have some resource handling | Partially Compliant | Needs pagination and exact data type review. |
| Resource reading | `resources/read` supported in spec-compatible result | Current implementation appears to have some read handling | Partially Compliant | Needs exact contents shape and error mapping review. |
| Resource templates | `resources/templates/list` exists in the spec | No evidence of implementation | Unverified | May be optional depending on scope, but absence should be explicit. |
| Resource subscriptions | Optional capability if supported | No evidence of implementation | Unverified | Fine if unsupported, but capability and behavior must be honest. |
| Resource list-changed notifications | Optional if declared | No evidence of implementation | Unverified | Same constraint as above. |
| Tool list-changed notifications | Optional if declared | No evidence of implementation | Unverified | Same constraint as above. |
| Notifications method names | MCP notification names must match the spec | Prior evidence suggests at least one lifecycle notification name mismatch | Non-Compliant | Needs full method-name audit. |
| Batch constraints on initialize | `initialize` must not be part of a batch | No evidence this is enforced | Unverified | Should be explicitly validated. |
| HTTP 202 behavior for notification/response-only POSTs | Required by Streamable HTTP transport | No evidence of full request-category handling | Non-Compliant | Current endpoint likely behaves as a simpler RPC API. |
| HTTP DELETE session termination semantics | Optional, but if sessions are used the behavior must align | No evidence | Unverified | Secondary but still part of proper transport design if sessions are introduced. |
| Client interoperability expectation | Conforming MCP client should not need special casing | Current design likely requires `ctxledger`-specific assumptions | Non-Compliant | This is the core release failure mode. |

---

## 6. Detailed Findings

## 6.1 Stronger Areas

The current implementation direction appears relatively stronger in these areas:

- domain-level workflow tool logic
- JSON-RPC-shaped request/response handling
- tool schema exposure
- visible workflow and resource concepts
- use of `/mcp` as a dedicated endpoint
- reuse of shared business logic across surfaces

These are useful foundations, but they do not establish MCP `2025-03-26` compliance on their own.

---

## 6.2 Most Serious Compliance Failures

The most serious current failures are likely:

1. **Protocol version mismatch**
   - visible evidence previously pointed to `2024-11-05`
   - required target is `2025-03-26`

2. **Lifecycle method mismatch**
   - visible evidence previously suggested `initialized`
   - spec requires `notifications/initialized`

3. **Transport model mismatch**
   - current `/mcp` appears to behave as a direct RPC endpoint
   - spec requires Streamable HTTP semantics, including POST/GET behavior and SSE handling

4. **Missing or unproven SSE behavior**
   - no strong evidence of compliant Streamable HTTP behavior

5. **Incorrect or incomplete error semantics**
   - likely conflation of protocol errors and tool execution errors

6. **Missing pagination for tools/resources**
   - spec expects pagination support
   - current implementation likely omits it

7. **Missing required security behavior**
   - no evidence of `Origin` validation

These are not polish issues. They indicate that the primary HTTP MCP surface is probably aimed at the wrong conformance target.

---

## 7. Transport-Level Verdict

## 7.1 Current `/mcp` Classification

The current `/mcp` implementation should be classified as:

- **Not yet a demonstrated MCP 2025-03-26 Streamable HTTP transport**
- **Likely a custom partial MCP-like transport**
- **Insufficient for release acceptance**

## 7.2 Practical Interpretation

The question is not:

- “Can `/mcp` answer `initialize`, `tools/list`, and `tools/call`?”

The real question is:

- “Can a spec-conforming MCP 2025-03-26 client use `/mcp` as a Streamable HTTP MCP server without any `ctxledger`-specific behavior?”

Current evidence says:

- **No, not yet**

---

## 8. Required Remediation Priorities

## Priority 1 — Replace or Correct the HTTP Transport Model

The project should first determine whether the current HTTP transport can be salvaged.

If it is fundamentally a custom JSON-RPC-over-POST implementation, then the preferred move is:

- preserve domain/service logic
- replace transport machinery
- target real Streamable HTTP behavior

## Priority 2 — Fix Lifecycle Compliance

Before broadening feature coverage:

- correct version negotiation
- correct notification names
- enforce initialization rules

## Priority 3 — Fix Error Semantics

The implementation must separate:

- protocol errors
- tool execution errors

according to MCP expectations.

## Priority 4 — Complete Spec-Surface Gaps

After transport and lifecycle are corrected:

- tools pagination
- resources pagination
- required resource support
- optional capability honesty
- SSE/session behavior
- security requirements

---

## 9. Recommended Next Artifact

The next useful artifact after this audit is:

- a **transport rewrite / adaptation decision memo**

That memo should answer:

1. Can the current `/mcp` handler be evolved into compliant Streamable HTTP?
2. Or should it be replaced with a proper MCP runtime abstraction for HTTP transport?
3. Which current components are transport-agnostic and can be preserved?

---

## 10. Final Audit Verdict

### Current Verdict

`ctxledger` is currently best classified as:

- **Partially MCP-like**
- **Not yet MCP 2025-03-26 conformant**
- **Blocked for release as a compliant remote MCP server**

### Why

Because the repository requirement is:

- MCP `2025-03-26`
- Streamable HTTP primary
- real MCP client interoperability

and the currently visible implementation appears to provide:

- a custom minimal HTTP method surface
- incomplete lifecycle compliance
- incomplete transport compliance
- incomplete spec fidelity

### Final Standard

The release should remain blocked until the answer to this question becomes yes:

> Is `/mcp` a spec-conforming MCP `2025-03-26` Streamable HTTP server that real MCP clients can use without special handling?

At the time of this audit:

> **No**