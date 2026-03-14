# Local TLS certificates for Traefik HTTPS mode

This directory is intended for **local-only** TLS certificate material used by the
Traefik small-auth deployment path.

Expected files:

- `localhost.crt`
- `localhost.key`

These filenames are referenced by:

- `docker/docker-compose.small-auth.yml`
- `docker/traefik/dynamic.yml`

## Purpose

The repository’s small-auth proxy path now supports an HTTPS entrypoint in
addition to the existing HTTP entrypoint.

That HTTPS path is intended for:

- local operator validation
- authenticated MCP client checks over `https`
- smoke validation against a TLS-terminated proxy
- development-time experiments with a production-like proxy boundary

It is **not** intended to encourage committing private key material into the
repository.

## Important rules

- Do **not** commit real certificate or key files to version control.
- Treat `localhost.key` as sensitive secret material.
- Use this directory only for local development certificates.
- Prefer certificates whose SAN includes `localhost` and `127.0.0.1` when you
  want browser/client trust to behave more predictably for local testing.

## Recommended local certificate generation

A practical local approach is to use `mkcert`:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
ls -l docker/traefik/certs
```

If you do not use `mkcert`, you can also generate a self-signed certificate with
OpenSSL:

```/dev/null/sh#L1-6
mkdir -p docker/traefik/certs
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout docker/traefik/certs/localhost.key \
  -out docker/traefik/certs/localhost.crt \
  -days 365 \
  -subj "/CN=localhost"
```

A plain OpenSSL self-signed certificate may not be trusted automatically by your
system or client.

## Validation notes

After creating the files, you can start the authenticated Traefik stack and use
the HTTPS endpoint at:

```/dev/null/txt#L1-1
https://127.0.0.1:8443/mcp
```

For local self-signed testing, clients and smoke checks may need an insecure or
trust-configured mode, depending on whether the certificate is trusted by the
local machine.

## Cleanup

If you want to remove local certificate material later:

```/dev/null/sh#L1-1
rm -f docker/traefik/certs/localhost.crt docker/traefik/certs/localhost.key
```
