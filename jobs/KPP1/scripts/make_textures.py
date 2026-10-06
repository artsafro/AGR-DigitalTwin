"""Generate the KPP1 VPM UDIM texture sets (Diffuse, ERM, Normal) from vpm_textures.json.

Usage: py -3 make_textures.py <out_dir>
Writes T_<Address>_{Diffuse|ERM|Normal}_1.<UDIM>.png (VPM naming, reg p.34 §4.3).
- full finishes: 4096 px, S = 4.096 m -> 1 px = 1 mm; patterns are periodic with the finish period P
  so faces shifted by whole periods keep the phase (vpm_uv.pack_uv);
- placeholders: 256 px single colour, no alpha (reg p.31 §3);
- ERM = R emissive (0 here), G roughness, B metallic; Normal = DirectX (G = -Y), reg p.30 §5.1.7;
- alpha only in Diffuse of alpha-cut finishes (0 = void, 255 = solid), reg p.36 §12.
Procedural, deterministic (fixed seeds). Colours are approximate RAL sRGB, not calibrated samples.
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def periodic_noise(n, scale, seed):
    """Tileable noise on an n x n cell: random spectrum low-passed at `scale` px (FFT is periodic)."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f, f)
    k = np.exp(-((fx ** 2 + fy ** 2) * (scale ** 2)))
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * k))
    return (out - out.mean()) / (out.std() + 1e-9)


def tile(cell, size):
    reps = -(-size // cell.shape[0])
    return np.tile(cell, (reps, reps))[:size, :size]


def uv_grid(size):
    """Pixel centres in tile metres (u right, v up), 1 px = 1 mm for S = 4.096 m."""
    u = (np.arange(size) + 0.5) / 1000.0
    v = (size - np.arange(size) - 0.5) / 1000.0
    return np.meshgrid(u, v)


def normal_from_height(h, strength):
    """DirectX normal map from a height field in px units (image rows grow downward)."""
    dhdx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    dhdrow = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2
    nx, ny_up, nz = -dhdx * strength, dhdrow * strength, np.ones_like(h)  # v up = -row
    ln = np.sqrt(nx ** 2 + ny_up ** 2 + nz ** 2)
    nx, ny_up, nz = nx / ln, ny_up / ln, nz / ln
    rgb = np.stack([(nx * 0.5 + 0.5), (-ny_up * 0.5 + 0.5), (nz * 0.5 + 0.5)], -1)  # DirectX: G = -Y
    return (rgb * 255).round().astype(np.uint8)


def save(arr, path, mode):
    Image.fromarray(arr, mode).save(path, optimize=True)


def make_full(t, size):
    u, v = uv_grid(size)
    rgb = np.array(t["rgb"], float)
    h = np.zeros((size, size))
    alpha = None
    rough = np.full((size, size), t["rough"])
    pat = t["pattern"]
    if pat == "tile300":  # porcelain 300x300, 4 mm joints at multiples of 0.3 m (world-aligned)
        jw = t.get("joint_half_mm", 2)
        ju = np.abs(((u * 1000 + jw) % 300) - jw) < jw
        jv = np.abs(((v * 1000 + jw) % 300) - jw) < jw
        joint = ju | jv
        n = tile(periodic_noise(300, 6, 1), size) * 0.025
        col = rgb[None, None, :] * (1 + n[..., None])
        col[joint] = rgb * 0.62
        h[joint] = -1.5
        rough[joint] = 0.85
    elif pat == "asphalt":  # 1.3 m periodic grain + aggregate speckles
        n1 = tile(periodic_noise(1300, 40, 2), size) * 0.06
        n2 = tile(periodic_noise(1300, 2, 3), size)
        col = rgb[None, None, :] * (1 + n1[..., None] + 0.12 * n2[..., None])
        h = n2 * 0.6
    elif pat == "cassette":  # metal cassettes: 8 mm open joints (dark), slight sheen noise
        ph = t.get("phase", [0.0, 0.0])
        jw = t.get("joint_half_mm", 4)
        ju = np.abs((((u - ph[0]) * 1000 + jw) % (t["P"][0] * 1000)) - jw) < jw
        jv = (np.abs((((v - ph[1]) * 1000 + jw) % (t["P"][1] * 1000)) - jw) < jw) if t.get("h_joints") else np.zeros_like(ju)
        joint = ju | jv
        n = tile(periodic_noise(600, 30, 4), size) * 0.015
        col = rgb[None, None, :] * (1 + n[..., None])
        col[joint] = rgb * 0.35
        h[joint] = -3.0
        rough[joint] = 0.9
    elif pat == "perforated":  # perforated cassette 0.6 x 0.6: holes d 50 mm, pitch 120 mm, joints 8 mm
        ph = t.get("phase", [0.0, 0.0])
        uu, vv = (u - ph[0]) % 0.6, (v - ph[1]) % 0.6
        jw = t.get("joint_half_mm", 4) / 1000
        joint = (np.minimum(uu, 0.6 - uu) < jw) | (np.minimum(vv, 0.6 - vv) < jw)
        cu, cv = (uu % 0.12) - 0.06, (vv % 0.12) - 0.06
        hole = (cu ** 2 + cv ** 2 < 0.025 ** 2) & ~joint
        col = np.broadcast_to(rgb, (size, size, 3)).copy().astype(float)
        col[hole] = (60, 62, 66)
        col[joint] = rgb * 0.45
        h[hole | joint] = -2.0
        rough[hole] = 0.95
    elif pat in ("railing", "ladder", "cage"):
        solid = np.zeros((size, size), bool)
        if pat == "railing":  # posts every 0.9 m (40 mm), top rail at 1.2 m (40 mm), 4 guide bars (20 mm)
            base = v - 0.05
            inside = (base >= 0) & (base <= 1.2)
            post = (np.abs(((u * 1000 + 20) % 900) - 20) < 20) & inside
            top = (base >= 1.16) & (base <= 1.2)
            bars = np.zeros_like(solid)
            for hb in (0.25, 0.5, 0.75, 1.0):
                bars |= np.abs(base - hb) < 0.01
            solid = post | top | (bars & inside)
        elif pat == "ladder":  # stiles 50 mm at u 0.04..0.09 / 0.79..0.84, rungs 30 mm every 0.372 m
            within = (u >= 0.04) & (u <= 0.84)
            stile = ((u >= 0.04) & (u <= 0.09)) | ((u >= 0.79) & (u <= 0.84))
            rung = (np.abs(((v * 1000 + 15) % 372) - 15) < 15) & within
            solid = stile | rung
        else:  # cage: vertical ties every 0.46 m (20 mm), hoops every 0.833 m (50 mm)
            tie = np.abs(((u * 1000 + 10) % 460) - 10) < 10
            hoop = np.abs(((v * 1000 + 25) % 833) - 25) < 25
            solid = tie | hoop
        col = np.broadcast_to(rgb, (size, size, 3)).copy()
        if pat == "railing" and "rgb_top" in t:  # handrail RAL 1021 (Revit 'Поручень ... (RAL 1021)', ИД)
            col[top & inside] = t["rgb_top"]
        alpha = np.where(solid, 255, 0).astype(np.uint8)
        h = np.where(solid, 1.0, 0.0)
    else:
        raise ValueError(pat)
    dif = np.clip(col, 0, 255).round().astype(np.uint8)
    erm = np.stack([np.zeros((size, size)), rough * 255, np.full((size, size), t["metal"] * 255)], -1)
    erm = erm.round().astype(np.uint8)
    nrm = normal_from_height(h, 0.5) if pat not in ("railing", "ladder", "cage") else None
    return dif, alpha, erm, nrm


def main(out):
    spec = json.load(open(os.path.join(HERE, "vpm_textures.json"), encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    a, fs, ps = spec["address"], spec["size_full"], spec["size_placeholder"]
    name = lambda kind, udim: os.path.join(out, f"T_{a}_{kind}_1.{udim}.png")
    flat_normal = np.broadcast_to(np.array([128, 128, 255], np.uint8), (ps, ps, 3)).copy()
    for f, t in sorted(spec["finishes"].items(), key=lambda kv: kv[1]["udim"]):
        u = t["udim"]
        if t["kind"] == "placeholder":
            save(np.broadcast_to(np.array(t["rgb"], np.uint8), (ps, ps, 3)).copy(), name("Diffuse", u), "RGB")
            erm = np.array([0, round(t["rough"] * 255), round(t["metal"] * 255)], np.uint8)
            save(np.broadcast_to(erm, (ps, ps, 3)).copy(), name("ERM", u), "RGB")
            save(flat_normal, name("Normal", u), "RGB")
        else:
            dif, alpha, erm, nrm = make_full(t, fs)
            if alpha is not None:
                save(np.dstack([dif, alpha]), name("Diffuse", u), "RGBA")
            else:
                save(dif, name("Diffuse", u), "RGB")
            if nrm is None:  # alpha-cut wire elements: flat normal and constant ERM as placeholders
                save(flat_normal, name("Normal", u), "RGB")
                e = np.array([0, round(t["rough"] * 255), round(t["metal"] * 255)], np.uint8)
                save(np.broadcast_to(e, (ps, ps, 3)).copy(), name("ERM", u), "RGB")
            else:
                save(nrm, name("Normal", u), "RGB")
                if (erm == erm[0, 0]).all():  # uniform map -> 256 placeholder (reg p.31 §3; SINTEZ 2.5.3.1)
                    save(np.broadcast_to(erm[0, 0], (ps, ps, 3)).copy(), name("ERM", u), "RGB")
                else:
                    save(erm, name("ERM", u), "RGB")
        print(f, u, t["kind"])


if __name__ == "__main__":
    main(sys.argv[1])
