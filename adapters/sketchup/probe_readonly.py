"""Read live SketchUp state and save evidence; never modify or save the model."""
import asyncio
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from sketchup_mcp.connection import SketchUpConnection

ROOT = Path(__file__).resolve().parent


async def main():
    output = ROOT / 'verification' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir(parents=True, exist_ok=False)
    conn = SketchUpConnection('127.0.0.1', 9876, 30)
    report = {}
    try:
        for name, args in [
            ('get_version', {}), ('get_model_info', {}),
            ('list_components', {'recursive': False, 'limit': 50}),
            ('get_materials', {'limit': 50}),
            ('get_viewport_screenshot', {'max_size': 1600, 'view_preset': 'current',
                                         'style': 'default', 'zoom_extents': False,
                                         'restore_view': True}),
        ]:
            raw = await conn.send_command(name, args)
            if raw.get('isError'):
                raise RuntimeError(raw)
            data = json.loads(raw['content'][0]['text'])
            if name == 'get_viewport_screenshot':
                for key in list(data):
                    if 'base64' in key or key in ('data', 'image'):
                        if isinstance(data[key], str):
                            binary = base64.b64decode(data[key], validate=True)
                            assert binary.startswith(b'\x89PNG\r\n\x1a\n')
                            (output / 'viewport.png').write_bytes(binary)
                            data[key] = '<saved as viewport.png>'
            report[name] = data
            (output / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        path = Path(report['get_model_info']['path'])
        report['source_disk_sha256'] = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        report['source_hash_scope'] = 'Saved disk file only; unsaved session may differ.'
        report['model_mutations_requested'] = False
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'output':str(output), 'model':report['get_model_info'],
                          'material_total':report['get_materials']['total'],
                          'screenshot_keys':list(report['get_viewport_screenshot'])}, ensure_ascii=True))
    finally:
        await conn.aclose()


if __name__ == '__main__':
    asyncio.run(main())
