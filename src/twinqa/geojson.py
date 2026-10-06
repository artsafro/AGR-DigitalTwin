"""VPM GeoJSON checks (V011; reg p.26-27, App.3 p.51-55; VPM_STANDARD.yaml `geojson`).

Typed checks of the exact source schema. Where the regulation contradicts itself the
result is `review`, never a silent pass/fail: a non-empty Glasses array (conflict #13).
Empty OKS fields follow SINTEZ AGR Checker v1.6.1 (conflict #2, decided 2026-10-07):
FNO_code is mandatory (3/6/9 digits), act_AGR may be empty.
"""
import base64
import binascii
import numbers
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from twinqa.io import read_json
from twinqa.report import Finding

PAGES = [26, 27, 51, 52, 53, 54, 55]
GLASS_RANGES = {"transparency": (0, 1), "refraction": (1, 3), "roughness": (0, 1), "metallicity": (0, 1)}
OKS_MAY_BE_EMPTY = {"other", "act_AGR"}  # conflict #2, decided 2026-10-07 (as the checker)


def _f(status, name, observed, expected, pages=PAGES, conflicts=()):
    return Finding(name, status, observed, expected, list(pages), "GeoJSON", list(conflicts))


def _number(value) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _decimals(value) -> int:
    text = repr(float(value))
    return len(text.split(".")[1].rstrip("0")) if "." in text and "e" not in text else 0


def _glasses(value, glass_names) -> list[Finding]:
    if value == []:
        return [_f("pass", "Glasses", "[] (no glass)", "[] or object keyed by glass material", [51, 55])]
    if isinstance(value, list):
        return [_f("review", "Glasses", "non-empty array", "array per §22 vs object keyed by material in the example",
                   [51, 52, 53, 55], [13])]
    if not isinstance(value, dict) or not value:
        return [_f("fail", "Glasses", f"{type(value).__name__}: {value!r}"[:80],
                   "[] or object keyed by glass material name", [51, 55])]
    out = []
    for material, props in value.items():
        if glass_names is not None and material not in glass_names:
            out.append(_f("fail", "Glasses material", material, f"one of the FBX glass materials {sorted(glass_names)}", [52, 55]))
        if not isinstance(props, dict):
            out.append(_f("fail", "Glasses entry", f"{material}: {props!r}"[:80], "object with colour and optics", [55]))
            continue
        rgb = props.get("color_RGB")
        if not (isinstance(rgb, dict) and set(rgb) == {"Red", "Green", "Blue"}
                and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in rgb.values())):
            out.append(_f("fail", "Glasses color_RGB", f"{material}: {rgb!r}"[:80], "{Red, Green, Blue} integers 0..255", [55]))
        for key, (lo, hi) in GLASS_RANGES.items():
            v = props.get(key)
            if not (_number(v) and lo <= v <= hi):
                out.append(_f("fail", f"Glasses {key}", f"{material}: {v!r}", f"number {lo}..{hi}", [55, 56]))
    return out or [_f("pass", "Glasses", f"{len(value)} glass material(s)", "colour, transparency, refraction, roughness, metallicity", [55])]


def _image(value) -> Finding:
    if not isinstance(value, str) or not value:
        return _f("fail", "imageBase64", "empty", "base64 of a 256x256 JPG", [54])
    try:
        img = Image.open(BytesIO(base64.b64decode(value, validate=True)))
        size, fmt = img.size, img.format
    except (binascii.Error, UnidentifiedImageError, ValueError) as exc:
        return _f("fail", "imageBase64", f"not a decodable image ({exc.__class__.__name__})", "base64 of a 256x256 JPG", [54])
    if fmt != "JPEG" or size != (256, 256):
        return _f("fail", "imageBase64", f"{fmt} {size[0]}x{size[1]}", "JPG 256x256", [54])
    return _f("pass", "imageBase64", "JPG 256x256", "JPG 256x256", [54])


def geojson_findings(data: bytes, profile: dict, ground: bool, glass_names: set[str] | None = None) -> list[Finding]:
    spec = profile["geojson"]
    try:
        doc = read_json(data)
    except UnicodeDecodeError:
        return [_f("fail", "UTF-8", "not valid UTF-8", "UTF-8", [26])]
    except ValueError as exc:
        return [_f("fail", "JSON", str(exc)[:120], "valid JSON without duplicate keys", [26, 27])]

    out = []
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        return [_f("fail", "type", repr(doc.get("type") if isinstance(doc, dict) else doc)[:60], "FeatureCollection", [51])]
    features = doc.get("features")
    if not isinstance(features, list) or len(features) != spec["top_level"]["features_count"]:
        return [_f("fail", "features", f"{len(features) if isinstance(features, list) else features!r}", "exactly one feature", [51])]
    feat = features[0]
    if not isinstance(feat, dict):
        return [_f("fail", "feature", repr(feat)[:60], "object", [51])]
    if feat.get("type") != "ObjectFeature":
        out.append(_f("fail", "feature type", repr(feat.get("type")), "literal ObjectFeature", [51]))

    geom = feat.get("geometry")
    coords = geom.get("coordinates") if isinstance(geom, dict) else None
    if not isinstance(geom, dict) or geom.get("type") != "Point":
        out.append(_f("fail", "geometry", repr(geom)[:80], "Point", [51]))
    if not (isinstance(coords, list) and len(coords) == 2 and all(_number(c) for c in coords)):
        out.append(_f("fail", "coordinates", repr(coords)[:80], "[x, y] numbers in MSK-77", [51, 55]))
    elif any(_decimals(c) > spec["coordinates"]["decimal_places"] for c in coords):
        out.append(_f("review", "coordinates precision", repr(coords), "3 decimal places", [55]))

    props = feat.get("properties")
    keys = spec["properties_keys"]
    if not isinstance(props, dict):
        out.append(_f("fail", "properties", repr(props)[:60], "object", [51]))
        props = {}
    missing, extra = [k for k in keys if k not in props], [k for k in props if k not in keys]
    if missing or extra:
        out.append(_f("fail", "property keys", f"missing {missing}, extra {extra}", "exact App.3 key set", [26, 27, 53]))
    nullable = set(spec["ground_nullable_as_empty_string"]) if ground else OKS_MAY_BE_EMPTY
    for key in keys:
        if key in ("imageBase64",) or key not in props:
            continue
        value = props[key]
        if value in ("", None) and key not in nullable:
            out.append(_f("fail", f"{key} empty", "empty", "mandatory value (never invent it; ask the customer)", [27]))
        elif key == "FNO_code" and not ground and isinstance(value, str):
            digits = value.replace(" ", "")
            if not (digits.isdigit() and len(digits) in (3, 6, 9)):
                out.append(_f("fail", "FNO_code format", repr(value), "XXX, XXX XXX or XXX XXX XXX (FNO classifier)", [53]))
    if "imageBase64" in props:
        out.append(_image(props["imageBase64"]))

    if "Glasses" not in feat:
        out.append(_f("fail", "Glasses", "missing", "[] or object keyed by glass material", [51]))
    else:
        out.extend(_glasses(feat["Glasses"], glass_names))
    if not any(f.status != "pass" for f in out):
        out.append(_f("pass", "schema", "FeatureCollection / ObjectFeature / Point, exact keys", "App.3"))
    return out
