# MCP tunnel status bridge for Homepage

Small read-only HTTP translator for an existing Gatus monitoring server. It reports HTTP 200 for a fresh successful probe on a configured MCP tunnel and HTTP 503 if failed, missing or stale. The adapter does not perform monitoring, manage Docker, store telemetry or require credentials.

The source in `server.py` is currently pinned to Hypershell's private OCI deployment: bind `10.42.0.129:8197`, local Gatus at `127.0.0.1:3001`, and an explicit client allowlist. It serves three fixed routes, `/general`, `/development`, and `/health`. This pinned source is reusable for other deployments **after** changing the deployment-bound addresses, named endpoints and allowlist. Do not publicly expose the HTTP listener. The systemd unit and deployment lifecycle remain in the infrastructure repository.

The Homepage consumer uses each private bridge URL as a `siteMonitor`. This gives `Up` (HTTP liveness), **not** Docker `Healthy`. Docker health status requires a separate Docker provider; avoid exposing a Docker API proxy to an additional host without evaluating inspection/secret metadata access.

If a secure, least-privilege OCI Docker-health backend replaces this bridge, retire the deployed service and Homepage consumer references together. The Resources source may remain as a reference if still useful; do not keep an unnecessary running service.

For source checks, run `python3 -m py_compile server.py`. Expected semantics: fresh success 200, failure/stale/missing 503, disallowed client 403, unknown route 404.
