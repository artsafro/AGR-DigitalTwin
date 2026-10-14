# OBJ03 — build by source modules (`from_source`): report

Date 2026-10-14. Branches: `harness/from-source-modules` (PR #106, code), `job/obj03-decor` (job decisions,
`modules/modules.json`, this report). Checker runs below are the main agent's own, **not independent**
(`independent-checker` was not available in the session; rerun it before acceptance).

## 1. Where it ended

| Version | Triangles (NPM 150 000) | Checks (own run) | What changed |
|---|---|---|---|
| v003 | 85 720 | 10/10 pass | first full build by modules: walls per storey, slab boxes, decor boxes |
| v005 | 140 013 | 10/10 pass | review 1: real decor sections, sloped balconies, balcony glass railings, enclosure without top, dark inserts |
| v006 | 129 867 | 10/10 pass | review 2: one mesh per run, piers into bands, dark inserts as inset boxes |
| v007 | 297 452 | 9/10: triangle_budget fails | review 3: bands main and continuous, collars round deeper piers, corner bands meet, inserts per plane |
| v008 | 133 926 | 10/10 pass | joints: main = further projecting, no collars (superseded the same day) |
| v009 | 95 803 | 11/11 pass incl. `complexity` | pattern `primitive-first`: storey bands as frames, piers through, plates as ids, two deliveries |

| v010 | 101 756 | 11/11 pass | Codex review 1 of #106: source decor no longer dropped (kept as source faces) |
| **v011** | **99 782** | **11/11 pass** | Codex review 2 of #106: kept source faces on built elements not doubled (1 974 dropped as covered), band ids per piece, slat tops are no screen top |

### v010 (after Codex review 1 of #106, 2026-10-14)

v009 dropped 1 442 source decor pieces (6 172 triangles) with no count: flat pieces and pieces no section is taken
of. User decision: keep them as the source's own faces, group `decor_as_source` (budget 8 000), listed here; nothing
of the source is dropped. Where (`outputs/from-source-v010/review/decor_as_source-only-persp.png`): strips along the
piers, short dashes at the storey lines, the roof edge; in the assembled model they are almost entirely hidden.
769 degenerate source triangles (no area) are counted and not built. Other changes: deck with no underside = its
plane, enclosure top only from the source, storey band id from its source.

### v009 (pattern primitive-first, 2026-10-14)

Outputs (local, git-ignored): `jobs/OBJ03/outputs/from-source-v009/`
- `npm/model.fbx` (+ `model.blend`) - attached, welded, checked; `modules/modules.blend` (+ `modules-scene.json`) -
  4 089 objects in 10 collections, 1 484 meshes, 624 of them shared (instances), read back 95 805 triangles;
- `check.json`, `summary.json`, `modules-report.json`, `review/ISSUE_{05,08,10,12}-*.png` and
  `review/ISSUE_08-sheet.png`, `ISSUE_10-sheet.png` (source left, model right) for the user's confirmation.

Checks (own run, not independent): bbox 0.0199 m, levels 0.0, floor_areas 0.35 %, silhouettes 0.987, mesh clean
(0 non-manifold, 0 overlaps), triangle_budget 95 803, opening_planes 0.9985, material ids ok, decor pass (empty),
complexity pass (budget per group, 12 section points max, 0 copies not instanced, 0 profiles without silhouette).
bbox grew from 0.001 to 0.02 m: a collapsed step keeps the larger side (the silhouette), so a few sections stand
up to 2 cm further out.

Before / after by module (triangles):

| Module | v008 | v009 | Budget (rough; the user holds the total, 2026-10-14) |
|---|---|---|---|
| walls | 21 472 | 21 472 | 24 000 |
| slabs | 11 632 | 11 632 | 12 000 |
| terraces | 308 | 308 | 1 000 |
| superstructure | 44 | 44 | 1 000 |
| parapets | 3 552 | 3 552 | 6 000 |
| decor, total | 96 918 | 58 795 | - |
| - storey band frames (8 bands, 57 pieces, 659 m) | in bands | 1 098 | 4 000 |
| - piers (1 328, through) | | 29 604 | 32 000 |
| - other bands (497) | | 5 716 | 10 000 |
| - balconies (187) | | 2 279 | 8 000 |
| - dark inserts (2 010 boxes) | | 20 100 | 22 000 |
| **total** | **133 926** | **95 803** | 150 000 |

Decor reduction: 2 839 thin plates (sills / heads) are no geometry - the openings' reveal faces carry ids 7 / 8;
320 band stops inside piers; silhouette test: 871 sections built as their box, 992 kept as a profile (steps
0.07-0.10 m, user); section points max 12; 196 pieces with no section skipped (counted).

Type catalogue (instances by translation only): piers 1 328 -> 798 types, bands 497 -> 149, balconies 187 -> 61,
dark inserts 2 010 -> 409, storey bands 8 unique. A turned copy is its own type (backlog EG5).

v007 outputs (local, git-ignored): `jobs/OBJ03/outputs/from-source-v007/` - `model.fbx`, `check.json`, `spec.json`,
`modules-report.json`, `ISSUE_*-v007.png` (source left, model right, for the user's markers 01-14).
v007 checks: bbox 0.0098 m, levels 0.0, floor_areas 0.35 % (spec-based), silhouettes 0.988, mesh clean (0
non-manifold, 0 overlaps, 0 open loops not allowed), opening planes 0.9985, material ids ok, decor pass (empty: the
spec has no decor - see 4.3).

Decor triangles in v007: collars 106 410 (3 052), pier pieces 73 917 (4 056 after the cut at bands), bands 57 182
(3 996). Sections: median 7 points, max 18; caps of non-quad sections are triangulated.

## 2. What works (user-confirmed by review)

- Source taken apart into modules (`modules/modules.json`, `build_as` per group), confirmed by the user with pictures.
- Walls storey by storey on the outline of the slab above (set 20 mm in, standing on the slabs), quads, glass =
  opening at the OD1 depth with reveals; openings keep the reveal depth off convex corners.
- Slabs and walkable decks as closed boxes (quad fill clipped by the outline, CDT only per cell, counted).
- Decor by real section per piece (piers per storey, balconies with their sloped underside), one mesh per run,
  bands continuous through piers and round corners, piers recessed 5 mm into bands with no hidden caps.
- Glass railings (terraces and balconies): one closed 20 mm plate per free side; frames and trims texture.
- Dark inserts (slots 70/72): boxes set into the wall, no back face, off the openings.
- Screen enclosure on the roof: planes, no top (as the source).
- The spec rebuilt by the same modules; the same checkers as the spec path.

## 3. What does not work yet

1. Budget solved in v009 (95 803); per-group budgets rough, the total 150 000 holds (user 2026-10-14).
2. Markers 08 / 10: confirmed by the user on v009 (2026-10-14).
3. Marker 11 (broken geometry at the SW corner): the cause was the corner insert box (fixed in v007 by grouping inserts
   per plane) - to be confirmed on the picture.
4. `check_decor` checks nothing on this path: the spec by modules carries no decor.
5. `opening_planes` checks the spec measured by the same modules: partly self-referential.
6. Instances only by translation; `npm/` is not regenerated from an edited `modules.blend` (backlog EG5).
7. Performance: v007 takes about 10 min (band-band corner test and pier lookups are O(n^2) over ~4 000 bands).

## 4. Work for the harness (engine, algorithms, checker, logic)

### 4.1 from_source
- Budget control: collars as boxes or only where a pier stands out of the band by more than a set depth; caps
  of non-quad sections quadrangulated; per-module triangle report against the profile limit before export.
- Spatial index (STRtree) for joints and corners; one pass instead of pairs.
- Decor in the spec by modules (kinds band / strip / panel, sections, runs) so `check_decor` compares something.
- Section choice: the longest piece's section per run is a heuristic; a rule for when sections differ in one run.
- Wall finishes as walls (ids 1-5 per cell from the nearest source finish) - now every wall cell is id 1.
- Corner windows: openings stop 0.45 m off convex corners; a real corner window (glass round the corner) is not
  modelled (marker 14b).
- Spec-by-modules vs an independent spec: the extractor (`dt spec extract`) cannot read a panelised OBJ03 (#84,
  #96, #97, #98); the two paths should be reconciled or the contract stated per path.

### 4.2 Checker (twinqa)
- Weld is a grid, not a distance weld (#101, P1, open); the engine's weld can move a vertex past weld_m (#102);
  welded opening end vs strip cut (#103); extractor weld of non-adjacent points (#104); patterns out of date (#105).
- New rules of this branch to review: seated loops, decor mesh left out, slab boxes, overlap = deeper than weld_m,
  spec-based storey areas, open enclosure top, robust silhouette union (GEOS fallback).

### 4.3 Open issues kept
#84 / #94 (DP sliver; PR open with P1 #95), #91 enclosure shell for mid / VPM, #96 decor extractor on a panelised
source, #97 self-crossing contour, #98 engine terraces, #101-#105 retro review of #99 / #100.

## 5. Decisions recorded (where)
- Modules and their treatment: `jobs/OBJ03/modules/modules.json` (`build_as`, `build`), `jobs/OBJ03/STATE.md`.
- Glass railings: pattern `terrace`. Decor by modules: pattern `facade-decor-inset`. Enclosure without top: pattern
  `roof-screen-enclosure`. Weld 3 mm: spec `weld_m`, merged #99. Overlap = deeper than weld; spec-based storey
  areas for panelised sources: `src/twinqa/geometry/checks.py` docstrings, PR #106.
- Workflow: "disputed geometry - look first, then classify" (`docs/agents/WORKFLOW.md`, merged #99).
