"""Capture unique source definitions and embedded maps, through read-only commands."""
import asyncio
import base64
import hashlib
import json
import sys
from collections import deque
from pathlib import Path
from sketchup_mcp.connection import SketchUpConnection

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'jobs/GLB-NPM/outputs/source-live-v001'

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'definitions').mkdir(exist_ok=True)
    (OUT/'textures').mkdir(exist_ok=True)
    c=SketchUpConnection('127.0.0.1',9876,45)
    async def call(name,args):
        raw=await c.send_command(name,args)
        if raw.get('isError'):raise RuntimeError(raw)
        return json.loads(raw['content'][0]['text'])
    try:
        scene=await call('get_source_scene',{})
        if Path(scene['path']).name!='ГЛБ для НПМ.skp':raise RuntimeError('Wrong model')
        resume='--textures-only' in sys.argv
        if resume:
            prior=json.loads((OUT/'scene.json').read_text(encoding='utf-8'))
            assert all(prior[k]==scene[k] for k in ('path','guid','root_count','definitions')), 'Source metadata changed; recapture into a new version'
        else:
            write(OUT/'scene.json',scene)
        root=await call('get_source_entities',{'limit':200})
        write(OUT/'root.json',root)
        towers=[e for e in root['entities'] if e.get('layer') in ['Корпус 1','Корпус 2'] and 'definition_id' in e]
        assert len(towers)==2
        write(OUT/'towers.json',towers)
        queue=deque(e['definition_id'] for e in towers)
        seen=set(); total_faces=0
        while queue:
            did=queue.popleft()
            if did in seen:continue
            seen.add(did)
            path=OUT/'definitions'/f'{did}.json'
            entities=[]
            if resume:
                entities=json.loads(path.read_text(encoding='utf-8'))['entities']
            else:
                while True:
                    page=await call('get_source_entities',{'definition_id':did,'offset':len(entities),'limit':200})
                    entities.extend(page['entities'])
                    if not page['more']:break
                write(path,{'definition_id':did,'entities':entities})
            total_faces+=sum(e['type']=='Face' for e in entities)
            queue.extend(e['definition_id'] for e in entities if 'definition_id' in e)
            if len(seen)%20==0:print(json.dumps({'definitions':len(seen),'pending':len(queue),'unique_faces':total_faces}),flush=True)
        materials=await call('get_materials',{'limit':200})
        write(OUT/'materials.json',materials)
        texture_manifest=[]
        for i,mat in enumerate(materials['items']):
            if not mat['texture']:continue
            for colorized in [False,True]:
                data=await call('get_source_texture',{'name':mat['name'],'colorized':colorized})
                binary=base64.b64decode(data.pop('png_base64'),validate=True)
                assert binary.startswith(b'\x89PNG\r\n\x1a\n')
                filename=f'mat_{i:02d}_{"colorized" if colorized else "raw"}.png'
                (OUT/'textures'/filename).write_bytes(binary)
                data.update(file=filename,material_index=i,sha256=hashlib.sha256(binary).hexdigest())
                texture_manifest.append(data)
            print('texture '+str(i)+' captured',flush=True)
        write(OUT/'textures/manifest.json',texture_manifest)
        end=await call('get_source_scene',{})
        write(OUT/'scene-after.json',end)
        signature=lambda s:(s['path'],s['guid'],s['root_count'],s['definitions'])
        assert signature(scene)==signature(end),'Model structural metadata changed during capture'
        report={'definitions':len(seen),'unique_definition_faces':total_faces,'texture_files':len(texture_manifest),
                'source_path':scene['path'],'source_modified':scene['modified'],
                'metadata_stable_during_capture':True,'atomic_snapshot':False,'model_write_commands':0}
        write(OUT/'capture-report.json',report)
        print(json.dumps(report,ensure_ascii=True))
    finally:await c.aclose()

if __name__=='__main__':asyncio.run(main())
