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
        cap.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 7.25), (*inner[c], 7.25))   # parapet inner face
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
    with pytest.raises(SpecError, match="outside and .* inside the top floor contour"):
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


# --- regressions from Codex review 2 of PR #27 -------------------------------------------------

def test_lower_deck_never_closes_a_missing_roof():
    # R2-1 (P1): 40 m2 roof at 6.6, a wall-connected 60 m2 deck at 5.8 below the missing part
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 7.2, extra_u={0: [4.0], 2: [6.0]}, extra_z=[5.8])   # deck corners on wall vertices
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    b.quad((4, 0, 5.8), (10, 0, 5.8), (10, 10, 5.8), (4, 10, 5.8))
    d = dump_of(b)
    d["meshes"].append(roof_part(6.6, 6.6, 0.0, 4.0).dump())
    with pytest.raises(SpecError, match="close only 40%"):
        extract_spec(d, OBJECT)


def test_equipment_never_closes_a_narrow_building():
    # R2-2 (P1): 10 x 1.5 m, roof on 6 m2 of 15, equipment over the rest above the parapet
    narrow = [[0, 0], [10, 0], [10, 1.5], [0, 1.5]]
    b = Mesh("Body")
    walls(b, narrow, 0.0, 7.2)
    flat(b, Polygon(narrow), 0.0, up=False)
    d = dump_of(b)
    d["meshes"].append(roof_part(6.6, 6.6, 0.0, 4.0, 0.0, 1.5).dump())
    box = Mesh("Equipment")
    box.box((4.0, 0.0, 8.0), (10.0, 1.5, 9.0))
    d["meshes"].append(box.dump())
    with pytest.raises(SpecError, match="close only 40%"):
        extract_spec(d, OBJECT)


def test_narrow_wing_drainage_is_measured():
    # R2-3: L-shaped floor; a 1.5 m wing rising 6.48 -> 6.72 is roof, its slope is reported
    contour = [[0, 0], [10, 0], [10, 10], [1.5, 10], [1.5, 20], [0, 20]]
    b = Mesh("Body")
    walls(b, contour, 0.0, 7.2)
    flat(b, Polygon(contour), 0.0, up=False)
    d = dump_of(b)
    d["meshes"] += [roof_part(6.6, 6.6).dump(), roof_part(6.48, 6.72, 0.0, 1.5, 10.0, 20.0, name="Wing").dump()]
    _, report = extract_spec(d, OBJECT)
    assert report["roof"]["slope_max_deg"] == pytest.approx(math.degrees(math.atan(0.024)), abs=0.05)
    assert (report["roof"]["surface_z_min_m"], report["roof"]["surface_z_max_m"]) == (6.48, 6.72)


def test_higher_ring_without_cap_evidence_stays_roof():
    # R2-6: annulus at 6.68 around a 6.60 centre, walls up to 7.20: not at the parapet top, so roof
    d = dump_of(walls_only())
    ring = Mesh("Ring")
    outer, inner = SQUARE10, [[2, 2], [8, 2], [8, 8], [2, 8]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        ring.quad((*outer[a], 6.68), (*outer[c], 6.68), (*inner[c], 6.68), (*inner[a], 6.68))
    d["meshes"] += [ring.dump(), roof_part(6.6, 6.6, 2.0, 8.0, 2.0, 8.0).dump()]
    _, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6512, abs=0.001)


@pytest.mark.parametrize("x0, x1", [(9.04, 10.04), (9.6, 19.6)])
def test_slightly_or_mostly_outside_part_is_a_question(x0, x1):
    # R2-7: 4 % or 96 % outside, both with real area on each side
    d = dump_of(walls_only())
    d["meshes"] += [roof_part(6.6, 6.6).dump(), roof_part(6.69, 6.69, x0, x1, name="Edge").dump()]
    with pytest.raises(SpecError, match="outside and .* inside the top floor contour"):
        extract_spec(d, OBJECT)


# --- regressions from Codex review 3 of PR #27 -------------------------------------------------

@pytest.mark.parametrize("narrow", [False, True])
def test_equipment_at_the_parapet_height_never_closes_a_missing_roof(narrow):
    # R3-1 (P1): a detached box 7.0-7.2 m (the parapet height) over the part without roof
    outline = [[0, 0], [10, 0], [10, 1.5], [0, 1.5]] if narrow else SQUARE10
    y1 = 1.5 if narrow else 10.0
    b = Mesh("Body")
    walls(b, outline, 0.0, 7.2)
    flat(b, Polygon(outline), 0.0, up=False)
    d = dump_of(b)
    d["meshes"].append(roof_part(6.6, 6.6, 0.0, 4.0, 0.0, y1).dump())
    box = Mesh("Equipment")
    box.box((4.0001, 0.0001, 7.0), (9.9999, y1 - 0.0001, 7.2))
    d["meshes"].append(box.dump())
    with pytest.raises(SpecError, match="close only 40%"):
        extract_spec(d, OBJECT)


def test_deck_below_a_sloped_roof_never_closes_it():
    # R3-2 (P1): roof over 40 % sloping 6.25 -> 6.95 (mean 6.60), a wall-connected deck at 6.30 elsewhere
    b = Mesh("Body")
    walls(b, SQUARE10, 0.0, 7.2, extra_u={0: [4.0], 2: [6.0]}, extra_z=[6.3])
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    b.quad((4, 0, 6.3), (10, 0, 6.3), (10, 10, 6.3), (4, 10, 6.3))
    d = dump_of(b)
    d["meshes"].append(roof_part(6.25, 6.95, 0.0, 4.0).dump())
    with pytest.raises(SpecError, match="close only 40%"):
        extract_spec(d, OBJECT)


def test_cap_is_known_by_its_parapet_not_by_the_highest_edge_point():
    # R3-3: real cap 6.68 over inner parapet faces around a 6.60 roof; a thin upstand reaches 7.20
    b = Mesh("Body")
    inner = [[2.0, 2.0], [8.0, 2.0], [8.0, 8.0], [2.0, 8.0]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE10[a], 0), (*SQUARE10[c], 0), (*SQUARE10[c], 6.68), (*SQUARE10[a], 6.68))
        b.quad((*SQUARE10[a], 6.68), (*SQUARE10[c], 6.68), (*inner[c], 6.68), (*inner[a], 6.68))
        b.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 6.68), (*inner[c], 6.68))
    b.quad((2, 2, 6.6), (8, 2, 6.6), (8, 8, 6.6), (2, 8, 6.6))
    b.quad((0, 0, 6.68), (0.1, 0, 6.68), (0.1, 0, 7.2), (0, 0, 7.2))          # thin vertical upstand
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    _, report = extract_spec(dump_of(b), OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.6, abs=0.001)


def test_roof_without_a_parapet_keeps_its_edge_ring():
    # R3-4: walls end at 6.60, roof ring 6.60 at the edge and centre 6.65: both are roof
    d = dump_of(walls_only(6.6))
    ring = Mesh("Ring")
    inner = [[2, 2], [8, 2], [8, 8], [2, 8]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        ring.quad((*SQUARE10[a], 6.6), (*SQUARE10[c], 6.6), (*inner[c], 6.6), (*inner[a], 6.6))
    d["meshes"] += [ring.dump(), roof_part(6.65, 6.65, 2.0, 8.0, 2.0, 8.0).dump()]
    _, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.618, abs=0.001) and report["roof"]["closed_share"] == 1.0



def test_parapet_is_measured_from_the_roof_level_not_from_an_inset_roof_plane():
    # B02 (user rule 2026-10-10, pattern roof-inset-plane): the roof plane is inset 5 mm above the
    # parapet foot; the spec heights come from LEVEL_roof (6.6), so the parapet is 0.6, not 0.595
    b = Mesh("Body")
    inner = [[0.3, 0.3], [9.7, 0.3], [9.7, 9.7], [0.3, 9.7]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE10[a], 0), (*SQUARE10[c], 0), (*SQUARE10[c], 7.2), (*SQUARE10[a], 7.2))
        b.quad((*SQUARE10[a], 7.2), (*SQUARE10[c], 7.2), (*inner[c], 7.2), (*inner[a], 7.2))
        b.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 7.2), (*inner[c], 7.2))
    roof = Mesh("RoofPlane")
    roof.quad((0.3, 0.3, 6.605), (9.7, 0.3, 6.605), (9.7, 9.7, 6.605), (0.3, 9.7, 6.605))
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    d = dump_of(b)
    d["meshes"].append(roof.dump())
    spec, report = extract_spec(d, OBJECT)
    assert report["roof"]["plane_m"] == pytest.approx(6.605, abs=0.001)
    assert spec.roof.parapet_h_m == 0.6



@pytest.mark.parametrize("roof_z", [6.605, 6.65, 6.69])
def test_roof_without_a_parapet_has_none_whatever_the_plane_height(roof_z):
    # Codex review 1 of PR #54: walls and a flat roof ending at roof_z (no parapet) near LEVEL_roof 6.6
    b = Mesh("Body")
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE10[a], 0), (*SQUARE10[c], 0), (*SQUARE10[c], roof_z), (*SQUARE10[a], roof_z))
    b.quad((0, 0, roof_z), (10, 0, roof_z), (10, 10, roof_z), (0, 10, roof_z))
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    spec, _ = extract_spec(dump_of(b), OBJECT)
    assert spec.roof.parapet_h_m == 0.0



@pytest.mark.parametrize("gap", [0.002, 0.010])
def test_a_low_real_parapet_does_not_depend_on_the_roof_plane(gap):
    # Codex review 2 of PR #54: parapet inner faces 6.600-6.625 m, an inset plane 2 or 10 mm up
    b = Mesh("Body")
    inner = [[0.3, 0.3], [9.7, 0.3], [9.7, 9.7], [0.3, 9.7]]
    for w in range(4):
        a, c = w, (w + 1) % 4
        b.quad((*SQUARE10[a], 0), (*SQUARE10[c], 0), (*SQUARE10[c], 6.625), (*SQUARE10[a], 6.625))
        b.quad((*SQUARE10[a], 6.625), (*SQUARE10[c], 6.625), (*inner[c], 6.625), (*inner[a], 6.625))
        b.quad((*inner[c], 6.6), (*inner[a], 6.6), (*inner[a], 6.625), (*inner[c], 6.625))
    roof = Mesh("RoofPlane")
    z = 6.6 + gap
    roof.quad((0.28, 0.28, z), (9.72, 0.28, z), (9.72, 9.72, z), (0.28, 9.72, z))
    flat(b, Polygon(SQUARE10), 0.0, up=False)
    d = dump_of(b)
    d["meshes"].append(roof.dump())
    spec, _ = extract_spec(d, OBJECT)
    assert spec.roof.parapet_h_m == 0.025
