"""Read-only Git/worktree inventory for deciding what belongs in the repository."""
import argparse
import hashlib
import json
import stat
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


PROMOTE_ROOTS = {
    ".cursor", "adapters", "benchmark", "docs", "schemas", "src", "standards",
    "technical_library", "tests", "tools",
}
TEXT_EXTENSIONS = {
    ".bat", ".cmd", ".cs", ".csv", ".ini", ".json", ".md", ".mdc", ".ms",
    ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml",
}
LOCAL_SEGMENTS = {
    ".pytest_cache", "__pycache__", "build", "dist", "outputs", "runs", "tmp",
}
SENSITIVE_NAMES = {
    ".env", ".npmrc", ".pypirc", "credentials.json", "mcp.json", "secrets.json",
}
SENSITIVE_EXTENSIONS = {".key", ".p12", ".pem", ".pfx"}
SENSITIVE_NAME_PARTS = {
    "api-key", "apikey", "id_ed25519", "id_rsa", "passwd", "password", "private-key",
}
SENSITIVE_CONTENT_MARKERS = (
    b"-----begin private key", b"authorization: bearer ", b"api_key=", b"api-key:",
    b"client_secret=", b"password=",
)


def run_git(root, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=check)
    return result.stdout


def git_paths(root, *args):
    raw = run_git(root, *args)
    return [item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item]


def classify_path(path, size, max_file_bytes):
    item = PurePosixPath(path.replace("\\", "/"))
    lowered = {part.lower() for part in item.parts}
    name = item.name.lower()
    suffix = item.suffix.lower()
    if (name in SENSITIVE_NAMES or name.startswith(".env.") or
            suffix in SENSITIVE_EXTENSIONS or
            any(marker in name for marker in SENSITIVE_NAME_PARTS)):
        return "blocked_sensitive"
    if lowered & LOCAL_SEGMENTS or size > max_file_bytes:
        return "keep_local"
    if item.parts and item.parts[0] in PROMOTE_ROOTS and suffix in TEXT_EXTENSIONS:
        return "promote_candidate"
    return "review_candidate"


def is_link_or_reparse(stat_result):
    return bool(stat.S_ISLNK(stat_result.st_mode) or
                getattr(stat_result, "st_file_attributes", 0) & 0x400)


def contains_sensitive_content(path, size):
    if size > 1_000_000:
        return False
    content = path.read_bytes().lower()
    return any(marker in content for marker in SENSITIVE_CONTENT_MARKERS)


def duplicate_groups(root, paths, max_file_bytes):
    hashes = defaultdict(list)
    errors = []
    for relative in paths:
        path = root / relative
        try:
            stat_result = path.lstat()
            if is_link_or_reparse(stat_result):
                errors.append({"path": relative, "error": "symlink or reparse point not hashed"})
                continue
            size = stat_result.st_size
            if size <= max_file_bytes and path.is_file():
                hashes[hashlib.sha256(path.read_bytes()).hexdigest()].append(relative)
        except OSError as error:
            errors.append({"path": relative, "error": str(error)})
    groups = [
        {"sha256": digest, "paths": sorted(group)}
        for digest, group in hashes.items() if len(group) > 1
    ]
    return groups, errors


def build_report(root, max_file_bytes):
    root = root.resolve()
    head = run_git(root, "rev-parse", "HEAD").decode().strip()
    branch = run_git(root, "branch", "--show-current").decode().strip()
    upstream = run_git(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}",
        check=False).decode().strip() or None
    origin_main = run_git(
        root, "rev-parse", "--verify", "refs/remotes/origin/main",
        check=False).decode().strip() or None
    tracked = sorted(set(
        git_paths(root, "diff", "--name-only", "-z") +
        git_paths(root, "diff", "--cached", "--name-only", "-z")))
    untracked = sorted(git_paths(root, "ls-files", "--others", "--exclude-standard", "-z"))
    ignored = git_paths(
        root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    classified = defaultdict(list)
    errors = []
    for relative in untracked:
        try:
            path = root / relative
            stat_result = path.lstat()
            size = stat_result.st_size
            if is_link_or_reparse(stat_result):
                classified["review_link"].append({"path": relative, "bytes": size})
                continue
            kind = classify_path(relative, size, max_file_bytes)
            if kind not in {"blocked_sensitive", "keep_local"} and contains_sensitive_content(path, size):
                kind = "review_sensitive_content"
            classified[kind].append({"path": relative, "bytes": size})
        except OSError as error:
            errors.append({"path": relative, "error": str(error)})
    ignored_roots = Counter(PurePosixPath(path.replace("\\", "/")).parts[0] for path in ignored)
    divergence = None
    if origin_main:
        counts = run_git(
            root, "rev-list", "--left-right", "--count", "HEAD...origin/main",
            check=False).decode().strip().split()
        if len(counts) == 2:
            divergence = {"ahead": int(counts[0]), "behind": int(counts[1])}
    duplicates, duplicate_errors = duplicate_groups(root, untracked, max_file_bytes)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only local Git inventory; no files staged, moved, deleted, committed or pushed",
        "repository": str(root),
        "git": {
            "branch": branch,
            "head": head,
            "upstream": upstream,
            "origin_main": origin_main,
            "origin_main_divergence": divergence,
        },
        "tracked_changes": tracked,
        "untracked": {name: items for name, items in sorted(classified.items())},
        "ignored": {"count": len(ignored), "top_level_counts": dict(sorted(ignored_roots.items()))},
        "exact_untracked_duplicates": duplicates,
        "duplicate_scan_errors": duplicate_errors,
        "errors": errors,
        "policy": {
            "promote_candidate": "Candidate only; review provenance, content and scope before staging.",
            "review_candidate": "Require provenance, purpose and acceptance scope before Git.",
            "review_link": "Do not follow automatically; resolve and approve the in-repository source.",
            "review_sensitive_content": "Possible credential marker; inspect locally and never publish the value.",
            "keep_local": "Keep generated, large or transient data outside ordinary Git.",
            "blocked_sensitive": "Never stage; remove secrets from the candidate set.",
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-file-bytes", type=int, default=5_000_000)
    args = parser.parse_args()
    report = build_report(Path(args.root), args.max_file_bytes)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "tracked_changes": len(report["tracked_changes"]),
        "untracked": sum(len(items) for items in report["untracked"].values()),
        "ignored": report["ignored"]["count"],
        "duplicate_groups": len(report["exact_untracked_duplicates"]),
        "errors": len(report["errors"]) + len(report["duplicate_scan_errors"]),
        "output": str(output),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
