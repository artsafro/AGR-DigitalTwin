"""PSU275 copy of jobs/KPP1/scripts/make_npm_atlas.py (accepted case KPP1 v005); change: spec = jobs/PSU275/vpm_textures.json,
KPP1 modules imported from jobs/KPP1/scripts.
"""
"""Build the KPP1 NPM texture set: one 2048 atlas per OKS (reg p.9 §5.1-5.11), PNG, no alpha channel.

Usage: py -3 make_npm_atlas.py <out_dir>
Writes T_<A>_001_Main_d_1.png (Diffuse, RGB), T_<A>_001_Main_o_1.png (Opacity, RGB white = solid,
black = void; railings/ladder/cage only, reg p.9 §5.8; no alpha channel anywhere, conflict #21) and
npm_atlas.json (finish -> region). No normal map (conflict #6), no metallic/roughness (optional pair,
reg p.9 §5.6).

Layout: one square region per finish on a 5 x 4 grid of 409 px cells; each region stands for the same
4.096 m as the finish's VPM UDIM tile, so NPM UV = region origin + VPM tile-local UV x region size and the
finish module (cassette 0.6 m, tile 0.3 m) has the same physical size as in VPM (docs/domain/uv-textures.md,
NPM-OKS rule). 6 px edge padding around each region -> >= 12 px between regions (reg p.9 §5.4: >= 8 px).
Joints are rasterised >= 1.5 px wide (lesson: sub-pixel joints vanish, FACADES_ATLAS).
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))
import make_textures as mt  # noqa: E402

ATLAS, CELL, PAD, COLS = 2048, 409, 6, 5
REGION = CELL - 2 * PAD
NPM_JOINT_HALF_MM = 8  # 16 mm on the atlas ~ 1.5 px at 97 px/m


def main(out):
    spec = json.load(open(os.environ.get("PSU275_SPEC") or os.path.join(HERE, "..", "vpm_textures.json"), encoding="utf-8"))
    a = os.environ.get("PSU275_NPM_ADDRESS") or spec["address"]
    nnn = f'{int(os.environ.get("PSU275_NPM_INDEX", "1")):03d}'
    os.makedirs(out, exist_ok=True)
    dif = np.zeros((ATLAS, ATLAS, 3), np.uint8)
    opa = np.full((ATLAS, ATLAS, 3), 255, np.uint8)
    layout = {}
    for k, (f, t) in enumerate(sorted(spec["finishes"].items(), key=lambda kv: kv[1]["udim"])):
        cx, cy = (k % COLS) * CELL, (k // COLS) * CELL      # cell origin, image rows from the top
        if t["kind"] == "full":
            tt = dict(t, joint_half_mm=NPM_JOINT_HALF_MM)
            d, alpha, _, _ = mt.make_full(tt, spec["size_full"])
            reg = np.asarray(Image.fromarray(d, "RGB").resize((REGION, REGION), Image.LANCZOS))
            if alpha is not None:
                m = np.asarray(Image.fromarray(alpha, "L").resize((REGION, REGION), Image.BOX))
                solid = m >= 128                                  # 0-127 void, 128-255 solid (reg p.36 §12.2)
                o = np.where(solid, 255, 0).astype(np.uint8)
                o = np.pad(o, PAD, mode="edge")
                opa[cy:cy + CELL, cx:cx + CELL] = o[..., None]
                mean = d[alpha >= 128].mean(0) if (alpha >= 128).any() else d.reshape(-1, 3).mean(0)
                reg = np.where(solid[..., None], reg, mean.round().astype(np.uint8))  # void colour = average
        else:
            reg = np.broadcast_to(np.array(t["rgb"], np.uint8), (REGION, REGION, 3))
        dif[cy:cy + CELL, cx:cx + CELL] = np.pad(reg, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
        # region in UV space (v up): x0, y0 of the region's lower-left corner and its size
        layout[f] = {"udim": t["udim"], "u0": (cx + PAD) / ATLAS, "v0": 1 - (cy + PAD + REGION) / ATLAS,
                     "size": REGION / ATLAS, "px_per_m": round(REGION / t.get("S", 4.096), 1)
                     if t["kind"] == "full" else None}
        print(f, t["udim"], t["kind"], (cx, cy))
    dn = os.path.join(out, f"T_{a}_{nnn}_Main_d_1.png")
    on = os.path.join(out, f"T_{a}_{nnn}_Main_o_1.png")
    Image.fromarray(dif, "RGB").save(dn, optimize=True)
    Image.fromarray(opa, "RGB").save(on, optimize=True)
    json.dump({"atlas": ATLAS, "cell": CELL, "pad": PAD, "region": REGION, "finishes": layout},
              open(os.path.join(out, "npm_atlas.json"), "w", encoding="utf-8"), indent=1)
    for p in (dn, on):
        print(os.path.basename(p), os.path.getsize(p), "bytes")


if __name__ == "__main__":
    main(sys.argv[1])
