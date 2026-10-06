# Idea ported from AGR src/dt_ai/validate/bundle.py (sha256 f02a83cd99bb) PNG block on
# 2026-10-06; changes: re-implemented without layout.json - per-file facts from the PNG
# header, map sets from VPM file names, ERM order and DirectX green judged from pixels
# (heuristics end as review when undecidable), NPM rules for embedded atlases.
"""PNG checks: NPM atlases (V006, reg p.9) and VPM Diffuse/ERM/Normal UDIM maps (V007, reg p.30-31)."""
import re
import struct
import zlib
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

from twinqa.bundle import size_status
from twinqa.report import Finding

SIGNATURE = b"\x89PNG\r\n\x1a\n"
# T_{Address}[_Ground]_{Diffuse|ERM|Normal}_{SlotNumber}.{UDIM}.png (reg p.34-35; VPM naming.texture_*)
VPM_NAME = re.compile(r"^T_(?P<address>[A-Za-z0-9_]+?)_(?P<map>Diffuse|ERM|Normal)_(?P<slot>[0-9]+)\.(?P<udim>[0-9]{4})\.png$")


@dataclass
class PngFacts:
    name: str
    width: int
    height: int
    bit_depth: int
    color_type: int  # 0 gray, 2 RGB, 3 palette, 4 gray+alpha, 6 RGBA
    has_trns: bool
    size_bytes: int

    @property
    def has_alpha(self) -> bool:
        return self.color_type in (4, 6) or self.has_trns


def png_facts(name: str, data: bytes) -> PngFacts:
    if not data.startswith(SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    pos, has_trns = 8, False
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"tRNS":
            has_trns = True
        if kind == b"IEND":
            break
        chunk = data[pos + 4:pos + 8 + length]
        if zlib.crc32(chunk) != struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]:
            raise ValueError(f"CRC error in {kind.decode('latin-1')} chunk")
        pos += 12 + length
    return PngFacts(name, width, height, bit_depth, color_type, has_trns, len(data))


def pixels(data: bytes) -> np.ndarray:
    with Image.open(BytesIO(data)) as im:
        return np.asarray(im.convert("RGB"))


def normal_convention(rgb: np.ndarray) -> tuple[str, float]:
    """Judge the green-channel convention of a tangent-space normal map.

    A map derived from a height field h has X = -dh/dx and Y = -dh/dy. With rows going
    down, the mixed derivatives d(X/Z)/d(row) and d(G/Z)/d(col) are equal when G stores
    -Y (DirectX, reg p.23: Y +1..-1 -> G 0..255) and opposite when G stores +Y (OpenGL).
    Returns ('directx'|'opengl'|'flat'|'undecided', correlation).
    """
    step = max(1, max(rgb.shape[:2]) // 1024)
    v = rgb[::step, ::step].astype(np.float32) / 127.5 - 1.0
    z = np.clip(v[..., 2], 0.05, None)
    a, b = v[..., 0] / z, v[..., 1] / z
    da = np.diff(a, axis=0)[:, :-1]
    db = np.diff(b, axis=1)[:-1, :]
    energy = float(np.sqrt((da * da).sum() * (db * db).sum()))
    if energy < 1e-6 * da.size:
        return "flat", 0.0
    corr = float((da * db).sum() / energy)
    if corr > 0.3:
        return "directx", corr
    if corr < -0.3:
        return "opengl", corr
    return "undecided", corr


def _f(status, name, observed, expected, pages, evidence, conflicts=()):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts))


def vpm_texture_findings(pngs: dict[str, bytes], profile: dict, prefix: str | None):
    """V007 findings for VPM maps in the ZIP root. Returns (findings, sets) where
    sets = {(slot, udim): {map: PngFacts}} for the UDIM/UV stages."""
    tex = profile["textures"]
    sizes = tex["allowed_square_sizes_px"]
    placeholder = tex["flat_placeholder"]["size_px"]
    out, sets = [], {}
    for name, data in sorted(pngs.items()):
        m = VPM_NAME.match(name)
        if not m:
            out.append(_f("fail", "texture name", name, "T_{Address}_{Diffuse|ERM|Normal}_{Slot}.{UDIM}.png", [34, 35], name))
            continue
        if prefix and not name.startswith(prefix + "_"):
            out.append(_f("fail", "texture address", name, f"{prefix}_...", [33, 34], name))
        try:
            facts = png_facts(name, data)
        except ValueError as exc:
            out.append(_f("fail", "PNG readable", f"{name}: {exc}", "valid PNG", [30], name))
            continue
        kind, udim = m["map"], int(m["udim"])
        sets.setdefault((int(m["slot"]), udim), {})[kind] = facts
        # 8 bit per channel, RGB 24 bit or RGBA 32 bit (reg p.30 §5.1.9)
        if facts.bit_depth != 8 or facts.color_type not in (2, 6):
            out.append(_f("fail", "8-bit RGB/RGBA", f"{name}: bit depth {facts.bit_depth}, colour type {facts.color_type}",
                          "8 bit per channel, RGB or RGBA", [30], name))
        if facts.width != facts.height or facts.width not in sizes + [placeholder]:
            out.append(_f("fail", "map size", f"{name}: {facts.width}x{facts.height}",
                          f"square {sizes} or {placeholder} placeholder", [30, 31], name))
        if kind in ("ERM", "Normal") and facts.has_alpha:
            out.append(_f("fail", "no alpha in ERM/Normal", f"{name}: alpha present", "RGB without alpha", [30], name))
        if facts.width == placeholder:
            # Flat placeholder: one averaged colour, no alpha (reg p.22, p.31 §3.1-3.5)
            px = pixels(data)
            if facts.has_alpha or (px != px[0, 0]).any():
                out.append(_f("fail", "flat placeholder", f"{name}: alpha or more than one colour",
                              "256x256, one colour, no alpha", [22, 31], name, [5]))
        elif kind == "ERM":
            # R = Emissive, G = Roughness, B = Metallic; R black when nothing glows (reg p.23, p.37 §14)
            px = pixels(data)
            lit = float((px[..., 0] > 0).mean())
            if lit >= 0.95:
                out.append(_f("review", "ERM channel order", f"{name}: R (emissive) non-zero on {lit:.0%} of pixels",
                              "R=Emissive (black where nothing glows), G=Roughness, B=Metallic", [23, 37], name))
        elif kind == "Normal":
            convention, corr = normal_convention(pixels(data))
            if convention == "opengl":
                out.append(_f("fail", "DirectX normal", f"{name}: green channel is OpenGL (+Y), curl correlation {corr:.2f}",
                              "DirectX (Y +1..-1 -> G 0..255)", [23, 30], name, [6]))
            elif convention == "undecided":
                out.append(_f("review", "DirectX normal", f"{name}: convention undecidable, correlation {corr:.2f}",
                              "DirectX", [23, 30], name, [6]))
    for (slot, udim), maps in sorted(sets.items()):
        missing = sorted({"Diffuse", "ERM", "Normal"} - set(maps))
        if missing:
            out.append(_f("fail", "map set", f"slot {slot} UDIM {udim}: missing {missing}",
                          "Diffuse + ERM + Normal for every used UDIM", [30], f"slot {slot}"))
        d = maps.get("Diffuse")
        for other in ("ERM", "Normal"):
            o = maps.get(other)
            if d and o and d.width < o.width:
                status = "review" if d.width == placeholder else "fail"
                out.append(_f(status, "Diffuse >= ERM/Normal", f"slot {slot} UDIM {udim}: Diffuse {d.width} < {other} {o.width}",
                              "Diffuse resolution >= ERM and Normal", [30], d.name))
    if not out:
        out.append(_f("pass", "VPM maps", f"{len(pngs)} PNG: names, 8-bit, sizes, alpha rules, sets, ERM order, DirectX green",
                      "reg p.30-31", [23, 30, 31], "ZIP root"))
    return out, sets


def npm_texture_findings(images: dict[str, bytes], profile: dict):
    """V006 findings for NPM atlases (embedded, reg p.9 §5.1-5.5)."""
    tex = profile["textures"]
    out = []
    for name, data in sorted(images.items()):
        try:
            facts = png_facts(name, data)
        except ValueError as exc:
            out.append(_f("fail", "PNG readable", f"{name}: {exc}", "PNG atlas", [9], name))
            continue
        if facts.width != facts.height or facts.width not in tex["allowed_square_sizes_px"]:
            # 128 px placeholders (reg p.3-4) are not in the size list (reg p.9 §5.2): conflict #5
            status = "review" if facts.width == facts.height == 128 else "fail"
            out.append(_f(status, "atlas size", f"{name}: {facts.width}x{facts.height}",
                          f"square {tex['allowed_square_sizes_px']}", [9], name, [5] if status == "review" else []))
        status, observed = size_status(facts.size_bytes, tex["max_file_bytes"])
        if status != "pass":
            out.append(_f(status, "atlas file size", f"{name}: {observed}", "<= 3 MB", [9], name, [12]))
        if facts.has_alpha:
            # Forbidden by reg p.9 §5.5, but accepted local atlases were RGBA: conflict #21 -> review
            out.append(_f("review", "no alpha", f"{name}: alpha channel present", "no alpha (separate opacity map)",
                          [9], name, [8, 21]))
        if facts.bit_depth != 8:
            out.append(_f("fail", "8-bit", f"{name}: bit depth {facts.bit_depth}", "8 bit per channel", [3, 9], name))
    if images and not out:
        out.append(_f("pass", "NPM atlases", f"{len(images)} images: sizes, <= 3 MB, no alpha, 8-bit", "reg p.9", [9], "embedded"))
    return out
