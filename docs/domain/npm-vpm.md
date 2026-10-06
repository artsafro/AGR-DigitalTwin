# NPM / VPM profiles, delivery structure, GeoJSON

Provenance keys: `reg p.N` = regulation `Rasporyajenies19012026trebovaniya(2).pdf` (Moscow DIT + Moskomarkhitektura order 19.04.2023 No 64-16-192/23/769, 56 pp., SHA-256 933f6b70...4222), PDF page index from 1, text read via OCR layer (pdftotext -enc UTF-8); pages 32 and 40 also checked as rendered images. `local:` paths are relative to the repo root (AGR `docs/` lives in `docs/agr/`).
Appendix map: App.1 NPM = pp.1-19, App.2 VPM = pp.20-50, App.3 GeoJSON = pp.51-56 (reg p.1, 20, 51; local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#1).

## Terms
- NPM = low-poly model; VPM = high-poly model; OKS = designed/reconstructed building with facade (buildings, underground-parking entrances, stylobate). Existing non-reconstructed buildings inside the site are NOT modeled. reg p.2, 21, 26.
- Usable roof (эксплуатируемая кровля) and greenery on roof/stylobate belong to the OKS, not to Ground. reg p.2, 7, 21.
- Ground (благоустройство) NPM = 3 parts: Ground relief/planes with texture (zones, parking marks, lawn-level greenery, road markings), GroundEl (MAF, fences, lighting masts, planters), Flora (greenery ~2x+ above lawn). reg p.1-2.
- Ground bounds = whole land plot, or the construction-stage boundary if the project is one stage; nothing outside current stage. reg p.2, 21.
- Courtyards open to sky, niches and border spaces are part of Ground; keep their furniture (urns, cafe tables, planters). reg p.29 §3.19, p.48.
- Material ID != SlotNumber != UDIM tile; no regulation rule "MatID n -> UDIM 100n". local: docs/agr/DIGITAL_TWIN_AI_PROJECT_BRIEF.md#1; local: standards/VPM_STANDARD.yaml#not_in_this_standard (project decision to keep them separate).

## Common to both
- FBX 7.4 (FBX 2014) binary; licensed software; no malware. reg p.4, 24.
- Model must match booklet/sketch design + project documentation; all OKS and Ground (incl. MAF, greenery, light poles) implemented fully and identically in VPM and NPM. reg p.4, 24.
- Metric: 1 unit = 1 m; scale 1:1. reg p.4.
- Scene cleaned: no lights (NPM), cameras, particles, fog. VPM list omits lights (lights go to separate Light FBX). reg p.4, 24.
- Address variable: Latin letters, digits, `_` only; other chars incl. space -> `_`; elements separated by `_`; numbers and letters separated by `_`; numeric part of street name written joined (`2jKotelnicheskijPereulok_Vl_3`); each word capitalized; only the word "улица" omitted; abbreviations per MinFin order 171n without trailing dot. reg p.4-5, 24-25.
- No address -> cadastral number of plot (any one of several) or of quarter; `:` -> `_` (e.g. `77_06_0002014_35`). reg p.5-6, 25.
- VPM only: free-standing buildings get unique index `_001`, `_002`... after address (`ProezdNansena_Uch_8_001`). reg p.26 §3.7. Not in YAML (local: docs/agr/decisions/ADR-0002-source-discrepancies.md#11).

## NPM (Appendix 1)
- One ZIP <= 1 GB, no broken/unreadable files. reg p.6 §1.1. 1 GB = 1024 MiB (conflict #12, decided as the checker).
- ZIP holds 2-21 FBX: 1 Ground FBX (mandatory) + up to 20 OKS FBX; textures embedded. reg p.6 §1.2, p.7 §1.6, p.14 fig.2.
- OKS FBX total <= 40 geometry objects: OKS geometry incl. usable roof (<= 20 objects, <= 40 texture sets) + translucent parts (<= 20 objects, no texture sets). reg p.6 §1.4.
- Ground FBX (<= 22 texture sets): Ground (<= 20 sets, also limited by density), GroundGlass (no sets), GroundEl (1 set), GroundElGlass (no sets), Flora (1 set, all vegetation). Usable-roof objects not in Ground. reg p.6-7 §1.5.
- Split OKS into several FBX (<= 20) ONLY when one FBX exceeds triangle limit; split only by indivisible units (free-standing building, section, korpus, structure, stylobate); translucent parts split accordingly; numbering continues across FBX (not reset). reg p.7 §2.1-2.4, p.14 fig.3.
- Triangle limits: OKS + its usable roof <= 150 000 per FBX; Ground + GroundEl + Flora total <= 180 000. reg p.7 §3.6.
- GeoJSON and UCX are NOT part of NPM package per App.1; add only if separate customer spec requires. local: standards/NPM_STANDARD.yaml#not_in_this_standard; local: docs/agr/READINESS_REPORT.md#2 (project decision: do not transfer VPM rules to NPM).
- Texture sets: 1 set per OKS; +1 extra set allowed if usable roof exists (may also hold facades). reg p.9 §5.11.
- Coordinates: geometry placed in Moscow coordinate system and heights per project; arbitrary/conditional coords or missing heights forbidden; object rotations after reset = OKS rotation in plan. reg p.10 §8.

## VPM (Appendix 2)
- Separate ZIP per free-standing OKS (incl. stylobate, korpus, usable roof) <= 500 MB; separate Ground ZIP <= 1 GB. reg p.26 §1.1, §1.3. Units are binary: 500 MiB / 1024 MiB (conflict #12, decided as the checker).
- ZIP content: FBX model; optional lighting FBX; GeoJSON; 3-2100 PNG. Textures NOT embedded. reg p.26 §1.2, p.30 §5.1.1.
- Project meta: 2-21 ZIPs (1 Ground ZIP + 1-20 OKS ZIPs); 1-700 texture sets (Diffuse, ERM, Normal). reg p.40 fig.2.1 (image-verified).
- Triangle limits (table): OKS + usable roof <= 1 000 000 per FBX excluding collision; Ground by (site area - building footprint): <=0.05 ha 300k; 0.05-0.1 705k; 0.1-0.25 1 125k; 0.25-0.5 1 650k; 0.5-0.75 1 950k; 0.75-1 2 625k; 1-1.5 3 150k; >1.5 ha 4 500k. reg p.28-29 §3.9-3.10. CONFLICT with fig. p.40 (800k/3M) - see conflicts.md.
- Project target (user decision 2026-10-07, conflict #1): <= 150 000 triangles per OKS FBX in VPM too, so the same model is reused for NPM. If that is impossible, replace windows with atlas textures on planes before adding geometry. The table above stays the hard limit; the validator reports 150 001-1 000 000 as review, above 1 000 000 as fail.
- Ground FBX is mandatory part of AGR. reg p.26 §1.4.
- Pivot/origin: per FBX own origin at world 0,0,0; OKS/Ground pivot at geometric center of model in X,Y and Z = project zero elevation; all meshes in one FBX share the same pivot (glass pivot = OKS pivot); collision pivots free; all rotations = 0 after reset; placement described by paired GeoJSON. reg p.32-33 §9 (image-verified p.32).
- Example structure: `SM_Etalonskaya_25_K_3.zip` -> `SM_..._K_3.fbx`, `SM_..._K_3_Light.fbx`, `SM_..._K_3.geojson`, `T_..._K_3_{Diffuse|ERM|Normal}_1.{1001..1008}.png`. reg p.41 fig.2.2.

## VPM lighting FBX (architectural light design)
- File `SM_Address_Light.fbx` / `SM_Address_Ground_Light.fbx`. reg p.33 §4.1.
- <= 250 lights per FBX; if exceeded, only most visible areas. Only omni point lights and conical spot lights; no renderer-specific lights (VRay/Octane/Corona/Arnold). Only color and intensity are configured. reg p.37-38 §15.2, 15.4, 15.6-15.7.
- Min spacing between neighbor lights: omni 5 m, spot 1.5 m. reg p.38 §15.5.
- Hierarchy: all lights parented to one root helper (empty, e.g. wire cube, pivot at its center); root pivot must coincide with lit object's pivot. reg p.21, p.38 §15.8-15.9.
- Names: `Address_Root`, `Address_Spot_001`, `Address_Omni_001` (001-250); Ground: `Address_Ground_Root/Spot_NNN/Omni_NNN`. reg p.34-35 §4.5-4.6.
- Light fixtures' glow = ERM red channel; light flux affecting surroundings = separate lights, not part of model. reg p.37 §14, §15.3.
- No collision required in lighting FBX. reg p.36 §13.3.

## GeoJSON (VPM only; App.3)
- Exact structure/syntax/names/values per App.3; UTF-8; only values may change - no renamed/duplicated/miswritten keys. reg p.26 §2.1, p.27 §2.5, p.28 §2.7.
- `{"type":"FeatureCollection","features":[{"type":"ObjectFeature","properties":{...},"geometry":{"type":"Point","coordinates":[x,y]},"Glasses":...}]}` - note literal `ObjectFeature`, not standard `Feature`. reg p.51-53.
- Properties: address, okrug (<=50 ch), rajon (<=50), name, developer (<=255), designer (<=255), cadNum, FNO_code, FNO_name (<=255), ZU_area (ha, <=4 decimals), h_relief (zero elevation m, <=2 dec), h_otn (max relative height, <=2 dec), h_abs (max absolute height, <=2 dec), s_obsh, s_naz, s_podz, spp_gns (m2, <=2 dec), act_AGR, imageBase64, other. reg p.53-55.
- cadNum mask `AA:BB:VVVVVVV:GG` (plot) or `AA:BB:VVVVVVV` (quarter); FNO_code mask `XXX XXX XXX` / `XXX XXX` / `XXX` per 306-PP. reg p.53.
- Multiple values allowed only in okrug, rajon, developer, designer, cadNum: comma-separated inside one string. reg p.27 §2.4.
- Org names quoted with typewriter apostrophe inside string: `"OOO 'Buro ...'"`. reg p.27 §2.3.
- Address string adds korpus/section info per cut building; none for stylobates. reg p.27 §2.2.
- OKS: all values except `other` mandatory and truthful; Ground: FNO_name, FNO_code, h_otn, h_abs, s_obsh, s_naz, s_podz, spp_gns, other may be empty `""`. reg p.27 §2.6, p.52 example. (Conflict with p.53-54, see conflicts.md.) **Decided 2026-10-07 (conflict #2, as the checker):** OKS `FNO_code` mandatory (3/6/9 digits, FNO classifier), `act_AGR` may be empty; an unknown `FNO_code` blocks delivery - ask the customer, never invent it.
- imageBase64: source JPG 256x256 converted to base64. reg p.54.
- coordinates: insertion point in MSK-77, 3 decimals, must match plan position per SPOZU; max offset 0.5 m. reg p.55 §21.
- Glasses: when no glass -> `[]`; otherwise object keyed by glass material name (`M_Address_MainGlass_1`..`_7`, `M_Address_GroundGlass_N`) with `color_RGB {Red,Green,Blue}` 0-255, `transparency` 0..1 (0 = fully transparent, 1 = opaque), `refraction` 1..3, `roughness` 0..1, `metallicity` 0..1. reg p.51-53, p.55 §22.
- Refraction reference: air 1.00, water 1.33, ice 1.31, glass 1.50, acrylic 1.49, quartz 1.52, diamond 2.42. reg p.56.
