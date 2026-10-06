# Наружная поверхность — параметризованный прототип

Ядро `src/dt_ai/geometry/exterior.py::extract_exterior` принимает подготовленную
измеренную сетку owner/x/y/z/angle и явно выбранные окна в локальных координатах.
Возвращает наружные квады, профили, проёмы, индексы фасадов и исходных стен.
Прямоугольные участки выделяет `geometry/grid_patches.py`; файлового I/O в ядре нет.
Старые tools/build_exterior_surface.py и compact_floor_body.py совместимы.

## Контракт

Задание: `jobs/OBR22-K02/exterior-adapter.json`. Пути grid_npz, source_json,
owner_registry_json относительно задания; окна выбираются по явному window_ids.
Отсутствующий/неоднозначный ID — ошибка. Отбор по имени102_Окно остаётся только
в старом входе Обр22, не в новом адаптере.

Параметры: units=m, height_m, height_basis, coordinate_budget_m,
microgap_closure_m, opening_match_m, window_plane_distance_m, wall_top_policy.
Основания выбора/допусков: selection_basis и tolerance_basis. Наличие ссылки не
проверяет её истинность. Значения Обр22 не являются нормой следующего здания.

Политика extend_to_height_record_unmatched_top_gaps воспроизводит старую логику:
наружный фасад до заданной высоты; разрывы у верха стены без соответствующего
оконного ID записываются в excluded_wall_top_gaps, не становятся новыми окнами.
Высотное допущение сохранено, новая версия требует рассмотрения человеком.

Поддерживается одна ортогональная внешняя граница, локальный пол z=0. Дворовые
фасады не строятся; несколько компонентов/наклонные фасады не поддержаны.
source_ids — индексы владельцев сетки; их связь с Revit требует входного реестра.
Реестр сохраняется ссылкой/хешем; полнота семантического сопоставления не доказана.
Это не live RVT-import: построение исходной сетки занятости остаётся отдельным шагом.

## Воспроизведение

Требуются локальные измеренные входы из ignored outputs, NumPy/Shapely и Blender4.4.
Каталог v001 уже создан; для повторного запуска выбрать новый каталог.

```powershell
.venv/Scripts/python.exe tools/run_exterior.py --config jobs/OBR22-K02/exterior-adapter.json --output jobs/OBR22-K02/outputs/exterior-adapter-v001
& 'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/exterior_adapter_blender.py -- jobs/OBR22-K02/outputs/exterior-adapter-v001
& 'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/exterior_adapter_blender.py -- jobs/OBR22-K02/outputs/exterior-adapter-v001 --check
.venv/Scripts/python.exe tools/check_exterior_surface.py jobs/OBR22-K02/outputs/exterior-adapter-v001
```

Выход: exterior-surface.npz/json, EXTERIOR_SURFACE.blend, inputs.json с хешами,
geometry-qa.json, exterior-readback.npz, exterior-qa.json, exterior-surface-check.json
и report.json. Последняя команда обновляет DCC-свидетельство отчёта, не снимая
ручные ворота. Геометрические данные остаются в файлах, в контекст идёт сводка.

Shell не входит в этот пакет. Его конфигурация, ядро и Blender-readback должны
публиковаться и проверяться отдельно после Exterior. Существующий output и
принятые файлы не перезаписываются.

## Проверки переноса

- 357 квадов,40 фасадных участков. Массивы NPZ, профили, контур, проёмы,
  высотные резы и исключённые верхние разрывы точно равны прежнему результату.
- Blender4.4 сохранил/прочитал сцену: нет неправильных нормалей, лишних координат
  разрезов или заполнения проёмов. Разница площадей профилей0;
  численный overlap3.64e-14м² ниже порога1e-8м².
- Итоговые команды, SHA базы/head и фактические результаты текущего PR записываются
  в его описание и `STATE.md`; старые числа из локального прототипа не используются
  как доказательство опубликованного пакета.

Проверен один реальный объект и синтетические рисковые случаи, не второй проект.
Визуальная приёмка нового выхода открыта, delivery=false. Далее: отдельно Shell,
затем окна/инстансы.
