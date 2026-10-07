"""Pure preflight checks for KPP1 delivery runs (no Blender dependency)."""
import argparse
import os
from pathlib import Path
import re


def validate_version(version):
    """Allow one short filesystem token, never a path or shell expression."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", version):
        raise ValueError("Version must be a 1-64 character alphanumeric/underscore/hyphen token")
    return version


def require_delivery_mode(environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("KEEP_QUADS"):
        raise ValueError("KEEP_QUADS is a review mode; unset it before a delivery run")


def run_paths(outputs, version):
    validate_version(version)
    root = Path(outputs).absolute()
    return {name: root / f"{name}-{version}" for name in
            ("build", "package-vpm", "package-npm", "npm-textures", "sintez")}


def reserve_run(outputs, version):
    """Reserve fresh directories before work; never remove or reuse prior results.

    Refuse aliases including junctions and broken links. In a competing reservation,
    mkdir(exist_ok=False) fails closed; any newly reserved partial directories remain
    as evidence and the caller must choose a new version.
    """
    paths = run_paths(outputs, version)
    root = Path(outputs).absolute()
    for parent in (root, *root.parents):
        if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
            raise ValueError(f"Output root must not pass through an alias: {parent}")
    occupied = [str(path) for path in paths.values() if os.path.lexists(path)]
    if occupied:
        raise FileExistsError("Version already has results: " + ", ".join(occupied))
    root.mkdir(parents=True, exist_ok=True)
    for path in paths.values():
        path.mkdir(exist_ok=False)
    return paths


def require_udim_regions(udims, by_udim):
    missing = sorted(set(udims) - set(by_udim))
    if missing:
        raise ValueError("NPM atlas has no region for UDIM(s): " + ", ".join(map(str, missing)))


def validate_atlas(atlas, texture_spec):
    """Reject a stale finish mapping even if another finish occupies its UDIM."""
    finishes = atlas["finishes"]
    by_udim = {region["udim"]: region for region in finishes.values()}
    if len(by_udim) != len(finishes):
        raise ValueError("NPM atlas contains duplicate UDIM regions")
    require_udim_regions((finish["udim"] for finish in texture_spec["finishes"].values()), by_udim)
    for name, expected in texture_spec["finishes"].items():
        if name not in finishes or finishes[name]["udim"] != expected["udim"]:
            raise ValueError(f"NPM atlas finish mapping is stale: {name}")
    return by_udim


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outputs")
    parser.add_argument("version")
    args = parser.parse_args()
    require_delivery_mode()
    reserve_run(args.outputs, args.version)
