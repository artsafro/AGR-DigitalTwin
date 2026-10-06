# ГЛБ — подключение SketchUp MCP — read-only v001

## Оценка пользователя
- 29.09.2026: «отлично, переходим к задаче» после подтверждения подключения.
- Принято подключение и чтение исходника; это не приёмка НПМ, UV или геометрии.

## Задача и входы
- Две башни из `C:/Users/artsafro/Downloads/ГЛБ для НПМ.skp`, SketchUp2026.
- Нужны анализ силуэта/геометрии, типовой этаж, атлас исходных материалов, НПМ.
- Стилобат вне моделирования. Работа без Computer Use по прямому уточнению.

## Что сработало и что пришлось исправить
- Python stdio MCP + Ruby TCP-мост localhost, версии согласованы handshake.
- Полный upstream отклонён auto-review из-за arbitrary Ruby по умолчанию.
- Установлен ограниченный вариант: dispatch разрешает только чтение; реализации
  eval/экспорта/редактирования удалены. Установка разрешена автоматической проверкой.
- Пользователь остановил Computer Use; загрузил расширение сам одной Ruby-командой.
- После этого чтение через API работает без UI. Автозапуск пока не настроен.
- Официальный облачный коннектор Trimble v1 не заменяет чтение существующего SKP.

## Воспроизведение
- [Адаптер](../../adapters/sketchup/README.md), prepare_readonly.py, probe_readonly.py.
- Upstream zinin/sketchup-mcp2, commit caf3d0b2532d6cf058f94f2ea3904f61257c8e7f.
- В Ruby: `require File.join(Sketchup.find_support_file('Plugins'), 'mcp_for_sketchup.rb'); MCPforSketchUp::Core::Application.start`.
- Команда проверки из корня: `adapters/sketchup/.venv/Scripts/python.exe adapters/sketchup/probe_readonly.py`.
- vendor/venv/dist/verification локальные ignored; исходник в Downloads не в Git.

## Проверки и доказательства
- 29.09.2026: `adapters/sketchup/verification/20260929T065929Z/report.json`, viewport.png.
- Handshake, model path, 14 root entities, 27 layers, 34 материала; снимок прочитан.
- SHA256 дискового SKP в отчёте, не является хешем несохранённой live-сцены.
- 182 upstream Python-теста пройдены раньше, не заменяют тест ограниченного Ruby.
- Полная геометрия/UV/извлечение пикселей текстур и экспорт ещё не проверены.

## Переиспользование
- Один live-кейс, оставить адаптером. Универсальный Skill не объявляется.
- Следующее: ограниченные команды чтения геометрии/UV и извлечения исходных текстур.
- Сравнимый опыт моделирования: OBR22_ACCEPTED_WORKFLOW.md; другой источник Revit.

## Сохранение
- Запись локальная, без коммита/push, база d7ecdfd. Реестр и STATE обновляются.
