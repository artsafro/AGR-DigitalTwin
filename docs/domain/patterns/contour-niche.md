# Niche in the contour (`contour-niche`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3–§4, §7 (grey zone); user decisions 2026-10-08
(#6, #31); `GLOSSARY.md` (Level contour). Benchmark: B02.

## Signs in the spec

- A recess of the facade written as contour points: consecutive kinks that step the wall inward
  and back. It is in the contour only because it runs over the full storey height.
- Not a niche (it never reaches the contour):
  - a recess over part of the storey height (plinth, belt, cornice) goes to the questions file;
  - a door recess (from the floor, >= 1.9 m high, 0.7-3 m wide at its mouth) is an opening
    of kind `door`;
  - a bump or notch with both plan sizes <= 0.10 m is relief, and so is a band or groove with
    depth and height both <= 0.10 m (user decision 2026-10-09).

## How to build

- Nothing special for the walls: the niche walls are contour walls (`wall-from-contour`). Each
  inner corner is a corner of its own angle (`non-90-corner`).
- Where the niche exists on some floors only, the contours of neighbouring floors differ; close
  the step at the level line with a horizontal face over the contour difference (soffit or
  floor of the niche). Build it only from the spec contours, never from a guess.
- On the top floor the parapet follows the niche.

## Profiles

- `npm_min`: geometry; the niche changes the contour.
- `mid`: same; detail inside the niche belongs to openings and attachments.

## Check

- `floor_areas` (the niche area is missing from the storey), `silhouettes` (top view), `mesh`.

## Traps

- Grey zone: a recess that is not clearly a full-height niche is never built on a guess. Build the
  module without it, ask with numbers (depth, length, floors) in `jobs/<object>/questions.md`,
  continue.
- An opening on a niche wall refers to that wall's index; it moves with the niche, not with the
  main facade.
- A niche narrower than twice the shell depth makes the inward shell collide: stop and ask.
