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
