# SYNTH-001

Продолжение: `../../STATE.md`. Код: `8f58339745574f3c5a668b8120e21e293a742f29`.
Профили NPM/VPM 0.1.0, schema 1.0.0. Хеш PDF — `project.json`.
Хеш определения синтетики — `project.inputs.fixture-definition.json`.

Цель выполненного среза: общий утверждённый тестовый реестр → атлас НПМ и
две плитки ВПМ → реальные FBX → read-back и отчёт. Это не реальный ОКС.

Сборка:
`dt build --job jobs/SYNTH-001/project.json --blender <blender.exe>`.
Выходы в `outputs/` игнорируются Git. C001–C004 pass при Blender 4.4.0,
33 теста прошли. Без Blender C004 not_run; delivery passed=false всегда.

Следующее: DT-020, инспектор нормативных пакетов отдельно от dev-bundle.
