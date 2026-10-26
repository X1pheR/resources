# Private Homepage Gatus + Docker-health bridge

A small credential-free, read-only adapter for Homepage's status indicators. It uses existing Gatus measurements and a **local, already restricted Docker read proxy**. It adds no probes, database, new public listener or Docker socket mount.

## Supported interfaces

- `/general`, `/development`, `/health`: the latest Gatus result for each configured OCI MCP tunnel. A fresh successful sample gives HTTP 200; a failed, absent or stale sample returns 503. Homepage `siteMonitor` presents **Up**.
- `/containers/json` and Docker API version-prefixed `/vN.N/containers/json`: Dockerode-compatible **minimal allowlisted** container listing for Homepage v2.7.0. Unfiltered list and `filters={"health":["healthy"]}` (also `unhealthy`/`starting`) are supported. Each output item contains only `Id`, `Names`, `State` and an empty `Labels` object. Homepage uses health-filtered lists to present native Docker **Healthy**. No image, mounts, ports, environment, container configuration, log, stats or unrelated container data is returned.

All other paths, Docker operations, methods and unsupported query filters are rejected. The bridge does **not** provide a general Docker API, even though it can serve as a minimal Homepage `docker.yaml` backend. The status indicator's optional stats panel is not supported; use `showStats: false` on its cards.

## Deployment and security

The currently accepted private OCI binding is `10.42.0.129:8197`; Homepage is an allowed client, never the public internet. The service runs under a constrained systemd identity. The existing Docker proxy listens **only on OCI loopback** at `127.0.0.1:2377`; this bridge requests its container listing locally and strips all non-allowlisted container records and metadata before replying.

Environment settings for another installation:

- `HOMEPAGE_STATUS_BIND`, `HOMEPAGE_STATUS_PORT`: private interface and port (Hypershell defaults used by the prior bridge).
- `HOMEPAGE_GATUS_URL`: local Gatus API base.
- `HOMEPAGE_STATUS_CLIENTS`: comma-separated allowed source IPv4 addresses.
- `HOMEPAGE_DOCKER_PROXY`: locally accessible read-only Docker proxy base.
- `HOMEPAGE_DOCKER_CONTAINERS`: **required for the Docker route**. Comma-separated exact container names; omitted/empty fails closed.

The current route-to-Gatus-name mapping is fixed for the three Hypershell tunnels. Change it deliberately if reusing this integration elsewhere. The OCI systemd unit, container allowlist, source activation and private firewall belong to `X1pheR/hypershell-infrastructure`; reusable implementation and tests belong to `X1pheR/resources`. No new network exposure of the real Docker proxy is permitted.

Run `python3 -m unittest -v test_server.py` and `python3 -m py_compile server.py` for representative security/contract checks. Tests cover read-filter semantics, exact allowlists, metadata suppression, unsupported filters, missing allowlist and supported routes.
