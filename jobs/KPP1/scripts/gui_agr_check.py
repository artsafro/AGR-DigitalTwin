"""Open Blender with the UI and run SINTEZ AGR Checker on a folder of AGR ZIPs, for visual review.

Usage: blender --python gui_agr_check.py -- <folder_with_zips>
Once the window is up: points the checker at the folder, runs the panel's "Check AGR zip-files"
operator (agr.run_calculate_all) in the 3D view context and opens the sidebar on the checker tab.
"""
import bpy, sys

folder = sys.argv[sys.argv.index("--") + 1]


def view3d():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                region = next(r for r in area.regions if r.type == "WINDOW")
                return win, area, region
    return None


def run():
    ctx = view3d()
    if not ctx:
        return 0.5  # UI not ready yet
    win, area, region = ctx
    scene = bpy.context.scene
    scene.agr_scene_properties.path = folder
    with bpy.context.temp_override(window=win, area=area, region=region, screen=win.screen, scene=scene):
        bpy.ops.agr.run_calculate_all()
    area.spaces.active.show_region_ui = True
    for r in area.regions:
        if r.type == "UI":
            for cat in ("SINTEZ AGR",):  # panels.py bl_category
                try:
                    r.active_panel_category = cat
                    break
                except Exception:
                    pass
    print("GUI-AGR: check finished for", folder)
    return None


bpy.app.timers.register(run, first_interval=2.0)
