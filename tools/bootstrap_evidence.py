"""Generate handoff locks, field-level provenance and explicitly synthetic fixtures.

Developer tool: review the source before changing page mappings here.
"""
import hashlib
import html
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main():
    folder = ROOT / "standards"
    pdf = next((folder / "source").glob("*.pdf"))
    names = ["NPM_STANDARD.yaml", "VPM_STANDARD.yaml", "DELIVERY_VALIDATOR.yaml"]
    lock = {"pdf_file": pdf.name, "pdf_sha256": sha(pdf), "pdf_pages": 56,
            "profiles": {n: sha(folder / n) for n in names},
            "handoff_matches_initial_commit": "e77018f", "profile_status": "original_0.1.0_with_open_decisions"}
    write(folder / "source/source-lock.json", lock)
    sections = {
        "NPM": {"units": ([4], "Табл.1 §2.1"), "asset_format": ([4], "Табл.1 §1.1"),
                "archive": ([6, 7], "Табл.2 §1"), "geometry": ([6, 7, 8], "Табл.2 §1–3"),
                "materials": ([8, 9], "Табл.2 §4"), "textures": ([9, 10], "Табл.2 §5–6"),
                "glass": ([9, 10], "Табл.2 §5.10, §7"), "positioning": ([10], "Табл.2 §8"),
                "naming": ([10, 11, 12, 13], "Табл.2 §9–10"), "not_in_this_standard": ([1, 19], "Граница извлечения приложения 1; не отдельная норма")},
        "VPM": {"units": ([24], "Табл.1 §2.1"), "asset_format": ([24], "Табл.1 §1.1"),
                "archive": ([26], "Табл.2 §1"), "geometry": ([28, 29, 32], "Табл.2 §3, §7–9"),
                "materials": ([29, 30, 32], "Табл.2 §4, §8"), "textures": ([22, 23, 30, 31, 36, 37], "Термины; табл.2 §5, §12, §14"),
                "uv": ([23, 31, 32, 39], "Табл.2 §5.2, §6; рис.1.2"), "glass": ([31, 32, 51, 52, 55], "Табл.2 §5.2.2, §8; приложение 3"),
                "collision": ([34, 36, 37], "Табл.2 §10.4.2, §13"), "positioning": ([32, 33], "Табл.2 §9"),
                "naming": ([26, 33, 34, 35, 36, 41], "Табл.1 §3.7; табл.2 §10–11; рис.2.2"),
                "geojson": ([26, 27, 51, 52, 53, 54, 55], "Табл.2 §2; приложение 3, табл.1"),
                "not_in_this_standard": ([30, 31], "Граница извлечения; не отдельная норма")}}
    ambiguous = {"archive": "ADR-0002 §4", "geojson.missing": "ADR-0002 §1",
                 "collision.triangle_limit": "ADR-0002 §2", "collision.note": "ADR-0002 §2",
                 "collision.recommended_gap": "ADR-0002 §3", "positioning": "ADR-0002 §6",
                 "textures.ground_density": "ADR-0002 §8", "materials.main_material_slots": "ADR-0002 §10"}
    rows = []
    for kind in ("NPM", "VPM"):
        data = yaml.safe_load((folder / f"{kind}_STANDARD.yaml").read_text(encoding="utf-8"))
        def walk(value, path, pages, clause):
            if isinstance(value, dict):
                for key, sub in value.items():
                    if key not in {"source_page", "source_pages", "schema_source_pages"}:
                        walk(sub, path + "." + str(key), pages, clause)
            else:
                decision = next((v for k, v in ambiguous.items() if path.startswith(k)), None)
                rows.append({"rule": kind + "." + path, "value": value, "pages": pages, "clause": clause,
                             "source_sha256": lock["pdf_sha256"], "status": "review" if decision else "source_section_reviewed",
                             "decision": decision, "verification": "section text + page image; full machine implementation pending",
                             "method": "manual_review" if decision or path.startswith("not_in") else "future_parser_or_DCC_inspection"})
        for group, (pages, clause) in sections[kind].items():
            walk(data[group], group, pages, clause)
    validator = yaml.safe_load((folder / "DELIVERY_VALIDATOR.yaml").read_text(encoding="utf-8"))
    for item in validator["stages"]:
        pages = item["source_pdf_pages"]
        if isinstance(pages, dict):
            pages = sorted({p for values in pages.values() for p in values})
        rows.append({"rule": item["id"], "value": item["check"], "pages": pages,
                     "clause": "Объединённая проверка; см. строки NPM/VPM", "source_sha256": lock["pdf_sha256"],
                     "status": "specification_only", "decision": None, "method": item["engine"],
                     "verification": "Not an executable delivery validator"})
    write(folder / "traceability.json", rows)
    rendered = ''.join('<tr>' + ''.join('<td>' + html.escape(str(row[k])) + '</td>' for k in ['rule','pages','clause','status','decision','method']) + '</tr>' for row in rows)
    (ROOT / "docs/traceability.html").write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Трассировка требований</title><style>body{font:14px system-ui;margin:32px}td,th{padding:8px;border:1px solid #ccc;text-align:left}table{border-collapse:collapse}</style><h1>Правило → PDF → способ проверки</h1><p>Исходные профили 0.1.0 сохранены. Статус source_section_reviewed означает сверку раздела, а не наличие исполняемой проверки. Неполнота профилей и спорные правила: ADR-0002.</p><table><tr><th>Правило</th><th>Страницы PDF</th><th>Пункт</th><th>Статус</th><th>Решение</th><th>Метод</th></tr>' + rendered + '</table></html>', encoding="utf-8")

    source = {"kind": "synthetic", "reference": "fixture-definition.json"}
    approval = {"actor": "fixture-author", "date": "2026-09-26", "scope": "synthetic_fixture",
                "note": "Only authorizes this software test; not approval by a customer or architect."}
    materials = [dict(id="MAT_Copper", label="Synthetic warm stripes", status="approved", source=source,
                      approval=approval, diffuse_rgb=[184, 102, 61], emissive=0, roughness=165, metallic=210,
                      pattern_delta=12, normal_opengl_rgb=[128, 152, 252]),
                 dict(id="MAT_Plaster", label="Synthetic pale stripes", status="approved", source=source,
                      approval=approval, diffuse_rgb=[220, 225, 232], emissive=37, roughness=220, metallic=0,
                      pattern_delta=10, normal_opengl_rgb=[142, 110, 252])]
    corners = [[0,0,0],[2,0,0],[2,2,0],[0,2,0],[0,0,2],[2,0,2],[2,2,2],[0,2,2]]
    faces = [("Bottom",[0,3,2,1]),("South",[0,1,5,4]),("East",[1,2,6,5]),("North",[2,3,7,6]),("West",[3,0,4,7]),("Roof",[4,5,6,7])]
    surfaces = [{"id":"SURF_"+name,"material_id":materials[i%2]["id"],"vertices":[corners[k] for k in ids]} for i,(name,ids) in enumerate(faces)]
    fixture = {"synthetic": True, "description": "Software fixture: a 2m cube, six quads, two invented stripe materials; no real OКС, windows or coordinates.",
               "dimensions_m": [2,2,2], "materials": materials, "surfaces": surfaces}
    fixture_path = ROOT / "jobs/SYNTH-001/fixture-definition.json"
    write(fixture_path, fixture)
    job = {"project": {"project_id":"SYNTH_001", "synthetic":True, "address_token":"Synthetic_001",
                      "standards_sha256":lock["pdf_sha256"], "profile_versions":{"NPM":"0.1.0","VPM":"0.1.0"},
                      "inputs":{"fixture-definition.json":sha(fixture_path)},
                      "placement":{"coordinate_system":"SYNTHETIC_LOCAL", "status":"unknown", "source":source}},
           "registry":{"materials":materials}, "master":{"synthetic":True,"source":source,"surfaces":surfaces}}
    write(ROOT / "jobs/SYNTH-001/project.json", job)
    write(ROOT / "tests/fixtures/registry.json", job["registry"])
    write(ROOT / "tests/fixtures/window.json", {"id":"WIN_Test", "width_m":1.0,"height_m":1.2,
                                              "source":source,"status":"proposed"})
    print(f"Generated source lock, {len(rows)} provenance rows, explicit synthetic fixtures")


if __name__ == "__main__":
    main()
