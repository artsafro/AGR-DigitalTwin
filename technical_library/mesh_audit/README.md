# Общая инвентаризация сетки

Одна операция вместо локальных копий basic inventory/readback в Ground, MASHI,
Revit, знаках, mesh optimization и продуктовых Blender-кейсах. Не заменяет
специализированный contour, BVH, CheckToolBox, геометрический fit и AGR Checker.

`core.py` — чистая топология по массивам; `blender.py` — чтение blend/FBX и отчёт.
Входы и выбранные object/collection задаются явно. Отчёт должен быть новым;
сцена не сохраняется, SHA входа проверяется до/после.

```powershell
& <blender.exe> --background --factory-startup --disable-autoexec --python-exit-code 1 --python technical_library/mesh_audit/blender.py -- --source <source.blend> --output <new-report.json> --collection LP
```

Повторяемые `--object`/`--collection` ограничивают набор; совместное использование
даёт пересечение этих фильтров. Без фильтров — все mesh текущей сохранённой сцены.
Извлекаются world XYZ × scene unit scale, polygon-size histogram, компоненты,
границы/multi-face/loose edges, material interfaces, дубли, UV finite/bounds.
Материал — индекс слота, не доказательство реального Max Material ID.

Дубли считаются внутри каждого объекта: rounded vertices (8 decimals), faces
по отсортированным индексам. Fan area пригодна как диагностика нулевой площади,
а не доказательство корректности вогнутых/самопересекающихся ngon. Fan triangles
— счётчик n−2, не evaluated-модификаторы. Не проверяются межобъектные overlaps,
растяжение UV, texel density, сохранение исходного контура, shaders, BVH/визуальный вид.
`delivery_passed=false` всегда: basic inventory не сдача модели.

[REPLAY.json](REPLAY.json): 9 запусков Blender4.4 на фактических сохранённых
blend/FBX, SHA всех входов неизменны. Ground blend и FBX: 33103 vertices /
32392 quads / 18 slots; ранее допустимые исходные overlaps сохранены. MASHI:
605194 faces / 615536 triangles, LP/Revit/LP_old не переименованы. Знаки:
8 mesh / 1144 faces. Остальные файлы — readback, не повторная визуальная приёмка.

Исходные версии/происхождение: [SOURCE.json](SOURCE.json), [реестр](../SOURCE_COVERAGE.jsonl) и [группы](../GROUP_REVIEW.md).
Blender API сверено через Context7 `/websites/blender_api_4_2`: raw meshes,
UV loops; фактический runtime4.4. Общие синтетические edge/duplicate/component
fixtures в tests/test_shared_library.py не заменяют реальные DCC-прогоны.
