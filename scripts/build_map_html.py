"""output/map_data.json + output/poi.json  ->  docs/index.html (the published map).

Self-contained page (Leaflet from CDN, NLSC WMTS basemaps, data inlined): owned-section
boundaries over the cadastral basemap, a party pie-dot per section sized by value/area,
filters (party / status / district / name), transport overlays, and a 縣外 panel."""
import json, pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = json.load(open(HERE / 'output' / 'map_data.json', encoding='utf-8'))
POI = json.load(open(HERE / 'output' / 'poi.json', encoding='utf-8'))

TEMPLATE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>宜蘭縣政治人物不動產地圖</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root{ --ink:#1b1f24; --muted:#5b616b; --line:#d9dce1; --bg:#fcfcfb; --panel:#ffffffee; }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;font-family:-apple-system,"PingFang TC","Microsoft JhengHei",system-ui,sans-serif;color:var(--ink)}
  #map{position:absolute;inset:0;z-index:0;background:#e8eef2}
  .card{background:var(--panel);backdrop-filter:blur(6px);border:1px solid var(--line);border-radius:10px;box-shadow:0 2px 10px #0002}
  #bar{position:absolute;top:10px;left:10px;z-index:500;max-width:min(92vw,460px);padding:12px 14px}
  #bar h1{font-size:16px;margin:0 0 2px} #bar .sub{font-size:11.5px;color:var(--muted);margin-bottom:8px;line-height:1.5}
  .frow{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:12px;margin:5px 0}
  .frow b{font-size:11px;color:var(--muted);min-width:34px}
  .chip{display:inline-flex;align-items:center;gap:5px;padding:3px 8px;border:1px solid var(--line);border-radius:999px;cursor:pointer;user-select:none;background:#fff;line-height:1.4}
  .chip input{margin:0} .chip .sw{width:10px;height:10px;border-radius:2px;display:inline-block}
  .chip.off{opacity:.4}
  select,input[type=search]{font:inherit;font-size:12px;padding:3px 6px;border:1px solid var(--line);border-radius:6px;background:#fff}
  #panel{position:absolute;top:10px;right:10px;z-index:500;width:300px;max-width:46vw;max-height:calc(100% - 20px);overflow:auto;padding:12px 14px;font-size:12px}
  #panel h2{font-size:13px;margin:2px 0 6px;display:flex;justify-content:space-between;align-items:center}
  #panel .toggle{font-weight:400;color:var(--muted);cursor:pointer;font-size:11px}
  .legrow{display:flex;align-items:center;gap:7px;margin:3px 0}
  .legrow .sw{width:13px;height:13px;border-radius:3px;border:1px solid #0003;flex:none}
  .note{color:var(--muted);line-height:1.55;font-size:11px;margin:7px 0 0}
  table.oc{width:100%;border-collapse:collapse;margin-top:4px}
  table.oc td{padding:2px 3px;border-bottom:1px solid #eee;vertical-align:top}
  table.oc td.r{text-align:right;white-space:nowrap;color:var(--muted)}
  .pop b{font-size:13px} .pop table{border-collapse:collapse;margin-top:4px;font-size:11.5px}
  .pop td{padding:1px 5px 1px 0;vertical-align:top} .pop .r{text-align:right;color:var(--muted)}
  .sec-title{font-size:13px;font-weight:600} .sec-sub{color:var(--muted);font-size:11px;margin-bottom:3px}
  .hint{position:absolute;bottom:8px;left:10px;z-index:500;font-size:11px;color:#333;background:#ffffffcc;padding:3px 8px;border-radius:6px}
  #info{position:absolute;left:10px;bottom:34px;z-index:600;width:360px;max-width:92vw;max-height:48vh;overflow:auto;padding:10px 12px;font-size:12px;display:none}
  #info .x{position:absolute;top:6px;right:10px;cursor:pointer;color:#999;font-size:17px;line-height:1}
  #info table{border-collapse:collapse;margin-top:5px;font-size:11.5px;width:100%}
  #info td{padding:1px 6px 1px 0;vertical-align:top} #info .r{text-align:right;color:var(--muted);white-space:nowrap}
  .poilbl{font-size:10.5px;font-weight:600;padding:0 4px;background:#ffffffe6;border:1px solid #bbb;border-radius:4px;color:#222;box-shadow:0 1px 2px #0003}
  .poilbl::before{display:none !important}
  body.lblhide .poilbl{display:none !important}
  #mtoggle{display:none}
  @media(max-width:680px){
    .leaflet-control-zoom{display:none}                        /* pinch to zoom on phones */
    #mtoggle{display:flex;gap:6px;align-items:center;position:absolute;top:8px;left:8px;right:8px;z-index:700}
    #mtoggle .mt-t{flex:1;min-width:0;text-align:right;font-size:12px;font-weight:700;color:#333;background:#ffffffcc;padding:6px 9px;border-radius:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #mtoggle button{font:inherit;font-size:13px;font-weight:600;padding:6px 13px;border:1px solid #2c3e50;border-radius:8px;background:#2c3e50;color:#fff;box-shadow:0 1px 4px #0003}
    #mtoggle button.on{background:#1f5fbf;border-color:#1f5fbf}
    #bar,#panel{top:48px;left:8px;right:8px;width:auto;max-width:none;max-height:70vh;overflow:auto;display:none}
    #bar.show,#panel.show{display:block}
    #info{left:8px;right:8px;width:auto;bottom:8px;max-height:52vh}
    .hint{display:none}
    #bar h1{display:none} .frow{font-size:13px;gap:7px 10px} .chip{padding:5px 11px}
    select,input[type=search]{font-size:13px;padding:5px 8px}
    .leaflet-popup-content{max-width:74vw !important}
  }
</style>
</head>
<body data-palette="#1f5fbf,#1e9e52,#1a9aad,#c6761a">
<div id="map"></div>
<div id="mtoggle"><button data-p="bar">☰ 篩選</button><button data-p="panel">圖例</button><span class="mt-t">宜蘭縣政治人物不動產地圖</span></div>

<div id="bar" class="card">
  <h1>宜蘭縣政治人物不動產地圖</h1>
  <div class="sub" id="summary"></div>
  <div class="frow"><b>著色</b>
    <label class="chip"><input type="radio" name="mode" value="party" checked> 依政黨</label>
    <label class="chip"><input type="radio" name="mode" value="status"> 依身分</label>
    <b style="margin-left:6px">大小</b>
    <label class="chip"><input type="radio" name="size" value="area"> 依持分面積</label>
    <label class="chip"><input type="radio" name="size" value="value" checked> 依參考估值</label>
  </div>
  <div class="frow" id="partyFilters"><b>政黨</b></div>
  <div class="frow" id="statusFilters"><b>身分</b></div>
  <div class="frow"><b>選區</b>
    <select id="district"><option value="">全部</option></select>
    <input type="search" id="search" placeholder="姓名…" size="8">
    <label class="chip"><input type="checkbox" id="alwaysPoly"> 段範圍外框</label>
  </div>
</div>

<div id="panel" class="card">
  <h2>圖例</h2>
  <div id="legend"></div>
  <h2 style="margin-top:12px">縣外持有 <span class="toggle" id="ocToggle">(展開)</span></h2>
  <div id="ocList" style="display:none"></div>
  <div class="note" id="notes"></div>
</div>
<div id="info" class="card"></div>
<div class="hint" id="zoomHint"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = /*__DATA__*/;
const COLORS = {'中國國民黨':'#1f5fbf','民主進步黨':'#1e9e52','台灣民眾黨':'#1a9aad','其他小黨':'#c6761a','無黨籍':'#8a8f98','非選任':'#5b616b'};
const STATUS_COLORS = {'候選人':'#1f5fbf','現任議員・參選':'#c6761a','現任・未參選':'#1e9e52'};
const MAJORS = {'中國國民黨':1,'民主進步黨':1,'台灣民眾黨':1,'無黨籍':1,'非選任':1};
const pGroup = p => MAJORS[p] ? p : '其他小黨';
const fmtW = v => v ? (v/1e4).toLocaleString('en',{maximumFractionDigits:0})+'萬' : '—';

// ---- map + NLSC basemaps ----
const map = L.map('map',{center:[24.70,121.74],zoom:11,zoomControl:true});
const emap = L.tileLayer('https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,attribution:'© 國土測繪中心 NLSC'}).addTo(map);
const landsect = L.tileLayer('https://wmts.nlsc.gov.tw/wmts/LANDSECT/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,opacity:0.9});
const photo = L.tileLayer('https://wmts.nlsc.gov.tw/wmts/PHOTO2/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,attribution:'© 國土測繪中心 NLSC'});
const layerCtl = L.control.layers({'電子地圖':emap,'正射影像':photo},{'段籍圖（段界）':landsect},{collapsed:true,position:'bottomright'}).addTo(map);

// ---- index holdings per section ----
const secHold = {};                                  // secKey -> [holding,...]
for(const h of DATA.holdings){ for(const k of h.sec_keys){ (secHold[k]=secHold[k]||[]).push(h); } }

function colorFor(h){ return (document.querySelector('input[name=mode]:checked').value==='status') ? (STATUS_COLORS[h.status]||'#888') : COLORS[pGroup(h.party)]; }
function secArea(list){ return list.reduce((a,h)=>a+(h.owned_m2||0),0); }            // 持分面積合計(㎡)
function secVal(list){ return list.reduce((a,h)=>a+(h.est_twd||0),0); }              // 參考估值合計(元)
function sizeMode(){ return (document.querySelector('input[name=size]:checked')||{}).value||'area'; }
function metric(list){ return sizeMode()==='value' ? secVal(list) : secArea(list); }
function dominant(list){ // party holding the most (of whatever drives size) in this section
  const val=sizeMode()==='value'; const c={};
  for(const h of list){ const col=colorFor(h); c[col]=(c[col]||0)+((val?h.est_twd:h.owned_m2)||0)+0.001; }
  return Object.entries(c).sort((a,b)=>b[1]-a[1])[0][0];
}
// circle area ∝ metric, scaled to the 90th-pct section so one huge outlier doesn't flatten the rest
function _pct90(f){ const a=Object.keys(DATA.sections).map(k=>f(secHold[k]||[])).filter(x=>x>0).sort((a,b)=>a-b); return a.length?a[Math.floor(a.length*0.90)]:1; }
const AREF=_pct90(secArea), VREF=_pct90(secVal);
function radForMetric(x){ const ref=sizeMode()==='value'?VREF:AREF; return x>0 ? 5 + 17*Math.min(1, Math.sqrt(x/ref)) : 4; }

// party shares within a section (by the current size metric), largest first -> pie wedges
function partyShares(list){
  const val=sizeMode()==='value'; const c={};
  for(const h of list){ const col=colorFor(h); c[col]=(c[col]||0)+((val?h.est_twd:h.owned_m2)||0); }
  let arr=Object.entries(c).map(([color,v])=>({color,v})).sort((a,b)=>b.v-a.v);
  let tot=arr.reduce((a,b)=>a+b.v,0);
  if(tot<=0){ const cc={}; for(const h of list){ const col=colorFor(h); cc[col]=(cc[col]||0)+1; }
    arr=Object.entries(cc).map(([color,v])=>({color,v})); tot=arr.reduce((a,b)=>a+b.v,0); }
  return arr.map(x=>({color:x.color, frac:tot?x.v/tot:1}));
}
function pieIcon(parts, d){
  let bg='#999';
  if(parts.length===1) bg=parts[0].color;
  else if(parts.length>1){ let acc=0; bg='conic-gradient('+parts.map(p=>{const a=(acc*100).toFixed(1), b=((acc+p.frac)*100).toFixed(1); acc+=p.frac; return `${p.color} ${a}% ${b}%`;}).join(',')+')'; }
  return L.divIcon({className:'piemk', iconSize:[d,d], iconAnchor:[d/2,d/2],
    html:`<div style="width:${d}px;height:${d}px;border-radius:50%;background:${bg};box-shadow:0 0 0 1.2px #fff,0 1px 2px #0006"></div>`});
}

// ---- section OUTLINE = context (its extent); centroid DOT = the datum (who holds here, how much 持分) ----
const outlineLayer = L.layerGroup(), dotLayer = L.layerGroup();
const secObjs = {};   // secKey -> {polys, dot}
for(const [k,s] of Object.entries(DATA.sections)){
  const polys = s.r.map(r=>L.polygon(r.map(([lng,lat])=>[lat,lng]),{weight:1.3,color:'#555',fill:false,opacity:0.7}));
  const dot = L.marker([s.lat,s.lng],{icon:pieIcon([{color:'#999',frac:1}],8), keyboard:false});
  polys.forEach(p=>{ p.on('click',()=>openPop(k,s)); outlineLayer.addLayer(p); });
  dot.on('click',()=>openPop(k,s));
  dot.bindTooltip(function(){ const l=activeFor(k); if(!l.length) return '';
    const ps=partyShares(l), by=sizeMode()==='value'?'估值':'持分';
    const mix=ps.length>1?`（${ps.map(p=>Math.round(p.frac*100)+'%').join('/')} 混）`:'';
    return `${s.t}${s.n}｜${l.length} 筆${mix}｜持分 ${Math.round(secArea(l)).toLocaleString('en')}㎡｜估值 ${fmtW(secVal(l))}`; },{direction:'top',opacity:0.95});
  secObjs[k]={polys,dot};
  dotLayer.addLayer(dot);
}
dotLayer.addTo(map);

const highlightLayer = L.layerGroup().addTo(map);
function highlight(k,s){
  highlightLayer.clearLayers();
  if(s.r && s.r.length){
    s.r.forEach(r=>L.polygon(r.map(([lng,lat])=>[lat,lng]),{color:'#ff2d2d',weight:3,opacity:1,fill:true,fillColor:'#ff2d2d',fillOpacity:0.1,interactive:false}).addTo(highlightLayer));
  } else {
    L.circleMarker([s.lat,s.lng],{radius:15,color:'#ff2d2d',weight:3,fill:false,interactive:false}).addTo(highlightLayer);
  }
}
function closeInfo(){ const el=document.getElementById('info'); if(el) el.style.display='none'; highlightLayer.clearLayers(); }
let _suppressMapClick=false;
function closeMobilePanels(){ document.querySelectorAll('#mtoggle button').forEach(b=>{ document.getElementById(b.dataset.p).classList.remove('show'); b.classList.remove('on'); }); }
document.querySelectorAll('#mtoggle button').forEach(b=>b.onclick=()=>{
  const el=document.getElementById(b.dataset.p), open=!el.classList.contains('show');
  closeMobilePanels(); if(open){ el.classList.add('show'); b.classList.add('on'); }
});
map.on('click',()=>{ if(!_suppressMapClick){ closeInfo(); closeMobilePanels(); } });  // tap empty map -> deselect / close panels

function openPop(k,s){
  _suppressMapClick=true; setTimeout(()=>{_suppressMapClick=false;},0);  // keep this click from deselecting
  const list = activeFor(k);
  if(!list.length) return;
  highlight(k,s);
  const HOWTAG = {renamed:'≈重測前段名', 'road-approx':'≈路名定位'};
  const rows = list.map(h=>`<tr><td>${h.name}${HOWTAG[h.how]?` <span style="color:#c6761a" title="定位為約略">${HOWTAG[h.how]}</span>`:''}</td><td class="r">${h.party}</td><td>${h.kind}</td><td class="r">${h.owned_m2?h.owned_m2.toLocaleString('en',{maximumFractionDigits:0})+'㎡':''}</td><td class="r">${fmtW(h.est_twd)}</td><td class="r">${h.owner_role}</td></tr>`).join('');
  const area = s.a>=1e6 ? (s.a/1e6).toFixed(2)+' km²' : Math.round(s.a/10000)+' 公頃';
  const owned = Math.round(secArea(list)).toLocaleString('en');
  const val=sizeMode()==='value';
  const pc={}; for(const h of list){ const g=pGroup(h.party); pc[g]=(pc[g]||0)+((val?h.est_twd:h.owned_m2)||0); }
  let tot=Object.values(pc).reduce((a,b)=>a+b,0); const mixArr=Object.entries(pc).sort((a,b)=>b[1]-a[1]);
  const mix = mixArr.length>1 ? '<div class="sec-sub">持有政黨：'+mixArr.map(([g,v])=>`<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${COLORS[g]||'#999'};margin:0 3px -1px 0"></span>${g} ${tot?Math.round(100*v/tot):0}%`).join('　')+'</div>' : '';
  const el=document.getElementById('info');
  el.innerHTML =
    `<span class="x" onclick="closeInfo()">×</span><div class="sec-title">${s.t}${s.n}</div>`+
    `<div class="sec-sub">此段內有 <b>${list.length}</b> 筆持有・持分合計 <b>${owned}㎡</b>（地段範圍約 ${area}，非持有範圍）</div>`+
    mix+
    `<table><tr style="color:#5b616b"><td>姓名</td><td class="r">政黨</td><td>類別</td><td class="r">持分面積</td><td class="r">參考估值</td><td class="r">權屬</td></tr>${rows}</table>`+
    `<div class="note">僅知持有人在此段內持有，不知段內確切位置/地號。</div>`;
  el.style.display='block';
}

// ---- filters ----
const F = {party:{}, status:{}, district:'', search:''};
function buildChips(id,items,store,colormap){
  const box=document.getElementById(id);
  for(const it of items){ store[it]=true;
    const lab=document.createElement('label'); lab.className='chip';
    lab.innerHTML=`<input type="checkbox" checked>${colormap?`<span class="sw" style="background:${colormap[it]}"></span>`:''}${it}`;
    lab.querySelector('input').onchange=e=>{store[it]=e.target.checked;lab.classList.toggle('off',!e.target.checked);refresh();};
    box.appendChild(lab);
  }
}
buildChips('partyFilters',['中國國民黨','民主進步黨','台灣民眾黨','其他小黨','無黨籍','非選任'],F.party,COLORS);
buildChips('statusFilters',['候選人','現任議員・參選','現任・未參選'],F.status,null);
const dsel=document.getElementById('district');
[...new Set(DATA.people.map(p=>p.district))].sort().forEach(d=>{const o=document.createElement('option');o.value=d;o.textContent=d;dsel.appendChild(o);});
dsel.onchange=e=>{F.district=e.target.value;refresh();};
document.getElementById('search').oninput=e=>{F.search=e.target.value.trim();refresh();};
document.querySelectorAll('input[name=mode]').forEach(r=>r.onchange=refresh);
document.querySelectorAll('input[name=size]').forEach(r=>r.onchange=()=>{renderLegend();refresh();});
document.getElementById('alwaysPoly').onchange=refresh;

function pass(h){ return F.party[pGroup(h.party)] && F.status[h.status] && (!F.district||h.district===F.district) && (!F.search||h.name.includes(F.search)); }
function activeFor(k){ return (secHold[k]||[]).filter(pass); }

function refresh(){
  const showOutline = map.getZoom()>=14 || document.getElementById('alwaysPoly').checked;
  if(showOutline) outlineLayer.addTo(map); else map.removeLayer(outlineLayer);
  let shown=0, area=0, val=0;
  for(const [k,o] of Object.entries(secObjs)){
    const list=activeFor(k); const on=list.length>0;
    if(on){ shown++; area+=secArea(list); val+=secVal(list); }
    const col=on?dominant(list):'#999';
    if(on){ o.dot.setIcon(pieIcon(partyShares(list), Math.max(8, Math.round(2*radForMetric(metric(list)))))); o.dot.setOpacity(1); }
    else o.dot.setOpacity(0);
    o.polys.forEach(p=>p.setStyle({color:on?col:'#999', opacity:on?0.7:0}));
  }
  const bySize = sizeMode()==='value'?'參考估值':'持分面積';
  document.getElementById('summary').innerHTML =
    `顯示 <b>${shown}</b> 段・持分面積 <b>${(area/10000).toLocaleString('en',{maximumFractionDigits:0})} 公頃</b>・參考估值 <b>${fmtW(val)}</b>　`+
    `<span style="color:#5b616b">圈＝段內有人持有（非整段），大小＝${bySize}</span>`;
  renderOC();
}
map.on('zoomend',refresh);

// ---- legend / out-of-county / notes ----
function renderLegend(){
  const mode=document.querySelector('input[name=mode]:checked').value;
  const m = mode==='status'?STATUS_COLORS:COLORS;
  document.getElementById('legend').innerHTML = Object.entries(m).map(([k,c])=>`<div class="legrow"><span class="sw" style="background:${c}"></span>${k}</div>`).join('')
    + (()=>{const by=sizeMode()==='value'?'參考估值合計':'持分面積合計';const bc=sizeMode()==='value'?'估值':'持分';
      return `<div class="note"><b>圈</b>＝該段內<b>有人持有</b>不動產（<b>非整段為其所有</b>）；大小＝${by}；多黨同段時圈分成各黨${bc}比例的扇形（單一政黨為整圈）。<b>外框</b>＝該段範圍（放大後顯示），僅供定位、不代表持有範圍。點圈看明細並高亮該段。公開資料只到「段」，不知段內確切位置。</div>`;})();
}
document.querySelectorAll('input[name=mode]').forEach(r=>r.addEventListener('change',renderLegend));
function renderOC(){
  const oc={};
  for(const h of DATA.out_of_county){ if(!pass(h))continue; const key=h.name+'|'+h.party; (oc[key]=oc[key]||{n:0,v:0,name:h.name,party:h.party,c:{}}); oc[key].n++; if(h.est_twd)oc[key].v+=h.est_twd; oc[key].c[h.county]=1; }
  const rows=Object.values(oc).sort((a,b)=>b.v-a.v).map(o=>`<tr><td>${o.name}<br><span style="color:#5b616b">${o.party}</span></td><td class="r">${Object.keys(o.c).join('、')}<br>${o.n} 筆・${fmtW(o.v)}</td></tr>`).join('');
  document.getElementById('ocList').innerHTML = rows? `<table class="oc">${rows}</table>` : '<div class="note">（目前篩選無縣外持有）</div>';
}
document.getElementById('ocToggle').onclick=function(){const el=document.getElementById('ocList');const sh=el.style.display==='none';el.style.display=sh?'block':'none';this.textContent=sh?'(收合)':'(展開)';};

const up = DATA.unplaced_yilan.length;
document.getElementById('notes').innerHTML =
  `<b>資料與限制</b><br>・底圖：國土測繪中心段籍圖/電子地圖 WMTS。地段範圍以免費「單點坐標回傳段籍」API 反查網格推估，為約略範圍，非實測地籍線。<br>`+
  `・公開只到「段」，地號/門牌依法遮蔽；本圖不定位到地塊。所有權人僅標本人/配偶/未成年子女。<br>`+
  `・參考估值為實價登錄同段中位數×持分面積的粗估，非申報值、非鑑價。<br>`+
  `・${up} 筆宜蘭不動產因僅寫路名（未辦保存）或為重測前舊地段名，尚未定位，另列清單。縣外 ${DATA.out_of_county.length} 筆見上方面板。`;

// ---- transport overlays (HSR planned / TRA / bus transfer) ----
const POI = /*__POI__*/;
function emIcon(ch,s){ return L.divIcon({html:`<div style="font-size:${s}px;line-height:${s}px;text-align:center;filter:drop-shadow(0 1px 1px #0007)">${ch}</div>`,className:'',iconSize:[s,s],iconAnchor:[s/2,s/2]}); }
function hav(la1,ln1,la2,ln2){ const R=6371000,p=Math.PI/180,dla=(la2-la1)*p,dln=(ln2-ln1)*p,a=Math.sin(dla/2)**2+Math.cos(la1*p)*Math.cos(la2*p)*Math.sin(dln/2)**2; return 2*R*Math.asin(Math.sqrt(a)); }
function badgeIcon(ch,d,border){ return L.divIcon({className:'',iconSize:[d,d],iconAnchor:[d/2,d/2],
  html:`<div style="width:${d}px;height:${d}px;border-radius:50%;background:#fff;border:2.5px solid ${border};display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px #0007;font-size:${Math.round(d*0.56)}px;line-height:1">${ch}</div>`}); }
function shieldIcon(txt,bg){ return L.divIcon({className:'',iconSize:[34,20],iconAnchor:[17,10],
  html:`<div style="padding:1px 5px;border-radius:5px;background:${bg};color:#fff;font-size:11px;font-weight:700;letter-spacing:.5px;box-shadow:0 1px 4px #0007;border:1.5px solid #fff;white-space:nowrap;text-align:center">${txt}</div>`}); }
function lbl(m,name,off){ m.bindTooltip(name,{permanent:true,direction:'top',className:'poilbl',offset:off||[0,-13]}); return m; }
// popup shared by every transport node: the node + which 段 within 1km someone holds (reflects filters)
function nodePopup(title, lat, lng, note){
  const near=[];
  for(const [k,sec] of Object.entries(DATA.sections)){
    const d=hav(lat,lng,sec.lat,sec.lng);
    if(d<=1000){ const hs=activeFor(k); if(hs.length) near.push({nm:sec.t+sec.n,d:Math.round(d),hs}); }
  }
  near.sort((a,b)=>a.d-b.d);
  const rows=near.map(n=>{ const who=[...new Set(n.hs.map(h=>h.name+'('+h.party+')'))].join('、');
    return `<tr><td>${n.nm}</td><td class="r">${n.d}m</td><td>${who}</td></tr>`; }).join('');
  return `<div class="pop"><div class="sec-title">${title}</div>`+(note?`<div class="note" style="margin:3px 0 5px">${note}</div>`:'')+
    `<b>1 公里內有政治人物持有的地段：${near.length} 段</b>`+
    (rows?`<table><tr style="color:#5b616b"><td>地段</td><td class="r">距離</td><td>持有人</td></tr>${rows}</table>`:'<div class="note">（目前篩選條件下無）</div>')+
    `<div class="note">距離以地段中心估算。</div></div>`;
}
function tname(s){ return s.heritage ? s.name+'（林鐵）' : '臺鐵'+s.name+'站'; }
const POPT={maxWidth:360};

const railLayer=L.layerGroup();
POI.rail.forEach(s=>{
  const m = s.major ? lbl(L.marker([s.lat,s.lng],{icon:badgeIcon('🚉',26,'#2c3e50'),zIndexOffset:1000}), tname(s), [0,-15])
                    : L.marker([s.lat,s.lng],{icon:emIcon(s.heritage?'🚞':'🚉',14)}).bindTooltip(tname(s),{direction:'top'});
  m.bindPopup(()=>nodePopup('🚉 '+tname(s), s.lat, s.lng, ''), POPT).addTo(railLayer);
});
const busLayer=L.layerGroup();
POI.bus.forEach(s=> lbl(L.marker([s.lat,s.lng],{icon:badgeIcon('🚌',24,'#e67e22'),zIndexOffset:1000}), s.name)
  .bindPopup(()=>nodePopup('🚌 '+s.name, s.lat, s.lng, ''), POPT).addTo(busLayer));
const rampLayer=L.layerGroup();
POI.ramp.forEach(s=> lbl(L.marker([s.lat,s.lng],{icon:shieldIcon('國5','#1a7a3a'),zIndexOffset:1000}), s.name, [0,-11])
  .bindPopup(()=>nodePopup('🛣️ '+s.name+'（國道5號）', s.lat, s.lng, ''), POPT).addTo(rampLayer));
const hsrLayer =L.layerGroup();
POI.hsr.forEach(s=>{
  L.circle([s.lat,s.lng],{radius:1000,color:'#d62828',weight:1.5,dashArray:'5,5',fill:false,interactive:false}).addTo(hsrLayer);
  lbl(L.marker([s.lat,s.lng],{icon:badgeIcon('🚄',32,'#d62828'),zIndexOffset:1200}), s.name, [0,-18])
    .bindPopup(()=>nodePopup('🚄 '+s.name, s.lat, s.lng, s.note), POPT).addTo(hsrLayer);
});
hsrLayer.addTo(map); railLayer.addTo(map); busLayer.addTo(map); rampLayer.addTo(map);
layerCtl.addOverlay(hsrLayer,'🚄 高鐵宜蘭站（規劃）');
layerCtl.addOverlay(railLayer,'🚉 台鐵車站（大站放大）');
layerCtl.addOverlay(busLayer,'🚌 轉運站');
layerCtl.addOverlay(rampLayer,'🛣️ 國道5號交流道');
function toggleLbl(){ document.body.classList.toggle('lblhide', map.getZoom()<12); }
map.on('zoomend',toggleLbl); toggleLbl();

renderLegend(); refresh();
document.getElementById('zoomHint').textContent='圈＝段內有人持有(非整段)，大小＝持分面積；放大顯示段範圍外框';
</script>
</body>
</html>
"""

out = (TEMPLATE.replace('/*__DATA__*/', json.dumps(DATA, ensure_ascii=False, separators=(',', ':')))
               .replace('/*__POI__*/', json.dumps(POI, ensure_ascii=False, separators=(',', ':'))))
(HERE / 'docs' / 'index.html').write_text(out, encoding='utf-8')
print('wrote docs/index.html', round(len(out)/1024), 'KB')
