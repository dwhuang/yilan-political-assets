"""Adaptive quadtree edge-refinement of the section sampling.

Starts from the existing uniform 300m grid (reused as a memo) and, level by level,
subdivides only the cells whose 4 corners disagree AND touch an owned section —
re-probing the new midpoints down to ~75m. Boundaries get sharp; small sections in
dense areas get more probes automatically (more disagreeing corners there), and new
small sections between existing points are discovered. Resumable (appends to the
same cache); polite (thread pool + jitter).

  python3 scripts/refine_boundaries.py [target_m]     # default 75
"""
import os, sys, ssl, json, time, math, threading, re, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
CACHE = HERE / 'inputs' / 'geo' / 'nlsc_cache.jsonl'
SSL = ssl._create_unverified_context()
UA = 'yilan-assets-research/1.0 (bdwhuang@gmail.com)'
WORKERS = 4
TARGET = float(sys.argv[1]) if len(sys.argv) > 1 else 75.0
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 16000   # hard cap on NEW probes, stay polite
# plain box, aligned to the existing 300m plain grid origin so level-0 corners are all cached
LAT0, LNG0 = 24.55, 121.71
LAT1, LNG1 = 24.95, 121.87

CN = '〇一二三四五六七八九'
def a2c(m):
    n = int(m.group(0))
    return CN[n] if n < 10 else ('十'+(CN[n%10] if n%10 else '') if n<20 else (CN[n//10]+'十'+(CN[n%10] if n%10 else '') if n<100 else m.group(0)))
def norm(s):
    s = re.sub(r'[（(].*?[）)]', '', s or '').replace('台','臺').replace(' ','').replace('　','')
    return re.sub(r'\d+', a2c, s)

owned = set(json.load(open(HERE / 'output' / 'map_data.json'))['sections'].keys())  # "town|norm"

memo = {}
for line in open(CACHE, encoding='utf-8'):
    d = json.loads(line)
    la, ln = d['k'].split(',')
    k = (round(float(la), 6), round(float(ln), 6))
    memo[k] = f"{d['tw']}|{norm(d['se'])}" if (d.get('cty') == '宜蘭縣' and d.get('se')) else None
print(f'cache memo: {len(memo)} points | owned sections: {len(owned)} | target {TARGET:.0f}m')

fh = open(CACHE, 'a', encoding='utf-8')
lock = threading.Lock()
new_count = {'n': 0}

def query(lat, lng):
    url = f'https://api.nlsc.gov.tw/other/TownVillagePointQuery/{lng:.6f}/{lat:.6f}/4326'
    for attempt in range(2):
        try:
            x = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=20, context=SSL).read()
            r = ET.fromstring(x)
            return r.findtext('ctyName'), r.findtext('townName'), r.findtext('sectName')
        except Exception:
            if attempt == 0: time.sleep(0.5)
    return None, None, None

def fetch(pt):
    lat, lng = pt
    cty, tw, se = query(lat, lng); time.sleep(0.15)
    lbl = f"{tw}|{norm(se)}" if (cty == '宜蘭縣' and se) else None
    with lock:
        memo[pt] = lbl; new_count['n'] += 1
        fh.write(json.dumps({'k': f'{pt[0]:.6f},{pt[1]:.6f}', 'cty': cty, 'tw': tw, 'se': se}, ensure_ascii=False) + '\n'); fh.flush()

def corners(la, ln, dla, dln):
    return [(round(la + i*dla, 6), round(ln + j*dln, 6)) for i in (0, 1) for j in (0, 1)]

# enumerate base cells on the aligned 300m lattice
dlat = 300 / 111000.0
dlng = 300 / (111000.0 * math.cos(math.radians((LAT0+LAT1)/2)))
cells = []
la = LAT0
while la < LAT1 - dlat/2:
    ln = LNG0
    while ln < LNG1 - dlng/2:
        cells.append((la, ln, dlat, dlng)); ln += dlng
    la += dlat

level = 0; t0 = time.time()
while cells:
    stepm = cells[0][2] * 111000.0
    if stepm <= TARGET * 1.3: break
    need = set()
    for (la, ln, dla, dln) in cells:
        for c in corners(la, ln, dla, dln):
            if c not in memo: need.add(c)
    if new_count['n'] + len(need) > BUDGET:
        print(f'level {level}: would exceed budget ({new_count["n"]}+{len(need)}>{BUDGET}); stopping'); break
    if need:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(fetch, need))
    nxt = []
    for (la, ln, dla, dln) in cells:
        cs = [memo.get(c) for c in corners(la, ln, dla, dln)]
        if len(set(cs)) > 1 and any(c in owned for c in cs):
            h1, h2 = dla/2, dln/2
            for i in (0, 1):
                for j in (0, 1):
                    nxt.append((la + i*h1, ln + j*h2, h1, h2))
    print(f'level {level}: step {stepm:.0f}m | cells {len(cells)} | queried new {len(need)} | subdividing {len(nxt)//4} | total new {new_count["n"]} | {time.time()-t0:.0f}s', flush=True)
    cells = nxt; level += 1

fh.close()
print(f'DONE refine: {new_count["n"]} new probes in {time.time()-t0:.0f}s | cache now ~{len(memo)} points')
