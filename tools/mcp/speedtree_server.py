"""SpeedTree file inspection and batch export; does not control the active GUI."""
from __future__ import annotations

import gzip
import hashlib
import os
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

INSTALL_ROOT = Path(os.environ.get("SPEEDTREE_ROOT", r"C:\Program Files\SpeedTree\SpeedTree Modeler v10.0.1"))
EXECUTABLE = INSTALL_ROOT / "win64/SpeedTree_Modeler.exe"
TASK_ROOT = Path(os.environ.get("SPEEDTREE_TASK_ROOT", str(Path(__file__).resolve().parents[2]))).resolve()
XML_LIMIT = 64 * 1024 * 1024
LOG_LIMIT = 64 * 1024
_export_lock = threading.Lock()
mcp = FastMCP("speedtree-batch")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Symlink/junction paths are not accepted: {part}")


def _input(path: str, extension: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("An exact absolute input path is required")
    _reject_links(candidate)
    candidate = candidate.resolve(strict=True)
    if not candidate.is_file() or candidate.suffix.lower() != extension:
        raise ValueError(f"Expected an existing {extension} file")
    return candidate


def _output(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("An absolute versioned output path is required")
    _reject_links(candidate)
    candidate = candidate.resolve()
    if not candidate.is_relative_to(TASK_ROOT):
        raise ValueError(f"Output must remain within task root: {TASK_ROOT}")
    expected = ".fbx"
    if candidate.suffix.lower() != expected:
        raise ValueError(f"This mode requires {expected} output")
    if candidate.exists():
        raise FileExistsError("Output already exists")
    if not candidate.parent.is_dir() or any(candidate.parent.iterdir()):
        raise ValueError("Use an existing EMPTY versioned output directory for all sidecars")
    return candidate


def _page(directory: Path, suffix: str, category: str, offset: int, limit: int) -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("offset must be nonnegative; limit must be 1..100")
    if not directory.is_dir():
        raise FileNotFoundError(str(directory))
    files = sorted(p for p in directory.rglob(f"*{suffix}") if p.is_file()
                   and (category == "all" or p.relative_to(directory).parts[0].lower() == category.lower()))
    items = [{"path": str(p), "name": p.name, "relative_path": p.relative_to(directory).as_posix(),
              "size_bytes": p.stat().st_size} for p in files[offset:offset + limit]]
    return {"total": len(files), "offset": offset, "items": items,
            "has_more": offset + len(items) < len(files)}


@mcp.tool()
def installation_info() -> dict[str, Any]:
    """Report configured installation and file-based batch scope; no active-model connection."""
    installed = EXECUTABLE.is_file()
    return {"installed": installed, "executable": str(EXECUTABLE),
            "executable_sha256": _sha256(EXECUTABLE) if installed else None,
            "task_root": str(TASK_ROOT), "interface": "local files and separate CLI batch export",
            "active_gui_control": False, "supported_export_formats": ["fbx"],
            "cli_verification": "requires a successful recorded fixture export"}


@mcp.tool()
def list_templates(category: Literal["all", "Games", "VFX"] = "all", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    """List a bounded page of installed SPM templates; return exact absolute paths."""
    return _page(INSTALL_ROOT / "tree_templates", ".spm", category, offset, limit)


@mcp.tool()
def list_presets(category: Literal["all", "Games", "VFX"] = "all", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    """List a bounded page of installed INI export presets."""
    return _page(INSTALL_ROOT / "export_presets", ".ini", category, offset, limit)


@mcp.tool()
def inspect_preset(path: str) -> dict[str, Any]:
    """Inspect one exact absolute INI path, retaining sections and literal values."""
    source = _input(path, ".ini")
    if source.stat().st_size > 1024 * 1024:
        raise ValueError("Preset exceeds 1 MiB inspection limit")
    sections: dict[str, dict[str, str]] = {"General": {}}
    section = "General"
    for raw in source.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections.setdefault(section, {})
        elif "=" in line:
            key, value = line.split("=", 1)
            sections[section][key.strip()] = value.strip()
    return {"path": str(source), "sha256": _sha256(source), "sections": sections}


@mcp.tool()
def inspect_spm(path: str) -> dict[str, Any]:
    """Inspect bounded gzip/XML SPM data; cached statistics do not prove exported geometry."""
    source = _input(path, ".spm")
    with gzip.open(source, "rb") as stream:
        xml = stream.read(XML_LIMIT + 1)
    if len(xml) > XML_LIMIT:
        raise ValueError("Decompressed SPM exceeds 64 MiB inspection limit")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("DTD/entity declarations are not accepted")
    root = ET.fromstring(xml)
    materials, meshes = [], []
    material_count = mesh_count = 0
    for node in root.iter():
        if node.tag == "Material_v8" and node.get("Name"):
            material_count += 1
            if len(materials) < 100:
                materials.append({"id": node.get("ID"), "name": node.get("Name")})
        elif node.tag == "Mesh" and node.get("Name"):
            mesh_count += 1
            if len(meshes) < 100:
                meshes.append({"id": node.get("ID"), "name": node.get("Name")})
    return {"path": str(source), "sha256": _sha256(source), "size_bytes": source.stat().st_size,
            "version": root.get("Version"), "version_string": root.get("VersionString"),
            "cached_triangles": root.findtext("Statistics/TotalTriangles"),
            "material_count": material_count, "materials": materials,
            "mesh_count": mesh_count, "meshes": meshes, "item_limit": 100}


@mcp.tool()
def export_tree(source_path: str, preset_path: str, output_path: str,
                timeout_seconds: int = 120) -> dict[str, Any]:
    """Batch-export an exact SPM using an exact INI to a new FBX.

    Requires an existing empty task output directory. Does not edit or inspect
    the user's active GUI model. Export validity still requires native readback.
    """
    if not 1 <= timeout_seconds <= 120:
        raise ValueError("timeout_seconds must be 1..120")
    if not EXECUTABLE.is_file():
        raise FileNotFoundError(str(EXECUTABLE))
    with _export_lock:
        source, preset = _input(source_path, ".spm"), _input(preset_path, ".ini")
        output = _output(output_path)
        before = {"source": _sha256(source), "preset": _sha256(preset)}
        command = [str(EXECUTABLE), str(source), "-export",
                   str(output), "-export_options", str(preset)]
        started = time.monotonic()
        error, exit_code = None, None
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                         timeout=timeout_seconds, cwd=str(output.parent),
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                error = f"Batch export timed out after {timeout_seconds}s"
            except OSError as exc:
                error = str(exc)
            logs = {}
            for name, stream in (("stdout", stdout), ("stderr", stderr)):
                length = stream.tell()
                stream.seek(0)
                logs[name] = stream.read(LOG_LIMIT).decode("utf-8", errors="replace")
                logs[name + "_truncated"] = length > LOG_LIMIT
        after = {"source": _sha256(source), "preset": _sha256(preset)}
        files = []
        for path in sorted(output.parent.rglob("*")):
            _reject_links(path)
            if path.is_file():
                files.append({"path": str(path), "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
        main_ok = output.is_file() and output.stat().st_size > 0
        recognized_fbx = None
        if main_ok:
            with output.open("rb") as stream:
                header = stream.read(256)
            recognized_fbx = header.startswith(b"Kaydara FBX Binary  \x00") or header.lstrip().startswith(b"; FBX")
            main_ok = main_ok and recognized_fbx
        return {"success": error is None and exit_code == 0 and main_ok and before == after,
                "error": error, "exit_code": exit_code, "command": command,
                "output_path": str(output), "files": files, "input_sha256_before": before,
                "input_sha256_after": after, "inputs_unchanged": before == after,
                "recognized_fbx_header": recognized_fbx,
                "native_readback_verified": False,
                "duration_seconds": round(time.monotonic() - started, 3), **logs}


if __name__ == "__main__":
    mcp.run()
