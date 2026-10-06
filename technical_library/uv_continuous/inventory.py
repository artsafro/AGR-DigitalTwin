"""Scoped SOSH1150 v006 stage; see README and replay evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PIPELINE, arguments

def inventory(root):
    import bpy, json
    from pathlib import Path
    o = bpy.context.active_object
    m = o.data
    if not (root / 'source_v001.blend').exists():
        bpy.ops.wm.save_as_mainfile(filepath=str(root / 'source_v001.blend'), copy=True)
    m.calc_loop_triangles()
    r = {'name': o.name, 'matrix': [list(x) for x in o.matrix_world], 'vertices': [list(o.matrix_world @ v.co) for v in m.vertices], 'faces': [list(p.vertices) for p in m.polygons], 'normals': [list(p.normal) for p in m.polygons], 'materials': [p.material_index for p in m.polygons], 'slots': [x.name if x else None for x in m.materials], 'uv': [[list(m.uv_layers.active.data[i].uv) for i in p.loop_indices] for p in m.polygons], 'images': [{'name': i.name, 'path': i.filepath, 'size': list(i.size)} for i in bpy.data.images], 'nodes': {mat.name: [{'type': n.type, 'image': n.image.name if n.type == 'TEX_IMAGE' and n.image else None} for n in mat.node_tree.nodes] for mat in m.materials if mat and mat.use_nodes}}
    r['triangles'] = [{'face': t.polygon_index, 'vertices': list(t.vertices)} for t in m.loop_triangles]
    (root / 'source.json').write_text(json.dumps(r), encoding='utf-8')
    print(json.dumps({'slots': r['slots'], 'images': r['images'], 'nodes': r['nodes']}))


def main():
    import bpy, hashlib, json, shutil
    args = arguments(scene=True)
    for source in [args.source_blend, args.diffuse]:
        if not source.is_file():
            raise ValueError('Input file not found')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.diffuse, root / 'T_Template_Address_001_Diffuse_1.1001.png')
    bpy.ops.wm.open_mainfile(filepath=str(args.source_blend.resolve()))
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH' or len(obj.data.polygons) != 8755:
        raise ValueError('This replay requires the scoped 8755-face SOSH1150 source')
    inventory(root)
    state = {'pipeline': PIPELINE, 'stage': 'inspect', 'input_sha256': {
        'source_v001.blend': hashlib.sha256(args.source_blend.read_bytes()).hexdigest(),
        'T_Template_Address_001_Diffuse_1.1001.png': hashlib.sha256(args.diffuse.read_bytes()).hexdigest()}}
    (root / 'PIPELINE.json').write_text(json.dumps(state, indent=2))
    print('Stage 1/4: inspect complete')


if __name__ == '__main__':
    main()
