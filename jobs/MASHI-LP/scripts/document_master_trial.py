import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3];job=root/'jobs/MASHI-LP';out=job/'outputs/master-v001'
qa=json.loads((out/'readback.json').read_text());cross=json.loads((out/'intersections.json').read_text());td=json.loads((out/'density-readback.json').read_text())
count=sum(o['faces'] for o in qa['objects']);unknown=sum(o['material_counts'].get('17',0) for o in qa['objects']);over2=sum(o['edges_more_than_two'] for o in qa['objects'])
assert Path(qa['file']).name=='MASHI-comparison-trial-v002.blend'
report=f'''# MASHI — независимый пробный master, 27.09.2026

**Статус: TRIAL, QA NOT PASSED. Запрос выполнен как опыт построения; чистовой
редактируемый master с корректными сопряжениями НЕ завершён.**

Открыт и повторно прочитан файл
`outputs/master-v001/MASHI-comparison-trial-v002.blend`.
Коллекция `MASTER_Revit_v001`, смещение +100м X. LP v002 рядом сохранена;
подписи всех59 исходных объектов совпали (геометрия, матрицы, индексы материалов, UV).
Нового коммита/push нет; база d7ecdfd, feature/revit-typical-floor.

## Что построено

- Независимая сетка по наружным контурам Revit; пользовательская LP не копировалась.
- Семь групп: body, walls, roof, profiles, frames, glass, spandrels.
- {count} квадов / {count*2} расчётных треугольников.
- 233 декоративных профиля собраны по сечениям/проекции контура; упрощение
  контура8мм — выбранный бюджет этого опыта. Не доказана общая точность поверхности
 8мм: соединение сечений и огибающие требуют отдельного сравнения с источником.
- 659 наружных стеклянных панелей исходника; рамы по их контурам. Сечение упрощено:
  лицевая полка40мм, глубина80мм, стекло утоплено35мм, захват края10мм.
  Это проектное упрощение по повторяющимся размерам LP_old, не обмер каждого профиля.
- Крупные глухие стены с откосами0.4м внутрь; задние внутренние поверхности не добавлялись.
- ID материалов и `source_patch` на гранях. Названия материалов взяты из LP_old;
  пространственное соответствие — предложение, не подтверждённая ведомость отделки.
  {unknown} граней имеют ID18_UNRESOLVED. Полный mapping: `material-provenance.json`.
  BIM ElementId в импорте отсутствует: сохранены имена объектов и индексы граней,
  а не выдуманные Revit ID. При восстановлении профиля связь дана на компонент.

## Проверка фактического файла

`readback.json`:100%quad;0 вырожденных граней,0 точных дублей,0 свободных рёбер,
0 найденных T-стыков при20мкм. Это **не** проверка всей сетки на корректность.
Остаются {over2} рёбер с более чем двумя соседними гранями. Открытые границы
фасадных оболочек/рам ожидаемы частично; намеренность каждой границы не подтверждена.

`intersections.json`: {cross['coplanar_count']} пар частичных coplanar-наложений
при допуске2мм и площади>0.00001м². Сумма площадей пар
{cross['coplanar_area']:.3f}м² — не уникальная площадь дефектов.
{cross['crossing_counts'].get('review',0)} пересечений внутренностей граней требуют
разбора; это не автоматически столько же дефектов: часть может быть конструктивным
врезанием. Допуск проверки: исключены3мм у границ, длина пересечения>20мм.
Ещё {cross['crossing_counts'].get('designed_10mm_glass_capture',0)} пар glass/frames
помечены как ожидаемый10мм захват стекла по конструкции; это не независимая
проверка глубины каждого стыка. Врезание рам в BODY отдельно не подтверждено.
Финальный Attach, полная проверка нормалей/перекручивания и замкнутости не выполнены.

## Нарезка и диагностическая UV

Connect сохраняет квады; максимальная сторона<3.8м. После дополнительной нарезки
проекционный размер каждого диагностического острова<3.8×3.8м.
`TD_1024_TEST`: проверка для4096px, ориентир1024px/м, отступ32px.
По сохранённым UV нет выходов за тайл с отступом. Но34 грани на двух профилях
не входят в512–1706px/м; минимум около231px/м вследствие сложных/перекрученных
сопряжений сечений. Их нельзя исправлять одним масштабом UV вместо геометрии.
Проблемные source_patch:2666 (Material #200),2698 (Material #230).
Полный список: `density-readback.json`. Требование «всё нарезано под TD» пока
не выполнено полностью. Это не производственная развёртка: не проверены фаза
отделки, зеркала, общий рисунок, финальный атлас/UDIM; карты не созданы.

## Неудачные подходы и следующий локальный шаг

Отбор только видимых треугольников дал разрывы; заменён восстановлением целых
контуров. Простое укрупнение Revit-треугольников усложняло сетку; для профилей
заменено новым loft по сечениям. Он восстановил общий объём, но на двух стойках
сопоставление углов сечений требует ручной/адресной коррекции. Полные плоскости
Revit также принесли дублирующиеся перекрывающиеся участки: их необходимо
перестроить как единую наружную поверхность, а не только удалить точные дубли.

Дальше: сначала два проблемных профиля, затем общие контуры BODY/стен/вставок,
удаление частичных наложений, измеренные сопряжения рам с BODY, повторный QA.
Не использовать этот опыт как универсальный автоматический Revit-моделер.

## Воспроизведение и регрессия

Основные скрипты в `scripts/`: extract_master_glass, prepare_master_windows,
prepare_master, loft_master_profiles, build_master, finalize_master_trial,
load_master_live, clean_master_live, verify_master, check_master_intersections,
check_master_density. Скрипты исследования/забракованных подходов сохранены
для трассировки; не запускать все подряд поверх результата. Outputs ignored.

27.09.2026:97passed/1skipped; dt profiles check3OK; dt schemas --check8OK.
Synthetic dt build: `outputs/synthetic-check-master`, development=true,
delivery=false. Эти проверки относятся к инструментам, не подтверждают качество
данного здания. Context7 использован для Blender API, проверялось в Blender4.4.

Превью: `outputs/master-v001/LP-and-MASTER.png`, `MASTER-A.png`,
`MASTER-B.png`, `MASTER-frame-detail.png`. Нативный screenshot получился чёрным
(окно недоступно для захвата); сравнение подтверждено рендером сохранённого файла.
'''
(job/'MASTER_TRIAL_REPORT.md').write_text(report,encoding='utf-8')
manifest=json.loads((job/'FILE_MANIFEST.json').read_text());manifest['master_trial_status']='QA NOT PASSED; visual acceptance pending'
for relative in ['outputs/master-v001/MASHI-comparison-trial-v002.blend','outputs/master-v001/LP-and-MASTER.png','outputs/master-v001/readback.json','outputs/master-v001/intersections.json','outputs/master-v001/density-readback.json']:
 p=job/relative;manifest['files'][relative]=dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(job/'FILE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(dict(quads=count,unknown_id_faces=unknown,over2_edges=over2,report=str(job/'MASTER_TRIAL_REPORT.md')))
