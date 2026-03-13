# HTTP FastAPI Cleanup Plan

## 1. Purpose

This document defines the cleanup plan for the current HTTP-only `ctxledger` server implementation after the transition from stdio MCP to HTTP MCP and the later introduction of FastAPI.

The current codebase is operational, but it still contains layering and routing patterns that appear to be transitional artifacts from earlier transport refactors. The goal of this plan is to reduce unnecessary indirection, clarify ownership of responsibilities, and make the FastAPI-based implementation easier to reason about and maintain.

This plan is intentionally focused on cleanup and simplification. It does not propose a protocol rewrite or a feature expansion.

---

## 2. Current Situation

At a high level, the current implementation has these relevant parts:

- `src/ctxledger/http_app.py`
- `src/ctxledger/server.py`
- `src/ctxledger/runtime/http_runtime.py`
- `src/ctxledger/runtime/http_handlers.py`
- `src/ctxledger/runtime/server_responses.py`
- `src/ctxledger/runtime/server_factory.py`
- `src/ctxledger/runtime/orchestration.py`

The rough structure is workable, but the HTTP request path currently includes avoidable indirection:

1. FastAPI receives the request
2. FastAPI route wrappers convert the request into string-based path/body inputs
3. the runtime receives a synthetic `route_name`
4. the runtime dispatches into a handler table
5. the handler builds a response object
6. FastAPI converts that response object back into an HTTP response

This layering is survivable, but it is no longer obviously justified now that FastAPI is the concrete HTTP framework in use.

There also appears to be leftover API surface in `server.py` that mainly exists to preserve compatibility during the MCP module extraction.

---

## 3. Cleanup Goal

The cleanup goal is to make the HTTP server architecture follow one clear rule:

> FastAPI should own HTTP routing, while runtime and server layers should own application behavior.

More concretely, the target state is:

- FastAPI defines and owns actual HTTP routes
- route handlers call concrete HTTP/MCP handler functions directly
- `server.py` focuses on bootstrap and lifecycle instead of acting as a compatibility barrel
- runtime abstractions keep only the behavior that still provides real value
- settings reflect the fact that the application is now HTTP-only

---

## 4. Non-Goals

This cleanup plan does not aim to:

- change business behavior of workflow operations
- change persistence design
- redesign MCP tool or resource semantics
- remove FastAPI
- replace the current MCP behavior with a new protocol implementation
- rewrite all tests from scratch

If protocol compliance work is needed later, that should be tracked separately.

---

## 5. Problems To Address

## 5.1 FastAPI is wrapped by a second routing layer

The current FastAPI app delegates to a runtime dispatch mechanism keyed by route names such as:

- `mcp_rpc`
- `workflow_resume`
- `runtime_introspection`

This means the code uses both:

- FastAPI route registration
- an internal route registry on the runtime adapter

That is likely unnecessary now.

### Why this is a problem

- adds cognitive overhead
- makes HTTP flow harder to trace
- creates more places where routes must stay in sync
- weakens the benefit of using FastAPI directly

### Cleanup direction

Move route ownership to FastAPI and call concrete handler functions directly from the app layer.

---

## 5.2 `server.py` has become a compatibility-heavy surface

`src/ctxledger/server.py` currently appears to contain:

- core server lifecycle
- runtime adapter implementation
- wrapper functions delegating to `runtime.http_handlers`
- wrapper functions delegating to `runtime.server_responses`
- helper re-exports
- orchestration passthrough functions

This makes the file larger and more ambiguous than it needs to be.

### Why this is a problem

- obscures where actual behavior lives
- increases import indirection
- makes future cleanup harder
- encourages tests and callers to depend on transitional wrappers

### Cleanup direction

Reduce `server.py` to the true application surface:

- `CtxLedgerServer`
- runtime construction that still has real value
- server creation
- startup and shutdown concerns

Move callers to import handler/response helpers from their real modules.

---

## 5.3 Runtime adapter responsibilities are mixed

The current `HttpRuntimeAdapter` appears to serve several roles:

- HTTP route registry
- MCP tool registry
- MCP resource dispatcher
- runtime introspection source
- lifecycle object with `start()` and `stop()`

Some of these are still reasonable. Some are artifacts of an older transport abstraction.

### Why this is a problem

The name and placement suggest an HTTP transport boundary, but the object also carries MCP feature dispatch concerns. That makes the boundary harder to understand.

### Cleanup direction

Retain only the responsibilities that are still useful after FastAPI directly owns HTTP routes:

- tool registration/schema surface
- tool dispatch
- resource dispatch
- introspection
- runtime lifecycle if still needed for logging and startup state

Remove internal HTTP route-table dispatch if no longer needed.

---

## 5.4 Server binding is performed through private attribute mutation

There is currently logic that assigns a server object to the runtime through a private field after creation.

### Why this is a problem

- private attribute mutation is a design smell
- it suggests the dependency graph is not expressed cleanly
- it makes initialization flow less obvious

### Cleanup direction

Construct the runtime with the dependencies it actually needs instead of patching them in afterward.

---

## 5.5 HTTP-only configuration still carries redundant transport shape

The application is now intentionally HTTP-only, but the settings still appear to preserve multiple overlapping concepts such as:

- transport mode
- HTTP enablement

When only one transport is supported, carrying both concepts is likely unnecessary.

### Why this is a problem

- creates redundant validation paths
- suggests unsupported modes still matter
- increases configuration complexity for no real gain

### Cleanup direction

Simplify configuration toward a single HTTP-only shape.

---

## 5.6 Import-time application startup should be reviewed

The current FastAPI app construction path should be reviewed for whether server startup happens at import time instead of FastAPI lifespan time.

### Why this is a problem

If startup work such as logging setup, database ping, or schema validation happens too early, this can:

- complicate testing
- create import side effects
- make application lifecycle less idiomatic for ASGI/FastAPI

### Cleanup direction

Prefer an explicit FastAPI lifespan-managed startup/shutdown flow if practical.

---

## 6. Target Architecture

The preferred target architecture after cleanup is:

### `src/ctxledger/http_app.py`
Owns:

- FastAPI app creation
- FastAPI route declarations
- request-to-handler bridging
- lifespan wiring

### `src/ctxledger/server.py`
Owns:

- `CtxLedgerServer`
- startup and shutdown
- health and readiness
- workflow service access
- server creation entrypoint if it remains the canonical bootstrap API

### `src/ctxledger/runtime/http_handlers.py`
Owns:

- HTTP-specific parsing
- auth extraction and enforcement
- request validation for HTTP entrypoints
- MCP HTTP request handling helper binding

### `src/ctxledger/runtime/server_responses.py`
Owns:

- application-level response building
- workflow response DTO assembly
- debug response DTO assembly
- projection failure action response DTO assembly

### runtime adapter
Owns only what is still genuinely runtime behavior:

- tool dispatch
- resource dispatch
- tool schema surface
- introspection support
- runtime lifecycle hooks if needed

---

## 7. Workstreams

## Workstream 1 — Add plan and freeze cleanup direction

### Goal

Document the intended cleanup so further changes move toward simplification rather than deepening transitional patterns.

### Tasks

- add this cleanup plan document
- align implementation changes with the target architecture in this plan
- avoid adding new wrappers or new route-name dispatch entries unless strictly required

### Exit Criteria

- cleanup direction is documented
- implementation work can proceed in small PR-sized steps

---

## Workstream 2 — Remove duplicate HTTP route dispatch

### Goal

Make FastAPI the direct owner of HTTP route resolution.

### Tasks

- change FastAPI route handlers to call concrete HTTP handler functions directly
- stop routing through a runtime `dispatch(route_name, path, body)` layer for ordinary HTTP requests
- remove route-name lookup as the primary execution path for FastAPI requests
- preserve existing payload and auth behavior

### Deliverable

An app layer where FastAPI routes directly invoke MCP and workflow HTTP handlers.

### Exit Criteria

- HTTP requests no longer require a second route table
- route behavior remains equivalent from the client point of view

---

## Workstream 3 — Shrink `server.py`

### Goal

Make `server.py` a true server/bootstrap module instead of a compatibility façade.

### Tasks

- identify wrapper functions in `server.py` that simply delegate to `runtime.http_handlers`
- identify wrapper functions in `server.py` that simply delegate to `runtime.server_responses`
- migrate tests and internal imports to the canonical modules
- remove wrappers that no longer provide meaningful API value

### Deliverable

A smaller `server.py` with clearer ownership boundaries.

### Exit Criteria

- most HTTP helper imports no longer come from `ctxledger.server`
- `server.py` mainly contains server lifecycle and assembly code

---

## Workstream 4 — Re-scope the runtime adapter

### Goal

Keep the runtime adapter only where it still adds architectural value.

### Tasks

- remove HTTP route registry duties if FastAPI routes are now direct
- preserve tool and resource dispatch surfaces if still useful
- preserve runtime introspection if still needed
- review whether `registered_routes()` remains useful or should be replaced by a more direct introspection model
- rename or document the runtime adapter more clearly if its role is MCP-centric rather than generic HTTP routing

### Deliverable

A runtime adapter whose responsibilities match its actual purpose.

### Exit Criteria

- the adapter is no longer a second HTTP router
- remaining methods represent real runtime behavior, not compatibility scaffolding

---

## Workstream 5 — Remove private runtime patching

### Goal

Make dependency wiring explicit.

### Tasks

- change runtime construction so the runtime receives the server dependency directly
- remove post-construction mutation of private fields used for runtime-server linkage
- ensure server factory code creates the runtime in a single coherent path

### Deliverable

A runtime/server relationship that is explicit during construction.

### Exit Criteria

- no private field patching is needed to finish server wiring
- initialization order is easy to follow

---

## Workstream 6 — Simplify HTTP-only settings

### Goal

Bring configuration into line with the current HTTP-only reality.

### Tasks

- review whether `TransportMode` still has real value
- review whether `HttpSettings.enabled` still has real value
- remove one of the overlapping concepts if it is redundant
- update validation and tests accordingly
- preserve operator ergonomics for expected environment variables

### Deliverable

A cleaner HTTP-only settings model.

### Exit Criteria

- configuration does not express unsupported transport complexity
- validation logic is simpler and clearer

---

## Workstream 7 — Align startup with FastAPI lifecycle

### Goal

Reduce import-time side effects and make startup/shutdown behavior more idiomatic.

### Tasks

- review current app creation flow for import-time startup behavior
- adopt FastAPI lifespan hooks if practical
- move server startup and shutdown into explicit lifecycle management
- ensure tests can still instantiate application state predictably

### Deliverable

A FastAPI app whose operational lifecycle is explicit and framework-aligned.

### Exit Criteria

- startup is not hidden in module import side effects unless intentionally preserved
- shutdown is also handled explicitly

---

## 8. Suggested Implementation Sequence

The cleanup should be implemented in this order:

1. add this plan
2. simplify FastAPI route execution path
3. update tests to import canonical modules directly
4. remove `server.py` wrappers that become unused
5. make runtime/server wiring explicit
6. simplify runtime adapter responsibilities
7. simplify HTTP-only configuration
8. adopt lifespan-managed startup/shutdown if this can be done safely in the same cleanup stream

This order minimizes risk because it removes indirection before removing compatibility surface.

---

## 9. Validation Strategy

The cleanup should be considered successful only if all of the following remain true:

- existing HTTP MCP behavior still works
- workflow HTTP routes still work
- debug routes still work when enabled
- auth behavior remains unchanged
- startup validation behavior remains correct
- tool and resource surfaces remain discoverable through the runtime where expected
- tests reflect the simplified architecture rather than preserving old indirection

Recommended validation areas:

- unit tests around HTTP handlers
- unit tests around server responses
- server bootstrap tests
- FastAPI application tests for route behavior
- auth-enabled route behavior tests
- MCP initialize/list/call smoke coverage

---

## 10. Risks and Mitigations

## Risk 1 — Test breakage due to import-path cleanup

Many tests may currently import compatibility wrappers from `ctxledger.server`.

### Mitigation

Update tests first-class to canonical module locations before removing wrappers.

---

## Risk 2 — Cleanup changes behavior unintentionally

Because the current architecture uses several layers, removing one may alter status codes, headers, or response payload shapes.

### Mitigation

Preserve response DTO generation in `runtime.server_responses` and compare behavior before/after through focused tests.

---

## Risk 3 — Lifecycle cleanup interacts with startup expectations

Moving startup into FastAPI lifespan can affect current test setup and import assumptions.

### Mitigation

Treat lifespan cleanup as a distinct step and land it only once route execution cleanup is stable.

---

## Risk 4 — Runtime introspection may rely on route registry internals

If route introspection currently depends on the runtime’s internal route table, removing that table may affect debug output.

### Mitigation

Decide whether route introspection should come from:
- a static route registry in the app layer
- explicit route metadata
- or a smaller retained registration structure only for introspection

Do not remove the route table until introspection behavior is accounted for.

---

## 11. Expected End State

After this cleanup, the codebase should have these properties:

- FastAPI routes are straightforward to trace
- `server.py` is materially smaller
- runtime responsibilities are clearly MCP/runtime-oriented rather than duplicate-routing-oriented
- startup wiring is explicit
- configuration better matches the HTTP-only product direction
- the codebase is easier to extend without reviving transitional transport abstractions

---

## 12. Immediate Next Actions

1. add this plan document
2. refactor `http_app.py` so FastAPI routes call concrete HTTP handler functions directly
3. update tests away from `ctxledger.server` compatibility wrappers where practical
4. remove the first batch of dead or thin delegating functions from `server.py`
5. run the focused server and HTTP test suites
6. iterate on runtime simplification once direct route execution is stable