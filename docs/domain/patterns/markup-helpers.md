# Markup helpers (`markup-helpers`)

Status: draft (MH1: the Blender route proven on `bench-b01-box`; MH2: the Revit route proven on KPP1). Source: user decisions 2026-10-10
(HARNESS_PLAN §14, backlog MH1-MH3); pattern `roof-inset-plane` (technological elements set no level).

## Signs in the source

- Every level elevation of the spec comes from a helper object `LEVEL_<name>` at that height (its world Z):
  `LEVEL_L0`, `LEVEL_L1`, ..., `LEVEL_roof` (the top of the roof covering, not the parapet top). Levels are
  never computed from geometry; inset plates, gaps and other technological elements set no level.
- Name rule (`src/dt_ai/spec/mesh.py`, `LEVEL_NAME`, `LEVEL_COUNTER`): `^LEVEL_[A-Za-z][A-Za-z0-9_]*$`, no
  trailing 3-digit counter (`LEVEL_roof001`, 3ds Max), no copy suffix (`LEVEL_L1.001`, Blender), no spaces;
  each name once, no two helpers at one height (1 mm). A broken name is an extractor error, never a guess.
- Later layers (MH3): axes `AXIS_<letter>` / `AXIS_<digit>`, anchors `TERRACE_<n>`, `ENTRANCE_<name>`.

## How to make them, per source

- 3ds Max (reference path, B01 / B02 / B02t): Point helpers; FBX export Z up, metres, scale 1.
- Blender (MH1, `bench-b01-box` Blender etalon, 2026-10-10): Empties; the FBX keeps them as Null nodes with
  their names. Scene Unit System metric, **Unit Scale 1.0** (decisive: at 0.01 the model reads 100x
  smaller); export **Up Z, Forward Y**, Scale 1.0, Apply Unit Scale on, Apply Scalings **FBX Units Scale**
  (for other importers; the Blender readback was the same with All / None / FBX Units at Unit Scale 1.0).
  Y up (Blender's default) also reads right — the importer applies the file's `UpAxis` — but the axis
  turn leaves ~1-2 µm float noise (a plate gap read 0.004999); Z up reads exactly.
- Revit (MH2, `src/dt_ai/spec/markup.py`): generated, not placed by hand. `measure_spec_revit_twin.mjs` writes
  the document's Levels and Roofs into twin-data.json; object.json `revit_levels` maps each Revit level to a
  spec name or `null` (not a floor: structural, parapet, basement band) and names the roof type whose
  covering top is `LEVEL_roof` = base level + offset + volume / area (user decisions 2026-10-10). A level
  the table does not name is a `revit-level` question. object.json `levels` (kept for sources without
  helpers) must agree with the generated helpers within 3 cm. Inset plates are not read from Revit (the
  design has no inset; the inset is the model's joint). Grids -> `AXIS_<name>`: MH3.

## Profiles

- Same in `npm_min` and `mid`.

## Check

- The extractor reads the helpers (`_levels`) and stops on a broken name, a name given twice or two
  helpers at one height; a source whose contour vanishes as relief (all <= 0.10 m: a model in the wrong
  units) stops with a units hint.
- `bench-b01-box` Blender etalon (`data/benchmark/bench-b01-box/blender-v001/`, made by Claude in Blender by
  hand from the B01 brief, user decision 2026-10-10): its spec equals the Max etalon's; the chain passes
  8/8 against itself and for the engine model (Up Z and Y up exports).
- KPP1, Revit route (MH2, 2026-10-11): helpers L0 0.000, L1 3.900, roof 7.9093 (roof 1613791: 7.7 + 60.36 /
  288.44); spec revit-twin v014 against the VPM FBX spec v030: levels 0 / 0 / 0.3 mm, verdict match.

## Traps

- Duplicating a helper in Blender makes `LEVEL_<name>.001`: rename, never leave both.
- A level helper in a parent's local space still reads by its world Z; keep helpers unparented.
- Units: a centimetre scene exports a 100x smaller model; the extractor stops on it (all relief).
