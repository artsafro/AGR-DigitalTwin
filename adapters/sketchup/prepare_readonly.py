"""Build a restricted upstream bridge: no eval, model writes or arbitrary exports."""
from pathlib import Path
import hashlib
import json
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'vendor/sketchup-mcp2/mcp_for_sketchup'
STAGE = ROOT / 'dist/readonly'
ALLOWED = ['get_model_info', 'list_components', 'get_component_info',
           'find_components', 'list_layers', 'get_selection',
           'get_viewport_screenshot', 'get_version', 'get_materials',
           'get_source_scene', 'get_source_entities', 'get_source_texture']


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC / 'mcp_for_sketchup', STAGE / 'mcp_for_sketchup', dirs_exist_ok=True)
    shutil.copyfile(SRC / 'mcp_for_sketchup.rb', STAGE / 'mcp_for_sketchup.rb')
    base = STAGE / 'mcp_for_sketchup'
    # Remove whole implementations, not merely their tool descriptions.
    removed = ['geometry', 'operations', 'joints', 'materials', 'export', 'eval']
    for name in removed:
        (base / f'handlers/{name}.rb').unlink(missing_ok=True)
    dispatch = base / 'handlers/dispatch.rb'
    body = dispatch.read_text(encoding='utf-8')
    lines = body.splitlines()
    lines = [s for s in lines if not (s.strip().startswith('when "') and 'Handlers::' in s
             and not any(f'"{name}"' in s for name in ALLOWED))]
    body = '\n'.join(lines) + '\n'
    body = body.replace('        case tool\n',
        '        if tool == "get_viewport_screenshot"\n'
        '          params = params.merge("restore_view" => true)\n'
        '        end\n        case tool\n'
        '        when "get_materials" then Handlers::Inspection.get_materials(params)\n'
        '        when "get_source_scene" then Handlers::Inspection.get_source_scene(params)\n'
        '        when "get_source_entities" then Handlers::Inspection.get_source_entities(params)\n'
        '        when "get_source_texture" then Handlers::Inspection.get_source_texture(params)\n')
    dispatch.write_text(body, encoding='utf-8')
    config = base / 'core/config.rb'
    body = config.read_text(encoding='utf-8').replace('eval_enabled:   true', 'eval_enabled:   false')
    start = body.index('      def self.eval_enabled?')
    end = body.index('\n      def self.level_value', start)
    body = body[:start] + '      def self.eval_enabled?\n        false\n      end\n' + body[end:]
    config.write_text(body, encoding='utf-8')
    mainfile = base / 'main.rb'
    body = mainfile.read_text(encoding='utf-8')
    for name in removed:
        body = body.replace(f'    handlers/{name}\n', '')
    body = body.replace('    ui/settings_validator\n', '').replace('    ui/settings_dialog\n', '')
    body = body.replace('    handlers/system\n', '    handlers/system\n    handlers/inspection\n')
    body = body.replace('  MCPforSketchUp::Core::Config.load_from_defaults!\n',
        '  MCPforSketchUp::Core::Config.load_from_defaults!\n'
        '  MCPforSketchUp::Core::Config.host = "127.0.0.1"\n'
        '  MCPforSketchUp::Core::Config.port = 9876\n'
        '  MCPforSketchUp::Core::Config.eval_enabled = false\n')
    body = '\n'.join(s for s in body.splitlines() if 'SettingsDialog.show' not in s) + '\n'
    body = body.replace('add_submenu("MCP Server")', 'add_submenu("MCP Server (Read Only)")')
    mainfile.write_text(body, encoding='utf-8')
    shutil.copyfile(ROOT / 'inspection.rb', base / 'handlers/inspection.rb')
    loader = STAGE / 'mcp_for_sketchup.rb'
    body = loader.read_text(encoding='utf-8').replace("'MCP Server for SketchUp'", "'MCP Server for SketchUp (Read Only)'")
    loader.write_text(body, encoding='utf-8')
    files = sorted(p for p in STAGE.rglob('*') if p.is_file())
    archive_path = ROOT / 'dist/mcp_for_sketchup_readonly_v0.3.1.rbz'
    with ZipFile(archive_path, 'w', ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, path.relative_to(STAGE).as_posix())
    with ZipFile(archive_path) as z:
        assert z.testzip() is None
        for path in files:
            assert z.read(path.relative_to(STAGE).as_posix()) == path.read_bytes()
    assert 'Handlers::Eval' not in dispatch.read_text(encoding='utf-8')
    report = {'allowed_tools': ALLOWED, 'files': len(files), 'eval_enabled': False,
              'model_mutations': False, 'host': '127.0.0.1',
              'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
              'archive_readback': True}
    (ROOT / 'dist/readonly-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
