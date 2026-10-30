"""Reverse-sample the free NLSC point->section API to recover 宜蘭 land-section
boundaries. Each grid point is labelled with the current 段 it falls in; grouping
points per section gives a centroid and a cell-union footprint.

Resumable: every queried point is cached to inputs/geo/nlsc_cache.jsonl, so re-runs
skip done points and a crash never loses progress. Polite: small thread pool + jitter.

Usage:
  python3 scripts/geocode_sections.py plain            # the 蘭陽平原 + coastal strips @300m
  python3 scripts/geocode_sections.py mountain         # 大同/南澳 @700m
  python3 scripts/geocode_sections.py plain --limit 400 # validation chunk
"""
import os, sys, ssl, json, time, math, threading, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
CACHE = HERE / 'inputs' / 'geo' / 'nlsc_cache.jsonl'
SSL = ssl._create_unverified_context()           # NLSC cert lacks SKI; curl trusts it, urllib won't
UA = 'yilan-assets-research/1.0 (bdwhuang@gmail.com)'
WORKERS = 4                                        # keep aggregate rate ~5-6 req/s

# (name, lat0, lat1, lng0, lng1, step_metres)
REGIONS = {
    'plain': [
        ('lanyang-plain', 24.550, 24.950, 121.710, 121.870, 300),
        ('toucheng-coast', 24.900, 24.975, 121.820, 121.930, 300),
        ('suao-south',     24.520, 24.625, 121.800, 121.885, 300),
    ],
    'mountain': [
        ('datong',  24.500, 24.780, 121.480, 121.720, 1000),
        ('nanao',   24.300, 24.620, 121.480, 121.860, 1000),
    ],
    # fill coverage gaps found after the first pass (small urban sections + mountain settlements)
    'gaps': [
        ('yilan-core-fine',  24.720, 24.790, 121.725, 121.795, 150),  # 公園段/坤門三段/艮門三段
        ('sanxing-yuanshan-w', 24.625, 24.725, 121.575, 121.720, 300),  # 大湖段/張公圍段/田心段
        ('datong-siji',      24.560, 24.655, 121.455, 121.560, 300),   # 四季段/四季村段/四重段
        ('nanao-town',       24.430, 24.545, 121.775, 121.880, 300),   # 南澳二段 + 東澳
    ],
    'gaps2': [
        ('datong-nanshan-siji', 24.395, 24.475, 121.355, 121.475, 300),  # 四季段/四季村段/四重段 (upper 蘭陽溪)
    ],
}

def grid(lat0, lat1, lng0, lng1, step_m):
    dlat = step_m / 111000.0
    dlng = step_m / (111000.0 * math.cos(math.radians((lat0 + lat1) / 2)))
    n = 0; la = lat0
    while la <= lat1:
        ln = lng0
        while ln <= lng1:
            yield round(la, 6), round(ln, 6); ln += dlng; n += 1
        la += dlat

def query(lat, lng):
    url = f'https://api.nlsc.gov.tw/other/TownVillagePointQuery/{lng:.6f}/{lat:.6f}/4326'
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            x = urllib.request.urlopen(req, timeout=20, context=SSL).read()
            r = ET.fromstring(x)
            cty = r.findtext('ctyName'); tw = r.findtext('townName'); se = r.findtext('sectName')
            return {'cty': cty, 'tw': tw, 'se': se}
        except Exception:
            if attempt == 0:
                time.sleep(0.5); continue
            return None

def load_cache():
    done = {}
    if CACHE.exists():
        for line in open(CACHE, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try:
                d = json.loads(line); done[d['k']] = d
            except Exception:
                pass
    return done

def main():
    region = sys.argv[1] if len(sys.argv) > 1 else 'plain'
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    pts = []
    seen = set()
    for (_, la0, la1, ln0, ln1, step) in REGIONS[region]:
        for la, ln in grid(la0, la1, ln0, ln1, step):
            k = f'{la:.6f},{ln:.6f}'
            if k not in seen:
                seen.add(k); pts.append((k, la, ln))
    done = load_cache()
    todo = [(k, la, ln) for (k, la, ln) in pts if k not in done]
    if limit: todo = todo[:limit]
    print(f'region={region}  grid points={len(pts)}  already cached={len(pts)-len(todo) if not limit else "?"}  to query={len(todo)}', flush=True)

    lock = threading.Lock()
    fh = open(CACHE, 'a', encoding='utf-8')
    counter = {'n': 0, 'hit': 0}
    t0 = time.time()

    def work(item):
        k, la, ln = item
        r = query(la, ln)
        time.sleep(0.15)                            # politeness jitter per worker
        rec = {'k': k, 'cty': (r or {}).get('cty'), 'tw': (r or {}).get('tw'), 'se': (r or {}).get('se')}
        with lock:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n'); fh.flush()
            counter['n'] += 1
            if rec['se']: counter['hit'] += 1
            if counter['n'] % 250 == 0:
                dt = time.time() - t0
                print(f"  {counter['n']}/{len(todo)}  hits={counter['hit']}  {counter['n']/dt:.1f} req/s  elapsed={dt:.0f}s", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))
    fh.close()
    print(f"DONE region={region}  queried={counter['n']}  section-hits={counter['hit']}  in {time.time()-t0:.0f}s", flush=True)

if __name__ == '__main__':
    main()
