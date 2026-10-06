"""Standards loader: lock, strict parsing, conflict annotations (standards/README.md)."""
import json
import shutil

import pytest

from twinqa.io import digest_text, read_json, read_yaml
from twinqa.profiles import DEFAULT_STANDARDS, load_profiles


@pytest.fixture
def standards_copy(tmp_path, monkeypatch):
    folder = tmp_path / "standards"
    shutil.copytree(DEFAULT_STANDARDS, folder, ignore=shutil.ignore_patterns("*.pdf"))
    lock_path = folder / "source/source-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["pdf_default_location"] = str(tmp_path / "absent.pdf")
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.delenv("TWINQA_REGULATION_PDF", raising=False)
    return folder


def relock(folder, name):
    lock_path = folder / "source/source-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["profiles"][name] = digest_text(folder / name)
    lock_path.write_text(json.dumps(lock), encoding="utf-8")


def test_repository_standards_load():
    p = load_profiles()
    assert p.vpm["uv"]["diffuse_density_px_per_m"] == {"min": 512, "max": 1706, "formula": "texture_side_px / polygon_length_m"}
    assert p.conflict("vpm", "geojson.Glasses")["ids"] == [13]
    assert p.conflict("npm", "archive.max_bytes")["status"] == "noted"  # conflict #12 decided
    assert [s["id"] for s in p.validator["stages"]] == [f"V{i:03d}" for i in range(1, 18)]


def test_pdf_is_optional_but_verified_when_present(standards_copy, tmp_path, monkeypatch):
    assert load_profiles(standards_copy).pdf_verified is False
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"%PDF-1.4 not the regulation")
    monkeypatch.setenv("TWINQA_REGULATION_PDF", str(fake))
    with pytest.raises(ValueError, match="PDF hash mismatch"):
        load_profiles(standards_copy)


def test_unlocked_profile_change_rejected(standards_copy):
    path = standards_copy / "NPM_STANDARD.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("max_file_bytes: 3145728", "max_file_bytes: 4000000"), encoding="utf-8")
    with pytest.raises(ValueError, match="Unreviewed profile change"):
        load_profiles(standards_copy)


def test_conflict_annotation_must_name_existing_field(standards_copy):
    path = standards_copy / "VPM_STANDARD.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "  uv.no_such_field: {ids: [9], status: review, note: x}\n", encoding="utf-8")
    relock(standards_copy, "VPM_STANDARD.yaml")
    with pytest.raises(ValueError, match="unknown field"):
        load_profiles(standards_copy)


def test_duplicate_keys_and_nonfinite_values_rejected(tmp_path):
    with pytest.raises(ValueError, match="Duplicate key"):
        read_json(b'{"a": 1, "a": 2}')
    with pytest.raises(ValueError, match="Nonfinite"):
        read_json(b'{"a": NaN}')
    for text, match in (("a: 1\na: 2\n", "Duplicate key"), ("a: .nan\n", "Nonfinite")):
        path = tmp_path / "x.yaml"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            read_yaml(path)


def test_size_limits_are_binary_units_conflict_12():
    from twinqa.bundle import size_status
    p = load_profiles()
    assert p.npm["archive"]["max_bytes"] == 1024 ** 3 and p.vpm["archive"]["oks_max_bytes"] == 500 * 1024 ** 2
    assert size_status(500 * 1024 ** 2, p.vpm["archive"]["oks_max_bytes"])[0] == "pass"
    assert size_status(500 * 1024 ** 2 + 1, p.vpm["archive"]["oks_max_bytes"])[0] == "fail"
