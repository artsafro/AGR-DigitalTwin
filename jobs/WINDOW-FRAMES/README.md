# Box lights на декоративных рамках

Рабочий сценарий Blender 4.4 для одного проверенного источника. Создаёт отдельный
меш по верхним внутренним поверхностям рамок: native inset, открытая оболочка,
выравнивание неплоских оснований с дополнительным опусканием. Размеры взяты
из образца. [Кейс и границы приёмки](../../docs/case_studies/WINDOW_FRAMES_BOX_LIGHTS.md).

## Состав

- `inspect_lights_live.py` — читает геометрию/нормали исходной сцены в JSON;
  несмотря на историческое имя, работает в background Blender.
- `analyze_lights.py` — связанные компоненты и отбор верхних внутренних граней.
- `build_box_lights.py` — native inset, планарность, открытая оболочка и provenance.
- `check_box_lights.py` — readback геометрии/материалов исходников, provenance,
  свойств результата, планарности и BVH surface-intersections.
- `evidence/readback-v002-summary.json` — компактная историческая проверка;
  `evidence/replay-2026-10-01.json` — проверка опубликованного сценария.

## Вход и запуск

Нужен локальный `box_light_source_v001.blend`: два меша `frames` (3118 вершин,
2352 грани) и `box_light` (8 вершин, 5 квадов), scale_length=1. Клон Git содержит
код и отчёты; исходная сцена хранится локально. Python: стандартная библиотека;
`bpy`, `bmesh`, `mathutils` поставляются с Blender. Установка pip для них не нужна.

В PowerShell задайте `$blenderExe` — путь к Blender 4.4, `$sourceBlend` — путь
к исходной копии. Запускать из корня репозитория, каждый раз с новым каталогом:

```powershell
$env:AGR_BOX_LIGHT_OUTPUT = Join-Path (Get-Location) 'tmp/box-lights-replay-new'
$scripts = 'jobs/WINDOW-FRAMES'
& $blenderExe --background $sourceBlend --disable-autoexec --python-exit-code 1 --python "$scripts/inspect_lights_live.py"
if ($LASTEXITCODE) { throw 'Inspection failed' }
python "$scripts/analyze_lights.py"
if ($LASTEXITCODE) { throw 'Selection failed' }
& $blenderExe --background $sourceBlend --disable-autoexec --python-exit-code 1 --python "$scripts/build_box_lights.py"
if ($LASTEXITCODE) { throw 'Build failed' }
$resultBlend = Join-Path $env:AGR_BOX_LIGHT_OUTPUT 'frames_box_lights_v002.blend'
& $blenderExe --background $resultBlend --disable-autoexec --python-exit-code 1 --python "$scripts/check_box_lights.py"
if ($LASTEXITCODE) { throw 'Readback failed' }
```

Сценарий отказывается перезаписывать исходный audit, результат или readback;
не запускать build на уже обработанной сцене. Живая сцена для этого маршрута не нужна.

## Что адаптировать для другой задачи

Имена мешей, счётчики, исключение грани образца1081, размеры inset/drop/height,
normal.z<-0.1 и отбор верхней половины компонента — параметры этого источника.
Не менять их автоматически для другой модели. Сначала измерить новый образец,
проверить отбор и собрать отдельный trial. Доказательств на втором объекте нет.
Сценарий не добавляет shader, источники света, UV или FBX. BVH проверяет
пересечения поверхностей секций, а не все вложенные объёмы. delivery_passed=false.

01.10.2026 опубликованные скрипты прогнаны на сохранённом источнике и отдельном
output: 247 новых секций/1235 квадов, исходники неизменны, warped quads0,
surface-intersections0, все четыре команды exit0. Это новый native readback;
повторная пользовательская визуальная приёмка не проводилась. Context7 недоступен.
