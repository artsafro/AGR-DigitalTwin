# BODY/Shell: адаптер проверенной наружной поверхности

Статус: prototype на Обр22, второй проект не проверен. Выделена операция
**наружная quad-сетка → Shell внутрь → наружные фейсы и откосы без inner faces**.
Вход формируется опубликованным Exterior-адаптером из `docs/EXTERIOR_ADAPTER.md`.
Оба адаптера пока проверены только на подготовленных данных Обр22: это не прямой
импорт RVT/FBX. Адаптер Shell не распознаёт произвольное здание и не строит окна.

## Вход и ручные решения

`jobs/OBR22-K02/body-shell-adapter.json`: отдельные пути surface_npz/profiles_json,
units=m, angle_rad, thickness_m, tolerance_m, body_name, surface_review_ref,
thickness_decision_ref. Пути относительно файла задания. Пустые ссылки на ручные
решения запрещены; их достоверность проверяет человек, наличие строки не является
автоматическим подтверждением. Новая версия результата требует отдельной приёмки.

NPZ: vertices, faces (квады), facade_indices (индексы профилей с1).
JSON: profiles/outward. Все входы читаются без изменения. 0.4м задано в конфигурации
Обр22, не скрыто в новом API. Один source_ref на исходную грань; откос хранит
исходную грань и граничное ребро. Отделка не угадывается: материал0 — нейтральный
BODY, не утверждённый материал. Прежние решения источника сохраняются в inputs.json.

## Исполнение

Ядро: `src/dt_ai/geometry/shell.py::shell_body`, чистая функция без DCC и записи файлов.
Старый `tools/build_shell_windows.py` вызывает её с прежними параметрами Обр22;
распознавание и построение окон не изменено.

Shell: для вершины решить систему смещений наружных плоскостей `N·delta=-thickness`
методом наименьших квадратов; соединить только граничные рёбра с внутренними.
Исходные наружные грани сохранены. Обратные внутренние грани не создаются.
Сохранена прежняя политика объединения координат с округлением до9 знаков.
Пока поддерживаются только вертикальные плоскости, ортогональные локальным осям.
Проверки входа: единицы, конечные значения, индексы, нормали, выпуклость/планарность,
дубли граней, nonmanifold-рёбра, несовместимые углы. Полная проверка пересечений
выполняется существующим `check_shell_windows.audit`, а не одной функцией Shell.

## Повторить

Зависимости: extra `contour-model`; Blender4.4 для DCC. Требуются локальные исходные
NPZ/JSON в ignored outputs, одного клона Git недостаточно. Для следующего прогона
указать новый каталог результата: существующий output не перезаписывается.

```powershell
.venv/Scripts/python.exe tools/run_body_shell.py --config jobs/OBR22-K02/body-shell-adapter.json --output jobs/OBR22-K02/outputs/body-shell-adapter-v001
& 'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/body_shell_blender.py -- jobs/OBR22-K02/outputs/body-shell-adapter-v001
.venv/Scripts/python.exe tools/check_body_shell_readback.py jobs/OBR22-K02/outputs/body-shell-adapter-v001
.venv/Scripts/python.exe tools/adapter_report.py jobs/OBR22-K02/outputs/body-shell-adapter-v001/report.json
```

Файлы результата: body-shell.json, inputs.json (параметры и хеши), qa.json,
BODY_SHELL.blend, blender-readback.json, blender-evidence.json, readback-qa.json,
report.json. Геометрические данные остаются в файлах; вывод — компактный.

## Предыдущая локальная проверка 27.09.2026

- Новый BODY полностью совпал с mesh BODY из `shell-windows-optimized.json`:
  вершины, грани, материал и имя;821 квад. SHA256 всех7 approved-файлов неизменны.
- Проверка геометрии до сохранения и по повторно прочитанной Blender-сцене прошла.
- Blender4.4.0 сохранил и повторно открыл отдельный BODY_SHELL.blend;
  максимальная ошибка координат1.8422e-6м, квады и происхождение сохранены.
- У Blender было предупреждение о кэше extensions; сохранение/readback завершились
  успешно с кодом0. Настройки пользователя не менялись.
- В отчёте оставлено ручное визуальное рассмотрение новой версии:
  required_checks_passed=false, delivery_passed=false. Никакой новой приёмки не выдумано.

Текущий PR проверяется заново от опубликованного Exterior-результата; его команды,
хеши и ограничения фиксируются в `STATE.md` и verification JSON. Далее — сквозная
сверка Exterior → Shell и отдельный пакет окон/инстансов. Не переносить на второй
проект значения/имена Обр22 без подтверждённых исходников и ручных решений.
