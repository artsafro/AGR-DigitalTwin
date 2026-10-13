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

## Runs

- 2026-10-12 run 1: no body (largest part an inner mass, facade 8884 panels) -> rules 1-5.
- 2026-10-13 probe (`C:/x/t-obj03`, local): one stop, a 0.07 m2 opening in the roof at (57.70, 151.83).

## Open issues from this job

#82 terrace parapets, #84 DP contour vs roof check, #85 open facade joined to an inner ring, #90 protrusion
root in the facade band, #91 enclosure shell for mid / VPM, #93 shaft under a marked enclosure.
