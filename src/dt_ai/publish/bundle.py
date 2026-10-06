from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def package(files: dict[str, bytes], output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, files[name])


def read_bundle(path: Path):
    """Read without extracting user-controlled archive paths."""
    with ZipFile(path) as archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP members")
        if sum(x.file_size for x in infos) > 256_000_000:
            raise ValueError("Development bundle exceeds 256 MB uncompressed safety limit")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise ValueError("Unsafe ZIP path")
        return {name: archive.read(name) for name in names}
