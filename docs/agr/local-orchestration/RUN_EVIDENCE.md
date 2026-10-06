# Проверка сохранённого RunRecord

Перед продолжением агент читает job STATE, выбирает конкретный run_id и
manifest его попытки. Один существующий RunRecord используется повторно;
новый ledger, повтор DCC и второй inspector не создаются.

## Запуск и зависимости

Python3.11+, зависимости существующего AGR (`pip install -e .`).
Используются `AdapterReport`, `core.io` и `core.run_record` из этого репозитория.
Из корня checkout:

```text
python tools/harness_status.py --run <run-directory> --manifest <attempt/input-manifest.json>
python tools/harness_status.py --run <run-directory> --manifest <attempt/input-manifest.json> --report <AdapterReport.json> --required-check <id>
```

Идентификаторы обязательных checks берутся из задания/профиля, а не только
из самого отчёта. Входы остаются локальными; для проверки настоящего job нужны
его файлы, указанные абсолютными путями в manifest. Они не включаются в Git.
Команда читает файлы, печатает JSON и не записывает сцену/ledger, не запускает
процесс, не снимает lock и не разрешает retry. Skill
`.agents/skills/agr-run-evidence/SKILL.md` связывает этот вход с продолжением агента.

## Контракт и ограничения

Проверяются run_id/schema, связь manifest inputs/context с input fingerprint,
фактические размеры/SHA256 входов и stage outputs, список ожидаемых outputs,
привязка report/input manifest и состояния этапов. При пропаже/изменении evidence
предлагается расследовать расхождение и сохранить исходники; produced означает
проверку сохранённого результата перед повтором исполнения. Running — лишь запись,
живой PID или активная DCC-сцена этой командой не подтверждаются.

Набор согласованных файлов не является аутентифицированным доказательством.
Reported pass остаётся `reported_pass_unverified`; integrity не подтверждает
native/visual/manual checks. Записанный verified относится только к одному этапу.
Команда всегда возвращает `delivery_passed=false`.
Exit0: не обнаружены ошибки целостности, но pending gates могут остаться.
Exit1: найдено расхождение evidence; exit2: непригодный ввод/ошибка чтения.
Отчёт показывает первые5 ошибок и полное errors_total; не скрывает остальные.

## Проверка переноса

Собственная реализация перенесена из зафиксированного AGR source commit,
CLI сохранён; в inspector исправлен отказ на status-массив/объект,
добавлены два regression-теста; в skill исправлена ссылка на этот документ.
[Компактный QA и происхождение](RUN_EVIDENCE_QA.json) фиксирует версии и проверки.
Адресные tests используют синтетические временные файлы: produced/verified,
tamper/missing, running/interrupted, fingerprint, report binding и manual gates.
Они не доказывают DCC readback или полную сдачу модели. Существующий проектный
RunRecord не меняется. Panel/global installers/активный A/B research не перенесены.
Это read-only инженерная операция, а не универсальный моделирующий Skill.

Следующая задача: применять inspector к сохранённому этапу вместе с его
профильными проверками. Для настоящего native gate нужны отдельные свежие evidence.
