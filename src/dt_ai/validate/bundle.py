import html
import math
import struct
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

from PIL import Image

from dt_ai.core.build import run_blender
from dt_ai.core.io import digest, read_json, write_json
from dt_ai.core.models import BuildJob, Finding, ValidationReport
from dt_ai.core.profiles import load_profiles
from dt_ai.geometry.uv import edge_densities, validate_uv, signed_area
from dt_ai.publish.bundle import read_bundle


def triangle_signature(vertices, uv):
    return tuple(sorted(tuple(round(c, 5) for c in xyz + pair) for xyz, pair in zip(vertices, uv)))


def validate(root: Path, archive: Path, output: Path, blender: str | None = None):
    profiles = load_profiles(root)
    checks = []
    source_hash = profiles["NPM_STANDARD.yaml"]["source"]["sha256"]

    def record(id, ok, pages, observed, expected, evidence):
        checks.append(Finding(id=id, status="pass" if ok else "fail", source_pdf_pages=pages,
                              observed=str(observed), expected=expected, evidence=evidence))

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    try:
        files = read_bundle(archive)
        manifest = read_json(files["bundle-manifest.json"])
        require(manifest["kind"] == "synthetic_development_bundle" and manifest["synthetic"] is True,
                "Expected labelled synthetic development bundle")
        require(manifest["source_sha256"] == source_hash, "Source hash mismatch")
        require(set(files) == set(manifest["files"]) | {"bundle-manifest.json"}, "Unexpected or missing ZIP member")
        require(all(digest(files[p]) == h for p, h in manifest["files"].items()), "File digest mismatch")
        job = BuildJob.model_validate(read_json(files["job.json"]))
        require(job.project.synthetic, "Synthetic job label is required")
        require(job.project.standards_sha256 == source_hash, "Job source hash mismatch")
        require(all(m.status == "approved" for m in job.registry.materials), "Unapproved material")
        layout = read_json(files["layout.json"])
        require(layout["synthetic"] is True, "Layout synthetic label is missing")
        record("C001", True, [6, 26], f"{len(files)} members, contracts and SHA-256 verified",
               "Exact inventory and valid input contracts", archive.name)
    except (ValueError, KeyError, OSError, TypeError, BadZipFile) as exc:
        # Corrupt ZIPs and decoder failures must produce a failing report, never pass.
        record("C001", False, [6, 26], str(exc), "Readable development bundle", archive.name)
        return finish(profiles, checks, source_hash, output)

    pngs = {}
    try:
        for name, content in files.items():
            if name.endswith(".png"):
                im = Image.open(BytesIO(content))
                require(im.format == "PNG", f"Not PNG: {name}")
                require(content[24] == 8, f"Not 8 bits/channel: {name}")
                im.load()
                require(im.mode == "RGB", f"Expected RGB: {name}")
                require(im.width == im.height, f"Not square: {name}")
                profile = profiles["NPM_STANDARD.yaml" if name.startswith("npm/") else "VPM_STANDARD.yaml"]
                require(im.width in profile["textures"]["allowed_square_sizes_px"], f"Invalid resolution: {name}")
                if name.startswith("npm/"):
                    require(len(content) <= profile["textures"]["max_file_bytes"], "Atlas exceeds profile limit")
                pngs[name] = im
        materials = {m.id: m for m in job.registry.materials}
        require(set(layout["materials"]) == set(materials), "Material layout mismatch")
        expected_pngs = set()
        for id, entry in layout["materials"].items():
            m = materials[id]
            require(entry["slot"] == 1, "Fixture uses one material slot, independent of UDIM")
            atlas = pngs[entry["npm_texture"]]
            expected_pngs.add(entry["npm_texture"])
            rect = entry["npm_rect_px"]
            require(atlas.getpixel((rect[0], rect[1])) == tuple(m.diffuse_rgb), f"Atlas material mismatch: {id}")
            for kind in ("Diffuse", "ERM", "Normal"):
                path = entry["textures"][kind]
                expected_pngs.add(path)
                require(path == f"vpm/T_{job.project.address_token}_{kind}_1.{entry['tile']}.png", "Texture name mismatch")
                im = pngs[path]
                require(im.width == entry["vpm_size"], "Image/layout size mismatch")
                base = im.getpixel((0, 0))
                expected = tuple(m.diffuse_rgb) if kind == "Diffuse" else (m.emissive, m.roughness, m.metallic) if kind == "ERM" else (m.normal_opengl_rgb[0], 255 - m.normal_opengl_rgb[1], m.normal_opengl_rgb[2])
                require(base == expected, f"Incorrect {kind} channels: {id}: {base} != {expected}")
                pad = entry["vpm_padding"]
                require(pad == profiles["VPM_STANDARD.yaml"]["textures"]["padding_px_min"][im.width], "Padding differs from profile")
                require(im.crop((0, 0, im.width, 1)).tobytes() == im.crop((0, pad, im.width, pad + 1)).tobytes(), "Top padding not dilated")
                require(im.crop((0, 0, 1, im.height)).tobytes() == im.crop((pad, 0, pad + 1, im.height)).tobytes(), "Left padding not dilated")
        require(set(pngs) == expected_pngs, "Unused or missing PNG maps")
        record("C002", True, [9, 23, 30, 37], f"{len(pngs)} PNGs; RGB, ERM R/G/B, DirectX green, padding checked",
               "NPM atlas + VPM Diffuse/ERM/Normal", archive.name)
    except (ValueError, KeyError, OSError, IndexError, TypeError) as exc:
        record("C002", False, [9, 23, 30, 37], str(exc), "Valid PNG sets and channel values", archive.name)

    try:
        source_surfaces = {s.id: s for s in job.master.surfaces}
        require(len(layout["surfaces"]) == len(source_surfaces), "Surface count mismatch")
        require({s["id"] for s in layout["surfaces"]} == set(source_surfaces), "Surface ID mismatch")
        tiles = {s["tile"] for s in layout["surfaces"]}
        require(sorted(tiles) == list(range(1001, 1001 + len(tiles))), "Nonsequential UDIM tiles")
        require(tiles == {e["tile"] for e in layout["materials"].values()}, "Unused UDIM")
        densities = []
        limits = profiles["VPM_STANDARD.yaml"]["uv"]["diffuse_density_px_per_m"]
        for surface in layout["surfaces"]:
            original = source_surfaces[surface["id"]]
            require(surface["vertices"] == original.vertices and surface["material_id"] == original.material_id,
                    "Surface identity or geometry changed")
            entry = layout["materials"][surface["material_id"]]
            require(surface["tile"] == entry["tile"] and surface["slot"] == 1, "Surface/material UDIM mismatch")
            require(validate_uv(surface["vpm_uv"], surface["tile"], entry["vpm_size"], entry["vpm_padding"]),
                    f"Invalid/mirrored/cross-tile UV: {surface['id']}")
            uv = surface["npm_uv"]
            require(signed_area(uv) > 0 and all(0 <= c <= 1 for pair in uv for c in pair), "Invalid NPM UV")
            x0, y0, x1, y1 = entry["npm_rect_px"]
            size = entry["atlas_size"]
            require(all(x0 - 1e-6 <= u * size <= x1 + 1e-6 and y0 - 1e-6 <= (1 - v) * size <= y1 + 1e-6 for u, v in uv), "NPM UV samples another material")
            values = edge_densities(original.vertices, surface["vpm_uv"], entry["vpm_size"])
            require(all(limits["min"] <= d <= limits["max"] for d in values), "Texel density outside limits")
            densities.extend(values)
        record("C003", True, [9, 30, 31, 32, 39], f"UDIM {sorted(tiles)}; edge density {min(densities):.1f}..{max(densities):.1f} px/m",
               "Sequential tiles, nonmirrored UV, padding, rectangular-surface density", "layout.json")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        record("C003", False, [9, 30, 31, 32, 39], str(exc), "Valid UV and density", "layout.json")

    if blender:
        try:
            audits = {}
            for profile in ("npm", "vpm"):
                members = [p for p in files if p.startswith(profile + "/") and p.endswith(".fbx")]
                require(len(members) == 1, f"One {profile} FBX required")
                content = files[members[0]]
                require(content.startswith(b"Kaydara FBX Binary  \x00\x1a\x00") and struct.unpack("<I", content[23:27])[0] == 7400,
                        "Expected binary FBX 7400")
                # Only the FBX is extracted. NPM image retrieval must work from embedded bytes.
                with tempfile.TemporaryDirectory(prefix="dt-roundtrip-") as tmp:
                    work = Path(tmp)
                    fbx = work / "model.fbx"
                    fbx.write_bytes(content)
                    evidence = run_blender(blender, root, {"operation": "audit", "fbx": str(fbx),
                        "result": str(work / "audit.json")}, work)
                    objects = evidence["objects"]
                    require(len(objects) == 1 and objects[0]["type"] == "MESH", "Unexpected FBX objects")
                    obj = objects[0]
                    require(obj["triangles"] == len(job.master.surfaces) * 2 and set(obj["polygon_sizes"]) == {3}, "FBX topology differs")
                    require(obj["uv_channels"] == 1 and len(obj["materials"]) == 1, "UV/material count differs")
                    expected_material = "M_" + job.project.address_token + ("_001_Main_1" if profile == "npm" else "_Main_1")
                    require(obj["materials"] == [expected_material], "FBX material name mismatch")
                    require(obj["parent"] is None and all(abs(c) < 1e-5 for c in obj["location"] + obj["rotation"])
                            and all(abs(c - 1) < 1e-5 for c in obj["scale"]), "Nonidentity FBX transform")
                    actual = sorted(triangle_signature(v, uv) for v, uv in zip(obj["faces_world"], obj["face_uv"]))
                    expected = []
                    for s in layout["surfaces"]:
                        for tri in ((0, 1, 2), (0, 2, 3)):
                            expected.append(triangle_signature([s["vertices"][i] for i in tri], [s[profile + "_uv"][i] for i in tri]))
                    require(actual == sorted(expected), "Reimported geometry/UV differs from source")
                    if profile == "npm":
                        atlas_sha = digest(files[next(p for p in pngs if p.startswith("npm/"))])
                        require(any(im["sha256"] == atlas_sha for im in evidence["images"]), "Embedded atlas absent or changed")
                    else:
                        require(not evidence["images"], "VPM FBX must have no external image paths")
                    audits[profile] = evidence
            write_json(output / "dcc-roundtrip.json", audits)
            record("C004", True, [4, 9, 24, 30, 31, 32], "Both FBX 7400 files reimported in isolated Blender; triangles, world vertices, UV, materials and embedding match",
                   "Validate actual FBX bytes from ZIP", "dcc-roundtrip.json")
        except (ValueError, KeyError, OSError, RuntimeError, IndexError, TypeError) as exc:
            record("C004", False, [4, 9, 24, 30, 31, 32], str(exc), "FBX roundtrip matches", archive.name)
    else:
        checks.append(Finding(id="C004", status="not_run", source_pdf_pages=[4, 9, 24, 30, 31],
            observed="Blender not requested", expected="Actual export/import", evidence=archive.name))
    return finish(profiles, checks, source_hash, output)


def finish(profiles, checks, source_hash, output):
    for rule in profiles["DELIVERY_VALIDATOR.yaml"]["stages"]:
        pages = rule["source_pdf_pages"]
        if isinstance(pages, dict):
            pages = sorted({p for items in pages.values() for p in items})
        checks.append(Finding(id=rule["id"], status="review" if rule["gate"] == "manual_review" else "not_run",
            source_pdf_pages=pages, observed="Full customer-delivery check not implemented or not supported by synthetic evidence",
            expected=rule["check"], evidence="docs/decisions/ADR-0001-synthetic-scope.md"))
    report = ValidationReport(synthetic=True, source_sha256=source_hash, checks=checks,
        development_checks_passed=all(c.status == "pass" for c in checks if c.id.startswith("C")),
        limitations=["Synthetic development bundle, not an official NPM/VPM delivery archive.",
                     "No project georeferencing, GeoJSON, ground, UCX, glazing or facade approval.",
                     "DCC evidence applies only to the explicitly executed Blender roundtrip; Max/Revit/CAD unverified.",
                     "Texel measurement currently covers rectangular fixture surfaces only."])
    write_json(output / "report.json", report.model_dump())
    rows = "".join(f"<tr><td>{html.escape(c.id)}</td><td>{c.status}</td><td>{html.escape(c.observed)}</td><td>{c.source_pdf_pages}</td></tr>" for c in checks)
    page = '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Digital Twin AI — проверка</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;background:#f4f5f7;color:#172233}td,th{padding:12px;text-align:left;border-bottom:1px solid #ccd}table{width:100%;background:white}h1{font-size:28px}.notice{padding:18px;background:#fff0c5}</style>'
    page += f'<h1>Digital Twin AI · синтетический пример</h1><p class="notice">Готовность к сдаче: НЕТ. Технические проверки примера: {"пройдены" if report.development_checks_passed else "не завершены или есть ошибки"}.</p>'
    page += '<table><tr><th>Проверка</th><th>Статус</th><th>Наблюдение</th><th>PDF</th></tr>' + rows + '</table>'
    page += '<ul>' + ''.join('<li>' + html.escape(s) + '</li>' for s in report.limitations) + '</ul></html>'
    (output / "report.html").write_text(page, encoding="utf-8")
    return report
