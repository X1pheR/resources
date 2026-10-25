#!/usr/bin/env python3
"""Reusable, privacy-safe Chromium/MCP/process status API for Homepage."""
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BROWSER_URL = os.environ.get("CDP_HTTP_URL", "http://127.0.0.1:9222").rstrip("/")
MCP_URL = os.environ.get("MCP_HTTP_URL", "")
MCP_HOST_HEADER = os.environ.get("MCP_HOST_HEADER", "localhost:8933")
PROCESS_NAME = os.environ.get("WATCH_PROCESS", "")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
PORT = int(os.environ.get("LISTEN_PORT", "8944"))
TIMEOUT = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "2"))


def get_json(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        return json.load(response)


def process_running(name):
    """Only inspect process comm, never arguments, environment, or session files."""
    if not name:
        return None
    try:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit():
                continue
            try:
                with open(f"/proc/{entry.name}/comm", encoding="utf-8") as handle:
                    if handle.read().strip().lower() == name.lower():
                        return True
            except (OSError, UnicodeError):
                continue
        return False
    except OSError:
        return None


def mcp_responding():
    # Use the same low-impact readiness shape as the existing sidecar healthcheck.
    # 400 indicates the allowlisted MCP endpoint rejected our intentionally
    # incomplete request. 403 (unallowlisted Host) and 5xx are NOT healthy.
    if not MCP_URL:
        return False
    request = urllib.request.Request(
        MCP_URL,
        data=b"{}",
        headers={
            "Host": MCP_HOST_HEADER,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status in (200, 202, 204, 400)
    except urllib.error.HTTPError as error:
        return error.code == 400
    except (OSError, ValueError):
        return False


def summary():
    browser = "Offline"
    tabs = None
    try:
        version = get_json(f"{BROWSER_URL}/json/version")
        targets = get_json(f"{BROWSER_URL}/json/list")
        if isinstance(version, dict) and isinstance(targets, list):
            browser = "Ready"
            # CDP type=page is our explicit definition of "Open tabs".
            # Never return titles, URLs, target IDs or debugger websocket URLs.
            tabs = sum(isinstance(item, dict) and item.get("type") == "page"
                       for item in targets)
    except (OSError, ValueError, KeyError):
        pass
    watched_process = process_running(PROCESS_NAME)
    mcp_state = ("Not configured" if not MCP_URL else
                 "Healthy" if browser == "Ready" and mcp_responding() else "Unavailable")
    return {
        "browser": browser,
        "open_tabs": tabs,
        "mcp": mcp_state,
        "process": "Running" if watched_process else ("Stopped" if watched_process is False else "Unknown"),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ok"})
        elif self.path == "/summary":
            self.respond(200, summary())
        else:
            self.respond(404, {"error": "Not Found"})

    def respond(self, status, payload):
        data = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer((LISTEN_HOST, PORT), Handler).serve_forever(poll_interval=0.5)
