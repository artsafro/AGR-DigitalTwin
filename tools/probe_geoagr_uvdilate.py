"""Isolated synthetic probe; never pass project images to this diagnostic."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

REVIEWED_SHA256 = "33229bd81a00c2d15673a144f702c643bb00ef45917e5ee928b925a2353c575e"


def probe(executable: Path) -> dict:
    executable = executable.resolve(strict=True)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest != REVIEWED_SHA256:
        raise ValueError("Unreviewed executable hash: repeat static review before execution")
    results = []
    with tempfile.TemporaryDirectory(prefix="dt-uvdilate-") as folder:
        root = Path(folder)
        for mode in ("RGBA", "RGB"):
            source, output = root / f"input-{mode}.png", root / f"output-{mode}.png"
            image = Image.new(mode, (16, 16), (0, 0, 0, 0) if mode == "RGBA" else (0, 0, 0))
            for x in range(6, 10):
                for y in range(6, 10):
                    image.putpixel((x, y), (37, 113, 211, 255) if mode == "RGBA" else (37, 113, 211))
            image.save(source)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            run = subprocess.run(
                [str(executable), "-j=1", f"-o={output}", str(source)],
                cwd=root, capture_output=True, timeout=20, check=False,
            )
            result = {
                "input_mode": mode, "returncode": run.returncode,
                "input_unchanged": before == hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_exists": output.exists(),
            }
            if output.exists():
                with Image.open(output) as actual:
                    actual.load()
                    result.update(output_mode=actual.mode, size=list(actual.size),
                                  center=list(actual.getpixel((7, 7))), corner=list(actual.getpixel((0, 0))))
            results.append(result)
    assert all(r["input_unchanged"] for r in results), results
    rgba = results[0]
    assert rgba["returncode"] == 0 and rgba["output_exists"], rgba
    assert rgba["output_mode"] == "RGB" and rgba["size"] == [16, 16], rgba
    assert rgba["center"] == rgba["corner"] == [37, 113, 211], rgba
    assert results[1]["returncode"] != 0 and not results[1]["output_exists"], results
    return {"synthetic": True, "executable": str(executable), "sha256": digest,
            "cases": results, "conclusion": "RGB dilation works on this fixture; alpha is dropped; not a production adapter"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args()
    report = probe(options.exe)
    # Create exclusively: even diagnostic reports must not overwrite an existing artifact.
    with options.out.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps(report, ensure_ascii=False))
