"""Explicit measured grid/window selection -> new exterior-surface artifacts."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dt_ai.geometry.exterior import extract_exterior
from dt_ai.core.io import read_json, write_json
from dt_ai.core.adapter_report import AdapterReport, Check
from check_shell_windows import audit


def run(config_path, output):
    c=read_json(config_path.read_bytes())
    if not c.get('selection_basis') or not c.get('tolerance_basis'):
        raise ValueError('Explicit selection and tolerance decision references required')
    paths={k:(config_path.parent/c[k]).resolve() for k in ('grid_npz','source_json','owner_registry_json')}
    with np.load(paths['grid_npz'],allow_pickle=False) as archive:
        data={k:archive[k] for k in archive.files}
    source=read_json(paths['source_json'].read_bytes())
    ids=c['window_ids']
    if not isinstance(ids,list) or any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('window_ids must be an explicit unique string list')
    selected={i:[] for i in ids}
    for item in source['items']:
        identity=item['props'].get('revit_element_id')
        if identity in selected:selected[identity].append(item)
    if any(len(items)!=1 for items in selected.values()):
        raise ValueError('Missing or ambiguous selected source ID')
    angle=float(data['angle']);R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    windows=[]
    for identity,items in selected.items():
        v=np.array(items[0]['vertices'],dtype=float);v[:,:2]=v[:,:2]@R
        windows.append({'id':identity,'min':v.min(0),'max':v.max(0)})
    arrays,report=extract_exterior(data,windows,**c['parameters'])
    report['angle_rad']=angle
    report['owner_registry']=str(paths['owner_registry_json'])
    qa=audit({'angle':angle,'windows':[],'meshes':[{'vertices':arrays['vertices'].tolist(),'faces':arrays['faces'].tolist()}]})
    output.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output/'exterior-surface.npz',**arrays)
    write_json(output/'exterior-surface.json',report)
    write_json(output/'geometry-qa.json',qa)
    write_json(output/'inputs.json',{'config':c,'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [config_path,*paths.values()]},
        'implementation_sha256':{name:hashlib.sha256((Path(__file__).resolve().parents[1]/name).read_bytes()).hexdigest() for name in ['src/dt_ai/geometry/exterior.py','src/dt_ai/geometry/grid_patches.py']}})
    with np.load(output/'exterior-surface.npz',allow_pickle=False) as saved:
        same=all(np.array_equal(saved[k],v) for k,v in arrays.items())
    result=AdapterReport(operation='extract-exterior',tool_version='prototype-1',
        scope='Prepared measured orthogonal grid -> outer perimeter and openings; not live RVT import',
        execution='completed',input_manifest=str(output/'inputs.json'),output_manifest=str(output/'exterior-surface.json'),
        checks=(Check(id='geometry',status='pass' if qa['geometry_checks_passed'] else 'fail',evidence=str(output/'geometry-qa.json')),
                Check(id='npz_readback',status='pass' if same else 'fail',evidence=str(output/'exterior-surface.npz')),
                Check(id='dcc_profile_readback',status='not_run',evidence='Run exterior_adapter_blender.py and check_exterior_surface.py')),
        pending_decisions=('Review perimeter/opening and wall-top interpretation for this output',),
        limitations=('One orthogonal outer perimeter only; courtyard facades omitted', 'Second project untested','Raw source grid construction remains separate'))
    write_json(output/'report.json',result.model_dump(mode='json'))
    print(json.dumps(result.summary()))
    return qa['geometry_checks_passed'] and same


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();sys.exit(0 if run(a.config.resolve(),a.output.resolve()) else 1)
