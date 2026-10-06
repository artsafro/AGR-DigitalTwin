"""GLB A/B captured-UV atlas recipe. No DCC mutation; case-specific."""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha256(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def input_inventory(input_dir, source_dir, config):
    paths = {
        "input/uv_before.csv": input_dir / "uv_before.csv",
        "input/face_uv_before.csv": input_dir / "face_uv_before.csv",
    }
    for item in config["textures"]:
        paths[f"textures/{item['file']}"] = source_dir / item["file"]
    return {name: sha256(path) for name, path in paths.items()}


def validate_inputs(input_dir, source_dir, config, node):
    scenario = config["scenarios"][node]
    expected = scenario["face_count"]
    observed_ids = {}
    for filename, columns in [("uv_before.csv", ("u", "v")),
                              ("face_uv_before.csv", ("u0", "v0", "u1", "v1"))]:
        with (input_dir / filename).open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if not rows or (filename.startswith("face_") and len(rows) != expected):
            raise ValueError("Wrong captured face count or empty CSV")
        observed_ids[filename] = {int(row["id"]) for row in rows}
        for row in rows:
            if int(row["id"]) not in config["POTENTIAL_ORDER"]:
                raise ValueError("Unknown source material ID")
            if not all(math.isfinite(float(row[key])) for key in columns):
                raise ValueError("Non-finite UV input")
    if observed_ids["uv_before.csv"] != observed_ids["face_uv_before.csv"]:
        raise ValueError("UV and face captures use different material IDs")
    expected_ids = set(scenario.get("material_ids", ()))
    if expected_ids and observed_ids["uv_before.csv"] != expected_ids:
        raise ValueError("Captured material IDs do not match the selected scenario")
    actual = input_inventory(input_dir, source_dir, config)
    expected_hashes = scenario.get("input_sha256")
    if expected_hashes and actual != expected_hashes:
        raise ValueError("Input SHA256 mismatch for selected scenario")
    return actual


def build(config, input_dir, source_dir, output_dir, node):
    INPUT, SOURCE, OUTPUT = map(Path, (input_dir, source_dir, output_dir))
    if OUTPUT.exists():
        raise FileExistsError("Choose a new output directory; overwrite is forbidden")
    inventory = validate_inputs(INPUT, SOURCE, config, node)
    SIZE, PAD = config["SIZE"], config["PAD"]
    POTENTIAL_ORDER = config["POTENTIAL_ORDER"]
    LABELS = {int(k): v for k, v in config["LABELS"].items()}
    RECTS = {int(k): v for k, v in config["RECTS"].items()}
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
    colors = {int(k): tuple(v) for k, v in config["colors"].items()}
    draw = ImageDraw.Draw(atlas)
    for material_id, color in colors.items():
        draw.rectangle(interior(RECTS[material_id]), fill=color)

    for item in config["textures"]:
        box = interior(RECTS[item["id"]])
        atlas.paste(fitted_texture(item["file"], box, item["crop"]), box)



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

    atlas_path = OUTPUT / f"{node}_1001_2048_RGBA.png"
    encoded = io.BytesIO()
    atlas.save(encoded, format="PNG")
    png_bytes = encoded.getvalue()
    png_sha256 = hashlib.sha256(png_bytes).hexdigest()
    expected_png = config["scenarios"][node].get("expected_png_sha256")
    if expected_png and png_sha256 != expected_png:
        raise ValueError("Rendered PNG SHA256 does not match the selected scenario")
    manifest = {
        "status": "TRIAL / QA NOT PASSED",
        "size": [SIZE, SIZE],
        "udim": 1001,
        "node": node,
        "atlas_file": atlas_path.name,
        "source_case": "GLB A/B Main; local SketchUp texture capture",
        "source_textures": [item["file"] for item in config["textures"]],
        "provenance": {
            "input_sha256": inventory,
            "expected_input_sha256": config["scenarios"][node].get("input_sha256"),
            "strict_input_match": bool(config["scenarios"][node].get("input_sha256")),
            "config_canonical_sha256": canonical_sha256(config),
            "renderer_sha256": sha256(__file__),
            "png_sha256": png_sha256,
            "expected_png_sha256": expected_png,
            "strict_png_match": bool(expected_png),
        },
        "visual_reconstructions": ["windows", "AC perforation opacity"],
        "materials": [
            {"old_id": material_id, "new_id": index + 1, "finish": LABELS[material_id],
             "rect_px": RECTS[material_id], "uv_bounds_before": bounds[material_id],
             "uv_groups": groups[material_id]}
            for index, material_id in enumerate(ORDER)
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=False)
    atlas_path.write_bytes(png_bytes)
    (OUTPUT / "atlas_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("scenarios.json"))
    parser.add_argument("--node", choices=("A_Main", "B_Main"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    build(config, args.input, args.textures, args.output, args.node)


if __name__ == "__main__":
    main()
