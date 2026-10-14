# Primitive first (`primitive-first`)

Reduction, not reproduction (user 2026-10-14 [D074]; replaces the earlier wording). A delivery model is built from the
simplest parts that keep the building's silhouette, assembled like Lego.

## 0. The parts first

Before any build the agent lists the parts the body is assembled from and how they meet: walls, slabs,
parapets, bands, pilasters, frames, glazing, balconies, superstructure. That is the job's `modules/modules.json`
plus, per part, its primitive (`build_as`: `box`, `plane`, `frame`, `shell`, `profile-extrude`, `instance`) and its
joint with the neighbours (inset into which part, `decor_inset_m` 20 mm). The user confirms the list before the
build. A raw mesh source reaches the list through objects, material ids, a visual look and sections; a BIM source
(Revit) through categories and families - its geometry is never guessed.

## 1. One element = one primitive

The simplest form that holds the silhouette, not a box by default:
- a band round a storey is a frame: a plane on the storey contour, inset, the inner polygon deleted, shelled to
  its projection, the back face set into the body - one element per band;
- a two-step cornice is one extrusion of its two-step profile, no seams;
- a pilaster or a pier is a box or a profile extrusion, running through, never cut by bands;
- fluting, close panels, rustication, joints, chamfers and tile joints are never geometry: normal / bump.

## 1a. Decisions on OBJ03 (user 2026-10-14 [D075])

- Thin plates (2 cm sills and heads) are not geometry: the opening's own face takes their id - a sill under the
  opening colours the opening's bottom reveal face (sill id), a head plate its top reveal face (head id).
- The storey band frame runs round the whole storey contour; where the source has no band and the frame shows on
  the facade (in plan it changes the silhouette) it is cut on both sides and the piece deleted; behind a pier it
  may stay.
- Pier profile steps of 0.07-0.10 m are kept (profile, not a box).

## 2. Profile reduction

Profile steps under 0.07 m collapse. 0.07-0.10 m: when the element has its own material / id or reads as a band
of its own - a question to the user with a picture, never decided by the agent. Over 0.10 m: geometry.

## 3. Silhouette test

A part is built more complex than its primitive only if replacing it by the simplest form changes the silhouette
in any of five views (four facades and the top) by more than 0.07 m (user 2026-10-14 [D076]: 0.07, so the kept 0.07-0.10 m
steps stay profiles; was 0.10). The test is automatic, per element, reported.

## 4. Repeats

One typical element times its copies, as instances in the scene (Max / Blender), not copies: balusters, frames,
balconies, terraces of one form. The report lists the type catalogue: type -> count -> where.

## 5. Mesh density

No densification except where openings and joints cut in.

## 6. Two deliveries

- `modules/`: the model taken apart - logical groups by part, live instances, ids set, nothing attached; for the
  user's own work with instances and ids.
- `npm/`: final - attached by the rules, welded at 3 mm, inset, exported to FBX, checked. Made from the first
  automatically; the user may edit the first and regenerate the second.

In the harness (`from_source`, 2026-10-14): `modules/modules-scene.json` -> `tools/export/export_modules_blender.py`
-> `modules/modules.blend` (a collection per group, one mesh per type, objects sharing it); `npm/model.fbx` from the
same build. A type is its geometry (`twinqa.geometry.complexity.geometry_key`: vertex set to the mm from the bbox low
corner, triangle ids) and instances are placed by translation only - a turned copy is a type of its own.
Regenerating `npm/` from an edited `modules.blend` is not built yet (`docs/backlog.md`).

## 7. Checker `complexity` (blocking)

Triangles per module against the budget (150 000 per NPM FBX, split per module in the job); at most 12 vertices
per decor element (storey-contour frames: the contour's vertices); elements against types - copies not made
instances fail; profiled elements built more complex than their primitive without passing the silhouette test fail.

In the harness: `src/twinqa/geometry/complexity.py`, run on the modules scene by `tools/qa/run_from_source.py` when
the job's tolerances have a `complexity` block (`budget` per group, `total_max`, `decor_groups`,
`decor_section_points_max`, `silhouette_dev_min_m`). "12 vertices" is 12 points of the element's section (an
extrusion has twice that many vertices; user 2026-10-14 [D077]: about 12 points describe a silhouette). The budget per
group is the job's (OBJ03: rough, the total 150 000 is what holds, user 2026-10-14 [D077]).

## Nothing of the source is dropped (user 2026-10-14 [D078])

A source piece that cannot be reduced to a primitive (flat, turned off the axes, no section) is kept as the
source's own faces in a group of its own (`decor_as_source`), counted and listed in the job report; only
degenerate triangles (no area) are left out, counted. OBJ03: 1 442 pieces, 6 172 triangles, mostly hidden.

## Traps

- Collars and pilasters cut by bands (OBJ03 v007) are what this pattern forbids.
- A RailClone source is assembled from sheets: sections taken piece by piece are ragged; measure the part, then
  build its primitive.
