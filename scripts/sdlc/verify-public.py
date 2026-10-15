#!/usr/bin/env python3
"""Public-only checkout verification of a checksummed checker artifact."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent
checker = root / "sdlc-conformance.py"
expected = (root / "SHA256SUMS").read_text().split()[0]
assert hashlib.sha256(checker.read_bytes()).hexdigest() == expected

with tempfile.TemporaryDirectory() as temp:
    repo = Path(temp) / "downstream"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "hypershell.json").write_text(json.dumps({
        "schema_version": 1, "name": "Public fixture",
        "category": "Infrastructure", "kind": "tool",
        "upstream": {"repository": "vendor/project", "reason": "fixture"}
    }))
    patch = {
        "id": "PF-P01", "kind": "upstream", "scope": "Portable behavior",
        "local_commits": ["abc1234"],
        "checked_on": datetime.date.today().isoformat(),
        "issue": "https://github.com/vendor/project/issues/1",
        "pr": "https://github.com/vendor/project/pull/2", "pr_state": "open",
    }
    def write_register():
        body = json.dumps({"schema_version": 1, "upstream": "vendor/project",
                           "baseline": "v1", "patches": [patch]})
        (repo / "UPSTREAM.md").write_text(
            "<!-- SDLC-UPSTREAM-REGISTER:1 -->\n" + "```json\n" + body + "\n```\n"
        )
    def run():
        return subprocess.run([sys.executable, str(checker), "--public-repo",
                               str(repo), "--json"], capture_output=True, text=True)
    write_register()
    good = run()
    assert good.returncode == 0, (good.stderr, good.stdout)
    patch["issue"] = None
    write_register()
    bad = run()
    assert bad.returncode == 1 and "downstream.patch_unlinked" in bad.stdout
    deny = subprocess.run([sys.executable, str(checker), "--public-repo",
                           str(repo), "--root", str(Path(temp) / "private")],
                          capture_output=True, text=True)
    assert deny.returncode == 2 and "does not accept private estate" in deny.stderr

print("PUBLIC_DISTRIBUTION_CONTRACT_PASS")
