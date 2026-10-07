"""Synthetic checks of KPP1 safeguards; these do not establish DCC acceptance."""
import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
from types import ModuleType
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "jobs/KPP1/scripts"
module_spec = importlib.util.spec_from_file_location("kpp1_export_safety", SCRIPTS / "export_safety.py")
safety = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(safety)


@pytest.mark.parametrize("version", ["", "..", "../v2", "v2/sub", r"v2\sub", "v2 x", "v2;rm", "v2.txt", "a" * 65])
def test_bad_version_creates_nothing(tmp_path, version):
    outputs = tmp_path / "outputs"
    with pytest.raises(ValueError):
        safety.reserve_run(outputs, version)
    assert not outputs.exists()


@pytest.mark.parametrize("occupied", ["build", "package-vpm", "package-npm", "npm-textures", "sintez"])
def test_existing_result_preserved_before_other_directories_reserved(tmp_path, occupied):
    outputs = tmp_path / "outputs"
    prior = outputs / f"{occupied}-v002"
    prior.mkdir(parents=True)
    marker = prior / "accepted.bin"
    marker.write_bytes(b"original accepted result")
    with pytest.raises(FileExistsError):
        safety.reserve_run(outputs, "v002")
    assert marker.read_bytes() == b"original accepted result"
    assert list(outputs.iterdir()) == [prior]


def test_fresh_reservation_and_second_run_refusal(tmp_path):
    paths = safety.reserve_run(tmp_path / "outputs", "v002-review")
    assert len(paths) == 5
    assert all(path.is_dir() for path in paths.values())
    paths["build"].joinpath("master.blend").write_bytes(b"original")
    with pytest.raises(FileExistsError):
        safety.reserve_run(tmp_path / "outputs", "v002-review")
    assert paths["build"].joinpath("master.blend").read_bytes() == b"original"


def test_output_root_alias_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlink permission unavailable: {exc}")
    with pytest.raises(ValueError, match="alias"):
        safety.reserve_run(alias / "outputs", "v002")
    assert list(real.iterdir()) == []


def test_delivery_mode_refuses_review_environment():
    safety.require_delivery_mode({})
    with pytest.raises(ValueError, match="review"):
        safety.require_delivery_mode({"KEEP_QUADS": "1"})


def test_current_spec_requires_new_udim_1019():
    spec = json.loads((SCRIPTS / "vpm_textures.json").read_text(encoding="utf-8"))
    atlas = {"finishes": {name: {"udim": finish["udim"]} for name, finish in spec["finishes"].items()}}
    assert 1019 in safety.validate_atlas(atlas, spec)
    del atlas["finishes"]["Walkway_Logicroof"]
    with pytest.raises(ValueError, match="1019"):
        safety.validate_atlas(atlas, spec)


def test_model_faces_require_coverage_even_outside_texture_spec():
    safety.require_udim_regions([1001, 1019, 1001], {1001: {}, 1019: {}})
    with pytest.raises(ValueError, match="1020"):
        safety.require_udim_regions([1001, 1020], {1001: {}, 1019: {}})


def test_same_udim_for_wrong_finish_is_refused():
    with pytest.raises(ValueError, match="stale"):
        safety.validate_atlas({"finishes": {"wrong": {"udim": 1001}}},
                              {"finishes": {"correct": {"udim": 1001}}})


def test_duplicate_atlas_udim_is_refused():
    with pytest.raises(ValueError, match="duplicate"):
        safety.validate_atlas({"finishes": {"a": {"udim": 1001}, "b": {"udim": 1001}}},
                              {"finishes": {"a": {"udim": 1001}}})


@pytest.fixture
def shell_run(tmp_path):
    """Run the real shell pipeline against synthetic local process doubles."""
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if git_bash.exists() else shutil.which("bash")
    if not bash:
        pytest.skip("Bash unavailable")
    job = tmp_path / "job"
    scripts = job / "scripts"
    scripts.mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    shutil.copyfile(SCRIPTS / "export_safety.py", scripts / "export_safety.py")
    run_text = (SCRIPTS / "run_all.sh").read_text(encoding="utf-8")
    blender = fake_bin / "blender"
    run_text = run_text.replace('BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"',
                                f'BL="{blender.as_posix()}"')
    (scripts / "run_all.sh").write_text(run_text, encoding="utf-8")
    stage_text = (SCRIPTS / "run_stage.sh").read_text(encoding="utf-8")
    stage_text = stage_text.replace('BL="/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"',
                                    f'BL="{blender.as_posix()}"')
    (scripts / "run_stage.sh").write_text(stage_text, encoding="utf-8")
    (fake_bin / "py").write_text(
        '#!/usr/bin/env bash\nshift\nexec "$KPP_TEST_PYTHON" "$@"\n', encoding="utf-8")
    (scripts / "package_vpm.py").write_text(
        'import pathlib, sys\np=pathlib.Path(sys.argv[1]).parent\n'
        '(p/"SM_Kpp_1.zip").write_bytes(b"synthetic zip")\n', encoding="utf-8")
    (scripts / "make_npm_atlas.py").write_text(
        'import pathlib, sys\n(pathlib.Path(sys.argv[1])/"npm_atlas.json").write_text("fresh synthetic atlas")\n',
        encoding="utf-8")
    mock = fake_bin / "mock_blender.py"
    mock.write_text(
        'import os, pathlib, sys\nargs=sys.argv[1:]\n'
        'assert "--python-exit-code" in args and "--disable-autoexec" in args\n'
        'script=pathlib.Path(args[args.index("--python")+1]).name\n'
        'tail=args[args.index("--")+1:]\n'
        'if script=="build_kpp1.py":\n'
        ' if os.environ.get("KPP_FAIL_STAGE"): sys.exit(9)\n'
        ' (pathlib.Path(tail[2])/"KPP1_VPM_v006_ucx.blend").write_bytes(b"synthetic master")\n'
        'elif script=="qa_master.py": print("QA-MASTER synthetic")\n'
        'elif script=="qa_overlap.py": print("OVERLAP synthetic")\n'
        'elif script=="export_vpm.py":\n'
        ' print("EXPORT synthetic")\n'
        ' if os.environ.get("KPP_FAIL_EXPORT"): sys.exit(7)\n'
        'elif script=="export_npm.py":\n'
        ' atlas=pathlib.Path(tail[1])/"npm_atlas.json"\n'
        ' assert atlas.read_text()=="fresh synthetic atlas"\n'
        ' (pathlib.Path(tail[2])/"0000_Kpp_1_01.fbx").write_bytes(b"synthetic FBX")\n'
        ' print("EXPORT-NPM synthetic")\n'
        'elif script=="run_agr_checker.py": print("AGR-SUMMARY synthetic")\n',
        encoding="utf-8")
    blender.write_text(f'#!/usr/bin/env bash\nexec "$KPP_TEST_PYTHON" "{mock.as_posix()}" "$@"\n',
                       encoding="utf-8")
    for path in (blender, fake_bin / "py", scripts / "run_stage.sh"):
        path.chmod(0o755)
    env = os.environ.copy()
    env.pop("KEEP_QUADS", None)
    env["KPP_TEST_PYTHON"] = sys.executable.replace("\\", "/")
    env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]

    def run(version="v002", **overrides):
        return subprocess.run([bash, str(scripts / "run_all.sh"), version],
                              env=env | overrides, capture_output=True, text=True, timeout=30)
    return job / "outputs", run


def test_pipeline_preserves_old_build_and_atlas_uses_fresh_version(shell_run):
    outputs, run = shell_run
    for name in ("build-v001", "npm-textures-v001"):
        prior = outputs / name
        prior.mkdir(parents=True)
        (prior / "accepted.txt").write_text("accepted original", encoding="utf-8")
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (outputs / "npm-textures-v002/npm_atlas.json").read_text() == "fresh synthetic atlas"
    assert (outputs / "sintez-v002/0000_Kpp_1.zip").exists()
    for name in ("build-v001", "npm-textures-v001"):
        assert (outputs / name / "accepted.txt").read_text() == "accepted original"
    again = run()
    assert again.returncode != 0
    assert (outputs / "sintez-v002/0000_Kpp_1.zip").exists()


def test_pipeline_refuses_old_version_before_build(shell_run):
    outputs, run = shell_run
    prior = outputs / "package-npm-v002"
    prior.mkdir(parents=True)
    (prior / "accepted.fbx").write_bytes(b"accepted")
    result = run()
    assert result.returncode != 0
    assert not (outputs / "build-v002").exists()
    assert (prior / "accepted.fbx").read_bytes() == b"accepted"


def test_blender_error_is_not_hidden_by_successful_grep(shell_run):
    outputs, run = shell_run
    result = run(KPP_FAIL_EXPORT="1")
    assert result.returncode == 7, result.stdout + result.stderr
    assert not (outputs / "package-vpm-v002/SM_Kpp_1.zip").exists()
    assert not (outputs / "npm-textures-v002/npm_atlas.json").exists()


def test_pipeline_refuses_review_mode_before_build(shell_run):
    outputs, run = shell_run
    result = run(KEEP_QUADS="1")
    assert result.returncode != 0
    assert not outputs.exists()


def test_build_stage_failure_stops_before_export(shell_run):
    outputs, run = shell_run
    result = run(KPP_FAIL_STAGE="1")
    assert result.returncode == 9, result.stdout + result.stderr
    assert not (outputs / "package-vpm-v002/SM_Kpp_1").exists()
    assert not (outputs / "build-v002/KPP1_VPM_v006_ucx.blend").exists()


def test_long_safe_version_works_through_real_stage_launcher(shell_run):
    outputs, run = shell_run
    version = "v" + "2" * 63
    result = run(version)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (outputs / f"build-{version}/KPP1_VPM_v006_ucx.blend").exists()


def test_exporter_stale_atlas_fails_before_scene_or_output_write(tmp_path, monkeypatch):
    """Execute actual exporter preflight; no Blender or synthetic scene is used."""
    spec = json.loads((SCRIPTS / "vpm_textures.json").read_text(encoding="utf-8"))
    atlas = {"finishes": {name: {"udim": finish["udim"]} for name, finish in spec["finishes"].items()
                         if finish["udim"] != 1019}}
    atlas_dir = tmp_path / "atlas"
    atlas_dir.mkdir()
    (atlas_dir / "npm_atlas.json").write_text(json.dumps(atlas), encoding="utf-8")
    out = tmp_path / "out"
    # If preflight reaches any bpy attribute, this empty module raises immediately.
    for name in ("bpy", "bmesh"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    mathutils = ModuleType("mathutils")
    mathutils.Vector = object
    mathutils.Matrix = object
    monkeypatch.setitem(sys.modules, "mathutils", mathutils)
    monkeypatch.setattr(sys, "argv", ["blender", "--", "unused.blend", str(atlas_dir), str(out)])
    monkeypatch.syspath_prepend(str(SCRIPTS))
    # Review copies remain supported by direct exporter, but still require full coverage.
    monkeypatch.setenv("KEEP_QUADS", "1")
    with pytest.raises(ValueError, match="1019"):
        runpy.run_path(str(SCRIPTS / "export_npm.py"), run_name="__main__")
    assert not out.exists()