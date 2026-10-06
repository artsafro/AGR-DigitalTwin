"""Build the B_Main 1001 color/alpha atlas from the captured SketchUp assets."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, default=ROOT / "outputs/v001")
parser.add_argument("--output", type=Path, default=ROOT / "outputs/v001")
parser.add_argument("--node", default="B_Main")
args = parser.parse_args()
INPUT = args.input
OUTPUT = args.output
OUTPUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT.parent / "GLB-NPM/outputs/source-live-v001/textures"
SIZE = 2048
PAD = 8

POTENTIAL_ORDER = [2, 3, 6, 11, 15, 20, 24, 27, 30, 31, 32, 50, 100]
LABELS = {
    2: "concrete_no_joints",
    3: "dark_reveals_and_sills",
    6: "dark_reveals_and_sill",
    11: "ac_units",
    15: "dark_upper_detail_unconfirmed",
    20: "fluted_columns",
    24: "dark_roof",
    27: "yellow_sill",
    30: "yellow_panel_top",
    31: "light_roof",
    32: "roof_ac_units",
    50: "windows",
    100: "spandrel",
}
RECTS = {
    2: (0, 0, 1024, 512),
    3: (0, 1536, 512, 256),
    6: (0, 1024, 512, 256),
    11: (512, 1024, 512, 256),
    15: (512, 1536, 512, 256),
    20: (1024, 0, 512, 1024),
    24: (1024, 1024, 512, 256),
    27: (0, 1280, 512, 256),
    30: (0, 512, 1024, 512),
    31: (1536, 1024, 512, 256),
    32: (512, 1280, 512, 256),
    50: (1536, 0, 512, 1024),
    100: (1024, 1280, 512, 256),
}


def interior(rect):
    x, y, w, h = rect
    return (x + PAD, y + PAD, x + w - PAD, y + h - PAD)


def fitted_texture(filename, box, crop=None):
    image = Image.open(SOURCE / filename).convert("RGBA")
    if crop:
        image = image.crop(crop)
    x0, y0, x1, y1 = box
    target_ratio = (x1 - x0) / (y1 - y0)
    current_ratio = image.width / image.height
    if current_ratio > target_ratio:
        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    else:
        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    return image.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)


uv = defaultdict(list)
with (INPUT / "uv_before.csv").open(newline="", encoding="utf-8") as stream:
    for row in csv.DictReader(stream):
        uv[int(row["id"])].append((float(row["u"]), float(row["v"])))

ORDER = [material_id for material_id in POTENTIAL_ORDER if material_id in uv]
bounds = {}
groups = {}
for material_id in ORDER:
    points = uv[material_id]
    bounds[material_id] = (
        min(p[0] for p in points), min(p[1] for p in points),
        max(p[0] for p in points), max(p[1] for p in points),
    )
    if material_id == 20 and any(p[1] > 0 for p in points) and any(p[1] < 0 for p in points):
        subsets = ["v_negative", "v_positive"]
        partitions = [[p for p in points if p[1] < 0], [p for p in points if p[1] >= 0]]
    elif material_id == 100 and any(p[0] < 1 for p in points) and any(p[0] > 1 for p in points):
        subsets = ["u_below_1", "u_above_1"]
        partitions = [[p for p in points if p[0] < 1], [p for p in points if p[0] >= 1]]
    else:
        subsets = ["all"]
        partitions = [points]
    groups[material_id] = [
        {"selector": selector, "bounds": (
            min(p[0] for p in subset), min(p[1] for p in subset),
            max(p[0] for p in subset), max(p[1] for p in subset),
        )}
        for selector, subset in zip(subsets, partitions)
    ]

atlas = Image.new("RGBA", (SIZE, SIZE), (100, 100, 100, 255))
colors = {
    3: (68, 68, 68, 255),
    6: (71, 71, 71, 255),
    11: (46, 47, 46, 255),
    15: (71, 71, 71, 255),
    24: (94, 94, 94, 255),
    27: (206, 190, 147, 255),
    31: (198, 193, 184, 255),
    32: (48, 49, 48, 255),
    50: (52, 57, 59, 255),
    100: (61, 65, 67, 255),
}
draw = ImageDraw.Draw(atlas)
for material_id, color in colors.items():
    draw.rectangle(interior(RECTS[material_id]), fill=color)

# Crop one interior slab panel; the original source image has visible seams.
atlas.paste(fitted_texture("mat_25_colorized.png", interior(RECTS[2]), (1450, 730, 2650, 1330)), interior(RECTS[2]))
atlas.paste(fitted_texture("mat_26_colorized.png", interior(RECTS[20]), (20, 20, 1080, 2155)), interior(RECTS[20]))
atlas.paste(fitted_texture("mat_09_colorized.png", interior(RECTS[30])), interior(RECTS[30]))


def map_point(material_id, u, v):
    u0, v0, u1, v1 = bounds[material_id]
    x0, y0, x1, y1 = interior(RECTS[material_id])
    return (
        round(x0 + (u - u0) / (u1 - u0) * (x1 - x0)),
        round(y1 - (v - v0) / (v1 - v0) * (y1 - y0)),
    )


faces = defaultdict(set)
with (INPUT / "face_uv_before.csv").open(newline="", encoding="utf-8") as stream:
    for row in csv.DictReader(stream):
        material_id = int(row["id"])
        if material_id in (11, 32, 50):
            faces[material_id].add(tuple(round(float(row[k]), 4) for k in ("u0", "v0", "u1", "v1")))


def pixel_box(material_id, face_box):
    u0, v0, u1, v1 = face_box
    left, bottom = map_point(material_id, u0, v0)
    right, top = map_point(material_id, u1, v1)
    return (min(left, right), min(top, bottom), max(left, right), max(top, bottom))


# Two lower repeated charts and the upper-window charts share one texture atlas.
draw = ImageDraw.Draw(atlas)
for face_box in sorted(faces[50]):
    x0, y0, x1, y1 = pixel_box(50, face_box)
    if x1 - x0 < 15 or y1 - y0 < 15:
        continue
    draw.rectangle((x0, y0, x1, y1), fill=(255, 255, 255, 255))
    border = max(3, min(x1 - x0, y1 - y0) // 20)
    draw.rectangle((x0, y0, x1, y1), outline=(30, 33, 34, 255), width=border)
    transom = round(y0 + 0.66 * (y1 - y0))
    draw.rectangle((x0 + border, transom - border // 2, x1 - border, transom + border // 2), fill=(32, 35, 36, 255))


def perforate(material_id, face_box):
    x0, y0, x1, y1 = pixel_box(material_id, face_box)
    x0 += 5; y0 += 5; x1 -= 5; y1 -= 5
    if x1 - x0 < 24 or y1 - y0 < 24:
        return
    for y in range(y0 + 7, y1 - 5, 14):
        for x in range(x0 + 7 + ((y // 14) % 2) * 7, x1 - 5, 14):
            draw.polygon([(x, y - 4), (x + 3, y), (x, y + 4), (x - 3, y)], fill=(20, 20, 20, 0))


# Only the central front chart is perforated; sides remain opaque.
for face_box in faces[11]:
    u0, v0, u1, v1 = face_box
    if 1.173 < u0 < 1.176 and v0 > 0.304 and u1 < 1.191:
        perforate(11, face_box)
for face_box in faces[32]:
    u0, v0, u1, v1 = face_box
    if 1.174 < u0 < 1.176 and v0 > 0.335 and u1 < 1.197:
        perforate(32, face_box)

atlas_path = OUTPUT / f"{args.node}_1001_2048_RGBA.png"
atlas.save(atlas_path)
manifest = {
    "status": "TRIAL / QA NOT PASSED",
    "size": [SIZE, SIZE],
    "udim": 1001,
    "node": args.node,
    "atlas_file": atlas_path.name,
    "source_skp": "C:/Users/artsafro/Downloads/ГЛБ для НПМ.skp",
    "source_textures": ["mat_25_colorized.png", "mat_26_colorized.png", "mat_09_colorized.png"],
    "visual_reconstructions": ["windows", "AC perforation opacity"],
    "materials": [
        {"old_id": material_id, "new_id": index + 1, "finish": LABELS[material_id],
         "rect_px": RECTS[material_id], "uv_bounds_before": bounds[material_id],
         "uv_groups": groups[material_id]}
        for index, material_id in enumerate(ORDER)
    ],
}
(OUTPUT / "atlas_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(atlas_path)
