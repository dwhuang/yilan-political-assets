"""NLSC reverse-sampling cache + output/yilan.json -> section geometry for the map.

For each owned land-section: builds a footprint by nearest-probe (Voronoi) rasterisation
of the cached point->段 lookups, traces + simplifies the outline, and anchors a dot at the
pole of inaccessibility (so it stays inside concave sections). Remaps old / typo / family /
wrong-town section names onto current ones (RENAME / ROADMAP), matches every 宜蘭 data row
to a section, and reports coverage.

Outputs:
  output/section_geo.json   {section_key: {town, name, lat, lng, area_m2, n_hits, rings:[[[lng,lat],...]]}}
  output/map_data.json      what the map reads (sections + holdings + out-of-county + ...)
  output/placement.json     {row index -> {how, town, section, lat, lng}}
  output/待處理_舊地段.md    the still-unplaced rows (old section names / road-only addresses)
"""
import json, re, math, glob, sys
import xml.etree.ElementTree as ET
from collections import defaultdict
import pathlib
sys.setrecursionlimit(20000)                 # Douglas-Peucker on long boundary rings

HERE = pathlib.Path(__file__).resolve().parent.parent
CACHE = HERE / 'inputs' / 'geo' / 'nlsc_cache.jsonl'

CN = '〇一二三四五六七八九'
def a2c(m):
    n = int(m.group(0))
    if n < 10: return CN[n]
    if n < 20: return '十' + (CN[n % 10] if n % 10 else '')
    if n < 100: return CN[n // 10] + '十' + (CN[n % 10] if n % 10 else '')
    return m.group(0)
def norm(s):
    s = re.sub(r'[（(].*?[）)]', '', s or '')
    s = s.replace('台', '臺').replace(' ', '').replace('　', '')
    return re.sub(r'\d+', a2c, s)

MOUNTAIN = {'大同鄉', '南澳鄉'}
def step_m(town):
    return 1000 if town in MOUNTAIN else 300

# old/typo/family/wrong-town  ->  current section name(s) in a town.
# value entries are either a name (same town) or a (town, name) pair.
RENAME = {
    ('宜蘭市', '良門二段'): ['艮門二段'],
    ('冬山鄉', '寶貞段'): ['寶員段'],
    ('礁溪鄉', '閩蘭二段'): ['開蘭二段'],
    ('宜蘭市', '金六結段金結小段'): ['金六結段五結小段'],
    ('宜蘭市', '振興段'): ['振興一段', '振興二段', '振興三段'],
    ('宜蘭市', '凱旋段一小段'): ['凱旋一段', '凱旋二段'],
    ('五結鄉', '協和段'): ['協和一段', '新協和段'],
    ('頭城鎮', '新興段一小段'): ['新興一段', '新興二段'],
    ('礁溪鄉', '中山段'): [('冬山鄉', '中山段')],
    # 大同 四季村 area: filings say the 部落/舊名; current sections there are 賓谷溪/發徒西 (approx)
    ('大同鄉', '四季段'): ['賓谷溪段', '發徒西段'],
    ('大同鄉', '四季村段'): ['賓谷溪段', '發徒西段'],
    ('大同鄉', '四季村'): ['賓谷溪段', '發徒西段'],
}

def load_points():
    secs = defaultdict(lambda: {'disp': '', 'pts': []})   # (town, normname) -> {...}
    for line in open(CACHE, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        d = json.loads(line)
        if d.get('cty') != '宜蘭縣' or not d.get('se'): continue
        la, ln = map(float, d['k'].split(','))
        key = (d['tw'], norm(d['se']))
        secs[key]['pts'].append((la, ln)); secs[key]['disp'] = d['se']
    return secs

def cell_outline(cells, dlat, dlng):
    """cells: set of (ix,iy). Return list of rings [[(lng,lat),...]] tracing the union border."""
    edges = defaultdict(int)  # undirected edge (p1,p2) as sorted corner pair -> count
    def E(a, b):
        edges[tuple(sorted((a, b)))] += 1
    for (ix, iy) in cells:
        E((ix, iy), (ix + 1, iy)); E((ix, iy + 1), (ix + 1, iy + 1))
        E((ix, iy), (ix, iy + 1)); E((ix + 1, iy), (ix + 1, iy + 1))
    border = [e for e, c in edges.items() if c == 1]          # edges on exactly one cell = boundary
    adj = defaultdict(list)
    for (a, b) in border:
        adj[a].append(b); adj[b].append(a)
    used = set(); rings = []
    for (a, b) in border:
        if (a, b) in used or (b, a) in used: continue
        ring = [a]; prev, cur = a, b; used.add((a, b)); used.add((b, a))
        while cur != a:
            ring.append(cur)
            nxts = [n for n in adj[cur] if (cur, n) not in used]
            if not nxts: break
            nxt = nxts[0]; used.add((cur, nxt)); used.add((nxt, cur)); prev, cur = cur, nxt
        ring = _dropcollinear(ring)                       # straight runs -> 2 points
        if len(ring) > 4:                                 # smooth the cell staircase into diagonals
            ring = _dp(ring + [ring[0]], 1.3)[:-1]
        if len(ring) >= 3:                                # drop degenerate speck
            rings.append([(round(cx * dlng, 6), round(cy * dlat, 6)) for (cx, cy) in ring])
    return rings

def _dropcollinear(ring):
    n = len(ring); out = []
    for i in range(n):
        a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
        if (b[0]-a[0]) * (c[1]-b[1]) - (b[1]-a[1]) * (c[0]-b[0]) != 0:  # not collinear
            out.append(b)
    return out

def _dp(pts, tol):                                        # Douglas-Peucker on a polyline (cell units)
    if len(pts) <= 2: return pts
    a, b = pts[0], pts[-1]; dx, dy = b[0]-a[0], b[1]-a[1]; L2 = dx*dx + dy*dy
    dmax, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i][0]-a[0], pts[i][1]-a[1]
        if L2 == 0: d = (px*px + py*py) ** 0.5
        else:
            t = (px*dx + py*dy) / L2; d = ((px - t*dx) ** 2 + (py - t*dy) ** 2) ** 0.5
        if d > dmax: dmax, idx = d, i
    if dmax > tol:
        return _dp(pts[:idx+1], tol)[:-1] + _dp(pts[idx:], tol)
    return [a, b]

def _pole(cells):
    """Pole of inaccessibility on a cell set: the cell farthest (grid-steps) from the
    edge. Guaranteed inside the footprint and in its thickest lobe — a good dot anchor
    for concave/multi-part sections where the mean centroid falls outside."""
    from collections import deque
    dist = {}; dq = deque()
    for (x, y) in cells:                      # seed BFS from edge cells (dist 0)
        if (x+1, y) not in cells or (x-1, y) not in cells or (x, y+1) not in cells or (x, y-1) not in cells:
            dist[(x, y)] = 0; dq.append((x, y))
    best, bestd = (next(iter(cells)) if cells else None), -1
    while dq:
        c = dq.popleft()
        if dist[c] > bestd: bestd, best = dist[c], c
        x, y = c
        for nb in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if nb in cells and nb not in dist:
                dist[nb] = dist[c] + 1; dq.append(nb)
    return best

def build_geo(secs):
    """Centroid per section (rings filled later by add_voronoi_rings for owned ones)."""
    geo = {}
    for (town, nm), v in secs.items():
        pts = v['pts']
        if not pts: continue
        geo[f'{town}|{nm}'] = {
            'town': town, 'name': v['disp'], 'norm': nm,
            'lat': round(sum(p[0] for p in pts) / len(pts), 6),
            'lng': round(sum(p[1] for p in pts) / len(pts), 6),
            'n_hits': len(pts), 'n_cells': 0, 'area_m2': 0, 'rings': [],
        }
    return geo

REFLAT = 24.74
def add_voronoi_rings(geo, secs, keys, F=25.0, MAXD=230.0):
    """Nearest-probe (Voronoi) rasterisation: a fine cell belongs to a section iff the
    globally-nearest probe is that section's and within MAXD. Boundaries fall midway
    between differing probes — sharp where the sampling was refined, no overlap/gaps."""
    import numpy as np
    from scipy.spatial import cKDTree
    mlat = 111000.0; mlng = 111000.0 * math.cos(math.radians(REFLAT))
    dflat, dflng = F / mlat, F / mlng
    kl = list(secs.keys()); kidx = {k: i for i, k in enumerate(kl)}
    xs, ys, ki = [], [], []
    for (t, n), v in secs.items():
        i = kidx[(t, n)]
        for la, ln in v['pts']:
            xs.append(ln * mlng); ys.append(la * mlat); ki.append(i)
    XY = np.column_stack([np.asarray(xs), np.asarray(ys)]); KI = np.asarray(ki)
    tree = cKDTree(XY)
    for key in keys:
        t, n = key.split('|', 1)
        if (t, n) not in kidx: continue
        si = kidx[(t, n)]; sel = KI == si
        sxy = XY[sel]; g = geo.get(key)
        # fallback anchor: the probe nearest the median (a real probe, so always inside the 段)
        if g is not None and len(sxy):
            mx, my = float(np.median(sxy[:, 0])), float(np.median(sxy[:, 1]))
            ri = int(np.argmin((sxy[:, 0] - mx) ** 2 + (sxy[:, 1] - my) ** 2))
            g['lat'] = round(sxy[ri, 1] / mlat, 6); g['lng'] = round(sxy[ri, 0] / mlng, 6)
        x0, x1, y0, y1 = sxy[:, 0].min(), sxy[:, 0].max(), sxy[:, 1].min(), sxy[:, 1].max()
        if (x1 - x0) > 9000 or (y1 - y0) > 9000:        # scattered/huge -> leave as dot
            continue
        marg = MAXD + F
        gx = np.arange(math.floor((x0 - marg) / F), math.ceil((x1 + marg) / F) + 1)
        gy = np.arange(math.floor((y0 - marg) / F), math.ceil((y1 + marg) / F) + 1)
        if gx.size * gy.size > 120000:                  # too big -> dot
            continue
        GX, GY = np.meshgrid(gx, gy)
        gxr, gyr = GX.ravel(), GY.ravel()
        dist, idx = tree.query(np.column_stack([gxr * F, gyr * F]), k=1)
        good = (KI[idx] == si) & (dist <= MAXD)
        cells = set(zip(gxr[good].tolist(), gyr[good].tolist()))   # faithful: every probe is a true 段 reading
        rings = cell_outline(cells, dflat, dflng)
        if len(rings) > 12: rings = []                  # too fragmented to render cleanly -> fall back to dot
        if g:
            g['rings'] = rings; g['n_cells'] = int(good.sum()); g['area_m2'] = round(int(good.sum()) * F * F)
            if cells:                                   # anchor the dot at the pole of inaccessibility (inside)
                px, py = _pole(cells)
                g['lat'] = round(py * dflat, 6); g['lng'] = round(px * dflng, 6)

def main():
    secs = load_points()
    geo = build_geo(secs)
    norm2key = defaultdict(list)
    for k, g in geo.items():
        norm2key[(g['town'], g['norm'])].append(k)

    # road/village-only rows geocoded via OSM -> the current section they fall in
    ROADMAP = {}
    rp_path = HERE / 'output' / 'road_placements.json'
    if rp_path.exists():
        for key, v in json.load(open(rp_path)).items():
            tw, sec = key.split('|', 1)
            if v.get('nlsc_sec'): ROADMAP[(tw, sec)] = (tw, v['nlsc_sec'])

    def resolve(town, sec):
        """-> (how, [section_keys]) for a data row's (town, raw-section)."""
        rn = norm(sec)
        if (town, rn) in norm2key: return ('current', norm2key[(town, rn)])
        tgt = RENAME.get((town, sec)) or RENAME.get((town, rn))
        if tgt:
            keys = []
            for t in tgt:
                tw2, nm2 = t if isinstance(t, tuple) else (town, t)
                keys += norm2key.get((tw2, norm(nm2)), [])
            if keys: return ('renamed', keys)
            return ('renamed-missing', [])
        if (town, sec) in ROADMAP:
            tw2, nm2 = ROADMAP[(town, sec)]
            keys = norm2key.get((tw2, norm(nm2)), [])
            if keys: return ('road-approx', keys)
        return ('unplaced', [])

    D = json.load(open(HERE / 'output' / 'yilan.json'))
    status = {p['name']: p.get('status', '') for p in D['people']}
    placement = {}; tally_rows = defaultdict(int)
    holdings = []; out_of_county = []; unplaced_yilan = []
    for i, r in enumerate(D['rows']):
        is_yilan = r['county'] in ('宜蘭縣', '')              # '' = parse miss (游國連 宜蘭段)
        base = {'name': r['name'], 'party': r['party'], 'office': r['office'],
                'district': r['district'], 'status': status.get(r['name'], ''),
                'owner_role': r['owner_role'], 'kind': r['kind'],
                'owned_m2': r['owned_m2'], 'est_twd': r['est_twd'] if r['est_counted'] else None}
        if not is_yilan:
            tally_rows['out-of-county'] += 1
            out_of_county.append({**base, 'county': r['county'], 'town': r['town'], 'section': r['section']})
            continue
        how, keys = resolve(r['town'], r['section'])
        tally_rows[how] += 1
        if keys:
            gs = [geo[k] for k in keys]
            lat = sum(g['lat'] for g in gs) / len(gs); lng = sum(g['lng'] for g in gs) / len(gs)
            placement[i] = {'how': how, 'town': r['town'], 'section': r['section'],
                            'keys': keys, 'lat': round(lat, 6), 'lng': round(lng, 6)}
            holdings.append({**base, 'sec_keys': keys, 'how': how,
                             'town': r['town'], 'section': r['section']})
        else:
            reason = 'deferred-old-name' if how == 'unplaced' and re.search(r'[路街巷村里鄰]', r['section'] or '') is None else 'road-or-village-only'
            unplaced_yilan.append({**base, 'town': r['town'], 'section': r['section'], 'reason': reason, 'how': how})

    json.dump(geo, open(HERE / 'output' / 'section_geo.json', 'w'), ensure_ascii=False)
    json.dump(placement, open(HERE / 'output' / 'placement.json', 'w'), ensure_ascii=False)
    used_keys = set(k for h in holdings for k in h['sec_keys'])   # only sections someone owns
    add_voronoi_rings(geo, secs, used_keys)                       # fill boundaries for owned sections
    sections_min = {k: {'t': geo[k]['town'], 'n': geo[k]['name'], 'lat': geo[k]['lat'], 'lng': geo[k]['lng'],
                        'a': geo[k]['area_m2'], 'r': geo[k]['rings']} for k in used_keys}
    map_data = {'sections': sections_min, 'holdings': holdings, 'out_of_county': out_of_county,
                'unplaced_yilan': unplaced_yilan,
                'people': [{'name': p['name'], 'party': p['party'], 'office': p['office'],
                            'district': p['district'], 'status': p.get('status', '')} for p in D['people']]}
    json.dump(map_data, open(HERE / 'output' / 'map_data.json', 'w'), ensure_ascii=False)
    print(f'sections with geometry: {len(geo)}')
    print('row placement:', dict(tally_rows))
    placed = sum(1 for p in placement.values())
    print(f'宜蘭 rows placed: {placed} | holdings={len(holdings)} | out-of-county={len(out_of_county)} | unplaced-yilan={len(unplaced_yilan)}')
    # a few sanity rows
    for k in list(geo)[:5]:
        g = geo[k]; print(f"  {k}: hits={g['n_hits']} cells={g['n_cells']} area={g['area_m2']/1e4:.1f}ha rings={len(g['rings'])} @({g['lat']},{g['lng']})")

if __name__ == '__main__':
    main()
