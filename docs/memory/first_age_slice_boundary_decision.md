# First AGE-Backed Graph Slice Boundary Decision

## Purpose

This note is the **canonical Phase A decision record** for the first Apache
AGE-backed graph slice in `0.6.0`.

It consolidates the repository’s current decision state around:

- graph ownership boundary
- bootstrap and initialization responsibility
- optionality vs required deployment expectations
- failure and degradation behavior
- the narrow recommended shape of the first graph-backed slice

This note is intended to be the primary reference for Plan `17.3` and the
Phase A requirement to settle setup and storage-boundary expectations before
expanding hierarchical retrieval behavior.

---

## Status

**Decision status:** active  
**Phase:** `0.6.0` Phase A  
**Plan relationship:** materially fulfills the Phase A decision portion of Plan
`17.3`

This note should be read as the repository’s current canonical answer to the
question:

> What should the first AGE-backed graph slice actually be, and under what
> operational boundary should it exist?

---

## Decision

For the current `0.6.0` stage, the first AGE-backed graph slice is:

- **boundary-first**
- **bootstrap-first**
- **behavior-preserving**

More concretely:

1. PostgreSQL relational storage remains the canonical system of record.
2. Apache AGE graph state is supplementary, derived, and rebuildable.
3. AGE setup, graph creation, and graph population must be explicit.
4. Runtime graph usage must be gated by capability/readiness checks.
5. Graph absence, unavailability, or graph-read failure must degrade to the
   relational path rather than redefining ordinary memory retrieval as failed.
6. The first slice must not broaden visible `memory_get_context` semantics just
   because AGE exists.

This is the Phase A conclusion that should govern follow-on work.

---

## Why this is the correct first slice

The first AGE-backed slice should not begin by changing retrieval semantics.

At the current stage, the most important unresolved questions are not about
multi-hop traversal, ranking, or summary-driven graph assembly.

They are about:

- where the graph layer begins and ends
- what remains canonical
- who is responsible for setup and readiness
- what happens when graph support is absent or degraded
- how to avoid accidental behavioral drift

That makes the correct first slice an **operational and architectural boundary
decision**, not a retrieval-behavior expansion.

This preserves the broader `0.6.0` principles:

- incremental over sweeping
- relational first, graph where justified
- operational clarity before opaque behavior
- testable and explainable behavior
- no premature abstraction
- behavior preservation outside the active target area

---

## Phase A conclusions

## 1. Graph ownership boundary

### Canonical relational data remains authoritative

The canonical system of record remains relational PostgreSQL.

This includes the current and near-term canonical memory domain, especially:

- `memory_items`
- `memory_relations`
- workflow and workspace relational entities
- other durability-governed PostgreSQL-backed records

For the first AGE-backed slice, canonical truth must continue to come from
relational storage.

### AGE graph state is derived and supporting

The AGE graph layer should be treated as:

- supplementary
- derived
- rebuildable
- non-authoritative for truth
- repository-managed support state rather than canonical persistence

Graph state exists to support constrained traversal and future hierarchical
retrieval work.

It does **not** replace canonical durability rules.

### Practical ownership rule

Use this rule:

- relational tables own truth
- graph state mirrors only what is needed for constrained graph-backed access
- graph state may be rebuilt from relational state
- graph state absence does not imply relational data absence
- graph state incompleteness does not justify changing user-visible retrieval
  semantics

---

## 2. Bootstrap and initialization responsibility

The first AGE-backed slice must keep responsibility boundaries explicit.

### Responsibility split

#### A. Extension availability
Handled by:

- environment provisioning
- setup or startup automation
- operator-facing database preparation

Ordinary retrieval code must not be responsible for installing or enabling AGE.

#### B. Graph existence
Handled by:

- explicit setup/bootstrap logic
- explicit graph creation responsibility
- named graph lifecycle preparation

Ordinary retrieval code must not lazily create the graph as a hidden side
effect.

#### C. Graph population
Handled by:

- explicit bootstrap or refresh flow
- rebuild-oriented population from canonical relational state
- operationally visible setup logic

Ordinary retrieval code must not silently populate or repair graph contents.

#### D. Runtime usage
Handled by:

- capability checks
- graph-readiness checks
- repository/runtime decision points that choose graph-backed reads only when
  the graph is actually usable

Runtime code may decide whether to use the graph-backed path, but it must not
assume graph readiness merely because AGE is nominally enabled.

### Canonical bootstrap rule

Use this rule:

- setup creates capability
- bootstrap creates and populates graph contents
- runtime checks readiness
- reads degrade cleanly when readiness is not satisfied

This is the core bootstrap-first Phase A conclusion.

---

## 3. Optionality vs required deployment expectations

This area requires careful wording because two truths coexist in the current
repository state.

### Deployment reading

In the currently validated local default deployment story, AGE is enabled in the
default repository-owned stack.

That means AGE should not be described as merely an exotic or fringe local
overlay in current validated local usage.

### Behavioral-contract reading

At the same time, AGE is **not** the sole required correctness path for ordinary
memory behavior in the first slice.

That is because:

- relational storage remains canonical
- relational baseline behavior still exists
- graph-backed prototype paths must fall back when AGE is disabled, unavailable,
  unready, or graph-read execution fails

### Canonical optionality conclusion

The correct current reading is:

- **AGE may be deployment-default enabled**
- **but graph-backed behavior remains contractually non-authoritative**
- **and relational fallback remains part of the current correctness boundary**

So the first AGE-backed slice should not be described as either:

- “AGE optional everywhere and irrelevant to validated deployment”
- or
- “AGE required for all memory behavior and no fallback exists”

Instead, it should be described as:

- **enabled by default in current validated graph-capable local deployment**
- **but still behavior-preserving through relational fallback at the retrieval
  boundary**

This distinction matters and should remain explicit.

---

## 4. Failure and degradation behavior

Failure behavior is one of the most important Phase A decisions.

If any of the following are true:

- AGE is disabled
- AGE is unavailable
- AGE is not loadable
- the named graph does not exist
- graph bootstrap has not been performed
- graph readiness is not satisfied
- the graph-backed read fails for graph-specific reasons

then the system should:

- use the relational baseline path
- preserve current constrained retrieval behavior
- avoid widening or redefining visible retrieval semantics
- treat the graph path as unavailable
- avoid turning the ordinary memory request into a generic failure solely
  because graph support is absent or degraded

### What should continue when AGE is unavailable

If AGE is unavailable or graph readiness is not satisfied:

- canonical memory writes should continue against relational storage
- canonical memory reads should continue against relational storage
- constrained graph-backed enhancements should simply be ineligible to run
- the absence of graph support should be observable, but not silently converted
  into an unrelated memory-service correctness failure

### What should not happen

The first slice should **not**:

- fail ordinary startup purely because a later graph-backed read enhancement may
  be unavailable
- make ordinary `memory_get_context` correctness depend on graph readiness
- blur graph-unavailable conditions into generic retrieval-logic bugs
- force graph repair during ordinary read handling

### Canonical degradation rule

Use this rule:

- **graph problems degrade to relational behavior**
- **they do not redefine relational correctness as broken**

This is the core behavior-preserving Phase A conclusion.

---

## 5. Environment expectations

## Local development

Current local expectations should be read as:

- validated graph-capable local setups may have AGE enabled by default
- relational-first behavior must still remain understandable and recoverable
- developers should be able to reason explicitly about whether they are testing:
  - relational baseline behavior
  - graph capability/readiness
  - graph-backed constrained reads
  - fallback behavior

The important local rule is not “AGE must be absent” or “AGE must always
control behavior.”

The important local rule is:

- graph enablement and graph readiness must remain explicit
- fallback behavior must remain intact
- graph use must not be magical

## Shared development and CI-like environments

These environments should make graph expectations explicit.

Graph-oriented environments should:

- provision AGE intentionally
- ensure the named graph exists
- run explicit bootstrap/population when graph-backed tests depend on it

Non-graph-oriented environments should not accidentally depend on graph state.

## Production-like environments

For the current stage:

- operators should only treat graph-backed behavior as eligible when AGE and the
  prototype graph are intentionally provisioned
- relational fallback remains the safe correctness boundary
- graph capability should be documented as an explicit operational concern, not
  an invisible assumption

---

## 6. Minimum implementation boundary of the first slice

The first AGE-backed slice should remain narrow.

It may include:

- configuration and setup support for AGE enablement
- extension/setup validation
- graph-readiness checks
- explicit bootstrap/population flows
- repository/service insertion points that can later host constrained graph
  reads
- diagnostic and operational visibility around graph availability and readiness

It should **not yet** include broad retrieval redesign.

### Specifically out of scope for the first slice

The first slice should not include:

- visible redesign of `memory_get_context`
- broad relation expansion
- multi-hop traversal
- graph-first ranking semantics
- summary-layer graph semantics beyond the minimum boundary discussion
- grouped-response redesign
- graph-only correctness assumptions
- broad graph abstraction layers created before repeated proven need

This keeps the first slice operationally clear and testable.

---

## 7. Recommended first graph scope

Once the Phase A boundary is accepted, the narrow graph scope should remain
constrained.

The first graph-backed model should be limited to the smallest useful and
explainable shape.

### Current recommended graph scope

Mirror only the subset needed for the constrained prototype path:

- memory item nodes
- `supports` edges between memory items

Do **not** yet model all hierarchical concepts in the graph.

### Recommended graph identity model

Graph nodes and edges should remain traceable to canonical relational IDs.

At minimum:

- node identity should reference canonical `memory_id`
- edge identity should reference canonical `memory_relation_id`, or otherwise
  remain clearly traceable to canonical source/target relation identity

This preserves explainability and rebuildability.

---

## 8. Recommended population model

The current first-slice reading should remain:

- explicit
- rebuild-first
- relationally derived

That means bootstrap/population should be interpreted as:

1. ensure the graph capability exists
2. ensure the named graph exists
3. rebuild the constrained prototype contents from canonical relational state
4. verify the constrained graph shape is ready enough for the intended read path

The first slice should prefer rebuild clarity over early incremental-sync
complexity.

This is appropriate because:

- the graph state is derived
- the supported traversal shape is narrow
- operational clarity is more valuable than early graph lifecycle cleverness

---

## 9. Why the first slice should not begin with a retrieval behavior change

A tempting alternative is to start with a tiny graph-backed retrieval behavior,
such as a narrow one-hop `supports` read.

That can be a good **next** constrained experiment, but it is not the right
**first** decision boundary.

Starting there too early forces unresolved questions at the wrong time:

- is graph readiness required
- how should graph absence degrade
- is graph state canonical or derived
- where should bootstrap responsibility live
- how should tests separate graph semantics from baseline relational semantics

Those questions must be settled first.

That is why the correct first slice remains:

- boundary-first
- bootstrap-first
- behavior-preserving

---

## 10. Consequences for subsequent phases

Because this Phase A decision is now explicit, follow-on work should proceed in
this order:

1. keep this boundary stable
2. define the minimal hierarchy model
3. choose one small first hierarchical retrieval improvement
4. only expand graph-backed read behavior within the established degradation and
   ownership boundary

This should reduce drift in:

- repository interface expectations
- retrieval design assumptions
- test expectations
- docs and implementation alignment

---

## 11. Canonical working rules

Use these rules for all immediate follow-on work.

### Ownership rule
- relational state is canonical
- graph state is derived and rebuildable

### Bootstrap rule
- setup creates capability
- bootstrap creates and populates graph contents
- runtime checks readiness
- reads do not bootstrap graph state implicitly

### Optionality rule
- deployment may default to graph-capable configuration
- correctness must still preserve relational fallback in the first slice

### Degradation rule
- graph problems degrade to relational behavior
- they do not redefine ordinary memory retrieval as broken

### Scope rule
- do not broaden retrieval semantics merely because the graph layer now exists

---

## 12. Non-goals of this decision note

This note does **not**:

- fully define the later minimal hierarchy model
- decide all future summary-layer graph structures
- define long-term incremental graph synchronization
- justify graph-first retrieval semantics
- replace relational canonical persistence
- claim that all later AGE design questions are settled

It only fixes the canonical Phase A boundary for the first AGE-backed slice.

---

## 13. Decision summary

The canonical Phase A conclusion for `0.6.0` is:

- the first AGE-backed graph slice is **boundary-first**
- it is **bootstrap-first**
- it is **behavior-preserving**
- PostgreSQL relational state remains canonical
- AGE graph state is derived, supplementary, and rebuildable
- setup/bootstrap/readiness responsibilities must remain explicit
- graph-backed paths must degrade cleanly to the relational baseline
- ordinary memory behavior must not be redefined as graph-required in this first
  slice

This note should be treated as the canonical decision record for Plan `17.3`
until a later phase intentionally and explicitly broadens graph-backed retrieval
behavior.