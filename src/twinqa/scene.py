"""FBX scene checks from a Blender readback (tools/blender/fbx_readback.py).

Fills the scene stages the header-only validator leaves not_run: V003 (triangulation,
triangle limits, object types), V004 (applied transforms), V006 (NPM embedded images),
V008 (one UV channel, mirrored islands, glass tile), V013 (shared pivot). Disputed limits
stay review (conflict #1).
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from twinqa.report import Finding

READBACK = Path(__file__).resolve().parents[2] / "tools" / "blender" / "fbx_readback.py"
ANGLE_TOL_DEG, SCALE_TOL = 1e-3, 1e-4
VPM_FIGURE_OKS_LIMIT = 800_000  # figure 2.1, reg p.40 (conflict #1)


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
    out = {"V003": [], "V004": [], "V008": [], "V013": [], "V006": []}
    if not rb.get("readback_ok"):
        out["V003"].append(_f("fail", "FBX readback", rb.get("error", "no meshes"), "importable FBX with meshes", [4, 24], src))
        return out
    meshes = rb["meshes"]
    tris = sum(m["triangles"] for m in meshes)

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
                status, limit, conflicts = "review", "by site area (reg p.29)", [1]
            else:
                limit = profile["geometry"]["oks_triangles_per_fbx_max_excluding_collision"]
                status = "fail" if tris > limit else "review" if tris > VPM_FIGURE_OKS_LIMIT else "pass"
                conflicts = [1] if status == "review" else []
        out["V003"].append(_f(status, "triangle count", f"{src}: {tris}", f"<= {limit}", [7, 28, 29, 40], src, conflicts))
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
