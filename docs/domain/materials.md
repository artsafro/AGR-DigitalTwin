# Materials

Keys: `reg p.N` = `Rasporyajenies19012026trebovaniya(2).pdf` page N. `local:` relative to the repo root (AGR knowledge base; AGR `docs/` lives in `docs/agr/`).

## Regulation - both profiles
- Shaders only: Standard (Legacy), Physical Material, Principled BSDF. Third-party renderers (VRay, Octane, Corona, Arnold, etc.) forbidden. reg p.8 §4.1, p.29-30 §4.1.
- Material properties/texture only in PBR paradigm, via extra maps or placeholders. reg p.8 §4.4.

## NPM
- Translucent-part material: no texture maps; color only via material params; opacity = 50% (constant). reg p.8 §4.2-4.3, p.2 term, p.13 fig.1.
- Opaque material count = texture set count. reg p.9 §4.5.
- Translucent materials <= 7, named `M_Glass_01..07` project-wide. reg p.9 §4.6, p.13 §3.5.
- Glass display mandatory when present; two methods, can be combined in one project: (1) opaque glass in atlas (not a separate object) using roughness+metallic maps; (2) translucent glass as separate object with special material. reg p.10 §7.
- NPM translucent glass needs simplified interior (walls/floor/ceiling) where visible through it. reg p.8 §3.12, p.13 fig.1a.

## VPM
- All texture paths removed from materials in FBX. reg p.30 §4.2.
- Max 7 materials per geometry object. reg p.30 §4.5.
- Main uses one material/slot until > 100 UDIM maps; then extra slots (<= 7) with sequential SlotNumber. Do not split Main by slots below 100 maps. reg p.30 §4.3-4.4.
- Do not group `*_MainGlass` with `*_Main` (or `*_GroundGlass` with `*_Ground`) under one parent (multi-sub) material. reg p.30 §4.4.
- Glazing: one object per model, special material, no texture maps; different physical/visual glass -> different materials, max 7; glass properties go to GeoJSON `Glasses`. reg p.32 §8.1-8.2, p.55.
- SlotNumber (1-7) is a label to pair material and texture set, unrelated to editor/engine slot numbering. reg p.21-22 term, p.35 §11.
- Emissive: glow via ERM red channel only; glow color from Diffuse. reg p.37 §14.

## Project rules / lessons
- Material registry: stable internal `MAT_xxx` with source (PDF sheet/fragment), status proposed/approved/conflict; keep NPM atlas region, VPM map/UDIM and DCC slot as separate fields; `MAT_xxx`/`WIN_xxx` are internal IDs, not delivery names. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#4 (project decision).
- Re-generation must never overwrite approved entries; conflicting proposal stored separately. local: docs/agr/decisions/ADR-0003-contracts.md (project decision).
- Material decisions trace to source sheet; pixel-measured size without scale reference is not a design dimension; color/brightness alone does not prove a material. local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#4; local: docs/agr/inventory/NPM_VPM_MAP.md (project decision).
- When album sheets conflict (facade legend vs spec sheet vs Revit names), user picks the source; record choice, keep old names untouched. local: docs/agr/decisions/OBR22_FACADE_PDF_UV_TRIAL.md (lesson).
- Colors sampled from PDF raster are color probes, not calibrated RAL; procedural textures are not manufacturer samples. local: docs/agr/decisions/OBR22_FACADE_PDF_UV_TRIAL.md; local: docs/agr/decisions/OBR22_PROCEDURAL_TEXTURES_V010.md (lesson).
- Roughness/metalness/glass derived heuristically from image brightness/white windows = proposals only until approved by a human. local: docs/agr/decisions/ADR-0004-reuse-installed-toolchains.md; local: docs/agr/inventory/INTEGRATION_PLAN.md#INT-003 (project decision).
- Ambiguous faces stay finish_id 0 (highlighted pink) until user decides; never assigned arbitrarily. local: docs/agr/decisions/OBR22_FACADE_PDF_UV_TRIAL.md (project decision).
- One shared set of seamless 2K maps for visualization across buildings (not per-building duplicates); per-building atlases keep their own tints. local: docs/agr/case_studies/FACADES_ATLAS_PARTIAL_ACCEPTANCE.md (project decision).
- Window frames in VPM: separate flat untextured material (no extra UDIM) was the working variant; glass separate by material. local: docs/agr/decisions/OBR22_SHARED_UV_V011.md (lesson, working variant only).
- Keep chain source material -> face/instance -> finish -> atlas region; generic names ("auto", "Material") and texture names don't prove finish; Revit structural-material parameter is not wall finish. local: jobs/GLB-NPM/AUDIT_AND_PLAN.md; local: jobs/OBR22-K02/STATE.md (lesson).
- Material IDs of the working model follow group ranges (`standards/material_id_ranges.yaml`: 1-5 facade, 6-10 reveals, 11-15 openings, 16-20 metal, 21-25 roof, 26-30 attachments, 31-35 interior); an unused range stays empty. They are a reading scheme only: UDIM tiles/slots are assigned on export by the regulation, glass always 1001. Boundaries are still a test. local: docs/adr/0001-material-ids-are-a-reading-scheme.md; local: docs/HARNESS_PLAN.md#6 (project decision).
- finish_id = Blender slot index + 1 = 3ds Max material ID; keep a material_ids.json to verify reorderings after import. local: jobs/MASHI-LP/MASTER_DIRECTIVE.md; local: jobs/GROUND-PROJECTION/RESULT.md (lesson).
- Glass: separate material, transparency from shader, never reuse frame color for glass; export glass as separate mesh in final FBX. local: jobs/REVIT-OPENINGS/outputs/diffuse-v001/README.md (project decision).
- Do not auto-transfer old model material slots to new surfaces without checking correspondence. local: jobs/MASHI-LP/AUDIT_AND_PLAN.md (lesson).
