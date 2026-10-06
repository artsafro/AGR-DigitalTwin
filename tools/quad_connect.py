"""Compatibility entry point for the recorded OBR22 workflow."""
import sys
from pathlib import Path

# Keep direct execution of the original tools possible from a checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dt_ai.geometry.connect import connect_quads


def subdivide(vertices, faces, max_side=3.9):
    return connect_quads(vertices, faces, max_side_m=max_side)
