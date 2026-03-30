# Azure Large Deployment Configuration Specification

## 1. Purpose

This document defines the runtime configuration contract for the **Azure large deployment pattern** of `ctxledger`.

It is intended to answer these questions clearly:

1. Which configuration values must be supplied for the Azure large pattern?
2. Which values are required versus optional?
3. Which values are environment-specific?
4. Which values are secrets?
5. Which values are application-owned versus infrastructure-owned?
6. Which values should be validated before the Azure deployment is accepted?

This specification should be read together with:

- `docs/operations/deployment/deployment.md`
- `docs/operations/runbooks/azure_large_operator_runbook.md`
- `docs/project/releases/plans/versioned/large_deployment_pattern_1_0_0_plan.md`
- `docs/project/releases/plans/versioned/1.0.0_large_deployment_acceptance_checklist.md`
- `infra/README.md`

This document is intentionally focused on the **large Azure pattern**.
It does not redefine the local `small` pattern.

A critical design boundary for the Azure large pattern is that it must distinguish clearly between:

- **persistence-oriented AI work**
- **interactive AI work**

Persistence-oriented AI work is the class of processing where:

- the input already exists in PostgreSQL
- the model output is used to create or update durable stored state
- the result is written into:
  - a table
  - a column
  - an embedding store
  - another derived retrieval-support structure

Interactive AI work is different.
It is the class of processing where:

- the model result is primarily needed so it can be returned directly to the MCP client
- the database is not being used as the main materialization target
- the primary value is immediate request/response behavior rather than durable derived state

This distinction matters for Azure large deployments because PostgreSQL-side `azure_ai` is a strong fit for the first class, but not the default fit for the second.

---

## 2. Scope

This specification covers:

- application runtime environment variables
- Azure deployment-specific configuration expectations
- secret classification
- required versus optional values
- validation rules
- recommended environment ownership boundaries

This specification does **not** attempt to fully define:

- the final Azure ingress or auth gateway product choice
- the final Key Vault integration model
- the final CI/CD implementation
- the final multi-environment release process
- every possible future config value that may be introduced later

However, this specification now assumes four important automation requirements are part of the large-pattern baseline:

- PostgreSQL extension allowlisting must be configured during infrastructure deployment
- `azure_ai` bootstrap must run automatically after deployment
- schema bootstrap must also run automatically after the PostgreSQL AI/bootstrap phase
- the bootstrap path must wait until PostgreSQL accepts connections
- once the server is reachable, the bootstrap path must execute the required SQL to:
  - create required extensions
  - configure Azure OpenAI settings for `azure_ai`
  - optionally validate direct embedding generation
  - apply the bundled `ctxledger` schema
  - verify representative schema objects
- the Azure large pattern should target a one-command deployment experience through `azd up`
- the deployment should be as self-contained as practical, without relying on user-created support resources just to complete the normal happy path
- for the normal first-run experience, the only intended user inputs should be:
  - Azure subscription selection
  - Azure location selection
- the large deployment path should avoid local Docker-engine builds and instead use Azure Container Registry remote build as the normal image-build path
- after deployment, an automatic postdeploy smoke test should validate that the deployed MCP endpoint is reachable and behaving in an expected bounded way
- the preferred smoke-test shape should be an MCP `initialize` probe followed by `tools/list` and `resources/list`, rather than only a generic HTTP reachability check
- after `azd up` completes successfully, the ideal remaining user to-do should be only:
  - configuring the AI agent / MCP client to use the deployed MCP endpoint
- the deployment workflow should also write MCP client snippet artifacts to disk so users can copy ready-made client configuration files instead of reconstructing them manually
- the deployment workflow should support auth-aware MCP snippet generation, so generated snippets can reflect:
  - no auth headers
  - standard bearer `Authorization` headers
  - custom header names for future large-pattern gateway alignment
- the deployment workflow should also render a small README artifact alongside those snippet files so users can understand what was generated and how to use it later
- the deployment workflow should support environment-specific auth handoff profiles so generated MCP snippets can stay aligned with:
  - development environments that currently expose no client auth header requirement
  - staging environments that prefer bearer-style header handoff
  - production-oriented environments that may require a gateway-specific custom header
- the generated MCP snippet summary metadata should also capture useful deployment context so users can understand the handoff artifacts later, including:
  - Azure environment name
  - Azure location
  - Azure environment type
  - auth mode
  - auth header interpretation
  - postdeploy smoke status
  - postdeploy smoke probe mode
  - postdeploy smoke protocol version
  - postdeploy smoke follow-up probes
  - postdeploy smoke body preview
  - deployment timestamp
  - application version

The goal is a bounded, explicit contract for the `1.0.0` large deployment direction.
- the generated MCP snippet summary metadata should use a release-evidence-oriented structure that keeps:
  - artifact paths together
  - environment context together
  - auth context together
  - smoke-validation context together
  - deployment metadata together
  - recommended usage guidance together

This specification also assumes an explicit AI execution boundary:

- persistence-oriented AI work should be modeled as configuration for durable materialization or retrieval-support behavior
- interactive AI work should not be forced into the same contract when its primary purpose is direct MCP response generation

This means the large Azure configuration contract should make it clear not only **which provider and auth mode are used**, but also **why a given execution path exists**:

- PostgreSQL-side `azure_ai`
  - for persistence-oriented and retrieval-support work
- application-side Azure OpenAI
  - for interactive direct-response work when such a feature is intentionally implemented

The goal is a bounded, explicit contract for the `1.0.0` large deployment direction.

---

## 3. Configuration Design Principles

The Azure large pattern should follow these configuration principles.

### 3.1 Keep configuration explicit

The cloud deployment should not depend on implicit local defaults that are only obvious from Docker Compose.

Operators should be able to answer:

- what value is set
- why it is set
- which environment owns it
- whether it is secret
- whether it is safe to change

### 3.2 Separate application config from infrastructure config

Some values belong primarily to the application runtime, such as:

- log level
- MCP HTTP path
- pool sizing
- embedding provider

Other values belong primarily to the infrastructure layer, such as:

- registry name
- resource names
- PostgreSQL server name
- ingress exposure mode
- PostgreSQL extension allowlisting through the `azure.extensions` server parameter
- post-deploy bootstrap execution for `azure_ai`
- deployment support resources required to make `azd up` self-contained, such as:
  - deployment script execution storage
  - managed identity resources needed by the deployment flow

Those concerns should be kept conceptually separate even when the infrastructure injects the final runtime values.

A practical implication for the large Azure pattern is:

- extension allowlisting belongs to infrastructure deployment
- bootstrap timing and execution belong to deployment automation
- application runtime config should assume the bootstrap step has already prepared the database successfully
- support resources required by the deployment flow should be provisioned by the same infrastructure when practical, instead of being pushed onto the user as manual prerequisites
- the end-to-end deployment workflow should be designed so `azd up` can complete the infrastructure, bootstrap, remote image build, and application rollout without requiring extra manual setup steps
- in the intended first-run happy path, users should not be asked to provide deployment inputs beyond subscription and location selection
- for the large Azure pattern, remote image build should follow the standard `azd` service-level Docker remoteBuild flow against Azure Container Registry rather than depending on a custom local Docker build step

### 3.3 Treat secrets differently from ordinary settings

Secrets must not be handled like ordinary configuration values.

In the large Azure pattern:

- secrets should not be committed to source control
- secrets should not be hardcoded in image layers
- secrets should not be copied casually into operator notes
- secret rotation should be possible without redefining the application contract

### 3.4 Preserve architecture boundaries

Configuration should not drift the architecture away from its current intended shape.

This means:

- `ctxledger` remains the backend application
- ingress and authentication remain outside the application core
- PostgreSQL remains canonical
- graph support remains bounded and non-canonical
- the MCP endpoint remains HTTP-oriented at `/mcp`

---

## 4. Configuration Surfaces

The Azure large deployment pattern involves multiple configuration surfaces.

## 4.1 Infrastructure-level configuration

Infrastructure-level configuration includes values such as:

- Azure region
- resource names
- resource SKUs
- scaling bounds
- ingress exposure settings
- registry/image source references
- PostgreSQL extension allowlist values
- deployment-script inputs used for automated database bootstrap

These values are typically expressed in Infrastructure as Code and deployment parameters.

## 4.2 Application runtime configuration

Application runtime configuration includes values such as:

- database URL
- HTTP host and port
- log settings
- debug endpoint enablement
- connection pool settings
- AGE feature toggle
- embedding settings

These values are ultimately injected into the application runtime environment.

For the large Azure pattern, runtime configuration should be read together with the automated bootstrap contract:

- the app should not be expected to allowlist PostgreSQL extensions itself
- the app should not be expected to perform first-time `azure_ai` bootstrap during normal startup
- the app should not be expected to apply the bundled schema during normal startup
- the app can assume the deployment process has already prepared the PostgreSQL environment, including schema bootstrap, if the deployment is accepted as healthy

This runtime configuration surface should also preserve the persistence / interactive AI boundary:

- settings that enable PostgreSQL-side `azure_ai` should be read as persistence-oriented or retrieval-support configuration
- settings that would enable direct application-side Azure OpenAI execution should be read as interactive-path or app-generated-path configuration
- these two classes can share the same Azure OpenAI deployment identity, but they should not be conflated into one undifferentiated “AI config” concept

## 4.3 Secret configuration

Secret configuration includes values such as:

- PostgreSQL administrator password
- application database connection secret material
- embedding provider API keys
- future auth or gateway secrets

These values should be sourced through secure Azure-appropriate secret handling rather than committed plaintext configuration.

---

## 5. Configuration Ownership Model

The following ownership model is recommended.

### 5.1 Infrastructure-owned values

Typically infrastructure-owned:

- Azure resource names
- Azure region
- image reference
- external ingress enablement
- min/max replicas
- container CPU and memory
- PostgreSQL SKU/version/storage
- HA enablement
- identity resource references

### 5.2 Application-owned values

Typically application-owned:

- `CTXLEDGER_HTTP_PATH`
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- `CTXLEDGER_LOG_LEVEL`
- `CTXLEDGER_LOG_STRUCTURED`
- `CTXLEDGER_DB_SCHEMA_NAME`
- `CTXLEDGER_DB_POOL_MIN_SIZE`
- `CTXLEDGER_DB_POOL_MAX_SIZE`
- `CTXLEDGER_DB_POOL_TIMEOUT_SECONDS`
- `CTXLEDGER_DB_AGE_ENABLED`
- `CTXLEDGER_DB_AGE_GRAPH_NAME`
- Azure OpenAI provider selection behavior
- Azure OpenAI deployment naming expectations
- PostgreSQL `azure_ai` / `azure_openai` extension usage posture

### 5.3 Shared values

Some values are effectively shared between infrastructure and application concerns, for example:

- `CTXLEDGER_PORT`
- `CTXLEDGER_DATABASE_URL`
- replica count versus connection pool sizing
- debug endpoint exposure versus health probe design
- Azure OpenAI resource endpoint and deployment naming
- PostgreSQL `azure_ai` extension settings written into the database
- the deployment-time sequence that:
  - allowlists extensions
  - waits for PostgreSQL connectivity
  - executes bootstrap SQL

These must be reviewed jointly because a change on one side can invalidate assumptions on the other.

---

## 6. Configuration Classes

Every config item in the large Azure pattern should be classified into one of the following.

### 6.1 Required

The deployment is not acceptable without the value.

### 6.2 Conditionally required

The value is required only if a corresponding feature or mode is enabled.

### 6.3 Optional

The deployment may omit the value safely and rely on a bounded default.

### 6.4 Secret

The value must be handled as sensitive material.

### 6.5 Environment-specific

The value is expected to differ between `dev`, `staging`, and `production-like` environments.

---

## 7. Runtime Configuration Table

This section defines the expected runtime environment variables for the Azure large pattern.

## 7.1 Core application identity and environment

### `CTXLEDGER_APP_NAME`
- purpose:
  - application name surfaced in runtime metadata
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- recommended large-pattern value:
  - `ctxledger`

### `CTXLEDGER_APP_VERSION`
- purpose:
  - release/runtime version label
- required:
  - strongly recommended
- secret:
  - no
- environment-specific:
  - yes, by release
- notes:
  - should align with the deployed image/release version

### `CTXLEDGER_ENV`
- purpose:
  - environment label used by the application
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- recommended values:
  - `dev`
  - `staging`
  - `prod`
  - another explicit environment label approved by the deployment model

---

## 7.2 Database configuration

### `CTXLEDGER_DATABASE_URL`
- purpose:
  - canonical PostgreSQL connection string for the application
- required:
  - yes
- secret:
  - yes
- environment-specific:
  - yes
- validation:
  - must point to the intended Azure Database for PostgreSQL Flexible Server instance
  - must specify the intended database
  - should require SSL/TLS in Azure
- notes:
  - this is one of the most critical runtime settings
  - the large pattern should not run without it
  - in the Azure large pattern, this database is expected to host:
    - `pgvector`
    - Apache AGE if accepted for the environment
    - the `azure_ai` extension configuration used for direct Azure OpenAI calls from PostgreSQL

### `CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS`
- purpose:
  - connection timeout applied when opening PostgreSQL connections
- required:
  - yes
- secret:
  - no
- environment-specific:
  - possibly
- validation:
  - must be greater than `0`
- recommended starting value:
  - `5`

### `CTXLEDGER_DB_STATEMENT_TIMEOUT_MS`
- purpose:
  - optional PostgreSQL statement timeout bound
- required:
  - no
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - when provided, must be greater than `0`
- notes:
  - omit if no timeout is desired
  - do not set casually without understanding MCP workload behavior

### `CTXLEDGER_DB_SCHEMA_NAME`
- purpose:
  - schema name used by the application
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- default:
  - `public`
- validation:
  - must not be empty

### `CTXLEDGER_DB_POOL_MIN_SIZE`
- purpose:
  - minimum PostgreSQL connection pool size per application replica
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be greater than or equal to `0`

### `CTXLEDGER_DB_POOL_MAX_SIZE`
- purpose:
  - maximum PostgreSQL connection pool size per application replica
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be greater than `0`
  - must be greater than or equal to `CTXLEDGER_DB_POOL_MIN_SIZE`
- operational caution:
  - this value must be reviewed together with:
    - `minReplicas`
    - `maxReplicas`
    - revision overlap expectations
    - PostgreSQL connection capacity

### `CTXLEDGER_DB_POOL_TIMEOUT_SECONDS`
- purpose:
  - timeout for waiting on a pooled PostgreSQL connection
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be greater than `0`

### `CTXLEDGER_DB_AGE_ENABLED`
- purpose:
  - enables the application-side AGE support path
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be boolean
- operational caution:
  - setting this to `true` is not enough by itself
  - the target Azure PostgreSQL configuration must actually support the intended AGE posture

### `CTXLEDGER_DB_AGE_GRAPH_NAME`
- purpose:
  - graph name used by AGE-related logic
- required:
  - yes if `CTXLEDGER_DB_AGE_ENABLED=true`
- secret:
  - no
- environment-specific:
  - usually no
- recommended value:
  - `ctxledger_memory`
- validation:
  - must not be empty when AGE is enabled

---

## 7.3 HTTP and MCP runtime configuration

### `CTXLEDGER_TRANSPORT`
- purpose:
  - declares the application transport mode
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- expected value for Azure large pattern:
  - `http`

### `CTXLEDGER_ENABLE_HTTP`
- purpose:
  - enables the HTTP runtime path
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- expected value for Azure large pattern:
  - `true`

### `CTXLEDGER_HOST`
- purpose:
  - host/interface binding inside the container
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- expected value for Azure large pattern:
  - `0.0.0.0`
- validation:
  - must not be empty

### `CTXLEDGER_PORT`
- purpose:
  - container listening port
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- expected Azure large-pattern value:
  - `8080`
- validation:
  - must be between `1` and `65535`
- operational caution:
  - must match the Container Apps target port

### `CTXLEDGER_HTTP_PATH`
- purpose:
  - MCP HTTP endpoint path
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- expected value:
  - `/mcp`
- validation:
  - must not be empty
- architectural note:
  - changing this affects MCP client compatibility and deployment docs

---

## 7.4 Debug and logging configuration

### `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS`
- purpose:
  - enables or disables `/debug/*` runtime surfaces
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- expected large-pattern posture:
  - default to `false` unless there is a clear operational need
- validation:
  - must be boolean
- operational caution:
  - if enabled, debug endpoints must remain behind the intended auth boundary

### `CTXLEDGER_LOG_LEVEL`
- purpose:
  - controls application log verbosity
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `debug`
  - `info`
  - `warning`
  - `error`
  - `critical`

### `CTXLEDGER_LOG_STRUCTURED`
- purpose:
  - enables structured logging output
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- recommended large-pattern value:
  - `true`
- validation:
  - must be boolean

---

## 7.5 Embedding configuration

For the Azure large pattern, the intended default posture is:

- do not use direct OpenAI API access
- prefer Azure OpenAI for embedding generation
- maximize use of PostgreSQL-side embedding generation through the `azure_ai` extension where the workflow allows it
- treat direct application-side embedding calls as secondary to the PostgreSQL-integrated Azure OpenAI path unless a specific feature requires app-side calls

This section should be read through the execution-boundary distinction:

- **persistence-oriented / retrieval-support embedding work**
  - examples:
    - generating embeddings for stored memory items
    - generating embeddings used to support semantic retrieval over stored records
    - creating AI-derived values that are written into tables or columns
  - preferred large-pattern fit:
    - PostgreSQL-side `azure_ai`
- **interactive AI work**
  - examples:
    - calling a model and returning the result directly to the MCP client as the primary output
  - preferred fit:
    - application-side Azure OpenAI
  - not the default target for PostgreSQL-side `azure_ai`

### `CTXLEDGER_EMBEDDING_ENABLED`
- purpose:
  - enables embedding-backed functionality
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be boolean

### `CTXLEDGER_EMBEDDING_PROVIDER`
- purpose:
  - selects the app-side embedding backend when the execution path is application-generated
- required:
  - yes when embedding is enabled and the execution path is app-generated
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `disabled`
  - `local_stub`
  - `openai`
  - `voyageai`
  - `cohere`
  - `custom_http`
- recommended Azure large-pattern posture:
  - choose explicitly
  - do not rely on accidental local defaults
  - for the Azure large pattern, prefer an Azure OpenAI-compatible provider path rather than direct public OpenAI usage
- operational note:
  - the current application config contract still exposes legacy provider names, but Azure large deployments should be documented and operated as Azure OpenAI-first
  - when the large pattern uses PostgreSQL-side `azure_ai`, do not model the environment as depending on `OPENAI_API_KEY`
  - if an application-side Azure OpenAI call path is ever enabled intentionally in the large pattern, use Azure-specific configuration such as:
    - `CTXLEDGER_AZURE_OPENAI_ENDPOINT`
    - `CTXLEDGER_AZURE_OPENAI_AUTH_MODE`
    - `CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY`
  - do not document or operate the Azure large pattern as if a public OpenAI API key were the normal credential shape
  - this provider setting should not be read as the main switch for PostgreSQL-side `azure_ai` execution; that belongs to the execution-mode and Azure-specific settings

### `CTXLEDGER_EMBEDDING_MODEL`
- purpose:
  - embedding model identifier
- required:
  - yes when embedding is enabled
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must not be empty when embedding is enabled
- Azure large-pattern note:
  - this should align with the Azure OpenAI embedding deployment model family

### `CTXLEDGER_EMBEDDING_DIMENSIONS`
- purpose:
  - embedding vector size
- required:
  - yes when embedding is enabled
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be greater than `0`
- Azure large-pattern note:
  - dimensions must remain consistent with the selected Azure OpenAI embeddings deployment and with any PostgreSQL-side vector column definitions

### `CTXLEDGER_EMBEDDING_BASE_URL`
- purpose:
  - base URL for app-generated `custom_http` embedding providers
- required:
  - yes when `CTXLEDGER_EMBEDDING_PROVIDER=custom_http` and `CTXLEDGER_EMBEDDING_EXECUTION_MODE=app_generated`
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be a valid absolute URL when provided
- Azure large-pattern note:
  - if the application performs direct Azure OpenAI-compatible calls, this value should point to the Azure OpenAI endpoint rather than a public OpenAI endpoint
  - this is not the normal PostgreSQL-side `azure_ai` setting path

### `OPENAI_API_KEY`
- purpose:
  - legacy application-side external API credential hook for non-large or explicitly app-generated embedding paths
- required:
  - no for the Azure large pattern
- secret:
  - yes
- environment-specific:
  - yes
- operational note:
  - the Azure large pattern should not depend on `OPENAI_API_KEY`
  - large deployments should instead use Azure-specific configuration such as:
    - `CTXLEDGER_AZURE_OPENAI_ENDPOINT`
    - `CTXLEDGER_AZURE_OPENAI_AUTH_MODE`
    - `CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY`
  - if the large pattern uses PostgreSQL-side `azure_ai`, `OPENAI_API_KEY` is not part of the intended configuration contract
  - if a future large-pattern application-side Azure OpenAI path is enabled intentionally, keep it Azure-specific rather than documenting it as a public OpenAI-first integration
- validation:
  - not part of the required Azure large-pattern credential contract

### `CTXLEDGER_AZURE_OPENAI_ENDPOINT`
- purpose:
  - Azure OpenAI endpoint used by the Azure large deployment when direct application-side Azure OpenAI calls are enabled
- required:
  - conditionally required
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be a valid absolute HTTPS URL when provided
- notes:
  - this value is strongly recommended for Azure large deployments even if PostgreSQL-side embedding generation is primary, because it keeps the endpoint contract explicit
  - this should reference the Azure OpenAI resource endpoint, not a public OpenAI endpoint

### `CTXLEDGER_AZURE_OPENAI_AUTH_MODE`
- purpose:
  - selects how Azure OpenAI authentication is configured for the Azure large deployment
- required:
  - yes when Azure OpenAI-backed execution is enabled
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `auto`
  - `subscription_key`
  - `managed_identity`
- recommended value:
  - `auto`
- notes:
  - `auto` should be treated as the preferred large-pattern posture
  - the intended behavior of `auto` is:
    - prefer `managed_identity`
    - fall back to `subscription_key` only when explicitly necessary and when the required key material is available
  - this value should be shared by:
    - PostgreSQL-side `azure_ai` bootstrap
    - any Azure-specific application-side OpenAI path that is intentionally enabled
  - do not treat `subscription_key` as the default large-pattern happy path unless the environment requires it

### `CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY`
- purpose:
  - Azure OpenAI subscription key used only when the selected auth mode is `subscription_key`
- required:
  - yes when `CTXLEDGER_AZURE_OPENAI_AUTH_MODE=subscription_key`
- secret:
  - yes
- environment-specific:
  - yes
- validation:
  - must not be set when `CTXLEDGER_AZURE_OPENAI_AUTH_MODE=managed_identity`
- notes:
  - this is part of the Azure-specific large-pattern contract
  - it is not a substitute for `managed_identity`
  - it should not be described as the default credential path for large environments

### `CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- purpose:
  - Azure OpenAI deployment name used for embeddings
- required:
  - yes when Azure OpenAI-backed embeddings are enabled
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must not be empty when Azure OpenAI-backed embeddings are enabled
- notes:
  - this should match the deployment name configured in Azure OpenAI and in PostgreSQL `azure_ai` settings where PostgreSQL-side embedding generation is used

### `CTXLEDGER_AZURE_OPENAI_API_VERSION`
- purpose:
  - explicit API version for Azure OpenAI direct calls when the application makes Azure OpenAI requests itself
- required:
  - recommended
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must not be empty when provided
- notes:
  - keep this explicit rather than relying on hidden SDK defaults in production-like environments

### `CTXLEDGER_AZURE_EMBEDDING_MODE`
- purpose:
  - declares whether Azure embeddings are expected to be generated primarily in the application or primarily inside PostgreSQL
- required:
  - strongly recommended
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `postgres_azure_ai`
  - `application_azure_openai`
  - `disabled`
- recommended large-pattern value:
  - `postgres_azure_ai`
- notes:
  - for the Azure large pattern, `postgres_azure_ai` should be treated as the default and preferred mode
  - when this mode is active together with `CTXLEDGER_AZURE_OPENAI_AUTH_MODE=auto`, the expected large-pattern behavior is:
    - prefer PostgreSQL-side `managed_identity`
    - use `subscription_key` only as an explicit or environment-required fallback
  - this setting is best understood as the primary execution-boundary selector for persistence-oriented or retrieval-support embedding work
  - use `postgres_azure_ai` when:
    - embeddings are being materialized from stored records
    - semantic retrieval support should stay close to the persisted embedding store
  - use `application_azure_openai` when:
    - an intentionally application-side Azure OpenAI path is required
    - the work is better served by application-owned execution rather than database-side materialization
  - do not use this setting to imply that direct client-facing interactive AI responses should default to PostgreSQL-side `azure_ai`

---

## 8. Infrastructure Parameter Table

This section defines the main infrastructure parameters for the Azure large pattern as currently scaffolded.

## 8.1 Core deployment identity

### `location`
- purpose:
  - Azure region for deployed resources
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `environmentName`
- purpose:
  - short environment label used in naming and tagging
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- example values:
  - `dev`
  - `staging`
  - `prod`

### `appName`
- purpose:
  - base workload name used in naming
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- recommended value:
  - `ctxledger`

### `tags`
- purpose:
  - Azure resource tagging
- required:
  - strongly recommended
- secret:
  - no
- environment-specific:
  - yes

---

## 8.2 Registry and image parameters

### `containerRegistryName`
- purpose:
  - Azure Container Registry name
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be globally unique
  - must satisfy Azure naming rules

### `imageTag`
- purpose:
  - container image tag to deploy
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes by release/environment
- operational note:
  - should map cleanly to a release record

---

## 8.3 Container Apps parameters

### `containerAppsEnvironmentName`
- purpose:
  - Container Apps managed environment name
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `containerAppName`
- purpose:
  - application resource name in Azure Container Apps
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `containerCpu`
- purpose:
  - CPU allocation per replica
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `containerMemory`
- purpose:
  - memory allocation per replica
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `minReplicas`
- purpose:
  - minimum replica count
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be greater than or equal to `1`

### `maxReplicas`
- purpose:
  - maximum replica count
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- validation:
  - must be greater than or equal to `1`
  - should be greater than or equal to `minReplicas`

### `externalIngressEnabled`
- purpose:
  - enables client-facing ingress on the Container App
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- operational caution:
  - this affects the public exposure model and must be reviewed with the ingress/auth design

### `targetPort`
- purpose:
  - Container Apps ingress target port
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- validation:
  - must match `CTXLEDGER_PORT`

### `mcpHttpPath`
- purpose:
  - the MCP path the deployment expects the app to serve
- required:
  - yes
- secret:
  - no
- environment-specific:
  - usually no
- validation:
  - must match `CTXLEDGER_HTTP_PATH`

---

## 8.4 PostgreSQL infrastructure parameters

### `postgresServerName`
- purpose:
  - Azure PostgreSQL Flexible Server resource name
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `postgresDatabaseName`
- purpose:
  - application database name
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `postgresAdminLogin`
- purpose:
  - PostgreSQL administrator login
- required:
  - yes
- secret:
  - sensitive
- environment-specific:
  - yes

### `postgresAdminPassword`
- purpose:
  - PostgreSQL administrator password
- required:
  - yes
- secret:
  - yes
- environment-specific:
  - yes

### `postgresVersion`
- purpose:
  - PostgreSQL major version
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- operational caution:
  - must be chosen together with extension compatibility validation

### `postgresSkuName`
- purpose:
  - PostgreSQL compute SKU
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `postgresStorageSizeGB`
- purpose:
  - PostgreSQL storage allocation
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `postgresHighAvailabilityEnabled`
- purpose:
  - enables HA mode for Flexible Server
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `azureOpenAiDeploymentCapacity`
- purpose:
  - Azure OpenAI capacity units for the embedding deployment
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `postgresAllowedExtensions`
- purpose:
  - comma-separated allowlist written to the PostgreSQL Flexible Server `azure.extensions` server parameter
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- recommended large-pattern value:
  - a value that includes at least:
    - `vector`
    - `azure_ai`
    - `age` when AGE remains enabled for the environment
- notes:
  - this value should be applied during infrastructure deployment, before bootstrap SQL execution is attempted

### `bootstrapEnsureAge`
- purpose:
  - controls whether the automated bootstrap path attempts to create the `age` extension after connectivity is established
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- notes:
  - this should align with the accepted AGE posture of the environment

### `bootstrapWaitTimeoutSeconds`
- purpose:
  - maximum time the deployment bootstrap step waits for PostgreSQL to become reachable
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- notes:
  - this value bounds the automated wait-before-bootstrap sequence

### `bootstrapWaitIntervalSeconds`
- purpose:
  - polling interval used while waiting for PostgreSQL connectivity before bootstrap SQL runs
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `bootstrapValidateEmbeddings`
- purpose:
  - controls whether the automated bootstrap path validates direct Azure OpenAI embedding generation from PostgreSQL after configuring `azure_ai`
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes
- recommended large-pattern value:
  - `true`

### `deploymentScriptStorageAccountName`
- purpose:
  - storage account name used by the deployment automation that runs the PostgreSQL bootstrap step
- required:
  - yes when deployment scripts are used for bootstrap
- secret:
  - no
- environment-specific:
  - yes
- large-pattern note:
  - for the self-contained `azd up` target, this should normally be created by the same infrastructure deployment rather than requiring the user to prepare it separately

### `deploymentScriptStorageContainerName`
- purpose:
  - blob container name used by the deployment automation that runs the PostgreSQL bootstrap step
- required:
  - yes when deployment scripts are used for bootstrap
- secret:
  - no
- environment-specific:
  - yes
- large-pattern note:
  - this should be treated as an internal deployment implementation detail, not as a user-facing prerequisite in the normal happy path

### `userAssignedIdentityName`
- purpose:
  - name of the user-assigned managed identity created for deployment bootstrap and related operations
- required:
  - yes when the deployment flow uses a user-assigned identity
- secret:
  - no
- environment-specific:
  - yes
- large-pattern note:
  - for the self-contained `azd up` target, this should normally be created by the same infrastructure deployment rather than requiring the user to supply an existing identity

### `CTXLEDGER_MCP_SNIPPETS_DIR`
- purpose:
  - filesystem output directory where deployment automation writes ready-to-copy MCP client configuration snippet artifacts
- required:
  - recommended
- secret:
  - no
- environment-specific:
  - yes
- recommended value:
  - `.azure/mcp-snippets`
- large-pattern note:
  - this should be treated as a deployment output artifact location, not as a user-supplied first-run prerequisite
  - the deployment workflow should create this directory automatically before writing snippet files
  - this directory should also contain a small rendered README artifact that explains the generated files and gives copy-friendly guidance for representative MCP clients

### `AZURE_CONTAINER_REGISTRY_ENDPOINT`
- purpose:
  - Azure Container Registry login server used by the large deployment flow
- required:
  - yes for ACR remote build
- secret:
  - no
- environment-specific:
  - yes
- notes:
  - this value is expected to come from infrastructure outputs after provisioning
  - this is the standard environment variable shape consumed by the `azd` service-level Docker `remoteBuild: true` flow
  - the large deployment flow should use it to target Azure Container Registry remote build rather than relying on a local Docker engine

### `CONTAINER_IMAGE_REPOSITORY`
- purpose:
  - repository name used for the built application image in Azure Container Registry
- required:
  - yes for ACR remote build
- secret:
  - no
- environment-specific:
  - yes
- notes:
  - this value is expected to come from infrastructure outputs after provisioning
  - it should be combined with the chosen image tag during the remote-build phase

### `CONTAINER_IMAGE_REFERENCE`
- purpose:
  - fully qualified image reference used for deployment after the remote build completes
- required:
  - yes for Azure Container Apps deployment
- secret:
  - no
- environment-specific:
  - yes
- notes:
  - this value should be set by the deployment workflow after ACR remote build succeeds
  - it should not depend on a local Docker engine build path in the Azure large pattern

### `CTXLEDGER_MCP_AUTH_MODE`
- purpose:
  - controls how generated MCP client snippet artifacts render authentication settings
- required:
  - recommended
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `none`
  - `bearer_header`
  - `custom_header`
- recommended value:
  - `none` until the large-pattern auth gateway is finalized
- large-pattern note:
  - this setting is for generated client handoff artifacts, not for the runtime application itself
  - use it to keep generated MCP snippets aligned with the current large-pattern auth posture

### `CTXLEDGER_MCP_AUTH_HEADER_NAME`
- purpose:
  - header name used when generated MCP client snippet artifacts are rendered in `custom_header` auth mode
- required:
  - yes when `CTXLEDGER_MCP_AUTH_MODE=custom_header`
- secret:
  - no
- environment-specific:
  - yes
- recommended value:
  - `Authorization` unless the finalized gateway requires a different header
- large-pattern note:
  - this setting exists to support future gateway-specific client configuration without forcing users to hand-edit the first generated snippets
  - it affects generated snippet artifacts and README guidance, not the application runtime itself

### Environment-oriented reading of MCP auth handoff settings

The generated MCP handoff artifacts should stay aligned with the currently intended auth posture of each environment profile.

#### `dev`
Recommended handoff posture:
- `mcpAuthMode=none`
- `mcpAuthHeaderName=Authorization`

Reading:
- the generated snippets should default to no client auth header
- this keeps the first Azure bring-up and endpoint handoff as simple as possible
- the checked-in `infra/main.dev.bicepparam` profile now aligns explicitly with this posture
- if a development environment later adds a gateway, update the handoff mode explicitly rather than relying on stale defaults

#### `staging`
Recommended handoff posture:
- `mcpAuthMode=bearer_header`
- `mcpAuthHeaderName=Authorization`

Reading:
- the generated snippets should include a standard bearer-style auth header shape
- this gives staging a more realistic preproduction handoff posture than `dev`
- the checked-in `infra/main.staging.bicepparam` profile now aligns explicitly with this posture
- use this mode when the staging environment is intended to rehearse shared-access or gateway-fronted client setup without locking into a production-only custom header contract too early

#### `prod`
Recommended handoff posture:
- `mcpAuthMode=custom_header`
- `mcpAuthHeaderName=X-Auth-Request-Access-Token`

Reading:
- the generated snippets should be able to reflect a finalized gateway-specific client header contract
- this mode exists so production-oriented handoff does not require users to reconstruct the first MCP client configuration manually after deployment
- the checked-in `infra/main.prod.bicepparam` profile now aligns explicitly with this posture
- once the final large-pattern gateway decision is closed, update the production profile if the authoritative header name differs from `X-Forwarded-Access-Token`

---

## 8.5 Identity-related parameters

### `enableUserAssignedIdentity`
- purpose:
  - controls whether a user-assigned identity is used for the Container App
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `userAssignedIdentityResourceId`
- purpose:
  - existing user-assigned identity resource ID
- required:
  - yes if `enableUserAssignedIdentity=true`
- secret:
  - no
- environment-specific:
  - yes

---

## 8.6 Embedding-related infrastructure parameters

### `embeddingEnabled`
- purpose:
  - infrastructure-side source of embedding enablement value
- required:
  - yes
- secret:
  - no
- environment-specific:
  - yes

### `embeddingProvider`
- purpose:
  - infrastructure-side source of embedding provider selection
- required:
  - yes when embedding is enabled
- secret:
  - no
- environment-specific:
  - yes
- Azure large-pattern note:
  - this should resolve to an Azure OpenAI-compatible posture, not public OpenAI-first behavior

### `embeddingModel`
- purpose:
  - infrastructure-side source of embedding model value
- required:
  - yes when embedding is enabled
- secret:
  - no
- environment-specific:
  - yes

### `embeddingDimensions`
- purpose:
  - infrastructure-side source of embedding dimensions
- required:
  - yes when embedding is enabled
- secret:
  - no
- environment-specific:
  - yes

### `embeddingBaseUrl`
- purpose:
  - infrastructure-side source of custom embedding endpoint URL
- required:
  - yes for `custom_http`
- secret:
  - no
- environment-specific:
  - yes
- Azure large-pattern note:
  - if direct app-side Azure OpenAI calls are used, this should point to the Azure OpenAI endpoint

### `embeddingApiKey`
- purpose:
  - secure infrastructure parameter used to inject external provider credentials
- required:
  - yes only when the chosen app-generated provider path requires it
- secret:
  - yes
- environment-specific:
  - yes
- Azure large-pattern note:
  - for the preferred PostgreSQL-side `azure_ai` path, this is not the primary credential contract
  - do not use this field to imply that large deployments normally depend on a generic external API key

### `azureOpenAiAccountName`
- purpose:
  - Azure OpenAI account resource name
- required:
  - strongly recommended
- secret:
  - no
- environment-specific:
  - yes

### `azureOpenAiCustomSubdomain`
- purpose:
  - custom subdomain or endpoint prefix used by the Azure OpenAI resource
- required:
  - strongly recommended
- secret:
  - no
- environment-specific:
  - yes

### `azureOpenAiEmbeddingDeploymentName`
- purpose:
  - Azure OpenAI deployment name used for embeddings
- required:
  - yes when Azure-backed embeddings are enabled
- secret:
  - no
- environment-specific:
  - yes

### `azureOpenAiApiVersion`
- purpose:
  - explicit API version used for direct Azure OpenAI application calls
- required:
  - recommended
- secret:
  - no
- environment-specific:
  - yes

### `azureOpenAiAuthMode`
- purpose:
  - infrastructure-side selection of the Azure OpenAI auth mode used by the large deployment
- required:
  - yes when Azure OpenAI-backed execution is enabled
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `auto`
  - `subscription_key`
  - `managed_identity`
- recommended value:
  - `auto`
- notes:
  - `auto` should be the preferred large-pattern baseline
  - in `auto`, the deployment logic should prefer `managed_identity` and only fall back to `subscription_key` when the environment requires it

### `azureOpenAiSubscriptionKey`
- purpose:
  - infrastructure-side secure parameter used only when Azure OpenAI auth mode is `subscription_key`
- required:
  - yes when `azureOpenAiAuthMode=subscription_key`
- secret:
  - yes
- environment-specific:
  - yes
- notes:
  - do not set this when `azureOpenAiAuthMode=managed_identity`
  - do not describe this as the normal large-pattern default path

### `azureEmbeddingMode`
- purpose:
  - infrastructure-side declaration of whether embeddings are expected to be generated in PostgreSQL or in the application
- required:
  - strongly recommended
- secret:
  - no
- environment-specific:
  - yes
- allowed values:
  - `postgres_azure_ai`
  - `application_azure_openai`
  - `disabled`
- recommended value:
  - `postgres_azure_ai`

---

## 9. Secret Classification Matrix

The following values should be treated as secrets or sensitive values in the Azure large pattern.

## 9.1 Strict secrets
- `CTXLEDGER_DATABASE_URL`
- `postgresAdminPassword`
- `embeddingApiKey`
- `CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY`
- Azure OpenAI access key material if key-based auth is used
- PostgreSQL `azure_ai` extension secret-backed settings when key-based auth is used
- future auth/gateway client secrets
- future database application passwords if separated from admin credentials

## 9.2 Sensitive but not always secret
- `postgresAdminLogin`
- resource IDs tied to restricted infrastructure
- externally reachable deployment URLs in restricted environments
- environment-specific gateway config values

## 9.3 Non-secret ordinary config
- log level
- MCP path
- replica counts
- CPU and memory sizing
- schema name
- graph name
- embedding model
- region
- resource names

---

## 10. Validation Rules

The Azure large pattern should validate configuration at multiple stages.

## 10.1 Static configuration validation

Before deployment, validate:

- required values are present
- enum-like values are legal
- numeric bounds are legal
- ports/path values are coherent
- secret placeholders are not being used as final values

Examples:
- `CTXLEDGER_PORT` must be a valid port number
- `CTXLEDGER_DB_POOL_MAX_SIZE` must be greater than or equal to `CTXLEDGER_DB_POOL_MIN_SIZE`
- `CTXLEDGER_LOG_LEVEL` must be one of the allowed values
- `CTXLEDGER_EMBEDDING_BASE_URL` must be a valid absolute URL when provided

## 10.2 Cross-field validation

Before acceptance, validate cross-field relationships such as:

- `CTXLEDGER_PORT` matches Container Apps `targetPort`
- `CTXLEDGER_HTTP_PATH` matches deployment expectations for `/mcp`
- `CTXLEDGER_DB_AGE_GRAPH_NAME` is set when AGE is enabled
- external embedding providers do not omit required API key configuration
- replica counts and pool sizing remain within a sane PostgreSQL connection envelope
- `CTXLEDGER_AZURE_OPENAI_ENDPOINT` and `CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT` match the intended Azure OpenAI resource and deployment
- PostgreSQL `azure_ai` settings match the same Azure OpenAI endpoint and embedding deployment used by the environment
- vector column dimensions remain consistent with the selected Azure OpenAI embedding deployment
- the deployment does not simultaneously claim PostgreSQL-side Azure embedding generation while leaving `azure_ai` configuration undefined
- `postgresAllowedExtensions` includes the extensions required by the accepted environment posture
- automated bootstrap settings are aligned with feature posture, including:
  - `bootstrapEnsureAge` versus AGE enablement
  - `bootstrapValidateEmbeddings` versus PostgreSQL-side Azure embedding mode
- the deployment automation does not attempt to execute bootstrap SQL before extension allowlisting is configured

## 10.3 Environment validation

Before runtime acceptance, validate:

- the deployment points to the intended Azure PostgreSQL environment
- the intended image tag is being deployed
- ingress exposure matches the intended environment posture
- debug endpoint exposure matches the intended environment posture
- the PostgreSQL server parameter allowlist has been applied successfully
- the automated bootstrap path has actually run in the target environment
- the deployment did not depend on extra manually prepared support resources that were omitted from the accepted user-facing workflow

## 10.4 Runtime validation

After deployment, validate:

- the app starts successfully with the supplied config
- the MCP endpoint is reachable at the intended path
- missing or invalid auth is rejected by the intended boundary
- the application can reach PostgreSQL successfully
- required extension posture is satisfied for the accepted environment
- Azure OpenAI connectivity is valid for the selected embedding mode
- when `postgres_azure_ai` mode is used:
  - PostgreSQL can execute the required `azure_ai` / `azure_openai` functions successfully
  - the database can generate embeddings directly through Azure OpenAI
- when application-side Azure OpenAI mode is used:
  - the application reaches the Azure OpenAI endpoint successfully with the intended deployment name

For the large Azure pattern, runtime validation should specifically include the automated bootstrap and postdeploy validation sequence outcome:

1. PostgreSQL Flexible Server deployment completes
2. required extensions are allowlisted through `azure.extensions`
3. wait until PostgreSQL accepts connections
4. bootstrap SQL creates required extensions
5. bootstrap SQL writes required `azure_ai` settings
6. optional embedding validation succeeds when enabled
7. bundled schema bootstrap runs automatically after the PostgreSQL AI/bootstrap phase
8. representative schema objects are verified successfully
9. any support resources needed by the deployment flow are provisioned automatically as part of the same infrastructure path
10. the `azd up` workflow completes without requiring manual post-provision bootstrap intervention
11. the deployment performs Azure Container Registry remote build instead of relying on a local Docker engine for the Azure large path
12. the deployment captures the resulting fully qualified image reference and uses it for the application rollout
13. an automatic postdeploy smoke test probes the deployed MCP endpoint and confirms an expected bounded result
14. the preferred postdeploy smoke-test mode uses an MCP `initialize` request followed by `tools/list` and `resources/list` so protocol-level reachability, a basic MCP capability request, and a basic MCP resource capability request are validated, not only generic HTTP reachability
15. the deployment writes MCP client snippet artifacts to a predictable output directory
16. those MCP client snippet artifacts support auth-aware rendering modes so the generated snippets can match the current large-pattern auth posture
17. the generated snippet summary metadata captures useful deployment and handoff context, including Azure environment name, location, environment type, auth-mode details, postdeploy smoke-result details, a bounded smoke body preview, deployment timestamp, application version, generated artifact paths, preferred artifact guidance, and auth/environment usage hints
18. the generated snippet summary metadata uses a release-evidence-oriented structure with clear sections for:
  - artifacts
  - environment
  - auth
  - smoke
  - deployment
  - recommended usage
19. the deployment writes a rendered README artifact alongside those snippet files so users can understand and reuse the generated configuration later
20. the terminal output at the end of deployment is handoff-first, surfacing the MCP endpoint and generated artifact paths before lower-priority detail
21. the console handoff remains README-first and artifact-first rather than relying on long inline snippet output in the terminal
22. the deployment surfaces the final MCP endpoint clearly enough that the remaining user task is only MCP client configuration

This validation sequence should also be interpreted through the persistence / interactive boundary:

- PostgreSQL-side validation is proving persistence-oriented and retrieval-support behavior
- it is not by itself proof that every possible interactive AI response path is implemented through the same mechanism
- if a future interactive application-side Azure OpenAI path is introduced, it should be validated separately as an application-owned response path

A deployment should not be considered complete if these steps remain manual or unverified.

---

## 11. Recommended Environment Profiles

This section provides a recommended starting posture by environment class.

## 11.1 `dev`
Recommended posture:
- `CTXLEDGER_ENV=dev`
- smaller replica counts
- lower-cost PostgreSQL SKU
- `CTXLEDGER_ENABLE_DEBUG_ENDPOINTS=false` by default unless actively diagnosing
- embeddings optional
- AGE explicitly validated or explicitly disabled/bounded

## 11.2 `staging`
Recommended posture:
- release-candidate image tags
- representative ingress/auth posture
- representative pool sizing
- representative embedding posture
- stronger logging visibility
- representative extension validation evidence

## 11.3 `prod`
Recommended posture:
- explicit release image
- explicit rollback-ready provenance
- debug endpoints normally disabled
- stronger review of HA and scale settings
- explicit secret rotation posture
- explicit decision on AGE support versus bounded deferral
- explicit monitoring baseline

---

## 12. Configuration Anti-Patterns to Avoid

The Azure large pattern should avoid these anti-patterns.

### 12.1 Reusing local-only assumptions silently
Examples:
- assuming local Traefik behavior defines Azure edge behavior
- assuming local Docker defaults are production-safe
- assuming local trust boundaries map directly to shared Azure usage

### 12.2 Treating secrets like normal config
Examples:
- committing real passwords in parameter files
- using placeholder secrets in accepted deployments
- copying database URLs into broad-access notes
- storing Azure OpenAI keys for PostgreSQL `azure_ai` setup in ordinary notes or scripts

### 12.3 Overstating AGE support
Examples:
- setting `CTXLEDGER_DB_AGE_ENABLED=true` without validating managed PostgreSQL support
- implying parity with the local AGE-capable Docker image without evidence

### 12.4 Ignoring connection scaling math
Examples:
- increasing `maxReplicas` without reviewing `CTXLEDGER_DB_POOL_MAX_SIZE`
- increasing per-replica pool size without checking PostgreSQL connection capacity

### 12.5 Enabling debug endpoints casually
Examples:
- enabling `/debug/*` in broad-exposure environments without strong need
- using debug endpoints as a substitute for proper health and logs posture

### 12.6 Treating Azure large embeddings as public OpenAI-first
Examples:
- documenting `OPENAI_API_KEY` as if it were part of the normal Azure large-pattern credential contract
- omitting Azure OpenAI endpoint, auth mode, and deployment naming from the accepted config contract
- failing to state that Azure OpenAI is the intended provider in the large pattern

### 12.7 Underusing PostgreSQL-side Azure AI integration
Examples:
- using app-side embedding generation everywhere even when PostgreSQL `azure_ai` can perform the work directly
- failing to configure `azure_ai` / `azure_openai` settings in the database while claiming PostgreSQL-integrated Azure embedding generation
- designing the large pattern as if the database were only a passive vector store

### 12.8 Leaving azure_ai bootstrap as a manual operator-only step
Examples:
- requiring operators to connect manually and run `CREATE EXTENSION` commands after deployment
- requiring operators to manually set `azure_ai` settings after infrastructure deployment
- allowlisting extensions in documentation but not automating the follow-up bootstrap sequence
- not waiting for PostgreSQL connectivity before attempting post-deploy bootstrap SQL

### 12.9 Requiring extra support-resource setup outside the normal azd up flow
Examples:
- requiring users to create deployment-script storage separately before the large pattern can work
- requiring users to prepare a managed identity separately for the standard happy path
- documenting `azd up` as the primary path while still depending on hidden manual Azure setup steps
- treating self-contained deployment support resources as optional even though the default flow depends on them

---


## 13. Minimum Acceptance Requirements for Config Completeness

The Azure large configuration contract should not be considered complete unless all of the following are true:

- required runtime variables are documented explicitly
- required infrastructure parameters are documented explicitly
- secret values are classified clearly
- conditional requirements are called out explicitly
- validation rules are defined
- cross-field dependencies are named
- environment-specific expectations are documented
- the contract does not imply unsupported auth, tenant, or graph guarantees

---

## 14. Suggested Future Extensions

## 14. Suggested environment parameter profiles

The current Azure large deployment scaffold now includes example parameter
profiles for:

- `infra/main.dev.bicepparam`
- `infra/main.staging.bicepparam`
- `infra/main.prod.bicepparam`

These profiles should be treated as starting points for environment sizing,
operational posture, and MCP client handoff behavior rather than immutable
final capacity decisions.

### 14.1 `dev` profile reading

The `dev` profile is intended for:

- first Azure validation
- developer-owned environment bring-up
- low-risk bootstrap verification
- endpoint handoff verification
- schema and `azure_ai` bootstrap confirmation

Representative characteristics:

- smaller compute footprint
- lower replica counts
- high availability disabled by default
- large-pattern architecture preserved, but at lower cost and lower scale
- MCP client handoff can remain auth-light, typically with:
  - `mcpAuthMode=none`
  - `mcpAuthHeaderName=Authorization`

### 14.2 `staging` profile reading

The `staging` profile is intended for:

- release-candidate validation
- representative concurrency testing
- operator validation of rollout behavior
- realistic postdeploy smoke validation
- acceptance evidence gathering before production promotion

Representative characteristics:

- more realistic database sizing than `dev`
- high availability enabled
- multiple container replicas
- representative statement timeout and pool sizing posture
- Azure OpenAI and PostgreSQL `azure_ai` posture kept aligned with production intent
- Azure OpenAI auth selection should still prefer the large-pattern safe path:
  - `azureOpenAiAuthMode=auto`
  - effective behavior should prefer `managed_identity`
  - `subscription_key` should be treated as an explicit or environment-required fallback, not as the default staging posture
- MCP client handoff can move closer to shared-environment reality, typically with:
  - `mcpAuthMode=bearer_header`
  - `mcpAuthHeaderName=Authorization`

### 14.3 `prod` profile reading

The `prod` profile is intended for:

- trusted production operation
- stronger scale and resilience posture
- production-oriented pool sizing and capacity planning
- stricter observability and rollout expectations

Representative characteristics:

- larger PostgreSQL SKU
- larger storage allocation
- high availability enabled
- larger replica ceiling
- large-pattern defaults preserved:
  - Azure OpenAI-first posture
  - PostgreSQL `azure_ai` preferred embedding mode
  - Azure OpenAI auth selection defaults to:
    - `azureOpenAiAuthMode=auto`
    - effective behavior should prefer `managed_identity`
    - `subscription_key` should be used only when the production environment explicitly requires or permits it
  - automated PostgreSQL bootstrap
  - automated schema bootstrap
  - automated MCP smoke validation and client handoff artifacts
- MCP client handoff can reflect finalized production gateway posture, typically with:
  - `mcpAuthMode=custom_header`
  - `mcpAuthHeaderName=X-Auth-Request-Access-Token`
- production review should confirm that both:
  - the MCP client-facing custom header posture
  - and the PostgreSQL-side Azure OpenAI auth resolution from `auto`
  match the intended production boundary

### 14.4 How to use these profiles

Use these parameter files as:

- reference defaults
- environment-class starting points
- release planning inputs
- capacity discussion baselines

Do not treat them as proof that no further environment tuning is required.
Operators should still validate:

- PostgreSQL connection envelope versus replica count
- Azure OpenAI capacity versus embedding demand
- latency expectations
- cost posture
- region-specific service availability
- auth/gateway behavior once finalized
- whether `azureOpenAiAuthMode=auto` resolves to the correct effective behavior for the target subscription or policy environment:
  - prefer `managed_identity`
  - use `subscription_key` only when the environment explicitly requires or permits it
- whether the checked-in environment profiles remain aligned with that reading:
  - `dev`
    - `azureOpenAiAuthMode=auto`
    - effective behavior should prefer `managed_identity`
  - `staging`
    - `azureOpenAiAuthMode=auto`
    - effective behavior should prefer `managed_identity`
  - `prod`
    - `azureOpenAiAuthMode=auto`
    - effective behavior should prefer `managed_identity`

## 15. Suggested Future Extensions

The following future additions would be natural extensions of this specification:

- Key Vault-backed secret reference guidance
- auth/gateway-specific config contract
- custom domain and TLS config contract
- network isolation config contract
- stronger staging/prod sizing guidance beyond the initial parameter profiles
- Grafana or Azure-native monitoring config contract
- schema/bootstrap job config contract
- extension validation job config contract

---

## 16. Summary

The Azure large deployment pattern needs a configuration contract that is:

- explicit
- bounded
- secret-aware
- environment-aware
- aligned with the current architecture

At minimum, the large pattern depends on correctly defining and validating:

- Azure resource identity and sizing
- PostgreSQL connectivity
- MCP HTTP exposure at `/mcp`
- logging and debug posture
- connection pool sizing
- AGE enablement intent
- Azure OpenAI-first embedding configuration
- PostgreSQL `azure_ai` / `azure_openai` configuration for direct database-side embedding generation
- automated extension allowlisting and post-deploy bootstrap execution
- secure secret handling

This specification provides the baseline contract for that work so the Azure large pattern can evolve without relying on local implicit assumptions or undocumented operator knowledge.

For the accepted Azure large pattern, the expected deployment sequence is:

1. run `azd up`
2. select the Azure subscription
3. select the Azure location
4. provision the support resources needed by the deployment workflow itself
5. deploy PostgreSQL Flexible Server
6. configure `azure.extensions` to allow the required extensions
7. wait until PostgreSQL accepts connections
8. execute PostgreSQL AI/bootstrap SQL automatically
9. verify `azure_ai` configuration and, when enabled, direct embedding generation
10. execute bundled schema bootstrap automatically
11. verify representative schema objects
12. perform Azure Container Registry remote build for the application image
13. use the standard `azd` service-level Docker `remoteBuild: true` flow against Azure Container Registry rather than a custom local Docker build path
14. capture the resulting image reference for deployment
15. deploy and expose the MCP application endpoint
16. run an automatic postdeploy smoke test against the deployed MCP endpoint, preferably by sending an MCP `initialize` request followed by `tools/list` and `resources/list`
17. write MCP client snippet artifacts to disk for representative clients
18. write release-evidence-oriented summary metadata that captures deployment, auth, smoke, environment, artifact paths, and recommended usage context in a structured way
19. write a rendered README artifact alongside those snippet files
20. print a handoff-first deployment summary that surfaces the endpoint and generated artifact paths prominently
21. keep the final console handoff README-first and artifact-first instead of depending on large inline snippet output
22. leave the user with only the remaining task of configuring the AI agent / MCP client against the deployed endpoint

That sequence should be treated as part of the configuration contract, not merely as optional operator guidance.