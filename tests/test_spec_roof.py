"""Sloped and separate roofs, frames per source (issue #9, user decisions 2026-10-08). Synthetic data."""
import math

import pytest
from shapely.geometry import Polygon

from dt_ai.spec import SpecError, extract_spec
from test_spec_contour_shapes import SQUARE10, dump_of, flat, walls
from test_spec_extract import OBJECT, Mesh


def walls_only(top=7.2):
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, top)
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    return b


def roof_part(z0, z1, x0=0.0, x1=10.0, y0=0.0, y1=10.0, name="Roof"):
    """A separate roof slab sloping along y from z0 to z1."""
    r = Mesh(name)
    r.quad((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1))
    return r


def test_drainage_slope_is_a_flat_roof_at_its_area_weighted_height():
    # 6.55 -> 6.65 m over 10 m: 0.57 degrees, mean 6.60; the roof is a separate object (normal)
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.55, 6.65).dump())
    spec, report = extract_spec(d, OBJECT)
    r = report["roof"]
    assert r["plane_m"] == pytest.approx(6.6, abs=0.001) and r["separate_roof_parts"] == 1
    assert (r["surface_z_min_m"], r["surface_z_max_m"]) == (6.55, 6.65)     # the surface, not triangle centres
    assert r["slope_max_deg"] == pytest.approx(math.degrees(math.atan(0.01)), abs=0.01)
    assert spec.roof.parapet_h_m == pytest.approx(0.6, abs=0.01)


def test_input_level_within_10_cm_of_the_mean_is_accepted():
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.62, 6.72).dump())          # mean 6.67, level 6.6
    _, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.67, abs=0.001)


def test_roof_steeper_than_10_degrees_is_a_question():
    d = dump_of(walls_only(6.6))
    rise = 5 * math.tan(math.radians(20))
    for y0, y1, z0, z1 in ((0, 5, 6.6, 6.6 + rise), (5, 10, 6.6 + rise, 6.6)):
        d["meshes"].append(roof_part(z0, z1, y0=y0, y1=y1, name=f"Pitch{y0}").dump())
    with pytest.raises(SpecError, match="steeper than 10 degrees"):
        extract_spec(d, OBJECT)


@pytest.mark.parametrize("part", [roof_part(7.0, 7.0), roof_part(6.6, 6.6, x0=12, x1=22)])
def test_separate_part_off_the_roof_level_or_contour_is_not_the_roof(part):
    d = dump_of(walls_only())
    d["meshes"].append(part.dump())
    with pytest.raises(SpecError, match="no up-facing roof surface"):
        extract_spec(d, OBJECT)


def test_frames_are_chosen_by_source():
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.6, 6.6).dump())
    d["source"] = "model.fbx"
    shift = {"to_object": [[1, 0, 0, 100], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}
    obj = {"id": "bench-synth-box", "frames": {"model.fbx": shift, "revit": OBJECT["frame"]}}
    spec, _ = extract_spec(d, obj)
    assert spec.floors[0].contour[0][:2] == [100.0, 0.0] and spec.frame.source == "model.fbx"
    with pytest.raises(SpecError, match="no frame for source 'other.fbx'"):
        extract_spec({**d, "source": "other.fbx"}, obj)
    with pytest.raises(SpecError, match="both frame and frames"):
        extract_spec(d, {**obj, "frame": shift})


def test_separate_parapet_cap_closes_the_floor_from_above():
    # KPP1 v005: roof and parapet cap are both separate objects; the cap ring counts for closure only
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.6, 6.6, 0.4, 9.6, 0.4, 9.6).dump())     # roof inside a 0.4 m cap ring
    cap = Mesh("Cap")
    outer, inner = SQUARE10, [[0.4, 0.4], [9.6, 0.4], [9.6, 9.6], [0.4, 9.6]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        cap.quad((*outer[a], 7.25), (*outer[c], 7.25), (*inner[c], 7.25), (*inner[a], 7.25))
    d["meshes"].append(cap.dump())
    spec, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6) and report["roof"]["closed_share"] >= 0.99
    without = dump_of(walls_only())
    without["meshes"].append(roof_part(6.6, 6.6, 0.4, 9.6, 0.4, 9.6).dump())
    with pytest.raises(SpecError, match="close only 85%"):
        extract_spec(without, OBJECT)


# --- regressions from Codex review 1 of PR #27 -------------------------------------------------

def test_equipment_top_never_closes_a_missing_roof():
    # F1 (P1): 40 m2 of roof, an equipment box over the other 60 m2 above the parapet
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.6, 6.6, 0.0, 4.0).dump())
    box = Mesh("Equipment")
    box.box((4.0, 0.0, 8.0), (10.0, 10.0, 9.0))
    d["meshes"].append(box.dump())
    with pytest.raises(SpecError, match="close only 40%"):
        extract_spec(d, OBJECT)


def test_drainage_surface_is_judged_by_its_mean_height():
    # F2: 6.25 -> 6.95 m (4 degrees), mean 6.60 = the input level
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.25, 6.95).dump())
    _, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6, abs=0.001)


def test_roof_part_half_outside_the_contour_is_a_question():
    # F3
    d = dump_of(walls_only())
    d["meshes"] += [roof_part(6.6, 6.6).dump(), roof_part(6.69, 6.69, 8.0, 12.0, name="Half").dump()]
    with pytest.raises(SpecError, match="outside the top floor contour"):
        extract_spec(d, OBJECT)


def test_sloped_coping_is_not_a_pitched_roof():
    # F4: complete flat roof at 6.6, a 0.2 m coping at 7.2 sloping 20 degrees inwards
    d = dump_of(walls_only())
    d["meshes"].append(roof_part(6.6, 6.6).dump())
    cop = Mesh("Coping")
    drop = 0.2 * math.tan(math.radians(20))
    outer, inner = SQUARE10, [[0.2, 0.2], [9.8, 0.2], [9.8, 9.8], [0.2, 9.8]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        cop.quad((*outer[a], 7.2), (*outer[c], 7.2), (*inner[c], 7.2 - drop), (*inner[a], 7.2 - drop))
    d["meshes"].append(cop.dump())
    _, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6)


def test_cap_8_cm_above_the_roof_is_not_folded_into_its_height():
    # F6: wide cap at 6.68 (64 m2) around a 6.6 roof (36 m2)
    b = Mesh("Body")
    inner = [[2.0, 2.0], [8.0, 2.0], [8.0, 8.0], [2.0, 8.0]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE10[a], 0), (*SQUARE10[c], 0), (*SQUARE10[c], 6.68), (*SQUARE10[a], 6.68))
        b.quad((*SQUARE10[a], 6.68), (*SQUARE10[c], 6.68), (*inner[c], 6.68), (*inner[a], 6.68))
        b.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 6.68), (*inner[c], 6.68))
    b.quad((2, 2, 6.6), (8, 2, 6.6), (8, 8, 6.6), (2, 8, 6.6))
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, report = extract_spec(dump_of(b), OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6, abs=0.001)
    assert spec.roof.parapet_h_m == pytest.approx(0.08, abs=0.005)
