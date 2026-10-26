#!/usr/bin/env python3
"""Private, read-only Homepage status adapter over existing OCI Gatus measurements."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
from urllib.request import urlopen

HOST = "10.42.0.129"
PORT = 8197
GATUS = "http://127.0.0.1:3001"
CLIENTS = {"192.168.18.3", "10.255.42.1", "10.42.0.129"}
TUNNELS = {
    "/general": "mcp-tunnels_hypershell-general",
    "/development": "mcp-tunnels_hypershell-development",
    "/health": "mcp-tunnels_hypershell-health",
}
MAX_SAMPLE_AGE = 120


def latest_status(slug, fetch=None, now=None):
    fetch = fetch or (lambda url: json.load(urlopen(url, timeout=3)))
    data = fetch(f"{GATUS}/api/v1/endpoints/{slug}/statuses")
    results = data.get("results", [])
    if not results:
        return False
    last = results[-1]
    timestamp = last.get("timestamp", "")
    # Gatus emits nanoseconds; datetime supports microseconds.
    if "." in timestamp and timestamp.endswith("Z"):
        main, fraction = timestamp[:-1].split(".", 1)
        timestamp = main + "." + fraction[:6] + "+00:00"
    sampled = datetime.fromisoformat(timestamp)
    if sampled.tzinfo is None:
        return False
    current = now or datetime.now(timezone.utc)
    age = (current - sampled).total_seconds()
    return -30 <= age <= MAX_SAMPLE_AGE and last.get("success") is True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0] not in CLIENTS:
            self.send_error(403)
            return
        if self.path not in TUNNELS:
            self.send_error(404)
            return
        try:
            ready = latest_status(TUNNELS[self.path])
        except (ValueError, KeyError, TimeoutError, OSError, TypeError):
            ready = False
        body = b"ready" if ready else b"unhealthy"
        self.send_response(200 if ready else 503)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    HTTPServer((HOST, PORT), Handler).serve_forever()
