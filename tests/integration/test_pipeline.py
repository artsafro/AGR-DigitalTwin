import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image
from pydantic import ValidationError

from dt_ai.core.build import build, prepare_assets
from dt_ai.core.io import digest, json_bytes, read_json, write_json
from dt_ai.core.models import ValidationReport
from dt_ai.core.profiles import load_profiles
from dt_ai.geometry.uv import tile_origin, tile_quad, validate_uv
from dt_ai.materials.textures import pack_erm, directx_normal, png
from dt_ai.publish.bundle import package, read_bundle
from dt_ai.validate.bundle import validate


def test_erm_channel_order_and_directx_are_not_interchangeable():
    channels = [Image.new("L", (2, 2), v) for v in [17, 109, 231]]
    assert pack_erm(*channels).getpixel((0, 0)) == (17, 109, 231)
    source = Image.new("RGB", (2, 2), (80, 63, 240))
    assert directx_normal(source).getpixel((0, 0)) == (80, 192, 240)
    assert source.getpixel((0, 0)) == (80, 63, 240)
    with pytest.raises(ValueError):
        pack_erm(channels[0], Image.new("L", (3, 3)), channels[2])


def test_udim_row_transition_and_mirroring():
    assert tile_origin(1010) == (9, 0)
    assert tile_origin(1011) == (0, 1)
    assert tile_origin(1100) == (9, 9)
    uv = tile_quad(1011, 2048, 16)
    assert validate_uv(uv, 1011, 2048, 16)
    assert not validate_uv(list(reversed(uv)), 1011, 2048, 16)
    uv[0][0] = -0.1
    assert not validate_uv(uv, 1011, 2048, 16)
    with pytest.raises(ValueError):
        tile_origin(1101)


@pytest.fixture
def bundle(root, tmp_path):
    output = tmp_path / "build"
    path = build(root, root / "jobs/SYNTH-001/project.json", output)
    return path


def rewrite(files, path):
    manifest = read_json(files["bundle-manifest.json"])
    manifest["files"] = {p: digest(data) for p, data in files.items() if p != "bundle-manifest.json"}
    files["bundle-manifest.json"] = json_bytes(manifest)
    package(files, path)


def test_roundtrip_independent_core_never_certifies_delivery(root, bundle, tmp_path):
    report = validate(root, bundle, tmp_path / "report")
    assert all(c.status == "pass" for c in report.checks if c.id in {"C001", "C002", "C003"})
    assert not report.passed
    assert next(c for c in report.checks if c.id == "C004").status == "not_run"
    data = report.model_dump()
    data["passed"] = True
    with pytest.raises(ValidationError):
        ValidationReport.model_validate(data)


@pytest.mark.parametrize("damage", ["erm_channels", "normal_green", "alpha", "udim_gap", "mirror_uv", "cross_tile", "unused_map", "missing_map", "bad_checksum", "missing_fbx"])
def test_corrupted_exports_fail(root, bundle, tmp_path, damage):
    files = read_bundle(bundle)
    if damage in {"erm_channels", "normal_green", "alpha"}:
        key = next(p for p in files if ("_ERM_" if damage != "normal_green" else "_Normal_") in p)
        im = Image.open(BytesIO(files[key])).copy()
        if damage == "alpha":
            im = im.convert("RGBA")
        elif damage == "erm_channels":
            r, g, b = im.split()
            im = Image.merge("RGB", (g, r, b))
        else:
            im = directx_normal(im)
        files[key] = png(im)
    elif damage in {"udim_gap", "mirror_uv", "cross_tile"}:
        layout = read_json(files["layout.json"])
        s = layout["surfaces"][0]
        if damage == "udim_gap":
            s["tile"] = 1010
        elif damage == "mirror_uv":
            s["vpm_uv"].reverse()
        else:
            s["vpm_uv"][0][0] = 9.0
        files["layout.json"] = json_bytes(layout)
    elif damage == "unused_map":
        files["vpm/unused.png"] = files[next(p for p in files if p.endswith(".png"))]
    elif damage == "missing_map":
        del files[next(p for p in files if "_ERM_" in p)]
    elif damage == "bad_checksum":
        files["layout.json"] += b" "
        package(files, bundle)
    else:
        # A request to verify real FBX cannot succeed on a core-only package.
        report = validate(root, bundle, tmp_path / "missing", blender="unused-because-files-missing")
        assert next(c for c in report.checks if c.id == "C004").status == "fail"
        return
    if damage != "bad_checksum":
        rewrite(files, bundle)  # Pixel/UV checks must catch damage even with updated inventory hashes.
    report = validate(root, bundle, tmp_path / "report")
    assert any(c.status == "fail" for c in report.checks)
    assert not report.development_checks_passed and not report.passed


def test_archive_traversal_and_duplicate_members_rejected(tmp_path):
    path = tmp_path / "bad.zip"
    for members in (["../escape"], ["same", "same"]):
        with ZipFile(path, "w") as z:
            for name in members:
                z.writestr(name, b"x")
        with pytest.raises(ValueError):
            read_bundle(path)


def test_empty_and_unreadable_archives_fail(root, tmp_path):
    path = tmp_path / "empty.zip"
    for content in (b"not a zip", b""):
        path.write_bytes(content)
        assert not validate(root, path, tmp_path / "report").development_checks_passed
    package({}, path)
    assert validate(root, path, tmp_path / "report").checks[0].status == "fail"


def test_repeat_build_and_material_change_preserve_unrelated_assets(root, job, tmp_path):
    output = tmp_path / "build"
    source = root / "jobs/SYNTH-001/project.json"
    first = build(root, source, output)
    a = first.read_bytes()
    build(root, source, output)
    assert first.read_bytes() == a
    assert read_json((output / "changes.json").read_bytes())["changed"] == []
    data = job.model_dump()
    data["registry"]["materials"][0]["diffuse_rgb"] = [190, 100, 50]
    source_copy = tmp_path / "project.json"
    (tmp_path / "fixture-definition.json").write_bytes((source.parent / "fixture-definition.json").read_bytes())
    write_json(source_copy, data)
    build(root, source_copy, output)
    changes = read_json((output / "changes.json").read_bytes())
    assert "vpm/T_Synthetic_001_Diffuse_1.1001.png" in changes["changed"]
    assert "vpm/T_Synthetic_001_Diffuse_1.1002.png" in changes["unchanged"]
    assert "vpm/T_Synthetic_001_ERM_1.1001.png" in changes["unchanged"]
    assert "layout.json" in changes["unchanged"]


def test_unapproved_registry_cannot_build(root, job):
    job.registry.materials[0].status = "proposed"
    with pytest.raises(ValueError, match="approved"):
        prepare_assets(job, load_profiles(root))


@pytest.mark.dcc
@pytest.mark.skipif(not os.environ.get("DT_BLENDER"), reason="Set DT_BLENDER to execute a real isolated Blender roundtrip")
def test_real_blender_export_and_reimport(root, tmp_path):
    path = build(root, root / "jobs/SYNTH-001/project.json", tmp_path / "build", os.environ["DT_BLENDER"])
    report = validate(root, path, tmp_path / "report", os.environ["DT_BLENDER"])
    assert report.development_checks_passed, [c.model_dump() for c in report.checks if c.status == "fail"]
    assert not report.passed
