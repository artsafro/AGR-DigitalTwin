"""Project-scoped AutoCAD COM fixes; leave installed multiCAD files untouched."""
from pathlib import Path
import hashlib

import pythoncom
from win32com.client import VARIANT
from adapters import AutoCADAdapter
from core import CADInterface, InvalidParameterError, get_config
from mcp_tools.decorators import get_current_adapter
from mcp_tools.tools import files

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def draw_spline(self, points, closed=False, degree=3, layer="0", color="white",
                lineweight=0, _skip_refresh=False):
    if closed or degree != 3:
        raise ValueError("This COM route supports open cubic fit-point splines only")
    if len(points) < 2:
        raise InvalidParameterError("points", points, "at least two points")
    pts = [CADInterface.normalize_coordinate(p) for p in points]
    start = tuple(pts[1][i] - pts[0][i] for i in range(3))
    end = tuple(pts[-1][i] - pts[-2][i] for i in range(3))
    if not any(start) or not any(end):
        raise ValueError("Adjacent endpoint fit points must be distinct")
    spline = self._get_document("draw_spline").ModelSpace.AddSpline(
        self._points_to_variant_array(pts),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, start),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end))
    return self._finalize_entity(spline, layer, color, lineweight, "spline",
                                _skip_refresh, "Created open cubic fit-point spline")


def save(spec):
    adapter = get_current_adapter()
    fmt = spec.get("format", "dwg").lower()
    if fmt not in {"dwg", "dxf"}:
        raise ValueError("Native SaveAs supports DWG/DXF; PDF requires a plot workflow")
    raw = spec.get("filepath") or spec.get("filename")
    if not raw:
        raise ValueError("Specify a new versioned output path")
    path = Path(raw).expanduser()
    if path.is_symlink():
        raise ValueError("Output must not be a symbolic link")
    if path.is_absolute():
        path = path.resolve()
    else:
        path = Path(adapter.resolve_export_path(str(path), "drawings")).resolve()
    configured = Path(get_config().output.directory).expanduser().resolve()
    if not (path.is_relative_to(PROJECT_ROOT) or path.is_relative_to(configured)):
        raise ValueError("Output must be under this project or configured export directory")
    if path.is_relative_to(PROJECT_ROOT) and path.relative_to(PROJECT_ROOT).parts[0].startswith('.'):
        raise ValueError("Do not export drawings into project configuration directories")
    if path.suffix.lower() != "." + fmt:
        raise ValueError("Output extension must match format")
    if path.exists() or path.is_symlink():
        raise FileExistsError("Choose a new versioned output path")
    if not path.parent.is_dir():
        raise ValueError("Output parent must already exist")
    doc = adapter._get_document("save_drawing")
    # Stable Autodesk AcSaveAsType values, also read back from installed 2025
    # generated typelib (4D6C720C...): ac2018_dwg=64, ac2018_dxf=65.
    # https://help.autodesk.com/cloudhelp/2019/PLK/AutoCAD-ActiveX/files/GUID-04B5A49A-96B3-4CE1-9AED-7C3DE85225F5.htm
    save_type = {"dwg": 64, "dxf": 65}[fmt]
    doc.SaveAs(str(path), save_type)
    actual = Path(doc.FullName).resolve()
    if actual != path or not actual.is_file() or actual.stat().st_size == 0:
        raise RuntimeError("SaveAs did not produce the requested nonempty file")
    header = actual.read_bytes()[:32]
    if fmt == "dwg" and not header.startswith(b"AC1032"):
        raise RuntimeError("Expected AutoCAD 2018 DWG header")
    if fmt == "dxf" and not (header.startswith(b"AutoCAD Binary DXF") or
                             header.lstrip().startswith(b"0\r\nSECTION") or
                             header.lstrip().startswith(b"0\nSECTION")):
        raise RuntimeError("SaveAs did not produce a recognized DXF header")
    return {"success": True, "path": str(actual), "format": fmt,
            "size_bytes": actual.stat().st_size,
            "sha256": hashlib.sha256(actual.read_bytes()).hexdigest()}


def info(spec):
    doc = get_current_adapter()._get_document("document_info")
    return {"success": True, "name": doc.Name, "path": doc.FullName,
            "saved": bool(doc.Saved), "insunits": int(doc.GetVariable("INSUNITS")),
            "modelspace_count": doc.ModelSpace.Count}


def open_drawing(spec):
    source = Path(spec["filepath"]).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {".dwg", ".dxf"}:
        raise ValueError("Open requires an existing DWG or DXF")
    adapter = get_current_adapter()
    if not adapter.open_drawing(str(source)):
        raise RuntimeError("AutoCAD could not open the requested file")
    result = info({})
    if Path(result["path"]).resolve() != source:
        raise RuntimeError("Active document does not match requested source")
    return result


def install():
    AutoCADAdapter.draw_spline = draw_spline
    files.FILE_DISPATCH["save"] = (save, [])
    files.FILE_DISPATCH["open"] = (open_drawing, ["filepath"])
    files.FILE_DISPATCH["info"] = (info, [])
