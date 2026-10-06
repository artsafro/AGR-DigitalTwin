"""Run SINTEZ AGR Checker (Blender extension sintez_agr_checker) headless on a folder of AGR ZIPs.

Usage: blender --background --factory-startup --python run_agr_checker.py -- <folder_with_zips> <out.json>

Enables the extension from the user_default repository, points it at the folder, runs the same
entry point as the panel button "Check AGR zip-files" (check_highpoly_lowpoly.calculate_all_checks),
saves the checker's own report (JSON + DOCX into its AGRChecker_data folder) and dumps every
checklist item (state, auto/manual, errors, recommendations) to <out.json>.
The checker is evidence, not the norm (docs/domain/validation.md): findings must be mapped to
regulation pages / V-codes before they count.
"""
import bpy, sys, json, importlib, addon_utils, traceback

folder, out = sys.argv[sys.argv.index("--") + 1:][:2]
MOD = "bl_ext.user_default.sintez_agr_checker"
addon_utils.enable(MOD, default_set=False, persistent=False, handle_error=lambda e: traceback.print_exc())
pkg = importlib.import_module(MOD)
chk = importlib.import_module(MOD + ".scripts.check_highpoly_lowpoly")
rep = importlib.import_module(MOD + ".scripts.check_report")
version = getattr(pkg, "bl_info", {}).get("version")


class Op:
    """Stand-in for bl_operator: collects report() messages."""
    messages = []

    def report(self, level, msg):
        self.messages.append([sorted(level) if isinstance(level, set) else level, msg])
        print("AGR-REPORT", level, msg)


props = bpy.context.scene.agr_scene_properties
props.path = folder
op = Op()
err = None
try:
    chk.calculate_all_checks(bpy.context, op)
except Exception:
    err = traceback.format_exc()
    print(err)
try:
    rep.save_report(bpy.context, op)
except Exception:
    print("save_report failed:", traceback.format_exc())


def dump(checklist):
    out = []
    for cat in checklist.categories:
        for it in cat.collection:
            out.append({"category": cat.name, "req_num": getattr(it, "req_num", ""), "name": it.name,
                        "state": it.check_state, "auto": getattr(it, "auto", None),
                        "errors_count": it.errors_count, "errors": it.errors_text,
                        "recommendations_count": it.recommendations_count, "recommendations": it.recommendations_text})
    return out


res = {"extension": MOD, "address_detected": props.project_data_address, "has_hp": props.has_highpoly,
       "has_lp": props.has_lowpoly, "error": err, "messages": op.messages,
       "hp": dump(props.checklist_hp_props), "lp": dump(props.checklist_lp_props)}
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
states = {}
for it in res["hp"]:
    states[it["state"]] = states.get(it["state"], 0) + 1
print("AGR-SUMMARY", json.dumps({"hp_items": len(res["hp"]), "states": states, "error": bool(err)}, ensure_ascii=False))
