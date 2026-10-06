# PSU275 — main building No 1

Sources and findings: `docs/sources/psu275.md`. Profile: NPM + VPM.

## Done (2026-10-07)

- S1 PDF album, S2 Revit (via the modified 1644 copy), S3 FBX inspected read-only.
- Decisions: geometry = Revit; PDF for appearance only; missing parts from FBX;
  first target = first floor (level 0.000) of main building No 1.

## Open

- Questions 1–3 in the source report (zero mark / MSK-77, object name, clean Revit copy).
- Fit FBX → Revit transform (offset, rotation) on two or more grid intersections.
- First-floor bounds: 0.000 to next level along the facade (+3.000 in the bays, the hall is
  a single volume) — confirm with the user.

## Next

Export level 0.000 walls/curtain walls/doors from Revit (3D view cropped to the first
floor) to a versioned FBX, build BODY in Blender (`src/dt_ai/geometry/exterior.py`).
