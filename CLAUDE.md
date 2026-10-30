# CLAUDE.md

專案說明見 `README.md`（給一般讀者的完整介紹、資料來源、方法與限制）。本檔是給接手開發者/
Claude 的技術備忘。**請用繁體中文回覆。**

## 管線（平常不打 API，用附帶的 NLSC 快取）

`scripts/extract.py`（inputs → `output/yilan.json`：解析申報、估值）
→ `scripts/build_sections.py`（NLSC 快取 + yilan.json → 段幾何、`map_data.json`、`placement.json`、`待處理_舊地段.md`）
→ `scripts/build_map_html.py`（→ `docs/index.html`）、`scripts/build_probes_html.py`（→ `docs/probes.html`）。
`build_xlsx.py` 另產 Excel。`make site` 一次跑完。

重建快取（慢，數小時）：`scripts/geocode_sections.py`（均勻基底網格）+ `scripts/refine_boundaries.py`
（自適應四叉樹，只在段界加密 300→37.5m）。`make sample`。

## 關鍵技術備忘

- **地段定位**：NLSC 免費「單點坐標回傳段籍」API 只能反查（點→段），無免費「段名→座標」。
  故用反查網格取樣求各段輪廓；快取在 `inputs/geo/nlsc_cache.jsonl`（約 7.7 萬點）。
- **畫段範圍**（`add_voronoi_rings`）：最近點（Voronoi）網格化（scipy cKDTree）；每格歸最近
  取樣點之段、距離 ≤230m。忠實呈現（API 回傳即真實段，不刪碎塊；>12 環才退回只畫點）。外框
  去共線點 + Douglas-Peucker 平滑。圓點錨點用**不可達極點** `_pole`（凹形段的平均中心會落在段外）。
- **舊/錯字/家族段名**：在 `build_sections.py` 的 `RENAME`/`ROADMAP` 對映到現行段；僅路名者
  用 OSM→NLSC 反查落點（`output/road_placements.json`）。仍有約 18 筆未定位（見 `待處理_舊地段.md`）。
- **環境雷**：NLSC 憑證缺 SKI，`urllib` 需 `ssl._create_unverified_context()`（curl 正常）。
  宜蘭縣政府 `*.e-land.gov.tw`（新舊地建號對照表、地政得來速）從本機 sandbox 連不到（TLS reset），
  要補那 18 筆的現行段需由瀏覽器下載對照表。
- **地圖**：本機/靜態 HTML（NLSC WMTS 底圖 + Leaflet CDN 為外部連線，故非 Artifact），資料內嵌。

## 隱私原則（務必維持）

公開只到「段」；地號/門牌不輸出、不反推。所有權人只標「本人／配偶／未成年子女」，不輸出姓名。
