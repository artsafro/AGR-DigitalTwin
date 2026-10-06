from io import BytesIO

from PIL import Image, ImageDraw, ImageOps


def png(image):
    stream = BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def patterned(size, rgb, delta):
    """Explicit synthetic stripes, not a facade inferred from a drawing."""
    im = Image.new("RGB", (size, size), tuple(rgb))
    alternate = tuple(min(255, max(0, x - delta)) for x in rgb)
    draw = ImageDraw.Draw(im)
    step = max(1, size // 8)
    for x in range(step, size, step * 2):
        draw.rectangle((x, 0, min(size - 1, x + step - 1), size - 1), fill=alternate)
    return im


def pack_erm(emissive, roughness, metallic):
    if any(c.mode != "L" for c in (emissive, roughness, metallic)):
        raise ValueError("ERM inputs must be 8-bit grayscale")
    if len({c.size for c in (emissive, roughness, metallic)}) != 1:
        raise ValueError("ERM inputs must have matching dimensions")
    return Image.merge("RGB", (emissive, roughness, metallic))


def directx_normal(opengl):
    if opengl.mode != "RGB":
        raise ValueError("Normal map must be RGB")
    r, g, b = opengl.split()
    return Image.merge("RGB", (r, ImageOps.invert(g), b))


def material_maps(material, size):
    diffuse = patterned(size, material.diffuse_rgb, material.pattern_delta)
    rough = patterned(size, [material.roughness] * 3, material.pattern_delta).getchannel("R")
    metal = Image.new("L", (size, size), material.metallic)
    emit = Image.new("L", (size, size), material.emissive)
    normal = directx_normal(patterned(size, material.normal_opengl_rgb, 2))
    return {"Diffuse": diffuse, "ERM": pack_erm(emit, rough, metal), "Normal": normal}


def padded_content(im, padding):
    """Dilate boundary texels; padding is part of the stored image."""
    size = im.width
    if im.width != im.height or padding * 2 >= size:
        raise ValueError("Invalid padded image")
    inner = im.crop((padding, padding, size - padding, size - padding))
    out = Image.new(im.mode, im.size)
    out.paste(inner, (padding, padding))
    w, h = inner.size
    out.paste(inner.crop((0, 0, 1, h)).resize((padding, h)), (0, padding))
    out.paste(inner.crop((w - 1, 0, w, h)).resize((padding, h)), (size - padding, padding))
    out.paste(out.crop((0, padding, size, padding + 1)).resize((size, padding)), (0, 0))
    out.paste(out.crop((0, size - padding - 1, size, size - padding)).resize((size, padding)), (0, size - padding))
    return out
