# Стены СОШ1150 — UV1500, 01.10.2026

## Пользовательская приёмка — 01.10.2026

«спасибо, молодец, успех» после выдачи FBX/ZIP. Принят результат этапа
UV/рисунка стен v006 и подготовленный FBX-пакет. Native Max-import пользователь
отдельно не подтверждал; полный ОКС/полный Checker не приняты автоматически.
Версии/фактические SHA256: ACCEPTED_V006.json; outputs сохранены.
Кейс: docs/case_studies/SOSH1150_CONTINUOUS_WALL_UV_FBX.md, реестр обновлён.
База d7ecdfd, локально без коммита/push. Отчёты readback прочитаны повторно,
хеши файлов вычислены заново; DCC/тесты сейчас не повторялись.
Этап закрыт в указанной области. Следующий шаг — только новый запрос;
сценарий остаётся кандидатом на адаптер до проверки на втором проекте.

## FBX для самостоятельного импорта в Max — 01.10.2026

outputs/FBX_For_Max_v006/Walls_FlipH_v006.fbx и отдельный PNG;
архив outputs/Walls_FlipH_v006_FBX_For_Max.zip. FBX7400, Zup,
FBX_SCALE_UNITS; геометрия/UV сохранены, diffuse embedded и внешний.
Экспорт в отдельном background Blender из сохранённого v006; живая сцена
и исходный blend не изменены. Материал экспорта — один Principled diffuse.
Повторный Blender import:47800вершин,42686квадов,1UVchannel/1material,
UV max error0.0, world max error9.78e-6м, Mesh.validate repairs=false.
Встроенные байтыPNG/привязка diffuse проверены, SHA совпал с исходной картой.
ZIP прочитан обратно, состав/байты совпали. Отчёты FBX_READBACK.json,
PACKAGE_QA.json. Команды: Blender --background --factory-startup --disable-autoexec
--python-exit-code1 --python scripts/export_max_v006.py;
.venv/Scripts/python.exe scripts/package_max_v006.py.
Нефатальное extensions-cache warning не повлияло на export/import(exit0).
Native Max import не проверен: пользователь запросил файл для самостоятельного
импорта. Глобальные проверки этого UV-этапа116passed/1skipped,profiles3,schemas8,
SYNTH development=true/delivery=false; код ядра при FBX упаковке не менялся.
Полная приёмка ОКС не заявлена. Следующий шаг — импорт пользователем в Max.

## Актуальная версия v006

Последнее уточнение пользователя: разрешён диапазон550–1500px/м;
нужно укрупнить плитки/белые линии и горизонтально отразить рисунок, быстро.
Файл outputs/walls_UV550-1500_FlipH_v006.blend открыт в Blender.
47800вершин,42686квадов,1001,20px padding. Native TD550.921–614.890,
по граням551.047–614.881;0вне диапазона. Mesh.validate repairs=false,
loose vertices0,рёбер>2faces0;original/packed diffuse SHA совпал с новой картой.
Поверхность5124.33599082м² против исходных5124.33602894м² (float32).
Native closest-point distance diagnostic max0.160мм.

Вместо фиксированного1500 решена система фаз45charts/52corner constraints:
горизонтальные масштабы0.8439–1.0502 при базе600px/м, вертикальный масштаб600.
Это допустимая местная подстройка в новом диапазоне, не изометричная развёртка.
Прежние14конфликтов замыканий устранены. На сохранённом файле проверено159584
endpoint samples общих рёбер вертикальных стен: max phase error0.0127px,
samples>0.1px0. Горизонтальные20soffit faces не входят в проверку вертикальной
фазы. Проверка установленного AGR TD/UV margin:0/0/0 failures.

Карта T_Template_Address_001_Diffuse_FlipH_v005.1001.png:4096²,
3колонки/8рядов кассет,8белых горизонталей/2диагонали; отражён native
редактируемый процедурный источник F1, wrap-padding20px. Проверены пары
пикселей на обоих периодических краях, включая bilinear sampling.
ImageGen был вызван для edit-study по исходной карте: horizontal mirror,
3x zoom, сохранить grey panels/white stripes, seamless opposite edges,4096².
Проба exec-db2cc284-d601-4e9a-85db-e55b5f7985b6.png не применена: она меняла
число линий и не подтверждала периодичность. Финал собран существующим native
editable texture generator (build_final_texture.py), не выдан за ImageGen-файл.
Фактическое увеличение рисунка≈2.5–2.9 к UV1500, не строго3.0.

Команды: scripts/closure_final.py → final_plan.py → build_v005.py;
scripts/build_final_texture.py;live_call.py scripts/apply_v006.py;
live_call.py scripts/render_v006.py;Blender4.4 --background --factory-startup
--disable-autoexec --python-exit-code1 --python scripts/readback_v006.py.
Отчёты: readback_v006.json,agr_scoped_v006.json,texture-v005-qa.json.
Native render walls_view_v006.png осмотрен. Без Computer Use.
v005 исправлена: повторная проекция почти плоских вертикальных triangles
вызывала35ошибочных UV endpoint samples;v006 оставляет общий chart mapping.
Предыдущие версии сохранить для диагностики, не использовать для сдачи.
Полная ручная приёмка/AGR всего ОКС не заявлены;delivery_passed=false.
Следующий шаг — визуальная оценка пользователя.

---

Статус: TRIAL / задача полной непрерывности не закрыта. База d7ecdfd,
без коммита; исходные изменения репозитория не затрагивались.

Вход: живая несохранённая Blender4.4-сцена, PID57888, порт9876,
Object1746168144, 8755 граней; все material_index=0. Исходник сохранён
в outputs/source_v001.blend. Diffuse4096 из прямого пользовательского пути.
Входная плотность: медиана585.143px/м, не1500.

Результат: outputs/walls_UV1500_TRIAL_v004.blend, открыт в живой сцене.
59383квада,65203вершины. Дополнительные разрезы по периодам texture repeat;
полигональные участки подразделены на квады с source_face provenance.
Diffuse не изменён; сохранена копия PNG, упакован в blend, SHA256 совпадает.
Основные фасады и показанный угол согласованы по фазе. Все UV находятся
в [0,1], намеренные наложения одного материала. Отступ от края0px.

Нерешённое: 14рёбер четырёх сложных замыканий с конфликтом горизонтальной
фазы. Список в outputs/plan.json и build.json. Простая жёсткая развёртка
с исходным паттерном и строго фиксированным масштабом не закрывает эти циклы.
Исследование линейной подстройки charts не дало допустимой малой деформации;
closure-study.json — только исследование, не применено. Малую подстройку
плотности спросили у пользователя; ответа нет. Не считать отсутствие ответа
разрешением на существенную деформацию. Полная визуальная приёмка открыта.

Проверки:
- .venv/Scripts/python.exe jobs/UV-CONTINUOUS/scripts/audit.py:
  проектные UV1499.998–1500.000px/м, поверхность5124.33602877м²;
  исходная5124.33602894м², max parent area error9.58e-8м².
  0дублей/вырожденных граней/выходов из тайла.
- Blender --background --factory-startup --disable-autoexec
  --python-exit-code1 --python jobs/UV-CONTINUOUS/scripts/readback.py:
  exit0,59383квада,0loose vertices,0рёбер>2faces,Mesh.validate repairs=false,
  packed diffuse hash совпал. Native float32: плотность по граням
  1497.420–1501.852; по skinny tessellation triangles1496.009–1502.453.
  Native closest_point_on_tri distance diagnostic до0.494мм;
  точная contour/topology certification вне этого прогона.
- Установленный AGR Checker CheckUtils._calculate_td({1001:4096},True):
  td_less0,td_greater0,margin_failures12196. Полный Checker не запускался.
- Native viewport OpenGL render сохранён в trial_view_v003.png для v004.
  Осмотрен основной угол; Computer Use остановлен по запросу пользователя,
  дальше только bridge/рендер/чтение файлов.
- pytest116passed/1skipped/1warning; profiles3OK; schemas8OK.
- dt build --job jobs/SYNTH-001/project.json --blender Blender4.4
  --output tmp/uv-continuous-synth-20261001:
  development_checks_passed=true,delivery_passed=false.

Предыдущие v002/v003 отклонены из-за5некорректных граней на почти совпавших
точках разрезов; v003 пропускал части поверхности. v004 устраняет эти
потери: дедупликация последовательных точек и сверка площади по source_face.
Не выдавать ранние файлы за результат.

Следующий шаг: согласовать приоритет на замыканиях, затем отдельно решить
14стыков и padding без заявления точного1500/отсутствия деформации заранее.
Полный результат delivery_passed=false.
