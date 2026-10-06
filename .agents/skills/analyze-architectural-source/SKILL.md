---
name: analyze-architectural-source
description: Inspect an incoming architectural source (FBX, Revit, SketchUp, Blender, 3ds Max, Unreal input) and record what it contains before any processing. Use when a new or updated source file arrives, or before building production assets from one.
---

# Analyze architectural source

Read-only inspection. Leave the source file unchanged; write findings to the report only.
Domain rules live in `docs/domain/` (each rule cites its source); open the file named
in a step when that step needs the rule, not before.

## Decision first: target profile

Ask or record which deliverable this source feeds: **NPM**, **VPM**, **both**, or
**Unreal-only**. The profile decides which budgets, coordinate rules and naming apply
(`docs/domain/npm-vpm.md`). If unknown, record it as a user question and analyse
against both NPM and VPM.

## Steps

1. **Identify.** Record path, format, file size, modification date, SHA-256 and
   authoring tool/version if discoverable. Done when the source has a row in the
   `Sources` table of `docs/PROJECT_STATE.md`.

2. **Scale and placement.** Determine units, up axis, origin, and one real-world
   reference dimension (storey height, door, grid spacing). Record where the source
   sits relative to the profile's placement rule: NPM in MSK-77 at project heights;
   VPM local origin with pivot at the geometric centre X/Y and Z at project zero
   (`docs/domain/geometry.md`). Done when the reference dimension is measured and
   compared with its expected value, and CRS / zero mark are either confirmed from a
   document or listed as user questions. Never assume a CRS or zero mark.

3. **Structure and composition.** List the object/layer/collection hierarchy,
   object count and instancing. Classify every top-level group as OKS (Body,
   windows, roof, usable roof), Ground, GroundEl, Flora, glass, or out of scope
   (interiors, existing non-reconstructed buildings, context). Use `GLOSSARY.md`
   terms. Done when every top-level group has a class and a count; anything
   unclassifiable is a user question.

4. **Geometry health.** Triangle count per future FBX against the profile budget,
   non-manifold edges, duplicated or overlapping faces, flipped normals, unapplied
   transforms, pivots. Separate deliberate embeds from defects before reporting a
   finding (`docs/domain/validation.md`, QA procedure). Done when each check has a
   number or `not checked: <reason>`.

5. **Materials and UVs.** Every material slot is classified (opaque, glass,
   emissive, vegetation/opacity, unknown); texture references found/missing; UV
   channels per object (`docs/domain/materials.md`, `docs/domain/uv-textures.md`).
   Done when no slot is unclassified without being listed as a question.

6. **Report.** Write `docs/sources/<source-name>.md`: findings above, production
   risks, user questions, and every entry of `docs/domain/conflicts.md` that this
   source touches (by number). Update `docs/PROJECT_STATE.md`.

## Completion

Every step has a recorded result. Unknowns are written as unknowns with the reason,
never filled by assumption. Synthetic or estimated values are labelled.
