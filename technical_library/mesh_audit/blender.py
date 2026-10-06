"""Inventory saved blend/FBX in background Blender without editing its mesh."""
import argparse,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import inspect_mesh


def main():
    import bpy
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--object',action='append',default=[])
    parser.add_argument('--collection',action='append',default=[])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    source=args.source.resolve()
    if args.output.exists():parser.error('Report exists; refusing overwrite')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if source.suffix.lower()=='.blend':bpy.ops.wm.open_mainfile(filepath=str(source))
    elif source.suffix.lower()=='.fbx':
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(source),use_image_search=False)
    else:parser.error('Only saved blend/FBX supported')
    for name in args.object:
        if bpy.data.objects.get(name) is None:parser.error('Object not found: '+name)
    for name in args.collection:
        if bpy.data.collections.get(name) is None:parser.error('Collection not found: '+name)
    selected={o.name for name in args.collection for o in bpy.data.collections[name].all_objects}
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and
             (not args.object or o.name in args.object) and (not args.collection or o.name in selected)]
    if not objects:parser.error('Selection has no mesh objects')
    unit=bpy.context.scene.unit_settings.scale_length;rows=[]
    for obj in sorted(objects,key=lambda o:o.name):
        mesh=obj.data
        vertices=[list((obj.matrix_world@v.co)*unit) for v in mesh.vertices]
        faces=[list(p.vertices) for p in mesh.polygons]
        row=inspect_mesh(vertices,faces,[list(e.vertices) for e in mesh.edges],[p.material_index for p in mesh.polygons])
        row.update(name=obj.name,materials=[m.name if m else None for m in mesh.materials],uv_layers=[])
        for layer in mesh.uv_layers:
            values=[tuple(v.uv) for v in layer.data];finite=all(math.isfinite(c) for uv in values for c in uv)
            row['uv_layers'].append({'name':layer.name,'loops':len(values),'finite':finite,
              'bounds':[min(c for uv in values for c in uv),max(c for uv in values for c in uv)] if values and finite else None})
        rows.append(row)
    unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==digest
    if not unchanged:raise RuntimeError('Source changed during read-only audit')
    report={'source_filename':source.name,'source_sha256':digest,'source_unchanged':unchanged,
      'blender_version':bpy.app.version_string,'unit_scale':unit,'objects':rows,
      'collections':{name:{'meshes':sum(o.type=='MESH' for o in bpy.data.collections[name].all_objects)} for name in args.collection},
      'scope':'Raw saved meshes; modifiers/visual acceptance/intersections not certified',
      'native_max_verified':False,'delivery_passed':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({'mesh_objects':len(rows),'faces':sum(r['faces'] for r in rows),'source_unchanged':unchanged}))


if __name__=='__main__':main()
