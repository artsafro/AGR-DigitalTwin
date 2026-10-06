import csv
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
rows = defaultdict(list)
with (ROOT / "outputs/v001/uv_before.csv").open(newline="", encoding="utf-8") as stream:
    for row in csv.DictReader(stream):
        rows[int(row["id"])].append((float(row["u"]), float(row["v"])))

image = Image.new("RGB", (1600, 1200), "#f6f6f6")
draw = ImageDraw.Draw(image)
for index, material_id in enumerate(sorted(rows)):
    values = rows[material_id]
    min_u = min(p[0] for p in values)
    max_u = max(p[0] for p in values)
    min_v = min(p[1] for p in values)
    max_v = max(p[1] for p in values)
    x0 = (index % 4) * 400
    y0 = (index // 4) * 400
    draw.rectangle((x0 + 10, y0 + 10, x0 + 390, y0 + 390), outline="#888888", width=2)
    draw.text((x0 + 20, y0 + 18), f"ID {material_id} ({len(values)} UV verts)", fill="#111111")
    draw.text((x0 + 20, y0 + 36), f"u {min_u:.4f}..{max_u:.4f}; v {min_v:.4f}..{max_v:.4f}", fill="#555555")
    x_scale = 350 / max(max_u - min_u, 1e-9)
    y_scale = 320 / max(max_v - min_v, 1e-9)
    for u, v in values:
        x = int(x0 + 30 + (u - min_u) * x_scale)
        y = int(y0 + 365 - (v - min_v) * y_scale)
        draw.point((x, y), fill="#154b82")

target = ROOT / "outputs/v001/uv_overview.png"
image.save(target)
print(target)
