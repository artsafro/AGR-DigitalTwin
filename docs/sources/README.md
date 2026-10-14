# Sources

Heavy sources are local only (`data/sources/`, git-ignored). One row per source; the analysis of a
source goes to `docs/sources/<source-name>.md` (`analyze-architectural-source` skill).

| Source | Path | Format | Status |
|---|---|---|---|
| PSU275 AR/MEP | `data/sources/revit/26_ПСУ275_АР_МЭП_RVT22.rvt` | Revit 2022, 282 MB | analyzed with PDF/FBX/PPTX (`psu275.md`) |
| PSU275 MEP layout | `data/sources/revit/26_ПСУ275_Разбивочный файл_МЭП_RVT22.rvt` | Revit 2022 | not analyzed |
| KPP1 AR/MEP | `data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt` | Revit 2022, 110 MB | used for KPP1 v005 (Revit 2025 copy, `jobs/KPP1/STATE.md`) |

Legacy job outputs (Obr22, GLB, SOSH1150, Ground, MASHI, facades…) are in `jobs/<JOB>/outputs/` and
other untracked job files, about 4.9 GB, local only. Files over 50 MB committed as links:
`linked-files.json`.
