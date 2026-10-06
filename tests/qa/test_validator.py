"""Validator CLI on generated packages: one good VPM package and one change per negative case.

Cases from the AGR review (2026-10-06): VPM ZIP without GeoJSON must exit 1, FBX 7500 fails,
Glasses=42 and string coordinates fail. Mutations ported from AGR tests/integration/test_pipeline.py
(missing map, UDIM gap, unsafe ZIP path, empty ZIP) where they apply to this validator.
"""
import base64
import json
import struct
import zipfile
from io import BytesIO

import pytest
from PIL import Image

import validate_package as vp
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
STEM = "SM_Test_K_1"
KEYS = PROFILES.vpm["geojson"]["properties_keys"]


def fbx(version=7400):
    return b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", version) + b"\x00" * 64


def png(color=(128, 128, 128)):
    buf = BytesIO()
    Image.new("RGB", (256, 256), color).save(buf, "PNG")  # flat 256 placeholder (reg p.22, p.31)
    return buf.getvalue()


def jpg256():
    buf = BytesIO()
    Image.new("RGB", (256, 256), (200, 200, 200)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def geojson(**over):
    props = {k: "value" for k in KEYS}
    props.update(imageBase64=jpg256(), other="", FNO_code="123 456")
    feature = {"type": "ObjectFeature", "properties": props,
               "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]}, "Glasses": []}
    for key, value in over.items():
        if key in props:
            props[key] = value
        else:
            feature[key] = value if key != "coordinates" else None
            if key == "coordinates":
                feature["geometry"]["coordinates"] = value
                del feature[key]
    return json.dumps({"type": "FeatureCollection", "features": [feature]}).encode()


def good_files():
    files = {f"{STEM}.fbx": fbx(), f"{STEM}.geojson": geojson()}
    for m, colour in (("Diffuse", (120, 110, 100)), ("ERM", (0, 170, 0)), ("Normal", (128, 128, 255))):
        files[f"T_Test_K_1_{m}_1.1001.png"] = png(colour)
    return files


def run(tmp_path, files, name=f"{STEM}.zip", profile=None):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    report = vp.validate(path, profile, PROFILES)
    return report, {s.id: s for s in report.stages}


def test_good_vpm_package_has_no_fail_but_is_not_passed(tmp_path):
    report, st = run(tmp_path, good_files())
    assert {k: st[k].status for k in ("V001", "V007", "V011")} == {"V001": "pass", "V007": "pass", "V011": "pass"}
    assert st["V002"].status == "not_run"  # header passes, units need the scene
    assert st["V012"].status == "review"  # _001 index for free-standing buildings: conflict #20
    assert st["V010"].status == "not_run"  # UCX not checked here: never a silent pass
    assert not report.passed and report.exit_code == 2


def test_missing_geojson_fails_with_exit_1(tmp_path):
    files = good_files()
    del files[f"{STEM}.geojson"]
    report, st = run(tmp_path, files)
    assert st["V001"].status == "fail" and report.exit_code == 1


def test_fbx_7500_fails(tmp_path):
    files = good_files()
    files[f"{STEM}.fbx"] = fbx(7500)
    report, st = run(tmp_path, files)
    assert st["V002"].status == "fail" and report.exit_code == 1


@pytest.mark.parametrize("over", [{"Glasses": 42}, {"coordinates": "x"}, {"coordinates": [1, None]},
                                  {"Glasses": {"M_Test_K_1_MainGlass_1": {"color_RGB": {"Red": 300, "Green": 0, "Blue": 0},
                                                                          "transparency": 0.5, "refraction": 1.5,
                                                                          "roughness": 0, "metallicity": 0}}}])
def test_geojson_type_errors_fail(tmp_path, over):
    files = good_files()
    files[f"{STEM}.geojson"] = geojson(**over)
    _, st = run(tmp_path, files)
    assert st["V011"].status == "fail"


@pytest.mark.parametrize("over, status", [
    ({"FNO_code": ""}, "fail"),          # mandatory for OKS (conflict #2 decided as the checker)
    ({"FNO_code": "12345"}, "fail"),     # XXX, XXX XXX or XXX XXX XXX
    ({"FNO_code": "123456789"}, "pass"),
    ({"act_AGR": ""}, "pass"),           # may be empty
])
def test_oks_empty_fields_follow_checker_conflict_2(tmp_path, over, status):
    files = good_files()
    files[f"{STEM}.geojson"] = geojson(**over)
    _, st = run(tmp_path, files)
    assert st["V011"].status == status


def test_missing_map_fails(tmp_path):
    files = good_files()
    del files["T_Test_K_1_ERM_1.1001.png"]
    files["T_Test_K_1_Diffuse_1.1002.png"] = png()  # keep the PNG count in range
    _, st = run(tmp_path, files)
    assert st["V007"].status == "fail"


def test_udim_gap_fails(tmp_path):
    files = good_files()
    for m in ("Diffuse", "ERM", "Normal"):
        files[f"T_Test_K_1_{m}_1.1003.png"] = png()
    _, st = run(tmp_path, files)
    assert st["V008"].status == "fail"


def test_unsafe_zip_path_fails(tmp_path):
    files = good_files()
    files["../evil.txt"] = b"x"
    report, st = run(tmp_path, files)
    assert st["V001"].status == "fail" and report.exit_code == 1


def test_npm_names_and_ground(tmp_path):
    files = {"0313_Test_K_1_01.fbx": fbx(), "0313_Test_K_1_Ground.fbx": fbx()}
    _, st = run(tmp_path, files, name="0313_Test_K_1.zip", profile="npm")
    assert st["V012"].status == "pass" and st["V001"].status == "pass"
    assert st["V006"].status == "not_run"
    del files["0313_Test_K_1_Ground.fbx"]
    files["0313_Test_K_1_02.fbx"] = fbx()
    _, st = run(tmp_path, files, name="0313_Test_K_1.zip", profile="npm")
    assert st["V001"].status == "fail"


def test_cli_exit_codes(tmp_path, capsys):
    files = good_files()
    del files[f"{STEM}.geojson"]
    run(tmp_path, files)
    assert vp.main([str(tmp_path / f"{STEM}.zip"), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is False and out["exit_code"] == 1
