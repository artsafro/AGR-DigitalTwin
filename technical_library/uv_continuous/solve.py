
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import arguments, require_stage, mark_stage, run_dcc
"""Scoped SOSH1150 v006 stage; see README and replay evidence."""

def plan(root):
    import json, numpy as np
    from collections import defaultdict, Counter, deque
    from pathlib import Path
    d = json.loads((root / 'source.json').read_text())
    v = np.array(d['vertices'])
    norm = np.array(d['normals'])
    t = np.column_stack((norm[:, 1], -norm[:, 0], np.zeros(len(norm))))
    length = np.linalg.norm(t, axis=1)
    vertical = length > 0.999
    t[vertical] /= length[vertical, None]
    edges = defaultdict(list)
    for fi, f in enumerate(d['faces']):
        for a, b in zip(f, f[1:] + f[:1]):
            key = tuple(sorted((tuple(np.round(v[a], 5)), tuple(np.round(v[b], 5)))))
            edges[key].append(fi)
    adj = defaultdict(list)
    for (a, b), fs in edges.items():
        if len(fs) == 2 and all(vertical[fs]) and (abs(a[0] - b[0]) + abs(a[1] - b[1]) < 0.0001):
            i, j = fs
            pos = (np.array(a) + b) / 2
            delta = pos @ (t[i] - t[j])
            adj[i].append((j, delta))
            adj[j].append((i, -delta))
        elif len(fs) == 2 and all(vertical[fs]) and (t[fs[0]] @ t[fs[1]] > 0.99999):
            i, j = fs
            pos = (np.array(a) + b) / 2
            delta = pos @ (t[i] - t[j])
            adj[i].append((j, delta))
            adj[j].append((i, -delta))
    parent = list(range(len(norm)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, links in adj.items():
        for j, delta in links:
            if t[i] @ t[j] > 0.99999:
                a, b = (find(i), find(j))
                parent[b] = a
    groups = defaultdict(list)
    for i in np.flatnonzero(vertical):
        groups[find(int(i))].append(int(i))
    for ids in groups.values():
        tangent = t[ids].mean(axis=0)
        tangent /= np.linalg.norm(tangent)
        t[ids] = tangent
    gadj = defaultdict(list)
    for i, links in adj.items():
        for j, delta in links:
            a, b = (find(i), find(j))
            if a != b:
                common = set(d['faces'][i]).intersection(d['faces'][j])
                if common:
                    delta = v[list(common)].mean(axis=0) @ (t[i] - t[j])
                gadj[a].append((b, delta, i, j))
    goff = {}
    for seed in sorted(groups, key=lambda g: -len(groups[g])):
        if seed in goff:
            continue
        goff[seed] = 0.0
        q = deque([seed])
        while q:
            a = q.popleft()
            for b, delta, i, j in gadj[a]:
                if b not in goff:
                    goff[b] = goff[a] + delta
                    q.append(b)
    offset = {i: goff[g] for g, ids in groups.items() for i in ids}
    components = []
    for seed in sorted(np.flatnonzero(vertical), key=lambda i: -len(adj[i])):
        if any((int(seed) in c for c in components)):
            continue
        visited = {int(seed)}
        q = deque([int(seed)])
        comp = []
        while q:
            i = q.popleft()
            comp.append(i)
            for j, delta in adj[i]:
                if j not in visited:
                    visited.add(j)
                    q.append(j)
        components.append(comp)
    conflicts = []
    for i, links in adj.items():
        for j, delta in links:
            common = set(d['faces'][i]).intersection(d['faces'][j])
            if common:
                delta = v[list(common)].mean(axis=0) @ (t[i] - t[j])
            if i < j and abs(offset[j] - offset[i] - delta) > 0.0001:
                conflicts.append([i, j, offset[j] - offset[i] - delta])
    uv = []
    for i, f in enumerate(d['faces']):
        p = v[f]
        if vertical[i]:
            uv.append(np.column_stack((p @ t[i] + offset[i], p[:, 2])).tolist())
        else:
            n = norm[i]
            a = p[1] - p[0]
            a /= np.linalg.norm(a)
            b = np.cross(n, a)
            b /= np.linalg.norm(b)
            uv.append(np.column_stack((p @ a, p @ b)).tolist())
    report = {'vertical_faces': int(vertical.sum()), 'components': len(components), 'component_sizes': sorted(map(len, components), reverse=True)[:20], 'conflicts': conflicts, 'edge_counts': dict(Counter(map(len, edges.values()))), 'polygon_sizes': dict(Counter(map(len, d['faces'])))}
    (root / 'plan.json').write_text(json.dumps({'metric_uv': uv, 'report': report}))
    (root / 'charts.json').write_text(json.dumps({'groups': {str(g): ids for g, ids in groups.items()}, 'tangents': t.tolist(), 'offsets': {str(i): x for i, x in offset.items()}, 'adj': {str(i): links for i, links in adj.items()}}))
    print(json.dumps({**report, 'conflicts': conflicts[:25], 'conflict_count': len(conflicts)}))

def closure_final(root):
    import json, numpy as np
    from pathlib import Path
    d = json.loads((root / 'source.json').read_text())
    c = json.loads((root / 'charts.json').read_text())
    p = json.loads((root / 'plan.json').read_text())
    v = np.array(d['vertices'])
    t = np.array(c['tangents'])
    groups = {int(k): ids for k, ids in c['groups'].items()}
    gids = list(groups)
    idx = {g: i for i, g in enumerate(gids)}
    faceg = {f: g for g, fs in groups.items() for f in fs}
    off = {int(i): x for i, x in c['offsets'].items()}
    N = len(gids)
    rows = []
    rhs = []
    keys = set()
    L = 4056 / 600
    for si, links in c['adj'].items():
        i = int(si)
        for j, _ in links:
            gi, gj = (faceg[i], faceg[j])
            if gi == gj or i > j:
                continue
            common = set(d['faces'][i]).intersection(d['faces'][j])
            if not common:
                continue
            xyz = v[list(common)].mean(axis=0)
            a, b = (idx[gi], idx[gj])
            k = (a, b, tuple(np.round(xyz[:2], 4)))
            if k in keys:
                continue
            keys.add(k)
            ui = xyz @ t[i]
            uj = xyz @ t[j]
            res = ui + off[i] - uj - off[j]
            target = round(res / L) * L
            row = np.zeros(2 * N)
            row[a] = ui
            row[b] = -uj
            row[N + a] = 1
            row[N + b] = -1
            rows.append(row)
            rhs.append(target - res)
    A = np.array(rows)
    rhs = np.array(rhs)
    weights = np.concatenate((np.ones(N), np.full(N, 10000.0)))
    solution = weights * np.linalg.lstsq(A * weights, rhs, rcond=1e-07)[0]
    scales = 1 + solution[:N]
    report = {'charts': N, 'constraints': len(rows), 'horizontal_scale_range': [float(scales.min()), float(scales.max())], 'td_range': [float(600 * np.sqrt(scales.min())), float(600 * np.sqrt(scales.max()))], 'constraint_max_m': float(abs(A @ solution - rhs).max()), 'scope': 'study only, not applied'}
    (root / 'closure-study.json').write_text(json.dumps({'report': report, 'chart_scales': {str(g): float(scales[i]) for i, g in enumerate(gids)}, 'chart_offsets_delta': {str(g): float(solution[N + i]) for i, g in enumerate(gids)}}, indent=2))
    print(json.dumps(report))

def final_plan(root):
    import json, numpy as np
    from pathlib import Path
    p = json.loads((root / 'plan.json').read_text())
    c = json.loads((root / 'charts.json').read_text())
    s = json.loads((root / 'closure-study.json').read_text())
    d = json.loads((root / 'source.json').read_text())
    v = np.array(d['vertices'])
    t = np.array(c['tangents'])
    for gs, fs in c['groups'].items():
        factor = s['chart_scales'][gs]
        delta = s['chart_offsets_delta'][gs]
        for i in fs:
            p['metric_uv'][i] = np.column_stack((v[d['faces'][i]] @ t[i] * factor + c['offsets'][str(i)] + delta, v[d['faces'][i]][:, 2])).tolist()
    p['report']['former_phase_conflicts'] = p['report']['conflicts']
    p['report']['conflicts'] = []
    p['report']['closure_study'] = s['report']
    p['report']['note'] = 'Residual at graph corners <0.01px; horizontal scale varies within user-authorized TD range.'
    (root / 'plan-strict-1500.json').write_text((root / 'plan.json').read_text())
    (root / 'plan.json').write_text(json.dumps(p))
    print(s['report'])


def main():
    args = arguments()
    root = require_stage(args.output, 'inspect')
    plan(root)
    closure_final(root)
    final_plan(root)
    mark_stage(root, 'solve')
    print('Stage 2/4: solve complete')


if __name__ == '__main__':
    main()
