# Chromium desktop status for Homepage

A small reusable dependency-free Python integration for the Homepage Custom API
widget. It reads a Chromium CDP discovery endpoint, optionally probes an
allowlisted MCP HTTP endpoint and optionally reports a named Linux process.
The interface never returns tab titles, URLs, target identifiers, passwords,
session data or command lines. It is intended for private networks only.

## API

GET /summary returns four fields:

    {"browser":"Ready","open_tabs":9,"mcp":"Healthy","process":"Running"}

- browser: Ready or Offline, based on read-only Chromium CDP discovery.
- open_tabs: count of CDP type=page targets; null if CDP is unavailable.
  Some popup windows also count. Browser UI and serviceworkers do not.
- mcp: Healthy or Unavailable if configured; otherwise Not configured.
  Healthy indicates a reachable endpoint plus CDP, not an arbitrary MCP tool.
- process: Running or Stopped if WATCH_PROCESS is set, otherwise Unknown.
  It checks Linux process comm names, not window/Discord functionality.

GET /health is publisher liveness and deliberately does not depend on CDP.

## Configuration

Environment variable | Default | Description
--- | --- | ---
CDP_HTTP_URL | http://127.0.0.1:9222 | Read-only, private CDP
MCP_HTTP_URL | empty | Optional private MCP URL
MCP_HOST_HEADER | localhost:8933 | MCP allowed-host header
WATCH_PROCESS | empty | Optional Linux comm process name
LISTEN_HOST | 0.0.0.0 | HTTP listener (private network only)
LISTEN_PORT | 8944 | HTTP port
PROBE_TIMEOUT_SECONDS | 2 | Per-upstream timeout

Run with Python 3.12+ (stdlib only):

    python3 -B server.py

## Deployment

See compose.example.yaml for a sidecar running in the same network namespace
as an existing desktop. Share the PID namespace only when using the optional
process check. Keep the CDP listener on loopback; do not publish port 9222 or
8944 to LAN/internet, grant Docker socket access, or mount a browser profile.
Make the HTTP read model reachable only on a controlled private network.
Homepage's existing Docker server/container fields continue to provide
container state and health independently.

Example Homepage widget addition to an existing service card:

    widget:
      type: customapi
      url: http://YOUR-DESKTOP:8944/summary
      method: GET
      refreshInterval: 30000
      mappings:
        - field: browser
          label: Browser
        - field: open_tabs
          label: Open tabs
        - field: mcp
          label: Automation
        - field: process
          label: App

The labels are deliberately consumer-owned: label Automation as Playwright
and App as Discord when those are your actual configured services. No
additional Homepage adapter is needed.

## Verification

    python3 -m unittest discover -s tests -p 'test_*.py' -v
    python3 -m py_compile server.py
    docker compose -f compose.example.yaml config --quiet

Test the summary and the rendered Homepage card before accepting a deployment.
Only restart the new telemetry sidecar on updates; preserve existing browser
sessions and human-operated desktop containers.
