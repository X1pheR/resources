#!/usr/bin/env python3
"""Private, read-only Homebox SQLite aggregate for Homepage (stdlib only)."""
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("HOMEBOX_DB_PATH", "/data/homebox.db")
BIND = os.environ.get("LISTEN_ADDRESS", "127.0.0.1")
PORT = int(os.environ.get("LISTEN_PORT", "8196"))


def inventory_summary(path=DB_PATH):
    # Read only live committed data, including SQLite WAL, without accessing
    # inventory names, attachments, private descriptions, sessions or tokens.
    uri = "file:" + os.path.abspath(path) + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=2) as db:
        db.execute("PRAGMA query_only=ON")
        items, locations = db.execute("""
            SELECT
              COALESCE(SUM(CASE WHEN t.is_location = 0 THEN 1 ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN t.is_location = 1 THEN 1 ELSE 0 END),0)
            FROM entities e JOIN entity_types t ON t.id=e.entity_type_entities
        """).fetchone()
        tags = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        warranties = db.execute("""
            SELECT COUNT(*)
            FROM entities e JOIN entity_types t ON t.id=e.entity_type_entities
            WHERE t.is_location=0
              AND (e.warranty_expires IS NOT NULL OR e.lifetime_warranty=1)
        """).fetchone()[0]
    return {"items": items, "locations": locations, "tags": tags, "warranties": warranties}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path != "/summary":
            return self.respond(404, {"error": "not_found"})
        try:
            return self.respond(200, inventory_summary())
        except (sqlite3.Error, OSError, ValueError):
            # Do not expose DB path or sensitive database errors to consumers.
            return self.respond(503, {"error": "data_unavailable"})

    def respond(self, code, data):
        payload = (json.dumps(data, separators=(",", ":")) + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever(poll_interval=0.5)
