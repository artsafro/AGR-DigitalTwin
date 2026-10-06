"""pre-commit: commit large NEW files as links instead of content.

A newly added file above the threshold is unstaged (it stays on disk), hidden
from git via .git/info/exclude, and recorded in docs/sources/linked-files.json
with size and SHA-256. Everything else commits normally (binaries via LFS).

Toggle: git config twin.linkLarge true|false (default true)
Size:   git config twin.linkLargeMb <MB>      (default 50)
Already-tracked files are never unstaged; above the threshold they only warn.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import date

MANIFEST = "docs/sources/linked-files.json"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def config(key, default):
    return git("config", "--get", key) or default


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if config("twin.linkLarge", "true").lower() in ("false", "0", "off", "no"):
        return 0
    limit = float(config("twin.linkLargeMb", "50")) * 1024 * 1024
    top = git("rev-parse", "--show-toplevel")
    main_root = os.path.dirname(os.path.abspath(git("rev-parse", "--git-common-dir")))
    staged = git("diff", "--cached", "--name-only", "--diff-filter=AM", "-z").split("\0")
    added = set(git("diff", "--cached", "--name-only", "--diff-filter=A", "-z").split("\0"))

    linked = []
    for rel in filter(None, staged):
        path = os.path.join(top, rel)
        if not os.path.isfile(path) or os.path.getsize(path) <= limit:
            continue
        if rel not in added:
            print(f"link-large: {rel} is tracked and over the limit; committed as is.", file=sys.stderr)
            continue
        linked.append(rel)

    if not linked:
        return 0

    manifest_path = os.path.join(top, MANIFEST)
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        manifest = {"note": "Large files kept out of git; read them at 'location'.", "files": {}}

    exclude = os.path.join(git("rev-parse", "--git-common-dir"), "info", "exclude")
    with open(exclude, encoding="utf-8") as f:
        excluded = set(line.strip() for line in f)

    for rel in linked:
        path = os.path.join(top, rel)
        # No copy: drive C is nearly full. A file linked from a worktree lives only there,
        # so warn that it must be moved before that worktree is removed.
        if os.path.normcase(os.path.abspath(top)) != os.path.normcase(main_root):
            print(f"link-large: {rel} stays in this worktree ({top}); move it to "
                  f"{os.path.join(main_root, rel)} before removing the worktree.", file=sys.stderr)
        manifest["files"][rel] = {
            "location": os.path.normpath(path),
            "size_bytes": os.path.getsize(path),
            "sha256": sha256(path),
            "linked": date.today().isoformat(),
        }
        subprocess.run(["git", "rm", "--cached", "-q", "--", rel], check=True)
        if "/" + rel not in excluded:
            with open(exclude, "a", encoding="utf-8") as f:
                f.write(f"/{rel}\n")
        print(f"link-large: {rel} ({os.path.getsize(path) / 1048576:.0f} MB) -> link in {MANIFEST}",
              file=sys.stderr)

    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    subprocess.run(["git", "add", "--", MANIFEST], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
