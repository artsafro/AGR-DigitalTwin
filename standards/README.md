# Standards (machine-readable layer)

Machine-readable NPM/VPM rules used by `src/twinqa`, `src/dt_ai` and
`tools/qa/validate_package.py`. The human-readable rules with citations live in
`docs/domain/`; when the two disagree, `docs/domain/` and the regulation PDF win and this
folder must be fixed.

## Files

| File | Encodes |
|---|---|
| `NPM_STANDARD.yaml` | App.1 low-poly models (reg pp.1-13): archive, geometry, materials, atlas textures, glass, positioning, naming. |
| `VPM_STANDARD.yaml` | App.2 high-poly models + App.3 GeoJSON (reg pp.20-39, 51-55): archive, geometry, materials, UDIM textures, UV and texel density, UCX collision, positioning, naming, GeoJSON schema. |
| `DELIVERY_VALIDATOR.yaml` | Validator spec V001-V017: scope, gate (blocking / manual_review), engine, regulation pages, pass policy. |
| `traceability.json` | One row per profile rule and per stage: regulation pages, clause, status (`source_section_reviewed` / `review` / `specification_only`), decision reference. Byte-identical to AGR. |
| `source/source-lock.json` | SHA-256 lock: regulation PDF, the three YAML files (annotated project copies), `traceability.json`; plus AGR origin hashes. |

The regulation PDF (`Rasporyajenies19012026trebovaniya(2).pdf`, 56 pp., SHA-256
`933f6b700c074d0db6b82030fc79d1dbe9db4a0067495ca716e0636acd544222`, 24 MB) is committed
at `standards/source/` as a plain Git blob (the account's LFS budget is exhausted). The loader verifies its hash when the file is found
(`TWINQA_REGULATION_PDF` env var or `standards/source/<pdf_file>`). One loader serves both
packages: `twinqa.profiles.load_profiles`; `dt_ai.core.profiles` wraps it.

## Provenance

Ported on 2026-10-06 from AGR commit `d7ecdfda5f83d0c0ad672a65fc954031fca0cfbc`
(the former AGR project; full history in `data/archive/AGR_Project-all.bundle`). Original SHA-256 of each file is in
`source/source-lock.json` → `agr_origin.files_sha256`; YAML files carry a provenance
header. Changes against AGR: provenance headers, inline `# conflict #N` comments and a
`conflicts:` block; no rule value changed (parsed data minus `conflicts` equals AGR).

## Conflicts

Every field touched by an entry of `docs/domain/conflicts.md` is listed in the YAML's
`conflicts:` block (`<dotted.path>: {ids, status, note}`), and the loader rejects a path
that does not exist.

- `status: review` — the sources disagree and nothing is decided. A check whose outcome
  depends on the disputed reading ends as `review` with the conflict number; it never
  becomes `pass` or `fail` on that reading alone (e.g. non-empty `Glasses`, #13).
- `status: noted` — this profile's own text is explicit and the conflict is with the
  other profile or with local practice (e.g. VPM DirectX normals, #6; padding, #29), or
  the user decided the conflict (note starts with `decided <date>`: #1, #2, #3, #6, #12 on
  2026-10-07, mostly "as SINTEZ AGR Checker"). The value is applied.

Conflicts without a YAML field (they need a new rule, not an annotation): #7 two-sided
alpha planes, #14 NPM light removal, #23-#28, #31-#34 (local modelling decisions).

## Changing a rule

1. Change the YAML (and `traceability.json` if a rule path is added or removed).
2. Record why in `docs/domain/` (and `conflicts.md` if a side was chosen by the user).
3. Update the hash in `source/source-lock.json` (`profiles` / `traceability_sha256`).
   The loader refuses unlocked changes, so tests fail until the lock is updated.
