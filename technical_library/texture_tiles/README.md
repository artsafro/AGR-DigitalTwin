# Карты материалов: одна операция, конфигурация объекта отдельно

`cli.py` выполняет validate → draw → PNG readback → ZIP readback. `panels.py`
содержит неизменённую панельную математику КПП v001. `kpp_v001.json` — цвета,
размеры и ID/UDIM конкретного кейса; временный clipboard путь не переносится.
Рецепт `solid` общий; `metric_pattern` вызывает уже опубликованный
`tools/facades_texture_pattern.raster`, без второй копии метрической математики.
RGB конфигурации: целые sRGB0–255; raster получает normalized0–1, PNG округляет
к uint8. `extent_m`, offset_m, panel_dimensions_m/joint_m — физические метры,
не произвольное масштабирование по Ground. Реальный metric export этим кейсом
не принят: отдельный synthetic fixture проверяет reuse того же raster.

```powershell
python technical_library/texture_tiles/cli.py --config technical_library/texture_tiles/kpp_v001.json --output <new-directory> --reference <local-original-maps-directory>
```

Output не должен существовать; имена PNG формируются только из целого UDIM.
Duplicate ID/UDIM и неизвестный рецепт отклоняются до создания output.
PNG реально открывается и проверяется; ZIP читается обратно и сверяются SHA.
`opposite_edges_equal` для metric_pattern — диагностическое поле: первый/последний
pixel centre не обязаны совпадать у метрически периодического сигнала.
Исходные карты/сцены не изменяются; ZIP/PNG остаются локально.

[QA.json](QA.json): 11 карт КПП совпали с прежними PNG **по каждому пикселю и
побайтно**. 1001/1005 — 4096², остальные256², RGB. ZIP каждого PNG совпал по SHA.
Алгоритм панели/seed2030 сохранён; 3×8 рисунок не задаёт неизвестный физический
размер панелей. RGB легенды не является лабораторным NCS/RAL преобразованием;
неоднозначный цвет1002 и diffuse-only glass1011 сохранены явно в конфигурации.
`delivery_passed=false`: shader/UV/Max/Checker/визуальная сдача модели не проверены.

Provenance: [SOURCE.json](SOURCE.json). Здесь нет копий v001/v002 каждого объекта;
новый набор карт добавлять данными или новой ответственностью, не вторым builder.
