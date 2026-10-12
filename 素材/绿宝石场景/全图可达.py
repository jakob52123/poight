"""Reachability graph with original interior warps and registered offset seams."""
import base64
from collections import deque

from 自由探索 import BEHAVIORS, legal


def graph_for(catalog):
    graph, offsets, decoded = {}, {}, {}
    cursor = 0
    for t in catalog['terrains']:
        offsets[t['id']] = cursor
        decoded[t['id']] = [base64.b64decode(t[k + 'B64'])
                            for k in ('walk', 'water', 'behavior', 'elevation')]
        cursor += t['columns'] * t['rows']
    scenes = {s['id']: s['terrainID'] for s in catalog['scenes']}
    for t in catalog['terrains']:
        off, n = offsets[t['id']], t['columns']
        walk, water, behavior, elevation = decoded[t['id']]
        both = set(t.get('bidirectionalLedges', []))
        seam_links = {}
        for e in t.get('seams', []):
            if any(e['shift']):
                dx, dy = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[e['direction']]
                for x, y, xx, yy in e['pairs']:
                    seam_links[(y * n + x, dx, dy)] = yy * n + xx
        for a in range(len(walk)):
            if not (walk[a] or water[a]):
                continue
            out = graph[off + a] = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                x, y = a % n + dx, a // n + dy
                if not (0 <= x < n and 0 <= y < t['rows']):
                    continue
                b = seam_links.get((a, dx, dy), y * n + x)
                if (walk[b] or water[b]) and legal(a, b, n, behavior, elevation, water, both):
                    out.append(off + b)
        for warp in t.get('warps', []):
            other = next(v for v in catalog['terrains'] if v['id'] == scenes[warp['destScene']])
            dest = int(warp['y'] // t['cellSize']) * other['columns'] + int(warp['x'] // t['cellSize'])
            graph.setdefault(off + warp['row'] * n + warp['col'], []).append(offsets[other['id']] + dest)
    return graph, offsets, decoded


def flood(graph, start):
    seen, q = {start}, deque([start])
    while q:
        for b in graph.get(q.popleft(), []):
            if b not in seen:
                seen.add(b)
                q.append(b)
    return seen


def reverse_graph(graph):
    reverse = {a: [] for a in graph}
    for a, ns in graph.items():
        for b in ns:
            reverse.setdefault(b, []).append(a)
    return reverse


def relax_traps(catalog):
    """Only relax ledge segments whose two sides have no alternate return path."""
    graph, offsets, decoded = graph_for(catalog)
    reverse = reverse_graph(graph)
    # Iterative Kosaraju: avoid recursion limits on a whole-world walking graph.
    seen, order = set(), []
    for root in graph:
        if root in seen:
            continue
        stack = [(root, False)]
        while stack:
            a, done = stack.pop()
            if done:
                order.append(a)
            elif a not in seen:
                seen.add(a)
                stack.append((a, True))
                stack.extend((b, False) for b in graph.get(a, []) if b not in seen)
    component = {}
    for root in reversed(order):
        if root in component:
            continue
        stack = [root]
        component[root] = root
        while stack:
            for b in reverse.get(stack.pop(), []):
                if b not in component:
                    component[b] = root
                    stack.append(b)
    receipt = []
    for t in catalog['terrains']:
        off, n = offsets[t['id']], t['columns']
        _walk, water, behavior, elevation = decoded[t['id']]
        for a, b in enumerate(behavior):
            rule = BEHAVIORS.get(b, {})
            if rule.get('mode') != 'ledge':
                continue
            dx, dy = rule['direction']
            before, after = a - dx - dy * n, a + dx + dy * n
            if off + before not in graph or off + after not in graph:
                continue
            if (not legal(before, a, n, behavior, elevation, water)
                    or not legal(a, after, n, behavior, elevation, water)):
                continue
            if component[off + before] == component[off + after]:
                continue
            t['bidirectionalLedges'].append(a)
            area = next(v for v in t['areas'] if v['gridX'] <= a % n < v['gridX'] + v['columns']
                        and v['gridY'] <= a // n < v['gridY'] + v['rows'])
            receipt.append({'terrain': t['id'], 'map': area['sourceName'], 'behavior': f'0x{b:02X}',
                            'local': [a % n - area['gridX'], a // n - area['gridY']],
                            'index': a, 'reason': 'one-way ledge separates strongly connected components'})
    return receipt
