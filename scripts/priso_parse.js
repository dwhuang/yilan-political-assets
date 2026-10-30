// 監察院財產申報查詢 (https://priso.cy.gov.tw/layout/baselist) 的擷取工具
// 用法：在瀏覽器開啟上面的網址，打開開發者工具 Console，貼上整份程式碼後執行：
//   const rows = await priso.fetchLatest('吳宏謀', '310');   // 姓名、廉政專刊期別
//   console.table(rows);
// 本頁的 CSP 允許 fetch 外部網址與 unsafe-eval，所以用 eval 載入 pdf.js 3.x（UMD 版，主執行緒模式）。
// 欄位 x 座標是廉政專刊財產申報表的固定版面；換版時要重新量。

window.priso = (() => {
  const query = async (value, size = 50) => {
    const r = await fetch('/api/Query/QueryData', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ Data: { Method: '', Type: '', Value: value },
        Page: { PageNo: 1, PageSize: size, TotalCount: 0, OrderByNum: 0, OrderBySort: '' } }) });
    return (await r.json()).Data.Data;   // [{Name, Period, Dept, Title, PublishType, PublishDate, PublishPage, Id}]
  };

  let loaded = false;
  const loadPdfJs = async () => {
    if (loaded) return;
    const base = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/';
    (0, eval)(await fetch(base + 'pdf.min.js').then(r => r.text()));
    (0, eval)(await fetch(base + 'pdf.worker.min.js').then(r => r.text()));
    loaded = true;
  };

  const getDoc = async (fileId) => {
    await loadPdfJs();
    const r = await fetch('/api/Query/getFile', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ From: 'base', FileId: fileId }) });
    return pdfjsLib.getDocument({ data: await (await r.blob()).arrayBuffer() }).promise;
  };

  // 解析「（二）不動產」的土地與建物表。列錨點＝坐落欄中以「XX縣/市」開頭的文字；
  // 坐落欄的續行歸給上方最近的錨點，其他欄位歸給垂直距離最近的錨點。
  const parse = async (doc) => {
    const cols = [[0, 200, 'loc'], [200, 255, 'area'], [255, 315, 'share'], [315, 383, 'owner'],
                  [383, 440, 'date'], [440, 492, 'reason'], [492, 999, 'price']];
    const col = x => cols.find(c => x >= c[0] && x < c[1])[2];
    const isAnchor = s => /^[一-鿿]{2}[縣市]/.test(s.replace(/^\d*★/, ''));
    const rows = []; let kind = null, done = false;
    for (let p = 1; p <= doc.numPages && !done; p++) {
      const tc = await (await doc.getPage(p)).getTextContent();
      const it = tc.items.filter(i => i.str.trim()).map(i => ({ x: i.transform[4], y: i.transform[5], s: i.str.trim() }))
        .sort((a, b) => b.y - a.y || a.x - b.x);
      const top = Math.max(...it.map(i => i.y)), bot = Math.min(...it.map(i => i.y));
      const region = [];
      for (const i of it) {
        if (i.y >= top - 14 || i.y <= bot + 14) continue;           // 頁首、頁尾
        if (/^（三）/.test(i.s) && kind) { done = true; break; }
        if (/^土地$/.test(i.s) && i.x < 120) { kind = '土地'; continue; }
        if (/^建物/.test(i.s) && i.x < 120) { kind = '建物'; continue; }
        if (kind) region.push({ ...i, kind });
      }
      const pageRows = region.filter(i => col(i.x) === 'loc' && isAnchor(i.s)).map(a => ({ kind: a.kind, _y: a.y, p, _items: [] }));
      const hdrY = {}; for (const i of region) if (i.s === '所 有 權 人') hdrY[i.kind] = i.y;
      for (const i of region) {
        if (/本欄空白/.test(i.s)) continue;
        const same = pageRows.filter(r => r.kind === i.kind); if (!same.length) continue;
        if (hdrY[i.kind] !== undefined && i.y >= hdrY[i.kind] - 10 && i.y > same[0]._y) continue;  // 表頭
        let best;
        if (col(i.x) === 'loc') best = same.filter(r => r._y >= i.y - 1).pop() || same[0];
        else { best = same[0]; for (const r of same) if (Math.abs(r._y - i.y) < Math.abs(best._y - i.y)) best = r; }
        best._items.push(i);
      }
      rows.push(...pageRows);
    }
    return rows.map(r => {
      const by = {}; for (const i of r._items) (by[col(i.x)] = by[col(i.x)] || []).push(i);
      const cell = c => (by[c] || []).sort((a, b) => b.y - a.y || a.x - b.x).map(i => i.s);
      const o = { kind: r.kind, page: r.p };
      for (const c of ['loc', 'area', 'share', 'owner', 'date', 'reason', 'price']) o[c] = cell(c).join(' ');
      o.area_num = cell('area').find(s => /^[\d,]+(\.\d+)?$/.test(s)) || null;
      const dm = o.date.replace(/\s/g, '').match(/(\d+)年(\d+)月(\d+)日/); o.date_n = dm ? `${dm[1]}/${dm[2]}/${dm[3]}` : null;
      return o;
    });
  };

  // 取某人某期的「01一般申報」並解析。跨頁斷行偶爾會讓日期或面積變成 null，需對照原文補正。
  const fetchLatest = async (name, period) => {
    const list = (await query(name)).filter(d => d.Name.startsWith(name));
    const d = list.find(x => (!period || x.Period === period) && x.PublishType.startsWith('01'));
    if (!d) throw new Error('查無一般申報：' + name);
    return parse(await getDoc(d.Id));
  };

  return { query, getDoc, parse, fetchLatest };
})();
