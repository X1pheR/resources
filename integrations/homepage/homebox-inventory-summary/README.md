# Homebox inventory summary for Homepage

Tiny read-only Python 3.12+ HTTP publisher for [Homebox](https://github.com/sysadminsmedia/homebox)
with SQLite storage. No dependencies or tokens. Use on a private network only.

GET /summary returns exactly four aggregate counts: items, locations, tags,
warranties. This implementation counts item/location entities by entity type,
and warranty-bearing items by expiry or lifetime warranty. It never exposes
names, values, prices, identifiers, descriptions, users or attachments.

GET /health reports publisher liveness; DB access failures return HTTP 503.

Environment:
- HOMEBOX_DB_PATH: absolute path to the Homebox SQLite database.
- LISTEN_ADDRESS: private interface IP (default 127.0.0.1).
- LISTEN_PORT: private TCP port (default 8196).

Production: run unprivileged with read-only access to the SQLite DB and WAL,
hardening enabled, no host-wide Docker socket or public reverse-proxy. Homepage
needs only internal HTTP reachability:

    widget:
      type: customapi
      url: http://PRIVATE-HOMEBOX-SUMMARY:8196/summary
      refreshInterval: 30000
      mappings:
        - field: items
          label: Items
        - field: locations
          label: Locations
        - field: tags
          label: Tags
        - field: warranties
          label: Warranties

Run tests: python3 -m unittest discover -s tests -v
