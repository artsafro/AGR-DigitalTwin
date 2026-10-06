"""Read-only component inventory and reference views for the GLB NPM job."""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
from sketchup_mcp.connection import SketchUpConnection

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'jobs/GLB-NPM/outputs/audit-v001'

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    conn = SketchUpConnection('127.0.0.1',9876,45)
    async def call(name,args):
        raw = await conn.send_command(name,args)
        if raw.get('isError'): raise RuntimeError(raw)
        return json.loads(raw['content'][0]['text'])
    try:
        model = await call('get_model_info',{})
        if Path(model['path']).name != 'ГЛБ для НПМ.skp':
            raise RuntimeError('Wrong active model')
        (OUT/'model.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
        for tool in ['get_materials','list_layers']:
            data=await call(tool,{'limit':200})
            (OUT/(tool+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        items=[]
        offset=0
        while True:
            page=await call('list_components',{'recursive':True,'max_depth':2,'limit':500,'offset':offset})
            items.extend(page['components'])
            (OUT/'components-depth2.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'offset':offset,'total':page['total']},ensure_ascii=True),flush=True)
            if not page['truncated']: break
            offset+=len(page['components'])
            if offset>=15000: raise RuntimeError('Bound reached; inspect existing pages')
        (OUT/'components-depth2.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
        for view in ['front','right','top','iso']:
            data=await call('get_viewport_screenshot',{'max_size':1800,'view_preset':view,'style':'default','zoom_extents':True,'restore_view':True})
            binary=base64.b64decode(data.pop('png_base64'),validate=True)
            (OUT/(view+'.png')).write_bytes(binary)
            (OUT/(view+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        with Path(model['path']).open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        (OUT/'source.json').write_text(json.dumps({'path':model['path'],'disk_sha256':digest,'unsaved_scene_may_differ':True,'read_only':True},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'output':str(OUT),'components':len(items)},ensure_ascii=True))
    finally:
        await conn.aclose()

if __name__=='__main__': asyncio.run(main())
