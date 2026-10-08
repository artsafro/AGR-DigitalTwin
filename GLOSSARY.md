# Glossary

One term per heading. Use these terms exactly in docs, prompts and reports.
Add a term when it is misunderstood or has to be explained twice.
Origin of migrated terms: the former AGR project (`docs/agr/`: brief, UV_RULES.md).

## NPM

НПМ — low-poly delivery model. Rules: appendix 1 of the source regulation PDF
(pages 1–19). Geometry in Moscow coordinate system (MSK-77) at project heights.
Textures: PNG atlas embedded in FBX, usually one texture set per OKS (an extra
set allowed for an accessible roof). UV: regions of one atlas shared by finish type.
Ground texel density is not applied to NPM-OKS.

## VPM

ВПМ — high-poly delivery model. Rules: appendix 2 of the source regulation PDF
(pages 20–50), GeoJSON in appendix 3 (51–56). FBX local origin at zero; insertion
coordinates in the paired GeoJSON. PNG maps (Diffuse/ERM/Normal, DirectX normal)
delivered separately from FBX, UDIM tiles. Target: one UDIM per texture ID.
Includes `UCX_` collisions and GeoJSON; these are not NPM requirements.

## OKS

ОКС — the capital construction object (building) being delivered. Profiles:
NPM-OKS, VPM-OKS, NPM-territory.

## Body

BODY — the building's main shell mesh: exterior faces only, no interior.
Cuts follow corners and real openings; clean exterior mesh with holes first,
then Shell inward 0.4 m, then windows. Kept as a logical group separate from
windows and roof.
In a source mesh read by the spec extractor, the body (корпус) is the largest connected
part; attachments (canopies, porches, stairs, roof equipment) are the other parts.
Decided 2026-10-08 (`docs/HARNESS_PLAN.md` §4).

## AGR

TODO: confirm the expansion (likely архитектурно-градостроительное решение).
AGR Checker — SINTEZ AGR Checker, the Blender add-on that validates deliveries.
A partial check (e.g. only its texel-density function) is not an AGR Checker pass.

## Master scene

TODO: define. Related concept from AGR project: Master Building — one semantic
layer (elements, surfaces, floors, openings, materials, sources); NPM and VPM
are derived from it.

## Source album

TODO: define (PDF facade album with materials schedule and window sizes?).

## Current album

TODO: define.

## Production asset

TODO: define.

## Spec

`spec.json` — the normalized description of one building's exterior that every modelling
run starts from: levels, a level contour per floor, openings, roof, attachments and a
mandatory `frame` to the object's coordinate system. Written only by an extractor, never
by hand. Contract: `docs/HARNESS_PLAN.md` §3.
_Avoid_: Master Building (the older quad-list schema), brief.

## Level contour

Контур уровня — the walls of the body over the full storey height: the closed outer boundary
of the horizontal body section found at both ends of the storey. Anything not over the full
height (plinth, belt, cornice, partial recess) never changes it and goes to the questions file;
2 or more levels or over 10 % of the facade length only raises the question's priority.
Decided 2026-10-08 (#6).
_Avoid_: footprint (that is the ground print only), outline.

## Etalon

Эталон — a benchmark building modelled by hand by the user (3ds Max, `.max` + FBX) on a
grid, from which the extractor takes the reference spec. Levels are marked by helpers
`LEVEL_<name>`. Lives in `benchmark/<bench-id>/`. An etalon with defects teaches defects.
_Avoid_: reference model, sample.
