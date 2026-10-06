"""Run only with 3dsmaxbatch.exe, -mxsString config:ABS_CONFIG.json.

No existing UI scene is loaded or reset. Import/re-export actual extracted FBX.
"""
import hashlib
import json
import os
from pathlib import Path
import pymxs

rt=pymxs.runtime


def main():
    config_path=Path(str(rt.execute('maxOps.mxsCmdLineArgs[#config]')))
    if not config_path.is_absolute():
        raise ValueError('Absolute config path required')
    config=json.loads(config_path.read_text(encoding='utf-8'))
    source=Path(config['fbx']).resolve()
    output=Path(config['output_dir']).resolve()
    output.mkdir(parents=True,exist_ok=True)
    result=output/'max-native.json'
    target=output/'max-roundtrip.fbx'
    scene=output/'max-import.max'
    if any(p.exists() for p in (result,target,scene)):
        raise FileExistsError('Fresh Max output required')
    evidence={'application':'3ds Max','pid':os.getpid(),'source':str(source),
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'version':str(rt.maxVersion()),'delivery_passed':False,'failures':[]}
    try:
        if len(rt.objects) or str(rt.maxFileName):
            raise RuntimeError('Batch process is not empty; no reset of an existing scene allowed')
        rt.units.SystemType=rt.Name('meters')
        rt.FBXImporterSetParam('Mode','create')
        if not rt.importFile(str(source),rt.Name('noPrompt'),using=rt.FBXIMP):
            raise RuntimeError('Native Max FBX import failed')
        objects=list(rt.geometry)
        evidence['objects']=[{'name':str(o.name),'class':str(rt.classOf(o)),
                             'material':str(o.material.name) if o.material else None,
                             'vertices':int(rt.getNumVerts(rt.snapshotAsMesh(o))),
                             'triangles':int(rt.getNumFaces(rt.snapshotAsMesh(o)))} for o in objects]
        evidence['unit_system']=str(rt.units.SystemType)
        rt.saveMaxFile(str(scene),quiet=True)
        rt.FBXExporterSetParam('Animation',False)
        rt.FBXExporterSetParam('EmbedTextures',True)
        rt.FBXExporterSetParam('ASCII',False)
        rt.FBXExporterSetParam('FileVersion','FBX201400')
        rt.FBXExporterSetParam('UpAxis','Z')
        rt.FBXExporterSetParam('SelectionSetExport',False)
        rt.FBXExporterSetParam('Cameras',False)
        rt.FBXExporterSetParam('Lights',False)
        if not rt.exportFile(str(target),rt.Name('noPrompt'),selectedOnly=False,using=rt.FBXEXP):
            raise RuntimeError('Native Max FBX reverse export failed')
        evidence['output_fbx']={'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        evidence['output_max']={'path':str(scene),'sha256':hashlib.sha256(scene.read_bytes()).hexdigest()}
    except Exception as exc:
        evidence['failures'].append(type(exc).__name__+': '+str(exc))
    evidence['operation_completed']=not evidence['failures']
    result.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MAX_COMPONENT_ROUNDTRIP',evidence['operation_completed'])
    if evidence['failures']:
        raise RuntimeError('; '.join(evidence['failures']))


main()
