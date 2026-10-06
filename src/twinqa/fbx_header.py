# Header test ported from AGR src/dt_ai/validate/bundle.py (sha256 f02a83cd99bb) and
# tools/check_profile_snapshot.py (sha256 e3d001b4a9cb) on 2026-10-06; changes: standalone
# function with a reason string; ASCII FBX recognised.
"""Binary FBX 7.4/2014 header check (reg p.4 NPM, p.24 VPM; YAML asset_format)."""
import struct

MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"  # 23 bytes, then uint32 LE version
REQUIRED_VERSION = 7400  # FBX 7.4 = "2014/2015" format


def fbx_header(data: bytes) -> tuple[str, int | None]:
    """('binary', version) | ('ascii', None) | ('unknown', None)."""
    if len(data) >= 27 and data[:23] == MAGIC:
        return "binary", struct.unpack("<I", data[23:27])[0]
    if b"FBX" in data[:200] and data[:1] == b";":
        return "ascii", None
    return "unknown", None


def check_fbx_header(data: bytes) -> tuple[bool, str]:
    encoding, version = fbx_header(data)
    if encoding == "binary":
        return version == REQUIRED_VERSION, f"binary FBX version {version}"
    if encoding == "ascii":
        return False, "ASCII FBX"
    return False, "not an FBX header"
