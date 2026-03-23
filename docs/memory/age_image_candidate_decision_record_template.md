# AGE-Capable Image Candidate Decision Record

## Purpose

This template records the evaluation of one candidate image or image strategy for
the optional AGE-capable Docker / development path used by the current
constrained `supports` prototype.

Use one copy of this template per serious candidate.

This template is intentionally narrow.

It is not a production deployment approval form.

It is not a broad graph platform decision record.

It is only for deciding whether a candidate fits the current constrained local /
dev validation path.

---

## Candidate Summary

- candidate name:
- source:
- image or build reference:
- intended usage:
  - prebuilt image / repository-owned build / other
- evaluation date:
- evaluator:

---

## Candidate Type

- category:
  - prebuilt image / repository-owned Docker build / manual install flow / other
- intended integration shape:
  - Compose overlay / local-only build path / other
- default stack impact:
  - none / partial / high
- optional-by-default preserved:
  - yes / no / uncertain

---

## Evaluation Against Required Capabilities

### 1. Apache AGE availability

- expected support for `LOAD 'age'`:
  - yes / no / unknown
- confidence:
  - high / medium / low
- notes:

### 2. PostgreSQL compatibility

- expected compatibility with current repository assumptions:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 3. pgvector compatibility

- expected compatibility with current pgvector expectations:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 4. Overlay friendliness

- suitable for explicit optional Compose overlay:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 5. Reproducibility

- likely reproducible for another engineer:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 6. Limited blast radius

- likely to preserve unchanged default stack:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

---

## Operator / Repository Fit

### 1. Explicit bootstrap compatibility

- compatible with current explicit bootstrap command:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 2. Explicit readiness-check compatibility

- compatible with current readiness-check flow:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 3. Runtime introspection compatibility

- compatible with current runtime observability expectations:
  - yes / no / partial / unknown
- confidence:
  - high / medium / low
- notes:

### 4. Documentation burden

- expected documentation complexity:
  - low / medium / high
- notes:

### 5. Ongoing maintenance burden

- expected maintenance burden:
  - low / medium / high
- notes:

---

## Expected Validation Path

### Before bootstrap target

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable"
}
```

### After bootstrap target

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

### Bootstrap success target

```/dev/null/txt#L1-1
AGE graph bootstrap completed for 'ctxledger_memory' (memory_item nodes repopulated=..., supports edges repopulated=...).
```

### Runtime introspection target

```/dev/null/json#L1-9
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "observability_routes": [
    "/debug/runtime",
    "/debug/routes",
    "/debug/tools"
  ],
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

### Confidence this candidate can satisfy the target

- high / medium / low
- notes:

---

## Risks

### Main risk 1
- description:
- severity:
  - low / medium / high
- mitigation:

### Main risk 2
- description:
- severity:
  - low / medium / high
- mitigation:

### Main risk 3
- description:
- severity:
  - low / medium / high
- mitigation:

---

## Unknowns / Open Questions

- open question 1:
- open question 2:
- open question 3:

---

## Comparison Notes

### Advantages of this candidate

- advantage 1:
- advantage 2:
- advantage 3:

### Disadvantages of this candidate

- disadvantage 1:
- disadvantage 2:
- disadvantage 3:

### Relative ranking against other candidates

- better than:
- worse than:
- roughly equivalent to:
- notes:

---

## Recommendation

- adopt / reject / keep as fallback / needs investigation

### Rationale

- 

### Conditions for adoption

- condition 1:
- condition 2:
- condition 3:

### Next action

- 

---

## Final Short Summary

- final read:
- suitable for the constrained prototype:
  - yes / no / maybe
- recommended next step: