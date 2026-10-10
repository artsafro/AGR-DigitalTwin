# bench-b02t-terrace

B02 (`bench-b02-corner-niche`) plus a terrace parapet on the L1 ledge: 0.6 m high from `LEVEL_L1`,
0.3 m thick, along the ledge's outer edges (the L0 contour over X 0-6, niche included); its ends meet
the upper block's wall X = 6, which is removed between 3.3 and 3.9 m. Nothing else changed from B02.

Patterns: terrace (plus the B02 patterns).

Etalon: hand-made in 3ds Max by the user (2026-10-10); never produced by the engine — the engine is
checked only against a hand-made etalon (HARNESS_PLAN §5). Every horizontal slab is inset (user rule
2026-10-10): the roof as in B02, and since etalon v2 the walkable terrace too — a hole in the body at
`LEVEL_L1` 3.300 and a separate plate at 3.305.

Brief (Claude Docs): https://claude.ai/code/artifact/95f7af8a-f484-4d9e-80ce-2a0f50ece086. Etalon files
outside git in `data/benchmark/bench-b02t-terrace/`, hashes in `etalon.json`; `spec.json` extracted
from it: the B02 spec plus `terraces: [{"level": "L1", "parapet_h_m": 0.6}]`, spec v0.4.

Status 2026-10-10 (etalon v2, run-inset-v001): spec unchanged, 0 questions (the walkable part read
from the inset plate 5 mm above the level); etalon against itself 8/8 and the engine model's FBX
readback 8/8, both with two loops per slab (roof 6.600 / 6.605, terrace 3.300 / 3.305, embed 20 mm).
Etalon v1 (welded terrace), run-v002: spec as the brief, 0 questions (L1 contour rule "terrace: parapet
0.600 m from the level"; walkable 45.42 + cap 6.48 = ledge 51.9 m2); etalon against itself 8/8; the
engine builds B02t and its FBX readback passes 8/8 against the etalon.

Run and checks: as `benchmark/bench-b01-box/README.md`, with this folder's `object.json` and
`tolerances.json`.
