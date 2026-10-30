"""output/yilan.json -> output/宜蘭縣政治人物不動產申報.xlsx  (說明 / 人物總覽 / 不動產明細).

The 人物總覽 sheet uses Excel formulas (COUNTIFS/SUMIFS), so values recalc when opened;
open once in Excel/LibreOffice if you need the computed numbers read back."""
import json, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

import pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
D = json.load(open(HERE / 'output' / 'yilan.json'))
rows, people = D['rows'], D['people']
F = 'Arial'
hdr_font = Font(name=F, bold=True, color='FFFFFF'); hdr_fill = PatternFill('solid', fgColor='2F4858')
base = Font(name=F, size=10)

# order people: mayor first, then by estimated total desc
tot = {}
for r in rows:
    if r['est_counted']: tot[r['seq']] = tot.get(r['seq'], 0) + r['est_twd']
people.sort(key=lambda p: (0 if '縣長' in p['office'] else 1, -tot.get(p['seq'], 0)))

wb = Workbook()
ws = wb.active; ws.title = '人物總覽'
det = wb.create_sheet('不動產明細')
note = wb.create_sheet('說明')

# ---- detail sheet
dcols = ['編號', '姓名', '職位/參選', '選區', '政黨', '所有權人', '類別', '縣市', '鄉鎮市區', '地段（坐落）', '坐落原文',
         '面積(㎡)', '權利範圍', '持分面積(㎡)', '取得日期(民國)', '取得原因', '申報取得價額（原文）', '備註',
         '估值依據', '同區成交筆數', '單價中位數(元/㎡)', '參考估值(元)', '估值下緣(元)', '估值上緣(元)', '計入合計']
det.append(dcols)
def clean_price(r):
    if r['declared_price'] is not None: return f"{r['declared_price']:,.0f}"
    return re.sub(r'\(\((.*?)\)\)', r'(\1)', r['price_note']).replace('((', '(').replace('))', ')')
for r in sorted(rows, key=lambda r: ([p['seq'] for p in people].index(r['seq']), r['kind'] != '土地')):
    det.append([r['seq'], r['name'], r['office'], r['district'], r['party'], r['owner_role'], r['kind'], r['county'], r['town'],
                r['section'], r['location_as_written'], r['area_m2'], r['share'], r['owned_m2'], r['acquired'], r['reason'],
                clean_price(r), r['note'], r['est_level'] or '無足夠成交資料', r['est_n'], r['unit_median'],
                r['est_twd'], r['est_low'], r['est_high'], '是' if r['est_counted'] else '否'])
nd = det.max_row
widths = [9, 9, 7, 10, 11, 9, 6, 8, 9, 16, 24, 11, 13, 11, 11, 10, 22, 16, 14, 9, 12, 13, 13, 13, 7]
for i, w in enumerate(widths, 1): det.column_dimensions[get_column_letter(i)].width = w
for row in det.iter_rows(min_row=2):
    for c in row: c.font = base
    for idx in (11, 13): row[idx].number_format = '#,##0.00'
    for idx in (20, 21, 22, 23): row[idx].number_format = '#,##0'
    if row[24].value == '否' and row[21].value: row[21].font = Font(name=F, size=10, color='888888')
t = Table(displayName='明細', ref=f'A1:{get_column_letter(len(dcols))}{nd}')
t.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=True)
det.add_table(t); det.freeze_panes = 'C2'

# ---- summary sheet
scols = ['編號', '姓名', '職位/參選', '選區', '政黨', '身分', '申報日', '土地筆數', '建物筆數', '其中宜蘭縣內筆數', '其中縣外筆數',
         '土地持分面積合計(㎡)', '參考估值合計(萬元)', '估值下緣(萬元)', '估值上緣(萬元)', '未能估值筆數', '原始申報（來源）']
ws.append(scols)
for i, p in enumerate(people, start=2):
    s = f'$A{i}'
    rng = lambda col: f"不動產明細!${col}$2:${col}${nd}"
    ws.append([p['seq'], p['name'], p['office'], p['district'], p['party'], p['status'], (p['declare_date'] or '').replace('民國', ''),
        f'=COUNTIFS({rng("A")},{s},{rng("G")},"土地")',
        f'=COUNTIFS({rng("A")},{s},{rng("G")},"建物")',
        f'=COUNTIFS({rng("A")},{s},{rng("H")},"宜蘭縣")',
        f'=COUNTIFS({rng("A")},{s},{rng("H")},"<>宜蘭縣",{rng("H")},"<>")',
        f'=SUMIFS({rng("N")},{rng("A")},{s},{rng("G")},"土地")',
        f'=SUMIFS({rng("V")},{rng("A")},{s},{rng("Y")},"是")/10000',
        f'=SUMIFS({rng("W")},{rng("A")},{s},{rng("Y")},"是")/10000',
        f'=SUMIFS({rng("X")},{rng("A")},{s},{rng("Y")},"是")/10000',
        f'=COUNTIFS({rng("A")},{s},{rng("Y")},"否",{rng("R")},"<>*建物基地*")',
        p['pdf']])
    lc = ws.cell(i, 17); lc.hyperlink = p['pdf']; lc.value = '中選會原始 PDF' if p['source'] != '監察院廉政專刊' else p.get('src_detail', '')
ns = ws.max_row
for row in ws.iter_rows(min_row=2):
    for c in row: c.font = base
    row[11].number_format = '#,##0'
    for idx in (12, 13, 14): row[idx].number_format = '#,##0'
    row[16].font = Font(name=F, size=10, color='0563C1', underline='single')
for i, w in enumerate([7, 9, 12, 11, 11, 13, 13, 8, 8, 10, 10, 13, 13, 12, 12, 10, 30], 1): ws.column_dimensions[get_column_letter(i)].width = w
t2 = Table(displayName='總覽', ref=f'A1:Q{ns}'); t2.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
ws.add_table(t2); ws.freeze_panes = 'C2'
ws.append([]); 
ws.append(['', '合計', '', '', '', '', ''] + [f'=SUM({c}2:{c}{ns})' for c in 'HIJKLMNOP'])
tr = ws.max_row
for c in ws[tr]: c.font = Font(name=F, size=10, bold=True)
for idx in (11, 12, 13, 14): ws.cell(tr, idx + 1).number_format = '#,##0'
ws.cell(tr + 1, 2, '參考估值為依實價登錄推估的地段行情，不是申報資料，也不是鑑價。估值方法與限制見「說明」分頁。').font = Font(name=F, size=9, italic=True, color='666666')

for sh in (ws, det):
    for c in sh[1]:
        c.font = hdr_font; c.fill = hdr_fill; c.alignment = Alignment(wrap_text=True, vertical='center')
    sh.row_dimensions[1].height = 32

# ---- notes
lines = [
 ('宜蘭縣政治人物不動產申報整理：2026 縣長、縣議員候選人＋現任未參選者', True),
 ('整理日期：2026-10-27', False), ('', False),
 ('範圍（共 76 人）', True),
 ('・2026年11月28日宜蘭縣長（5人）與縣議員（59人）候選人的「公職候選人財產申報表」，申報日約為 115年8月底至9月初。', False),
 ('・不在選票上的現任者 12 人，取自監察院《廉政專刊》最近一期公告：第20屆縣議員中未登記參選的 10 人（楊順木、黃惠慈、吳宏謀、黃雯如、陳鴻禧、簡松樹、謝燦輝、陳文昌、謝正信、游吉祥）、縣長林姿妙（2024年12月31日起停職，申報日 113/11/01，是網上最新一期）、以及目前代理縣長的副縣長林茂盛（非選任，因實際主持縣政一併列入）。', False),
 ('・兩種申報的時間點不同：候選人是 115年8–9月；現任者多為 114年11月的定期申報。', False),
 ('・現任議員異動：陳俊宇 2024年2月轉任立委、由黃雯如補選；莊淑如因當選無效解職、由黃惠慈遞補；李茂豐 2024年10月病逝、席次懸缺，三人皆未列。', False),
 ('・「身分」欄：候選人／現任議員・參選（23人，資料用較新的候選人申報）／現任・未參選。政黨：候選人依中選會登記彙總表（115/09/07），現任者依維基百科現任議員表。', False), ('', False),
 ('資料來源', True),
 ('・候選人原始申報表：中選會公職候選人財產申報系統公告端 https://pdps-dec.cec.gov.tw/release/formal/files/<編號>.pdf （總覽分頁每人有連結）。逐筆轉錄來自開源專案「候選人財產透視」(github.com/Sigma-Snaken/candidate-wealth-tw) 以 AI 從掃描檔轉錄的資料。', False),
 ('・現任者：監察院財產申報資料查詢 https://priso.cy.gov.tw/layout/baselist ，輸入姓名即可下載；總覽分頁列出期別與頁次。這些 PDF 有文字層，本表直接從文字擷取，不是 OCR。', False),
 ('・實價登錄：內政部不動產成交案件實際資訊開放資料（114S1–115S3 買賣），使用上述專案已彙整的各地段單價分位數。', False), ('', False),
 ('核對情形', True),
 ('・候選人 64 人的土地、建物筆數都與申報表上自己寫的「總申報筆數」一致。人工對照原始 PDF 抽查吳宗憲、陳玉萍（打字表）與林義剛（手寫表）；林義剛一筆建物面積轉錄遺漏，已依原件補為 203㎡。手寫申報表較容易誤讀，引用前請以原件為準。', False),
 ('・現任者 12 人：逐人比對擷取筆數與申報表「所有權人」欄出現次數，全部相符；跨頁斷行造成的 4 處缺漏（日期、面積、原因）已依原文補正。', False), ('', False),
 ('欄位說明', True),
 ('・地段：公開版本只到「段/小段」，地號、建號、門牌已依規定遮蔽，所以無法定位到單一地塊。少數未辦保存登記的建物只寫到路名。', False),
 ('・所有權人：只標示「本人／配偶／未成年子女」，不列配偶與子女姓名。', False),
 ('・持分面積 = 面積 × 權利範圍。', False),
 ('・申報取得價額：只有五年內取得者才填，較早取得的寫「超過五年」。部分申報人把同一筆房地總價寫在多列（例如「5-23筆同一取得價額」「房地總價額」），請勿逐列相加。', False),
 ('・已交付信託的不動產（林姿妙全部不動產、林茂盛部分不動產）列在信託申報表，日期欄是信託移轉登記日，不是原始取得日，也沒有取得價額。', False), ('', False),
 ('參考估值的算法（不是申報資料）', True),
 ('・建物：持分面積 300㎡ 以下者，以同一地段（不分樓層、屋齡）房地成交單價中位數 × 建物持分面積；成交不足時依序退到「段（不分小段）」、「鄉鎮市區」。單價已含土地，所以同一人同日取得、同段的土地視為「建物基地」，不另計，避免重複。持分超過 300㎡ 的建物（多為透天、農舍、廠房或商用）以住宅單價推估誤差太大（抽查中有一筆申報價 350 萬、推估卻超過 3,000 萬），因此不估。', False),
 ('・土地：只用同段（或不分小段）的土地成交單價；持分 1,000㎡ 以上改用大面積成交。同段成交價差超過 5 倍（農地、建地混雜）或成交太少則不估。', False),
 ('・估值下緣／上緣為第 25／75 百分位單價。開源專案以 598 組近期買賣校準：建物估值中位數約為申報價的 1.01 倍，土地約 1.16 倍，但單筆誤差常超過 1.4 倍。農地、原住民保留地、公同共有、持分不明的土地多半估不出來，所以「參考估值合計」只是下限式的粗估，不代表個人總資產。', False),
]
for txt, b in lines:
    note.append([txt]); note.cell(note.max_row, 1).font = Font(name=F, size=11 if b else 10, bold=b)
    note.cell(note.max_row, 1).alignment = Alignment(wrap_text=True, vertical='top')
note.column_dimensions['A'].width = 120
wb.move_sheet('說明', offset=-2); wb.active = 1
wb.save(HERE / 'output' / '宜蘭縣政治人物不動產申報.xlsx')
print(ns, nd)
