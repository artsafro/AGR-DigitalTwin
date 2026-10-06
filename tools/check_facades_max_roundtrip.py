"""Read FBX exported by live Max and compare all corner UV/positions to Blender."""
import bpy,json,sys
from pathlib import Path
import numpy as np
from mathutils.kdtree import KDTree
from collections import Counter
out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.import_scene.fbx(filepath=str(out/'max_roundtrip.fbx'))
reference=json.loads((out/'blender-reference.json').read_text());report={}
for name,ref in reference.items():
    o=bpy.data.objects[name];m=o.data;uv=m.uv_layers[0]
    corners=np.array([[*(o.matrix_world@m.vertices[m.loops[i].vertex_index].co),*uv.data[i].uv] for p in m.polygons for i in p.loop_indices])
    expected=np.array(ref['corners']);tree=KDTree(len(expected))
    for i,c in enumerate(expected):tree.insert(c[:3],i)
    tree.balance();max_pos=0.;max_uv=0.
    for c in corners:
        candidates=tree.find_range(c[:3],.002)
        assert candidates,(name,c.tolist())
        best=min(candidates,key=lambda item:np.max(abs(expected[item[1],3:]-c[3:])))
        max_uv=max(max_uv,float(np.max(abs(expected[best[1],3:]-c[3:]))));max_pos=max(max_pos,best[2])
    assert max_uv<2e-6,(name,max_uv)
    assert len(m.polygons)==ref['faces']
    assert dict(Counter(str(len(p.vertices)) for p in m.polygons))==ref['degrees']
    report[name]={'faces':len(m.polygons),'corners_checked':len(corners),'max_uv_error':max_uv,'max_position_error_m':max_pos,'polygon_degrees_preserved':True}
(out/'max-roundtrip-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
