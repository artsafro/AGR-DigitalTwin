# Pattern registry

A pattern is a portable rule for one building node, not a project story: a building name in a
pattern is a review error. File format `<slug>.md`, 20-40 lines: signs in the spec; how to build
it with engine functions; differences per profile (`npm_min` / `mid`); which checker confirms
it; traps, one line each. Source: `docs/HARNESS_PLAN.md` §7.

Status: draft / proven on benchmark / in work. A pattern changes only with the user's approval.

| Name | Slug | What it does | Status |
|---|---|---|---|
| Walls from a level contour | `wall-from-contour` | builds the exterior walls of one level from its contour points | draft |
| Opening plane with window ID | `opening-plane` | recessed plane in the opening with the type ID; base for the atlas and detailed windows | draft |
| Typical floor — build once, repeat | `typical-floor-repeat` | builds a floor once and copies it by `repeat_to` | draft |
| Corner that is not 90° | `non-90-corner` | joins two walls at any angle without breaking the mesh | draft |
| Niche in the contour | `contour-niche` | facade recess given by contour points | draft |
| Parapet | `parapet` | roof edge along the contour of the top level | draft |
| Vent grille | `vent-grille` | inset grille: an opening of kind `grille`; texture in `npm_min`, geometry in `mid` | draft |
| Inset slab | `roof-inset-plane` | every slab (roof in a parapet, terrace walkable) is a separate plate embedded into the faces around its hole, +2-10 mm: no height; its joint = two open loops (hole A, plate B), required (user 2026-10-10) | proven on benchmark (B01, B02, B02t) |
| Roof screen enclosure | `roof-screen-enclosure` | screens round roof equipment (marked `roof_screens`): npm_min planes on their outer outline up to their top, no bottom, roof ids; mid shell later (#91); spec v0.7 `roof_structures` (user 2026-10-13) | draft (OBJ03) |
| Floor step | `floor-step` | a contour per floor; at the step a ledge (up, roof ID) or a soffit (down, facade ID) | draft |
| Terrace | `terrace` | a floor-step ledge with a parapet from the spec (`terraces`, v0.4): outer face, inner face, cap, walkable part | proven on benchmark (`bench-b02t-terrace`, user 2026-10-10) |
| Markup helpers | `markup-helpers` | levels from `LEVEL_<name>` helpers only (name rule, no copy suffixes, once each); per-source routes: Max Point, Blender Empty (MH1), Revit Levels (MH2) | draft |
| Primitive first | `primitive-first` | reduction, not reproduction: parts listed and confirmed first (build_as box / plane / frame / shell / profile-extrude / instance, joints), one primitive per element, profile steps < 7 cm collapse, silhouette test 0.10 m, instances for repeats, two deliveries (modules / npm), blocking `complexity` check (user 2026-10-14) | draft |
| Facade decor inset | `facade-decor-inset` | one simple solid per decor element, embedded 0.02 m with the inner face deleted, body not cut, 5 mm off openings, ids 26-30; 0.10 m or less is texture (user 2026-10-11); by source modules: real sections, one mesh per run, piers run through and are never cut, storey bands as frames on the contour cut where they show without a source band, other bands stop 0.02 m inside piers, inset dark panels (user 2026-10-14, pattern `primitive-first`) | draft |
