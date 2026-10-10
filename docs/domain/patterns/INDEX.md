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
| Inset roof plane | `roof-inset-plane` | the roof covering as a separate plane embedded into the parapet, +2-10 mm: no height; its joint = two open loops (hole A, plane B) | draft |
