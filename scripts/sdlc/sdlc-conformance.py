#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ronald de Wit
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Read-only cross-estate SDLC structural conformance.

Pre-first-release maintained source belongs under ``repos/local`` and is
intentionally non-Git. Released products live under the provider root as Git
repositories with a recognizable publication remote. The checker derives
ordinary facts from filesystem and Git without turning runtime copies into a
second source authority.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(os.environ.get("HYPERSHELL_ROOT", "/srv/hypershell"))
DEFAULT_EXCEPTIONS = Path(__file__).with_name("sdlc-exceptions.v1.json")
VERIFIER_FILES = ("scripts/verify.sh", "scripts/test.sh", "tests/run.sh")
NON_SOFTWARE_REPOSITORIES = {"hypershell-infrastructure", "resources", "hypershell-brand"}
PRODUCT_CATEGORIES = {"Agentic AI", "Applications", "Infrastructure", "Identity & Resilience", "Knowledge", "Operations"}
PRODUCT_KINDS = {"application", "mcp-server", "service", "tool", "library", "website"}

def _metadata_error(path: Path) -> str | None:
    metadata = path / "hypershell.json"
    if not metadata.is_file():
        return "Maintained software requires root hypershell.json for product discovery and publication."
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"Invalid hypershell.json: {type(exc).__name__}"
    mandatory = {"schema_version", "name", "category", "kind"}
    if not isinstance(data, dict) or not mandatory <= data.keys() or data.keys() - (mandatory | {"upstream"}):
        return "hypershell.json must contain required keys and no unsupported attributes."
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        return "hypershell.json requires schema_version 1."
    if not isinstance(data["name"], str) or not data["name"].strip():
        return "hypershell.json name must be non-empty."
    if data["category"] not in PRODUCT_CATEGORIES or data["kind"] not in PRODUCT_KINDS:
        return "hypershell.json category or kind is not canonical."
    if "upstream" in data:
        upstream = data["upstream"]
        if not isinstance(upstream, dict) or set(upstream) != {"repository", "reason"}:
            return "hypershell.json upstream must contain exactly repository and reason."
        if not isinstance(upstream["repository"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", upstream["repository"]):
            return "hypershell.json upstream.repository must be owner/repository."
        if not isinstance(upstream["reason"], str) or not upstream["reason"].strip():
            return "hypershell.json upstream.reason must be non-empty."
    return None

GITHUB_REMOTE_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    re.IGNORECASE,
)

@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str
    disposition: str = "active"

    @property
    def blocking(self) -> bool:
        return self.disposition == "active"


def _run_git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={path}", "-C", str(path), *args],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def _git_repo(path: Path) -> bool:
    result = _run_git(path, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def _origin(path: Path) -> str | None:
    result = _run_git(path, "remote", "get-url", "origin")
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _github_identity(remote: str | None) -> str | None:
    if not remote:
        return None
    match = GITHUB_REMOTE_RE.match(remote.strip())
    if not match:
        return None
    return f"{match.group('owner').lower()}/{match.group('repo').lower()}"


def _has_package_verify(path: Path) -> bool:
    package = path / "package.json"
    if not package.is_file():
        return False
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = data.get("scripts")
    return isinstance(scripts, dict) and isinstance(scripts.get("verify"), str) and bool(scripts["verify"].strip())


def _detect_verifier(path: Path) -> str | None:
    for rel in VERIFIER_FILES:
        if (path / rel).is_file():
            return rel
    if _has_package_verify(path):
        return "package.json#scripts.verify"
    return None


def _load_exceptions(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read exception metadata: {exc}") from exc
    if data.get("schema_version") != 1:
        raise ValueError("exception metadata schema_version must be 1")
    repos = data.get("repositories", {})
    stacks = data.get("docker_stacks", {})
    if not isinstance(repos, dict) or not isinstance(stacks, dict):
        raise ValueError("repositories and docker_stacks must be objects")
    for key, value in repos.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError("repository exceptions must be object entries")
        if value.get("disposition") not in {"delegated", "active"}:
            raise ValueError(f"invalid repository disposition for {key}")
    for key, value in stacks.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError("docker stack exceptions must be object entries")
        if value.get("disposition") not in {"delegated", "active"}:
            raise ValueError(f"invalid docker stack disposition for {key}")
    return data


def _repo_disposition(identity: str | None, exceptions: dict[str, Any]) -> str:
    if identity is None:
        return "active"
    entry = exceptions["repositories"].get(identity.lower())
    return entry.get("disposition", "active") if isinstance(entry, dict) else "active"


# This inline register belongs to each product UPSTREAM.md, not to a new estate registry.
UPSTREAM_MARKER = "<!-- SDLC-UPSTREAM-REGISTER:1 -->"
UPSTREAM_REGISTER_RE = re.compile(re.escape(UPSTREAM_MARKER) + r"\s*```json\s*\n(.*?)\n```", re.DOTALL)


def _upstream_link(value: object, repository: str, kind: str) -> bool:
    if not isinstance(value, str):
        return False
    pattern = rf"https://github\.com/{re.escape(repository)}/{kind}/[1-9][0-9]*"
    return re.fullmatch(pattern, value, re.IGNORECASE) is not None


def _review_age_invalid(value: object, today: date) -> bool:
    try:
        checked = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return True
    return checked is None or checked > today or (today - checked) > timedelta(days=30)


def _divergence_approved(patch: dict[str, Any], root: Path, today: date) -> bool:
    ref = patch.get("adr")
    approval = patch.get("approval_ref")
    if not isinstance(ref, str) or not ref.startswith("knowledge/products/") or "/adr/" not in ref:
        return False
    if not isinstance(approval, str) or not approval.strip():
        return False
    vault = (root / "vaults/hypershell").resolve()
    candidate = (vault / ref).resolve()
    if not candidate.is_relative_to(vault) or not candidate.is_file():
        return False
    try:
        content = candidate.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            return False
        import yaml
        data = yaml.safe_load(content.split("---", 2)[1])
        if not isinstance(data, dict):
            return False
        review = data.get("review_due")
        if isinstance(review, date):
            deadline = review
        elif isinstance(review, str):
            deadline = date.fromisoformat(review)
        else:
            return False
        return (data.get("status") == "accepted"
                and data.get("operator_approval_ref") == approval
                and patch["id"] in data.get("approved_patch_ids", [])
                and data.get("approved_scope") == patch.get("scope")
                and deadline >= today)
    except (OSError, ValueError, ImportError, TypeError, KeyError):
        return False


def _downstream_findings(path: Path, root: Path, upstream: str, *, allow_divergence: bool = True) -> list[Finding]:
    subject = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    doc = path / "UPSTREAM.md"
    if not doc.is_file():
        return [Finding("downstream.tracking_missing", subject, "Maintained Downstream has no UPSTREAM.md.")]
    try:
        content = doc.read_text(encoding="utf-8")
    except OSError:
        return [Finding("downstream.register_invalid", subject, "UPSTREAM.md is unreadable.")]
    match = UPSTREAM_REGISTER_RE.search(content)
    if not match:
        return [Finding("downstream.register_missing", subject, "UPSTREAM.md lacks the versioned inline JSON patch register.")]
    if len(UPSTREAM_REGISTER_RE.findall(content)) != 1:
        return [Finding("downstream.register_invalid", subject, "UPSTREAM.md contains multiple patch registers.")]
    try:
        register = json.loads(match.group(1))
    except ValueError:
        register = None
    if (not isinstance(register, dict) or set(register) != {"schema_version", "upstream", "baseline", "patches"}
        or type(register["schema_version"]) is not int or register["schema_version"] != 1
        or not isinstance(register["upstream"], str) or register["upstream"].lower() != upstream.lower()
        or not isinstance(register["baseline"], str) or not register["baseline"].strip()
        or not isinstance(register["patches"], list) or not register["patches"]):
        return [Finding("downstream.register_invalid", subject, "Patch register shape, upstream identity, baseline or non-empty patch list is invalid.")]
    findings: list[Finding] = []
    today = date.today()
    seen: set[str] = set()
    for row in register["patches"]:
        if not isinstance(row, dict):
            findings.append(Finding("downstream.patch_record_invalid", subject, "Patch must be an object."))
            continue
        pid, kind = row.get("id"), row.get("kind")
        if (not isinstance(pid, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*-[PD][0-9]{2,}", pid)
            or pid in seen or kind not in ("upstream", "divergence")
            or not isinstance(row.get("scope"), str) or not row["scope"].strip()
            or not isinstance(row.get("local_commits"), list) or not row["local_commits"]
            or not all(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit) for commit in row["local_commits"])):
            findings.append(Finding("downstream.patch_record_invalid", subject, f"Invalid or duplicate patch row: {pid!r}."))
            continue
        seen.add(pid)
        if _review_age_invalid(row.get("checked_on"), today):
            findings.append(Finding("downstream.review_stale", f"{subject}:{pid}", "Patch review is missing, invalid, future-dated or older than 30 days."))
        if kind == "upstream":
            if not (_upstream_link(row.get("issue"), upstream, "issues")
                    and _upstream_link(row.get("pr"), upstream, "pull")):
                findings.append(Finding("downstream.patch_unlinked", f"{subject}:{pid}", "Retained generic patch lacks an upstream repository issue and linked pull request URL."))
            elif row.get("pr_state") not in ("open", "draft", "merged", "released"):
                findings.append(Finding("downstream.pr_inactive", f"{subject}:{pid}", "Upstream PR is closed-unmerged, rejected, or has no explicitly verified current lifecycle state."))
        elif not allow_divergence or not _divergence_approved(row, root, today):
            findings.append(Finding("downstream.divergence_unapproved", f"{subject}:{pid}", "Divergence lacks a current scope-matching accepted product ADR and explicit operator approval reference."))
    return findings


def _direct_children(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted((item for item in path.iterdir() if item.is_dir() and not item.name.startswith(".")), key=lambda p: p.name)


def check(root: Path, exceptions_path: Path) -> tuple[list[Finding], dict[str, int]]:
    exceptions = _load_exceptions(exceptions_path)
    findings: list[Finding] = []
    github_root = root / "repos/github/X1pheR"
    local_root = root / "repos/local"
    local_infra = local_root / "hypershell-infrastructure"
    released_infra = github_root / "hypershell-infrastructure"
    if local_infra.is_dir() and released_infra.is_dir():
        findings.append(Finding(
            "repository.infrastructure_dual_authority",
            "hypershell-infrastructure",
            "Both pre-first-release and released infrastructure source roots exist; complete or roll back the source-authority handoff before accepting SDLC conformance.",
        ))
    infra = released_infra if released_infra.is_dir() else local_infra
    stack_root = root / "stacks/docker"

    repositories: list[tuple[Path, str | None, str]] = []
    for path in _direct_children(github_root):
        if not _git_repo(path):
            findings.append(Finding("repository.not_git", str(path.relative_to(root)), "Released repository directory under repos/github is not a Git worktree."))
            continue
        remote = _origin(path)
        identity = _github_identity(remote)
        disposition = _repo_disposition(identity, exceptions)
        repositories.append((path, identity, disposition))
        canonical_location = identity is not None
        if identity is None:
            findings.append(Finding("repository.origin_missing_or_unrecognized", str(path.relative_to(root)), "Released repository under the GitHub provider root has no recognizable GitHub origin."))
        else:
            owner, repo = identity.split("/", 1)
            owner_dir = github_root.name if owner == github_root.name.lower() else owner
            expected = root / "repos/github" / owner_dir / repo
            if path.resolve() != expected.resolve():
                canonical_location = False
                findings.append(Finding("repository.noncanonical_checkout", str(path.relative_to(root)), f"GitHub origin {identity} belongs at {expected.relative_to(root)}.", disposition))
        if canonical_location and _detect_verifier(path) is None:
            findings.append(Finding("repository.verifier_missing", str(path.relative_to(root)), "No recognized repository-owned canonical verifier entrypoint was found.", disposition))
        if canonical_location and path.name not in NON_SOFTWARE_REPOSITORIES:
            metadata_error = _metadata_error(path)
            if metadata_error:
                findings.append(Finding("repository.product_metadata_invalid", str(path.relative_to(root)), metadata_error, disposition))
            else:
                data = json.loads((path / "hypershell.json").read_text(encoding="utf-8"))
                if "upstream" in data:
                    findings.extend(_downstream_findings(path, root, data["upstream"]["repository"]))

    local_non_git_sources = 0
    for path in _direct_children(local_root):
        if not _git_repo(path):
            local_non_git_sources += 1
            continue
        remote = _origin(path)
        identity = _github_identity(remote)
        disposition = _repo_disposition(identity, exceptions)
        repositories.append((path, identity, disposition))
        if identity:
            owner, repo = identity.split("/", 1)
            owner_dir = github_root.name if owner == github_root.name.lower() else owner
            expected = root / "repos/github" / owner_dir / repo
            findings.append(Finding("repository.noncanonical_checkout", str(path.relative_to(root)), f"Released GitHub origin {identity} is stored under repos/local; canonical released location is {expected.relative_to(root)}.", disposition))
        elif remote:
            findings.append(Finding("repository.external_remote_under_local", str(path.relative_to(root)), "Pre-first-release source under repos/local must not carry an external origin."))
        else:
            findings.append(Finding("repository.pre_release_git", str(path.relative_to(root)), "Pre-first-release source under repos/local must remain non-Git until an accepted first-release transition creates the released repository."))

    by_origin: dict[str, list[tuple[Path, str]]] = {}
    for path, identity, disposition in repositories:
        if identity:
            by_origin.setdefault(identity, []).append((path, disposition))
    for identity, entries in sorted(by_origin.items()):
        unique = {str(path.resolve()) for path, _ in entries}
        if len(unique) > 1:
            disposition = "delegated" if all(d == "delegated" for _, d in entries) else "active"
            subjects = ", ".join(str(path.relative_to(root)) for path, _ in entries)
            findings.append(Finding("repository.duplicate_origin", identity, f"Multiple persistent checkouts share this GitHub origin: {subjects}.", disposition))

    git_owned_stacks = {
        path.name for path in _direct_children(infra / "compose/docker")
        if (path / "compose.yaml").is_file()
    }
    stack_exceptions = exceptions["docker_stacks"]
    runtime_stacks = _direct_children(stack_root)
    stack_local_count = 0
    for path in runtime_stacks:
        name = path.name
        entry = stack_exceptions.get(name, {})
        disposition = entry.get("disposition", "active") if isinstance(entry, dict) else "active"
        compose_path = path / "compose.yaml"
        if name not in git_owned_stacks:
            if compose_path.is_file():
                stack_local_count += 1
            else:
                kind = "directory" if compose_path.is_dir() else "missing"
                findings.append(Finding("stack.compose_source_invalid", f"stacks/docker/{name}", f"Stack-local source cannot be inferred because compose.yaml is {kind}, not a regular file.", disposition))
        if _git_repo(path):
            findings.append(Finding("stack.embedded_git_source", f"stacks/docker/{name}", "A runtime stack directory is itself a Git worktree; this can create a second source authority unless explicitly delegated.", disposition))

    for name in sorted(stack_exceptions):
        if not (stack_root / name).is_dir():
            findings.append(Finding("exception.stale_stack", name, "Exception metadata names a Docker stack that no longer exists."))

    findings.sort(key=lambda item: (not item.blocking, item.code, item.subject))
    signals = {
        "repositories_observed": len(repositories),
        "github_repository_directories": len(_direct_children(github_root)),
        "local_non_git_sources": local_non_git_sources,
        "runtime_docker_stacks": len(runtime_stacks),
        "git_owned_docker_stacks": len(git_owned_stacks),
        "stack_local_docker_stacks": stack_local_count,
        "exception_docker_stacks": len(stack_exceptions),
    }
    return findings, signals


def _payload(findings: list[Finding], signals: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "fail" if any(item.blocking for item in findings) else "pass",
        "blocking_count": sum(1 for item in findings if item.blocking),
        "delegated_count": sum(1 for item in findings if not item.blocking),
        "signals": signals,
        "findings": [{**asdict(item), "blocking": item.blocking} for item in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTIONS)
    parser.add_argument("--json", action="store_true", dest="json_output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--downstream-repo", type=Path, help="Private Hypershell release gate for a governed downstream source tree.")
    mode.add_argument("--public-repo", type=Path, help="Public-only downstream source contract; no estate root, vault or private exceptions.")
    args = parser.parse_args(argv)
    try:
        if args.public_repo is not None and (args.root != DEFAULT_ROOT or args.exceptions != DEFAULT_EXCEPTIONS):
            raise ValueError("Public mode does not accept private estate root or exception overrides.")
        root = args.root.resolve() if args.public_repo is None else None
        if args.public_repo is not None:
            path = args.public_repo.resolve()
            if not path.is_dir() or not _git_repo(path):
                raise ValueError("Public downstream source must be an existing Git checkout.")
            metadata_error = _metadata_error(path)
            if metadata_error:
                findings = [Finding("repository.product_metadata_invalid", str(path), metadata_error)]
            else:
                data = json.loads((path / "hypershell.json").read_text(encoding="utf-8"))
                if "upstream" not in data:
                    findings = [Finding("downstream.not_maintained", str(path), "Public release source is not a Maintained Downstream.")]
                else:
                    # Never read private exception metadata or local vault ADRs in public mode.
                    # Divergences require independent private owner verification and thus fail closed.
                    findings = _downstream_findings(path, path, data["upstream"]["repository"], allow_divergence=False)
            signals = {"public_downstream_repositories_observed": 1}
        elif args.downstream_repo is None:
            findings, signals = check(root, args.exceptions.resolve())
        else:
            path = args.downstream_repo.resolve()
            published = path.is_relative_to(root / "repos/github")
            candidate = path.is_relative_to(root / "repos/worktrees")
            if not path.is_dir() or not (published or candidate):
                raise ValueError("Downstream release source must be a released checkout or governed worktree inside the supplied root.")
            if candidate and (not _git_repo(path) or not _github_identity(_origin(path))):
                raise ValueError("Release candidate worktree lacks a verifiable GitHub publication origin.")
            metadata_error = _metadata_error(path)
            if metadata_error:
                findings = [Finding("repository.product_metadata_invalid", str(path), metadata_error)]
            else:
                data = json.loads((path / "hypershell.json").read_text(encoding="utf-8"))
                if "upstream" not in data:
                    findings = [Finding("downstream.not_maintained", str(path), "Release path is not a Maintained Downstream.")]
                else:
                    findings = _downstream_findings(path, root, data["upstream"]["repository"])
            signals = {"downstream_repositories_observed": 1}
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload = _payload(findings, signals)
    if args.json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"SDLC estate conformance: {payload['status'].upper()} ({payload['blocking_count']} active, {payload['delegated_count']} delegated)")
        for item in findings:
            marker = "FAIL" if item.blocking else "INFO"
            print(f"[{marker}] {item.code}: {item.subject} — {item.detail}")
        print("Signals: " + ", ".join(f"{key}={value}" for key, value in sorted(signals.items())))
    return 1 if payload["blocking_count"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
