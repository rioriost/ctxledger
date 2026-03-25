# MCP Planning Index

## 1. Purpose

This document provides a single index and recommended reading order for the MCP transport rewrite planning materials in `ctxledger`.

For authentication, proxy, and deployment-boundary planning materials, see also:

- `docs/plans/auth_planning_index.md`

It is intended to help a new contributor, reviewer, or future session quickly answer:

1. What problem are we solving?
2. What is the current compliance status?
3. What architectural decision has already been made?
4. What implementation sequence is expected?
5. What are the merge/release gates?

This index does **not** redefine any requirement.
The source contract remains:

- `docs/specification.md`

In particular, the planning set assumes:

- MCP `2025-03-26` compatibility is required
- Streamable HTTP is the primary transport
- `/mcp` must become a real spec-conforming MCP endpoint
- custom MCP-like HTTP behavior is not acceptable as the release target

---

## 2. Recommended Reading Order

Read the documents in this order.

### Step 1 — Source Contract
1. `docs/specification.md`

Read this first and treat it as non-negotiable.
It defines the repository-level expectation that the MCP server is:

- MCP `2025-03-26` compatible
- Streamable HTTP first
- remote-client interoperable

---

### Step 2 — Why Remediation Exists
2. `docs/plans/mcp_2025_03_26_compliance_remediation_plan.md`

Read this next to understand:

- why the current `/mcp` direction is not sufficient
- why “minimal MCP-like HTTP” is not acceptable
- what the remediation is supposed to achieve

Use this as the top-level problem statement.

---

### Step 3 — Current State Assessment
3. `docs/plans/mcp_2025_03_26_conformance_audit.md`

Read this to understand:

- what is currently compliant
- what is partially compliant
- what is non-compliant
- what is still unverified

This is the best document for answering:
“What is wrong with the current implementation?”

---

### Step 4 — Core Decision
4. `docs/plans/mcp_transport_rewrite_decision_memo.md`

Read this to understand the primary architectural decision:

- do **not** incrementally patch the custom `/mcp` path as the final answer
- instead, replace the transport-facing HTTP MCP machinery
- preserve transport-agnostic workflow/business logic where possible

This is the document that answers:
“Are we patching or rewriting?”

---

### Step 5 — End-to-End Execution Strategy
5. `docs/plans/mcp_transport_rewrite_execution_plan.md`

Read this for the broad implementation workstreams:

- freeze and isolate the current custom transport
- extract reusable core
- implement compliant transport foundation
- bind features
- replace local tests with protocol-oriented tests
- remove obsolete code and drift

This is the best document for answering:
“What is the overall implementation sequence?”

---

### Step 6 — File/Function-Level Cutover
6. `docs/project/releases/plans/mcp_transport_cutover_checklist.md`

Read this when you need to work directly in code.
It maps current implementation responsibilities into:

- Preserve
- Extract
- Replace
- Delete / Quarantine

This is the best document for answering:
“What exactly in `server.py` should be kept versus replaced?”

---

### Step 7 — Module Structure Direction
7. `docs/project/releases/plans/mcp_module_split_proposal.md`

Read this when you need to decide where code should live after the rewrite.

It proposes the `ctxledger.mcp` package split, including modules such as:

- `lifecycle.py`
- `streamable_http.py`
- `tool_schemas.py`
- `tool_handlers.py`
- `resource_handlers.py`
- `result_mapping.py`

This is the best document for answering:
“How should we restructure the codebase?”

---

### Step 8 — PR-by-PR Implementation Sequence
8. `docs/project/releases/plans/mcp_pr_sequence_overview.md`

Read this for the practical review/implementation order:

1. PR 1 — extraction
2. PR 2 — lifecycle + transport scaffold
3. PR 3 — result mapping + feature binding
4. PR 4 — transport hardening + cutover
5. PR 5 — cleanup + doc convergence

This is the best document for answering:
“What order should implementation happen in?”

---

### Step 9 — Patch-Level Planning
9. `docs/project/releases/plans/mcp_first_patch_plan.md`
10. `docs/project/releases/plans/mcp_second_patch_plan.md`
11. `docs/project/releases/plans/mcp_third_patch_plan.md`

Read these only after the higher-level documents above.

They define the expected scope and non-goals of each patch:

- Patch 1: extraction only
- Patch 2: lifecycle and Streamable HTTP scaffold
- Patch 3: result mapping and required feature binding

These are the best documents for answering:
“What should this specific patch do, and what should it avoid doing?”

---

### Step 10 — Review Gates
12. `docs/project/releases/plans/mcp_review_gate_checklist.md`

Read this before opening or reviewing any MCP rewrite PR.

It defines:

- merge conditions
- reject conditions
- cross-PR pause conditions
- minimum standards before anyone can claim compliance

This is the best document for answering:
“What must be true before this PR is allowed to merge?”

---

### Step 11 — Final Release Gate
13. `docs/project/releases/plans/mcp_release_acceptance_checklist.md`

Read this last.

This is the release-closeout checklist, not a progress tracker.
It answers:

- when `v0.1.0` is still blocked
- when `v0.1.0` may proceed to closeout review
- what “acceptable as an MCP server” actually means at release time

This is the best document for answering:
“Can we close out the release yet?”

---

## 3. Quick Reference by Question

Use this section if you do not want to read everything in order.

### “What is the binding contract?”
- `docs/project/product/specification.md`

### “Why is the current `/mcp` not enough?”
- `docs/project/releases/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/project/releases/plans/mcp_2025_03_26_conformance_audit.md`

### “Are we rewriting or patching?”
- `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`

### “What is the implementation strategy?”
- `docs/project/releases/plans/mcp_transport_rewrite_execution_plan.md`

### “What in the current code should be preserved or replaced?”
- `docs/project/releases/plans/mcp_transport_cutover_checklist.md`

### “How should the code be split into modules?”
- `docs/project/releases/plans/mcp_module_split_proposal.md`

### “What order should PRs land in?”
- `docs/project/releases/plans/mcp_pr_sequence_overview.md`

### “What should Patch 1 / Patch 2 / Patch 3 do?”
- `docs/project/releases/plans/mcp_first_patch_plan.md`
- `docs/project/releases/plans/mcp_second_patch_plan.md`
- `docs/project/releases/plans/mcp_third_patch_plan.md`

### “What must be true before merging a PR?”
- `docs/project/releases/plans/mcp_review_gate_checklist.md`

### “What must be true before release closeout?”
- `docs/project/releases/plans/mcp_release_acceptance_checklist.md`

---

## 4. Suggested Reading Paths by Role

### For a new implementer
Read in this order:

1. `docs/project/product/specification.md`
2. `docs/project/releases/plans/mcp_2025_03_26_compliance_remediation_plan.md`
3. `docs/project/releases/plans/mcp_2025_03_26_conformance_audit.md`
4. `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`
5. `docs/project/releases/plans/mcp_transport_cutover_checklist.md`
6. `docs/project/releases/plans/mcp_module_split_proposal.md`
7. the relevant patch plan

### For a reviewer
Read in this order:

1. `docs/project/product/specification.md`
2. `docs/project/releases/plans/mcp_pr_sequence_overview.md`
3. the relevant patch plan
4. `docs/project/releases/plans/mcp_review_gate_checklist.md`

### For a release approver
Read in this order:

1. `docs/project/product/specification.md`
2. `docs/project/releases/plans/mcp_2025_03_26_conformance_audit.md`
3. `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`
4. `docs/project/releases/plans/mcp_release_acceptance_checklist.md`

### For a future session handoff
At minimum, read:

1. `docs/project/product/specification.md`
2. `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`
3. `docs/project/releases/plans/mcp_transport_cutover_checklist.md`
4. `docs/project/releases/plans/mcp_pr_sequence_overview.md`

---

## 5. Planning Set Summary

The current MCP planning set is organized into five layers.

### Layer 1 — Contract
- `docs/project/product/specification.md`

### Layer 2 — Problem and Assessment
- `docs/project/releases/plans/mcp_2025_03_26_compliance_remediation_plan.md`
- `docs/project/releases/plans/mcp_2025_03_26_conformance_audit.md`

### Layer 3 — Architectural Direction
- `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`
- `docs/project/releases/plans/mcp_module_split_proposal.md`

### Layer 4 — Execution and Patch Planning
- `docs/project/releases/plans/mcp_transport_rewrite_execution_plan.md`
- `docs/project/releases/plans/mcp_transport_cutover_checklist.md`
- `docs/project/releases/plans/mcp_first_patch_plan.md`
- `docs/project/releases/plans/mcp_second_patch_plan.md`
- `docs/project/releases/plans/mcp_third_patch_plan.md`
- `docs/project/releases/plans/mcp_pr_sequence_overview.md`

### Layer 5 — Review and Release Gates
- `docs/project/releases/plans/mcp_review_gate_checklist.md`
- `docs/project/releases/plans/mcp_release_acceptance_checklist.md`

---

## 6. Final Recommendation

If you only have time to read a minimal subset before implementation, read these five files:

1. `docs/project/product/specification.md`
2. `docs/project/releases/plans/mcp_2025_03_26_conformance_audit.md`
3. `docs/project/releases/plans/mcp_transport_rewrite_decision_memo.md`
4. `docs/project/releases/plans/mcp_transport_cutover_checklist.md`
5. `docs/project/releases/plans/mcp_review_gate_checklist.md`

That subset is the fastest way to understand:

- what the repository requires
- why the current implementation is insufficient
- what architectural decision was made
- what code should change
- what merge conditions must hold

If you are actively implementing the rewrite, then the full recommended order in Section 2 should be followed.