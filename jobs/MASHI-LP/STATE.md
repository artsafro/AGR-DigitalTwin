# MASHI — независимый пробный master, 27.09.2026

Текущий файл в Blender: outputs/master-v001/MASHI-comparison-trial-v002.blend.
MASTER_Revit_v001 стоит рядом (+100м X); все59 исходных объектов LP/Revit/LP_old
неизменны по подписям после повторного открытия. Мастер40 881quad,7 групп,
233 профиля,659 исходных стеклянных панелей и новые рамы. См. MASTER_DIRECTIVE.md.

Статус **TRIAL / QA NOT PASSED**, не завершённая модель. 0 точных дублей,
вырождений/T-стыков/свободных рёбер;110 рёбер>2 граней. Проверка нашла8851 пар
частичных coplanar-наложений,6703 пересечения для разбора (часть может быть
разрешённой врезкой). Диагностические UV: нет выходов за тайл,34 грани на двух
профилях не проходят TD. 3541 грань с ID18_UNRESOLVED. Полный состав/пороги:
MASTER_TRIAL_REPORT.md. Не выдавать этот файл за чистовой master или нормативную сдачу.

Команды: loft_master_profiles.py → Blender build_master.py/finalize_master_trial.py;
live_call.py load_master_live.py/clean_master_live.py; Blender verify_master.py
на фактическом comparison-trial-v002; check_master_intersections.py;
Blender check_master_density.py.97passed/1skipped, profiles3OK, schemas8OK;
synthetic-check-master development=true/delivery=false. Git d7ecdfd, без нового коммита.

Далее: корректное сопоставление сечений source_patch2666/2698; перестроить общие
наружные контуры BODY/стен/вставок без частичных наложений, проверить посадку рам.
Визуальная приёмка не получена. Файлы/хеши FILE_MANIFEST.json; outputs ignored.

## Сохранённый предыдущий этап — LP v002

База Git d7ecdfd, feature/revit-typical-floor; нового коммита/push нет.
Уточнение пользователя: простые поверхности/квады, сейчас без Shell.
См. MODELING_DIRECTIVE.md. Принят аудит/план v001, не готовая геометрия.

Открытый результат: outputs/model-v002/LP_working-v002.blend.
Добавлены 5 mesh/2710quad: дворовые стороны, оконные поля, кровля, площадки.
В LP 30mesh+Shape006 Empty; 5515 граней/12389 расчётных треугольников.
Все 54 исходных объекта неизменны по подписям. Revit26/LP_old2 скрыты.
Новые объекты локальные, выделены в Blender. Толщина/модификаторы не добавлены.

QA: повторное чтение рабочей версии, новые 100%quad; 0 дублей/вырождений,
рёбер>2 граней, найденных T-стыков, coplanar overlaps и пересечений внутренностей
в заданных допусках. Группы не сварены финальным Attach. Пороги и ограничения:
MODEL_V002_REPORT.md; readback-v002.json, overlap-check.json, crossing-check.json.
Грубое покрытие 84.62–87.23%, не нормативная готовность.

Команды: Blender --background input.blend --python scripts/build_v002.py;
verify_v002.py на LP_working-v002.blend; check_new_meshes.py/check_crossings.py.
97passed/1skipped; profiles3OK; schemas8OK. Synthetic dt build в отдельном
outputs/synthetic-check-v002: development=true/delivery=false.

Исходные160tri/162ngon и6 дублей Object032 сохранены. Мелкая детализация неполная,
оконные поля без толщины; UV/материалы/экспорт не выполнялись.
Далее: визуальная приёмка добавленных поверхностей, локальные правки.
Shell/Inset/финальное объединение — отдельный последующий этап.
Кейс принятого аудита: docs/case_studies/MASHI_LP_SCENE_AUDIT.md.
Outputs ignored: для воспроизведения нужен локальный каталог.
