"""PSU275 VPM textures with the KPP1 v005 generator (accepted case) and jobs/PSU275/vpm_textures.json.

    uv run --with pillow python jobs/PSU275/scripts/make_textures_psu275.py <out_dir>
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "jobs" / "KPP1" / "scripts"))
import make_textures as mt  # noqa: E402  (KPP1 generator: make_full, save, flat placeholders)

spec_path = Path(os.environ.get("PSU275_SPEC") or ROOT / "jobs" / "PSU275" / "vpm_textures.json")  # extra OKS: own spec dir
mt.HERE = str(spec_path.parent)  # main() reads HERE/vpm_textures.json
mt.main(sys.argv[1])
