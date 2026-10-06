# Ported from AGR src/dt_ai/publish/bundle.py (sha256 0d190a116dd4) on 2026-10-06;
# changes: read_bundle only (package() dropped), BundleError, caller-supplied uncompressed
# limit, CRC check, directory entries skipped; size_finding() moved here from the previous
# tools/qa/validate_package.py; conflict #12 decided 2026-10-07 (binary units).
"""Safe ZIP reading (no extraction of archive-controlled paths) and archive size rules."""
import zipfile
from pathlib import PurePosixPath


class BundleError(ValueError):
    pass


def read_bundle(path, max_uncompressed: int) -> dict[str, bytes]:
    """Return {member: bytes}. Rejects broken ZIPs, unsafe paths, duplicates, oversize content."""
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise BundleError(f"Not a readable ZIP: {exc}") from exc
    with archive:
        infos = [x for x in archive.infolist() if not x.is_dir()]
        names = [x.filename for x in infos]
        if len(names) != len(set(names)):
            raise BundleError("Duplicate ZIP members")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise BundleError(f"Unsafe ZIP path: {name}")
        total = sum(x.file_size for x in infos)
        if total > max_uncompressed:
            raise BundleError(f"Uncompressed content {total} B exceeds safety limit {max_uncompressed} B")
        try:
            return {name: archive.read(name) for name in names}
        except (zipfile.BadZipFile, OSError, EOFError) as exc:  # CRC errors, truncated members
            raise BundleError(f"Broken ZIP member: {exc}") from exc


def size_status(size_bytes: int, limit_bytes: int) -> tuple[str, str]:
    """Limits are binary bytes (MiB/GiB), as SINTEZ AGR Checker (conflict #12, decided 2026-10-07)."""
    label = f"{limit_bytes / 1024 ** 2:g} MiB"
    if size_bytes > limit_bytes:
        return "fail", f"{size_bytes} B exceeds {label}"
    return "pass", f"{size_bytes} B <= {label}"
