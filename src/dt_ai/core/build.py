import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from dt_ai import __version__
from dt_ai.core.io import digest, json_bytes, read_json, write_json
from dt_ai.core.models import BuildJob
from dt_ai.core.profiles import load_profiles
from dt_ai.geometry.uv import tile_quad
from dt_ai.materials.textures import material_maps, padded_content, png
from dt_ai.publish.bundle import package


def run_blender(executable: str, root: Path, request: dict, work: Path):
    work.mkdir(parents=True, exist_ok=True)
    request_path = work / "request.json"
    write_json(request_path, request)
    command = [executable, "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", str(root / "adapters/blender/bridge.py"), "--", str(request_path.resolve())]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    (work / "blender.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Blender failed; see {work / 'blender.log'}")
    result_path = Path(request["result"])
    if not result_path.is_file():
        raise RuntimeError("Blender did not produce evidence")
    return read_json(result_path.read_bytes())


def prepare_assets(job: BuildJob, profiles):
    if not job.project.synthetic:
        raise ValueError("This vertical slice builds synthetic fixtures only; real-project publication is not implemented")
    if any(m.status != "approved" for m in job.registry.materials):
        raise ValueError("All materials must be approved before build")
    source_hash = profiles["NPM_STANDARD.yaml"]["source"]["sha256"]
    if source_hash != job.project.standards_sha256:
        raise ValueError("Job source PDF hash mismatch")
    for key in ("NPM", "VPM"):
        if job.project.profile_versions[key] != profiles[f"{key}_STANDARD.yaml"]["version"]:
            raise ValueError("Job profile version mismatch")
    npm = profiles["NPM_STANDARD.yaml"]
    vpm = profiles["VPM_STANDARD.yaml"]
    materials = sorted(job.registry.materials, key=lambda m: m.id)
    atlas_size = 512  # Engineering fixture choice, not a customer rule.
    cols = math.ceil(math.sqrt(len(materials)))
    cell = atlas_size // cols
    pad = npm["textures"]["island_padding_px_min"]
    if cell <= pad * 2:
        raise ValueError("Too many materials for the fixture atlas")
    atlas = Image.new("RGB", (atlas_size, atlas_size))
    layout = {"schema_version": "1.0.0", "synthetic": True, "materials": {}, "surfaces": []}
    assets = {}
    address = job.project.address_token
    npm_path = f"npm/T_{address}_001_Main_d_1.png"
    size = min(vpm["textures"]["allowed_square_sizes_px"])
    padding = vpm["textures"]["padding_px_min"][size]
    for index, material in enumerate(materials):
        x, y = (index % cols) * cell, (index // cols) * cell
        patch = padded_content(material_maps(material, cell)["Diffuse"], pad)
        atlas.paste(patch, (x, y))
        rect = [x + pad, y + pad, x + cell - pad, y + cell - pad]
        tile = 1001 + index
        paths = {}
        for kind, im in material_maps(material, size).items():
            path = f"vpm/T_{address}_{kind}_1.{tile}.png"
            assets[path] = png(padded_content(im, padding))
            paths[kind] = path
        layout["materials"][material.id] = {"npm_rect_px": rect, "npm_texture": npm_path,
            "atlas_size": atlas_size, "npm_padding": pad, "tile": tile,
            "slot": 1, "vpm_size": size, "vpm_padding": padding, "textures": paths}
    assets[npm_path] = png(atlas)
    for surface in job.master.surfaces:
        m = layout["materials"][surface.material_id]
        x0, y0, x1, y1 = m["npm_rect_px"]
        npm_uv = [[x0 / atlas_size, 1 - y1 / atlas_size], [x1 / atlas_size, 1 - y1 / atlas_size],
                  [x1 / atlas_size, 1 - y0 / atlas_size], [x0 / atlas_size, 1 - y0 / atlas_size]]
        layout["surfaces"].append({"id": surface.id, "material_id": surface.material_id,
            "vertices": surface.vertices, "npm_uv": npm_uv,
            "vpm_uv": tile_quad(m["tile"], size, padding), "tile": m["tile"], "slot": 1})
    return assets, layout


def build(root: Path, job_path: Path, output: Path, blender: str | None = None):
    job = BuildJob.model_validate(read_json(job_path.read_bytes()))
    # Input hashes are relative to the job file, and must be supplied, not invented.
    from dt_ai.core.io import inside
    for name, expected in job.project.inputs.items():
        source = inside(job_path.parent, name)
        if not source.is_file() or digest(source.read_bytes()) != expected:
            raise ValueError(f"Input hash mismatch: {name}")
    profiles = load_profiles(root)
    assets, layout = prepare_assets(job, profiles)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    dcc = {}
    if blender:
        for profile in ("npm", "vpm"):
            folder = output / profile
            fbx = folder / f"SM_{job.project.address_token}_{profile}.fbx"
            request = {"operation": "export", "profile": profile, "layout": layout,
                       "address": job.project.address_token, "fbx": str(fbx.resolve()),
                       "blend": str((folder / f"synthetic_{profile}.blend").resolve()),
                       "atlas": str((output / next(p for p in assets if p.startswith("npm/"))).resolve()),
                       "result": str((folder / "export-result.json").resolve())}
            dcc[profile] = run_blender(blender, root, request, output / "logs" / profile)
            assets[fbx.relative_to(output).as_posix()] = fbx.read_bytes()
    assets["job.json"] = json_bytes(job.model_dump())
    assets["layout.json"] = json_bytes(layout)
    hashes = {p: digest(data) for p, data in sorted(assets.items())}
    previous_path = output / "build-manifest.json"
    previous = read_json(previous_path.read_bytes()).get("files", {}) if previous_path.exists() else {}
    changes = {"changed": sorted(p for p in hashes if hashes[p] != previous.get(p)),
               "unchanged": sorted(p for p in hashes if hashes[p] == previous.get(p)),
               "removed": sorted(set(previous) - set(hashes))}
    manifest = {"schema_version": "1.0.0", "kind": "synthetic_development_bundle", "synthetic": True,
                "generator_version": __version__, "source_sha256": job.project.standards_sha256,
                "files": hashes, "dcc": dcc, "delivery_ready": False}
    assets["bundle-manifest.json"] = json_bytes(manifest)
    package(assets, output / "development_bundle.zip")
    write_json(previous_path, manifest)
    write_json(output / "changes.json", changes)
    write_json(output / "layout.json", layout)
    return output / "development_bundle.zip"
