# Azure Infrastructure Scaffold for the `ctxledger` Large Deployment Pattern

## Purpose

This directory contains the initial Infrastructure as Code scaffold for the
`ctxledger` **large deployment pattern**.

The large pattern is the Azure-hosted deployment direction intended to
complement the existing local `small` pattern.

The current scaffold focuses on:

- Azure Container Registry
- Azure Container Apps
- Azure Database for PostgreSQL Flexible Server
- Azure OpenAI
- Log Analytics integration for Container Apps environment logging
- Azure-native embedding integration through PostgreSQL `azure_ai`

A key target for the large pattern is a **self-contained one-command deployment
experience** through Azure Developer CLI:

- on first run, the only required user choices should ideally be:
  - Azure subscription selection
  - Azure location selection
- `azd up` should provision infrastructure and deploy the application
- PostgreSQL `azure_ai` bootstrap should run automatically as part of that flow
- the deployment should not depend on pre-created bootstrap infrastructure
  outside the checked-in IaC happy path
- resource naming, bootstrap support resources, database bootstrap, and other
  normal deployment details should be derived or created automatically
- the large-pattern container image should be built remotely in Azure Container
  Registry rather than by a local Docker engine
- the deployment flow should use the standard `azd` remoteBuild path so image
  creation stays inside the Azure deployment workflow
- the remaining user to-do should ideally be only:
  - configuring the AI agent / MCP client to use the deployed endpoint
- the deployment workflow should surface ready-to-copy MCP client configuration
  snippets automatically after deployment completes
- the deployment workflow should also write MCP client snippet artifacts to a
  predictable local output directory for later reuse
- the deployment workflow should support auth-aware MCP snippet generation so
  generated client snippets can reflect:
  - no auth headers
  - standard bearer `Authorization` headers
  - custom header names aligned with the intended large-pattern gateway contract
- the deployment workflow should also enrich the generated snippet metadata with
  deployment context such as:
  - Azure environment name
  - Azure location
  - Azure environment type
  - selected MCP auth mode
  - selected MCP auth header name when applicable
- the deployment workflow should also persist post-deploy smoke result metadata
  alongside those snippet artifacts, including:
  - smoke status
  - smoke probe mode
  - smoke protocol version
  - smoke follow-up probes
  - smoke body preview
  - deployment timestamp
  - application version
- the deployment workflow should also write a small README artifact alongside
  those snippet files so users can understand the generated outputs later
- the preferred terminal handoff should be README-first:
  - first point the user at the deployed MCP endpoint
  - then point the user at the generated README artifact
  - then point the user at the snippet directory and summary metadata
  - avoid relying on large inline snippet dumps as the primary handoff surface
- the generated summary metadata should also be structured as lightweight
  release evidence for the MCP handoff path, with clear sections for:
  - artifacts
  - environment
  - auth
  - smoke
  - deployment
  - recommended usage
- in practice, users should treat the generated `README.md` as the primary
  handoff artifact and `summary.json` as the structured release-evidence record
  for later review, automation, or operator traceability
- the infrastructure directory should provide environment-oriented parameter
  profiles for:
  - development
  - staging
  - production
- those environment-oriented parameter profiles should also make the intended MCP
  client handoff auth posture explicit, so generated snippet artifacts can stay
  aligned with the expected environment-specific auth model

This directory should be read together with:

- `docs/project/releases/plans/versioned/large_deployment_pattern_1_0_0_plan.md`
- `docs/project/releases/plans/versioned/1.0.0_large_deployment_acceptance_checklist.md`
- `docs/operations/runbooks/azure_large_operator_runbook.md`
- `docs/operations/deployment/deployment.md`

This infrastructure directory is a **starting point**, not a final
production-complete Azure platform.

---

## Current files

### `main.bicep`

Primary Bicep template for the current Azure large deployment scaffold.

It provisions a bounded baseline made of:

- Azure Container Registry
- Azure Container Apps managed environment
- Azure Container App for `ctxledger`
- Azure Database for PostgreSQL Flexible Server
- a PostgreSQL database
- a firewall rule allowing Azure services to reach PostgreSQL
- PostgreSQL extension allowlisting through the `azure.extensions` server parameter
- Azure OpenAI account and embedding deployment
- a deployment-script storage account created by the same IaC
- a user-assigned managed identity created by the same IaC
- an automated post-deploy bootstrap step that:
  - waits for PostgreSQL connectivity
  - connects to the target database
  - creates the required extensions
  - configures `azure_ai` for Azure OpenAI
  - optionally validates `azure_openai.create_embeddings(...)`
  - applies the bundled `ctxledger` schema automatically
  - verifies representative schema objects after bootstrap
- Log Analytics workspace
- ACR pull role assignment for the Container App identity

### `main.dev.bicepparam`

Example parameter file for a development-oriented deployment shape.

Use it as:

- a reference for expected parameters
- a starting point for environment-specific parameter files
- an example of how the current scaffold is intended to be customized

This profile is also the default companion for the standard `azd` remoteBuild
flow:

- `azd` provisions infrastructure first
- the registry endpoint output is then used by the service definition in
  `azure.yaml`
- image build happens remotely in Azure Container Registry rather than through a
  local Docker engine

Do **not** treat the example values as production-ready defaults.

### `main.staging.bicepparam`

Example parameter file for a staging-oriented deployment shape.

This profile is intended to represent a more realistic shared environment than
`dev`, including:

- higher PostgreSQL sizing than `dev`
- high availability enabled
- more than one application replica
- bounded production-like logging and timeout posture

Use it when you want:

- release-candidate validation
- shared preproduction testing
- concurrency and rollout rehearsal
- stronger verification of the Azure large pattern than a minimal dev setup

Current MCP handoff auth reading:

- `staging` is a good fit for a bearer-header-oriented handoff posture
- the checked-in staging profile now sets:
  - `mcpAuthMode=bearer_header`
  - `mcpAuthHeaderName=Authorization`
- the checked-in staging profile should also keep Azure OpenAI auth selection on:
  - `azureOpenAiAuthMode=auto`
- generated MCP client snippets can therefore be rendered with a standard
  `Authorization` header when that is the intended staging auth model
- for Azure OpenAI access, `auto` should still prefer `managed_identity`
  unless the environment explicitly requires a different path

### `main.prod.bicepparam`

Example parameter file for a production-oriented deployment shape.

This profile is intended to provide a more conservative baseline for production
planning, including:

- higher PostgreSQL sizing than `staging`
- high availability enabled
- stronger replica posture than `staging`
- production-oriented tags and capacity assumptions

Use it as:

- a starting point for production review
- a baseline for hardening discussions
- an example of how the large pattern should differ across environments

Current MCP handoff auth reading:

- `prod` is a good fit for a custom-header-oriented handoff posture when the
  finalized large-pattern gateway uses a non-default propagated header
- the checked-in production profile now sets:
  - `mcpAuthMode=custom_header`
  - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
- the checked-in production profile should also keep Azure OpenAI auth selection on:
  - `azureOpenAiAuthMode=auto`
- generated MCP client snippets can therefore be rendered with a custom header
  name that matches the intended production gateway contract
- for Azure OpenAI access, `auto` should still prefer `managed_identity`
  unless the environment explicitly requires a different path

As with the other parameter files, treat it as a checked-in scaffold rather than
as a final environment-specific truth without review.

---

## Design intent

The IaC in this directory is designed to preserve the repository’s current
architecture principles.

### 1. `ctxledger` remains the application backend

The infrastructure should host `ctxledger`, not change its role.

The app remains responsible for:

- MCP behavior
- workflow logic
- memory logic
- persistence orchestration

The infrastructure owns:

- cloud resource provisioning
- network exposure
- runtime hosting
- managed database hosting
- secret injection posture
- operational integration points

### 2. PostgreSQL remains canonical

Even in Azure, PostgreSQL remains the canonical system of record for:

- workflow state
- checkpoints
- memory items
- embeddings
- summaries
- other durable relational state

### 3. Graph support remains bounded

The large pattern is intended to preserve:

- `pgvector`
- Apache AGE, if validated on the target Azure PostgreSQL shape

But the architectural rule remains:

- graph-backed structures are derived or bounded support layers
- relational PostgreSQL state remains canonical

### 4. Ingress and authentication stay outside the application core

The Bicep scaffold deploys the application into Azure Container Apps, but it
does **not** finalize the full ingress and authentication architecture for all
future environments.

That is intentional.

The large pattern should preserve the design rule that:

- public exposure happens at the ingress or gateway boundary
- authentication happens outside `ctxledger`
- `ctxledger` should not become the identity provider

### 5. Azure OpenAI replaces the small-pattern OpenAI posture

The local `small` pattern can rely on direct public OpenAI API usage, but the
Azure `large` pattern should not carry that posture forward unchanged.

For the large pattern, the intended AI posture is:

- Azure OpenAI is the primary embedding provider
- PostgreSQL should use the `azure_ai` extension wherever practical
- PostgreSQL-side calls such as `azure_openai.create_embeddings(...)` should be
  treated as a first-class capability
- direct application-side Azure OpenAI calls should be bounded and justified,
  rather than becoming the default without review

---

## What the current scaffold provisions

The current `main.bicep` provisions these resources.

### Azure Container Registry

Used for:

- storing application images
- release image provenance
- runtime image pull source for Azure Container Apps

Current posture:

- admin user disabled
- anonymous pull disabled
- retention policy enabled

### Log Analytics Workspace

Used for:

- Container Apps environment log integration
- baseline operational visibility

### Azure Container Apps Managed Environment

Used for:

- hosting the `ctxledger` Container App
- integrating Container Apps logs with Log Analytics

### Azure Container App

Used for:

- running the `ctxledger` HTTP MCP server
- setting runtime configuration through environment variables
- scaling with bounded replica settings
- exposing the app through Container Apps ingress when enabled

### Azure Database for PostgreSQL Flexible Server

Used for:

- canonical relational persistence
- `pgvector`
- Apache AGE if validated and supported
- `azure_ai` extension-backed Azure OpenAI integration
- direct PostgreSQL-side embedding generation where practical

### PostgreSQL Database

Used for:

- the actual `ctxledger` application database
- PostgreSQL-side AI configuration state used by `azure_ai`

### Firewall rule allowing Azure services

Used for:

- enabling Azure-hosted runtime access to PostgreSQL in the current scaffold
- allowing the post-deployment bootstrap step to reach PostgreSQL during initial
  `azure_ai` configuration

This is a practical early scaffold decision, not necessarily the final network
hardening posture.

### PostgreSQL extension allowlisting and automated `azure_ai` bootstrap

Used for:

- adding the required extensions to the Flexible Server allowlist through the
  `azure.extensions` server parameter
- ensuring PostgreSQL is allowed to create:
  - `vector`
  - `azure_ai`
  - `age`
- automatically running a post-deploy bootstrap step after infrastructure
  provisioning
- waiting until PostgreSQL accepts connections before executing bootstrap SQL
- configuring PostgreSQL-side Azure OpenAI settings through `azure_ai`
- validating the PostgreSQL-integrated Azure OpenAI path with
  `azure_openai.create_embeddings(...)` when enabled

Operationally, this means the infrastructure is expected to do more than just
create the database server.

It also means the bootstrap path should be **self-contained** inside the checked-in
deployment assets:

- the storage used by deployment scripts is created by the IaC
- the managed identity used by deployment scripts is created by the IaC
- the deployment should not depend on separately prepared bootstrap resources to
  complete the normal happy path

The intended flow is:

1. provision Flexible Server
2. set `azure.extensions`
3. provision bootstrap execution dependencies as part of the same IaC
4. wait for PostgreSQL connectivity
5. connect to the target database
6. run extension and `azure_ai` bootstrap work
7. optionally validate Azure OpenAI embedding creation directly from PostgreSQL

### Azure OpenAI account and deployment

Used for:

- providing the Azure OpenAI endpoint for the large pattern
- hosting the embedding deployment used by the Azure environment
- aligning the AI provider with Azure-native identity, networking, and
  operations
- supporting both:
  - application-side Azure OpenAI usage
  - PostgreSQL-side Azure OpenAI usage through `azure_ai`

### ACR pull role assignment

Used for:

- allowing the Container App managed identity to pull images from ACR

---

## What the scaffold does not do yet

This directory intentionally does **not** claim to solve every production
concern.

Important non-goals or follow-up areas include:

- final private networking design
- final auth gateway choice
- final custom domain and certificate design
- final Key Vault integration
- final zero-downtime rollout posture
- final autoscaling tuning
- final multi-environment deployment topology
- final production-grade firewall and VNet isolation design
- final Grafana hosting decision
- schema bootstrap automation
- extension validation automation for `pgvector`, `azure_ai`, and Apache AGE
- final PostgreSQL-side Azure OpenAI bootstrap and validation procedure

You should treat those as explicit follow-up areas, not hidden assumptions.

---

## Parameters overview

The root Bicep template exposes parameters for the major areas below.

### Core deployment identity

- `location`
- `environmentName`
- `appName`
- `tags`

### Container image and registry

- `containerRegistryName`
- `imageTag`

### Container Apps runtime

- `containerAppsEnvironmentName`
- `containerAppName`
- `containerCpu`
- `containerMemory`
- `minReplicas`
- `maxReplicas`
- `externalIngressEnabled`
- `targetPort`
- `mcpHttpPath`

### PostgreSQL

- `postgresServerName`
- `postgresDatabaseName`
- `postgresAdminLogin`
- `postgresAdminPassword`
- `postgresVersion`
- `postgresSkuName`
- `postgresStorageSizeGB`
- `postgresHighAvailabilityEnabled`

### Application runtime configuration

- `enableDebugEndpoints`
- `logLevel`
- `logStructured`
- `dbConnectTimeoutSeconds`
- `dbStatementTimeoutMs`
- `dbSchemaName`
- `dbPoolMinSize`
- `dbPoolMaxSize`
- `dbPoolTimeoutSeconds`
- `dbAgeEnabled`
- `dbAgeGraphName`

### Embeddings

- `embeddingEnabled`
- `embeddingProvider`
- `embeddingModel`
- `embeddingDimensions`
- `embeddingBaseUrl`
- `embeddingApiKey`
- `azureEmbeddingMode`
- `azureOpenAiApiVersion`
- `azureOpenAiEmbeddingDeploymentName`

### Azure OpenAI

- `azureOpenAiLocation`
- `azureOpenAiAccountName`
- `azureOpenAiCustomSubdomain`
- `azureOpenAiEmbeddingDeploymentName`
- `azureOpenAiEmbeddingModelName`
- `azureOpenAiEmbeddingModelVersion`
- `azureOpenAiSkuName`
- `azureOpenAiDeploymentCapacity`

### Identity

- `enableUserAssignedIdentity`
- `userAssignedIdentityResourceId`

---

## Current application configuration mapping

The Container App template currently maps Azure infrastructure inputs into the
runtime configuration expected by `ctxledger`.

Examples include:

- `CTXLEDGER_DATABASE_URL`
- `CTXLEDGER_TRANSPORT`
- `CTXLEDGER_ENABLE_HTTP`
- `CTXLEDGER_HOST`
- `CTXLEDGER_PORT`
- `CTXLEDGER_HTTP_PATH`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- `CTXLEDGER_LOG_LEVEL`
- `CTXLEDGER_LOG_STRUCTURED`
- `CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS`
- `CTXLEDGER_DB_STATEMENT_TIMEOUT_MS`
- `CTXLEDGER_DB_SCHEMA_NAME`
- `CTXLEDGER_DB_POOL_MIN_SIZE`
- `CTXLEDGER_DB_POOL_MAX_SIZE`
- `CTXLEDGER_DB_POOL_TIMEOUT_SECONDS`
- `CTXLEDGER_DB_AGE_ENABLED`
- `CTXLEDGER_DB_AGE_GRAPH_NAME`
- `CTXLEDGER_EMBEDDING_ENABLED`
- `CTXLEDGER_EMBEDDING_PROVIDER`
- `CTXLEDGER_EMBEDDING_MODEL`
- `CTXLEDGER_EMBEDDING_DIMENSIONS`
- `CTXLEDGER_EMBEDDING_BASE_URL`
- `CTXLEDGER_AZURE_EMBEDDING_MODE`
- `CTXLEDGER_AZURE_OPENAI_ENDPOINT`
- `CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- `CTXLEDGER_AZURE_OPENAI_API_VERSION`
- `CTXLEDGER_AZURE_OPENAI_AUTH_MODE`
- `CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY`

This makes the IaC easier to align with the application’s existing config
contract while keeping the Azure large pattern explicit about Azure OpenAI and
PostgreSQL `azure_ai` usage.

The large Azure path should also be read with one more important deployment
boundary in mind:

- local Docker engine use is a small-pattern concern
- large-pattern image build should happen remotely in Azure Container Registry
- the preferred implementation is the standard `azd` service-level
  `remoteBuild` flow defined in `azure.yaml`
- provisioning can therefore create a placeholder runtime shape first, and the
  real application image can be built remotely and supplied during the Azure
  deploy workflow

---

## Important cautions

## 1. This scaffold does not validate extension support for you

The large pattern depends on explicit validation of:

- `pgvector`
- `azure_ai`
- Apache AGE

It also depends on using the correct Azure OpenAI authentication mode for
PostgreSQL `azure_ai`:

- `subscription_key`
- `managed_identity`

The large Azure path should not be described or operated as using
`OPENAI_API_KEY`.

Provisioning PostgreSQL Flexible Server is not, by itself, proof that the target
environment satisfies those requirements.

You must explicitly validate:

- supported PostgreSQL version
- supported extension matrix
- environment-specific extension enablement procedure
- Azure OpenAI connectivity from PostgreSQL where `azure_ai` is in scope
- actual runtime compatibility with the deployed app

## 2. Schema/bootstrap remains explicit, but `azure_ai` bootstrap is automated

The infrastructure scaffold creates the database resource, but it does not mean
the full application schema is initialized automatically.

The current direction distinguishes between two bootstrap classes:

### Automated by infrastructure
- PostgreSQL extension allowlisting through `azure.extensions`
- provisioning the deployment-script execution dependencies needed for bootstrap
- waiting for PostgreSQL readiness after deployment
- creating required extensions in the target database
- writing PostgreSQL `azure_ai` settings for Azure OpenAI endpoint and
  credential material
- optional validation of `azure_openai.create_embeddings(...)`
- applying the bundled `ctxledger` schema automatically
- verifying representative schema objects after schema bootstrap

### Still explicit deployment or operator concerns
- migrations or bootstrap logic beyond the bundled baseline schema
- higher-level data initialization
- any future bootstrap logic not yet encoded into the infrastructure deployment

This keeps both `azure_ai` bootstrap and baseline schema bootstrap automatic
while preserving the broader rule that not every future schema or migration
concern should be hidden inside ordinary app startup.

It also supports the large-pattern goal that a normal environment can be created
through a self-contained `azd up` flow instead of depending on external
pre-created bootstrap resources.

## 3. The current firewall posture is intentionally simple

Allowing Azure services to reach PostgreSQL is a practical bootstrap choice for
the scaffold.

It is not necessarily the final recommended production posture.

Future hardening may require:

- private networking
- narrowed network rules
- private DNS
- environment isolation by network boundary

## 4. Debug endpoints should stay bounded

The template exposes `enableDebugEndpoints`.

Do not enable debug endpoints casually in broader-exposure environments.

If enabled, they should remain behind the intended auth boundary and be treated
as operationally sensitive.

## 5. Traefik assumptions do not carry forward automatically

The local `small` pattern uses Traefik because it fits Docker Compose well.

This infrastructure scaffold does **not** assume Traefik is the permanent Azure
edge.

Container Apps ingress can expose the service, but the broader ingress/auth
gateway decision should still be evaluated deliberately.

## 6. Azure OpenAI posture must be reviewed together with PostgreSQL `azure_ai`

The large pattern should not be accepted as merely “Azure-hosted with optional
AI wiring.”

Instead, operators should review together:

- the Azure OpenAI account and deployment
- the application-side Azure OpenAI posture
- the PostgreSQL-side `azure_ai` posture
- vector dimension alignment
- whether the preferred embedding mode is:
  - PostgreSQL-native via `azure_openai.create_embeddings(...)`
  - application-side Azure OpenAI calls
  - a bounded hybrid mode

The intended default large-pattern direction is to maximize PostgreSQL-native
Azure AI usage where practical.

---

## Example deployment flow

A typical operator flow using this directory should look like:

1. choose or create the target resource group
2. choose the parameter profile that matches the target environment:
   - `main.dev.bicepparam`
   - `main.staging.bicepparam`
   - `main.prod.bicepparam`
3. review only the environment-specific differences that actually need changing
4. validate the Bicep template
5. run `azd up` as the primary happy-path deployment command
6. confirm that the image build path is using the standard `azd` remoteBuild
   workflow with Azure Container Registry rather than a local Docker engine
7. verify ACR, ACA, PostgreSQL, Azure OpenAI, and bootstrap execution
   dependencies exist as expected
8. confirm the automated PostgreSQL bootstrap completed successfully:
   - extension allowlisting applied
   - PostgreSQL became reachable
   - `azure_ai` configuration ran
   - embedding validation passed if enabled
   - the bundled `ctxledger` schema was applied
   - representative schema objects were verified
9. confirm the automatic post-deploy smoke test completed successfully against
   the deployed MCP endpoint
10. validate the intended embedding path
11. record deployment evidence

For the intended happy path, those steps should be reachable from a
self-contained `azd up` workflow without separate manual preparation of storage,
identity, bootstrap execution resources, manual schema application steps, or
extra first-run inputs beyond Azure subscription and location selection.

After deployment completes, the workflow should also run an automatic
post-deploy smoke test against the deployed MCP endpoint before printing
ready-to-copy MCP client configuration snippets. The preferred smoke posture is
an MCP `initialize` probe followed by `tools/list` and `resources/list`, so the
deployment validates not only HTTPS reachability but also basic protocol-level
MCP responsiveness, a representative tool capability query, and a representative
resource capability query. This reduces the remaining user task further to
copying the appropriate client settings into their AI agent or MCP client.

In addition to printing snippets to the terminal, the workflow should write
snippet artifacts to a predictable local directory such as:

- `.azure/mcp-snippets/`

That directory should contain:

- representative client configuration files
- a small summary file
- a rendered `README.md` artifact that explains the generated files and shows
  copy-friendly client examples

Those generated client artifacts should also support auth-aware rendering so the
snippet outputs can remain aligned with the current large-pattern auth posture,
including:

- no auth headers
- standard bearer `Authorization` headers
- custom header names for future gateway-specific handoff

They should also preserve post-deploy smoke result metadata so the handoff files
record not only what to copy into the MCP client, but also the basic validation
result that was observed during deployment, including:

- smoke status
- smoke probe mode
- smoke protocol version
- smoke follow-up probes
- smoke body preview
- deployment timestamp
- application version

For the Azure large pattern, these artifacts should also preserve the Azure
OpenAI authentication posture used by the deployment:

- `managed_identity`
- `subscription_key`

They should not imply that `OPENAI_API_KEY` is part of the large-pattern
infrastructure contract.

The generated `summary.json` should be read as lightweight release evidence for
the MCP handoff path.
A practical reading of its structure is:

- `schemaVersion`
  - version of the handoff-summary structure
- `evidenceType`
  - identifies the file as MCP handoff evidence
- `artifacts`
  - generated file locations, including the preferred README artifact
- `environment`
  - Azure environment name, location, and environment type
- `auth`
  - auth mode, auth header name when relevant, and whether a concrete credential
    was embedded
- `smoke`
  - postdeploy validation result, including probe mode and follow-up probes
- `deployment`
  - deployment timestamp and application version
- `recommendedUsage`
  - concise hints telling the user which artifact to open first and how to read
    the auth/environment posture

The generated `README.md` should be read as the primary human-facing handoff
surface.
A practical reading of the pair is:

- `README.md`
  - first document to open after deployment
  - copy/paste-oriented guidance for representative MCP clients
  - human-readable explanation of auth and environment posture
- `summary.json`
  - structured handoff evidence
  - operator/release traceability record
  - easier input for later automation or audit-style review

This allows the user to reopen or copy the snippets later without rerunning the
deployment.
The generated handoff artifacts should also make the preferred copy/paste path
obvious by preserving:

- a preferred artifact hint pointing to the rendered README
- auth-aware usage hints
- environment-aware usage hints
- smoke body preview
- deployment timestamp

This allows the user to reopen or copy the snippets later without rerunning the
deployment.

This ordering matters because infrastructure success alone is not enough for
application acceptance, and the automated PostgreSQL bootstrap must also be
verified as part of the deployment result.

---

## Suggested environment-specific files

As this directory evolves, prefer keeping environment-specific parameter files
separate, for example:

- `main.dev.bicepparam`
- `main.staging.bicepparam`
- `main.prod.bicepparam`

Current intended reading of those files:

- `main.dev.bicepparam`
  - minimal shared-development baseline
  - checked-in MCP handoff auth defaults:
    - `mcpAuthMode=none`
    - `mcpAuthHeaderName=Authorization`
  - checked-in Azure OpenAI auth default:
    - `azureOpenAiAuthMode=auto`
- `main.staging.bicepparam`
  - preproduction validation and release-candidate baseline
  - checked-in MCP handoff auth defaults:
    - `mcpAuthMode=bearer_header`
    - `mcpAuthHeaderName=Authorization`
  - checked-in Azure OpenAI auth default:
    - `azureOpenAiAuthMode=auto`
- `main.prod.bicepparam`
  - production-oriented sizing and availability baseline
  - checked-in MCP handoff auth defaults:
    - `mcpAuthMode=custom_header`
    - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
  - checked-in Azure OpenAI auth default:
    - `azureOpenAiAuthMode=auto`
    - `mcpAuthHeaderName=X-Forwarded-Access-Token`

That keeps:

- naming
- sizing
- secrets handling
- scaling choices
- HA posture
- environment intent

explicit per environment.

Do not rely on one mutable parameter file for every environment.

---

## Security guidance

Use the scaffold with these minimum security rules:

- do not hardcode real secrets in committed parameter files
- do not enable ACR admin user just for convenience
- do not enable anonymous image pull
- prefer managed identity where practical
- treat database admin credentials as sensitive
- treat Azure OpenAI credential material as sensitive
- treat PostgreSQL `azure_ai` secret-backed settings as sensitive
- treat debug surfaces as sensitive
- review public ingress exposure deliberately

If you need stronger secret handling, move toward:

- secure deployment-time parameters
- secret references
- managed secret stores
- stricter network boundaries
- reduced dependence on key-based Azure OpenAI access where identity-based options become viable

---

## Observability guidance

The current scaffold wires Container Apps environment logs to Log Analytics.

That provides a baseline only.

You should still define:

- what logs operators must inspect
- what deployment evidence is recorded
- what health signals determine readiness
- whether Grafana remains part of the accepted large pattern
- whether Azure-native monitoring becomes the primary baseline

Do not assume observability is complete only because Log Analytics exists.

---

## Known limitations of the current scaffold

At the time this scaffold was introduced, the main known limitations include:

- no Key Vault integration yet
- no VNet/private endpoint design yet
- no schema application job resource
- no finalized auth gateway pattern
- no finalized custom domain/TLS certificate posture
- no finalized Azure OpenAI credential hardening pattern yet
- no staging/prod parameter files yet
- no production-tuned sizing guidance yet

These are expected follow-up items.

---

## Recommended next steps

The most natural next improvements in this directory are:

1. add environment-specific parameter files beyond `dev`
2. add a dedicated config specification document for the Azure large pattern
3. add Key Vault integration
4. add private networking options
5. strengthen the automated PostgreSQL bootstrap and schema bootstrap path with
   tighter secret and network posture
6. reduce remaining deployment-time prerequisites so the `azd up` happy path
   stays as self-contained as possible
7. continue refining the checked-in environment parameter profiles as real
   deployment evidence accumulates
8. add validation guidance for `pgvector`, `azure_ai`, Azure OpenAI, and Apache AGE
9. add deployment command examples once the delivery workflow is finalized

---

## Summary

This `infra/` directory establishes the initial Bicep-based infrastructure
scaffold for the `ctxledger` Azure large deployment pattern.

It gives the project a concrete starting point for:

- Azure Container Registry
- Azure Container Apps
- Azure Database for PostgreSQL Flexible Server
- Azure OpenAI
- baseline Azure logging integration
- PostgreSQL-native Azure AI integration planning
- an `azd up`-oriented one-command deployment target

It is intentionally bounded.

Use it as:

- a reproducible starting point
- a bridge between planning docs and implementation
- a place to evolve Azure deployment posture carefully
- the foundation for a self-contained deployment experience where first run
  ideally requires only Azure subscription and location selection, the deployed
  MCP endpoint is surfaced automatically, an automatic post-deploy smoke test
  verifies basic endpoint reachability with an MCP `initialize` probe followed by
  `tools/list` and `resources/list`, and the terminal output is handoff-first:
  - first point the user at the deployed MCP endpoint
  - then point the user at the generated snippet README and snippet directory
  - then summarize the current environment/auth context
  - keep the README and generated artifacts as the primary handoff surface
- ready-to-copy MCP client snippets are also written to local auth-aware snippet
  artifacts with richer summary metadata, persisted smoke result metadata
  including smoke body preview, deployment timestamp, and application version,
  plus a rendered `README.md`, so the main remaining user task after rollout is
  MCP client configuration
- in other words, the intended release-evidence and handoff posture is:
  - `README.md` first for humans
  - `summary.json` first for structured traceability
  - raw client snippet files for direct copy/paste
- and the intended build posture is:
  - `azure.yaml` drives the standard `azd` remoteBuild flow
  - Azure Container Registry performs the image build
  - the large pattern does not depend on the local Docker engine for the normal
    Azure deployment path
  - ACR remote build outputs and image references as part of deployment evidence

Do not use it to over-claim that all production architecture decisions are
already closed.