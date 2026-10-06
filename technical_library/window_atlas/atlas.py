"""Data-driven reconstruction of the accepted window atlas v8."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw, ImageFont

def validate_config(config):
    config = dict(config)
    items = config['WINDOWS']
    ids = [item['id'] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate window ID')
    mapping = {int(k): value for k, value in config['DOCX_IMAGES'].items()}
    if set(mapping) != set(ids):
        raise ValueError('Every ID must have an explicit source-image mapping')
    for item in items:
        if item['width'] <= 0 or item['height'] <= 0 or item['leaves'] <= 0:
            raise ValueError('Invalid window dimensions or leaves')
        if any(leaf < 0 or leaf >= item['leaves'] for leaf in item['door_leaves']):
            raise ValueError('Door leaf outside window')
    config['DOCX_IMAGES'] = mapping
    config['WINDOWS'] = [SimpleNamespace(**item) for item in items]
    return config

def text_center(draw: ImageDraw.ImageDraw, x: float, y: int, value: str, fnt, color: str):
    box = draw.textbbox((0, 0), value, font=fnt)
    draw.text((round(x - (box[2] - box[0]) / 2), y), value, font=fnt, fill=color)

def draw_window(draw, x, bottom, item, FRAME, GLASS):
    top = bottom - item.height
    w = item.width
    h = item.height
    frame = item.frame_px
    mullion = item.mullion_px
    draw.rectangle((x - 2, top - 2, x + w + 1, bottom + 1), fill='#333539')
    draw.rectangle((x, top, x + w - 1, bottom - 1), fill=FRAME)
    gx0, gx1 = (x + frame, x + w - frame - 1)
    gy0, gy1 = (top + frame, bottom - frame - 1)
    draw.rectangle((gx0, gy0, gx1, gy1), fill=GLASS)
    if item.transom:
        transom_fraction = item.transom_fraction
        transom_y = top + round(h * transom_fraction)
        draw.rectangle((gx0, transom_y, gx1, transom_y + mullion - 1), fill=FRAME)
        main_top = transom_y + mullion
    else:
        main_top = gy0
    cell_w = (gx1 - gx0 + 1) / item.leaves
    if item.asymmetric_split is not None:
        split = gx0 + round((gx1 - gx0) * item.asymmetric_split)
        draw.rectangle((split - 2, gy0, split + 3, gy1), fill=FRAME)
        return (x, top, w, h)
    if item.split_ratios:
        span = gx1 - gx0 + 1
        edges = [gx0] + [round(gx0 + span * ratio) for ratio in item.split_ratios] + [gx1 + 1]
    else:
        edges = [round(gx0 + leaf * cell_w) for leaf in range(item.leaves)] + [gx1 + 1]
    for split in edges[1:-1]:
        draw.rectangle((split - mullion // 2, gy0, split + mullion // 2 - 1, gy1), fill=FRAME)
    if item.middle_sash:
        middle_left = edges[1] + 5
        middle_right = edges[2] - 6
        draw.rectangle((middle_left, main_top + 4, middle_right, gy1 - 3), outline=FRAME, width=3)
    if item.lower_pane:
        lower_split = gy1 - max(22, round(h * 0.22))
        draw.rectangle((gx0, lower_split, gx1, lower_split + 6), fill=FRAME)
    for leaf in item.door_leaves:
        bay_outer_left = edges[leaf]
        bay_outer_right = edges[leaf + 1] - 1
        draw.rectangle((bay_outer_left, main_top, bay_outer_right, gy1), fill=FRAME)
        inner_left = bay_outer_left + 5
        inner_right = bay_outer_right - 5
        available = inner_right - inner_left + 1
        side_glass_w = max(9, round(available * 0.17))
        divider_w = 5
        strip_on_left = item.side_glass_left
        if strip_on_left:
            side_left, side_right = (inner_left, inner_left + side_glass_w - 1)
            door_left, door_right = (side_right + divider_w + 1, inner_right)
        else:
            door_left, door_right = (inner_left, inner_right - side_glass_w - divider_w)
            side_left, side_right = (door_right + divider_w + 1, inner_right)
        kick_top = gy1 - max(16, round((gy1 - main_top) * 0.13))
        draw.rectangle((side_left, main_top + 5, side_right, kick_top - 5), fill=GLASS)
        draw.rectangle((door_left, main_top + 8, door_right, kick_top - 5), fill=GLASS)
    return (x, top, w, h)

def build(config, output, font_dir):
    config = validate_config(config)
    SIZE, RAL, GLASS, FRAME, BG, BLACK, WHITE, DOCX_IMAGES, SWATCHES, WINDOWS = [config[k] for k in ["SIZE", "RAL", "GLASS", "FRAME", "BG", "BLACK", "WHITE", "DOCX_IMAGES", "SWATCHES", "WINDOWS"]]
    OUT = Path(output)
    def font(size, bold=False):
        return ImageFont.truetype(str(Path(font_dir) / ("arialbd.ttf" if bold else "arial.ttf")), size)
    im = Image.new('RGB', (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(im)
    draw.text((42, 25), config['TITLE'], font=font(24, True), fill=WHITE)
    draw.text((42, 59), config['SUBTITLE'], font=font(16), fill='#E5E5E5')
    draw.line((42, 96, 2006, 96), fill='#6E6F74', width=2)
    margin = 45
    gap = 20
    bottom = 530
    total = sum((window.width for window in WINDOWS)) + gap * (len(WINDOWS) - 1)
    if total > SIZE - 2 * margin:
        raise ValueError(f'Window strip too wide: {total}')
    x = margin
    rows = []
    for item in WINDOWS:
        px, py, w, h = draw_window(draw, x, bottom, item, FRAME, GLASS)
        text_center(draw, x + w / 2, 545, f'ID {item.id}', font(17, True), WHITE)
        rows.append({'id': item.id, 'kind': item.kind, 'x': px, 'y': py, 'width': w, 'height': h, 'frame_ral': '7024', 'source_docx_image': DOCX_IMAGES[item.id], 'source': 'case source DOCX images and facade screenshots'})
        x += w + gap
    draw.line((42, 599, 2006, 599), fill='#6E6F74', width=2)
    draw.text((42, 625), 'ЦВЕТОВЫЕ ЗАГЛУШКИ  •  69 × 69 px', font=font(20, True), fill=WHITE)
    draw.rectangle((0, 675, SIZE - 1, 985), fill=BLACK)
    centers = (176, 564, 952, 1340, 1728)
    swatch_top = 718
    swatch_font = font(19, True)
    id_font = font(15)
    for (ral, ids), cx in zip(SWATCHES, centers):
        left = cx - 34
        draw.rectangle((left, swatch_top, left + 68, swatch_top + 68), fill=RAL[ral])
        if ral == '8022':
            draw.rectangle((left - 1, swatch_top - 1, left + 69, swatch_top + 69), outline='#AAAAAA')
        text_center(draw, cx, 797, f'RAL {ral}', swatch_font, WHITE)
        chunks = config['SWATCH_LABEL_LINES'][ral]
        for n, chunk in enumerate(chunks):
            text_center(draw, cx, 826 + n * 22, chunk, id_font, WHITE)
    OUT.mkdir(parents=True, exist_ok=False)
    image_path = OUT / 'new_building_windows_ral_atlas_2048_v8.png'
    im.save(image_path, optimize=True)
    with (OUT / 'new_building_window_uv_manifest_v8.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return image_path
