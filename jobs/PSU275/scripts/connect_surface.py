"""Subdivide an exterior-surface npz to quads <= max side (VPM texel cuts), keeping provenance.

    uv run python jobs/PSU275/scripts/connect_surface.py <surface_dir> <out_dir> [--max-side 3.9]

Uses src/dt_ai/geometry/connect.connect_quads (opposite-edge propagation, T-free). Copies the
surface JSON (profiles) unchanged; facade_indices and finish follow the parent quad.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from dt_ai.geometry.connect import connect_quads  # noqa: E402

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
max_side = float(sys.argv[sys.argv.index("--max-side") + 1]) if "--max-side" in sys.argv else 3.9
d = np.load(src / "exterior-surface.npz")
v, f, parents = connect_quads(d["vertices"], d["faces"], max_side_m=max_side)
v, f, parents = np.asarray(v), np.asarray(f, dtype=np.int32), np.asarray(parents)
edges = np.linalg.norm(v[f] - v[np.roll(f, -1, axis=1)], axis=2)
dst.mkdir(parents=True, exist_ok=False)
np.savez_compressed(dst / "exterior-surface.npz", vertices=v, faces=f,
                    facade_indices=d["facade_indices"][parents].astype(np.int32),
                    finish=d["finish"][parents].astype(np.int32), parent=parents.astype(np.int32))
doc = json.loads((src / "exterior-surface.json").read_text(encoding="utf-8"))
doc.update({"connect": {"max_side_m": max_side, "source": str(src), "quads_before": int(len(d["faces"])),
                        "quads": int(len(f)), "max_edge_m": float(edges.max()), "min_edge_m": float(edges.min())}})
(dst / "exterior-surface.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
print(json.dumps(doc["connect"]))
