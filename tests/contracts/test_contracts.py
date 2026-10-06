import copy
import shutil

import pytest
from pydantic import ValidationError

from dt_ai.core.io import read_json, read_yaml
from dt_ai.core.models import BuildJob, MaterialRegistry, ProjectManifest, ValidationReport, WindowType
from dt_ai.core.profiles import load_profiles
from dt_ai.materials.registry import merge_proposals


def test_fixture_and_window_validate(root, job):
    assert len(job.master.surfaces) == 6
    WindowType.model_validate(read_json((root / "tests/fixtures/window.json").read_bytes()))


@pytest.mark.parametrize("mutation", ["duplicate_id", "unknown_material", "approved_without_evidence", "invented_field", "channel_overflow", "nonfinite", "real_with_synthetic"])
def test_invalid_contracts_are_rejected(job, mutation):
    data = job.model_dump()
    if mutation == "duplicate_id":
        data["registry"]["materials"][1]["id"] = data["registry"]["materials"][0]["id"]
    elif mutation == "unknown_material":
        data["master"]["surfaces"][0]["material_id"] = "MAT_Absent"
    elif mutation == "approved_without_evidence":
        data["registry"]["materials"][0]["approval"] = None
    elif mutation == "invented_field":
        data["project"]["invented_height"] = 123
    elif mutation == "channel_overflow":
        data["registry"]["materials"][0]["emissive"] = 256
    elif mutation == "nonfinite":
        data["master"]["surfaces"][0]["vertices"][0][0] = float("nan")
    else:
        data["project"]["synthetic"] = False
    with pytest.raises(ValidationError):
        BuildJob.model_validate(data)


def test_missing_elevation_cannot_be_approved(job):
    data = job.project.model_dump()
    data["placement"]["status"] = "approved"
    with pytest.raises(ValidationError):
        ProjectManifest.model_validate(data)


def test_proposals_do_not_overwrite_approved(job):
    proposal = job.registry.model_dump()
    proposal["materials"][0]["diffuse_rgb"] = [1, 2, 3]
    proposal["materials"][0]["status"] = "proposed"
    proposed = MaterialRegistry.model_validate(proposal)
    merged, conflicts = merge_proposals(job.registry, proposed)
    assert merged.model_dump() == job.registry.model_dump()
    assert len(conflicts) == 1
    assert conflicts[0]["proposal"]["diffuse_rgb"] == [1, 2, 3]


def test_yaml_duplicate_keys_rejected(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text("version: 1\nversion: 2\n")
    with pytest.raises(ValueError, match="Duplicate"):
        read_yaml(path)


def test_json_duplicate_and_nonfinite_rejected():
    for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
        with pytest.raises(ValueError):
            read_json(raw)


def test_unreviewed_profile_change_rejected(root, tmp_path):
    shutil.copytree(root / "standards", tmp_path / "standards")
    profile = tmp_path / "standards/VPM_STANDARD.yaml"
    profile.write_text(profile.read_text(encoding="utf-8").replace("R: Emissive, G: Roughness", "R: Roughness, G: Emissive"), encoding="utf-8")
    with pytest.raises(ValueError, match="Unreviewed"):
        load_profiles(tmp_path)


def test_all_profile_rules_have_page_evidence(root):
    profiles = load_profiles(root)
    rows = read_json((root / "standards/traceability.json").read_bytes())
    ids = [row["rule"] for row in rows]
    assert len(ids) == len(set(ids))
    assert {s["id"] for s in profiles["DELIVERY_VALIDATOR.yaml"]["stages"]} <= set(ids)
    assert all(row["source_sha256"] == profiles["NPM_STANDARD.yaml"]["source"]["sha256"] for row in rows)
