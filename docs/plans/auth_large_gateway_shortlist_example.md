# Large-Pattern Auth Gateway Shortlist Example for `ctxledger`

## 1. Purpose

This document provides a **worked example shortlist scorecard** for the future large-pattern authentication gateway of `ctxledger`.

It is intentionally:

- illustrative
- provisional
- non-binding
- not a final decision record

Its purpose is to show how the evaluation criteria in:

- `docs/plans/auth_large_gateway_evaluation_memo.md`

can be applied in a more concrete way before the project reaches an actual gateway selection decision.

The final decision, when the roadmap gate is reached, should still be recorded separately using:

- `docs/plans/auth_large_gateway_decision_record_template.md`

---

## 2. Important Status Note

This document is an **example**.

It does **not** mean:

- the large pattern is being implemented now
- a final gateway has been chosen
- `ctxledger` has already committed to a multi-user identity architecture
- app-layer authorization requirements have already been settled

The current repository posture remains:

- small pattern is implemented
- proxy-only auth is the current documented deployment model
- large pattern is deferred
- roadmap `0.4` or later remains the earliest intended point for active large-pattern implementation work

---

## 3. Example Evaluation Context

This example assumes a future scenario where:

- `ctxledger` is being considered for shared internal organizational use
- multiple engineers may connect through MCP-capable IDE clients
- shared static tokens are no longer considered acceptable
- the team wants to preserve the current proxy-first architecture
- the project still prefers to avoid reintroducing end-user auth logic into `ctxledger`

This example also assumes that the real client set has not yet been fully validated, so all scores should be treated as **provisional**.

---

## 4. Candidate Shortlist Used in This Example

This example narrows the earlier broad candidate set to four practical shortlist categories:

1. `Pomerium`
2. `oauth2-proxy`
3. another OIDC-aware gateway
4. organization-standard identity gateway

These are the same categories already discussed in the evaluation memo.

---

## 5. Scoring Method Used

### 5.1 Scale

This example uses the same 1-5 scale described in the evaluation memo:

- `1` = poor fit
- `2` = weak fit
- `3` = acceptable fit
- `4` = strong fit
- `5` = excellent fit

### 5.2 Weights

This example uses the same default weights:

| Category | Weight |
| --- | --- |
| MCP IDE compatibility | `5` |
| Identity quality | `4` |
| Operational fit | `4` |
| Identity propagation readiness | `3` |
| Authorization extensibility | `3` |
| Architecture alignment | `4` |
| Organization-standard alignment | `2` |

### 5.3 Formula

```/dev/null/txt#L1-1
weighted_score = sum(category_score * category_weight) / sum(category_weight)
```

Total weight in this example:

```/dev/null/txt#L1-1
5 + 4 + 4 + 3 + 3 + 4 + 2 = 25
```

---

## 6. Example Shortlist Scorecard

## 6.1 Numeric Worksheet

| Candidate | MCP IDE compatibility (x5) | Identity quality (x4) | Operational fit (x4) | Identity propagation (x3) | Authorization extensibility (x3) | Architecture alignment (x4) | Org-standard alignment (x2) | Weighted score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Pomerium` | `4` | `5` | `3` | `4` | `5` | `5` | `2` | `4.12` |
| `oauth2-proxy` | `2` | `4` | `4` | `3` | `3` | `4` | `4` | `3.20` |
| Other OIDC-aware gateway | `3` | `3` | `3` | `3` | `3` | `4` | `2` | `3.08` |
| Organization-standard gateway | `3` | `4` | `4` | `4` | `4` | `4` | `5` | `3.88` |

---

## 6.2 Worked Calculation Example

Example calculation for `Pomerium`:

```/dev/null/txt#L1-1
(4*5 + 5*4 + 3*4 + 4*3 + 5*3 + 5*4 + 2*2) / 25 = 103 / 25 = 4.12
```

Example calculation for `oauth2-proxy`:

```/dev/null/txt#L1-1
(2*5 + 4*4 + 4*4 + 3*3 + 3*3 + 4*4 + 4*2) / 25 = 80 / 25 = 3.20
```

---

## 7. Example Candidate Notes

## 7.1 `Pomerium`

### Example scores
- MCP IDE compatibility: `4`
- Identity quality: `5`
- Operational fit: `3`
- Identity propagation readiness: `4`
- Authorization extensibility: `5`
- Architecture alignment: `5`
- Organization-standard alignment: `2`

### Why this example scores it well
`Pomerium` scores strongly in this example because it appears to fit the long-term shape the project may want:

- strong identity-aware proxy posture
- good fit for internal engineering tools
- strong policy story
- clean alignment with keeping auth outside `ctxledger`
- good future headroom if downstream identity propagation or authorization needs emerge later

### Why this example does not score it even higher
It does not receive a perfect operational score because:

- it is still heavier than the current small pattern
- it may introduce more operator burden than some standardized or already-adopted internal gateway
- actual MCP client compatibility would still need explicit validation

### Example interpretation
In this example, `Pomerium` looks like the **strongest strategic candidate**, but not yet an automatically chosen one.

---

## 7.2 `oauth2-proxy`

### Example scores
- MCP IDE compatibility: `2`
- Identity quality: `4`
- Operational fit: `4`
- Identity propagation readiness: `3`
- Authorization extensibility: `3`
- Architecture alignment: `4`
- Organization-standard alignment: `4`

### Why this example scores it lower on compatibility
The main drag on `oauth2-proxy` in this example is IDE compatibility risk:

- it is often most natural in redirect-heavy browser flows
- remote MCP clients may not fit that interaction model cleanly
- the burden of proving a good non-browser UX may be higher than for a more explicitly identity-gateway-oriented option

### Why this example still keeps it viable
It still scores reasonably because:

- it is mature
- many teams already know how to operate it
- it can fit well where organization familiarity is already high
- it may still become the best answer if real client validation turns out better than expected

### Example interpretation
In this example, `oauth2-proxy` remains a **serious candidate**, but one that needs real client validation before it could plausibly lead the shortlist.

---

## 7.3 Other OIDC-aware gateway

### Example scores
- MCP IDE compatibility: `3`
- Identity quality: `3`
- Operational fit: `3`
- Identity propagation readiness: `3`
- Authorization extensibility: `3`
- Architecture alignment: `4`
- Organization-standard alignment: `2`

### Why this example keeps scores neutral
This category is intentionally scored conservatively because it is broad and under-specified.

Without a concrete product in hand, it is hard to justify high scores. A neutral score here means:

- plausible
- worth leaving open
- not yet persuasive enough to beat named candidates

### Example interpretation
This category remains useful as a placeholder for future discovery, but in this example it is **not yet shortlist-leading**.

---

## 7.4 Organization-standard gateway

### Example scores
- MCP IDE compatibility: `3`
- Identity quality: `4`
- Operational fit: `4`
- Identity propagation readiness: `4`
- Authorization extensibility: `4`
- Architecture alignment: `4`
- Organization-standard alignment: `5`

### Why this example scores it strongly
This category performs well in-context because:

- existing standards can reduce operational friction
- supportability and ownership may already exist
- identity integrations may already be approved and maintained
- rollout can be simpler than adopting a totally new gateway stack

### Why this example does not rank it first automatically
It does not lead by default because:

- “organization-standard” does not guarantee MCP client compatibility
- browser assumptions may still be a hidden problem
- an established platform pattern can still be the wrong fit for remote MCP traffic

### Example interpretation
In this example, the organization-standard path looks like a **very plausible finalist**, especially if it passes client validation.

---

## 8. Example Ranking

Using the provisional weighted scores above, the example ranking is:

1. `Pomerium` — `4.12`
2. Organization-standard gateway — `3.88`
3. `oauth2-proxy` — `3.20`
4. Other OIDC-aware gateway — `3.08`

This should be read carefully.

It means only:

- `Pomerium` looks strategically strongest in this hypothetical comparison
- the organization-standard gateway could become highly competitive if client validation is good
- `oauth2-proxy` remains viable but is more exposed to IDE compatibility concerns
- the broader OIDC-aware category remains open but unspecific

It does **not** mean the project has chosen `Pomerium`.

---

## 9. Example Shortlist Outcome

If this example were used to narrow the field for a future real evaluation, the practical shortlist would likely become:

### Example shortlist
- `Pomerium`
- organization-standard gateway
- `oauth2-proxy` as a retained alternate if client validation is favorable

### Example deprioritized category
- other generic OIDC-aware gateway, unless a concrete offering appears that clearly improves MCP compatibility or operational fit

---

## 10. Example Hard-Blocker Notes

Even with weighted scores, some findings should override simple ranking.

### Example blocker 1 — MCP IDE incompatibility
If a candidate requires a browser-only flow that MCP clients cannot realistically support, it should be treated as blocked regardless of otherwise strong scores.

### Example blocker 2 — unacceptable operator burden
If the team cannot realistically operate the gateway or obtain ownership for it, a high conceptual score should not be treated as sufficient.

### Example blocker 3 — mismatch with actual product needs
If future work clearly requires app-layer authorization, ownership semantics, or tenant isolation in the same phase, gateway selection alone is not the whole architectural answer.

---

## 11. What This Example Still Does Not Decide

This example still does **not** decide:

- the final large-pattern gateway
- whether app-layer authorization will be required in the same phase
- whether workflows need explicit ownership semantics
- whether tenant isolation is needed
- whether identity propagation is immediate or deferred
- which MCP clients must be supported as a hard requirement
- whether browser-assisted login is actually acceptable in practice

Those remain real decision inputs for the future decision record.

---

## 12. Recommended Next Step When the Phase Gate Is Reached

When the project actually reaches the large-pattern implementation phase, the next practical step should be:

1. replace provisional example scoring with evidence-backed candidate scoring
2. validate real MCP client behavior against the finalist candidates
3. confirm whether downstream identity propagation is required
4. confirm whether app-layer authorization remains deferred or must be introduced
5. record the result in:
   - `docs/plans/auth_large_gateway_decision_record_template.md`

---

## 13. Current Example Conclusion

This worked example suggests the following provisional interpretation:

- `Pomerium` is the most strategically attractive future large-pattern candidate
- an organization-standard identity gateway may still become the best real-world answer
- `oauth2-proxy` remains viable but is more exposed to MCP IDE compatibility risk
- large-pattern work should still remain deferred until the roadmap and readiness gates are truly satisfied

In short:

> this example is useful for narrowing future attention, but not for making the actual gateway decision yet