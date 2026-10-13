# OBJ03 — panelised tower, facade decor, through the harness

Pipeline status: draft

Object `OBJ03` (former `case-alina-bld`), spec id `obj03-decor`, branch `job/obj03-decor`. Purpose: the
building of the accepted colleague case (`docs/cases.md`) through spec -> engine -> checkers, mixed mode for
what the engine lacks (`EG<n>`), and a count of decor elements against the colleague's 2471.

## Source (read only)

- Source .max, layer `Геометрия исходная` (3ds Max 2024, metres); other layers are the colleague's results.
- `data/sources/OBJ03/source-geometry-v001.fbx` (FBX 2014, Z up, metres), dump `dumps/source-dump-v001.json`;
  dump with material slots `jobs/OBJ03/outputs/source-dump-materials-v001.json` (local).
- Class `panelised`: no closed body; the facade is RailClone panels. Contours by panels (#83).
- Slabs `Shape211223725` (storeys), `Shape211223718` (terrace decks).

## Decisions (user)

- 2026-10-12 rules 1-5, implemented in #80, #81, #83 (panelised source, mid-storey section, parapet thickness
  default, `--collect-stops` without provisional values).
- 2026-10-13 **1a**: protrusions by segment and the terrace storey's own slab (#87 / #88 in #89), no new fields.
- 2026-10-13 **2a**: 96.55 is the roof, 95.75 is no level (top storey 92.3-96.55). The roof screen enclosure
  `RailClone2142` (up to 102.56) is planes in `npm_min` (pattern `roof-screen-enclosure`, #92):
  `roof_screens`. Its mid / VPM shell: issue #91.
- 2026-10-13 **3a**: OD1 applies, opening depth default 0.4 (C24 record updated).
- Parapet thickness default 0.3 (`parapet_thickness_default_m`).
- Terrace levels L16 / L20 / L24 = walkable tops of the decks (56.2 / 69.4 / 82.6), 0.2 above the slabs.
- 2026-10-13 roof sliver (stop at 96.55, 0.07 m2 at (57.70, 151.83)): **A** - the corner niche is open, no roof
  over it; the niche lies outside the contour, the stop is the contour simplification (#84; fix #94 open, its P1 #95).
- 2026-10-13 stops and build errors: never fixed in the run - the element is skipped, marked in the report, the
  rest is built (scratch skips in `C:/x/t-obj03/run/`, local).
- 2026-10-13 building weld `weld_m` 3 mm inclusive (merged #99) and pointed corners as triangles (merged #100).
- 2026-10-13 triangulated horizontal faces - **cancelled** (local WIP branch `harness/tri-faces`, no PR). New build
  path `from_source` by source modules, beside `from_spec`, both through the same checkers; the spec stays the
  contract for the checks. Step 1: modules of the source (`modules/modules.json` + renders, local png) - waits for
  the user's confirmation before any build. Step 2: walls by their own contour, quads; slabs inset, quad fill
  clipped by the contour (CDT only as a reported fallback); decor one box per element (`facade-decor-inset`, 20 mm
  inset); glazing = glass, depth 0.4 (OD1); superstructure planes (2a); attachments > 0.8 m skipped (EG2); each
  module compared with its source module (silhouette, extent, area) before the next. Branch
  `harness/from-source-modules`, three Codex rounds, old path regression unchanged, merge on command; at most
  three attempts per failing module, then report with numbers and a picture.
- 2026-10-13 retro review of #99 / #100: four P1 (#101-#104), one P2 (#105).
- 2026-10-13 **lamellas** of the east facade slot (0.05 x 0.20 x 3.28 m fins, 0.10 m pitch, 11 per storey): NPM as a
  **texture** on the slot back, no geometry (as at Butovskaya, user 2026-10-07).
- 2026-10-13 disputed geometry: look first, then classify (`WORKFLOW.md`); questions to the user only with a picture.

## Runs

- 2026-10-12 run 1: no body (largest part an inner mass, facade 8884 panels) -> rules 1-5.
- 2026-10-13 probe (`C:/x/t-obj03`, local): one stop, a 0.07 m2 opening in the roof at (57.70, 151.83).
- 2026-10-13 run 2 (spec v003 report): the same single stop. Scratch run past it: spec v004 - decor 0 (all 28 entries
  w_m < 0, #96), 8 storeys with self-crossing contours (#97), 9 terraces not built (#98), 754 corner openings not
  built, roof parapet not built (its cap narrows to a point). After #99 / #100 the build stops at 'cuts between
  faces and walls do not settle' (strips across a 107-197-vertex plan) -> engine PR: triangulated horizontal faces.
- 2026-10-13 decor triage `outputs/decor-triage.md` (local, with renders): the extractor reads the facade relief as
  not decor on a panelised source (the contour is the panel envelope); lamellas split into 222 columns + 104 shapes;
  ~430 window parts reach the decor set. Input for #96.

## Open issues from this job

#82 terrace parapets, #84 DP contour vs roof check, #85 open facade joined to an inner ring, #90 protrusion
root in the facade band, #91 enclosure shell for mid / VPM, #93 shaft under a marked enclosure.
#95 #84 fix P1, #96 decor widths / panelised decor, #97 self-crossing contour, #98 terraces not built.
