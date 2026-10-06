# Ported from AGR src/dt_ai/publish/bundle.py (sha256 0d190a116dd4) on 2026-10-06;
# changes: read_bundle only (package() dropped), BundleError, caller-supplied uncompressed
# limit, CRC check, directory entries skipped; size_finding() moved here from the previous
# tools/qa/validate_package.py (conflict #12 handling unchanged).
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


def unit_limits(limit_bytes: int) -> tuple[str, int, int]:
    """YAML stores decimal bytes (conflict #12). Return (label, decimal, binary) readings."""
    for unit, power in (("GB", 3), ("MB", 2)):
        if limit_bytes % 1000 ** power == 0:
            n = limit_bytes // 1000 ** power
            return f"{n} {unit}", limit_bytes, n * 1024 ** power
    return f"{limit_bytes} B", limit_bytes, limit_bytes


def size_status(size_bytes: int, limit_bytes: int) -> tuple[str, str]:
    """fail only if over the limit under both decimal and binary readings; review if over
    only one (the regulation does not define MB/GB, docs/domain/conflicts.md #12)."""
    label, decimal, binary = unit_limits(limit_bytes)
    if size_bytes > max(decimal, binary):
        return "fail", f"{size_bytes} B exceeds {label} under both decimal and binary units"
    if size_bytes > min(decimal, binary):
        return "review", f"{size_bytes} B exceeds {label} only if the unit is decimal"
    return "pass", f"{size_bytes} B <= {label}"
