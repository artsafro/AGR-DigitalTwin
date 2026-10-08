# KPP1 spec comparison v003 — two paths match (issue #36, spec v0.3)

Date 2026-10-09. Tool: `uv run dt spec compare`; thresholds, reference sides and the verdict in
`benchmark/bench-k01-kpp1/tolerances.json` (verdict enabled since #29). Local outputs:
`jobs/KPP1/outputs/spec-compare-v018/`. Previous: `spec-compare-v002.md` (no match on openings only).

- a = Revit path (`revit-twin`, walls on their location lines, #29): `outputs/revit-twin-v003/`
  (TwinPack export, Revit 2025, document unmodified), spec `spec-revit-twin-v011.json`.
- b = mesh path (Blender sections of VPM v005 `SM_Kpp_1.fbx`): `outputs/spec-v016/spec-v016.json`.
- Both spec v0.3 (user decision 2026-10-08): the opening is the hole in the wall with its frame;
  glass is `glass_w` / `glass_h` and `panes`; `depth_m` only as an exception to
  `opening_depth_default_m` (0.2 m; no exception on KPP1).

## Verdict: **match** — every criterion of HARNESS_PLAN §4 within its threshold

| Criterion | Revit | Mesh | Difference | Threshold |
|---|---|---|---|---|
| level count | 3 | 3 | 0 | equal |
| levels L0 / L1 / roof, m | 0.000 / 3.900 / 7.909 | same | 0 | 0.03 |
| roof covering, m | 7.909 | 7.911 | 0.002 | 0.03 |
| parapet top / height, m | 8.650 / 0.741 | 8.650 / 0.739 | 0 / 0.002 | 0.03 |
| L0 contour: area, Hausdorff, kinks | 322.516 m2 | 322.516 m2 | 0.0 %, 0.0 m, 4 = 4 | 2 %, 0.05 m, equal |
| L1 contour: area, Hausdorff, kinks | 322.516 m2 | 322.516 m2 | 0.0 %, 0.0 m, 4 = 4 | 2 %, 0.05 m, equal |
| L0 openings: count, pairs (worst) | 21 | 21 | 21 pairs, 0.005 m | equal, 0.05 m |
| L1 openings: count, pairs (worst) | 11 | 11 | 11 pairs, 0.005 m | equal, 0.05 m |

L0 holds 11 doors and 10 windows, one of them a single frame through the L1 line (`level_to: L1`,
z 1.2-6.65, 4 panes); L1 holds 10 windows and 1 door.

## What made the openings match (v002 -> v003)

- **Same definition.** v002 compared the Revit window family box (1.08 x 1.70) with the mesh glass
  (0.94 x 1.56). In v0.3 both give the hole with its frame: the mesh path reads the reveal of the
  body around the glass (the recess pieces it touches, 18 openings on KPP1); the Revit path reads
  the window frame wall (a curtain-function wall `ADSK_Стена для окна_рамка 50x100` hosting the
  window: its line and heights) or the embedded curtain wall. Example, south L0: mesh reveal
  x 18.395-19.57, z 1.2-3.0; Revit frame wall line 18.395-19.575, z 1.2-3.0.
- **Glass as attributes.** The panes in one reveal are one opening (`panes: 2` for the two 0.785 m
  panes of L1 west, 0.19 m apart), so the counts agree (11 = 11 on L1).
- **Depth.** Not compared per opening any more: both sides use the 0.2 m default (mesh reveals
  0.23-0.26 m are within the 0.10 m exception threshold).

## Not compared / open

- Revit `window` elements without a transparent material (vent grilles, 8 on L0, 1 on L1) are no
  openings on the Revit path; the mesh path has no element there either. HARNESS_PLAN §3 lists
  vent grilles among inset elements — how to carry them is open.
- `glass_w` / `glass_h` are not a comparison criterion (Revit: family / panel extents; mesh: panes).
- Questions: Revit 9 (attachments: vestibules, canopies); mesh 25.
