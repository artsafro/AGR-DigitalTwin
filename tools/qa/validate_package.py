"""NPM/VPM delivery validator: findings per stage V001-V017 (standards/DELIVERY_VALIDATOR.yaml).

    py -3 tools/qa/validate_package.py <package.zip | model.fbx | model.geojson> [--profile npm|vpm] [--json] [--scene]

Exit code: 0 passed (every blocking machine stage ran and passed), 1 any fail,
2 only review / not_run remain. Stages that need the FBX scene (units, triangles,
UV islands, UCX, coordinates) are not_run unless --scene runs the Blender readback
(tools/blender/fbx_readback.py) on every FBX.
Manual stages (V015-V017) always need a signed review.
"""
import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from twinqa.bundle import BundleError, read_bundle, size_status  # noqa: E402
from twinqa.fbx_header import check_fbx_header  # noqa: E402
from twinqa.geojson import geojson_findings  # noqa: E402
from twinqa.io import digest  # noqa: E402
from twinqa.png import npm_texture_findings, vpm_texture_findings  # noqa: E402
from twinqa.profiles import load_profiles  # noqa: E402
from twinqa.report import Finding, Stage, ValidationReport  # noqa: E402
from twinqa.scene import readback, scene_findings  # noqa: E402
from twinqa.uv import sequential_tiles  # noqa: E402

STEM = re.compile(r"^[A-Za-z0-9_]+$")
NPM_ARCHIVE = re.compile(r"^(?P<code>[0-9]{4})_(?P<address>[A-Za-z0-9_]+)$")
SCENE_NOTE = "needs the FBX scene: run tools/blender readback"


def finding(status, name, observed, expected, pages, evidence="", conflicts=()):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts))


def build_stages(profiles, kind: str) -> dict[str, Stage]:
    stages = {}
    for spec in profiles.validator["stages"]:
        if spec["scope"] not in ("both", kind.upper()):
            continue
        pages = spec.get("source_pdf_pages", [])
        if isinstance(pages, dict):
            pages = pages.get(kind.upper(), [])
        stages[spec["id"]] = Stage(spec["id"], spec["check"], spec["gate"], list(pages))
    return stages


def check_fbx_headers(stage: Stage, fbx: dict[str, bytes]):
    for name, data in sorted(fbx.items()):
        ok, observed = check_fbx_header(data)
        stage.findings.append(finding("pass" if ok else "fail", "FBX header", f"{name}: {observed}",
                                      "binary FBX 7400 (7.4/2014)", stage.source_pdf_pages, name))
    stage.findings.append(finding("not_run", "units and scale", "1 unit = 1 m not read from the scene",
                                  "1 unit = 1 m, scale 1:1", stage.source_pdf_pages, SCENE_NOTE))


def validate_vpm_zip(stem: str, files: dict[str, bytes], profile: dict, st: dict[str, Stage]):
    ground = stem.endswith("_Ground")
    address = stem[3:-len("_Ground")] if ground else stem[3:]
    fbx = {n: d for n, d in files.items() if n.lower().endswith(".fbx")}
    pngs = {n: d for n, d in files.items() if n.lower().endswith(".png")}
    geo = {n: d for n, d in files.items() if n.lower().endswith(".geojson")}
    other = sorted(set(files) - set(fbx) - set(pngs) - set(geo))

    v1, pages = st["V001"], st["V001"].source_pdf_pages
    nested = [n for n in files if len(PurePosixPath(n).parts) > 1]
    if nested:
        v1.findings.append(finding("fail", "flat archive", f"{len(nested)} file(s) in folders, e.g. {nested[0]}", "files in the ZIP root", pages))
    if other:
        v1.findings.append(finding("fail", "foreign files", ", ".join(other[:5]), "FBX, optional Light FBX, GeoJSON, PNG only", pages))
    main, light = f"{stem}.fbx", f"{stem}_Light.fbx"
    if main not in fbx:
        v1.findings.append(finding("fail", "main FBX", f"{sorted(fbx)}", main, pages))
    extra_fbx = sorted(set(fbx) - {main, light})
    if extra_fbx:
        v1.findings.append(finding("fail", "FBX set", f"unexpected {extra_fbx}", f"{main} and optional {light}", pages))
    if f"{stem}.geojson" not in geo or len(geo) != 1:
        v1.findings.append(finding("fail", "GeoJSON", f"{sorted(geo) or 'none'}", f"exactly {stem}.geojson", pages))
    lo, hi = profile["archive"]["png_count_range"]
    if not lo <= len(pngs) <= hi:
        v1.findings.append(finding("fail", "PNG count", str(len(pngs)), f"{lo}..{hi}", pages))

    v12, npages = st["V012"], st["V012"].source_pdf_pages
    if not STEM.match(stem) or not stem.startswith("SM_") or len(stem) > profile["naming"]["max_characters"]:
        v12.findings.append(finding("fail", "archive name", stem, "SM_{Address}[_Ground], A-Z a-z 0-9 _", npages))
    elif ground:
        v12.findings.append(finding("pass", "archive name", stem, "SM_{Address}_Ground", npages))
    else:
        # Free-standing buildings need an _001.. index (reg p.26 §3.7), not encoded: conflict #20
        v12.findings.append(finding("review", "archive name", stem, "SM_{Address}; _001.. index for free-standing buildings",
                                    npages, conflicts=[20]))

    if main in fbx:
        check_fbx_headers(st["V002"], {k: v for k, v in fbx.items() if k in (main, light)})
    prefix = f"T_{address}_Ground" if ground else f"T_{address}"
    findings, sets = vpm_texture_findings(pngs, profile, prefix)
    st["V007"].findings.extend(findings)

    v8 = st["V008"]
    for slot in sorted({s for s, _ in sets}):
        tiles = sorted(u for s, u in sets if s == slot)
        ok = sequential_tiles(tiles)
        v8.findings.append(finding("pass" if ok else "fail", "UDIM sequence", f"slot {slot}: {tiles}",
                                   "1001..1100 sequential without gaps", v8.source_pdf_pages))
    v8.findings.append(finding("not_run", "UV channel and islands", "single UV channel, mirroring, glass in 1001",
                               "one UV channel, no mirrored islands, glass only in 1001", v8.source_pdf_pages, SCENE_NOTE))

    if f"{stem}.geojson" in geo:
        st["V011"].findings.extend(geojson_findings(geo[f"{stem}.geojson"], profile, ground))


def validate_npm_zip(stem: str, files: dict[str, bytes], profile: dict, st: dict[str, Stage]):
    v1, pages = st["V001"], st["V001"].source_pdf_pages
    fbx = {n: d for n, d in files.items() if n.lower().endswith(".fbx")}
    other = sorted(set(files) - set(fbx))
    if other:
        # NPM textures are embedded in the FBX (reg p.9 §5.1); anything else is foreign
        v1.findings.append(finding("fail", "foreign files", ", ".join(other[:5]), "FBX only (textures embedded)", pages))
    count = profile["archive"]["fbx_total"]
    if not count["min"] <= len(fbx) <= count["max"]:
        v1.findings.append(finding("fail", "FBX count", str(len(fbx)), f"{count['min']}..{count['max']} (1 Ground + 1..20 OKS)", pages))
    m = NPM_ARCHIVE.match(stem)
    v12 = st["V012"]
    if not m:
        v12.findings.append(finding("fail", "archive name", stem, "{territory_code_4}_{Address}", v12.source_pdf_pages))
    else:
        ground_name, part = f"{stem}_Ground.fbx", re.compile(rf"^{re.escape(stem)}_(0[1-9]|1[0-9]|20)\.fbx$")
        if ground_name not in fbx:
            v1.findings.append(finding("fail", "Ground FBX", f"{sorted(fbx)}", ground_name, pages))
        bad = sorted(n for n in fbx if n != ground_name and not part.match(n))
        v12.findings.append(finding("fail" if bad else "pass", "FBX names", f"{bad or 'all match'}",
                                    f"{stem}_01..20.fbx and {ground_name}", v12.source_pdf_pages))
    check_fbx_headers(st["V002"], fbx)
    st["V006"].findings.append(finding("not_run", "embedded atlases", "PNG inside FBX not extracted",
                                       "sizes, <= 3 MB, no alpha, 8 px padding", st["V006"].source_pdf_pages, SCENE_NOTE))


def fbx_role(name: str) -> str:
    stem = Path(name).stem
    return "light" if stem.endswith("_Light") else "ground" if stem.endswith("_Ground") else "oks"


def add_scene(st: dict[str, Stage], kind: str, profile: dict, fbx: dict[str, bytes], notes: list[str]):
    """Blender readback of each FBX; replaces the scene not_run placeholders it covers."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in sorted(fbx.items()):
            path = Path(tmp) / Path(name).name
            path.write_bytes(data)
            try:
                rb = readback(path)
            except (OSError, RuntimeError) as exc:
                notes.append(f"scene readback skipped for {name}: {exc}")
                return
            for stage_id, findings in scene_findings(rb, kind, fbx_role(name), profile).items():
                if stage_id in st:
                    st[stage_id].findings.extend(findings)
            notes.append(f"scene readback: {name} in Blender {rb.get('blender')}")
    covered = {"V008": "UV channel and islands", "V006": "embedded atlases"}
    for stage_id, placeholder in covered.items():
        if stage_id in st and len(st[stage_id].findings) > 1:
            st[stage_id].findings = [f for f in st[stage_id].findings if f.name != placeholder]


def validate(target: Path, kind: str | None, profiles, scene: bool = False) -> ValidationReport:
    data = target.read_bytes()
    suffix = target.suffix.lower()
    if suffix == ".geojson":
        kind = "vpm"
    elif kind is None and suffix in (".fbx", ".png"):
        kind = "npm"
    files, notes = {}, []
    if suffix == ".zip":
        try:
            files = read_bundle(target, max_uncompressed=4 * 10**9)
        except BundleError as exc:
            kind = kind or "vpm"
            st = build_stages(profiles, kind)
            st["V001"].findings.append(finding("fail", "ZIP", str(exc), "readable ZIP, safe paths", st["V001"].source_pdf_pages))
            return report(target, data, kind, profiles, st, notes)
        if kind is None:
            kind = "vpm" if any(n.lower().endswith((".geojson", ".png")) for n in files) else "npm"
            notes.append(f"profile auto-detected as {kind.upper()} from archive content")
    profile = profiles.profile(kind)
    st = build_stages(profiles, kind)

    if suffix == ".zip":
        archive = profile["archive"]
        limit = archive.get("max_bytes") or (archive["ground_max_bytes"] if target.stem.endswith("_Ground") else archive["oks_max_bytes"])
        status, observed = size_status(len(data), limit)
        st["V001"].findings.append(finding(status, "archive size", observed, f"<= {limit} B",
                                           st["V001"].source_pdf_pages, conflicts=[12] if status == "review" else []))
        (validate_vpm_zip if kind == "vpm" else validate_npm_zip)(target.stem, files, profile, st)
        if scene:
            add_scene(st, kind, profile, {n: d for n, d in files.items() if n.lower().endswith(".fbx")}, notes)
    elif suffix == ".fbx":
        check_fbx_headers(st["V002"], {target.name: data})
        if scene:
            add_scene(st, kind, profile, {target.name: data}, notes)
        else:
            notes.append("single FBX: header only; add --scene for the Blender readback")
    elif suffix == ".geojson":
        st["V011"].findings.extend(geojson_findings(data, profile, target.stem.endswith("_Ground")))
        notes.append("single GeoJSON: only V011 applies")
    elif suffix == ".png" and kind == "npm":
        st["V006"].findings.extend(npm_texture_findings({target.name: data}, profile))
    else:
        notes.append(f"unsupported file type {suffix}")
    return report(target, data, kind, profiles, st, notes)


def report(target, data, kind, profiles, stages, notes) -> ValidationReport:
    return ValidationReport(kind, str(target), digest(data), profiles.pdf_sha256, profiles.pdf_verified,
                            list(stages.values()), notes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", type=Path)
    ap.add_argument("--profile", choices=["npm", "vpm"])
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--standards", type=Path, help="standards folder (default: <repo>/standards)")
    ap.add_argument("--scene", action="store_true", help="read every FBX back in background Blender")
    args = ap.parse_args(argv)
    if not args.target.is_file():
        print(f"Error: {args.target} does not exist", file=sys.stderr)
        return 1
    profiles = load_profiles(args.standards) if args.standards else load_profiles()
    result = validate(args.target, args.profile, profiles, args.scene)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) if args.json else result.summary())
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
