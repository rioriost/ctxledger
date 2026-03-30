# `1.0.0` Large Deployment Pattern Plan for Azure

## 1. Purpose

This document defines the planning baseline for adding a **large deployment pattern** in `1.0.0`.

The intent of the large pattern is to complement the existing **small pattern** rather than replace it.

A major user-experience goal for the large pattern is to achieve a **self-contained one-command Azure deployment**.

The intended ideal is:

- the operator runs `azd up`
- the only required first-run selections are:
  - Azure subscription
  - Azure location
- Azure infrastructure is provisioned
- the application container image is built remotely in Azure Container Registry through the standard `azd` remoteBuild flow rather than through a local Docker engine
- the application is deployed
- PostgreSQL extension allowlisting and `azure_ai` bootstrap run automatically
- the bundled `ctxledger` schema is applied automatically after database readiness and extension bootstrap succeed
- deployment support resources required for bootstrap are also created automatically
- the deployed MCP endpoint is produced as an output
- an automatic postdeploy smoke test validates the deployed MCP endpoint before the workflow reports success
- the preferred smoke path uses an MCP `initialize` probe followed by `tools/list` and `resources/list` rather than only a bare HTTP reachability check
- deployment completion output includes MCP client configuration snippets for representative clients
- MCP client configuration snippets are also written as reusable deployment artifacts
- generated MCP client snippets should support auth-aware rendering modes so they can reflect:
  - no auth headers
  - standard bearer `Authorization` headers
  - custom header names for future large-pattern gateway alignment
- generated MCP client snippet artifacts should also include richer summary metadata such as:
  - Azure environment name
  - Azure location
  - Azure environment type
  - auth rendering mode
  - auth header name when custom-header rendering is used
  - postdeploy smoke status
  - postdeploy smoke probe mode
  - postdeploy smoke protocol version
  - postdeploy smoke follow-up probes
  - postdeploy smoke body preview
  - deployment timestamp
  - application version
- a rendered MCP snippet README artifact is also written so the generated files are easy to understand and reuse later
- deployment completion output should be README-first and handoff-first:
  - present the MCP endpoint clearly
  - point users first to the generated snippet README
  - then point users to the generated snippet directory and summary metadata
  - avoid overloading the final console output with large inline snippet blocks when the generated artifacts already contain the canonical handoff material
  - keep the final console messaging optimized for “configure your AI agent / MCP client now”
- the remaining user to-do is limited to configuring the AI agent or MCP client to use that endpoint

- **small pattern**
  - local Docker Compose
  - single operator or small shared-trust usage
  - repository-owned local proxy/TLS path
  - all major runtime components run locally

- **large pattern**
  - Azure-hosted deployment
  - larger runtime capacity
  - multiple concurrent users
  - cloud-managed network, compute, and database services
  - operator posture suitable for team use rather than a single local machine

The large pattern should preserve the current architecture principle:

> `ctxledger` remains focused on MCP, workflow, memory, and persistence behavior, while authentication, network exposure, and cloud-operational concerns are handled outside the application core wherever practical.

This document is a **planning artifact**, not an implementation-complete deployment guide.

---

## 2. Goals

The `1.0.0` large deployment pattern should achieve the following goals.

### 2.1 Functional goals

- provide an Azure-hosted deployment path for `ctxledger`
- support **multiple simultaneous users**
- support **larger and more durable operation** than the local small pattern
- keep PostgreSQL as the canonical state store
- preserve availability of:
  - `pgvector`
  - Apache AGE
  - `azure_ai`
- use **Azure OpenAI** for large deployments instead of direct OpenAI API usage
- maximize use of PostgreSQL-native Azure AI integration where practical, especially:
  - `azure_openai.create_embeddings(...)`
  - database-side embedding generation and vector update flows
- expose the MCP server in a cloud-appropriate way
- support container-based delivery of the MCP server runtime

### 2.2 Operational goals

- move core runtime hosting from local Docker to Azure-managed services
- reduce dependence on local-machine-only operational assumptions
- make it possible to operate the service for a team
- define the trust boundary, ingress posture, and secret posture more explicitly than the small pattern
- prepare for future automation with Infrastructure as Code
- make the large pattern operable through `azd up` as the primary happy-path deployment entrypoint
- constrain first-run required input to:
  - Azure subscription selection
  - Azure location selection
- minimize required post-deploy manual steps
- make “configure your AI agent / MCP client” the primary remaining user task after successful deployment

### 2.3 Architectural goals

- avoid pushing end-user identity or login logic into `ctxledger`
- keep the application backend replaceable behind a cloud ingress/gateway boundary
- preserve PostgreSQL as canonical truth
- treat AGE and other graph-oriented capabilities as derived or bounded support layers, not a competing source of truth
- preserve compatibility with the repository’s current MCP-over-HTTP posture

---

## 3. Non-Goals

The `1.0.0` large pattern should **not** be interpreted as solving all future multi-tenant or enterprise concerns.

This plan does **not** assume `1.0.0` will fully implement:

- application-layer multi-tenancy
- per-user authorization inside `ctxledger`
- tenant-aware ownership models for workflows or workspaces
- a final organization-wide identity architecture decision
- a final gateway selection for all future deployments
- zero-downtime migrations for every schema change
- globally distributed deployment or multi-region failover
- complete autoscaling tuning evidence for every workload shape
- a complete redesign of the application’s embedding architecture in `1.0.0`

The immediate goal is a credible, well-bounded **Azure large deployment pattern**, not the final end state of all future cloud architecture.

---

## 4. Current Baseline and Delta

### 4.1 Current baseline: small pattern

The current small pattern is best understood as:

- local Docker-based operation
- local PostgreSQL
- local proxy/TLS posture
- local auth/proxy mechanics
- a trusted or tightly controlled environment
- practical for one operator or a small shared-trust group

In practice, the small pattern assumes:

- the operator controls the host
- local Docker networking is available
- local certificate handling is acceptable
- a local reverse proxy such as Traefik is practical
- operational simplicity matters more than cloud-scale concerns

### 4.2 `1.0.0` delta: large pattern

The large pattern changes the deployment assumptions materially.

The large pattern is intended to move from:

- local machine
- local Compose topology
- local-only trust boundary
- local prerequisite tooling such as certificate generation and host preparation

to:

- Azure-managed runtime services
- cloud database service
- shared organizational use
- stronger separation of public ingress, backend runtime, and data services
- explicit cloud security and operational posture
- an `azd up`-centered deployment workflow that avoids external preflight steps like `mkcert`

---

## 5. Proposed Azure Target Topology

## 5.1 Core Azure services

The current planning target for the large pattern is:

- **Azure Container Registry**
  - image storage for the `ctxledger` server container
  - remote build target for the large deployment pattern
- **Azure Container Apps**
  - runtime hosting for the MCP server
- **Azure Database for PostgreSQL Flexible Server**
  - canonical relational persistence
  - `pgvector`
  - Apache AGE support target
  - `azure_ai` extension support target
  - direct Azure OpenAI integration from PostgreSQL
  - automated `azure_ai` bootstrap after infrastructure deployment
- **Azure OpenAI**
  - model hosting for embeddings used by the large pattern
  - deployment target for the embedding model consumed by both the app tier and PostgreSQL-native AI paths
- **Azure-managed deployment support resources**
  - deployment script execution resources created as part of the same infrastructure deployment
  - managed identity for bootstrap automation
  - storage required by deployment-time automation
- optional supporting Azure services to be evaluated:
  - Azure Key Vault
  - Azure Monitor / Log Analytics
  - managed ingress/gateway service
  - private DNS / virtual network integration

## 5.2 Intended logical topology

```/dev/null/txt#L1-9
MCP client
  -> Azure ingress / gateway boundary
  -> Azure Container Apps environment
  -> ctxledger application container
  -> Azure Database for PostgreSQL Flexible Server

Supporting services:
  -> Azure Container Registry
  -> Azure OpenAI
  -> Key/secret store
  -> monitoring / logs / dashboards
```

## 5.3 Role of each service

### Azure Container Registry

Use ACR for:

- storing versioned application images
- remote container builds for the large Azure pattern through the standard `azd` remoteBuild path
- CI/CD push target
- controlled deployment promotion
- stable image provenance for releases

### Azure Container Apps

Use ACA for:

- running the MCP server container
- scaling the runtime horizontally or vertically as needed
- managing revisions and deployment rollout behavior
- integrating with managed ingress and secrets
- simplifying cloud hosting without managing full Kubernetes control-plane operations

### Azure Database for PostgreSQL Flexible Server

Use Flexible Server for:

- canonical workflow persistence
- canonical memory persistence
- vector-backed search support through `pgvector`
- bounded Apache AGE-backed capabilities, if validated
- `azure_ai` extension-backed Azure OpenAI integration
- database-side embedding generation paths where practical
- backup, patching, and managed PostgreSQL operations

### Azure OpenAI

Use Azure OpenAI for:

- embedding model deployment used by the Azure large pattern
- replacing the small pattern’s direct `OPENAI_API_KEY` posture
- shared embedding capability across:
  - the application tier
  - PostgreSQL-native `azure_ai` / `azure_openai` calls
- Azure-aligned identity, networking, and secret posture

---

## 6. Database Posture

## 6.1 Canonical requirement

PostgreSQL remains mandatory in the large pattern.

The application is not meaningfully operational without:

- database connectivity
- writable canonical storage
- required schema state
- extension availability required by the deployment mode

## 6.2 `pgvector`

A key requirement for the large pattern is preserving the currently documented vector-backed retrieval posture.

The large pattern therefore assumes:

- `pgvector` must remain available
- `azure_ai` must be evaluated as a first-class large-pattern extension
- the PostgreSQL server-level allowlist must explicitly include the required extensions through the `azure.extensions` configuration
- post-deployment bootstrap must wait until the Flexible Server is actually reachable before running SQL
- bootstrap automation must create and configure required extensions and Azure AI settings without relying on ad hoc manual operator steps
- deployment validation should fail early if the target database cannot support the required extension set

For the large pattern, vector generation should no longer be described as “direct OpenAI API usage from the app by default.”
Instead, the target posture should be:

- Azure OpenAI as the model provider
- PostgreSQL-side AI integration through `azure_ai`
- application-side Azure OpenAI usage only where it is still operationally justified
- Azure Container Registry remote build through the standard `azd` remoteBuild flow rather than a local Docker engine build for the large deployment path
- automated bootstrap that configures PostgreSQL for direct Azure OpenAI usage immediately after infrastructure deployment

## 6.3 Apache AGE

A major reason to choose Azure Database for PostgreSQL Flexible Server in this plan is the desire to preserve the existing graph-support direction used in the small pattern.

The intended requirement is:

- large pattern should support Apache AGE in a way consistent with the repository’s existing bounded graph posture
- large pattern should support `azure_ai` in a way consistent with PostgreSQL remaining canonical and relational-first

However, this area should be treated as a **validation-critical assumption**, not a casual guarantee.

### Current planning stance

For `1.0.0`, the document should assume the target is:

- PostgreSQL Flexible Server with
  - `pgvector`
  - Apache AGE
  - `azure_ai`

But delivery should be gated on explicit validation of:

- extension support in the intended Azure PostgreSQL offering
- supported PostgreSQL major version compatibility
- operational model for enabling and maintaining AGE
- operational model for enabling and maintaining `azure_ai`
- schema/bootstrap compatibility with managed service restrictions
- backup/restore and upgrade implications of enabled extensions

### Important architectural caution

Even when AGE is available, the repository’s architectural rule should remain unchanged:

- PostgreSQL relational state is canonical
- AGE-backed graph structures are derived, bounded, and degradable support layers
- `azure_ai` and Azure OpenAI integration are capability enablers, not a replacement for canonical relational persistence

The large pattern must not accidentally evolve into a design where graph-side state becomes a second source of truth.

---

## 7. MCP Server Hosting Posture

## 7.1 Containerized application path

The MCP server runtime should be packaged as a container image and deployed to ACA from ACR.

This aligns well with the current application shape:

- HTTP MCP endpoint at `/mcp`
- container-friendly runtime
- clear separation between app image, deployment runtime, and data service

## 7.2 Concurrency and scaling expectations

The large pattern exists specifically to support:

- larger workloads than the small pattern
- multiple simultaneous users
- cloud-hosted uptime expectations
- more durable shared operation

That implies planning for:

- concurrent request handling
- container replica scaling policy
- connection pool sizing against the managed PostgreSQL backend
- request timeout behavior suitable for IDE-driven MCP usage
- rollout behavior that does not create unnecessary interruption during deployment revisions

## 7.3 Connection management concern

Because the application is PostgreSQL-backed and already has an explicit connection-pooling posture, the ACA deployment design must consider:

- replica count
- per-replica connection pool size
- maximum allowed PostgreSQL connections
- peak concurrent tool/resource workloads
- behavior during rolling revision overlap

A cloud deployment can fail operationally even when the app is functionally correct if aggregate connection pressure is not planned carefully.

---

## 8. Ingress and Traefik Reconsideration

## 8.1 Why Traefik must be reconsidered

In the small pattern, Traefik is a natural fit because:

- it fits Docker Compose ergonomics well
- it provides local TLS termination
- it supports a simple local auth/proxy topology
- it is easy to understand in a single-machine setup

In Azure, those assumptions change.

Azure Container Apps already provides managed ingress behavior, and Azure-native or organization-standard gateway patterns may be more appropriate than carrying forward the exact local Traefik shape.

Therefore, for the large pattern:

> Traefik should be treated as an open design question, not a default carry-forward.

## 8.2 Current recommendation

For `1.0.0`, the planning default should be:

- **do not assume Traefik remains the primary ingress component in Azure**
- prefer evaluating Azure-native ingress and gateway options first
- preserve the architectural rule that the backend application remains behind an ingress/auth boundary
- keep the app transport expectations simple:
  - HTTP
  - `/mcp`
  - proxy/gateway-managed public exposure

## 8.3 Candidate ingress/gateway directions to evaluate

The large pattern should evaluate at least these categories:

- Azure Container Apps built-in ingress alone
- ACA ingress plus an Azure-native edge service
- ACA behind an organization-standard identity-aware gateway
- ACA behind a reverse proxy or gateway only if there is a clear Azure-specific reason

## 8.4 Key gateway evaluation questions

The ingress/gateway decision for Azure should be validated against:

- compatibility with MCP HTTP clients
- support for non-browser-heavy client behavior
- custom header handling
- TLS termination posture
- support for authentication at the boundary
- logging and traceability
- operational complexity
- future support for stronger identity-aware access

## 8.5 Practical implication

The large pattern should keep the **design principle** from the small pattern:

- public ingress and auth stay outside `ctxledger`

But it should not blindly copy the **exact Traefik implementation** from local Docker into Azure.

---

## 9. Authentication and Access Posture

## 9.1 Required shift from small pattern assumptions

The large pattern exists because the small pattern’s fixed-token and local-trust assumptions are no longer sufficient for a larger shared environment.

The large pattern therefore needs a stronger access posture than:

- one shared static bearer token
- purely local secrets
- local-machine trust assumptions
- direct app-local `OPENAI_API_KEY` handling as the primary AI integration model

## 9.2 Minimum planning requirements

At minimum, the large pattern should define:

- how clients authenticate to the public endpoint
- how the gateway or ingress validates identity or access
- how secrets are stored and rotated
- how the backend remains private from direct public exposure where possible
- how operator/admin access is separated from general client access

## 9.3 Application-layer caution

This plan should remain aligned with the established repository posture:

- do not reintroduce end-user login logic into `ctxledger`
- do not assume `ctxledger` becomes the identity boundary
- keep authentication and access control at the proxy/gateway layer unless future product needs explicitly require otherwise

## 9.4 Open question: large-pattern auth/gateway decision

This plan depends on, but does not finalize, the broader large-pattern gateway decision.

The following still need explicit confirmation for Azure:

- what the production auth boundary is
- whether an Azure-native identity-aware gateway is sufficient
- whether an organization-standard gateway should be preferred
- how IDE-based MCP clients authenticate in practice
- whether the first large pattern supports:
  - trusted private team use
  - organization SSO
  - service-account or personal-token mediated access
  - another bounded access model

This is one of the highest-risk open decisions in the `1.0.0` plan.

---

## 10. Networking and Security Posture

## 10.1 Expected direction

The Azure large pattern should prefer:

- managed TLS at the ingress boundary
- private connectivity between app runtime and database where feasible
- least-privilege identity between Azure services
- secret storage outside source control and outside container images
- explicit network-boundary documentation

## 10.2 Minimum security expectations

The plan should include:

- ACR access restricted appropriately
- ACA configured without unnecessary public surface
- PostgreSQL firewall/network access narrowed to intended runtime paths
- TLS for client-facing access
- managed secret references where supported
- no hardcoded credentials in app config or IaC
- audit/log visibility for authentication and runtime failure paths

## 10.3 Secret management concern

The large pattern should not rely on `.env`-style local operational posture as its primary production model.

Instead, it should define a cloud-appropriate secret posture for items such as:

- database connection details
- application secrets
- auth/gateway configuration secrets
- external provider API keys
- observability credentials if used

---

## 11. Observability and Operations

## 11.1 Observability goals

The large pattern should preserve or improve the current operator visibility available in the repository.

That includes planning for:

- application logs
- revision/deployment logs
- health and readiness signals
- database health visibility
- request failure diagnosis
- authentication/gateway failure diagnosis
- Azure OpenAI and `azure_ai` integration failure diagnosis
- runtime metrics where available

## 11.2 Grafana question

The local small pattern includes Grafana-oriented observability posture.
For the Azure large pattern, this should be treated as a design decision rather than an automatic carry-forward.

Questions to answer include:

- should Grafana remain part of the large pattern
- should Azure-native monitoring surfaces be primary instead
- if Grafana remains, where should it run
- what read-only PostgreSQL access model is appropriate in Azure
- whether dashboard access is operator-only or broader

## 11.3 Operator tasks that need explicit cloud guidance

The large pattern documentation will eventually need concrete guidance for:

- image build and push
- deployment rollout
- schema/bootstrap execution
- extension verification
- secret rotation
- incident diagnosis
- rollback or revision pinning
- backup and restore checks

---

## 12. Delivery Scope Proposal for `1.0.0`

A practical `1.0.0` scope should likely include the following.

## 12.1 Required deliverables

- documentation for the large Azure deployment pattern
- a defined target topology using:
  - ACR
  - ACA
  - Azure Database for PostgreSQL Flexible Server
  - Azure OpenAI
- explicit statement of ingress/gateway assumptions and open decisions
- explicit statement of database extension assumptions
- explicit statement that large deployments use Azure OpenAI rather than direct OpenAI API usage
- explicit statement that large deployments use the standard `azd` Azure Container Registry remoteBuild flow rather than a local Docker engine build
- an `azd up`-oriented deployment path as the primary operator experience
- automation for PostgreSQL extension allowlisting and `azure_ai` bootstrap within the deployment flow
- self-contained deployment support resources created by the same IaC path so normal deployment does not depend on separately precreated bootstrap infrastructure
- automated schema bootstrap as part of the deployment flow after PostgreSQL connectivity and extension readiness are confirmed
- deployment outputs that surface the deployed MCP endpoint directly to the user
- automatic postdeploy smoke testing against the deployed MCP endpoint
- preferred use of an MCP `initialize` request followed by `tools/list` and `resources/list` for smoke validation so protocol-level reachability, a basic MCP capability response, and a basic MCP resource capability response are exercised during deployment handoff
- automatic post-deploy output of representative MCP client configuration snippets
- automatic writing of MCP client configuration snippet artifacts for later reuse
- auth-aware MCP client snippet rendering so generated client configuration can evolve with the finalized large-pattern auth gateway posture
- richer MCP snippet summary metadata so generated handoff artifacts also preserve:
  - Azure environment context
  - auth rendering context
  - postdeploy smoke result context
  - release-evidence-oriented deployment metadata
  - artifact file locations
  - preferred artifact and usage hints so the intended copy/paste path remains obvious after deployment
- automatic writing of a rendered MCP snippet README artifact so the generated snippet files remain easy to interpret after deployment
- handoff-first final console output so the deployment ends by directing the user immediately to:
  - the MCP endpoint
  - the generated snippet README
  - the generated snippet directory
- deployment validation checklist
- initial Infrastructure as Code direction, preferably Bicep
- release-scoped risk register

## 12.2 Strongly recommended deliverables

- a minimal reproducible Azure deployment example
- environment/config contract for large pattern settings
- database bootstrap/validation script or documented procedure
- Azure OpenAI deployment and configuration procedure
- `azure_ai` configuration procedure for PostgreSQL
- health/readiness requirements for cloud deployment
- logging and monitoring baseline
- rollback/redeployment guidance

## 12.3 Possible stretch deliverables

- CI/CD integration for image publish and deploy
- managed secret integration
- private networking hardening
- production-like load/concurrency validation
- formal gateway comparison record specific to Azure

## 12.4 Environment parameter profiles

To support the `azd up`-first operator experience cleanly, the large pattern should
also maintain explicit environment parameter profiles under `infra/`.

At minimum, the repository should carry:

- `main.dev.bicepparam`
- `main.staging.bicepparam`
- `main.prod.bicepparam`

The intent of these profiles is not to create separate architectures, but to make
the following differences explicit and reviewable by environment:

- compute sizing
- PostgreSQL sizing
- replica counts
- HA posture
- timeout posture
- connection pool posture
- tagging
- environment labels
- MCP client handoff auth posture
- generated snippet auth mode and header expectations

Recommended reading of the profiles:

### `dev`
Use for:

- first Azure bring-up
- low-risk integration validation
- extension/bootstrap verification
- low-cost operator experimentation

Typical characteristics:

- lower replica counts
- smaller PostgreSQL SKU
- lower storage allocation
- bounded but non-production sizing
- debug still disabled by default unless actively diagnosing
- MCP handoff snippets default to:
  - no auth headers
  - `mcpAuthMode=none`
  - `mcpAuthHeaderName=Authorization`

This profile is intentionally the simplest handoff posture.
It is appropriate when the large-pattern auth gateway is not yet finalized for the
environment, or when the environment is being used mainly for infrastructure and
protocol-path validation rather than final user access rehearsal.

### `staging`
Use for:

- release-candidate validation
- pre-production operator rehearsal
- realistic smoke and concurrency validation
- revision and rollback drills

Typical characteristics:

- HA enabled where representative
- more realistic pool sizing
- more realistic replica counts
- representative embedding posture
- production-like bootstrap validation
- MCP handoff snippets default to:
  - standard bearer-header rendering
  - `mcpAuthMode=bearer_header`
  - `mcpAuthHeaderName=Authorization`

These defaults are now fully aligned with the checked-in staging parameter profile.

This profile is intended to exercise a more realistic user handoff than `dev`.
It should be the first place where generated MCP client snippets are reviewed
against the environment’s expected auth boundary and copy/paste ergonomics.

### `prod`
Use for:

- trusted shared usage
- production-facing rollout
- strongest reliability posture supported by the accepted scope

Typical characteristics:

- HA enabled
- stricter sizing and connection-planning posture
- higher replica ceilings
- stronger operational tagging
- strongest expectation that the `azd up` flow is already fully validated by earlier environments
- MCP handoff snippets default to:
  - custom-header rendering
  - `mcpAuthMode=custom_header`
  - `mcpAuthHeaderName=X-Forwarded-Access-Token`

These defaults are now fully aligned with the checked-in production parameter profile.

This profile is intended to keep the generated MCP client handoff aligned with a
more production-like gateway posture.
Even if the exact final gateway product remains adjustable, the production profile
should make the expected client-facing auth header contract explicit and reviewable.

These parameter profiles should be treated as part of the large-pattern
operational contract, not as optional convenience files.

They should also be read as the primary place where environment-specific MCP
client handoff behavior is made explicit.
That includes not only sizing and HA posture, but also the auth-aware rendering
mode used for generated MCP client snippet artifacts after deployment.

The checked-in profiles are now fully aligned to this reading:

- `main.dev.bicepparam`
  - `mcpAuthMode=none`
  - `mcpAuthHeaderName=Authorization`
- `main.staging.bicepparam`
  - `mcpAuthMode=bearer_header`
  - `mcpAuthHeaderName=Authorization`
- `main.prod.bicepparam`
  - `mcpAuthMode=custom_header`
  - `mcpAuthHeaderName=X-Forwarded-Access-Token`

This means the intended environment-specific MCP handoff posture is no longer
only documentary guidance. It is now expressed directly in the checked-in
parameter profiles that drive generated MCP client snippet behavior.

---

## 13. Key Risks and Concerns

## 13.1 PostgreSQL extension support risk

This is one of the highest-risk assumption clusters.

Concerns:

- managed PostgreSQL extension support may differ from local expectations
- supported versions may constrain PostgreSQL version choice
- extension enablement may require Azure-specific operational steps
- future managed-service upgrades may complicate extension usage
- the accepted extension set now includes:
  - Apache AGE
  - `pgvector`
  - `azure_ai`

Mitigation:

- validate supported extension matrix early
- gate implementation on real environment verification
- preserve degradable graph posture if AGE support is partial or constrained
- explicitly validate `azure_ai` enablement and Azure OpenAI connectivity before accepting the large pattern

## 13.2 Ingress/gateway uncertainty

Concerns:

- the local Traefik model may not translate cleanly to ACA
- IDE/MCP client compatibility may be harmed by the wrong gateway choice
- auth ergonomics may be worse than expected for non-browser clients

Mitigation:

- evaluate Azure-native and organization-standard gateway options before implementation lock-in
- explicitly test with real MCP clients
- keep the app’s HTTP contract simple and stable

## 13.3 Database connection scaling risk

Concerns:

- ACA scaling can multiply DB connections quickly
- rolling revisions can temporarily double pressure
- pool sizing safe for local use may not be safe in Azure

Mitigation:

- define pool sizing rules per replica
- estimate peak connection counts before rollout
- validate under concurrent load

## 13.4 Cost posture risk

Concerns:

- ACA, ACR, PostgreSQL Flexible Server, networking, and monitoring can materially exceed local cost assumptions
- HA-capable database and network posture can dominate total cost

Mitigation:

- define target SKUs for:
  - development
  - staging
  - production-like
- identify minimum acceptable reliability posture
- document cost-sensitive variants

## 13.5 Operational complexity risk

Concerns:

- cloud deployment can introduce too many moving parts too early
- a “large pattern” that is theoretically correct but too hard to operate will not be adopted well

Mitigation:

- keep the first version intentionally narrow
- prefer managed services over self-managed complexity
- document failure handling and day-2 operations early

## 13.6 Multi-user semantics gap

Concerns:

- cloud hosting enables multiple users, but the application is not yet a full multi-tenant authorization system
- users may incorrectly assume complete per-user isolation or ownership controls already exist

Mitigation:

- document the exact semantics clearly
- distinguish:
  - multi-user access capability
  - multi-user authorization maturity
  - tenant isolation maturity

## 13.7 Azure OpenAI and `azure_ai` integration risk

Concerns:

- Azure OpenAI model deployment names and dimensions must align with both application expectations and PostgreSQL vector schema
- `azure_ai` configuration depends on correct Azure OpenAI endpoint and credential posture
- PostgreSQL-side embedding generation can introduce throttling, retry, timeout, or transactional behavior that differs from application-side API calls
- the project could accidentally maintain two divergent embedding paths unless the large-pattern posture is made explicit

Mitigation:

- standardize on Azure OpenAI as the large-pattern embedding provider
- document one preferred embedding flow for large deployments, with PostgreSQL-native generation as the preferred path where practical
- validate deployment name, dimensions, retry behavior, and failure handling explicitly
- document when the app may still call Azure OpenAI directly and when PostgreSQL-side `azure_openai.create_embeddings(...)` should be preferred

---

## 14. Additional Topics That Must Be Evaluated

The following topics should be explicitly reviewed before implementation is declared complete.

### 14.1 Azure regional availability

Confirm availability of:

- ACA
- ACR
- PostgreSQL Flexible Server
- required extension support
- networking features required by the chosen topology

### 14.2 PostgreSQL version and extension matrix

Confirm:

- supported PostgreSQL major version
- `pgvector` compatibility
- Apache AGE compatibility
- `azure_ai` compatibility
- migration implications for future upgrades

### 14.3 Schema/bootstrap process in managed PostgreSQL

Confirm:

- who runs migrations/bootstrap
- when extension checks occur
- how failures are surfaced
- whether bootstrap is one-time, per-release, or idempotent
- how `azure_ai` settings for Azure OpenAI endpoint and credentials are configured safely
- how `azure_openai.create_embeddings(...)` usage is validated during rollout
- how the deployment automatically waits for PostgreSQL connectivity before bootstrap SQL is executed
- how the extension allowlist is applied during infrastructure deployment before bootstrap attempts `CREATE EXTENSION`
- how automated bootstrap is retried or failed deterministically if the server is provisioned but not yet accepting connections

### 14.4 Runtime scaling policy

Define:

- minimum replicas
- maximum replicas
- concurrency assumptions
- CPU/memory sizing baseline
- cold start and revision behavior expectations

### 14.5 Public vs private exposure

Decide:

- whether ACA ingress is publicly exposed
- whether a separate gateway sits in front
- whether database access is private only
- whether admin/ops surfaces are separately restricted

### 14.6 Backup, restore, and disaster recovery

Define at least the minimum operator posture for:

- PostgreSQL backups
- point-in-time restore expectations
- redeploying ACA revisions
- restoring image provenance from ACR

### 14.7 Release engineering

Decide:

- image tagging strategy
- release promotion process
- environment separation
- rollback mechanics
- configuration drift control
- how `dev`, `staging`, and `prod` parameter profiles are versioned and reviewed together with release changes

### 14.8 Azure OpenAI configuration and secrets

For the large pattern, define:

- how Azure OpenAI resources and deployments are provisioned
- which embedding deployment name is standard for the environment
- whether the application tier uses:
  - Azure OpenAI directly
  - PostgreSQL `azure_ai`
  - or a bounded combination of both
- where Azure OpenAI endpoint and credential material live
- whether PostgreSQL-side `azure_ai` uses key-based configuration, managed identity, or another approved posture
- fallback behavior when Azure OpenAI is unavailable
- how throttling, timeout, and retry failures appear in logs and health signals

---

## 15. Recommended Implementation Sequence

A practical implementation order for the large pattern is:

1. confirm Azure service target set and scope boundaries
2. validate PostgreSQL Flexible Server extension support for:
   - `pgvector`
   - Apache AGE
   - `azure_ai`
3. define Azure OpenAI resource and deployment posture
4. define the preferred embedding path for large deployments:
   - PostgreSQL-native via `azure_openai.create_embeddings(...)`
   - app-side Azure OpenAI only where still justified
5. define the ingress/gateway decision envelope
6. define runtime configuration contract for large deployments
7. produce initial IaC for:
   - ACR
   - ACA
   - PostgreSQL Flexible Server
   - Azure OpenAI
   - required supporting resources
8. automate PostgreSQL extension allowlisting during deployment, including the required `azure.extensions` configuration
9. automate post-deployment bootstrap so it:
   - waits for PostgreSQL connectivity
   - connects successfully before running SQL
   - creates required extensions
   - configures `azure_ai` settings for Azure OpenAI
   - validates `azure_openai.create_embeddings(...)` where required
10. automate bundled schema bootstrap so it:
   - runs after PostgreSQL connectivity and extension readiness are confirmed
   - applies the checked-in `ctxledger` schema without requiring manual operator intervention
   - verifies representative schema objects exist after bootstrap
11. create any deployment support resources needed for bootstrap inside the same IaC deployment so the happy path does not depend on separately precreated infrastructure
12. package the deployment around an `azd up`-first operator workflow
13. ensure deployment outputs surface the final MCP endpoint clearly
14. run an automatic postdeploy smoke test against the deployed MCP endpoint before the deployment is treated as successfully handed off
15. emit representative MCP client configuration snippets automatically at deployment completion
16. write those representative MCP client snippets as reusable deployment artifacts for later copy/paste
17. make generated MCP client snippets auth-aware so they can render:
   - no auth headers
   - bearer `Authorization` headers
   - custom header names for future gateway alignment
18. enrich generated MCP client artifact metadata so the handoff files also preserve:
   - Azure environment name
   - Azure location
   - Azure environment type
   - auth rendering mode
   - custom auth header name when applicable
   - postdeploy smoke status
   - postdeploy smoke probe mode
   - postdeploy smoke protocol version
   - postdeploy smoke follow-up probes
   - postdeploy smoke body preview
   - deployment timestamp
   - application version
   - artifact file locations
19. write a rendered MCP snippet README artifact that explains the generated files and provides a simple handoff surface
20. use the standard `azd` remoteBuild flow so image build responsibility stays inside the normal `azd` deployment pipeline instead of requiring a custom local-Docker-driven build step
21. make the final `azd up` console output README-first and handoff-first, so it leads with:
   - the MCP endpoint
   - the remotely built image reference from Azure Container Registry
   - the generated snippet README path
   - the generated snippet directory path
   - the generated summary metadata path
   - concise guidance that the user’s next step is MCP client configuration
22. refine the generated handoff summary structure so it is useful as lightweight release evidence, including:
   - endpoint and server identity
   - environment context
   - auth handoff context
   - smoke result context
   - deployment timestamp and application version
   - preferred artifact guidance
   - generated file locations
23. validate end-to-end deployment with a minimal MCP smoke path, preferably using an MCP `initialize` request followed by `tools/list` instead of a bare endpoint probe
24. validate concurrent-use and database-connection posture
25. validate Azure OpenAI, `azure_ai`, schema bootstrap, standard `azd` remoteBuild behavior, client-handoff artifact behavior, release-evidence summary behavior, and final console handoff behavior
26. finalize operator documentation and release checklist

This sequence is important because the database-extension question, Azure OpenAI integration question, bootstrap automation design, and ingress question can materially alter the rest of the design.

---

## 16. Acceptance Criteria Proposal for the Plan

This plan should be considered sufficiently closed for `1.0.0` when the repository has, at minimum:

- a documented large Azure deployment pattern
- a documented target topology using ACR, ACA, PostgreSQL Flexible Server, and Azure OpenAI
- explicit statement of why Traefik is not automatically carried forward
- explicit statement of open ingress/auth decisions
- explicit handling of `pgvector`, Apache AGE, and `azure_ai` assumptions
- explicit statement that Azure OpenAI replaces the small pattern’s direct OpenAI API posture in large deployments
- a risk section covering extension support, Azure OpenAI integration, scaling, and multi-user semantics
- a documented list of follow-up implementation tasks

Implementation acceptance for the actual feature would require more, including real validation, but the planning artifact itself should at least make those constraints impossible to miss.

---

## 17. Follow-Up Work Items

The following follow-up items should be tracked after this plan.

### 17.1 Architecture and platform
- choose the concrete Azure ingress/gateway pattern
- decide whether Grafana remains in-scope for large deployments
- define network isolation posture
- define environment separation strategy

### 17.2 Database
- verify Flexible Server extension support in the chosen configuration
- document extension bootstrap procedure
- document `azure_ai` configuration procedure
- automate extension allowlisting through Bicep/server configuration
- automate post-deployment bootstrap waiting, connection, and SQL execution
- define migration and upgrade posture
- define backup/restore expectations
- define how PostgreSQL stores and uses Azure OpenAI endpoint and credential settings safely

### 17.3 Application/runtime
- define large-pattern environment variables and secrets contract
- define Azure OpenAI-specific application configuration
- validate connection-pool sizing in ACA
- validate readiness/liveness behavior in cloud deployment
- define revision rollout and rollback guidance
- define when embeddings are generated by PostgreSQL versus the application tier

### 17.4 Security and auth
- define the production auth boundary
- validate MCP IDE compatibility with the chosen gateway
- define operator/admin access separation
- document secret rotation posture
- define Azure OpenAI credential posture for both the application tier and PostgreSQL `azure_ai`

### 17.5 Delivery
- add IaC under `infra/`
- add deployment validation checklist
- add release/operator runbook for Azure
- add minimal smoke validation for deployed `/mcp`
- add Azure OpenAI deployment validation
- add PostgreSQL `azure_ai` embedding validation
- maintain explicit `dev`, `staging`, and `prod` parameter profiles under `infra/`
- keep environment-specific sizing and HA differences reviewable through those parameter profiles
- keep environment-specific MCP handoff auth posture reviewable through those parameter profiles
- ensure generated MCP client snippet behavior stays aligned with the intended auth mode of each environment profile

---

## 18. Summary

The `1.0.0` large deployment pattern should establish a credible Azure-hosted path for `ctxledger` built around:

- Azure Container Registry
- Azure Container Apps
- Azure Database for PostgreSQL Flexible Server
- Azure OpenAI

It should also aim for a deployment experience that is materially simpler than the local `small` pattern for end users:

- no `mkcert`-style prerequisite step
- no manual PostgreSQL AI bootstrap step
- no manual schema bootstrap step
- no separate precreation of bootstrap support infrastructure in the normal happy path
- no local Docker engine dependency for the large deployment build path
- standard `azd` remoteBuild as the preferred large-pattern image build flow
- no long post-deploy checklist before the system becomes usable
- `azd up` as the primary happy path
- first-run required input ideally limited to:
  - Azure subscription selection
  - Azure location selection
- deployment completion ideally runs an automatic smoke test against the deployed MCP endpoint
- that smoke test ideally uses an MCP `initialize` probe followed by `tools/list` and `resources/list` so deployment success reflects protocol-level readiness, basic MCP capability responsiveness, and basic MCP resource capability responsiveness, not only raw HTTP reachability
- deployment completion ideally prints representative MCP client configuration snippets using the deployed MCP endpoint
- deployment completion ideally writes those MCP client snippets as reusable artifacts as well
- those generated MCP client snippets ideally support auth-aware rendering modes so they stay aligned with the finalized large-pattern auth posture
- those generated MCP client artifacts ideally also preserve richer summary metadata describing:
  - Azure environment context
  - auth rendering context
  - postdeploy smoke result context, including smoke body preview
  - deployment timestamp
  - application version
  - generated file locations
  - preferred artifact and usage hints that tell the user which generated file to open first and how to interpret auth/environment context
- deployment completion ideally writes a rendered MCP snippet README artifact alongside those generated snippet files
- deployment completion ideally ends with README-first and handoff-first console output that points the user directly to:
  - the MCP endpoint
  - the generated snippet README
  - the generated snippet directory
  - the generated summary metadata
- generated summary metadata should be structured so it can double as lightweight release evidence for the handoff path
- user follow-up ideally limited to configuring the AI agent or MCP client with the deployed MCP endpoint

It should preserve the repository’s architectural commitments:

- PostgreSQL remains canonical
- `pgvector` remains available
- Apache AGE remains bounded and non-canonical if supported
- `azure_ai` is used to maximize PostgreSQL-native Azure OpenAI integration where practical
- the large pattern uses Azure OpenAI instead of the small pattern’s direct OpenAI API posture
- the MCP app remains behind a gateway/ingress boundary
- authentication and public exposure remain outside the application core
- PostgreSQL AI bootstrap is automated as part of deployment rather than left as a manual afterthought

The largest unresolved design questions are:

- whether Apache AGE is fully viable in the intended managed PostgreSQL shape
- what the final validated `azure_ai` posture is in the chosen Flexible Server configuration
- how to standardize Azure OpenAI usage between PostgreSQL-native embedding generation and any remaining app-side AI calls
- what the most reliable deployment-time bootstrap mechanism is for waiting on PostgreSQL readiness and executing SQL automatically
- what Azure ingress/gateway pattern should replace or supersede the local Traefik-based posture
- how to support multiple concurrent users without overstating the current maturity of in-app authorization semantics

Those questions should be treated as first-class planning constraints for `1.0.0`, not implementation footnotes.