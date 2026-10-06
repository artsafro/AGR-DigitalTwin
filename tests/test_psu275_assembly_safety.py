"""Assembly preflight tests; Blender tests use isolated files and processes."""
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "jobs/PSU275/scripts/assemble_body_roof.py"


def load_module():
    spec = importlib.util.spec_from_file_location("assemble_body_roof", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def paths(tmp_path):
    body, roof = tmp_path / "body.blend", tmp_path / "roof.json"
    body.write_bytes(b"source body")
    roof.write_text("{}", encoding="utf-8")
    return body, roof, tmp_path / "new.blend", tmp_path / "readback.json"


def test_new_distinct_paths_allowed_without_creating_outputs(paths):
    assert load_module().plan_paths(*paths) == paths
    assert not paths[2].exists()
    assert not paths[3].exists()


@pytest.mark.parametrize("index", [2, 3])
def test_existing_output_refused_and_preserved(paths, index):
    paths[index].write_bytes(b"accepted result")
    with pytest.raises(FileExistsError):
        load_module().plan_paths(*paths)
    assert paths[index].read_bytes() == b"accepted result"
    assert paths[0].read_bytes() == b"source body"


@pytest.mark.parametrize("output_index,input_index", [(2, 0), (2, 1), (3, 0), (3, 1), (3, 2)])
def test_input_output_aliases_refused(paths, output_index, input_index):
    args = list(paths)
    args[output_index] = args[input_index]
    with pytest.raises(ValueError, match="distinct"):
        load_module().plan_paths(*args)
    assert paths[0].read_bytes() == b"source body"


def test_parent_missing_refused_before_any_output(paths):
    args = [*paths[:2], paths[2].parent / "missing" / "new.blend", paths[3]]
    with pytest.raises(FileNotFoundError):
        load_module().plan_paths(*args)
    assert not paths[3].exists()

@pytest.mark.dcc
def test_blender_preserves_loaded_text_and_refuses_second_write(tmp_path):
    """Synthetic fixture, isolated Blender process; no production scene is touched."""
    import hashlib
    import json
    import os
    import subprocess

    blender = os.environ.get("DT_BLENDER")
    if not blender:
        pytest.skip("Set DT_BLENDER for isolated native verification")
    body = tmp_path / "body.blend"
    roof = tmp_path / "roof.json"
    output = tmp_path / "assembled.blend"
    report = tmp_path / "readback.json"
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "import bpy,sys,json\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        "me=bpy.data.meshes.new('BODY')\n"
        "me.from_pydata([(0,0,0),(1,0,0),(1,0,1),(0,0,1)],[],[(0,1,2,3)])\n"
        "obj=bpy.data.objects.new('BODY',me)\n"
        "bpy.context.collection.objects.link(obj)\n"
        "obj['shell_m']=0.4\n"
        "me.materials.append(bpy.data.materials.new('M_BODY'))\n"
        "uv=me.uv_layers.new(name='UVMap')\n"
        "for loop,point in zip(uv.data,[(0,0),(1,0),(1,1),(0,1)]): loop.uv=point\n"
        "bpy.data.texts.new('PROVENANCE.json').write(json.dumps([{'source_ref':'synthetic','role':'outer'}]))\n"
        "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])\n",
        encoding="utf-8",
    )
    common = [blender, "--background", "--factory-startup", "--python-exit-code", "1"]
    made = subprocess.run([*common, "--python", str(fixture), "--", str(body)],
                          capture_output=True, text=True, timeout=90)
    assert made.returncode == 0, made.stdout + made.stderr
    roof.write_text(json.dumps({
        "mesh": {"name": "ROOF", "vertices": [[0,0,1],[1,0,1],[1,1,1],[0,1,1]],
                 "faces": [[0,1,2,3]], "materials": [0]},
        "face_roles": [{"role": "roof", "region": 0}], "regions": [{"region": 0}],
        "scope": "synthetic test",
    }), encoding="utf-8")
    args = [*common, "--python", str(SCRIPT), "--",
            str(body), str(roof), str(output), str(report)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["body_provenance_preserved"]
    assert evidence["roof_provenance_preserved"]
    assert evidence["geometry_uv_materials_transforms_properties_preserved"]
    assert evidence["inputs_unchanged"]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (body, roof, output, report)}
    repeated = subprocess.run(args, capture_output=True, text=True, timeout=90)
    assert repeated.returncode != 0
    assert "FileExistsError" in repeated.stdout + repeated.stderr
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
