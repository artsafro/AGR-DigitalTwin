# KPP1 spec comparison v002 — Revit wall lines vs mesh path (issue #29)

Date 2026-10-08. Tool: `uv run dt spec compare`; thresholds, reference sides and the verdict switch in
`benchmark/bench-k01-kpp1/tolerances.json`. Local outputs: `jobs/KPP1/outputs/spec-compare-v012/`
(after Codex review 1 of PR #35; v011 before it, same numbers).
Previous comparison (Revit walls as bounding boxes): `spec-compare-v001.md`.

- a = Revit path, route `revit-twin` (#29): `outputs/revit-twin-v003/` — TwinPack `twin_floor_manifest` +
  `twin_export_floor` for bands 2-4 (Revit 2025, local upgraded copy, document unmodified before and
  after), spec `spec-revit-twin-v008.json`. Walls on their location lines with thickness; glass by
  material transparency; doors from the door records; attachments by the stack rule.
- b = mesh path: `outputs/spec-v010/spec-v010.json` (VPM v005 `SM_Kpp_1.fbx`, spec v0.2 rules of #31).

User decision 2026-10-08: the match / "install Rhino" criterion applies after #29; levels, roof,
parapet and now contours from Revit are the reference.

## Verdict

**no match** — on openings only. Contour equality does not make the whole criterion pass while the
opening criteria fail. Every level, roof, parapet and contour criterion matches:

| Quantity | Revit | Mesh | Difference | Threshold |
|---|---|---|---|---|
| levels L0 / L1 / roof, m | 0.000 / 3.900 / 7.909 | same | 0 | 0.03 |
| roof covering, m | 7.909 | 7.911 | 0.002 | 0.03 |
| parapet top / height, m | 8.650 / 0.741 | 8.650 / 0.739 | 0 / 0.002 | 0.03 |
| L0 contour: area, Hausdorff, kinks | 322.516 m2 | 322.516 m2 | 0.0 %, 0.0 m, 4 = 4 | 2 %, 0.05 m |
| L1 contour: area, Hausdorff, kinks | 322.516 m2 | 322.516 m2 | 0.0 %, 0.0 m, 4 = 4 | 2 %, 0.05 m |

The L0 0.70 m of v001 is gone: the entrance frames are attachments on both paths now (Revit: by the
stack rule, user decision 2026-10-08; mesh: separate parts). **Rhino is not needed for contours**:
the Blender-section contours equal the Revit wall-line contours to 0.0 mm on both levels.

## Openings (no reference)

| Level | Revit | Mesh | Pairs within 0.05 m | Within 0.30 m |
|---|---|---|---|---|
| L0 | 21 (11 doors, 10 windows, 1 across L0-L1) | 21 | 0 | 21 |
| L1 | 11 | 12 | 0 | 10 |

No pairs within 0.05 m. Within 0.30 m: L0 all 21 pairs; L1 10 pairs, 1 Revit and 2 mesh openings
unpaired (the west windows below). The differences are definitions, not positions:
- **Window size.** Revit gives the window family's box: the opening in the wall with its frame
  (1.08 x 1.70 m). The mesh path sees the glass only (0.94 x 1.56 m: the VPM body is closed over
  windows), 7 cm of frame on each side.
- **Depth.** Revit: the host wall's thickness; mesh: the recess or glass depth from the facade.
  The pair box includes depth since PR #32, so this alone moves pairs by up to 0.27 m.
- **Doors.** Same positions, widths and heights on both paths (0.0 m in plan); a door with a
  glazed transom is 2.7 m high on the Revit side (door + panel above, one frame).
- **L1 west, x ~4.0.** Two windows 0.19 m apart: two openings on the mesh (glass gap > 0.15 m), one
  with 2 panes on Revit (family boxes 0.0 m apart) — the count 11 vs 12.

So the opening criterion fails by the unit of measurement (frame vs glass, depth), not by
geometry. User decision 2026-10-08: the spec opening is the hole in the wall with its frame (as
Revit); the glass is attributes `glass_w` / `glass_h` and `panes`; the mesh path measures reveals,
not glass; depth is `opening_depth_default_m` with exceptions. Implemented after #29 (follow-up
issue); the opening criteria are rerun then.

## Questions

Revit path: 9 attachments (3 entrance vestibules with portal beams, 6 door canopies), each one
question with its element ids. Mesh path: 45 (`jobs/KPP1/questions.md` merges by version).
