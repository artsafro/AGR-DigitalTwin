"""Synthetic regression tests for the case-specific GLB atlas renderer."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from PIL import Image
import pytest


@pytest.fixture(scope="module")
def renderer():
    path = Path(__file__).resolve().parents[1] / "technical_library/glb_atlas/build.py"
    spec = importlib.util.spec_from_file_location("glb_atlas_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synthetic_case(tmp_path, renderer):
    inputs = tmp_path / "inputs"
    textures = tmp_path / "textures"
    inputs.mkdir()
    textures.mkdir()
    (inputs / "uv_before.csv").write_text(
        "vertex,id,u,v\n1,2,0,0\n2,2,1,1\n", encoding="utf-8")
    (inputs / "face_uv_before.csv").write_text(
        "face,id,u0,v0,u1,v1\n1,2,0,0,1,1\n", encoding="utf-8")
    texture = textures / "custom.png"
    Image.new("RGBA", (16, 16), (12, 34, 56, 255)).save(texture)
    config = {
        "SIZE": 64,
        "PAD": 2,
        "POTENTIAL_ORDER": [2],
        "LABELS": {"2": "synthetic"},
        "RECTS": {"2": [0, 0, 64, 64]},
        "colors": {},
        "textures": [{"file": "custom.png", "id": 2, "crop": None}],
        "scenarios": {"A_Main": {"face_count": 1, "material_ids": [2]}},
    }
    config["scenarios"]["A_Main"]["input_sha256"] = renderer.input_inventory(
        inputs, textures, config)
    return inputs, textures, config


def test_deterministic_output_and_provenance(renderer, synthetic_case, tmp_path):
    inputs, textures, config = synthetic_case
    first = tmp_path / "first"
    manifest = renderer.build(config, inputs, textures, first, "A_Main")
    expected = manifest["provenance"]["png_sha256"]
    strict = deepcopy(config)
    strict["scenarios"]["A_Main"]["expected_png_sha256"] = expected
    second = tmp_path / "second"
    repeated = renderer.build(strict, inputs, textures, second, "A_Main")

    assert (first / "A_Main_1001_2048_RGBA.png").read_bytes() == (
        second / "A_Main_1001_2048_RGBA.png").read_bytes()
    assert repeated["source_textures"] == ["custom.png"]
    assert repeated["provenance"]["strict_input_match"] is True
    assert repeated["provenance"]["strict_png_match"] is True
    assert repeated["provenance"]["input_sha256"] == strict["scenarios"]["A_Main"]["input_sha256"]
    saved = json.loads((second / "atlas_manifest.json").read_text(encoding="utf-8"))
    assert saved == json.loads(json.dumps(repeated))


def test_changed_input_is_rejected_before_output(renderer, synthetic_case, tmp_path):
    inputs, textures, config = synthetic_case
    path = inputs / "uv_before.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("1,2,0,0", "1,2,0.5,0"), encoding="utf-8")
    output = tmp_path / "changed"
    with pytest.raises(ValueError, match="Input SHA256 mismatch"):
        renderer.build(config, inputs, textures, output, "A_Main")
    assert not output.exists()


def test_nonfinite_and_overwrite_are_rejected(renderer, synthetic_case, tmp_path):
    inputs, textures, config = synthetic_case
    output = tmp_path / "first"
    renderer.build(config, inputs, textures, output, "A_Main")
    with pytest.raises(FileExistsError):
        renderer.build(config, inputs, textures, output, "A_Main")

    trial = deepcopy(config)
    trial["scenarios"]["A_Main"].pop("input_sha256")
    path = inputs / "uv_before.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("1,2,0,0", "1,2,nan,0"), encoding="utf-8")
    with pytest.raises(ValueError, match="Non-finite UV input"):
        renderer.build(trial, inputs, textures, tmp_path / "nan", "A_Main")


def test_wrong_expected_png_is_rejected_before_output(renderer, synthetic_case, tmp_path):
    inputs, textures, config = synthetic_case
    config["scenarios"]["A_Main"]["expected_png_sha256"] = "0" * 64
    output = tmp_path / "wrong-png"
    with pytest.raises(ValueError, match="Rendered PNG SHA256"):
        renderer.build(config, inputs, textures, output, "A_Main")
    assert not output.exists()
