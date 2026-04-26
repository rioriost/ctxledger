# ctxledger

![Grafana overview](images/grafana.png)

Durable workflow runtime and memory system for AI agents.

`ctxledger` is a remote MCP server for teams that want agent work to be:

- resumable across sessions
- durable across process restarts
- recorded in PostgreSQL as canonical state
- searchable and inspectable later
- observable through CLI and Grafana

It provides:

- workflow lifecycle control
- automatic and explicit memory capture
- bounded historical recall
- file-work metadata capture
- searchable file-work records linked to work loops
- PostgreSQL-backed persistence
- HTTPS-friendly local deployment
- operator-facing observability
- optional derived Apache AGE graph support in the default local stack

---

## For users

### What you get

#### Quick Start (small): local Docker/TLS pattern

The default local setup gives you:

- MCP endpoint:
  - `https://localhost:8443/mcp`
- Grafana:
  - `http://localhost:3000`
- authenticated HTTPS access
- PostgreSQL 17 with the repository-owned local image path
- Docker Compose startup for the full local stack

#### Quick Start (large): Azure deployment pattern

The Azure large deployment path gives you:

- MCP endpoint:
  - Azure Container Apps HTTPS endpoint
- Azure OpenAI-backed PostgreSQL `azure_ai` bootstrap
- Azure Database for PostgreSQL Flexible Server
- Azure Container Registry remote image build
- Azure Developer CLI (`azd`) one-command deployment flow
- generated MCP client snippets under `.azure/mcp-snippets`

### Quick Start (small)

#### 1. Clone the repository and move into it

```/dev/null/sh#L1-2
git clone https://github.com/rioriost/ctxledger.git
cd ctxledger
```

#### 2. Create local TLS certificates

`ctxledger` expects local certificates for `localhost`.

A practical setup with `mkcert`:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -install
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

#### 3. Create `.env` from the example

```/dev/null/sh#L1-1
cp .env.example .env
```

#### 4. Populate the generated-secret placeholders in `.env`

The fastest way to get a usable local setup is:

- copy `.env.example` to `.env`
- populate these placeholders:
  - `CTXLEDGER_SMALL_AUTH_TOKEN`
  - `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`
  - `CTXLEDGER_GRAFANA_POSTGRES_PASSWORD`
- then add `OPENAI_API_KEY` in your editor

Run the helper script once:

```/dev/null/sh#L1-1
python scripts/populate_env_placeholders.py .env --mode local
```

The generated Grafana admin password is intentional:
it reliably includes upper-case, lower-case, digits, and punctuation so it satisfies Grafana password policy.

If you use `envrcctl`, use the shell helper script to store the local ctxledger secrets first:

```/dev/null/sh#L1-1
sh scripts/bootstrap_envrcctl_secrets.sh
```

#### 5. Add `OPENAI_API_KEY` to `.env`

`OPENAI_API_KEY` is required for the default local stack because embeddings are enabled.

Open `.env` and add your key:

```/dev/null/dotenv#L1-6
OPENAI_API_KEY=replace-with-your-openai-api-key
CTXLEDGER_SMALL_AUTH_TOKEN=generated-value
CTXLEDGER_GRAFANA_ADMIN_USER=admin
CTXLEDGER_GRAFANA_ADMIN_PASSWORD=generated-value
CTXLEDGER_GRAFANA_POSTGRES_USER=ctxledger_grafana
CTXLEDGER_GRAFANA_POSTGRES_PASSWORD=generated-value
```

If you use [`envrcctl`](https://github.com/rioriost/envrcctl), store your real `OPENAI_API_KEY` in `envrcctl` too.

```sh
envrcctl secret set --account 'ctxledger_openai_api_key' OPENAI_API_KEY
```

#### 6. `.rules` file

The `.rules` file is required to use `ctxledger` effectively.

Copy it into the project directory where you use your AI agent for development, and use it there as-is.

#### 7. Start the stack

```/dev/null/sh#L1-1
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

If you use `envrcctl`, run:

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

##### Run under Podman

The same compose files are designed to run cleanly under rootless Podman.
The recommended runtime is `podman compose` (the Docker Compose v2 plugin
talking to the Podman socket), because it has the broadest support for
`condition: service_completed_successfully` used by `ctxledger-private-init`:

```/dev/null/sh#L1-1
podman compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

`podman-compose` (the Python implementation) also works on recent
versions, but older releases may not honor
`condition: service_completed_successfully`. If you must use it, prefer
the latest `podman-compose` from your distribution.

For systemd-managed Podman deployments, Quadlet (`.container`,
`.kube`, `.pod`) is the recommended path and `restart:` policies in
the compose files can be replaced by `Restart=always` in a Quadlet
unit. Quadlet unit files are not shipped in this repository.

##### Optional: live-edit development overlay

The production compose files do not bind-mount the repository into the
containers; the application is baked into the `ctxledger:local` image at
build time. For a live-edit workflow, add the dev overlay:

```/dev/null/sh#L1-4
docker compose \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.small-auth.yml \
  -f docker/docker-compose.dev.yml up --build
```

The dev overlay re-introduces `..:/app:Z` and the `auth-small` source
mount. The `:Z` SELinux relabel is required on rootless Podman /
SELinux-enforcing hosts and is silently ignored by Docker Desktop.

##### Optional: deploy to a non-`localhost` host

Two environment knobs let the small stack run on a different host
without editing compose:

- `CTXLEDGER_GRAFANA_DOMAIN` and `CTXLEDGER_GRAFANA_ROOT_URL`
  - set both directly in your env file when the stack is reachable at
    something other than `http://localhost:3000`
  - example for a host named `ctxledger.lan`:
    - `CTXLEDGER_GRAFANA_DOMAIN=ctxledger.lan`
    - `CTXLEDGER_GRAFANA_ROOT_URL=http://ctxledger.lan:3000`
  - update your `mkcert` (or other CA) SAN list to include the same name
    when serving TLS from that host
- `CTXLEDGER_PUBLIC_HOST`
  - documented convention you can reference inside your own env file
    (for example `CTXLEDGER_GRAFANA_DOMAIN=${CTXLEDGER_PUBLIC_HOST}`)
  - the compose files do not interpolate it directly because
    `podman-compose` 1.5.x does not support nested variable substitution
    (`containers/podman-compose#1064`); resolve it once in your env file
    and the resolved values flow into the stack
- `CTXLEDGER_BIND_HOST`
  - default empty (bind on all interfaces, matching prior behavior)
  - prefixes the host port mappings for postgres `55432`, grafana `3000`,
    and traefik `8443`
  - set to `127.0.0.1` to restrict the stack to loopback

#### 8. Verify the endpoint

Without auth, the endpoint should reject the request:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

With auth, the workflow scenario should succeed:

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token YOUR_TOKEN_HERE --scenario workflow --workflow-resource-read --insecure
```

Replace `YOUR_TOKEN_HERE` with the value of `CTXLEDGER_SMALL_AUTH_TOKEN`.

#### 9. Connect your MCP client

Example Zed configuration:

```/dev/null/json#L1-7
{
  "ctxledger": {
    "url": "https://localhost:8443/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
  }
}
```

Example VS Code configuration:

```
"servers": {
		"ctxledger": {
			"url": "https://localhost:8443/mcp",
			"type": "http",
			"headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
		}
	},
```

### SSL/TLS troubleshooting

This troubleshooting applies only to the local `localhost:8443` Traefik/TLS setup used by the small pattern. It does not apply to the Azure Container Apps endpoint used by the Azure large deployment path.

If your AI agent or other client reports a certificate trust error, first verify which certificate Traefik is serving.

#### 1. Check the served certificate

```text
openssl s_client -connect localhost:8443 -servername localhost < /dev/null 2>/dev/null | openssl x509 -noout -subject -issuer
```

Expected output:

```text
subject=CN=localhost
issuer=CN=localhost
```

If you see `TRAEFIK DEFAULT CERT`, the local certificate is not being selected correctly.

#### 2. Trust the local certificate on macOS

The generated certificate file is:

```text
docker/traefik/certs/dev.crt
```

On macOS, open this certificate in Keychain Access and mark it as trusted.

Typical flow:

- open `docker/traefik/certs/dev.crt`
- add it to Keychain Access
- open the certificate details
- under Trust, set the certificate to “Always Trust”

#### 3. Retry the AI agent connection

After trusting the certificate, reconnect your AI agent to:

```text
https://localhost:8443/mcp
```

If the endpoint is reachable but your client uses a method that the MCP endpoint does not accept for that probe, you might see an HTTP `405 Method Not Allowed`. That indicates method handling differences, not a TLS trust failure.

### Quick Start (large)

Use this path when you want to deploy `ctxledger` to Azure Container Apps with Azure Database for PostgreSQL Flexible Server and Azure OpenAI.

#### 1. Clone the repository and move into it

```/dev/null/sh#L1-2
git clone https://github.com/rioriost/ctxledger.git
cd ctxledger
```

#### 2. Sign in to Azure and select the target subscription

Make sure the Azure CLI and Azure Developer CLI are installed, then sign in and select the subscription you want to use.

```/dev/null/sh#L1-3
az login
azd auth login
az account set --subscription YOUR_SUBSCRIPTION_ID_OR_NAME
```

#### 3. Run the Azure large deployment

The intended happy path is a single command:

```/dev/null/sh#L1-1
azd up
```

This flow provisions the Azure infrastructure, builds and deploys the container image, bootstraps PostgreSQL / `azure_ai`, applies the schema, and runs a bounded postdeploy smoke test.

#### 4. Review the generated environment and MCP snippets

After a successful deployment, `azd` writes deployment environment values and MCP client snippets to the local workspace.

Important generated paths:

- environment values
  - `.azure/ctxledger/.env`
- MCP snippet README
  - `.azure/mcp-snippets/README.md`
- MCP snippet summary
  - `.azure/mcp-snippets/summary.json`

#### 5. Connect your MCP client to the Azure endpoint

Use the generated MCP endpoint shown by `azd up`, or open the snippet README and copy the client configuration that matches your tool.

The deployed endpoint has the form:

```/dev/null/text#L1-1
https://<your-container-app-fqdn>/mcp
```

If you are using the current Azure large default flow, a basic HTTP smoke probe might return HTTP `405 Method Not Allowed`. That still indicates that the endpoint is reachable; it reflects method handling rather than endpoint unavailability.

### What you can do with it

An MCP client or agent can:

- register a workspace
- start a workflow
- checkpoint progress with bounded auto-memory capture
- resume work from durable state
- complete a workflow with verification status
- record file-touching work in durable ctxledger state with the `file_work_record` MCP tool
- search later for file-linked work context during resume, continue, and debugging
- record explicit high-signal episodes
- search memory with bounded canonical retrieval
- read grouped context optimized for hierarchy-aware clients
- inspect workflow, memory, and failure state

Useful CLI commands:

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`
- `ctxledger failures`

---

## Options

### Check stack health

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps
```

### Open Grafana

Grafana is available at:

```/dev/null/txt#L1-1
http://localhost:3000
```

Log in with:

- username:
  - `CTXLEDGER_GRAFANA_ADMIN_USER`
- password:
  - `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`

### Build an episode summary explicitly

```/dev/null/sh#L1-4
python -m ctxledger.__init__ build-episode-summary \
  --episode-id <episode-uuid> \
  --summary-kind episode_summary \
  --format json
```

### Check or refresh derived AGE graph state

Readiness:

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

Refresh derived summary graph:

```/dev/null/sh#L1-1
ctxledger refresh-age-summary-graph
```

Bootstrap the constrained graph explicitly:

```/dev/null/sh#L1-1
ctxledger bootstrap-age-graph
```

### Current local deployment mode

The supported local deployment mode in this repository is:

- `small`
  - HTTPS
  - proxy-layer authentication
  - Grafana enabled
  - Apache AGE enabled
  - repository-owned PostgreSQL image path

---

## For developers

If you need the current system shape, start with:

- product overview:
  - `docs/project/product/specification.md`
  - `docs/project/product/architecture.md`
  - `docs/project/product/mcp-api.md`
  - `docs/project/product/memory-model.md`
- operations:
  - `docs/operations/README.md`
- memory docs:
  - `docs/memory/README.md`
- release state:
  - `docs/project/releases/CHANGELOG.md`
  - `docs/project/releases/0.9.0_acceptance_review.md`
  - `docs/project/releases/0.9.0_closeout.md`

Useful repository scripts:

- `scripts/apply_schema.py`
- `scripts/ensure_age_extension.py`
- `scripts/mcp_http_smoke.py`
- `scripts/setup_grafana_observability.py`

Core local startup files:

- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`
- `docker/docker-compose.dev.yml` (optional live-edit overlay)
- `docker/auth_small/Dockerfile` (pre-built `auth-small` proxy image)
- `scripts/private_init_entrypoint.sh` (entrypoint for `ctxledger-private-init`)

Current development posture:

- PostgreSQL state is canonical
- workflow, checkpoint, and projection state remain canonical-first
- summaries, rankings, and graph-backed structures are derived support layers
- file-work metadata is stored without broad file-content indexing
- the default runtime exposes a bounded `file_work_record` MCP tool so agents can record file-touching work in the active work loop
- normal file-touching runtime flows should also naturally leave a durable file-work trail when bounded workflow context is available, with explicit `file_work_record` still available for deliberate higher-signal notes or gap-filling
- the README is intentionally brief; use the docs above for details

---

## License

Licensed under the Apache License, Version 2.0.
See `LICENSE`.
