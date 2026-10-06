# 3ds Max scripts for NPM/VPM production

External MAXScript tools in `C:\Users\artsafro\Desktop\!3D viz\Плагины 3dMax\Andrew_scripts\`
and `...\Плагины 3dMax\A101AGRLP.ms`. Read-only inventory of 2026-10-06 (code read, nothing
run): written for 3ds Max 2024 (MAXScript + dotNet), no author header. The user treats them
as working tools that may be reused. **None is regulation-compliant as is** — run them on an
export copy of the scene and check the result with `tools/qa/validate_package.py`.

## Which tool for which delivery part

| Part | Tools | Use | Watch out (rule) |
|---|---|---|---|
| Flora (NPM) | `FloraAtlas.ms` V1.2 | wrap: then fix output | Diffuse saved RGBA (NPM forbids alpha, reg p.9 §5.5); padding 2 px (NPM ≥ 8, p.9 §5.4); up to 8192 (Flora ≤ 2048, p.10 §5.13); names `flora_atlas.png` not `T_…`; converts sources to Editable Mesh; leaves hidden `*_BACKUP` objects |
| Ground relief | `NUM2CIRCLE.lsp` → `Ground_Tools.ms` (Terrain 1:1, DP simplify) → `Region_Cut.ms` | as is, on copies | NUM2CIRCLE takes **all** numeric texts of the DWG and deletes them — run on a DWG copy; Ground_Tools converts the selection to Poly; Region_Cut works on the flat grid before deformation |
| Ground placeholders | `Texture_Zaglushki_Ground.ms` v9 | re-implement per profile | always 256 + ERM; NPM needs 128 and r/m maps (reg p.3-4; conflicts #5); `_1` suffix on name clash breaks the name mask |
| MAF / GroundEl | `Maf Tools.mcr` v3.0 (Glue, Maf Check, TD, RTT bake) | wrap | sets UDIM = 1000 + MatID — against "MatID ≠ UDIM" (npm-vpm.md Terms, conflicts #33); split deletes the source by default; RTT padding 4 px |
| UCX (VPM) | `UCX_Tools.ms` v3.35 (slice, convex parts, 2 mm gap, hull) | build; rename and validate after | names `UCX_NNN` in layer `UCX_Box` (need `UCX_SM_{Address}_Main_NNN`, reg p.34); no triangle budget (reg p.36-37; conflicts #3); hull needs MassFX `nvpx` |
| UCX check | `UCX_Check.ms` Turbo v2 | do not rely on | misses nested volumes, does not measure the gap (reg p.36 §13.4) — use our checks |
| VPM lights | `FreeSpot_Tools.ms` v2.3 | wrap | no `Address_Root` / `Address_Spot_NNN` names, no 5 m omni spacing check (reg p.34-35, p.38); "analyse" deletes all FreeSpots of the scene |
| UDIM preview / reimport | `UDIM Viewer_V1.4.ms` = `Udim_Geo_Json.ms` (same code) | preview only | skips ERM, clamps negative UV, accepts 1001-1999 (norm 1001-1100 sequential); does **not** write GeoJSON |
| NPM naming + export | `A101AGRLP.ms` | port naming/checks, fix bugs | drops the leading zero of the 4-digit code (0313→313, reg p.11); Ground export button calls a missing function; glass without 50 % opacity (p.8); FBX 2014 only in commented code (p.4); renames/resets **working** objects |
| Modelling helpers | `Poly Actions Copy_V6.ms`, `Zamena_V2.ms`, `Interier_Box.ms` | as is, on copies | leftover `___PAC_BACKUP___`; `.pac` import executes file lines; Zamena makes copies, not instances |

## Gaps (no tool yet)

- GeoJSON writer — none of the scripts writes it; to be written against `standards/VPM_STANDARD.yaml` `geojson`.
- UCX checks (nesting, gap, triangle budget, names) — to be written; `UCX_Check.ms` is not enough.
- Profile-aware placeholders and Flora atlas post-processing (RGB, ≥ 8 px, ≤ 2048, `T_`/`M_` names).
- Leftover service objects/layers (`*_BACKUP`, `UCX_Box`, `FreeSpot`, `Interior_box`) must be absent
  from delivered FBX (reg p.6 §1.3, p.28) — check with `validate_package.py --scene` (V003 object types).
