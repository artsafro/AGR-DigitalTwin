# Terrace (`terrace`)

Status: draft. Source: user decisions 2026-10-10 (a terrace = a floor-step ledge with a parapet
from the spec; thickness = the build input `parapet_thickness_m`; PR A engine, PR B extractor +
etalon B02t); patterns `floor-step`, `parapet`, `roof-inset-plane`.

## Signs in the spec

- `terraces: [{"level": "L1", "parapet_h_m": 0.6}]` (spec v0.4): at that level a ledge of the
  floor below (pattern `floor-step`) carries a parapet `parapet_h_m` high, measured from the level.
- The parapet runs along the ledge's outer edges only, not along the walls of the floor above.

## How to build (`src/dt_ai/geometry/from_spec.py`, `_terrace`)

- Outer face: the walls below go on up along the outer edges to level + `parapet_h_m` (facade ID).
- Inner face: the band `parapet_thickness_m` inside the outer edges (mitred, flat at the walls of the
  floor above), from the level to its top (roof ID), facing the walkable part.
- Cap: the band at the top (roof ID); walkable terrace: the ledge minus the band (roof ID).
- The floor-above wall cells behind the parapet's ends are hidden and not built.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- `floor_areas`, `silhouettes`, `mesh` (quads, no open loop but the bottom ring; a terrace may also
  carry an inset covering, pattern `roof-inset-plane`); walkable + cap = the ledge area.

## Traps

- No step under the level, a ledge with no outer edge, or a parapet leaving no walkable part: BuildError.
- A terrace parapet the spec does not give stays a question (`questions.md`), never a guess.
- The extractor does not read terrace parapets yet (PR B): until then they come out as questions.
