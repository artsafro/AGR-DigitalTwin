# Corner that is not 90° (`non-90-corner`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3–§4, §7; extractor `src/dt_ai/spec/mesh.py`
(kinks, arcs); `docs/domain/geometry.md` (contour orthogonalization, corner windows). Benchmark: B02.

## Signs in the spec

- Two consecutive contour edges with a turn other than 90°. The extractor keeps kinks over 5° as
  given and drops kinks of 5° or less on purpose.
- Rounded corner: `[x, y, {"r": r}]`. An arc is read only when its points and both walls fit one
  circle within 5 mm + 0.5 % of r.

## How to build

- Both walls end on the shared contour vertex: one vertical corner edge, shared and welded, no gap
  and no overlap.
- The corner edge carries the facade's shared Z cuts, so both walls split at the same heights
  (engine function to come with `from_spec.py`).
- Rounded corner: an arc of radius r tangent to both walls, each chord a planar wall strip.
- The shell offset (and reveals near the corner) follows the true angle, not 90°.

## Profiles

- `npm_min`: planar walls meeting at the vertex; arcs with the fewest chords that stay inside the
  silhouette threshold.
- `mid`: same corner; more chords on arcs only when the silhouette check asks for it.

## Check

- `floor_areas`, `silhouettes` (top view shows the angle), `mesh` (no non-manifold edge or
  overlapping faces at the corner).

## Traps

- Never square a corner silently. Orthogonalization may move a vertex by at most 0.25 mm; a wall
  that needs more is reported, not flattened.
- An opening never runs across the corner vertex: it belongs to one wall. A corner window is two
  openings with two planes (`opening-plane`).
- Elements on a dropped small kink are still measured on the real facet.
- If the inward shell offset self-intersects at a corner, stop and ask (proposed safeguard).
