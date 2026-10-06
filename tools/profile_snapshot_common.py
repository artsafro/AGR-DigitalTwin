"""Native Blender snapshot primitives; no interactive process or source writes."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy


NUMERICAL_BUDGET = 1e-5
BUDGET_BASIS = "src/dt_ai/validate/bundle.py:triangle_signature rounds world/UV to 5 decimal places; serialization comparison only, not customer tolerance"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def request():
    if not bpy.app.background:
        raise RuntimeError('Snapshot adapters require an isolated background Blender process')
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) != 1 or not Path(args[0]).is_absolute():
        raise ValueError('Expected exactly one absolute config JSON path after --')
    return json.loads(Path(args[0]).read_text(encoding='utf-8'))


def absolute(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Config file paths must be absolute: ' + value)
    return path.resolve()


def image_facts(images):
    facts = []
    for image in images:
        path = Path(bpy.path.abspath(image.filepath, library=image.library))
        packed = bytes(image.packed_file.data) if image.packed_file else None
        facts.append({'name': image.name, 'source': image.source,
                      'path': str(path), 'size': list(image.size),
                      'packed_sha256': hashlib.sha256(packed).hexdigest() if packed else None,
                      'external_sha256': digest(path) if path.is_file() else None})
    return facts


def used_images(objects):
    images = {}
    for obj in objects:
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        images[node.image.name] = node.image
    return list(images.values())


def object_facts(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    uv_layers = list(mesh.uv_layers)
    active = mesh.uv_layers.active
    material_names = [slot.material.name if slot.material else None for slot in obj.material_slots]
    triangles = []
    degenerate = 0
    geometry_signatures = {}
    finish = mesh.attributes.get('finish_id')
    histogram = {}
    for polygon in mesh.polygons:
        key = str(len(polygon.vertices))
        histogram[key] = histogram.get(key, 0) + 1
    for tri in mesh.loop_triangles:
        polygon = mesh.polygons[tri.polygon_index]
        xyz = [list(obj.matrix_world @ mesh.vertices[mesh.loops[i].vertex_index].co) for i in tri.loops]
        uv = [list(active.data[i].uv) for i in tri.loops] if active else None
        a, b, c = [obj.matrix_world @ mesh.vertices[i].co for i in tri.vertices]
        area = (b - a).cross(c - a).length / 2
        if area == 0:
            degenerate += 1
        sig = tuple(sorted(tuple(point) for point in xyz))
        geometry_signatures[sig] = geometry_signatures.get(sig, 0) + 1
        triangles.append({'polygon_index': tri.polygon_index, 'positions': xyz, 'uv': uv,
                          'uv_layers': {layer.name: [list(layer.data[i].uv) for i in tri.loops] for layer in uv_layers},
                          'material_index': polygon.material_index,
                          'material': material_names[polygon.material_index] if polygon.material_index < len(material_names) else None,
                          'finish_id': finish.data[tri.polygon_index].value if finish and finish.domain == 'FACE' and finish.data_type == 'INT' else None})
    return {'name': obj.name, 'mesh': mesh.name, 'matrix_world': [list(row) for row in obj.matrix_world],
            'vertices': len(mesh.vertices), 'polygons': len(mesh.polygons), 'polygon_sizes': histogram,
            'triangles_count': len(triangles), 'materials': material_names,
            'uv_channels': len(uv_layers), 'active_uv': active.name if active else None,
            'exact_degenerate_triangles': degenerate,
            'exact_duplicate_surface_triangles': sum(n - 1 for n in geometry_signatures.values() if n > 1),
            'triangles': triangles}


def snapshot(objects):
    units = bpy.context.scene.unit_settings
    return {'blender': bpy.app.version_string, 'unit_system': units.system,
            'unit_scale': units.scale_length, 'objects': [object_facts(obj) for obj in objects],
            'images': image_facts(used_images(objects))}


def render_scope(objects, names):
    """Resolve the exact exported mesh scope before framing or rendering."""
    if not names or len(names) != len(set(names)):
        raise ValueError('Explicit nonempty unique mesh_names required')
    by_name = {obj.name: obj for obj in objects if obj.type == 'MESH'}
    if not set(names) <= set(by_name):
        raise ValueError('Render scope contains missing mesh objects')
    return [by_name[name] for name in names]


def orthographic_fit(x, y, aspect):
    """Fit projected points about the fixed camera target, including asymmetry."""
    if not x or not y or not math.isfinite(aspect) or aspect <= 0 or not all(math.isfinite(v) for v in [*x, *y]):
        raise ValueError('Finite projected points and positive aspect required')
    scale = 2 * max(max(abs(v) for v in x), max(abs(v) for v in y) * aspect) * 1.15
    if scale <= 0:
        raise ValueError('Degenerate projected bounds')
    return scale


def compare_triangles(expected, actual):
    """Finite, winding-preserving maximum matching within the numerical budget."""
    from collections import defaultdict, deque
    from itertools import product
    budget = NUMERICAL_BUDGET
    def valid(tri):
        def corners(value, dimensions):
            return len(value) == 3 and all(len(p) == dimensions and all(math.isfinite(c) for c in p) for p in value)
        try:
            return (corners(tri['positions'], 3) and
                    (tri['uv'] is None or corners(tri['uv'], 2)) and
                    all(corners(layer, 2) for layer in tri.get('uv_layers', {}).values()))
        except (TypeError, KeyError, ValueError, OverflowError):
            return False
    invalid_expected = sum(not valid(tri) for tri in expected)
    invalid_actual = sum(not valid(tri) for tri in actual)
    if invalid_expected or invalid_actual:
        return {'expected_triangles': len(expected), 'actual_triangles': len(actual),
                'unmatched_expected': len(expected), 'unmatched_actual': len(actual),
                'invalid_expected': invalid_expected, 'invalid_actual': invalid_actual,
                'max_matched_position_error': 0.0, 'max_matched_uv_error': 0.0, 'passed': False}
    buckets = defaultdict(list)
    def cell(tri):
        return tuple(math.floor(sum(p[d] for p in tri['positions']) / 3 / budget) for d in range(3))
    for index, tri in enumerate(actual):
        buckets[cell(tri)].append(index)
    candidates = []
    for wanted in expected:
        key = cell(wanted)
        compatible = {}
        for delta in product((-1, 0, 1), repeat=3):
            for index in buckets.get(tuple(a + b for a, b in zip(key, delta)), ()):
                got = actual[index]
                if (wanted['material'] != got['material'] or
                        wanted.get('material_index') != got.get('material_index') or
                        (wanted['uv'] is None) != (got['uv'] is None)):
                    continue
                for shift in range(3):
                    pe = max(abs(wanted['positions'][j][d] - got['positions'][(j + shift) % 3][d]) for j in range(3) for d in range(3))
                    ue = max(abs(wanted['uv'][j][d] - got['uv'][(j + shift) % 3][d]) for j in range(3) for d in range(2)) if wanted['uv'] is not None else 0.0
                    # FBX may rename UV channels, but their ordinal surface coordinates must survive.
                    wanted_layers = list(wanted.get('uv_layers', {}).values())
                    got_layers = list(got.get('uv_layers', {}).values())
                    if len(wanted_layers) != len(got_layers):
                        continue
                    for wl, gl in zip(wanted_layers, got_layers):
                        ue = max(ue, max(abs(wl[j][d] - gl[(j + shift) % 3][d]) for j in range(3) for d in range(2)))
                    if pe <= budget and ue <= budget:
                        compatible[index] = (index, pe, ue)
                        break
        candidates.append(dict(sorted(compatible.items(), key=lambda item: (item[1][1], item[1][2], item[0]))))
    # Augmenting paths allow an earlier ambiguous choice to be reassigned.
    # Iterative BFS avoids recursion limits on duplicate/near-identical surfaces.
    matches, owners = {}, {}
    for start in range(len(expected)):
        queue, seen_expected, parent_actual = deque([start]), {start}, {}
        free = None
        while queue and free is None:
            wanted_index = queue.popleft()
            for actual_index in candidates[wanted_index]:
                if actual_index in parent_actual:
                    continue
                parent_actual[actual_index] = wanted_index
                if actual_index not in owners:
                    free = actual_index
                    break
                previous = owners[actual_index]
                if previous not in seen_expected:
                    seen_expected.add(previous)
                    queue.append(previous)
        while free is not None:
            wanted_index = parent_actual[free]
            old = matches.get(wanted_index)
            matches[wanted_index] = candidates[wanted_index][free]
            owners[free] = wanted_index
            free = old[0] if old else None
    unmatched = len(expected) - len(matches)
    return {'expected_triangles': len(expected), 'actual_triangles': len(actual),
            'unmatched_expected': unmatched, 'unmatched_actual': len(actual) - len(owners),
            'max_matched_position_error': max((m[1] for m in matches.values()), default=0.0),
            'max_matched_uv_error': max((m[2] for m in matches.values()), default=0.0),
            'passed': unmatched == 0 and len(owners) == len(actual)}
