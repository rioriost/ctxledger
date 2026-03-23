# AGE Prototype Validation Observation

## Purpose

This note records one real validation pass for the constrained Apache AGE
prototype.

It is intended to capture what environment was used, what commands were run,
what was observed, and whether the current constrained prototype behaved as
expected.

---

## Environment

- environment name:
- validation date:
- execution context:
  - host shell / Docker host / `ctxledger` container / other
- PostgreSQL target:
- AGE expected:
  - yes / no
- graph name:
- prototype enabled:
  - true / false

---

## Preconditions

- canonical schema applied:
  - yes / no
- canonical memory data present:
  - yes / no / unknown
- canonical `supports` relations present:
  - yes / no / unknown

---

## Commands Run

### 1. Readiness before bootstrap

```/dev/null/sh#L1-1
ctxledger age-graph-readiness ...
```

Observed output:

```/dev/null/json#L1-6
{
  "age_enabled": ,
  "age_graph_name": "",
  "age_available": ,
  "age_graph_status": ""
}
```

### 2. Bootstrap

```/dev/null/sh#L1-1
ctxledger bootstrap-age-graph ...
```

Observed output:

```/dev/null/txt#L1-1
AGE graph bootstrap completed for '...' (memory_item nodes repopulated=..., supports edges repopulated=...).
```

### 3. Readiness after bootstrap

```/dev/null/sh#L1-1
ctxledger age-graph-readiness ...
```

Observed output:

```/dev/null/json#L1-6
{
  "age_enabled": ,
  "age_graph_name": "",
  "age_available": ,
  "age_graph_status": ""
}
```

### 4. Runtime introspection

```/dev/null/txt#L1-1
/debug/runtime
```

Observed `age_prototype` payload:

```/dev/null/json#L1-9
{
  "age_enabled": ,
  "age_graph_name": "",
  "observability_routes": [
    "/debug/runtime",
    "/debug/routes",
    "/debug/tools"
  ],
  "age_available": ,
  "age_graph_status": ""
}
```

---

## Interpretation

- readiness before bootstrap:
- bootstrap counts interpretation:
- readiness after bootstrap:
- runtime introspection matches CLI readiness:
  - yes / no
- fallback still expected anywhere:
  - yes / no
- mismatches observed:
- likely cause classification:
  - config / provisioning / bootstrap / runtime / unknown

---

## Conclusion

- validation result:
  - passed / partially passed / failed
- current prototype reading after this validation:
- next recommended action: