"""Restricted MCP adapter for the installed RizomUV standalone Link API."""

from __future__ import annotations

import os
import hashlib
import json
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

RIZOMUV_EXE = Path(
    os.environ.get(
        "RIZOMUV_EXE",
        r"C:\Program Files\Rizom Lab\RizomUV 2024.1\rizomuv.exe",
    )
)
RIZOMUV_LINK_DIR = Path(
    os.environ.get(
        "RIZOMUV_LINK_DIR",
        r"C:\Program Files\Rizom Lab\RizomUV 2024.1\RizomUVLink",
    )
)
sys.path.insert(0, str(RIZOMUV_LINK_DIR))

def _link_worker() -> None:
    """Keep the native DLL and its blocking lifetime out of the MCP process."""
    def send(success: bool, result: Any) -> None:
        print(json.dumps([success, result], default=str), flush=True)
    send(True, "import")
    from RizomUVLink import CRizomUVLink
    send(True, "constructor")

    allowed = {"Connect", "RizomUVVersion", "Version", "Load", "Save",
               "Unfold", "Optimize", "Pack", "Quit"}
    try:
        link = CRizomUVLink()
        send(True, "ready")
        for line in sys.stdin:
            method, args = json.loads(line)
            try:
                if method not in allowed:
                    raise ValueError("Unsupported Link operation")
                result = getattr(link, method)(*args)
                send(True, result)
            except Exception as exc:
                send(False, str(exc))
    except Exception as exc:
        send(False, str(exc))
    finally:
        # EOF/shutdown must not run the opaque native DLL destructor.
        os._exit(0)


class _ManagedLink:
    def __init__(self) -> None:
        self.worker = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--link-worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.responses: queue.Queue[Any] = queue.Queue()
        def collect() -> None:
            assert self.worker.stdout is not None
            try:
                for line in self.worker.stdout:
                    self.responses.put(json.loads(line))
            except Exception as exc:
                self.responses.put((False, str(exc)))
            finally:
                self.responses.put((False, "RizomUV Link worker exited"))
        threading.Thread(target=collect, daemon=True).start()
        deadline = time.monotonic() + 25
        stage = "spawn"
        while stage != "ready":
            try:
                success, stage = self.responses.get(timeout=max(0, deadline-time.monotonic()))
            except queue.Empty:
                self.close()
                raise TimeoutError(f"RizomUV Link initialization timed out at {stage}")
            if not success:
                self.close()
                raise RuntimeError(str(stage))

    def close(self) -> None:
        if self.worker.poll() is None:
            self.worker.terminate()
        try:
            self.worker.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.worker.kill()
            self.worker.wait(timeout=3)
        if self.worker.stdin:
            self.worker.stdin.close()

    def __getattr__(self, method: str) -> Any:
        def call(*args: Any) -> Any:
            if self.worker.poll() is not None:
                raise RuntimeError("RizomUV Link worker unavailable; operation state must be inspected")
            try:
                assert self.worker.stdin is not None
                self.worker.stdin.write(json.dumps([method, args])+"\n")
                self.worker.stdin.flush()
                try:
                    success, result = self.responses.get(timeout=25)
                except queue.Empty:
                    raise TimeoutError(f"RizomUV Link {method} exceeded 25 seconds; result unknown")
            except (EOFError, OSError, TimeoutError):
                self.close()
                raise
            if not success:
                if result == "RizomUV Link worker exited":
                    self.close()
                raise RuntimeError(result)
            return result
        return call

mcp = FastMCP("rizomuv")
_link: _ManagedLink | None = None
_process: subprocess.Popen[bytes] | None = None
_port: int | None = None
_session_lock = threading.RLock()
_loaded_path: str | None = None


def _running_process() -> bool:
    return _process is not None and _process.poll() is None


def _clear_finished_session() -> None:
    global _link, _process, _port, _loaded_path
    if _process is not None and _process.poll() is not None:
        if _link is not None:
            _link.close()
        _link, _process, _port = None, None, None
        _loaded_path = None


def _require_session() -> _ManagedLink:
    _clear_finished_session()
    if _link is None or not _running_process():
        raise RuntimeError("No live RizomUV MCP session; call open_session first")
    return _link


def _open_session() -> _ManagedLink:
    global _link, _process, _port, _loaded_path
    _clear_finished_session()
    if _link is not None and _running_process():
        if _link.worker.poll() is not None:
            replacement = _ManagedLink()
            try:
                replacement.Connect(_port)
                replacement.RizomUVVersion()
            except Exception:
                replacement.close()
                raise
            _link = replacement
        return _link
    if not RIZOMUV_EXE.is_file():
        raise RuntimeError(f"RizomUV executable not found: {RIZOMUV_EXE}")

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    link = _ManagedLink()
    try:
        process = subprocess.Popen([str(RIZOMUV_EXE), "-id", str(port)])
    except Exception:
        link.close()
        raise
    _loaded_path = None
    _link, _process, _port = link, process, port
    try:
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError(f"Managed RizomUV exited during startup: {process.returncode}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Managed RizomUV did not open its Link port within 30 seconds")
                time.sleep(0.2)
        link.Connect(port)
        version = link.RizomUVVersion()
        if not version:
            raise TimeoutError("RizomUV Link did not return a version within 10 seconds")
        return link
    except Exception:
        link.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        _link, _process, _port = None, None, None
        raise


@mcp.tool()
def get_session_status() -> dict[str, Any]:
    """Report managed process state and probe the RizomUV Link endpoint."""
    with _session_lock:
        _clear_finished_session()
        running = _running_process()
        responsive = False
        link_error: str | None = None
        if running and _link is not None:
            try:
                responsive = bool(_link.RizomUVVersion())
            except Exception as exc:
                link_error = str(exc)
        return {
            "connected": running and responsive,
            "process_running": running,
            "link_responsive": responsive,
            "link_error": link_error,
            "pid": _process.pid if running and _process else None,
            "port": _port if running and _link is not None else None,
            "executable": str(RIZOMUV_EXE),
            "loaded_path": _loaded_path if running else None,
        }


@mcp.tool()
def open_session() -> dict[str, Any]:
    """Launch a separate RizomUV window and connect through RizomUVLink."""
    with _session_lock:
        link = _open_session()
        return {
            "connected": True,
            "version": str(link.RizomUVVersion()),
            "pid": _process.pid if _process else None,
        }


@mcp.tool()
def get_version() -> dict[str, str]:
    """Read the connected RizomUV application and Link API versions."""
    with _session_lock:
        link = _require_session()
        return {"rizomuv": str(link.RizomUVVersion()), "link_api": str(link.Version())}


@mcp.tool()
def load_obj(path: str) -> dict[str, Any]:
    """Load one existing OBJ into the MCP-managed RizomUV session."""
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".obj":
        raise ValueError("path must point to an existing .obj file")
    return load_mesh(str(source))


@mcp.tool()
def load_mesh(path: str) -> dict[str, Any]:
    """Load an existing OBJ or FBX, preserving XYZ, UV data and UV properties."""
    global _loaded_path
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {".obj", ".fbx"}:
        raise ValueError("path must point to an existing OBJ or FBX file")
    with _session_lock:
        _loaded_path = None
        result = _require_session().Load({"File.Path": str(source),
                                          "File.XYZUVW": True,
                                          "File.UVWProps": True,
                                          "File.ImportGroups": True})
        _loaded_path = str(source)
        return {"loaded": str(source), "result": str(result)}


@mcp.tool()
def save_mesh(path: str, uv_properties: bool = True) -> dict[str, Any]:
    """Save the managed mesh to a new explicit OBJ or FBX path; never overwrite."""
    destination = Path(path).expanduser()
    if not destination.is_absolute():
        raise ValueError("Use an absolute versioned output path")
    if destination.is_symlink():
        raise ValueError("Output must not be a symbolic link")
    destination = destination.resolve()
    if destination.suffix.lower() not in {".obj", ".fbx"}:
        raise ValueError("Output format must be OBJ or FBX")
    if not destination.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    with _session_lock:
        link = _require_session()
        if not _loaded_path:
            raise RuntimeError("Load the intended mesh before saving")
        if destination.exists():
            raise FileExistsError("Output already exists; choose a new version")
        result = link.Save({"File.Path": str(destination), "File.UVWProps": uv_properties})
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("RizomUV Save did not produce a nonempty output file")
        return {"saved": str(destination), "source": _loaded_path,
                "size_bytes": destination.stat().st_size,
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "result": str(result)}


@mcp.tool()
def unfold_visible(working_set: str = "Visible&UnLocked") -> dict[str, str]:
    """Unfold visible, unlocked geometry in the managed document."""
    if working_set not in {"Visible", "Visible&UnLocked", "Selected"}:
        raise ValueError("working_set must be Visible, Visible&UnLocked, or Selected")
    with _session_lock:
        result = _require_session().Unfold({"WorkingSet": working_set, "PrimType": "Island"})
        return {"task": "Unfold", "result": str(result)}


@mcp.tool()
def optimize_visible(working_set: str = "Visible&UnLocked") -> dict[str, str]:
    """Optimize visible, unlocked UV geometry in the managed document."""
    if working_set not in {"Visible", "Visible&UnLocked", "Selected"}:
        raise ValueError("working_set must be Visible, Visible&UnLocked, or Selected")
    with _session_lock:
        result = _require_session().Optimize({"WorkingSet": working_set, "PrimType": "Island"})
        return {"task": "Optimize", "result": str(result)}


@mcp.tool()
def pack_visible(working_set: str = "Visible&UnLocked") -> dict[str, str]:
    """Pack UV islands with translation explicitly enabled."""
    if working_set not in {"Visible", "Visible&UnLocked", "Selected"}:
        raise ValueError("working_set must be Visible, Visible&UnLocked, or Selected")
    with _session_lock:
        result = _require_session().Pack({"WorkingSet": working_set, "Translate": True})
        return {"task": "Pack", "result": str(result)}


@mcp.tool()
def close_managed_session() -> dict[str, Any]:
    """Close only the RizomUV process launched by this MCP instance."""
    global _link, _process, _port, _loaded_path
    with _session_lock:
        _clear_finished_session()
        if _link is None or _process is None:
            return {"closed": False, "reason": "no live MCP-managed session is open"}
        pid = _process.pid
        try:
            _link.Quit()
            _process.wait(timeout=10)
        except Exception as exc:
            if _process.poll() is None:
                raise RuntimeError(f"Managed RizomUV remains open; close outcome uncertain: {exc}") from exc
        _link.close()
        _link, _process, _port = None, None, None
        _loaded_path = None
        return {"closed": True, "pid": pid}


if __name__ == "__main__":
    if sys.argv[1:] == ["--link-worker"]:
        _link_worker()
    else:
        try:
            mcp.run()
        finally:
            if _link is not None:
                _link.close()
