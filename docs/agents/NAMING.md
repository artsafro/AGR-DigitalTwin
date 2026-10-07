# Naming

Decided by the user on 2026-10-07. A name says **what the thing does**; the object it was
first made for lives only in data (`jobs/<object-id>/`, its config and its outputs). Shared
scripts, tools, skills, branches and shared tags carry no object code.

Apply this to every new name. Existing names are migrated stage by stage (`docs/backlog.md`);
until then, keep a legacy name and give the new one in the commit or STATE.

## Object id

`<site>-<code>`, lowercase ASCII, digits kept: `tec26-kpp1`, `tec26-psu275`.
The registry `jobs/REGISTRY.md` maps each id to its Russian name, sources and job folder.
Delivery file names (`SM_Kpp_1`, `0000_Kpp_1`, …) follow the AGR regulation and stay as the
regulation demands; they come from the object's data, never from a script name.

## Scripts and tools

`<verb>_<subject>[_<qualifier>][_<dcc>].py`, snake_case, no version and no object code.

| Verb | Meaning |
|---|---|
| `inspect` | read a source or scene, change nothing |
| `measure` | take dimensions, marks, openings, clearances from a source |
| `build` | create geometry |
| `assemble` | combine built parts into one scene |
| `connect`, `seal` | join parts; weld or embed joints |
| `clean` | remove loops, doubles, strips that carry nothing |
| `unwrap`, `pack` | UV |
| `texture`, `atlas` | make textures; build or remap an atlas |
| `export`, `package` | write FBX/GLB; build a delivery ZIP/package |
| `readback` | read an exported file back and record what it holds |
| `check` | QA with a pass/fail result |
| `render` | previews and comparison images |
| `run` | orchestrate other steps |

Subjects are glossary terms (`GLOSSARY.md`): `body`, `shell`, `roof`, `openings`, `fills`,
`stairs`, `parts`, `ucx`, `atlas`, `ground`, `flora`, `mesh`, `package`. Add a new subject to
the glossary first. The DCC suffix (`_blender`, `_max`, `_revit`, `_autocad`) appears only
when the file runs inside that application.

Shared tools are grouped by pipeline stage: `tools/source/`, `tools/geometry/`, `tools/uv/`,
`tools/materials/`, `tools/export/`, `tools/qa/`, `tools/render/` (plus the existing
`tools/mcp/`, `tools/herdr/`, `tools/git-hooks/`).
Examples: `seal.py` → `tools/geometry/seal_joints.py`; `qa_master_psu275.py` →
`tools/qa/check_mesh.py`; `build_facades_textures_v004.py` → `tools/materials/texture_facades.py`.

## Job folders

```
jobs/<object-id>/
  object.json   # zero mark, frame transform, profiles, finishes, delivery names
  STATE.md, REPORT.md
  run.sh        # calls shared steps with object.json
  scripts/      # one-off steps for this object only, named by the same rule
```

Operation jobs that are not an object (atlas, UV, audit trials) use `<subject>-<what>`:
`window-atlas`, `mesh-opt-audit`.

## Output folders and files

`outputs/<stage>-v<NNN>/` with a three-digit version: `build-v006`, `package-npm-v003`,
`max-review-v002`. A new run takes a new version; the folder of an existing version is
never reused.

## Branches

`<type>/<area>-<what>`, lowercase, hyphens. Types: `feature/`, `fix/`, `experiment/`,
`research/`, `harness/` for shared code and the harness; `job/<object-id>-<stage>` for work on
one object (`job/tec26-psu275-delivery`). Rename an auto-generated agent branch
(`claude/<random>`) before its first push or merge.

## Tags

Annotated tags only; the message states scope, status and open gates.

| Family | Form | Example |
|---|---|---|
| Object milestone | `object/<object-id>/<stage>-v<NNN>-<status>` | `object/tec26-psu275/delivery-v003-reviewed` |
| Shared pipeline | `pipeline/<capability>-v<N>` | `pipeline/vpm-npm-v1` |
| Domain decisions | `domain/<what>` | `domain/conflicts-batch2` |
| Repository baseline | `baseline/<YYYY-MM-DD>` | `baseline/2026-10-07` |

Status follows the separate statuses in `AGENTS.md`: `reviewed` (user accepted as reviewed),
`qa-passed` (every mandatory check and gate closed), `delivered` (handed over). A higher
status is a new tag on the commit that earned it.
