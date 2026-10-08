# KPP1 spec comparison v001 — Revit path vs mesh path (issue #11)

Date 2026-10-08. Tool: `uv run dt spec compare` (`src/dt_ai/spec/compare.py`); thresholds in
`benchmark/bench-k01-kpp1/tolerances.json`. Local outputs: `jobs/KPP1/outputs/spec-compare-v001/`.

- a = Revit path: `outputs/spec-revit-v003/spec-revit-v003c.json` (Revit 2025, local upgraded copy,
  read only, unmodified before and after; PR #30).
- b = mesh path: `outputs/spec-v005/spec-v005.json` (VPM v005 `SM_Kpp_1.fbx`; PR #27).
- Both in the object system (Revit project coordinates). The mesh frame was checked on Revit:
  four outer facade corners at 0.000 land on v005 mesh vertices within 0.0 mm (`object.json`).

**No Rhino verdict.** User decision 2026-10-08: the match / "install Rhino" criterion applies
only after #29 (Revit walls from location lines). Until then this report lists the differences
per level with their cause and side. Levels, roof and parapet from Revit are the reference now;
contours become comparable after #29.

## Levels, roof, parapet (reference: Revit)

| Quantity | Revit | Mesh | Difference | Threshold | Within |
|---|---|---|---|---|---|
| level count | 3 | 3 | 0 | equal | yes |
| L0 / L1 / roof elevation, m | 0.000 / 3.900 / 7.909 | same | 0 | 0.03 | yes |
| roof covering, measured, m | 7.909 | 7.911 | 0.002 | 0.03 | yes |
| parapet top, m | 8.650 | 8.650 | 0.000 | 0.03 | yes |
| parapet height, m | 0.741 | 0.739 | 0.002 | 0.03 | yes |

Level elevations are inputs of both paths (`object.json`, taken from Revit and confirmed by the
user), so their row is equal by construction; the measured checks are the roof covering and the
parapet. The mesh path matches the Revit reference on all of them.

## Contours (reference: after #29)

| Level | Criterion | Revit | Mesh | Difference | Threshold | Within |
|---|---|---|---|---|---|---|
| L0 | area, m2 | 324.196 | 319.480 | 1.45 % | 2 % | yes |
| L0 | Hausdorff, m | | | 0.70 | 0.05 | no |
| L0 | kinks | 28 | 48 | 20 | equal | no |
| L1 | area, m2 | 322.516 | 322.004 | 0.16 % | 2 % | yes |
| L1 | Hausdorff, m | | | 0.26 | 0.05 | no |
| L1 | kinks | 4 | 64 | 60 | equal | no |

Causes, by region (all difference regions are "Revit only"; none is "mesh only"):

| Level | Region | Size | Cause | Side |
|---|---|---|---|---|
| L0 | 6 bumps out of the facade, y -1.03..-0.33 (south x 7.6-8.0, 11.0-11.4, 14.9-15.3, 17.5-17.9) and y 11.33..12.03 (north x 8.4-8.8, 13.8-14.2) | 0.4 x 0.7 m each | Small 150 mm walls of the entrance frames (e.g. 1615083-1615085, z -0.02..2.70) become body boxes: the Revit path takes every wall as body (it has no part connectivity), while these frames are not in the mesh contour at 0.5 m. **This is the 0.70 m Hausdorff of L0.** | Revit path (all walls are body; to be covered with #29) |
| L0 | 11 notches into the facade, 0.23 m deep (south x 0.4-1.6, 5.53-6.53, 8.5-10.5, 15.68-17.08, 21.9-23.1, 25.4-26.6; east y 5.98-6.98, 8.1-9.3; north x 9.35-10.35, 12.23-13.23; west y 3.59-4.59) | 1.0-2.0 m wide | Each notch is a wall opening of a door (Revit category Doors, family `MEP_Отверстие…`, z 0..2.10). At the contour height 0.5 m the mesh section runs into the door recess down to the concrete face; the Revit wall boxes are solid over the opening. By the contour rule (a part not over the full storey height does not change the contour) the facade line is straight here and the door is an opening, so the Revit line is right only by accident. | Mesh path: door recess without glass read as contour (#31); Revit path: boxes solid over openings (#29) |
| L1 | notch south x 12.96-14.14, 0.26 m deep | 1.18 m | Tall opening (windows 1614477 / 1614483 / 1737788 in one frame, z 1.12..6.73) cut at 4.5 m: same as the L0 notches. **This is the 0.26 m Hausdorff of L1.** | Mesh path (#31); Revit path (#29) |
| L1 | notch east y 5.68-6.98, 0.23 m deep | 1.3 m | Door wall opening of L1 (`MEP_Отверстие…`, z 3.90..6.00) | Mesh path (#31); Revit path (#29) |
| L1 | 14 bumps on the north facade, 0.075 x 0.09 m (each < 0.01 m2) | 60 kinks | Edge profiles of the curtain-wall frames (`Обрамление витражей` 1615747, 1615758, 1832606 end exactly there) are in the mesh body; the Revit path makes curtain walls panes. Within 9 cm. | Mesh detail; not a defect of either path |

Kink counts differ for the same reasons: Revit L0 = rectangle + 6 bumps (28 points); mesh L0 =
rectangle + 11 notches (48); mesh L1 = rectangle + 2 notches + 14 frame bumps (64).

## Openings (no reference)

| Level | Revit | Mesh | Pairs outside 0.05 m | Unpaired |
|---|---|---|---|---|
| L0 | 15 | 11 | 11 of 11 | 4 Revit |
| L1 | 9 | 12 | 9 of 9 | 3 mesh |

The two paths count openings in different units, so the pair boxes cannot match yet:
- Revit: one opening per curtain wall (3-5 m wide, frame boxes) and per door; mesh: one per
  glass pane group (0.94 m panes; mullions wider than the 0.25 m join gap split a curtain wall).
- Doors: Revit has them (sill 0); the mesh path has no glass and no through hole there, so they
  are the contour notches above, not openings.
A common opening unit (curtain wall = one opening or panes) is a decision for the user; it is
listed as an open question, not decided here.

## Follow-ups

- #29 — Revit walls from location lines; then rerun this comparison and apply the match / Rhino
  criterion (contours, kinks).
- #31 — mesh path: a door recess without glass at the contour height becomes a
  contour notch instead of an opening.
- Question for the user — the opening unit for comparison (curtain wall as one opening or its panes).
