# Parapet and roof (`parapet`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3–§4; issues #16, #9; user decisions 2026-10-08.

## Signs in the spec

- The top input level (`levels[-1]`, e.g. `roof`) is the roof plane: the top of the roof covering,
  not the parapet top and not a structural level. `roof.parapet_h_m` = parapet top − roof plane.
- The parapet runs along the contour of the top floor; its top is read on the outer wall line.

## How the extractor reads the roof

- The roof level is input; geometry only confirms it: up-facing near-flat surfaces inside the top
  floor contour whose area-weighted height lies within ±10 cm of that level, covering at least
  25 % of the floor themselves and, with the cap along the outer edge and shaft tops of the body,
  at least 90 %. A surface along the outer edge (cap, coping) is not roof when another surface is.
  Equipment tops never close a missing roof. Otherwise the extractor stops and asks.
- **Drainage slopes are the norm of a flat roof.** Roof surfaces sloped up to 10° are one roof;
  its height is their area-weighted mean, reported with the height range and the slope (max,
  mean). Roof parts steeper than 10° are a question, not a guess (user decision 2026-10-08, #9).
- **A roof modelled as a separate object is normal, not a defect.** The body is the walls plus the
  parts that lie inside the contour of the top floor at the roof level ±10 cm; such parts join the
  body for the roof check. Anything else that is not connected stays an attachment. If a separate
  part at the roof level cannot be placed this way (partly outside the contour, another height),
  the extractor asks instead of choosing (user decision for #9, option (a)).
- Roof data from Revit (#10) is a comparison for the mesh path, not its main source.

## How to build

- Roof plane at the roof level inside the top contour; parapet walls from the roof plane to the
  parapet top along the contour (engine function to come with `from_spec.py`).

## Profiles

- `npm_min`: roof plane, parapet inner faces and cap; walkways and roof equipment are attachments.
- `mid`: same roof; detail in attachments.

## Check

- Roof height (area-weighted) ±10 cm of the input level; parapet height ±3 cm (HARNESS_PLAN §5).

## Traps

- Giving the parapet top or a structural Revit level as the roof level: the extractor stops with
  the nearby horizontal surfaces listed; give the covering top instead.
- A wide parapet cap or a terrace near the roof level is not the roof; a hole in the roof is
  accepted only as a shaft whose walls go down into the building.
