---
name: validate-delivery
description: Final check of a deliverable (NPM/VPM package, exported model, Unreal level, packaged build) against project priorities and delivery rules before it is reported done or handed over. Use before declaring a delivery complete or sending it to a client.
---

# Validate delivery

Validate the **delivered files**, not the working scene: re-read the exported result
(from the ZIP when there is one) in a clean scene/process and check that.
Run the machine checks: `py -3 tools/qa/validate_package.py <zip|fbx|geojson> --json`
(stages V001-V017; exit 0 passed, 1 fail, 2 review/not_run left). Stages it reports
`not_run` need the FBX scene (tools/blender readback) or manual review — never count them as pass.

## Decision first: which rule set

- **NPM / VPM package** → run the V001–V017 checks in `docs/domain/validation.md`;
  each check cites its regulation page.
- **Unreal / internal deliverable** → run the five priority checks below only.

## Checks

Run in priority order from `CLAUDE.md`. Each check ends as `pass`, `fail`,
`review: <conflict # or reason>` or `not checked: <reason>`.

1. **Architectural accuracy.** Key dimensions and element counts (floors, openings,
   facade modules) match the source report in `docs/sources/`.
2. **Scale and transforms.** Units (1 unit = 1 m), up axis, origin and pivots per
   profile, rotations reset (`docs/domain/geometry.md`).
3. **Materials.** Every material slot assigned and named per profile, no missing
   textures, maps/format/size/padding per profile (`docs/domain/materials.md`,
   `docs/domain/uv-textures.md`).
4. **Performance.** Triangle count per FBX against the profile budget; material and
   texture-set counts; texture resolutions.
5. **Visual fidelity.** Screenshots from fixed cameras (front and angled), compared
   with the approved reference or previous accepted version.

## Decision points

- A check touching an entry in `docs/domain/conflicts.md` ends as `review` with that
  entry number; do not pick a side.
- Output of an external checker (SINTEZ AGR Checker, CheckToolBox, ucx_check) is
  evidence, not the verdict: map each finding to a check and a regulation page. A
  partial run (one function, isolated component) is not a checker pass.
- Manual checks (V015–V017, visual fidelity) need the user's sign-off; record who and
  when.

## Report

Write `docs/deliveries/<deliverable>-<YYYY-MM-DD>.md`: file paths with SHA-256, each
check with result and evidence (numbers, screenshots, commands), and the verdict.
Update the `Deliverables` table in `docs/PROJECT_STATE.md`.

## Completion

The verdict is `passed` only when every check is `pass` and every manual check is
signed. Any `fail`, `review` or `not checked` makes it `not passed`, listed with what
remains.
