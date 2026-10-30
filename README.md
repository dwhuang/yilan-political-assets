# 宜蘭縣政治人物不動產地圖

> An interactive map of real-estate holdings declared by Yilan County (Taiwan)
> politicians — 2026 county-magistrate & councillor candidates plus sitting
> incumbents — placed at the land-section (段) level over the official cadastral
> basemap. Built from public filings; shows *where* holdings are, not exact parcels.

**🗺️ 線上地圖 / Live map:** https://dwhuang.github.io/yilan-political-assets/

把宜蘭縣政治人物「公開財產申報」中的不動產，整理並畫到以「地段」為單位的互動地圖上。
資料全來自公開申報，只呈現到「段」，地號與門牌依法遮蔽——重點是看**誰在哪一段有不動產、
大致多少**，而不是定位到單一地塊。

## 收錄範圍（共 76 人、968 筆不動產）

- **2026/11/28 選舉候選人**：宜蘭縣長 5 位、縣議員 59 位（申報日約 115 年 8–9 月）。
- **未參選的現任者 12 人**：停職中縣長林姿妙、代理縣長（副縣長）林茂盛，及第 20 屆未登記
  參選的 10 位縣議員（申報多為 114 年 11 月定期申報，來源為監察院廉政專刊）。

兩種申報時間點不同（候選人 115/8–9；現任者多為 114/11），地圖的「身分」欄可區分。

## 地圖怎麼看

- **圓點 = 該段內有政治人物持有不動產**（**不代表整段為其所有**）。大小可切換「依參考估值
  （預設）／依持分面積」；同一段有多位不同政黨持有時，圓點畫成**餅圖**（各黨依比例分扇形）。
- **外框 = 該段的大致範圍**（放大後顯示），只供定位，不代表持有範圍。
- 可依**政黨 / 身分 / 選區 / 姓名**篩選；點圓點在左下角看持有明細（含政黨比例）並高亮該段。
- **交通疊圖**（右下角切換）：規劃高鐵宜蘭站（含 1km 範圍圈）、臺鐵車站、轉運站、國道 5 號
  交流道；點任一節點可看其 1 公里內的政治人物持有地段。
- **縣外持有**另列面板（地圖只畫宜蘭縣內）。

## 資料來源與授權

| 資料 | 來源 | 授權/註記 |
|---|---|---|
| 候選人申報逐筆 | 中選會公告 PDF（掃描檔），經開源專案 **[候選人財產透視 candidate-wealth-tw](https://github.com/Sigma-Snaken/candidate-wealth-tw)** 以 AI 轉錄 | CC BY 4.0；須標示該專案與貢獻者，並註明為 AI 轉錄、以原件為準（見 `inputs/candidate_wealth/LICENSE-DATA.md`） |
| 現任者申報逐筆 | 監察院《廉政專刊》財產申報（有文字層 PDF） | 政府資料開放授權 |
| 地段位置/範圍 | 國土測繪中心（NLSC）免費「單點坐標回傳段籍」API + 段籍圖 WMTS 底圖 | 政府資料開放授權 |
| 參考估值 | 內政部不動產**實價登錄**同段單價中位數 × 持分面積 | 政府資料開放授權；為粗估，非鑑價 |
| 交通節點 | OpenStreetMap（Overpass） | © OSM contributors, ODbL |

程式碼為 MIT（見 `LICENSE`）；各項**資料**依其原始授權。

## 方法與限制（重要）

- **參考估值是推估、不是鑑價、也不是申報值**：用同段實價登錄單價中位數 × 持分面積。農地、
  原住民保留地、公同共有、持分不明者多半估不出；合計只是下限式粗估。
- **只到「段」**：公開資料遮蔽地號/門牌，無法定位到單一地塊，也無法得知段內確切位置。
- **地段範圍是反查推估、非實測地籍線**：以 NLSC 免費 API 反查網格（邊界處自適應加密至約
  37.5m），再用最近點（Voronoi）網格化描邊——是約略輪廓，階梯狀邊界已平滑處理。
- **重測前舊地段**：部分申報用的是重測前舊段名，已不在現行地籍；能對應者已修正，仍有約
  18 筆（含僅寫路名的未辦保存建物）尚未定位，另列於 `output/待處理_舊地段.md`。
- 詳細核對情形見 `output/宜蘭縣政治人物不動產申報.xlsx` 的「說明」分頁。

## 隱私原則

- 只呈現到「段」；地號、門牌不輸出、不反推。
- 所有權人只標「本人／配偶／未成年子女」，不輸出配偶、子女姓名。

## 專案結構

```
inputs/          原始資料（來源見上）
  candidate_wealth/      候選人逐筆轉錄（CC BY，上游專案）
  incumbents_raw.txt     現任者逐筆（由監察院 PDF 整理，| 分隔）
  geo/nlsc_cache.jsonl   NLSC 反查快取（已附，避免再打 API）
scripts/         建置程式（見下方管線）
output/          產生的資料（yilan.json、map_data.json、xlsx…）
docs/            發布的網站（GitHub Pages）：index.html=地圖, probes.html=取樣偵錯圖
```

## 重現 / 建置

需求：Python 3，`pip install -r requirements.txt`（numpy、scipy、openpyxl）。

```bash
make site     # 用附帶的 NLSC 快取重建全部（不打任何 API）→ docs/index.html
make xlsx     # 另外產生 Excel
```

各階段：`make data`（解析申報→`output/yilan.json`）→ `make sections`（快取+yilan.json→
段幾何與 `map_data.json`）→ `make map`（→`docs/index.html`）。

`make sample` 會重新向 NLSC API 反查、重建快取——**耗時數小時**，平常不需要（快取已附）。

`scripts/priso_parse.js` 是一次性的瀏覽器 Console 程式，用來從監察院網站擷取現任者申報
（產生 `inputs/incumbents_raw.txt`），非 Python 管線的一部分。
