"""Run a pinned UCX checker on generated fixtures, never on a working scene."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

REVIEWED_SHA256 = "e40e33a5b32362d557c8712608fc4018ffa1bd43585824d950b1a48da1d0484f"
VERTICES = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
FACES = [(1, 3, 2), (1, 4, 3), (5, 6, 7), (5, 7, 8), (1, 2, 6), (1, 6, 5),
         (4, 8, 7), (4, 7, 3), (1, 5, 8), (1, 8, 4), (2, 3, 7), (2, 7, 6)]


def mesh(offset, scale):
    lines = ["# Synthetic arbitrary unit cubes, not a real OKS"]
    for index, (name, delta, factor) in enumerate([
        ("UCX_SyntheticA", (0, 0, 0), 1), ("UCX_SyntheticB", offset, scale)
    ]):
        lines.append("o " + name)
        lines += ["v " + " ".join(str(x * factor + dx) for x, dx in zip(v, delta)) for v in VERTICES]
        lines += ["f " + " ".join(str(v + index * 8) for v in face) for face in FACES]
    return "\n".join(lines) + "\n"


def probe(executable: Path):
    executable = executable.resolve(strict=True)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest != REVIEWED_SHA256:
        raise ValueError("Unreviewed executable hash: repeat static review before execution")
    results = []
    with tempfile.TemporaryDirectory(prefix="dt-ucx-") as folder:
        root = Path(folder)
        cases = {"apart": ((2, 0, 0), 1), "intersect": ((.5, .25, .25), 1),
                 "contained": ((.25, .25, .25), .5), "touch": ((1, 0, 0), 1),
                 "invalid": ((0, 0, 0), 1)}
        for name, (offset, scale) in cases.items():
            work = root / name
            work.mkdir()
            source = work / "synthetic.obj"
            source.write_text("not an obj\n" if name == "invalid" else mesh(offset, scale), encoding="ascii")
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            run = subprocess.run([str(executable), str(source), "--quiet"], cwd=work,
                                 capture_output=True, timeout=20, check=False)
            output = source.with_suffix(".txt")
            results.append({"case": name, "returncode": run.returncode,
                            "input_unchanged": before == hashlib.sha256(source.read_bytes()).hexdigest(),
                            "findings_file_exists": output.exists(),
                            "names": output.read_text(encoding="cp1251").splitlines() if output.exists() else None,
                            "sidecar_files": sorted(p.name for p in work.iterdir() if p != source)})
    by_name = {r["case"]: r for r in results}
    assert all(r["input_unchanged"] for r in results), results
    assert by_name["apart"]["returncode"] == 0 and by_name["apart"]["names"] == [], results
    assert by_name["intersect"]["returncode"] == 0, results
    assert set(by_name["intersect"]["names"]) == {"UCX_SyntheticA", "UCX_SyntheticB"}, results
    assert by_name["contained"]["returncode"] == 0 and by_name["contained"]["names"] == [], results
    assert by_name["touch"]["returncode"] == 0, results
    assert set(by_name["touch"]["names"]) == {"UCX_SyntheticA", "UCX_SyntheticB"}, results
    assert by_name["invalid"]["returncode"] != 0 and not by_name["invalid"]["findings_file_exists"], results
    return {"synthetic": True, "executable": str(executable), "sha256": digest,
            "cases": results, "scope": "OBJ pair intersection diagnostic; not full UCX validation"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = probe(args.exe)
    with args.out.open("x", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps(result, ensure_ascii=False))
