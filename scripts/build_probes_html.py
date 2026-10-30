"""inputs/geo/nlsc_cache.jsonl  ->  docs/probes.html (sampling debug view).

Plots every reverse-sampled probe point coloured by the 段 the NLSC API returned, over
the cadastral basemap (toggle the real 段界 overlay to compare). Shows where sampling is
dense (section borders) vs sparse (interiors)."""
import json, re, pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
CACHE = HERE / 'inputs' / 'geo' / 'nlsc_cache.jsonl'

CN = '〇一二三四五六七八九'
def a2c(m):
    n = int(m.group(0))
    return CN[n] if n < 10 else ('十'+(CN[n%10] if n%10 else '') if n<20 else (CN[n//10]+'十'+(CN[n%10] if n%10 else '') if n<100 else m.group(0)))
def norm(s):
    s = re.sub(r'[（(].*?[）)]', '', s or '').replace('台','臺').replace(' ','').replace('　','')
    return re.sub(r'\d+', a2c, s)

owned = set()
mp = HERE / 'output' / 'map_data.json'
if mp.exists():
    for k in json.load(open(mp))['sections']:
        owned.add(k)   # "town|norm"

secidx = {}; secnames = []; pts = []
for line in open(CACHE, encoding='utf-8'):
    d = json.loads(line)
    if d.get('cty') != '宜蘭縣' or not d.get('se'):
        continue
    la, ln = d['k'].split(',')
    key = f"{d['tw']}|{norm(d['se'])}"
    if key not in secidx:
        secidx[key] = len(secnames); secnames.append({'k': key, 'n': d['tw']+d['se'], 'own': 1 if key in owned else 0})
    pts.append([round(float(la), 5), round(float(ln), 5), secidx[key]])

DATA = {'sec': secnames, 'pts': pts}
print('points:', len(pts), '| sections:', len(secnames), '| owned:', sum(s['own'] for s in secnames))

TEMPLATE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>宜蘭地段反查原始取樣點</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
 html,body{margin:0;height:100%;font-family:-apple-system,"PingFang TC",system-ui,sans-serif}
 #map{position:absolute;inset:0}
 #bar{position:absolute;top:8px;left:8px;z-index:500;background:#fffffff2;border:1px solid #d9dce1;border-radius:8px;padding:8px 10px;font-size:12px;max-width:340px;box-shadow:0 1px 6px #0002}
 #bar b{font-size:13px} #bar input{font:inherit;font-size:12px;padding:2px 6px;border:1px solid #ccc;border-radius:5px}
 .note{color:#5b616b;font-size:11px;line-height:1.5;margin-top:5px}
</style></head><body>
<div id="map"></div>
<div id="bar">
 <b>反查原始取樣點</b>（每點＝一次 NLSC 單點查詢，顏色＝回傳的地段）<br>
 <label style="margin-top:4px;display:inline-block"><input type="checkbox" id="ownonly"> 只顯示有人持有的段</label>
 <input type="search" id="q" placeholder="高亮段名…" size="10">
 <div class="note">開啟右下角「段籍圖」比對：同色點群應落在同一段界內。方塊狀破碎＝不同解析度網格重疊。點一下看段名。</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = /*__DATA__*/;
const map = L.map('map',{center:[24.75,121.75],zoom:12,preferCanvas:true});
L.tileLayer('https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,attribution:'© NLSC'}).addTo(map);
const landsect=L.tileLayer('https://wmts.nlsc.gov.tw/wmts/LANDSECT/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,opacity:.85});
L.control.layers(null,{'段籍圖（真實段界，開啟比對）':landsect},{position:'bottomright'}).addTo(map);
function hue(i){ return (i*47)%360; }               // stable distinct-ish colour per section
const canvas=L.canvas({padding:.5});
let markers=[];
function rad(){ const z=map.getZoom(); return z>=17?8:z>=16?6:z>=15?5:z>=14?4:3; }
function draw(){
  markers.forEach(m=>map.removeLayer(m)); markers=[];
  const ownonly=document.getElementById('ownonly').checked;
  const q=document.getElementById('q').value.trim();
  const r=rad();
  for(const [la,ln,si] of DATA.pts){
    const s=DATA.sec[si];
    if(ownonly && !s.own) continue;
    const hit = q && s.n.includes(q);
    const col = `hsl(${hue(si)},72%,47%)`;
    const m=L.circleMarker([la,ln],{renderer:canvas,radius:hit?r+2:r,weight:hit?1.5:0.4,color:hit?'#000':'#fff',fillColor:col,fillOpacity:q?(hit?1:.1):.85});
    m.on('click',()=>m.bindPopup(`${s.n}${s.own?'（有人持有）':''}`).openPopup());
    m.addTo(map); markers.push(m);
  }
}
document.getElementById('ownonly').onchange=draw;
document.getElementById('q').oninput=draw;
map.on('zoomend',draw);
draw();
</script></body></html>"""

out = TEMPLATE.replace('/*__DATA__*/', json.dumps(DATA, ensure_ascii=False, separators=(',', ':')))
(HERE / 'docs' / 'probes.html').write_text(out, encoding='utf-8')
print('wrote docs/probes.html', round(len(out)/1024), 'KB')
