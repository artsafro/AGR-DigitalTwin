# Conflict choices for VPM and windows (prepared 2026-10-09)

One choice per conflict for the user (`docs/backlog.md` → C1–C34). Numbers are those of
`docs/domain/conflicts.md`. Nothing here is decided until the user writes the decision; then it
goes to `conflicts.md`, the matching file of `docs/domain/` and the YAML `conflicts:` block
(status `noted`). Order: after the B01 benchmark; none of these blocks B01–B03 (`npm_min`,
geometry before UV and textures).

| # | Topic | Blocks | Recommendation |
|---|---|---|---|
| C3 | UCX triangle budget | — | already decided 2026-10-07 (checker formula); encoded in `VPM_STANDARD.yaml` |
| C7 | Two-sided alpha planes | VPM alpha planes (P5/P6 era), shared plane tools | A: rule per profile |
| C8 | Alpha in textures | VPM Diffuse with cut-outs | A: rule per profile (YAML already says so) |
| C10 | Texel density formula | V009 (Q2) | A: division, as the page image |
| C24 | Window plane seating | `opening-plane` in real objects | C: mid-reveal in `npm_min`, measured in `mid` |
| C25 | Infill recess behind the frame | `mid` windows only | B: a window-type parameter, default from the library |

## C3 — UCX triangle budget (decided)

Decided 2026-10-07: < 50 000 triangles -> 15 000, else min(ceil(5 %), 100 000), as the SINTEZ AGR
Checker. `standards/VPM_STANDARD.yaml` `collision.triangle_limit` carries it (`noted`). Left: the
boundary 49 999 / 50 000 is untested; test it with the UCX validator V010 (P5).

## C7 — Two-sided alpha planes

- NPM: no thickness and no duplicated offset faces on opacity geometry (reg p.8 §3.13).
- VPM: a duplicate face 0.003–0.01 m off with a flipped normal (reg p.36 §12.3; offset already in Q6).

The two rules belong to two profiles, so they do not contradict each other; the risk is a shared
tool that applies one rule to both.

- **A (recommended):** rule per profile. NPM: one face, opacity map. VPM: duplicate at 0.005 m
  (inside 0.003–0.01), normal flipped. Tools that make alpha planes take the profile as input.
- B: one rule for both (NPM-style single faces). Breaks reg p.36 for VPM.

Decision: _____

## C8 — Alpha in textures

- NPM: no alpha channel; a separate opacity map is allowed (reg p.9 §5.5, §5.8). Decided with C21
  on 2026-10-07: RGB + `_o_` map.
- VPM: alpha in Diffuse allowed for cut-outs; ERM / Normal never; MainGlass has no maps (reg p.30, 32, 36).

Both YAML files already carry it as `noted`; only `conflicts.md` lacks the decision line.

- **A (recommended):** confirm the rule per profile as encoded. NPM opacity always a separate
  `_o_` map. VPM cut-outs in Diffuse alpha (0–127 invisible, 128–255 visible).
- B: separate opacity maps in VPM too. Allowed by the regulation, but it adds a map per material.

Decision: _____

## C10 — Texel density formula

- OCR text of reg p.32 shows "+"; the page image shows rho = L_t / L_p (texture side in px /
  polygon length in m). Image-verified (`docs/agr/decisions/ADR-0002-source-discrepancies.md#12`).
  The worked examples on the page only add up with division (4096 px over 7.8 m = 525 px/m).
- **A (recommended):** division, range 512–1706 px/m on Diffuse only. V009 (Q2) is built on it.
- B: wait for a corrected regulation. V009 stays `not_run`.

Decision: _____

## C24 — Window plane seating (NPM)

- Accepted earlier project: the plane at mid-reveal depth, 10 mm past the opening edges on 4 sides;
  seating behind the reveal was rejected (visible slits) (`docs/domain/geometry.md`).
- General rule: measure the seating per window from the source; the 10 mm embed does not define
  the seating depth; do not invent it.

The benchmark checker accepts both: a plane anywhere inside the reveal, within 2 cm of the edges.

- A: always mid-reveal + 10 mm. Simple, accepted once; ignores a real window that sits elsewhere.
- B: always measured. Needs the window position in every source; an `npm_min` mesh source often
  has only the hole.
- **C (recommended):** `npm_min` mid-reveal + 10 mm. `mid` measured from the source (Revit family
  offset, glass position in the mesh), mid-reveal as fallback, written in the report.

Decision: _____

## C25 — Infill recess behind the frame (`mid`)

- Window library pilot: infill 30 mm behind the frame face (`jobs/REVIT-OPENINGS`, not accepted).
- Another project: 35 mm, with a 10 mm glass-edge grip, 40 mm frame face, 80 mm depth (`jobs/MASHI-LP`).

Only `mid` windows use it. `npm_min` has a plane only.

- A: one number for every window (30 or 35 mm).
- **B (recommended):** a parameter of the window type in `library/windows/window_types.json`;
  default 30 mm until a type gives its own. Decide the default when the first `mid` window is built.

Decision: _____
