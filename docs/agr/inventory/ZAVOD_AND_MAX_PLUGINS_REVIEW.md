# Дополнительный разбор zavod и библиотеки плагинов Max

26.09.2026. База: `37930230ec9bbb8345f58821594380c19903dc0c`.
Проверены указанные пользователем `C:\Users\artsafro\Desktop\zavod` и
`C:\Users\artsafro\Desktop\!3D viz\Плагины 3dMax`.
Это продолжение каталога, а не повторное доказательство DCC-готовности.
**Ни один найденный скрипт/установщик не запускался; оригиналы не изменены.**

## Охват и доказательства

Свежий проход `tools/inventory_scan.py`: 479 + 919 = **1398 файлов** выбранных
расширений, без ошибок обхода. Это не число инструментов: сюда входят 546 `.max`,
справочные примеры, документация и сборочные файлы. Карты, виртуальные окружения,
кэши, junctions и некоторые служебные каталоги исключены настройками сканера.
EXE/CSV/RAR/7z не входят в его фильтр; содержимое этих форматов в этом проходе
не исследовалось. GeoAGR уже имеет отдельный подробный отчёт.

Все **48 MZP** открыты как ZIP: прочитаны списки модулей и доступные `mzp.run`,
выбранные исходники. Установочные команды не выполнялись, архивы не распаковывались
в Max. Крупные библиотеки моделей не открывались. Полного аудита каждой строки
каждого скрипта нет: ниже указаны исследованные точки входа и ограничения.

Проверено 60 сопоставлений имён loose scripts/членов MZP с ранее найденными
установленными файлами Max, из них **57 SHA совпали, 3 отличаются**. Список путей
для сравнения взят из предыдущего сканирования, но хеши файлов прочитаны заново.
Это выборочное сравнение, отсутствие совпадения не доказывает отсутствие установки.
Отдельно проверены **40 Python-модулей xView: все совпали** с установленным пакетом.
Свежим чтением подтверждены startup xView и привязка Copitor в Octopus.
Настройка запуска не доказывает частоту использования или результат операции.

Метаданные, хеши, точки входа, архивные модули и сравнения:
[folder-followup-evidence.json](folder-followup-evidence.json).

## Что действительно полезно

### 1. xView: готовые исходники геометрических проверок — MAX-26

Источник: `XViewInspectorMax\XViewInspectorMax.mzp`, пакет `xview_max`0.1.0.
Установлен в `...\3dsMax\2024 - 64bit\ENU\scripts\xview_inspector_max`;
startup и `C:\usermacros\XViewInspectorMax.mcr` ведут к этому пакету.
40 `.py` совпадают с архивом; сам установленный макрос отличается от архивного.

Доступны `checks/duplicate_faces.py`, `open_edges.py`, `non_manifold.py`,
`overlapping_vertices.py`, `self_intersections.py`, zero-area/zero-length,
nonplanar, sliver, ngon/triangle и loose-geometry checks.
Контракт `MeshData`: vertices XYZ, faces с **0-based** индексами, необязательная
карта рёбер; findings возвращают **1-based** индексы Max. Параметры отдельно в
`AnalysisSettings`. Чистые модули checks/core отделены от DCC-извлечения и GUI.

Ограничения, видимые из исходников:

- `duplicate_faces` сравнивает наборы vertex IDs; это не полный поиск геометрически
  совпадающих граней с разными вершинами.
- `non_manifold` отмечает рёбра с 0 или >2 смежными гранями; открытые рёбра проверяет
  отдельный модуль. Один non-manifold check не доказывает замкнутость UCX.
- `self_intersections` делает fan triangulation n-gon и по умолчанию ограничен
  20000 треугольников; превышение вызывает `RuntimeError`, не успешную проверку.
  Вогнутые n-gon и invalid indices требуют отдельных negative fixtures.
- Метаданные автора: «Все права защищены». Наличие Python не означает разрешение
  скопировать его в наш репозиторий. Здесь сохраняются только метаданные.

Решение: **обернуть адаптером**, workflow **prototype**. DT-020/021/033.
Сначала локальный worker вокруг установленной копии, синтетические mesh-контракты,
сохранение ошибок/пропусков и сопоставление checks→PDF. На этом этапе checks не запускались.

### 2. Andrew Maf Tools: MatID→UDIM, плотность и упаковка — MAX-31

`Andrew_scripts\Maf Tools.mcr`, открытый MAXScript. Основные точки:
`unwrapByMatIDToUDIM_Advanced`(стр.243), `tdt_GetMeters`(438),
`tdt_OptimizedSetTD`(495), `ua_collectTiles`(722), `ua_packTiles`(819),
`ua_applyTiles`(890), `ua_run`(922).
Вход: выделенные объекты/MatID, UV channel, flatten settings, размеры/gap.
Выход: изменённые UV/модификатор и раскладка. IDs переводятся через `(matID-1)%10`
и `floor((matID-1)/10)`; выбран канал1, функция может convertToPoly.

Решение: **обернуть адаптером**, **prototype**, DT-012/013/014. Не переписывать
раскладчик до теста этой реализации. Сохранить исходные UV/MatID, вынести параметры
и snapshot selection; проверить sparse IDs, границы плиток, units.SystemScale,
cross-tile faces, texel density и padding. Фактическое подключение этой копии
в активное меню не установлено.

### 3. Poly Actions Copy: повторяемые операции по фасаду — MAX-32

Файл `Andrew_scripts\Poly Actions Copy_V6.ms`; внутри UI **v7.6.0**, так что
имя V6 не является надёжной версией. Записывает extrude/inset/MatID/connect и
выбор групп, строит локальные frames, сохраняет backup/restore и `.pac` presets.
Это кандидат для повторяющихся элементов DT-030–032, не готовая реконструкция окон.

Решение: **доработать**, **prototype**. Разделить запись действий и применение,
принимать проверенный declarative action list. Импорт `.pac` на стр.765 использует
`execute(readLine f)` — файл является исполняемым вводом. Агенту нельзя считать
его безопасным JSON-пресетом. Проверки: разные ориентации групп, изменение topology,
неполное совпадение, rollback и сохранение stable IDs.

### 4. Zavod scene census и FBX inventory — MAX-36 / GEN-13

`scripts\scene\agr_inspect_max.ms` уже собирает JSON с файлом сцены, Max/renderer,
units, bbox, объектами, instance groups, material names, missing maps, pivots.
`scene_load_report.ms` — геометрические количества по слоям и тяжёлым объектам.
Сцену эти просмотренные пути не редактируют, но census перезаписывает свои
фиксированные temp JSON. Нужны job-specific output и привязка к PID/scene identity.

`scripts\fbx\inspect_fbx.py` читает binary/ASCII FBX без Max и SDK, возвращает
версию/формат, модели/родителей, материалы и дубли имён. Это metadata parser,
не проверка UV, ERM, normals или полного geometry round-trip. CLI без `-o` пишет
JSON рядом со входом; адаптер должен всегда выбирать свою output-папку.

Решение для обоих: **обернуть адаптером**, **prototype**, DT-020/021/022.
В этом проходе не исполнялись. Историческая отладка FBX-runner не является
свежим успешным тестом. Max UI export/prepare отдельно может менять меши.

### 5. Сбор карт: есть две основы, но обе нужно ограничить — MAX-35 / MAX-37

`collect_asset_v2.099b.mzp` содержит открытый `collect_asset_2.099.ms`:
`getAssetFiles`, `getAssetFilesSelected`, `getXrefAsset`, `getFileHash`,
`collect_as`, IFL/point-cache обработку, Corona/V-Ray/proxy/renderer assets.
Это значительно шире простой переборки Bitmaptexture. В том же UI есть relink,
сохранение сцены, удаление файлов и `rmdir /S /Q` для временных каталогов.
Решение: **обернуть адаптером только выделенное чтение/сбор**, **prototype**.
Не вызывать весь installer/UI/archive action как непрозрачный exporter.

В zavod: `optimizer\collect_scene_maps.ms` умеет уникальные назначения и
`_manifest.txt`; `g_collectMapsDryRun` по умолчанию **false**, Environment по
умолчанию **false**. `audit_scene_maps.ms` помимо отчёта предлагает удаление.
`zavod_lib_proxy.ms` действительно перезаписывает `.cgeo` через временный файл
и backup; запуск в read-only инвентаризации недопустим.

Для DT-012/022 переиспользовать manifest/dedup, но отделить discovery от copy/relink
и delete. Проверять одинаковые basename с разным содержимым, missing assets,
environment, IFL, абсолютные пути и повторное чтение экспортного пакета.
Proxy/pipe LOD вынесены в MAX-38: **изучить на тестовой сцене**, не ставить в сборку
по умолчанию. `pipe_to_cylinder9.ms` использует PCA/эвристики; 9 сторон — решение
конкретного инструмента, не требование PDF.

## Что нельзя считать готовой проверкой

### Collizii.ms — MAX-33

`checkPreciseIntersection`(144–161) после bbox overlap получает два snapshot mesh,
удаляет их и возвращает `true`; проверки треугольников между ними нет.
`isConvex`(352–398) использует фиксированный допуск0.001 и возвращает true при
<4 vertices/faces. Это не полный тест замкнутой выпуклой UCX-оболочки.
Решение: **заменить точную проверку** в агентском workflow существующим
геометрическим checker с независимыми тестами; bbox оставить только broad phase.
DT-021/033, **prototype**. Это вывод чтения кода, не runtime-испытание.

### UDIM Viewer_V1.2.ms — MAX-34

Заголовок внутри говорит v7.4. `detectChannelType` узнаёт ERM/ORM (43–45),
но `case chType` назначения карт(257–275) не содержит этих веток.
Поэтому «нашёл ERM файл» здесь не означает «подключил ERM».
`extremeAssignIDs`(108–162) convertToPoly, назначает MatID по среднему UV грани,
прижимает отрицательные UV к нулю. Пересечение границей UDIM этим не проверяется.
Это изменяющий материал/геометрию preview, не read-only инспектор.
Решение: **доработать**, **prototype**, DT-013: explicit channel mapping/Non-Color,
normal convention, сохранение IDs и проверка каждой вершины против границ плитки.

### ClearCustomAttributesAndObjProp_010.ms — MAX-39

В UI(587–598) по умолчанию включены очистка material CA, user properties,
vertex channels и animation keys; extra map channels2+ выключены. Это может
удалить provenance/ID и другой нужный экспортный контекст. **Доработать**: allowlist
того, что снимается с экспортной копии, затем readback. Не использовать как общий
«исправить всё» шаг. Ранняя версия001 — отдельный вариант, не доказанный дубль.

## Дополнительные кандидаты и дубликаты

- **MAX-40 rapidTools:** 31 макрос MZP побайтово совпал с `C:\usermacros`.
  Есть mesh cleanup, quad/ngon, panelizer, conform, OBJ exporter. Главные операции
  в MSE, установленный макрос сам по себе не доказывает наличие/работу kernel.
  **Изучить на тестовой сцене**, DT-030/033; installer не выполнялся.
- **MAX-41 замена объектов/дверей:** `Andrew_scripts\Zamena_V2.ms` переносит world
  transform при замене по имени; `zavod\scripts\doors\place_box001_on_doors.ms`
  привязан к `Box001` и шаблону имён дверей. **Доработать** под WindowType/approved
  manifest, ID и clone-only output; размеры не брать из выдуманного шаблона.
- **MAX-42 Road Markings Generator:** три MZP побайтово одинаковы. MSE и macro
  совпадают с установленными в Max2024. **Изучить на тестовой сцене** для Ground;
  наличие не подтверждает использование командой. Дубли не удалялись.
- `H_instancer-1.0.mcr` и копия в `developer_tools-h_instancer-1.0` — точный дубль.
  Остальные две группы loose-file SHA относятся к пустым `__init__.py` и generated
  assembly attributes; их нельзя представлять как найденные лишние инструменты.
- UVTools3.2m macro совпал с установленным,3.3.05 отличается: более новый архив
  не означает обновлённую установку. Версия основного runtime этим не определена.
- Copitor имеет кнопку Octopus(416/422) и установленную копию v3 с тем же SHA;
  v1.61/v2/v2.3 в `Previous_versions` — варианты, не точные дубли v3.
- ArchViz Tools содержит541 `.max` и множество
  MSE. Окна/двери, billboard, backdrop, разметка — кандидаты ассетов, но не источник
  размеров реального ОКС. В Billboard Generator виден текст MS с обфусцированными
  именами и зависимостями Corona/V-Ray; не считать его прозрачным готовым API.

## Что изменено в плане Digital Twin AI

Следующая задача остаётся **INT-001**. В неё добавить xView native findings
и разделение `pass / fail / error / not_run`; индексы Max нормализовать явно.
Переиспользовать census/FBX inventory как входной inspect, не писать его заново.
INT-003: сначала MatID→UDIM/texel density из Maf Tools и безопасный asset manifest;
ERM preview UDIM Viewer требует исправления, его нельзя брать как эталон.
INT-005: оценить action replay/замену по данным утверждённого реестра.
INT-006: исключить Collizii precise из доказательств приёмки; объединить подходящие
xView/GeoAGR/SINTEZ findings, отдельно проверить gaps, containment и coverage.

Все новые производственные workflow — **prototype**. Пустые Skills не создавались.
Основной код проекта/нормативные профили не менялись. Готовность DCC и реального
пилота не повышена. Для статического этапа не нужен запуск рабочего ОКС.

Вопросы на будущее: пользуется ли команда Maf Tools/PAC; какая копия UVTools
считается рабочей; разрешён ли перенос собственного кода Andrew/xView или нужен
только локальный адаптер. Они не блокируют подготовку независимых фикстур.
