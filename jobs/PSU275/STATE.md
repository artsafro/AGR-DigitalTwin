# PSU275 — main building No 1

Sources, decisions and derived values: `docs/sources/psu275.md`. Profile: NPM + VPM.

## Done (2026-10-07)

- S1 PDF, S2 Revit (detached 2025 copy `…_modified_1644`), S3 FBX, S4 PPTX inspected read-only.
- 0.000 = 169.65; first floor = 0.000 … +13.060; finishes from the S4 schedule.
- Chimney: take from S3 (user).
- `scripts/clip_floor1.py` → `outputs/psu275_floor1_src_v001.blend` (local): 254 meshes,
  3.54 M tris, band −0.150 … +13.060, context dropped.
- S3 ↔ Revit fit from facade planes (`scripts/facade_planes.py`), residual ≤ 0.02 m:
  `FBX = (Y_rvt + 142.55, 204.86 − X_rvt, Z)` (−90° rotation, no mirror).
  Outer faces: main 94.24 × 108.56 m, annex 18.66 × 56.58 m (L-shaped footprint).

- BODY (exterior surface, pre-Shell) v002: `scripts/build_floor1_grid.py` → `outputs/grid-v003`
  (54 openings ray-measured on the S3 opaque wall layer, edges snapped to S3 vertices,
  stacked curtain strips merged, edges consolidated within 12 mm, max move 2.3 mm) →
  `tools/run_exterior.py --config jobs/PSU275/exterior-adapter.json` → `outputs/exterior-v002`.
  2072 quads, 6 facade runs, height 13.060, min edge 40 mm. Checks pass: geometry QA,
  NPZ readback, Blender readback (max error 2.3e-6 m), `check_exterior_surface.py`
  (no inward faces, no opening fill, no overlap, profiles exact). Preview `preview_*.png`.
- Frame: local = Revit − (37.17, 54.00) m, Z = 0.000 (= 169.65). Earlier tries kept as
  evidence: grid-v001/v002, exterior-v001 (float32 readback 8.6e-6 m at S3 coords, 2 mm faces).

- Shell v001 (C23 decided by the user: Shell 0.4 m inward, no inner faces):
  `body-shell-adapter.json` → `outputs/shell-v001/BODY_SHELL.blend`, 3260 quads, min edge 40 mm.
  Checks pass: geometry, JSON readback, Blender readback (max error 1.9e-6 m). Visual review open.

- Approach changed (user, 2026-10-07): no typical floor in an industrial building → whole
  building as massing → one stitched surface with openings → one Shell. First-floor band
  results above stay as intermediate evidence.
- Full-height source: `outputs/psu275_full_src_v001.blend` (713 meshes, z −0.15…66.20).
  Masses: `masses.json` (8 boxes from `wall_planes_v001.json` + `heightmap_v001`).
- `massing-profiles-v002` (15 profiles, 23 040 m²) → `wall-masks-v001` → `massing-surface-v004`:
  130 openings, 2537 quads, 0 T-junctions, 20 corner lines (5 iterations), edges consolidated
  ≤ 12 mm (max move 2.3 mm), corner clearance 0.41 m (20 trims). Audit passes.
- Shell `body-shell-full-adapter.json` → `shell-full-v001` (3701 quads; 10 coplanar overlaps at
  junctions) → `drop_step_bottom_rims.py` → **`shell-full-v002/BODY_SHELL.blend`**: 3668 quads,
  33 step-bottom rims removed. Checks pass: geometry, JSON readback, Blender readback (3e-6 m).

- Roofs and parapet wells: `scripts/roof_wells.py` → `outputs/roof-wells-v001` (7 regions,
  211 quads: 127 roof, 61 parapet inner, 23 well faces closing the step-face gaps). Flat roofs
  at the roof level (hall 38.32, annex 13.56, boiler 62.20, inserts/superstructure at top);
  slopes not modelled. Audit alone passes; merged with BODY: 0 overlaps, 0 crossings.
- `scripts/assemble_body_roof.py` → **`outputs/building-v002/PSU275_BODY_ROOF.blend`**
  (BODY 3668 quads + ROOF 211 quads), Blender readback in `readback.json`.

- Portals: S3 faces outside the masses (`scripts/outside_clusters.py` → `outside_faces_v002.npz`),
  source check by `scripts/render_region.py`: portals are U/L frames around recessed doors or
  floating canopies (doors stay in BODY openings). `scripts/portal_frames.py` → `portals-v003`:
  15 portals (11 frames, 4 canopies; vestibule = 2 frames), front silhouette on the measured
  outer plane extruded to the facade (depth 1.60–1.68 m), coords consolidated ≤ 12 mm,
  185 quads, min edge 0.49 m. Audit alone passes; with BODY+ROOF: 0 overlaps, 0 crossings.
  (Trying portals as masses was dropped: it removed the recessed doors.)
- **`outputs/building-v003/PSU275_BODY_ROOF_PORTALS.blend`**: BODY 3668 + ROOF 211 + PORTALS 185 quads.

- Opening merge fix: chained merges had produced three ~31 m "openings" mostly over wall;
  merges now need ≥ 85 % void (`massing-surface-v006`: 152 openings, 2809 quads, 0 T) →
  `shell-full-v003` → `shell-full-v004` (4048 quads, 31 step rims dropped; all checks pass;
  re-audited with ROOF + PORTALS: 0 overlaps/crossings).
- Opening fills (user: both variants): `scripts/sample_openings.py` (first-hit class + depth,
  2.5 cm rays) → `opening-samples-v002` → `scripts/opening_fills.py` → `fills-v003`:
  116 windows, 35 doors/gates (2 sectional gates 5.0 × 5.8 classed "other" → door), 1 void.
  NPM: 152 planes at the frame depth, 10 mm reveal embed. VPM: frame/leaf minus 2446 panes,
  glass 2–4 cm deeper with pane sides, 23 144 quads, min edge 15 mm. Window-contract audit with
  BODY passes for both (embeds documented, 0 unapproved crossings, 0 T, 0 duplicates).
- **`building-v004-npm/PSU275_NPM.blend`** and **`building-v004-vpm/PSU275_VPM.blend`**: BODY +
  ROOF + PORTALS + WINDOWS_NPM / WINDOWS_VPM with preview materials (glass, frame RAL 9016,
  door RAL 7004, louvre, void).

- 2026-10-07 merged origin/main (KPP1 v005 accepted case, export-safety). VPM continues on the KPP1
  pipeline (experience-transfer): `vpm_textures.json` (9 UDIM: plinth tile300, sandwich RAL7047/5015
  with 1.19 m joints measured on S3, portal cassettes, 5 placeholders), `make_textures_psu275.py`
  (KPP1 generator) → `textures-v001`; `vpm_stage5.py` (Main + MainGlass, KPP1 seal/texel_cut/pack_uv/
  materials), `vpm_ucx.py` (23 boxes, 2 mm gaps, 0 intersections), `qa_master_psu275.py` (KPP1 QA copy,
  leak rays never start inside the masses: the shell is open inside by project rule).
- Finish zoning: `sample_finish_masks.py` → `massing_surface.py` bands (plinth 0–0.46, grey to 13.215,
  blue to 40.545, grey to 60.62, blue top; cuts across the whole facade); `connect_surface.py` 3.9 m.
- Wells moved into BODY (`massing_profiles.py --wells`, trimmed only at lower-parapet ends),
  `roof_wells.py --no-wells`, `fix_junction_caps.py --roofs` (drops roof-level step rims and well-band
  end rims, un-mitres overlapping parapet caps) replaces `drop_step_bottom_rims.py` (whose index-space
  bug and dropped rims left 0.4 m slots). Portals embed 11 mm and keep 6 mm from facade planes.
- Current: `vpm-stage5-v006/PSU275_VPM_stage6_ucx.blend`: Main 64 394 quads (128 788 tris) + Glass
  5 440 tris (< 150 000), max edge 3.54 m, UV overflow 0, density 1000 px/m. QA (KPP1 suite):
  overlaps 3, non-manifold 16, T 4, leaks 77 (32 at ground z=0), back faces seen from outside 40.
  Not clean yet: junction corners (bay/insert_1, hall/boiler east, annex portal) need work.

- **VPM + NPM v002** (`scripts/run_all.sh v002 …`, 3.5 min): inputs shell-vpm-v010 (surface v009 + 3.9 m
  connect, wells in BODY, junction caps fixed), roof-wells-v002 (no wells), portals-v009 (11 mm wall embed,
  6 mm clearances from facade planes / door jambs / ground), fills-v004, textures-v002 (address `Psu_1`,
  8 UDIM: Grille dropped — no louvre faces). Master `build-v002/PSU275_VPM_stage6_ucx.blend`:
  Main 64 984 quads = 129 968 tris, Glass 5 440 tris, 23 UCX; KPP1 QA: leaks 0, T 0, xView overlaps 0,
  non-manifold 0, doubles 0, oversize 0; 4 back-face probe hits (pane head faces / one superstructure
  face, ray artefacts of the open shell — known, not slits). Readback of the VPM FBX: 25 objects, tris equal.
- Packages: `package-vpm-v002/SM_Psu_1.zip` (FBX + 24 PNG), `package-npm-v002/0000_Psu_1.zip`
  (atlas 2048 `_d_` + `_o_`). SINTEZ AGR Checker (`sintez-v002`): VPM 64 passed / 3 failed, NPM 38 / 5 —
  same as accepted KPP1 v005; all failures deferred by the user (УКЭП, GeoJSON, Ground, district code,
  height/coordinates). Manual items: VPM 53, NPM 29.
- Fixed along the way: SINTEZ index (address must end with _1), MainGlass isolated vertices (15 566),
  empty UDIM.

- Extras (user 2026-10-07): chimney/ducts/transformer/tanks = separate OKS FBX (SM_Psu_2…); racks skipped
  (absent in S3); tanks rebuilt as full cylinders. Inventory: `scripts/inventory_extras.py` →
  `extras_inventory_v001.json`; S3 site renders `s3_site_*.png`. S3 has an odd underground element
  (RAL 1022/5015, z −52…−11) — excluded.
- External stairs rebuilt by parameters (KPP1 practice): `scripts/measure_stairs.py` (decking landings with
  vertex bounds, flights) → `stairs_v002.json`; `scripts/build_stairs.py` → `stairs-mesh-v007`: 5 switchback
  towers, platform +3.01 with flight, 3 ladders; 1 248 quads; joints: flights embed 11 mm into landings,
  12 mm split between halves, 6 mm clearances (walls, ground/roof lift), guards 10 mm out, no guards against
  walls; double alpha guard planes 8 mm apart (Railing_Alpha RAL 1021, explicit metre UVs), ladders split
  ≤ 3.5 m (Ladder_Alpha RAL 1021); steel Metal_RAL5015. Spec + 3 finishes (11 UDIM), textures-v003.
- **VPM + NPM v006** (`EXTRAS=stairs.json run_all.sh v006 …`): Main 66 282 quads = 132 564 tris + Glass
  5 440; QA: leaks 0, T 0, overlaps 0, non-manifold 0; back-face probe 236 (230 = alpha strip ends, as
  KPP1). SINTEZ VPM 64/3, NPM 38/5 (deferred items only).
- **Separate OKS v004** (`scripts/build_oks_extras.py` → `outputs/oks-extras-v004`; `run_oks.sh <key> v004`;
  specs `oks/<key>/vpm_textures.json`): chimney Psu_2 (R 6.70/6.00, 120 m, RAL 3020 bands from S3,
  platform +105.883 with railing ring, 2 944 tris), ducts Psu_3 (Ø4 tubes on measured centrelines, cone
  Ø8→Ø4 from the main north wall, U duct into the chimney with the two S3 halves joined, 2 duct buildings,
  4 supports; 2 360 tris, 35 UCX), transformer Psu_4 (S3 voxelised 0.25 m, well-composed, 43 628 tris,
  114 UCX boxes), tanks Psu_5 (3 cylinders to the ground, railing rings; 1 728 tris). Each: T 0, leaks 0,
  overlaps 0, non-manifold 0, doubles 0; open edges only on alpha railing strips. Colours other than the
  chimney are proposals. VPM: own package and pivot each, no MainGlass (`export_vpm_psu275.py`).
- **Combined delivery v002** (`run_npm_combined.sh v002 …`): NPM `0000_Psu_1.zip` = main `_01` + OKS
  `_02.._05` (objects `SM_Psu_1_<NNN>_Main`, shared frame of the main pivot, object origin at each OKS
  centre — SINTEZ «точка отсчёта»), VPM `SM_Psu_1..5.zip`. SINTEZ: «2-21 FBX» now passes; failures are the
  deferred items only (УКЭП, GeoJSON ×2, Ground, district code, height mark).
- **Checkpoint 2026-10-07 (user review in 3ds Max 2026, HP = VPM / LP = NPM quad copies, `outputs/delivery-v002/max_review/import_hp_lp.ms`):** accepted as a checkpoint — main volume and mesh OK. Next: remove loops/rings that support no opening or corner (thin strips), keeping texel limits; reference logic `Desktop/zavod/scripts/mesh/clean_opening_grid.ms` (keep borders, creases, U/V lines of island corners; RemoveLoop the rest).
- **Mesh clean-up v009** (`PSU275_ROOF_EMBED=1 PSU275_CLEAN_LOOPS=1 EXTRAS=… run_all.sh v009 …`): cause of the dense
  grid was seal's T-junction cascade across the welded roof-parapet seam (29k -> 60k faces, cuts from one facade
  ran across the roof to the opposite facade). Fix 1 (stage5): roof membrane as its own piece, border pushed 11 mm
  under parapets (ends of welded edges never move), parapet bottoms lowered 11 mm under it. Fix 2
  (`scripts/clean_loops.py`, port of zavod `clean_opening_grid.ms`): per plane keep borders, creases, finish
  changes, uvx and non-rectangular quads and U/V lines of island corners; dissolve all-junk edge loops before
  texel_cut. Main 66 282 -> 36 556 quads (-45 %; membrane 20 227 -> ~2 700 faces); QA T 0, leaks 0, overlaps 0,
  doubles 0, UV overflow 0; SINTEZ VPM 64/3 (deferred only). v007/v008 = failed intermediates (overlaps / UV
  overflow on skewed caps). Combined `delivery-v003` (main v009 + OKS v004), quad review copies in
  `delivery-v003/max_review`. Remaining density: opening-corner lines across whole facades (needed for T-free
  quads) and window frames (Frame_RAL9016 ~20k faces).
- **Accepted 2026-10-07** (user, Blender review of the quad masters): mesh clean-up v009 = success; delivery-v003 fixed as the result of this stage. Report `REPORT.md`, case `docs/agr/case_studies/PSU275_VPM_NPM_DELIVERY_V003.md`.

## Open

- Visual/user review of `shell-full-v002` against S4 facades; louvres counted as openings.
- Roof slopes (hall 38.32…39.35), skylight lantern details, roof equipment not modelled.
- Transformer is a voxel massing (0.25 m); parametric parts (tank, bushings, conservator) if needed.
- Racks (эстакады) absent in S3 — skipped until a source exists.
- Opening IDs are S3 measurement IDs, not Revit IDs. Minimum rim edge 10 mm.
- Generalization of the massing builder → backlog P12 (Codex).

## Next

Optional: window-frame simplification, parametric transformer, 3ds Max xView check (like KPP1); GeoJSON/MSK-77/Ground when the user un-defers them; racks when a source appears; generalisation candidates to Codex (P12, clean_loops + unwelded roof).
