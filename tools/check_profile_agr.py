"""Run installed SINTEZ native NPM checks on actual extracted FBX, background only.

Blender: --background --factory-startup --disable-autoexec --python-exit-code 1
  --python tools/check_profile_agr.py -- /absolute/config.json
Config: addon_path, fbx, output_dir, result (absolute); optional address/zip_path.
This diagnostic never certifies delivery and never applies model fixes.
"""
import argparse
import hashlib
import importlib
import json
import stat
import sys
import traceback
import types
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath
from zipfile import ZipFile


def sha256(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256")
    return digest.hexdigest()


def absolute(value, label):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    return path.resolve()


def write_report(path, report):
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                  allow_nan=False) + "\n", encoding="utf-8")
    pending.replace(path)


def load_native(addon_path):
    # Do not execute extension __init__/register: it registers UI/install-state.
    # Relative imports still resolve against the exact installed native sources.
    name = "_dt_native_agr"
    package = types.ModuleType(name)
    package.__path__ = [str(addon_path)]
    package.__file__ = str(addon_path / "__init__.py")
    sys.modules[name] = package
    scripts = types.ModuleType(name + ".scripts")
    scripts.__path__ = [str(addon_path / "scripts")]
    sys.modules[scripts.__name__] = scripts
    native = importlib.import_module(name + ".scripts.check_highpoly_lowpoly")
    lowpoly = importlib.import_module(name + ".scripts.autochecks.lp_checks")
    common = importlib.import_module(name + ".scripts.common_props")
    logger = importlib.import_module(name + ".scripts.logger")
    return native, lowpoly, common, logger


def native_record(check):
    errors = list(check.error_list)
    recommendations = list(check.recommendation_list)
    internal = check.name.startswith("Проверка не выполнена.")
    native_status = ("error" if internal else "fail" if errors else
                     "review" if not check.verified else "pass")
    status = "review" if check.checked_count == 0 and not errors else native_status
    return {"ids": list(check.paragraph_ids), "name": check.name,
            "directory": check.directory, "paragraph": check.paragraph,
            "status": status, "native_status": native_status,
            "native_verified": bool(check.verified),
            "checked_count": check.checked_count, "units": check.units_text,
            "error_count": len(errors), "recommendation_count": len(recommendations),
            "errors": errors, "recommendations": recommendations,
            "comment": check.comment,
            "zero_checked_count": check.checked_count == 0,
            "reason": "native internal check exception" if internal else
                      "zero checked_count; coverage requires review" if check.checked_count == 0 and not errors else
                      "native findings" if not check.verified else "native verified flag"}


def load_bundled_pillow(addon, output):
    """Unpack the bundled matching wheel into this run; never install globally."""
    import platform
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Bundled Pillow harness currently supports Windows AMD64 only")
    candidates = sorted((addon / "wheels").glob(f"pillow-*-{tag}-{tag}-win_amd64.whl"))
    if len(candidates) != 1:
        raise RuntimeError(f"Exactly one bundled Pillow wheel for {tag}/win_amd64 required")
    wheel = candidates[0]
    dependencies = output / "dependencies"
    dependencies.mkdir(exist_ok=False)
    with ZipFile(wheel) as archive:
        entries = archive.infolist()
        if sum(item.file_size for item in entries) > 128_000_000:
            raise ValueError("Bundled dependency exceeds extraction safety budget")
        seen = set()
        destinations = []
        for item in entries:
            name = item.filename
            relative = PurePosixPath(name)
            key = name.casefold().rstrip("/")
            if (not name or relative.is_absolute() or ".." in relative.parts or
                    "\\" in name or ":" in name or key in seen or
                    stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError(f"Unsafe or duplicate wheel member: {name}")
            target = (dependencies / name).resolve()
            if not target.is_relative_to(dependencies.resolve()):
                raise ValueError(f"Wheel member escapes dependency root: {name}")
            seen.add(key)
            destinations.append((item, target))
        for item, target in destinations:
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(archive.read(item))
    # A host harness path is temporary process state, not an extension installer.
    # package_helper.ensure_import_pillow remains native and unchanged.
    sys.path.insert(0, str(dependencies))
    importlib.invalidate_caches()
    pillow = importlib.import_module("PIL")
    imported_from = Path(pillow.__file__).resolve()
    if not imported_from.is_relative_to(dependencies):
        raise RuntimeError("Pillow was already imported outside this run dependency root")
    return {"wheel": str(wheel), "wheel_sha256": sha256(wheel),
            "python_tag": tag, "platform_tag": "win_amd64",
            "version": pillow.__version__, "imported_from": str(imported_from),
            "dependency_root": str(dependencies), "members": len(destinations),
            "installation": "per-run extraction; no pip or installed-addon changes"}


def run(config_path):
    import bpy
    if not bpy.app.background:
        raise RuntimeError("Only isolated background Blender is permitted")
    if bpy.data.filepath or bpy.context.scene.objects:
        raise RuntimeError("Require --factory-startup and an empty isolated scene")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    addon = absolute(config["addon_path"], "addon_path")
    fbx_path = absolute(config["fbx"], "fbx")
    output = absolute(config["output_dir"], "output_dir")
    result = absolute(config["result"], "result")
    if not result.is_relative_to(output) or result == output:
        raise ValueError("result must be a file inside output_dir")
    if output.is_relative_to(addon) or addon.is_relative_to(output):
        raise ValueError("output must be separate from installed addon")
    if fbx_path.is_relative_to(output) or output == fbx_path.parent:
        raise ValueError("output must be separate from extracted input")
    if not fbx_path.is_file() or not (addon / "blender_manifest.toml").is_file():
        raise FileNotFoundError("Actual extracted FBX and installed addon required")
    output.mkdir(parents=True, exist_ok=True)
    for evidence in (result, output / "native-checks.json", output / "native-log.json",
                     output / "native-report.txt"):
        if evidence.exists():
            raise FileExistsError(f"Refuse to overwrite prior native evidence: {evidence}")
    result.parent.mkdir(parents=True, exist_ok=True)
    report = {"kind": "native_agr_component_diagnostic", "execution": "running",
              "scope": "NPM component transfer; all native LowpolyChecks.run_checks producers",
              "delivery_passed": False, "blender": bpy.app.version_string,
              "config_sha256": sha256(config_path), "fbx": str(fbx_path),
              "fbx_sha256_before": sha256(fbx_path), "addon_path": str(addon),
              "limitations": [
                  "Not full project delivery: archive naming, Ground and placement findings remain native.",
                  "All run_checks producers invoked; this does not mean all normative/manual criteria exist or ran.",
                  "Native zero checked_count/absent IDs do not establish coverage; native flags are preserved separately.",
                  "No fix_coordinates/material fixes/UI/export/save/package install invoked.",
                  "Native checks may select elements or annotate isolated imported mesh custom properties."]}
    records = []
    logs = []
    registered = []
    pointer_owned = False
    try:
        import tomllib
        metadata = tomllib.loads((addon / "blender_manifest.toml").read_text(encoding="utf-8"))
        provenance = {p.relative_to(addon).as_posix(): sha256(p)
                      for p in sorted(addon.rglob("*"))
                      if p.is_file() and p.suffix in {".py", ".json", ".csv", ".toml"}}
        report["addon_version"] = metadata["version"]
        report["addon_sources_sha256"] = provenance
        report["addon_source_manifest_sha256"] = hashlib.sha256(
            json.dumps(provenance, sort_keys=True).encode("utf-8")).hexdigest()
        report["pillow_dependency"] = load_bundled_pillow(addon, output)
        native, lowpoly, common, logger = load_native(addon)

        def log(message):
            logs.append({"level": "info", "message": str(message)})
            print(message)

        def log_error(error, msg=""):
            logs.append({"level": "error", "message": str(msg),
                         "error": str(error), "traceback": traceback.format_exc()})
            print(msg, error)

        # Redirect native logging into owned output, not the extracted package.
        # Do not alter checks, geometry criteria or exception_handler behavior.
        logger.add = log
        logger.add_status = log
        logger.add_error = log_error
        td_type = common.CUSTOM_objectCollection_TD_error
        bpy.utils.register_class(td_type)
        registered.append(td_type)

        class DTAGRDiagnosticProperties(bpy.types.PropertyGroup):
            path: bpy.props.StringProperty()
            Address: bpy.props.StringProperty()
            lp_td_errors: bpy.props.CollectionProperty(type=td_type)

        bpy.utils.register_class(DTAGRDiagnosticProperties)
        registered.append(DTAGRDiagnosticProperties)
        if hasattr(bpy.types.Scene, "agr_scene_properties"):
            raise RuntimeError("AGR properties already registered; require factory-startup isolation")
        bpy.types.Scene.agr_scene_properties = bpy.props.PointerProperty(type=DTAGRDiagnosticProperties)
        pointer_owned = True
        bpy.context.scene.agr_scene_properties.path = str(output)
        bpy.context.scene.agr_scene_properties.Address = config.get("address", "")
        before = {"actions": len(bpy.data.actions), "cameras": len(bpy.data.cameras),
                  "collections": len(bpy.data.collections), "objects": set(bpy.data.objects)}
        imported = bpy.ops.import_scene.fbx(filepath=str(fbx_path), use_image_search=False)
        if "FINISHED" not in imported:
            raise RuntimeError("Actual FBX import did not finish")
        descriptor = native.FbxFile(fbx_path.name, str(fbx_path.parent))
        descriptor.meshes = set(bpy.data.objects) - before["objects"]
        if not descriptor.meshes:
            raise RuntimeError("No objects imported from actual FBX")
        descriptor.objects_actions_count = len(bpy.data.actions) - before["actions"]
        descriptor.objects_cameras_count = len(bpy.data.cameras) - before["cameras"]
        descriptor.objects_collections_count = len(bpy.data.collections) - before["collections"]
        if config.get("zip_path"):
            archive = absolute(config["zip_path"], "zip_path")
            if not archive.is_file():
                raise FileNotFoundError(archive)
            descriptor.zip_name = archive.name
            report["actual_zip"] = {"path": str(archive), "sha256": sha256(archive)}
        checker = lowpoly.LowpolyChecks()
        checker.address = config.get("address", "")
        # Actual extraction parent: do not construct numeric folders or fake ZIPs.
        checker.root_path = str(fbx_path.parent)
        checker.run_checks([descriptor])
        records = [native_record(check) for group in checker.lp_checks.values() for check in group]
        (output / "native-report.txt").write_text(checker.lp_result_report, encoding="utf-8")
        report["objects"] = [{"name": obj.name, "type": obj.type}
                             for obj in descriptor.meshes]
        report["execution"] = "completed"
        report["native_internal_errors"] = sum(item["level"] == "error" for item in logs)
    except Exception as error:
        report["execution"] = "failed"
        report["failure"] = {"type": type(error).__name__, "reason": str(error),
                             "traceback": traceback.format_exc()}
    finally:
        report["checks"] = records
        report["check_status_counts"] = dict(Counter(item["status"] for item in records))
        report["native_status_counts"] = dict(Counter(item["native_status"] for item in records))
        report["reported_ids"] = sorted({value for item in records for value in item["ids"]})
        report["fbx_sha256_after"] = sha256(fbx_path)
        report["input_fbx_unchanged"] = report["fbx_sha256_before"] == report["fbx_sha256_after"]
        if not report["input_fbx_unchanged"]:
            report["execution"] = "failed"
            report["failure"] = {"type": "InputMutation", "reason": "Actual FBX bytes changed"}
        write_report(output / "native-log.json", logs)
        write_report(result, report)
        if pointer_owned:
            del bpy.types.Scene.agr_scene_properties
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
    print(json.dumps({"execution": report["execution"], "checks": len(records),
                      "counts": report["check_status_counts"], "result": str(result),
                      "delivery_passed": False}))
    return report["execution"] == "completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    import bpy
    if not bpy.app.background or bpy.data.filepath or "--factory-startup" not in sys.argv:
        raise RuntimeError("Require isolated --background --factory-startup process")
    # Only the disposable factory-startup scene is cleared. Never load live source.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sys.dont_write_bytecode = True
    if not run(args.config.resolve()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
