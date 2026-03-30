# Azure Large Deployment Operator Runbook

## 1. Purpose

This runbook describes the intended operator workflow for the **Azure large deployment pattern** for `ctxledger`.

The large pattern is the cloud-hosted deployment shape intended for:

- larger runtime capacity than the local `small` pattern
- multiple concurrent users
- Azure-managed compute, registry, database, and AI services
- Azure Container Registry remote build for the large-pattern container image path
- a clearer production-like boundary between ingress, application runtime, and canonical data storage
- a self-contained one-command deployment experience through `azd up`, where the ideal first-run input is limited to:
  - Azure subscription selection
  - Azure location selection
- standard `azd` remote-build behavior for the application image rather than a custom local-Docker build path
- after successful deployment, the remaining user to-do is ideally only MCP client configuration

This document is a **runbook scaffold** for the `1.0.0` large deployment direction.

It should be read as:

- operator guidance for the planned Azure topology
- a checklist-oriented deployment and validation reference
- a bounded operational baseline
- guidance for the final user handoff after deployment, including MCP client configuration

It should **not** be read as a claim that every Azure design decision has already been finalized.

However, several requirements are now explicit for the large pattern:

- the deployment should converge toward a one-command `azd up` experience
- on first run, the ideal interactive choices should be limited to:
  - Azure subscription selection
  - Azure location selection
- infrastructure provisioning, application deployment, PostgreSQL `azure_ai` bootstrap, and schema bootstrap should all be part of that flow
- PostgreSQL extension allowlisting must be configured during infrastructure deployment
- after deployment, automation must wait until PostgreSQL accepts connections
- once PostgreSQL is reachable, automation must execute the bootstrap queries needed to:
  - enable and configure `azure_ai`
  - apply the bundled `ctxledger` schema
  - verify representative schema objects
- the bootstrap execution path itself should be self-contained within the Azure deployment flow rather than depending on pre-created helper resources or manual script distribution
- naming, passwords, and other deployment internals should be generated or derived automatically in the normal happy path wherever practical
- large-pattern auth guidance must distinguish clearly between:
  - PostgreSQL-side `azure_ai` authentication to Azure OpenAI
  - client-facing MCP authentication or gateway enforcement
- `azure_ai` authentication for PostgreSQL must support both:
  - Azure OpenAI subscription-key authentication
  - Azure OpenAI managed-identity / Entra ID authentication
- the large pattern should also support an `auto` Azure OpenAI auth mode for PostgreSQL bootstrap:
  - prefer `managed_identity` when the environment is aligned to Entra ID / RBAC management
  - fall back to `subscription_key` only when that path is explicitly configured and acceptable for the environment
- the ideal remaining user task after successful deployment is only configuring the AI agent / MCP client against the deployed MCP endpoint

In particular, operators should treat the following as explicit design variables until closed by implementation and release acceptance:

- the final ingress/gateway choice
- the final authentication boundary implementation
- the final Azure observability baseline
- the final Apache AGE support posture on the selected Azure PostgreSQL configuration
- final Azure OpenAI deployment shape and model/deployment naming convention
- the final `azure_ai` extension bootstrap query set and secure setting procedure inside PostgreSQL
- the final split of responsibilities between:
  - application-side Azure OpenAI usage
  - PostgreSQL-side Azure OpenAI usage through `azure_ai`

---

## 2. Target Topology Summary

The large deployment pattern is intended to use:

- Azure Container Registry (`ACR`)
- Azure Container Apps (`ACA`)
- Azure Database for PostgreSQL Flexible Server

Logical request path:

```/dev/null/txt#L1-8
MCP client
  -> ingress / auth gateway boundary
  -> Azure Container Apps
  -> private ctxledger container
  -> Azure Database for PostgreSQL Flexible Server

Supporting services:
  -> Azure Container Registry
  -> secret / monitoring services
```

Operationally, that means:

- `ctxledger` remains the backend application
- the public HTTPS boundary lives outside the application process
- `/mcp` remains the MCP endpoint
- PostgreSQL remains the canonical source of truth
- `pgvector` remains required
- Azure OpenAI is the intended embedding provider for the large Azure pattern
- the PostgreSQL `azure_ai` extension should be used wherever practical so PostgreSQL can invoke Azure OpenAI directly for embedding generation
- Apache AGE remains a bounded, non-canonical support layer if enabled and validated

---

## 3. Architecture and Boundary Rules

Operators should preserve the repository’s current architecture principles during Azure deployment.

### 3.1 Canonical data rule

Treat PostgreSQL as canonical for:

- workflow state
- workflow checkpoints
- workflow completion state
- memory state
- embeddings
- summary persistence
- other durable relational state

Do not treat derived or graph-shaped structures as a competing source of truth.

### 3.2 Public boundary rule

Treat ingress, TLS termination, and authentication as external deployment concerns.

The Azure large pattern should continue to follow this rule:

- `ctxledger` should not become the identity provider
- `ctxledger` should not own end-user login flows
- `ctxledger` should remain deployable behind a replaceable ingress/auth boundary

### 3.3 Traefik caution

The local `small` pattern uses Traefik because it fits Docker Compose and local TLS ergonomics well.

The Azure large pattern should **not** automatically assume the same exact Traefik shape carries forward unchanged.

For Azure operation, evaluate the actual cloud ingress choice deliberately and keep the app contract stable:

- HTTP application runtime
- `/mcp`
- private backend posture
- gateway-managed public exposure

This distinction also matters for auth guidance:

- PostgreSQL-side `azure_ai` authentication to Azure OpenAI is a database integration concern
- MCP client authentication is a gateway or ingress concern
- operators should not conflate those two boundaries when validating or troubleshooting the large pattern

Operationally, this should support a deployment experience where users do not need local TLS tooling, local reverse-proxy setup, or other preflight steps similar to the `small` pattern.
The target user experience is:

- run `azd up`
- wait for Azure provisioning, deployment, and automated PostgreSQL bootstrap to finish
- avoid any separate prerequisite setup for deployment helper infrastructure
- configure the AI agent / MCP client with the reported MCP endpoint

---

## 4. Service Responsibilities

## 4.1 Azure Container Registry

Use ACR for:

- storing versioned application images
- release image provenance
- CI/CD or operator-driven image promotion
- providing the runtime image source for ACA

Environment profile note:

- `dev` can tolerate more cost-sensitive image promotion and validation posture
- `staging` should use release-candidate or staging-tagged images
- `production-like` should use explicit release-backed image tags with rollback-ready provenance

Operator expectations:

- image tags should be explicit and traceable
- image sources used in deployment should be documented
- anonymous or ad hoc image sourcing should be avoided

## 4.2 Azure Container Apps

Use ACA for:

- running the `ctxledger` application container
- managing revisions
- injecting runtime configuration and secrets
- providing cloud-hosted runtime scale beyond the local pattern
- integrating with ingress and monitoring posture

Operator expectations:

- confirm the app port matches the ACA target port
- confirm revision settings and rollout expectations
- confirm runtime configuration is sourced from approved deployment config
- confirm logs and health status are observable after rollout

## 4.3 Azure Database for PostgreSQL Flexible Server

Use Flexible Server for:

- canonical relational persistence
- `pgvector`
- PostgreSQL-side Azure AI integration through the `azure_ai` extension
- bounded Apache AGE-backed capabilities if validated

Operator expectations:

- confirm the chosen PostgreSQL version explicitly
- validate required extensions before accepting the deployment as healthy
- treat schema migration as an explicit operational task
- treat `azure_ai` bootstrap as an automated deployment task rather than a manual operator-only task
- confirm backup and restore posture for the environment
- confirm the `azure_ai` extension is enabled and configured when Azure OpenAI-backed embeddings are in scope
- confirm the Azure OpenAI endpoint, deployment name, and credential posture used by PostgreSQL are the intended ones
- confirm which PostgreSQL-side Azure OpenAI auth mode is intended for the environment:
  - `auto`
  - `subscription_key`
  - `managed_identity`
- if `auto` is used, confirm the expected resolution order is understood:
  - prefer `managed_identity`
  - use `subscription_key` only as an explicit fallback when that path is available and allowed
- confirm that PostgreSQL-side auth mode is reviewed separately from MCP client-facing auth expectations

---

## 5. Preconditions

Before starting a large deployment or rollout, ensure the following are true.

### 5.1 Azure resource prerequisites

You should have access to the Azure resources used by the environment, including:

- subscription
- resource group
- Azure Container Registry
- Azure Container Apps environment and application resources
- Azure Database for PostgreSQL Flexible Server
- any required secret or monitoring resources

### 5.2 Release artifact prerequisites

You should have:

- the intended application image tag
- the intended environment configuration set
- deployment-specific secret references
- the expected database bootstrap or migration procedure
- the expected ingress/auth boundary design for the target environment

### 5.3 Application contract prerequisites

You should know:

- the external base URL for the deployment
- the expected `/mcp` endpoint path
- the expected listening port inside the container
- the expected health/readiness behavior
- the intended auth behavior for:
  - missing auth
  - invalid auth
  - valid auth

You should also know that the large pattern has **two different auth surfaces** that must be reviewed independently:

- PostgreSQL-side Azure OpenAI auth for `azure_ai`
- MCP client-facing auth at the ingress or gateway boundary

### 5.4 Database prerequisites

Before accepting an environment as deployable, confirm:

- PostgreSQL version is the intended one
- database connectivity exists from the runtime environment
- schema bootstrap ownership is clear
- `pgvector` support is available
- `azure_ai` support is available when Azure OpenAI-backed embeddings are part of the environment
- PostgreSQL-side Azure OpenAI auth mode is explicitly known:
  - `auto`
  - `subscription_key`
  - `managed_identity`
- the auth-mode-specific prerequisites are satisfied:
  - for `auto`, the environment is understood well enough that the bootstrap path can prefer `managed_identity` and only use `subscription_key` as an acceptable fallback
  - for `subscription_key`, the correct Azure OpenAI key is available to the bootstrap path
  - for `managed_identity`, the PostgreSQL server identity and Azure RBAC assignments are in place
- Apache AGE support is either:
  - validated and in-scope
  - or explicitly bounded out for that environment

---

## 6. Environment Classification

Operators should classify Azure environments clearly.

Recommended minimum environment classes:

- `dev`
- `staging`
- `production-like`

The repository infrastructure examples are expected to align to these classes through:

- `infra/main.dev.bicepparam`
- `infra/main.staging.bicepparam`
- `infra/main.prod.bicepparam`

Operators should treat those parameter profiles as the starting sizing and posture baseline for the Azure large pattern, then adjust only where environment-specific policy, quota, or reliability requirements require it.

Those profiles should also be read as the starting point for MCP client handoff auth posture, and that posture is now explicitly aligned through the checked-in parameter profiles:

- `dev`
  - `mcpAuthMode=none`
  - `mcpAuthHeaderName=Authorization`
  - `azureOpenAiAuthMode=auto`
  - default MCP snippet handoff remains auth-light or header-free while the environment is still focused on early Azure bring-up
  - PostgreSQL-side Azure OpenAI auth should still prefer managed identity through the `auto` path
- `staging`
  - `mcpAuthMode=bearer_header`
  - `mcpAuthHeaderName=Authorization`
  - `azureOpenAiAuthMode=auto`
  - MCP snippet handoff reflects a bearer-header-oriented posture so shared preproduction validation exercises a more realistic protected-client shape
  - PostgreSQL-side Azure OpenAI auth should still prefer managed identity through the `auto` path unless the environment explicitly requires a key-based fallback
- `prod`
  - `mcpAuthMode=custom_header`
  - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
  - `azureOpenAiAuthMode=auto`
  - MCP snippet handoff is ready to reflect a gateway-specific custom header posture when the production boundary requires one
  - PostgreSQL-side Azure OpenAI auth should still prefer managed identity through the `auto` path, with subscription-key fallback treated as exceptional rather than normal

Suggested reading of those classes:

### `dev`
Use for:

- early Azure deployment verification
- config validation
- bootstrap validation
- ingress/auth smoke testing
- initial `/mcp` smoke validation

### `staging`
Use for:

- release-candidate validation
- revision rollout testing
- bounded concurrency validation
- operational diagnosis rehearsal
- acceptance checklist evidence

Current parameter profile guidance:

- start from `infra/main.staging.bicepparam`
- expect a more production-like runtime than `dev`, including:
  - larger PostgreSQL SKU and storage
  - HA enabled
  - at least two replicas
  - non-debug logging posture
  - PostgreSQL-side Azure embedding mode through `postgres_azure_ai`
- use this environment to validate rollout behavior, MCP smoke behavior, and operator handoff before wider production-like use
- treat the staging profile as the default place to rehearse auth-aware MCP client handoff with:
  - `mcpAuthMode=bearer_header`
  - `mcpAuthHeaderName=Authorization`
  - bearer-header-oriented generated snippets
  - copied client examples that are closer to the intended shared-environment posture than `dev`
- treat the staging profile as the default place to validate Azure OpenAI auth auto-resolution with:
  - `azureOpenAiAuthMode=auto`
  - managed-identity-first behavior
  - key-based fallback only when the environment explicitly requires it

### `production-like`
Use for:

- trusted shared usage
- bounded real-user access
- release-backed operator procedures
- monitored runtime operation
- rollback readiness

Current parameter profile guidance:

- start from `infra/main.prod.bicepparam`
- expect the strongest baseline posture in the checked-in parameter profiles, including:
  - larger PostgreSQL SKU and storage than `staging`
  - HA enabled
  - at least two replicas with higher max scale ceiling
  - non-debug runtime settings
  - PostgreSQL-side Azure embedding mode through `postgres_azure_ai`
- treat this profile as the baseline for production-oriented review, not as a guarantee that no further hardening is required
- treat the production-oriented profile as the place where MCP client handoff should be able to reflect the finalized gateway posture, including:
  - `mcpAuthMode=custom_header`
  - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
  - custom-header-oriented generated snippets when required
  - explicit operator review that the generated MCP client artifacts match the real production boundary
- treat the production-oriented profile as the strongest expected Azure OpenAI auth posture as well, including:
  - `azureOpenAiAuthMode=auto`
  - managed-identity-first behavior as the preferred production path
  - explicit review before allowing any subscription-key fallback

---

## 7. Deployment Responsibilities

The large Azure pattern should be operated with clear separation of responsibilities.

Recommended operator concerns include:

- image provenance
- revision rollout
- secret injection
- database bootstrap/migration
- extension validation
- ingress/auth validation
- health/readiness validation
- rollback readiness
- incident diagnosis

Recommended non-responsibilities for the application process itself include:

- direct certificate issuance
- end-user login UX
- public TLS termination
- organization identity management

---

## 8. Configuration Expectations

The Azure large pattern should use an explicit runtime configuration contract.

At minimum, operators should know and validate:

- application environment name
- database connection settings
- database SSL/TLS expectations
- embedding provider configuration
- external provider secrets if used
- debug endpoint posture
- logging level
- any graph/AGE-specific feature toggles
- any observability-specific settings

### 8.1 Secret handling rule

Do not treat local `.env` habits as the production model for Azure.

Instead:

- secrets should live in approved cloud secret handling mechanisms
- secrets should not be hardcoded in deployment templates
- secrets should not be embedded into image layers
- secret rotation posture should be documented per environment

### 8.2 Debug endpoint caution

If debug endpoints exist in the deployment:

- do not expose them publicly without deliberate review
- ensure they follow the intended auth boundary
- treat returned payloads as operationally sensitive
- disable them in broader exposure scenarios unless there is a clear operational need

---

## 9. Deployment Procedure

This section is intentionally scaffolded.
Replace placeholders with environment-specific commands and procedures as the Azure implementation is finalized.

The target operator and user experience for the large pattern is:

- one primary command:
  - `azd up`
- first-run interactive input is ideally limited to:
  - Azure subscription selection
  - Azure location selection
- infrastructure provisioning happens inside that workflow
- container image build should happen inside that workflow through Azure Container Registry remote build
- the large pattern should not depend on the local Docker engine for the normal Azure build/deploy path
- application deployment should follow the standard `azd` remoteBuild flow for Container Apps rather than a custom local-build workflow
- PostgreSQL allowlisting, `azure_ai` bootstrap, and schema bootstrap happen inside that workflow
- the deployment workflow is self-contained and should not depend on separately prepared helper storage, helper identities, manually uploaded bootstrap artifacts, or manual naming/password preparation in the normal happy path
- the remaining user task after success is ideally only MCP client configuration

This is intentionally different from the `small` pattern, where local startup depends on extra preflight preparation such as local certificate setup.
- after successful deployment, the workflow should run an automatic post-deploy smoke test against the deployed MCP endpoint
- the preferred smoke path is an MCP `initialize` probe followed by:
  - `tools/list`
  - `resources/list`
  rather than only a generic HTTP reachability check
- after successful deployment, the workflow should use a README-first, handoff-first console output shape
- that output should print the deployed MCP endpoint prominently
- that output should point users first to:
  - the generated MCP snippet README
  - the generated snippet directory
  - the generated summary metadata artifact
- that summary metadata should be treated as lightweight release evidence for the MCP handoff path
- after that, the workflow should keep console guidance concise and avoid overloading the user with long inline snippet blocks when the generated artifacts already contain the preferred copy/paste path
- generated MCP client snippets should support auth-aware rendering modes so they can align with the current large-pattern auth posture, including:
  - no auth headers
  - standard bearer `Authorization` headers
  - custom header names for future gateway-specific alignment
- operators should read those auth-aware snippets together with the selected environment profile:
  - `dev`
    - low-friction bring-up posture
    - `mcpAuthMode=none`
    - `mcpAuthHeaderName=Authorization`
    - `azureOpenAiAuthMode=auto`
  - `staging`
    - bearer-header rehearsal
    - `mcpAuthMode=bearer_header`
    - `mcpAuthHeaderName=Authorization`
    - `azureOpenAiAuthMode=auto`
  - `prod`
    - custom-header-ready handoff when required
    - `mcpAuthMode=custom_header`
    - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
    - `azureOpenAiAuthMode=auto`
- after successful deployment, the workflow should write MCP client snippet artifacts to:
  - `.azure/mcp-snippets`
- after successful deployment, the workflow should also write a small README artifact to:
  - `.azure/mcp-snippets/README.md`
- the remaining user task after success is ideally only copying or adapting one of those MCP client snippets

This is intentionally different from the `small` pattern, where local startup depends on extra preflight preparation such as local certificate setup.

## 9.1 Step 1 — Confirm intended release input

Before deployment, confirm:

- target environment name
- target Azure subscription and resource group
- target image tag
- expected app revision behavior
- expected auth boundary
- expected database target
- whether AGE is expected in this environment
- whether the environment is intended to support the one-command `azd up` flow without extra manual bootstrap steps

Record at least:

- deployment date/time
- operator identity
- release identifier
- image identifier
- target environment

## 9.2 Step 2 — Confirm image availability in ACR

Before rollout, confirm:

- the intended image exists in ACR
- the image tag matches the release record
- the image digest is traceable if possible
- the ACA deployment will reference the intended image, not an implicit mutable local state

Representative operator checklist:

- [ ] image repository identified
- [ ] image tag identified
- [ ] image digest recorded if available
- [ ] release/version mapping confirmed

## 9.3 Step 3 — Confirm runtime configuration and secrets

Before rollout, confirm:

- required settings are present
- required secret references are present
- secret values are not being copied into unsafe operator notes
- environment-specific overrides are intentional
- embedding configuration is appropriate for the environment
- database connection settings point to the intended Flexible Server instance

Representative checklist:

- [ ] DB host and database name confirmed
- [ ] DB credentials or identity-based access model confirmed
- [ ] Azure OpenAI resource, endpoint, and deployment name confirmed
- [ ] Azure OpenAI credential posture confirmed for both:
  - application runtime use
  - PostgreSQL `azure_ai` extension use
- [ ] debug posture confirmed
- [ ] logging posture confirmed

## 9.4 Step 4 — Confirm PostgreSQL readiness

Before application rollout, confirm:

- the database is reachable
- required schemas are present or will be created by the approved bootstrap path
- `pgvector` is available
- `azure_ai` posture is known
- Azure OpenAI deployment prerequisites are available
- AGE posture is known
- migration/bootstrap order is understood

Representative checklist:

- [ ] DB connectivity confirmed
- [ ] schema/bootstrap ownership confirmed
- [ ] extension validation plan confirmed
- [ ] backup posture confirmed for the environment

## 9.5 Step 5 — Apply or verify schema/bootstrap

Apply or verify the approved bootstrap/migration step for the target environment.

Operator expectations:

- schema changes should be explicit
- migration ownership should be clear
- startup should not be relied on to perform uncontrolled schema mutation
- failures here should block rollout acceptance
- extension bootstrap should include the PostgreSQL-side Azure AI configuration needed for Azure OpenAI embedding calls when that path is enabled

Representative checklist:

- [ ] bootstrap/migration step executed or verified
- [ ] required tables/views present
- [ ] extension state confirmed
- [ ] `azure_ai` configuration applied if Azure OpenAI-backed embeddings are enabled
- [ ] Azure OpenAI deployment reference stored in PostgreSQL extension settings if required by the chosen bootstrap path
- [ ] no blocking schema errors remain

## 9.6 Step 6 — Run automated PostgreSQL bootstrap after PostgreSQL provisioning

For the large Azure pattern, PostgreSQL bootstrap must not be left as a manual afterthought.

In the ideal large-pattern experience, this step is part of the same `azd up` flow that provisions infrastructure and deploys the application.

The deployment flow should automate the following sequence:

1. configure the PostgreSQL server parameter that allowlists required extensions through `azure.extensions`
2. wait until the PostgreSQL server accepts connections
3. connect to the intended database
4. execute the bootstrap queries needed to:
   - create required extensions such as:
     - `azure_ai`
     - `vector`
     - optionally `age`
   - set PostgreSQL-side Azure OpenAI settings
   - verify those settings
   - optionally validate the embedding deployment with a representative
     `azure_openai.create_embeddings(...)` call
5. execute schema bootstrap work needed to:
   - apply the bundled `ctxledger` schema
   - verify representative canonical tables and other expected objects
   - leave the database in a state where the application can start without requiring a separate manual schema step in the normal happy path

Operational expectations:

- this step should run automatically as part of infrastructure deployment or immediately after it
- deployment acceptance should fail if this bootstrap step fails
- operators should not need to copy/paste bootstrap SQL or schema SQL manually for normal environment creation
- the automation must wait for real database readiness instead of assuming provisioning completion means immediate connectivity
- the automation should be self-contained inside the Azure deployment flow rather than requiring pre-created helper resources or manually staged bootstrap files
- users should not need a separate post-deploy checklist beyond MCP client configuration in the normal happy path

Representative checklist:

- [ ] required extensions were allowlisted through the `azure.extensions` server parameter
- [ ] bootstrap automation waited for PostgreSQL connectivity successfully
- [ ] bootstrap automation connected to the intended database successfully
- [ ] `CREATE EXTENSION IF NOT EXISTS azure_ai` executed successfully
- [ ] PostgreSQL-side Azure OpenAI settings were written successfully
- [ ] PostgreSQL-side Azure OpenAI settings were verified successfully
- [ ] representative embedding validation succeeded when enabled
- [ ] the bundled `ctxledger` schema was applied automatically
- [ ] representative schema verification succeeded

## 9.7 Step 7 — Roll out the ACA revision

## 9.7 Step 7 — Roll out the ACA revision

Deploy the intended application revision using the approved deployment method.

Operator expectations:

- confirm the intended image is used
- confirm the expected container port is configured
- confirm secret and env injection succeeds
- confirm the revision becomes healthy
- confirm rollout behavior matches the intended strategy

Representative checklist:

- [ ] new revision created or updated as expected
- [ ] app startup completed
- [ ] no immediate config/secret crash loop observed
- [ ] ingress target and port mapping consistent
- [ ] health/readiness signals available

## 9.8 Step 8 — Validate ingress and auth boundary

After rollout, validate the ingress path.

At minimum, validate:

- public endpoint resolves correctly
- TLS termination behaves as expected
- missing auth is rejected
- invalid auth is rejected
- valid auth reaches the app successfully
- `/mcp` remains the effective endpoint

For the one-command large-pattern goal, this validation should be part of the deployment workflow or immediate operator validation after `azd up`, not a user-side setup burden.

The preferred direction is that a lightweight post-deploy smoke test runs automatically as part of the deployment flow before the final MCP client configuration snippets are shown to the user.

For the Azure large pattern, the preferred smoke shape is:

- an MCP `initialize` probe against the deployed `/mcp` endpoint
- a follow-up `tools/list` probe after successful initialization
- a follow-up `resources/list` probe after successful initialization
- using the protocol version expected by the deployment
- treating the result as successful only when it demonstrates bounded MCP-level reachability or bounded auth enforcement

Representative checklist:

- [ ] base URL reachable
- [ ] `/mcp` reachable through intended ingress
- [ ] missing auth rejected
- [ ] invalid auth rejected
- [ ] valid auth accepted

## 9.9 Step 9 — Validate database-backed readiness

After ingress validation, confirm the app is operational against the real Azure database.

At minimum, validate:

- startup completed against the real DB
- the app is not failing due to schema mismatch
- the app is not failing due to extension mismatch
- the app is not failing due to DB SSL/network configuration
- the app can execute a representative MCP flow
- the selected Azure OpenAI integration path works as intended:
  - application-side Azure OpenAI calls when used
  - PostgreSQL-side `azure_ai` embedding calls when used

Representative checklist:

- [ ] DB-backed startup successful
- [ ] no extension-related startup failure
- [ ] no connection/auth failure to PostgreSQL
- [ ] representative MCP workflow smoke succeeds

## 9.10 Step 10 — Record deployment evidence

For each rollout, capture deployment evidence such as:

- deployed image tag and digest
- revision identifier
- target URL
- auth validation results
- representative `/mcp` validation result
- DB readiness result
- whether the environment satisfied the intended one-command `azd up` posture
- whether the automatic post-deploy smoke test ran and passed as intended
- whether the deployment output included the MCP endpoint and MCP client configuration snippets as intended
- whether the generated MCP client snippets used the intended auth-aware rendering mode for the environment
- whether that auth-aware rendering mode matched the selected environment profile:
  - `dev`
    - `mcpAuthMode=none`
    - `mcpAuthHeaderName=Authorization`
  - `staging`
    - `mcpAuthMode=bearer_header`
    - `mcpAuthHeaderName=Authorization`
  - `prod`
    - `mcpAuthMode=custom_header`
    - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
- whether the Azure OpenAI auth mode matched the selected environment profile:
  - `dev`
    - `azureOpenAiAuthMode=auto`
  - `staging`
    - `azureOpenAiAuthMode=auto`
  - `prod`
    - `azureOpenAiAuthMode=auto`
- if `auto` was used, whether it resolved to the expected managed-identity-first posture for that environment
- whether the deployment output included the MCP endpoint and handoff-first artifact pointers as intended
- whether MCP client snippet artifacts were written successfully under:
  - `.azure/mcp-snippets`
- whether the MCP snippet README artifact was written successfully under:
  - `.azure/mcp-snippets/README.md`
- whether the generated snippet summary metadata artifact was written successfully under:
  - `.azure/mcp-snippets/summary.json`
- whether that summary metadata artifact is being treated as lightweight release evidence for the MCP handoff path
- whether the generated snippet summary metadata captured the deployment and release-evidence context needed for later reuse, including:
  - MCP endpoint
  - auth mode
  - auth header name when relevant
  - Azure environment name
  - Azure location
  - Azure environment type
  - deployment timestamp
  - application version
  - postdeploy smoke status
  - postdeploy smoke probe mode
  - postdeploy smoke protocol version
  - postdeploy smoke follow-up probes
  - postdeploy smoke body preview
  - preferred artifact guidance
  - preferred artifact hint pointing to the rendered README
  - auth-aware usage hints
  - environment-aware usage hints
- known limitations or follow-up items

This evidence should be stored in the project’s normal release/operations record location.

---

## 10. Post-Deploy Validation

The large Azure pattern should not be treated as healthy until post-deploy checks pass.

## 10.1 Required validation classes

At minimum, validate:

1. endpoint reachability
2. auth reject path
3. auth allow path
4. DB-backed app startup
5. representative MCP call path

## 10.2 Representative validation shape

The exact command set may vary by environment and auth boundary, but the validation intent should remain stable:

- unauthenticated request should fail
- invalidly authenticated request should fail
- validly authenticated `/mcp` request should succeed
- representative workflow-oriented MCP behavior should succeed
- representative resource read behavior should succeed if included in the environment’s acceptance scope

## 10.3 Optional scale-oriented validation

For staging or production-like environments, also consider validating:

- concurrent request behavior
- rollout behavior during overlapping revisions
- DB connection pressure under representative parallel usage
- latency posture for representative tool calls

---

## 11. Health and Readiness Expectations

Operators should define and verify health/readiness expectations clearly.

### 11.1 Minimum readiness interpretation

A deployment should not be considered ready if any of the following are unresolved:

- container startup failure
- missing runtime config
- unresolved secret injection failure
- database connectivity failure
- schema/bootstrap failure
- missing required extension support
- ingress misrouting
- auth boundary misconfiguration

### 11.2 Minimum healthy-state interpretation

A deployment can be treated as minimally healthy only when:

- the current revision is running normally
- the intended ingress path is live
- the intended auth boundary behaves correctly
- the app can serve `/mcp`
- the app can reach canonical PostgreSQL state successfully

---

## 12. PostgreSQL Extension Validation

The Azure large pattern must handle extension validation explicitly.

## 12.1 `pgvector`

`pgvector` should be treated as required for the accepted large deployment path.

Operators should confirm:

- the extension is supported on the chosen Flexible Server configuration
- the extension is enabled where required
- the deployment does not silently proceed without vector capability if the release claims vector-backed retrieval support

Representative checklist:

- [ ] `pgvector` support confirmed
- [ ] `pgvector` enablement confirmed
- [ ] app behavior consistent with vector-backed retrieval expectations

## 12.2 `azure_ai` and Azure OpenAI

The large Azure pattern should use Azure OpenAI instead of direct public OpenAI API usage.

Wherever practical, PostgreSQL should use the `azure_ai` extension so embedding creation can be invoked directly from the database through Azure OpenAI functions such as:

- `azure_openai.create_embeddings(...)`

Operators should confirm:

- the `azure_ai` extension is supported on the chosen Flexible Server configuration
- the extension is allowlisted through the `azure.extensions` server parameter
- the extension is created automatically after connectivity becomes available
- the Azure OpenAI endpoint is configured correctly for the extension
- the intended PostgreSQL-side Azure OpenAI auth mode is explicit and correct:
  - `auto`
  - `subscription_key`
  - `managed_identity`
- the auth-mode-specific configuration is correct:
  - `auto`
    - the bootstrap path prefers `managed_identity`
    - the fallback to `subscription_key` is used only when explicitly available and acceptable for the environment
  - `subscription_key`
    - `azure_openai.auth_type = 'subscription-key'`
    - `azure_openai.subscription_key` is set correctly
  - `managed_identity`
    - `azure_openai.auth_type = 'managed-identity'`
    - PostgreSQL Flexible Server managed identity is enabled
    - Azure OpenAI RBAC is assigned correctly
- the intended Azure OpenAI deployment name is known and matches the environment
- the chosen embedding dimensions are compatible with the selected Azure OpenAI embedding deployment
- representative PostgreSQL-side embedding generation succeeds when this path is in scope

Representative checklist:

- [ ] `azure_ai` support confirmed
- [ ] `azure.extensions` allowlist contains `azure_ai`
- [ ] automated bootstrap created `azure_ai` successfully after PostgreSQL became reachable
- [ ] Azure OpenAI endpoint configured for PostgreSQL extension use
- [ ] PostgreSQL-side Azure OpenAI auth mode confirmed
- [ ] if auth mode is `auto`, the managed-identity-first resolution posture is confirmed
- [ ] PostgreSQL-side Azure OpenAI auth settings or managed identity prerequisites confirmed
- [ ] Azure OpenAI embedding deployment name confirmed
- [ ] representative `azure_openai.create_embeddings(...)` validation succeeds
- [ ] application docs and operator docs consistently describe Azure OpenAI as the large-pattern embedding provider

Operational caution:

- do not carry forward the local `OPENAI_API_KEY` posture from the `small` pattern as the default large-pattern design
- for the large pattern, do not treat PostgreSQL-side `azure_ai` auth settings as the same thing as MCP client-facing auth settings
- if the application runtime also calls Azure OpenAI directly, keep that configuration aligned with the PostgreSQL-side `azure_ai` configuration
- if PostgreSQL-side embedding generation becomes the primary path, operator guidance and validation should treat it as a first-class acceptance requirement
- do not treat extension allowlisting alone as sufficient; the deployment must also wait for connectivity and execute the bootstrap queries successfully

## 12.3 Apache AGE

AGE requires special caution.

Operators should confirm one of the following for each environment:

1. AGE is supported, enabled, and validated
2. AGE is intentionally disabled or deferred, with the environment documented accordingly

Do not leave AGE in an ambiguous state.

Representative checklist:

- [ ] AGE support status is explicit
- [ ] if supported, AGE enablement is validated
- [ ] if not supported, the environment is documented as bounded accordingly
- [ ] graph-related behavior is not treated as canonical

---

## 13. Observability and Diagnosis

The Azure large pattern requires operator-visible diagnosis paths.

## 13.1 Minimum operator visibility

Operators should be able to inspect:

- container startup failures
- revision deployment failures
- auth/ingress failures
- database connectivity failures
- schema/bootstrap failures
- extension-related failures
- Azure OpenAI configuration failures
- PostgreSQL `azure_ai` invocation failures

## 13.2 Minimum logging posture

The accepted Azure runbook should eventually point to the concrete logging surfaces used in the environment, such as:

- ACA revision logs
- application logs
- gateway/ingress logs
- database diagnostic signals where enabled

### Failure classes that should be distinguishable

Operators should be able to tell the difference between:

- app startup failure
- secret/config failure
- auth failure
- ingress routing failure
- PostgreSQL connectivity failure
- extension validation failure
- migration/bootstrap failure
- Azure OpenAI endpoint or credential misconfiguration
- PostgreSQL-side `azure_ai` execution failure

## 13.3 Grafana question

The local pattern includes Grafana, but the Azure large pattern should treat Grafana as a deliberate choice, not an automatic carry-forward.

For each environment, document whether Grafana is:

- included
- optional
- deferred
- replaced by Azure-native monitoring as the primary baseline

Do not leave the observability posture implicit.

---

## 14. Scaling and Connection Management

The Azure large pattern exists partly to support multiple concurrent users, but cloud scaling must remain bounded and intentional.

## 14.1 ACA scaling posture

For each environment, document:

- minimum replicas
- maximum replicas
- expected concurrency posture
- CPU/memory baseline
- rollout/revision overlap expectations

Do not claim unbounded scale.

## 14.2 PostgreSQL connection posture

Because `ctxledger` is PostgreSQL-backed, operators must consider aggregate connection pressure across:

- steady-state replicas
- scale-out events
- overlapping revisions during rollout

For each environment, document:

- per-replica pool sizing assumptions
- total expected connection count
- maximum safe DB connection envelope
- mitigation plan if connection pressure grows too high

Representative checklist:

- [ ] per-replica pool assumptions documented
- [ ] aggregate connection estimate documented
- [ ] scale-out impact considered
- [ ] revision overlap impact considered

---

## 15. Rollback and Recovery

Every Azure large deployment should have at least a bounded recovery posture.

## 15.1 App rollback

Operators should be able to answer:

- which image tag was previously known-good
- which ACA revision was previously healthy
- how to move traffic back or redeploy the known-good app version
- how to verify recovery after rollback

Representative checklist:

- [ ] previous known-good image identified
- [ ] previous known-good revision identified
- [ ] rollback method documented
- [ ] post-rollback verification steps documented

## 15.2 Database rollback caution

Do not conflate:

- application rollback
- database restore

Database restore should be treated as a separate operational concern with higher caution.

Operators should avoid casual assumptions that a bad deploy can always be solved by simply reverting the database.

## 15.3 Extension-related recovery

If deployment failure is caused by extension support or bootstrap mismatch:

- stop treating the rollout as a simple app-only failure
- document whether the environment is blocked by:
  - unsupported extension posture
  - migration error
  - bootstrap drift
  - version incompatibility

---

## 16. Incident Triage Guide

Use the following high-level triage split when the Azure deployment is unhealthy.

## 16.1 Endpoint unreachable

Likely classes:

- ingress misconfiguration
- gateway outage or misrouting
- ACA ingress exposure mismatch
- DNS or certificate misconfiguration

Primary questions:

- is the public endpoint resolving
- is TLS terminating correctly
- is traffic reaching ACA at all

## 16.2 Auth always fails

Likely classes:

- gateway/auth config error
- missing expected header propagation
- incorrect client auth shape
- secret/config mismatch

Primary questions:

- does missing auth fail differently from invalid auth
- does valid auth ever reach the app
- did the auth boundary change unexpectedly

## 16.3 Revision starts then fails

Likely classes:

- missing secret
- invalid env configuration
- app startup failure
- port mismatch
- health probe mismatch

Primary questions:

- did the container start successfully
- is the expected listening port configured correctly
- did secret injection succeed

## 16.4 Revision is running but app is unhealthy

Likely classes:

- DB connectivity issue
- schema/bootstrap mismatch
- missing extension
- Azure OpenAI configuration issue
- PostgreSQL `azure_ai` configuration issue
- PostgreSQL-side Azure OpenAI auth mode mismatch
- runtime dependency failure

Primary questions:

- can the app reach PostgreSQL
- does the schema match expectations
- are required extensions actually available
- is Azure OpenAI configured correctly for the environment
- is PostgreSQL `azure_ai` configured correctly for direct embedding calls
- if PostgreSQL uses `managed_identity`, are the identity and RBAC assignments correct
- if PostgreSQL uses `subscription_key`, is the correct Azure OpenAI key configured

## 16.5 MCP endpoint responds but workflow usage fails

Likely classes:

- DB transactional problem
- schema drift
- memory/embedding config issue
- Azure OpenAI deployment mismatch
- PostgreSQL `azure_ai` extension configuration issue
- PostgreSQL-side Azure OpenAI auth mismatch
- extension-specific feature mismatch

Primary questions:

- is canonical DB state writable
- are required tables/views present
- did bootstrap succeed fully
- is Azure OpenAI reachable through the intended integration path
- does PostgreSQL-side `azure_openai.create_embeddings(...)` work in the deployed environment when expected
- is PostgreSQL using the intended auth mode:
  - `auto`
  - `subscription_key`
  - `managed_identity`
- if `auto` is configured, did it resolve to the expected mode for this environment
- is the environment claiming features it cannot currently support

---

## 17. Operational Records

For each Azure deployment or operator intervention, record at least:

- date/time
- operator
- environment
- target image tag
- target revision
- deployment outcome
- validation outcome
- known issues
- follow-up actions

Recommended additional records:

- image digest
- auth validation summary
- representative MCP smoke result
- extension status summary
- rollback actions if performed

---

## 18. Open Questions to Close Over Time

This scaffold intentionally leaves room for final decisions.
The following should be resolved as the Azure large pattern matures:

- final ingress/gateway choice
- final auth mechanism for MCP-capable IDE clients
- final Grafana vs Azure-native monitoring posture
- final AGE support posture on the target Flexible Server configuration
- final environment sizing guidance
- final rollout and rollback command sequences
- final Infrastructure as Code source of truth

---

## 19. Minimum Acceptance Reading for Operators

Before operating the Azure large pattern, operators should read together:

- the main `README.md`
- `docs/operations/deployment/deployment.md`
- `docs/project/releases/plans/versioned/large_deployment_pattern_1_0_0_plan.md`
- `docs/project/releases/plans/versioned/1.0.0_large_deployment_acceptance_checklist.md`
- the environment parameter profile that matches the target deployment:
  - `infra/main.dev.bicepparam`
  - `infra/main.staging.bicepparam`
  - `infra/main.prod.bicepparam`

Use this runbook as the operational bridge between those planning and deployment documents.

---

## 20. Summary

The Azure large deployment pattern is intended to provide a credible cloud-hosted path for `ctxledger` using:

- Azure Container Registry
- Azure Container Apps
- Azure Database for PostgreSQL Flexible Server

Operators should preserve the key architectural rules:

- PostgreSQL is canonical
- `pgvector` is required
- Azure OpenAI is the intended large-pattern AI provider
- PostgreSQL should use the `azure_ai` extension as much as practical for direct Azure OpenAI embedding generation
- Apache AGE is bounded and non-canonical if supported
- ingress, TLS, and authentication stay outside the application core
- `/mcp` remains the external MCP contract

The intended user experience should also remain clear:

- unlike the `small` pattern, the Azure `large` pattern should not depend on local preflight tooling such as certificate generation utilities
- the ideal flow is `azd up`
- the ideal first-run prompts should be limited to subscription and location selection
- that `azd up` flow should be self-contained rather than assuming separate helper infrastructure preparation for deployment automation
- after successful completion, the deployment flow should already have run a lightweight smoke test against the MCP endpoint
- that smoke test should preferably use MCP `initialize` followed by:
  - `tools/list`
  - `resources/list`
  so the deployment validates basic protocol-level reachability and a representative capability/resource response instead of only generic HTTP reachability
- after successful completion, the deployment output should follow a README-first, handoff-first shape:
  - first, tell the user that the next step is MCP client configuration
  - then surface the MCP endpoint prominently
  - then point the user to the generated handoff artifacts under:
    - `.azure/mcp-snippets/README.md`
    - `.azure/mcp-snippets/summary.json`
    - `.azure/mcp-snippets`
  - treat the README as the primary user-facing handoff artifact
  - treat the summary metadata as lightweight release evidence for the MCP handoff path
  - keep the final console guidance concise, preferring the generated README and summary artifacts over long inline snippet output
- the large deployment should rely on the standard `azd` remoteBuild flow so the same handoff expectations remain valid whether the image was built locally during small-pattern work or remotely for the large Azure pattern
- those generated MCP client snippets should support auth-aware rendering modes so they can match the current large-pattern auth posture, including bearer-header or custom-header variants when needed
- operators should expect those auth-aware generated snippets to differ by environment profile:
  - `dev`
    - lowest-friction handoff posture
    - `mcpAuthMode=none`
    - `mcpAuthHeaderName=Authorization`
    - `azureOpenAiAuthMode=auto`
  - `staging`
    - bearer-header-oriented rehearsal posture
    - `mcpAuthMode=bearer_header`
    - `mcpAuthHeaderName=Authorization`
    - `azureOpenAiAuthMode=auto`
  - `prod`
    - custom-header-capable handoff posture when required by the finalized gateway
    - `mcpAuthMode=custom_header`
    - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
    - `azureOpenAiAuthMode=auto`
- operators should also expect the PostgreSQL-side Azure OpenAI auth posture to remain managed-identity-first across those profiles when `auto` is selected
- after successful completion, the deployment flow should also write snippet summary metadata that records the deployment handoff context in a lightweight release-evidence structure, including:
  - endpoint and server identity
  - auth mode and auth header interpretation
  - Azure environment name
  - Azure location
  - Azure environment type
  - deployment timestamp
  - application version
  - remotely built image reference
  - postdeploy smoke status
  - postdeploy smoke probe mode
  - postdeploy smoke protocol version
  - postdeploy smoke follow-up probes
  - postdeploy smoke body preview
  - generated artifact paths
  - preferred artifact guidance
- the remaining user task should ideally be only MCP client / AI agent configuration
- operators should not need to perform a separate local Docker build to satisfy the large Azure deployment path

Until the Azure implementation is fully closed out, this runbook should be used as a scaffolded operator baseline:

- explicit
- bounded
- cautious about unresolved platform assumptions
- focused on safe deployment, validation, and recovery
- explicit that PostgreSQL bootstrap is automated through deployment sequencing:
  - allowlist required extensions
  - wait for connectivity
  - run `azure_ai` bootstrap queries
  - apply the bundled schema
  - verify representative schema objects