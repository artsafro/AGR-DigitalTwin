# Benchmark

Hand-made etalons and the checks that compare a model with them (`docs/HARNESS_PLAN.md` §5).
Terms: Etalon, Spec, Level contour in `GLOSSARY.md`.

- An etalon is modelled by the user in 3ds Max on a grid, in whole numbers, with level
  helpers `LEVEL_<name>`; the agent gets `.max` + FBX (large files by link).
- Direction is etalon -> extractor -> `spec.json`, never the reverse. Nobody writes a spec by hand.
- Compared: geometry, before UV and textures. UV/PNG stay with V006-V008; the final FBX goes
  through the delivery validator at the very end. These checks do not replace V001-V017.
- Every threshold lives in `<bench-id>/tolerances.json`, not in code.
- Any rule change reruns the whole set: fixing one benchmark must not break another.

| Id | What it tests | Patterns |
|---|---|---|
| `bench-b01-box` | box 10x10 m, 2 storeys, 2 windows, flat roof with parapet | wall-from-contour, opening-plane, typical-floor-repeat, parapet |
| `bench-b02-corner-niche` | one non-90 corner, one contour niche, two roof levels | non-90-corner, contour-niche |
| `bench-b03-attachments` | rounded corner, vent grille, AC basket, outside stair | attachments (patterns to be written) |
| `bench-k01-kpp1` | first real building, object `tec26-kpp1` | all of the above |

Layout of one benchmark:

```
<bench-id>/
  README.md         what is checked, which patterns
  etalon.max        user's hand model (by link when large)
  etalon.fbx        export with LEVEL_<name> helpers
  spec.json         taken by the extractor from the etalon
  tolerances.json   thresholds for the checks
```
