"""Package the pinned upstream Ruby extension without requiring external Ruby."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "vendor/sketchup-mcp2/mcp_for_sketchup"
OUTPUT = ROOT / "dist/mcp_for_sketchup_v0.3.1.rbz"


def main():
    files = [SOURCE / "mcp_for_sketchup.rb"]
    files += sorted(p for p in (SOURCE / "mcp_for_sketchup").rglob("*") if p.is_file())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for source in files:
            archive.write(source, source.relative_to(SOURCE).as_posix())
    with ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        for source in files:
            assert archive.read(source.relative_to(SOURCE).as_posix()) == source.read_bytes()
    report = {
        "upstream": "https://github.com/zinin/sketchup-mcp2",
        "commit": "caf3d0b2532d6cf058f94f2ea3904f61257c8e7f",
        "package": str(OUTPUT),
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "files": len(files),
        "archive_readback": True,
        "sketchup_live_verified": False,
    }
    OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
