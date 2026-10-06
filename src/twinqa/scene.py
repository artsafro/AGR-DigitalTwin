"""FBX scene checks from a Blender readback (tools/blender/fbx_readback.py).

Fills the scene stages the header-only validator leaves not_run: V003 (triangulation,
triangle limits, object types), V004 (applied transforms), V006 (NPM embedded images),
V008 (one UV channel, mirrored islands, glass tile), V010 (UCX triangle budget only),
V013 (shared pivot). Triangle limits follow the 2026-10-07 decisions on conflicts #1 and #3.
"""
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from twinqa.report import Finding

READBACK = Path(__file__).resolve().parents[2] / "tools" / "blender" / "fbx_readback.py"
ANGLE_TOL_DEG, SCALE_TOL = 1e-3, 1e-4
# Project target (user decision on conflict #1, 2026-10-07): one model serves VPM and NPM, so
# VPM OKS aims at the NPM limit; above it, windows go to atlas textures on planes.
PROJECT_TRIANGLE_TARGET = 150_000
UCX_SMALL_MODEL, UCX_SMALL_LIMIT, UCX_SHARE, UCX_CAP = 50_000, 15_000, 0.05, 100_000


def ucx_triangle_limit(model_triangles: int) -> int:
    """UCX budget (reg p.36-37 §13.7-13.8) as SINTEZ AGR Checker v1.6.1 (conflict #3, decided):
    < 50 000 -> 15 000; else ceil(5 %) capped at 100 000."""
    if model_triangles < UCX_SMALL_MODEL:
        return UCX_SMALL_LIMIT
    return min(math.ceil(model_triangles * UCX_SHARE), UCX_CAP)


def find_blender() -> str | None:
    """TWINQA_BLENDER, then blender on PATH, then the newest install under Program Files."""
    explicit = os.environ.get("TWINQA_BLENDER") or shutil.which("blender")
    if explicit:
        return explicit
    root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation"
    found = sorted(root.glob("Blender */blender.exe"), key=lambda p: [int(x) for x in p.parent.name.split()[1].split(".")])
    return str(found[-1]) if found else None


def readback(fbx_path: Path, blender: str | None = None, timeout: int = 600) -> dict:
    blender = blender or find_blender()
    if not blender:
        raise FileNotFoundError("Blender not found (set TWINQA_BLENDER)")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "readback.json"
        proc = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1",
                               "--python", str(READBACK), "--", str(fbx_path), str(out)],
                              capture_output=True, text=True, timeout=timeout)
        if not out.is_file():
            raise RuntimeError(f"Blender readback produced no report (exit {proc.returncode}): {proc.stderr[-400:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def _f(status, name, observed, expected, pages, evidence, conflicts=()):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts))


def scene_findings(rb: dict, kind: str, role: str, profile: dict) -> dict[str, list[Finding]]:
    """role: 'oks' | 'ground' | 'light'. Returns {stage_id: findings}."""
    src = Path(rb["source"]).name
    out = {"V003": [], "V004": [], "V008": [], "V010": [], "V013": [], "V006": []}
    if not rb.get("readback_ok"):
        out["V003"].append(_f("fail", "FBX readback", rb.get("error", "no meshes"), "importable FBX with meshes", [4, 24], src))
        return out
    meshes = rb["meshes"]
    ucx = [m for m in meshes if m["name"].upper().startswith("UCX_")]
    tris = sum(m["triangles"] for m in meshes if m not in ucx)  # collision is excluded (reg p.28 §3.9)

    # V003: triangulated on export, triangle limits, no foreign objects (reg p.6-8, 28-29)
    not_tri = [m["name"] for m in meshes if set(m["polygon_degrees"]) != {"3"}]
    out["V003"].append(_f("fail" if not_tri else "pass", "triangulated", f"{src}: {not_tri or 'all triangles'}",
                          "triangulated on export", [7, 28], src))
    if role != "light":
        if kind == "npm":
            limit = profile["geometry"]["ground_triangles_total_max" if role == "ground" else "oks_triangles_per_fbx_max"]
            status, conflicts = ("fail" if tris > limit else "pass"), []
        else:
            if role == "ground":
                status, limit, conflicts = "review", "by site area (reg p.29 table)", []
            else:
                hard = profile["geometry"]["oks_triangles_per_fbx_max_excluding_collision"]
                status = "fail" if tris > hard else "review" if tris > PROJECT_TRIANGLE_TARGET else "pass"
                limit = (f"{PROJECT_TRIANGLE_TARGET} project target (reuse as NPM; else windows as atlas planes), "
                         f"{hard} regulation limit")
                conflicts = []
        out["V003"].append(_f(status, "triangle count", f"{src}: {tris}", f"<= {limit}", [7, 28, 29], src, conflicts))
    foreign = [o for o in rb["other_objects"] if not (role == "light" and o["type"] in ("LIGHT", "EMPTY"))]
    if foreign:
        lights = all(o["type"] == "LIGHT" for o in foreign)
        out["V003"].append(_f("review" if lights and kind == "vpm" else "fail", "object types",
                              f"{src}: {[(o['name'], o['type']) for o in foreign][:5]}",
                              "meshes only (lights only in the Light FBX)", [4, 24, 33], src, [14] if lights else []))

    # V004: transforms applied, rotation 0 (reg p.8, 29, 32-33)
    bad = [m["name"] for m in meshes
           if any(abs(a) > ANGLE_TOL_DEG for a in m["rotation_euler_deg"]) or any(abs(s - 1) > SCALE_TOL for s in m["scale"])]
    out["V004"].append(_f("fail" if bad else "pass", "applied transforms", f"{src}: {bad or 'rotation 0, scale 1'}",
                          "rotation 0, scale 1 after reset", [8, 29, 33], src))

    if kind == "vpm" and role != "light":
        # V010: UCX triangle budget only; shape, coverage and offsets need other checks (reg p.34-37)
        if ucx:
            ucx_tris, budget = sum(m["triangles"] for m in ucx), ucx_triangle_limit(tris)
            out["V010"].append(_f("fail" if ucx_tris > budget else "pass", "UCX triangle budget",
                                  f"{src}: {ucx_tris} UCX for {tris} model triangles", f"<= {budget}", [36, 37], src))
            out["V010"].append(_f("not_run", "UCX shape and coverage", "convex, closed, no intersections, coverage, offsets",
                                  "reg p.34-37", [34, 36, 37], src))
        # V008: one UV channel, no mirrored islands, glass only in 1001 (reg p.31-32, 39)
        multi = [m["name"] for m in meshes if m["uv_channels"] != 1]
        mirrored = {m["name"]: m["mirrored_uv_triangles"] for m in meshes if m["mirrored_uv_triangles"]}
        glass = {m["name"]: m["udim_tiles"] for m in meshes if m["name"].endswith("MainGlass") and m["udim_tiles"] != [1001]}
        out["V008"].append(_f("fail" if multi else "pass", "one UV channel", f"{src}: {multi or 'all meshes'}", "1 UV channel", [31], src))
        out["V008"].append(_f("fail" if mirrored else "pass", "mirrored islands", f"{src}: {mirrored or 'none'}", "no mirrored UV", [31], src))
        if glass:
            out["V008"].append(_f("fail", "glass tile", f"{src}: {glass}", "glass only in UDIM 1001", [31, 32], src))
        # V013: all meshes of one FBX share one pivot (reg p.32-33); geometric-centre rule is conflict #19
        pivots = {tuple(round(c, 4) for c in m["location"]) for m in meshes}
        out["V013"].append(_f("pass" if len(pivots) == 1 else "fail", "shared pivot", f"{src}: {len(pivots)} pivot(s)",
                              "one pivot for all meshes in the FBX", [32, 33], src))
        out["V013"].append(_f("not_run", "pivot position and MSK-77 point", "geometric centre X/Y, Z = project zero; GeoJSON point",
                              "reg p.32-33, p.55", [32, 33, 55], src, [19]))

    if kind == "npm":
        # V006: textures embedded in the FBX (reg p.9 §5.1); pixel rules need the PNG bytes
        loose = [i["name"] for i in rb.get("images", []) if not i["packed"]]
        out["V006"].append(_f("fail" if loose else "pass", "embedded textures", f"{src}: {loose or 'all embedded'}",
                              "PNG embedded in FBX", [9], src))
    return out
