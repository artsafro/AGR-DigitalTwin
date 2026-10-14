# Pattern: roof-screen-enclosure (draft)

Status: draft (user decision 2026-10-13, OBJ03). Spec v0.7 `roof_structures`.

## Signs in the source

- On the roof: screens (louvres, mesh fences) round roof equipment, standing above the roof level; the
  equipment blocks stand inside them. OBJ03: `RailClone2142` up to 102.56 m over the roof at 96.55 m.
- The marking is the human's: `object.json` → `roof_screens: [mesh names]`, as with `slabs`. The extractor does
  not guess which meshes are screens.

## The rule (user, 2026-10-13)

1. The enclosure is part of the body's silhouette (an exit to the roof), not an attachment.
2. `npm_min`: planes on the screens' outer outline, from the roof level up to their top, facing out, and a top
   plane at the top - a box with no bottom and no thickness. The equipment blocks inside are not modelled.
   A build by source modules follows the source: screens with no top get no top plane (OBJ03, user 2026-10-14);
   the checker allows the open ring on the outline at the top then.
   Ids: the roof group (21-25).
3. `mid` / VPM: the same planes as a shell (the screen's thickness); the blocks inside are decided later
   (issue #91; until then the engine raises a `BuildError`).
4. What lies under the outline - the equipment, the screens, their steep parts - is no roof question: the roof
   check keeps only the flat roof at the level there, and the enclosure closes the roof from above.

## Spec

`roof_structures: [{kind: "screen", outline: [[x, y], …], z_top_m}]` (spec v0.7). The extractor reads the
outline as the outer line of the screens' plan (their faces projected, joints up to 0.10 m closed,
Douglas–Peucker 0.10 m) and the top as their highest point. A name not in the source, a screen not above the
roof or a plan that does not close is a stop. A group of screens must enclose exactly one space (a hole of
its plan not capped by the screens above and below - a thick screen's own inside is capped twice): none is an
open screen, two or more (enclosures sharing screens) is a stop too - their tops cannot be told apart.

## Check

- The enclosure's wall bottom is a flat closed open loop at the roof level on the spec's outline: allowed
  (`roof-structure`), it takes no part in the slab joints of `roof-inset-plane`.

## Traps

- An unmarked enclosure is read as roof structure: steep equipment tops stop the roof ("a pitched roof").
