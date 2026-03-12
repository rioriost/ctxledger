# MCP Review Gate Checklist

## 1. Purpose

This document defines the review gates for the MCP rewrite PR sequence in `ctxledger`.

It exists to answer one practical question for each PR in the rewrite stream:

> What must be true before this PR is allowed to merge?

The intent is to keep the rewrite honest to the repository contract established by:

- `docs/specification.md`

and to prevent the project from drifting back toward:

- custom JSON-RPC-over-HTTP behavior
- weakened acceptance language
- transport shortcuts that appear to work locally but are not MCP `2025-03-26` compliant

This checklist is downstream of:

- `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/plans/mcp_2025_03_26_conformance_audit.md`
- `docs/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/plans/mcp_transport_rewrite_execution_plan.md`
- `docs/plans/mcp_transport_cutover_checklist.md`
- `docs/plans/mcp_module_split_proposal.md`
- `docs/plans/mcp_first_patch_plan.md`
- `docs/plans/mcp_second_patch_plan.md`
- `docs/plans/mcp_third_patch_plan.md`
- `docs/plans/mcp_pr_sequence_overview.md`

---

## 2. Global Review Rule

Every PR in the MCP rewrite must satisfy this rule:

> A PR may improve structure, transport semantics, feature binding, or testing, but it must never weaken the requirement that `/mcp` become an MCP `2025-03-26` Streamable HTTP server.

That means reviewers must reject any PR that:

- treats a custom minimal `/mcp` path as good enough
- re-centers correctness on stdio behavior
- weakens docs to match an incomplete implementation
- preserves wrong lifecycle names or version behavior for convenience
- confuses auxiliary HTTP routes with MCP protocol evidence

---

## 3. Global Must-Not-Regress Conditions

These conditions apply to **all** PRs in the sequence.

A PR must not:

1. edit `docs/specification.md`
2. weaken the MCP `2025-03-26` requirement
3. broaden the old custom `/mcp` path as if it were the release target
4. introduce new transport-specific business logic forks unless absolutely necessary
5. break canonical workflow persistence behavior
6. break startup / health / readiness behavior without explicit intended replacement
7. blur the distinction between:
   - MCP transport
   - workflow-specific HTTP routes
   - operator/action routes
   - debug routes
8. use passing local endpoint tests as a substitute for protocol correctness
9. reintroduce acceptance language based on “minimal MCP-like” behavior

---

## 4. PR Sequence Covered by This Checklist

This checklist assumes the following PR order:

1. **PR 1 — MCP package bootstrap extraction**
2. **PR 2 — Lifecycle and Streamable HTTP scaffold**
3. **PR 3 — Result mapping and required feature binding**
4. **PR 4 — Transport hardening and `/mcp` cutover**
5. **PR 5 — Post-cutover cleanup and documentation convergence**

Each PR has its own merge gate below.

---

## 5. PR 1 Review Gate — MCP Package Bootstrap Extraction

## 5.1 Intent of PR 1

PR 1 is a refactor-preserving extraction patch.

It should:

- create the MCP package structure
- move reusable schemas and handlers out of `server.py`
- preserve behavior
- avoid changing MCP transport semantics

It should **not** try to become a compliance patch.

---

## 5.2 PR 1 Merge Conditions

PR 1 may merge only if all of the following are true:

- [ ] `src/ctxledger/mcp/` package exists
- [ ] tool schemas are extracted from `src/ctxledger/server.py`
- [ ] transport-neutral tool handler builders are extracted
- [ ] resource URI / handler logic is extracted where safe
- [ ] `src/ctxledger/server.py` is smaller and has fewer MCP business concerns
- [ ] existing behavior is preserved
- [ ] no transport-level semantics have changed accidentally
- [ ] no acceptance claims are changed
- [ ] imports are explicit and readable
- [ ] no serious circular import problem is introduced
- [ ] existing tests pass or require only import-stability adjustments

---

## 5.3 PR 1 Reject Conditions

PR 1 must be rejected if any of the following occur:

- [ ] it changes `/mcp` lifecycle behavior
- [ ] it changes protocol version handling
- [ ] it introduces SSE / session / GET semantics
- [ ] it changes acceptance framing
- [ ] it expands into a transport rewrite
- [ ] it makes `server.py` look cleaner without actually extracting reusable MCP assets

---

## 6. PR 2 Review Gate — Lifecycle and Streamable HTTP Scaffold

## 6.1 Intent of PR 2

PR 2 introduces the first real protocol-facing authority outside `server.py`.

It should:

- introduce `mcp/lifecycle.py`
- introduce `mcp/streamable_http.py`
- begin defining `/mcp` as a real MCP endpoint
- scaffold GET/POST and lifecycle ownership
- remain intentionally incomplete

---

## 6.2 PR 2 Merge Conditions

PR 2 may merge only if all of the following are true:

- [ ] `mcp/lifecycle.py` exists
- [ ] `mcp/streamable_http.py` exists
- [ ] lifecycle ownership begins moving out of `server.py`
- [ ] `initialize` handling is no longer only embedded in the old generic dispatcher
- [ ] `notifications/initialized` is introduced as the correct lifecycle name
- [ ] protocol version handling is no longer hardcoded in the old path as the only authority
- [ ] `/mcp` is represented through a new protocol-oriented transport scaffold
- [ ] GET handling is at least explicitly scaffolded
- [ ] old custom `/mcp` logic is clearly transitional
- [ ] non-MCP HTTP routes still behave correctly
- [ ] no false claim of full compliance is made

---

## 6.3 PR 2 Reject Conditions

PR 2 must be rejected if any of the following occur:

- [ ] it creates new lifecycle/transport files but leaves all real authority in `server.py`
- [ ] it still treats `initialized` as the correct lifecycle notification
- [ ] it still hardcodes a wrong protocol version as the canonical behavior
- [ ] it claims compliance without feature traffic or transport hardening
- [ ] it introduces broad feature binding too early
- [ ] it makes the new transport purely cosmetic

---

## 7. PR 3 Review Gate — Result Mapping and Required Feature Binding

## 7.1 Intent of PR 3

PR 3 is the first patch where the new `/mcp` path becomes meaningfully useful.

It should:

- introduce result mapping
- separate protocol errors from execution errors
- bind required workflow tools into the new transport
- begin protocol-oriented feature tests

---

## 7.2 PR 3 Merge Conditions

PR 3 may merge only if all of the following are true:

- [ ] `mcp/result_mapping.py` exists
- [ ] the local `ok/result/error` envelope is no longer the final transport-facing MCP result model
- [ ] the new transport supports `tools/list`
- [ ] the new transport supports `tools/call`
- [ ] required workflow tools are visible on the new transport:
  - [ ] `workspace_register`
  - [ ] `workflow_start`
  - [ ] `workflow_checkpoint`
  - [ ] `workflow_resume`
  - [ ] `workflow_complete`
- [ ] protocol errors are distinguished from tool execution failures more cleanly
- [ ] tool schemas are surfaced through the new transport
- [ ] protocol-oriented tests exist for the new tool path
- [ ] old `/mcp` assumptions are reduced rather than deepened
- [ ] unrelated workflow/debug/operator routes remain stable

---

## 7.3 PR 3 Conditional Acceptance for Resources

PR 3 may still merge if workflow resources are not yet fully bound to the new transport, but only if all of the following are true:

- [ ] the omission is explicit
- [ ] the omission is documented in PR notes or code comments
- [ ] resource work is clearly deferred to the next patch
- [ ] no one claims that the resource surface is already complete

---

## 7.4 PR 3 Reject Conditions

PR 3 must be rejected if any of the following occur:

- [ ] execution failures are still flattened into protocol errors
- [ ] `tools/list` works only through old custom `/mcp` behavior
- [ ] required workflow tools are not really owned by the new transport
- [ ] the new result mapping is still driven by local ad hoc envelopes
- [ ] the patch binds too many optional features and becomes unreviewable
- [ ] tests still prove only local custom behavior instead of MCP-oriented semantics

---

## 8. PR 4 Review Gate — Transport Hardening and `/mcp` Cutover

## 8.1 Intent of PR 4

PR 4 is the transport-hardening patch.

It should:

- complete the core Streamable HTTP behavior needed for the primary transport
- harden `/mcp` toward real MCP interoperability
- retire or quarantine the old custom `/mcp` path

---

## 8.2 PR 4 Merge Conditions

PR 4 may merge only if all of the following are true:

- [ ] `/mcp` is now clearly owned by the new transport path
- [ ] GET behavior is implemented according to the intended transport design
- [ ] SSE behavior is implemented to the required level for the chosen design
- [ ] request category handling is no longer ad hoc
- [ ] 202 behavior is implemented where required
- [ ] `Origin` validation exists
- [ ] session behavior is either:
  - [ ] implemented correctly, or
  - [ ] explicitly omitted with honest handling and no misleading claims
- [ ] old custom `/mcp` logic is retired or clearly quarantined
- [ ] transport-oriented tests exist for the hardened path
- [ ] no release-facing docs continue to point at the old custom behavior
- [ ] the new path is the only credible acceptance target

---

## 8.3 PR 4 Reject Conditions

PR 4 must be rejected if any of the following occur:

- [ ] `/mcp` still depends on the old custom handler in practice
- [ ] GET/SSE/request-category semantics are still largely missing
- [ ] `Origin` validation is absent
- [ ] old and new `/mcp` paths coexist ambiguously
- [ ] transport hardening is claimed without corresponding tests
- [ ] compliance is claimed while core transport semantics remain approximate

---

## 9. PR 5 Review Gate — Post-Cutover Cleanup and Documentation Convergence

## 9.1 Intent of PR 5

PR 5 finishes the rewrite stream by aligning repository wording, code cleanliness, and acceptance framing with the actual implementation state.

It should:

- remove obsolete custom transport assumptions
- converge docs outside `specification.md`
- clarify stdio’s place
- finalize acceptance evidence direction

---

## 9.2 PR 5 Merge Conditions

PR 5 may merge only if all of the following are true:

- [ ] obsolete custom `/mcp` references are removed or clearly marked historical
- [ ] docs outside `specification.md` are aligned with the actual compliant target
- [ ] docs no longer use weakened framing such as:
  - [ ] “minimal MCP path is enough”
  - [ ] “custom HTTP MCP surface is acceptable”
  - [ ] “MCP-like HTTP transport”
- [ ] stdio’s role is explicitly and correctly described
- [ ] acceptance evidence docs no longer rely on the wrong transport assumptions
- [ ] code and docs point at the same primary transport target
- [ ] no misleading transitional wording remains in release-facing materials

---

## 9.3 PR 5 Reject Conditions

PR 5 must be rejected if any of the following occur:

- [ ] docs still understate the requirement from `specification.md`
- [ ] release framing still permits custom non-compliant `/mcp` behavior
- [ ] stdio is still implicitly treated as the acceptance center
- [ ] cleanup is partial in a way that leaves major ambiguity
- [ ] implementation reality and docs still materially disagree

---

## 10. Cross-PR Gate: When to Pause the Sequence

The PR sequence should pause and be re-evaluated if any PR reveals that:

- the chosen transport model is still wrong
- current business handlers are more transport-coupled than expected
- required workflow resources cannot be cleanly expressed through the new transport design
- session/SSE requirements force a bigger architectural change than planned
- the current test strategy cannot distinguish protocol compliance from custom local success

If any of these become true, the correct response is:

- re-open the execution plan
- update the cutover checklist
- narrow or split the next PR
- do **not** paper over the mismatch with docs

---

## 11. Cross-PR Gate: Minimum Conditions Before Claiming “Compliant”

No PR, and no combination of partially finished PRs, should be used to claim MCP `2025-03-26` compliance until all of the following are true:

- [ ] lifecycle behavior is correct
- [ ] version handling is correct
- [ ] `notifications/initialized` is correct
- [ ] `/mcp` follows the intended Streamable HTTP shape
- [ ] required workflow tools are discoverable
- [ ] required workflow tools are invokable
- [ ] required resources are compliant or explicitly out of scope
- [ ] protocol errors and execution errors are separated correctly
- [ ] transport-oriented tests prove the behavior
- [ ] docs outside `specification.md` do not weaken the requirement

Until then, the repository should be treated as:

- under remediation
- not yet compliant
- not yet releasable as a conformant MCP remote server

---

## 12. Reviewer Questions by Stage

Reviewers should ask these questions at each stage.

### PR 1 reviewers should ask
- Did this reduce coupling without changing behavior?
- Did we move the right reusable assets?
- Did we avoid premature protocol work?

### PR 2 reviewers should ask
- Is protocol authority really beginning to move out of `server.py`?
- Is `notifications/initialized` now the intended lifecycle direction?
- Is `/mcp` beginning to look like a transport endpoint rather than a generic route?

### PR 3 reviewers should ask
- Does the new transport now carry real MCP features?
- Are result semantics becoming MCP-correct?
- Are execution failures still being mishandled?

### PR 4 reviewers should ask
- Is the new transport actually the primary path now?
- Are Streamable HTTP semantics really hardened?
- Is the old handler truly out of the acceptance path?

### PR 5 reviewers should ask
- Does the repository now honestly describe what it implements?
- Has documentation drift been fully corrected?
- Is there any remaining ambiguity about the transport contract?

---

## 13. Final Gate Before Release Closeout

Before release closeout is even discussed, reviewers should confirm:

- [ ] the PR sequence reached PR 4 or PR 5 successfully
- [ ] the old custom `/mcp` path is not the practical primary route anymore
- [ ] protocol-oriented tests are passing on the new path
- [ ] docs outside `specification.md` are aligned
- [ ] no one is relying on “good enough” local endpoint behavior as evidence

If any of those are false, closeout discussion is premature.

---

## 14. Final Recommendation

Use this checklist as the merge gate for every MCP rewrite PR.

The key review discipline is simple:

- PR 1 must make extraction safer
- PR 2 must establish protocol ownership
- PR 3 must establish feature usefulness
- PR 4 must establish transport credibility
- PR 5 must establish repository honesty

Any PR that fails its stage-specific role should be revised rather than merged.