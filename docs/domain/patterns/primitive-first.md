# Primitive first (`primitive-first`)

Reduction, not reproduction (user 2026-10-14; replaces the earlier wording). A delivery model is built from the
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

## 2. Profile reduction

Profile steps under 0.07 m collapse. 0.07-0.10 m: when the element has its own material / id or reads as a band
of its own - a question to the user with a picture, never decided by the agent. Over 0.10 m: geometry.

## 3. Silhouette test

A part is built more complex than its primitive only if replacing it by the simplest form changes the silhouette
in any of five views (four facades and the top) by more than 0.10 m. The test is automatic, per element, reported.

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

## 7. Checker `complexity` (blocking)

Triangles per module against the budget (150 000 per NPM FBX, split per module in the job); at most 12 vertices
per decor element (storey-contour frames: the contour's vertices); elements against types - copies not made
instances fail; profiled elements built more complex than their primitive without passing the silhouette test fail.

## Traps

- Collars and pilasters cut by bands (OBJ03 v007) are what this pattern forbids.
- A RailClone source is assembled from sheets: sections taken piece by piece are ragged; measure the part, then
  build its primitive.
