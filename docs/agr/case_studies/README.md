# Реестр опыта AGR

- ГЛБ: [A_Main](GLB_A_MAIN_ATLAS.md) и [B_Main](GLB_B_MAIN_ATLAS.md):
  положительная оценка текущей сцены; [Python-пакет](../../technical_library/glb_atlas/README.md)
  воспроизводит карты, но не неизвестные правки A v005. FBX/Checker открыты.


Перед сходной задачей читай релевантный кейс и проверяй его область приёмки.
Похвала пользователя, успешный тест и публикация файла — разные статусы.
Новый кейс оформляй по [шаблону](TEMPLATE.md) и
[правилу фиксации](../EXPERIENCE_CAPTURE.md).

- Декоративные рамки: [box lights v002](WINDOW_FRAMES_BOX_LIGHTS.md) — принята
  раскладка на этом узле; 247 новых секций, native readback и hash локального
  `.blend` проверены. UV, FBX, Checker и второй объект не проверены.
  [Скрипты и запуск](../../jobs/WINDOW-FRAMES/README.md).
- Обр22: [принятый рабочий процесс](OBR22_ACCEPTED_WORKFLOW.md) ([PR #4](https://github.com/artsafro/AGR_Project/pull/4)) — приняты геометрия,
  масштаб материалов, НПМ v012 и UV ВПМ v011; полная сдача ОКС не подтверждена.
- ГЛБ: [ошибка упрощения составного окна](../lessons/SKETCHUP_COMPOSITE_WINDOW_OPENINGS.md)
  ([PR #2](https://github.com/artsafro/AGR_Project/pull/2)) — урок отклонённого
  результата, не приёмка модели и не разрешение продолжать моделирование.
- Ground, MASHI, Facades: [кейсы и границы приёмки](CASEFILE_INDEX.md)
  ([PR #16](https://github.com/artsafro/AGR_Project/pull/16))
  — частичные результаты и ошибки; ignored outputs остаются локальными.
- REVIT-OPENINGS: [статус пилота СОШ1150](../../jobs/REVIT-OPENINGS/STATE.md)
  ([PR #19](https://github.com/artsafro/AGR_Project/pull/19))
  — пилот с открытой визуальной приёмкой.

После слияния соответствующих PR связывай кейсы по постоянным путям в репозитории.

- СОШ1150: [непрерывный рисунок стен и FBX v006](SOSH1150_CONTINUOUS_WALL_UV_FBX.md)
  — принят UV/рисунок и подготовленный пакет, native Max не подтверждён.
  [Исполняемый маршрут и математическая логика](../../technical_library/UV_V006.md).

Рабочая логика сворачивается в пакеты операций в
[технической библиотеке](../../technical_library/README.md). Временные версии
остаются локально; ошибки сохраняются как контрпримеры, не готовые инструменты.
