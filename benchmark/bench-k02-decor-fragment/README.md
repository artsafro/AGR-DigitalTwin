# bench-k02-decor-fragment

The decor benchmark (pattern `facade-decor-inset`; user decision 2026-10-11): a **fragment** of the facade of
a real building — one bay, two storeys — not a building. No building context is needed or checked; the only
goal is the decor pattern. It replaces the synthetic B03 as the first decor benchmark (B03 stays a later
regression, `docs/backlog.md` EG1).

Two files, both made by the user in 3ds Max:

| File | What it is | Read by |
|---|---|---|
| `source.max` | the fragment cut from the source FBX as delivered: decor as separate meshes (pilaster pieces per storey, belt in its stepped pieces), `LEVEL_*` helpers added | the extractor (`dt spec extract`) |
| `etalon.max` | the same fragment modelled for NPM by the rules: one box per decor element, relief of 0.10 m or less as texture | the checkers |

Chain: `source` -> extractor -> `spec.json` (its `decor` block, PR 2) -> engine (PR 3) -> model -> checks
against `etalon`; the etalon is also checked against itself.

## Source and where to cut (brief for the user)

Source: the FBX of the colleague job recorded in `docs/cases.md` (2026-10-11). The numbers below come from
that job's derived `decor.json` / `openings.json` (catalogue: `decor-catalog.json`), not from the FBX:
**check them in the FBX before cutting** and report any difference.

- **Wall**: the wall at x = 56.719 from y 176.261 to 152.46 (facade faces -X, the building is at +X), in
  the storeys below z 56.2. Wall coordinate u = 176.261 - y.
- **Fragment**: u 13.0 ... 17.6, i.e. **y 158.661 ... 163.261** (4.6 m), and **z 12.52 ... 19.69** (7.17 m;
  corrected 2026-10-12 after review 2 of PR #73 — the first brief's z 13.1 ... 20.3 cut through a spandrel at the
  bottom and an upper window at the top). Bottom: the lower spandrel's bottom edge; top: just under the upper
  window (19.699), so no opening is cut. Cut lines run along element edges, never through a decor element's
  width: the left edge is the left lesene's edge, the right edge the pilaster's right edge. The lesenes and the
  upper pilaster piece run on past the top / bottom and are cut there (height only).
- **Inside the fragment** (every `decor.json` / `openings.json` record of that wall overlapping it; u / z on
  the wall, projection from the wall):
  - belt: horizontal band over the whole wall, z 15.80-16.26, projection 0.30, two stacked pieces
    (15.80-16.05 and 16.05-16.26; the upper one is set back only at the wall ends, outside the fragment) — cut
    by the fragment's side lines;
  - below the belt: lesenes (0.30) u 13.00-13.35 and 13.85-14.20 with a strip 13.35-13.85 (0.18) between
    them, all from z 0.02 / 0.04 up to 15.76-15.80; lesene u 16.4-17.6 (0.30) up to 15.80;
  - above the belt: lesenes (0.30) u 13.0-14.2 and 16.4-17.0 from z 16.30 up (cut at the top); pilaster u
    17.0-17.6, projection 0.18, **split** into pieces with a 0.02 m joint: z 16.34-19.06 and 19.08-20.28 (the
    second cut at the top) — the pieces the extractor must merge into one element;
  - window bay u 14.2-16.4: spandrel (0.18) z 12.52-13.68, window z 13.70-15.80, belt, spandrel (0.18) z
    16.32-16.98, window z 17.00-19.10, plain wall 19.10-19.69;
  - glass inserts 0.59 x 0.55, projection 0.02 (<= 0.10: texture), u 14.23-14.82, z 13.75-14.30 and
    17.05-17.60 — they lie inside the window rectangles: check in the FBX whether they are part of the window
    (then they belong to the opening, not the decor).
  - the left neighbour's windows (z 13.10-15.80 and 17.00-19.10) end at u 13.001, 1 mm past the cut line u 13.0:
    rounding in the job data; check in the FBX that they end at the lesene's edge, and keep them out of the fragment.
- **Body**: close the fragment as a box behind the facade, 3.0 m deep (x 56.719 ... 59.719): the facade face
  as in the source with its window openings; sides, back, top and bottom are flat cut faces of the facade
  material. No interior, no slabs.
- **Coordinates**: move the fragment so that the facade's bottom-left corner seen from outside is the origin:
  subtract (56.719, 158.661, 12.52), no rotation (the facade then lies in x = 0 facing -X, y 0 ... 4.6, z
  0 ... 7.17). Metres, Z up. Write the offset you used into this README.
- **Helpers** (`LEVEL_<name>`, Point helpers, name rule of `markup-helpers`): `LEVEL_cut_bottom` at z 0,
  `LEVEL_F1` and `LEVEL_F2` at the finished floor levels of the two storeys as the source shows them (the
  slabs are outside the cut, take them from the source; if a floor is below the cut, put the helper at the cut
  bottom and say so), `LEVEL_cut_top` at z 7.17.
- Keep the source's decor exactly as delivered (separate meshes, their materials and joints); only cut and
  move. Openings stay as in the source (their reveal depth is read, default 0.4 when the source has none).

## Etalon (by the rules, by the user)

- Belt: one box over the fragment width (both stacked parts project 0.30 here, so they are one element), embedded 0.02 m (back face deleted), body
  not cut; a face that would coincide with a window face is moved 5 mm (`plate_gap_m`).
- Pilaster above the belt: one box 0.6 x 0.18 over its whole height, joints as texture.
- Lesenes: one box each, 0.30, embedded 0.02 m.
- Spandrel panels: one box each, 0.18.
- Glass inserts: no geometry (0.02 m): texture.
- IDs: decor in the attachment group 26-30, one id per decor kind (belt, lesene, pilaster, spandrel; the table
  goes into `object.json` with the etalon). Body and openings as B01 (facade 1, reveal 6, opening 11).
- This bay has no free-standing column: the column rule (own ID and UV island) stays tested by the synthetic
  B03 later.

## Delivery

`data/benchmark/bench-k02-decor-fragment/source.max` and `etalon.max` (3ds Max 2024); the agent exports both
FBX and records their SHA256 in `etalon.json`. The repo keeps spec, hashes and the catalogue only.

## Checks (after PRs 2-4)

Extractor on the source: belt, lesenes, pilaster and spandrels as geometry entries, the pilaster pieces as one
element, the glass inserts as texture, anything the rules do not cover as a question (no question for a number at a threshold). Engine model against the etalon: the
8 checks of §5 plus the decor checks — no decor face within 5 mm of an opening face, no body edge cut by decor,
decor ids in 26-30, nothing of 0.10 m or less built as geometry.
