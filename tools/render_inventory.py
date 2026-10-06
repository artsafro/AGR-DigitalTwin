"""Render the reviewed local tool catalogue without touching installed tools."""
import argparse
import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/inventory'

def render(data):
    rows = data['tools']
    ids = [r['id'] for r in rows]
    assert len(ids) == len(set(ids)), 'duplicate tool IDs'
    assert all(r['paths'] and r['tasks'] and r['evidence'] for r in rows)
    assert all(p in data['path_evidence'] for r in rows for p in r['paths'])
    decisions = {'использовать как есть', 'обернуть адаптером', 'доработать', 'изучить на тестовой сцене', 'заменить'}
    assert all(r['decision'] in decisions for r in rows)
    esc = html.escape
    body = []
    for r in rows:
        fields = [('Назначение', r['purpose']), ('Основание', r['evidence']),
                  ('Зависимости', r['dependencies']), ('Исходный код', r['source_code']),
                  ('Границы и следующий шаг', r['limitations']), ('Копирование', r['copy_policy'])]
        details = ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in fields)
        paths = ''.join(f'<li><code>{esc(p)}</code></li>' for p in r['paths'])
        body.append(f'''<tr data-app="{esc(r['application'])}"><td><details><summary><b>{esc(r['id'])} · {esc(r['name'])}</b></summary><p>{esc(r['version'])}</p><dl>{details}</dl><ul>{paths}</ul></details></td><td>{esc(r['application'])}</td><td>{esc(r['status'])}</td><td>{esc(r['decision'])}</td><td>{esc(', '.join(r['tasks']))}</td></tr>''')
    opts = ''.join(f'<option>{esc(x)}</option>' for x in sorted({r['application'] for r in rows}))
    page = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Digital Twin AI — инструменты</title>
<style>body{margin:0;background:#f5f6f8;color:#1c2935;font:15px/1.5 system-ui}main{max-width:1500px;margin:auto;padding:32px}h1{font-size:28px;margin:0 0 8px}h2{font-size:20px}p{max-width:1050px}.note{border-left:4px solid #a56b14;padding:8px 18px;background:#fff6df}nav{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}input,select{font:inherit;padding:10px;border:1px solid #aab3be;border-radius:4px}input{flex:1;min-width:260px}table{width:100%;border-collapse:collapse;background:white}th,td{padding:14px;text-align:left;vertical-align:top;border-bottom:1px solid #d8dfe6}th{background:#e5eaf0;position:sticky;top:0}td:first-child{width:48%}summary{cursor:pointer;color:#175786}dt{font-weight:600;margin-top:12px}dd{margin:3px 0}code{font-size:12px;overflow-wrap:anywhere}a{color:#175786}small{color:#4d6071}[hidden]{display:none!important}@media(max-width:850px){main{padding:16px}.table-wrap{overflow:auto}table{min-width:800px}}</style>
<main><h1>Digital Twin AI: каталог инструментов</h1><p>26 сентября 2026 · __COUNT__ инструментов и рабочих цепочек · инвентаризация и синтетические проверки</p>
<p class="note"><b>Подключение ≠ использование ≠ нормативное соответствие.</b> Текущий ответ получен от Max2024. Blender4.4 — сохранённые настройки и ранее созданные результаты; AutoCAD/Revit сейчас не запущены. GeoAGR13.63: два отдельных CLI проверены на синтетических файлах; главный EXE и DLL-методы не запускались. Оригиналы и настройки DCC не изменялись.</p>
<p>Главные кандидаты: GeoAGR, SINTEZ AGR Checker, встроенный A101LP, BMAX, Andrew UCX/Ground, готовые фасадные и CAD/Revit цепочки. План: сначала проверка покрытия и адаптеры; независимое ядро хранит источники, утверждения и нормативный отчёт.</p>
<p><a href="README.md">Метод и ограничения</a> · <a href="INTEGRATION_PLAN.md">План интеграции</a> · <a href="NPM_VPM_MAP.md">Карта НПМ/ВПМ</a> · <a href="catalog.csv">CSV</a> · <a href="catalog.json">JSON</a> · <a href="duplicates.json">Дубликаты по SHA</a> · <a href="GEOAGR_13_63_REVIEW.md">GeoAGR13.63: API и тесты</a> · <a href="ZAVOD_AND_MAX_PLUGINS_REVIEW.md">zavod и библиотека Max</a></p>
<nav><input id="search" aria-label="Поиск инструмента" placeholder="Поиск: UCX, DT-023, GeoJSON, путь…"><select id="app" aria-label="Приложение"><option value="">Все приложения</option>__OPTIONS__</select></nav><p id="count"></p>
<div class="table-wrap"><table><thead><tr><th>Инструмент — раскрыть доказательства и пути</th><th>Среда</th><th>Статус</th><th>Решение</th><th>Задачи брифа</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<h2>Как читать статус</h2><p><b>runtime_verified</b> — текущий успешный вызов; <b>runtime_loaded</b> — DLL/global в живом Max; <b>configured_ui</b> — привязка рабочего меню; <b>enabled_preferences</b> — сохранённое включение Blender; <b>workflow_artifacts</b> — сохранённые результаты; <b>installed_usage_unknown</b> — только наличие; <b>older_version</b> — старая версия, не разрешение удалить.</p>
<p><small>Исходники сторонних инструментов не включены. Пути и хеши — снимок этой машины. Даты файлов не использовались как доказательство запуска.</small></p></main>
<script>const rows=[...document.querySelectorAll('tbody tr')],q=document.querySelector('#search'),app=document.querySelector('#app');function filter(){let n=0;const s=q.value.toLocaleLowerCase();for(const r of rows){const show=(!app.value||r.dataset.app===app.value)&&r.textContent.toLocaleLowerCase().includes(s);r.hidden=!show;if(show)n++;}document.querySelector('#count').textContent=`Показано ${n} из ${rows.length}`;}q.addEventListener('input',filter);app.addEventListener('change',filter);filter();</script></html>'''
    return page.replace('__COUNT__', str(len(rows))).replace('__OPTIONS__', opts).replace('__ROWS__', '\n'.join(body))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    data = json.loads((BASE/'catalog.json').read_text(encoding='utf-8'))
    page = render(data)
    out = BASE/'catalog.html'
    if args.check:
        assert out.read_text(encoding='utf-8') == page, 'stale HTML'
        csv_rows = list(csv.DictReader((BASE/'catalog.csv').open(encoding='utf-8-sig', newline='')))
        assert [r['id'] for r in csv_rows] == [r['id'] for r in data['tools']], 'CSV mismatch'
        mapping = json.loads((BASE/'stage-map.json').read_text(encoding='utf-8'))
        known = {r['id'] for r in data['tools']}
        for stage in mapping['stages']:
            assert set(stage['tools']) <= known, stage
        print(f"Inventory OK: {len(known)} tools; paths/evidence, decisions, CSV, HTML and stage references checked")
    else:
        out.write_text(page, encoding='utf-8', newline='\n')
        print(out)

if __name__ == '__main__':
    main()
