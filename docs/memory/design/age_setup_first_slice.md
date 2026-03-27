# Minimum AGE Setup Approach for the First `0.6.0` Graph Slice

> Historical design record:
> this document captures the first-slice `0.6.0` AGE setup posture.
> For the current release-facing posture, read the `0.9.0` release and product docs first.

## Purpose

This note defines the **minimum setup and operational approach** for the first
Apache AGE-related slice in `0.6.0`.

Its purpose is to clarify:

- how AGE should enter the system
- who is responsible for setup/bootstrap
- how local, dev, and test environments should behave
- how failure and degradation should be handled in the first slice

This note is intentionally narrower than a full graph-retrieval design.

It does **not** define graph-backed retrieval behavior yet.

---

## Scope

This note covers:

- AGE setup approach for the first slice
- bootstrap responsibility
- environment expectations
- optionality vs requirement
- failure and degradation expectations
- the minimum implementation boundary for this first step

This note does **not** cover:

- graph-backed `memory_get_context` behavior
- graph traversal semantics
- relation expansion
- grouped response changes
- graph-first ranking or planning
- broader Apache AGE adoption beyond the first slice

---

## Relationship to the First-Slice `0.6.0` Retrieval Contract

The first-slice `0.6.0` memory retrieval contract remains:

- relational first
- behavior-preserving outside the active target area
- constrained in relation-aware behavior
- explicitly documented and test-backed in its current grouped reading

That means this first AGE setup slice should be read as:

- preparatory
- operational
- architectural

rather than as a visible retrieval-behavior change.

In particular:

- `memory_get_context` should remain behaviorally unchanged in this slice
- grouped response structure should remain unchanged in this slice
- current relation-aware behavior should remain constrained and relationally
  driven in this slice

This setup slice exists to create a safe and explicit foundation for later
graph-oriented work, not to introduce graph semantics early.

---

## Current Recommendation

For the first `0.6.0` AGE slice, the recommended approach is:

- **boundary-first**
- **bootstrap-first**
- **behavior-preserving**
- **optional by default in the first slice**

In practice, that means:

- define how AGE is expected to be provisioned and initialized
- define how the application behaves when AGE is unavailable
- keep current retrieval behavior on the relational path
- avoid making AGE a hidden runtime prerequisite for existing memory retrieval

This recommendation matches the broader `0.6.0` direction:

- incremental over sweeping
- operational clarity before opaque behavior
- relational first, graph where justified
- avoid premature abstraction

---

## Setup Responsibility

The first AGE slice should make setup responsibility explicit.

### Recommended ownership model

The first slice should treat AGE setup as an **explicit setup concern**, not as
an implicit side effect of retrieval behavior.

The preferred initial responsibility split is:

- **schema / extension availability**
  - handled by explicit database setup or migration responsibility
- **application runtime expectations**
  - handled by explicit startup checks or configuration-aware validation
- **retrieval behavior**
  - unchanged unless a later graph-backed slice explicitly opts in

### Recommended first-step rule

The application should **not** silently introduce AGE-dependent retrieval logic
before the deployment/setup path is clear.

That means the first slice should prefer:

- explicit configuration or documented setup expectations
- explicit detection of whether AGE support is available
- explicit degradation behavior when it is not

rather than hidden best-effort graph usage.

---

## Optionality and Degradation

The first slice should define AGE as **optional by default** unless a deployment
explicitly enables and provisions it.

### Why optional first

This keeps the first graph-oriented slice aligned with the current
behavior-preserving milestone direction.

It also reduces the risk of:

- local development friction
- test fragility
- environment drift
- accidental breakage of stable relational retrieval paths

### Degradation rule

If AGE is unavailable in the first slice:

- existing relational behavior should continue to work
- the application should not silently change retrieval semantics
- graph-dependent later slices should either:
  - remain disabled, or
  - fail explicitly at the graph-specific boundary

### Practical reading

In the first slice:

- no existing `memory_get_context` call should become graph-required
- graph unavailability should not be reinterpreted as a retrieval logic bug
- graph availability should be understood as an environment/setup capability,
  not as a hidden behavioral assumption

---

## Local / Dev / Test Expectations

The first slice should make expectations explicit across environments.

### Local development

Recommended default:

- AGE is optional in local development
- local relational workflows should remain usable without AGE
- developers should be able to opt in explicitly when working on graph slices

This lowers adoption friction while keeping graph work possible.

### Development / shared environments

Recommended default:

- graph availability should be explicit
- environments intended to exercise graph-specific paths should provision AGE
- environments not intended for graph work may remain relational-only

### Test environments

Recommended default:

- AGE should be optional by default for broad test suites
- graph-specific tests should opt in explicitly
- stable relational tests should not become graph-dependent by accident

This helps keep the current test suite aligned with the current relational-first
contract.

### Production-like environments

Recommended default:

- AGE expectations should be explicit in deployment/setup documentation
- if a later graph-backed slice is introduced, graph availability should be
  enforced at that graph-specific boundary rather than assumed globally too early

---

## Minimum Implementation Boundary

The first slice should keep implementation narrow.

If code changes are made in this slice, they should be limited to setup-oriented
or detection-oriented concerns such as:

- configuration support for graph enablement or graph availability expectations
- setup/bootstrap helper boundaries
- startup validation or health-check style checks
- explicit no-op or disabled-state handling for graph-first features not yet in use

This first slice should **not** yet include:

- graph-backed retrieval queries
- graph-driven relation expansion
- grouped response changes
- new graph-derived retrieval routes
- new user-visible graph semantics

The implementation boundary should stay firmly on the setup/operational side.

---

## Relation to Canonical Storage

The first slice should preserve the current canonical reading:

- the relational database remains the system of record

In the first slice, the graph layer should be treated as:

- supplementary
- derived or support-oriented
- not yet the canonical source of retrieval truth

This boundary should remain explicit until a later slice intentionally introduces
a constrained graph-backed read path.

---

## Follow-up Slice After Setup

Once the setup and operational boundary are explicit, the most natural next
graph-oriented candidate is:

- a **constrained internal graph-backed read prototype**

The recommended shape for that later prototype would still remain narrow, such
as:

- one-hop only
- `supports` only
- behavior-preserving where possible
- no grouped-response redesign
- no graph-first semantics

That later prototype should only proceed after the first setup slice has made
the operational footing explicit.

---

## Non-Goals

This first setup slice should not attempt to do any of the following:

- change `memory_get_context` behavior
- broaden relation traversal
- add new response fields
- redesign grouped output
- introduce graph-first retrieval semantics
- decide full graph query semantics
- replace the relational canonical model
- overbuild a generalized graph abstraction layer before the first concrete graph
  usage is justified

---

## Working Rule

Use this rule for the first AGE slice:

- **make setup explicit**
- **make optionality explicit**
- **make degradation explicit**
- **do not change retrieval behavior yet**

This keeps the first graph-oriented step small, testable, and operationally
clear.

---

## Decision Summary

For the first `0.6.0` AGE-related slice, the minimum setup approach should:

- define explicit setup and bootstrap expectations
- treat AGE as optional by default in the first slice
- preserve the current relational retrieval behavior
- prepare a clean footing for a later constrained graph-backed prototype

The graph layer should enter the system first as a clearly bounded operational
and architectural capability, not yet as a retrieval-semantics expansion.