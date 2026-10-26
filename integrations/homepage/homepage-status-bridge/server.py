#!/usr/bin/env python3
"""Private Homepage adapter for Gatus readiness and narrowly filtered Docker health."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

HOST = os.getenv("HOMEPAGE_STATUS_BIND", "10.42.0.129")
PORT = int(os.getenv("HOMEPAGE_STATUS_PORT", "8197"))
GATUS = os.getenv("HOMEPAGE_GATUS_URL", "http://127.0.0.1:3001")
DOCKER_PROXY = os.getenv("HOMEPAGE_DOCKER_PROXY", "http://127.0.0.1:2377")
CLIENTS = set(os.getenv("HOMEPAGE_STATUS_CLIENTS", "192.168.18.3,10.255.42.1,10.42.0.129").split(","))
# An empty allowlist must never permit enumeration.
DOCKER_CONTAINERS = set(filter(None, os.getenv("HOMEPAGE_DOCKER_CONTAINERS", "").split(",")))
TUNNELS = {
    "/general": "mcp-tunnels_hypershell-general",
    "/development": "mcp-tunnels_hypershell-development",
    "/health": "mcp-tunnels_hypershell-health",
}
MAX_SAMPLE_AGE = 120
HEALTH_STATES = {"healthy", "unhealthy", "starting"}
DOCKER_LIST = re.compile(r"^(?:/v[0-9]+\.[0-9]+)?/containers/json$")


def latest_status(slug, fetch=None, now=None):
    fetch = fetch or (lambda url: json.load(urlopen(url, timeout=3)))
    data = fetch(f"{GATUS}/api/v1/endpoints/{slug}/statuses")
    results = data.get("results", [])
    if not results:
        return False
    last = results[-1]
    timestamp = last.get("timestamp", "")
    if "." in timestamp and timestamp.endswith("Z"):
        main, fraction = timestamp[:-1].split(".", 1)
        timestamp = main + "." + fraction[:6] + "+00:00"
    sampled = datetime.fromisoformat(timestamp)
    if sampled.tzinfo is None:
        return False
    current = now or datetime.now(timezone.utc)
    age = (current - sampled).total_seconds()
    return -30 <= age <= MAX_SAMPLE_AGE and last.get("success") is True


def parse_docker_filter(query):
    """Only the actual Homepage v2.7.0 listContainers filter syntax is supported."""
    params = parse_qs(query, strict_parsing=True, keep_blank_values=True)
    if not set(params) <= {"all", "filters"} or any(len(v) != 1 for v in params.values()):
        raise ValueError("Unsupported Docker query")
    if "all" in params and params["all"][0] not in {"1", "true"}:
        raise ValueError("Unsupported Docker list mode")
    if "filters" not in params:
        return None
    filters = json.loads(params["filters"][0])
    if not isinstance(filters, dict) or set(filters) != {"health"}:
        raise ValueError("Unsupported Docker filter")
    states = filters["health"]
    if not isinstance(states, list) or not states or not all(isinstance(x, str) and x in HEALTH_STATES for x in states):
        raise ValueError("Unsupported health state")
    return set(states)


def docker_list(query, fetch=None, allowlist=None):
    """Expose only ID, exact name, running state and no labels. No inspect/env/mounts."""
    health_filter = parse_docker_filter(query)
    names = DOCKER_CONTAINERS if allowlist is None else allowlist
    if not names:
        raise ValueError("Docker container allowlist is empty")
    fetch = fetch or (lambda url: json.load(urlopen(url, timeout=3)))
    containers = fetch(f"{DOCKER_PROXY}/containers/json?all=1")
    if not isinstance(containers, list):
        raise ValueError("Invalid backend response")
    output = []
    for container in containers:
        matches = [n for n in container.get("Names", []) if n.startswith("/") and n[1:] in names]
        if not matches:
            continue
        state = container.get("State")
        ident = container.get("Id")
        if not isinstance(state, str) or not isinstance(ident, str) or not re.fullmatch("[0-9a-f]{64}", ident):
            raise ValueError("Invalid container identity")
        status = container.get("Health", {})
        health = status.get("Status") if isinstance(status, dict) else None
        if health_filter is not None and health not in health_filter:
            continue
        output.append({"Id": ident, "Names": matches, "State": state, "Labels": {}})
    return output


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.client_address[0] not in CLIENTS:
            self.respond(403, b"forbidden")
            return
        url = urlsplit(self.path)
        if url.path in TUNNELS and not url.query:
            try:
                ready = latest_status(TUNNELS[url.path])
            except (ValueError, KeyError, TimeoutError, OSError, TypeError):
                ready = False
            self.respond(200 if ready else 503, b"ready" if ready else b"unhealthy")
            return
        if DOCKER_LIST.fullmatch(url.path):
            try:
                result = docker_list(url.query)
            except (ValueError, KeyError):
                self.respond(400, b"invalid request or backend response")
                return
            except (TimeoutError, OSError, TypeError):
                self.respond(503, b"upstream unavailable")
                return
            self.respond(200, json.dumps(result, separators=(",", ":")).encode("utf-8"), "application/json")
            return
        self.respond(404, b"not found")

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
