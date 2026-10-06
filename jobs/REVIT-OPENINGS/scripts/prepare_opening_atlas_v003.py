"""Measured FBX panes and PDF facade evidence for a compact opening library."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs/source-v001"
LIB = ROOT / "outputs/library-v001"
OUT = ROOT / "outputs/openings-v003"
OUT.mkdir(parents=True, exist_ok=True)

cores = {t["id"]: t for t in json.loads((LIB / "rebuilt-core.json").read_text(encoding="utf-8"))}
curtains = {t["id"]: t for t in json.loads((LIB / "curtain-types.json").read_text(encoding="utf-8"))}


def rects(type_id: str, matrix=None):
    transform = np.eye(4) if matrix is None else np.asarray(matrix)
    result = []
    for part in cores[type_id]["parts"]:
        if part["role"] not in {"GLASS", "GLASS_CANDIDATE"}:
            continue
        vertices = np.asarray(part["vertices"]) @ transform[:3, :3].T + transform[:3, 3]
        low, high = vertices.min(axis=0), vertices.max(axis=0)
        box = [round(float(low[0]), 4), round(float(low[2]), 4),
               round(float(high[0]), 4), round(float(high[2]), 4)]
        # Revit export contains 10-50 mm seam slivers classified as glass.
        if box[2] - box[0] < .1 or box[3] - box[1] < .1:
            continue
        result.append(box)
    return result


def make_spec(name, source, title, *, pdf, confidence, role="window", opaque=False):
    if source.startswith("CW_"):
        item = curtains[source]
        w, _, h = item["dimensions"]
        panes = [p for member in item["members"] for p in rects(member["type"], member["matrix"])]
        count = len(item["placements"])
    else:
        item = cores[source]
        w, _, h = item["dimensions"]
        panes = rects(source)
        count = len(item["instances"])
        if source.startswith("WINDOW_"):
            frame = np.asarray([v for part in item["parts"] if part["role"] == "FRAME_LEAF"
                                for v in part["vertices"]])
            low = frame.min(axis=0)
            panes = [[round(p[0] - float(low[0]), 4), round(p[1] - float(low[2]), 4),
                      round(p[2] - float(low[0]), 4), round(p[3] - float(low[2]), 4)] for p in panes]
            high = frame.max(axis=0)
            w, h = float(high[0] - low[0]), float(high[2] - low[2])
    if opaque:
        panes = [[.1, .1, round(w - .1, 4), round(h - .1, 4)]]
    panes = sorted(set(tuple(p) for p in panes))
    assert all(0 <= x0 < x1 <= w + .015 and 0 <= z0 < z1 <= h + .015
               for x0, z0, x1, z1 in panes), name
    return {"id": name, "title": title, "role": role, "source": source,
            "width_m": round(w, 4), "height_m": round(h, 4), "panes_m": panes,
            "source_occurrences": count, "pdf_pages": pdf, "match": confidence,
            "infill": "opaque_leaf" if opaque else "glass",
            "frame_finish": "F11 / RAL 7016" if not opaque else "unassigned",
            "geometry": "front skin, recessed infill; no hardware"}


specs = [
    make_spec("W01", "CW_001", "Широкое окно / 3 поля", pdf=[18, 19, 20, 21], confidence="pixel+dimension"),
    make_spec("W02", "WINDOW_027", "Двухсекционное", pdf=[20, 21], confidence="visual+FBX"),
    make_spec("W03", "WINDOW_025", "Узкое с фрамугой", pdf=[19, 20, 21], confidence="visual+FBX"),
    make_spec("W04", "CW_006", "Витраж / 2 секции", pdf=[20, 21], confidence="visual+FBX", role="curtain"),
    make_spec("W05", "CW_016", "Витражная сетка / 6 секций", pdf=[20, 21], confidence="visual+FBX", role="curtain"),
    make_spec("W06", "CW_011", "Витраж / 2 высоких поля", pdf=[19, 20, 21], confidence="visual+FBX", role="curtain"),
    make_spec("W07", "CW_018", "Витраж / 3 секции", pdf=[19, 20, 21], confidence="visual+FBX", role="curtain"),
    make_spec("D01", "DOOR_119", "Остеклённая 1 створка", pdf=[19, 20, 21], confidence="visual+FBX", role="door"),
    make_spec("D02", "DOOR_102", "Остеклённая 2 створки", pdf=[19, 20, 21], confidence="visual+FBX", role="door"),
    make_spec("D03", "CW_005", "Входная группа с фрамугой", pdf=[19, 20, 21], confidence="visual+FBX", role="door_system"),
    make_spec("D04", "DOOR_048", "Глухое полотно / 1 створка", pdf=[], confidence="FBX only; facade mapping pending", role="door", opaque=True),
]
equivalents = {
    'W01': ['CW_001','CW_002','CW_004'],
    'W02': ['WINDOW_027','WINDOW_028','WINDOW_033'],
    'W04': ['CW_006','CW_008','CW_010','CW_024'],
    'W05': ['CW_016','CW_017'],
    'D03': ['CW_005','CW_020','CW_025','CW_013','CW_023','CW_015','CW_026'],
    'D04': ['DOOR_048','DOOR_049'],
}
for spec in specs:
    variants=equivalents.get(spec['id'],[spec['source']])
    spec['merged_sources']=variants
    spec['represented_occurrences']=sum(len((curtains if source.startswith('CW_') else cores)[source]
                                         ['placements' if source.startswith('CW_') else 'instances'])
                                         for source in variants)
size_variants = [
    make_spec('W01_H', 'CW_003', 'Широкое окно / высокая версия', pdf=[18,19,20,21], confidence='same subdivision, FBX size', role='window'),
    make_spec('W02_H', 'WINDOW_029', 'Двухсекционное / высокая версия', pdf=[20,21], confidence='same subdivision, FBX size', role='window'),
    make_spec('W03_H', 'WINDOW_026', 'Узкое / высокая версия', pdf=[19,20,21], confidence='same subdivision, FBX size', role='window'),
    make_spec('W01_N', 'CW_019', 'Широкое окно / уже', pdf=[18,19,20,21], confidence='same subdivision, FBX size', role='window'),
    make_spec('W04_N', 'CW_009', 'Витраж / уже', pdf=[19,20,21], confidence='same subdivision, FBX size', role='curtain'),
    make_spec('D03_W', 'CW_012', 'Входная группа / шире', pdf=[19,20,21], confidence='same entrance family, FBX size', role='door_system'),
]
extra_equivalents = {
    'W01_H': ['CW_003','CW_007','CW_014'],
    'W02_H': ['WINDOW_029','WINDOW_030','WINDOW_032','WINDOW_034'],
    'W03_H': ['WINDOW_026'],
    'W01_N': ['CW_019'],
    'W04_N': ['CW_009'],
    'D03_W': ['CW_012'],
}
for spec in size_variants:
    spec['family']=spec['id'][:3]
    spec['merged_sources']=extra_equivalents[spec['id']]
    spec['represented_occurrences']=sum(len((curtains if source.startswith('CW_') else cores)[source]
                                         ['placements' if source.startswith('CW_') else 'instances'])
                                         for source in spec['merged_sources'])

# Pixel coordinates refer to the 9048-pixel-high render of sheet 18.
# Explicit uncertainty prevents treating visual measurements as exact Revit sizes.
pixel = {"page": 18, "source": "facade-18-hi.png",
         "scale": "60600 mm / approximately 6160 rendered pixels = 9.84 mm/px",
         "W01": {"outer_box_px": [3868, 2468, 4230, 2762],
                 "inner_verticals_px": [3876, 4030, 4130, 4222],
                 "uncertainty_px": 5}}
box = pixel["W01"]["outer_box_px"]
pdf_w = box[2] - box[0]
pdf_h = box[3] - box[1]
pixel["W01"]["ratio_pdf"] = round(pdf_w / pdf_h, 4)
pixel["W01"]["ratio_fbx"] = round(specs[0]["width_m"] / specs[0]["height_m"], 4)
pixel["W01"]["ratio_error_pct"] = round(100 * abs(pdf_w / pdf_h - specs[0]["width_m"] / specs[0]["height_m"]) / (specs[0]["width_m"] / specs[0]["height_m"]), 2)
pixel["W01"]["width_pdf_m"] = round(pdf_w * .00984, 3)
pixel["W01"]["height_pdf_m"] = round(pdf_h * .00984, 3)
source_edges=[.07,1.62,2.61,3.53]
pdf_edges=pixel['W01']['inner_verticals_px']
pixel['W01']['source_verticals_projected_px']=[round(box[0]+x/specs[0]['width_m']*pdf_w,1) for x in source_edges]
pixel['W01']['division_error_px_max']=round(max(abs(a-b) for a,b in zip(pdf_edges,pixel['W01']['source_verticals_projected_px'])),1)

font_path = Path("C:/Windows/Fonts/arial.ttf")
font = ImageFont.truetype(str(font_path), 26)
small = ImageFont.truetype(str(font_path), 21)
atlas = Image.new("RGB", (2048, 2700), "#f5f6f7")
draw = ImageDraw.Draw(atlas)
draw.text((48, 30), "СОШ 1150 | типы окон, дверей и витражей", font=font, fill="#20242a")
draw.text((48, 70), "FBX + фасады PDF 18–21 | рама F11 | заполнение отдельно", font=small, fill="#4b535d")
for index, s in enumerate(specs):
    col, row = index % 3, index // 3
    left, top = 48 + col * 675, 125 + row * 635
    draw.rounded_rectangle((left, top, left + 640, top + 600), 12, fill="white", outline="#cdd3d8", width=2)
    draw.text((left + 20, top + 15), f"{s['id']}  {s['title']}", font=small, fill="#1f2730")
    draw.text((left + 20, top + 48), f"{s['width_m']:.2f} × {s['height_m']:.2f} м  |  {s['source']}", font=small, fill="#59636e")
    other_sizes=[v for v in size_variants if v['family']==s['id']]
    if other_sizes:
        versions=', '.join(f"{v['id']} {v['width_m']:.2f}×{v['height_m']:.2f}" for v in other_sizes)
        draw.text((left+20,top+78),f"Размеры: {versions}",font=small,fill='#59636e')
    max_w, max_h = 570, 410
    factor = min(max_w / s["width_m"], max_h / s["height_m"])
    ww, hh = s["width_m"] * factor, s["height_m"] * factor
    x0, y0 = left + 320 - ww / 2, top + 310 - hh / 2
    draw.rectangle((x0, y0, x0 + ww, y0 + hh), fill="#303b46")
    for a, b, c, d in s["panes_m"]:
        pad = 0
        coords = (x0 + a*factor+pad, y0+(s["height_m"]-d)*factor+pad,
                  x0+c*factor-pad, y0+(s["height_m"]-b)*factor-pad)
        draw.rectangle(coords, fill="#d7e2e8" if s["infill"] == "glass" else "#89929a")
    pdf_label=','.join(map(str,s['pdf_pages'])) or 'не привязан'
    draw.text((left + 20, top + 555), f"{s['role']} | FBX {s['represented_occurrences']} экз. | PDF {pdf_label}",
              font=small, fill="#424a55")

atlas.save(OUT / "openings-atlas-2048.png")
pdf_source = ROOT / "outputs/window-study-v003/facade-18-hi.png"
if pdf_source.exists():
    source_image = Image.open(pdf_source)
    a,b,c,d = pixel['W01']['outer_box_px']
    pdf_crop = source_image.crop((a-12,b-12,c+12,d+12)).convert('RGB')
    comparison = Image.new('RGB',(1000,490),'#f5f6f7')
    pdf_crop.thumbnail((450,365))
    comparison.paste(pdf_crop,(35,75))
    pen=ImageDraw.Draw(comparison)
    mx,my,mw,mh=550,80,420,round(420*specs[0]['height_m']/specs[0]['width_m'])
    pen.rectangle((mx,my,mx+mw,my+mh),fill='#303b46')
    for x0,z0,x1,z1 in specs[0]['panes_m']:
        pen.rectangle((mx+x0/specs[0]['width_m']*mw,
                       my+(specs[0]['height_m']-z1)/specs[0]['height_m']*mh,
                       mx+x1/specs[0]['width_m']*mw,
                       my+(specs[0]['height_m']-z0)/specs[0]['height_m']*mh),fill='#d7e2e8')
    pen.text((35,22),'PDF 18: measured raster',font=small,fill='#20242a')
    pen.text((550,22),'FBX CW_001: simplified model',font=small,fill='#20242a')
    pen.text((35,452),f"PDF {pixel['W01']['width_pdf_m']:.2f} x {pixel['W01']['height_pdf_m']:.2f} m   |   FBX 3.60 x 2.90 m   |   ratio delta {pixel['W01']['ratio_error_pct']:.2f}%",font=small,fill='#424a55')
    comparison.save(OUT/'W01-pdf-vs-model.png')
(OUT / "type-map.json").write_text(json.dumps({"types": specs, "size_variants": size_variants, "pixel_comparison": pixel,
    "scope": "facade openings only; 50-100 mm differences merged where subdivision matches",
    "excluded": "interior doors; decorative colored cassette surrounds; opening-direction diagonals and handles",
    "review": "typology proposed; user visual acceptance pending"}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"types": len(specs), "pdf_match": pixel["W01"], "atlas": str(OUT / "openings-atlas-2048.png")}, ensure_ascii=False))
