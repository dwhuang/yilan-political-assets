"""inputs/ -> output/yilan.json  (the core dataset: {people, rows}).

Parses the per-row real-estate declarations for the 2026 Yilan candidates (from the
candidate-wealth-tw AI transcriptions) and the sitting incumbents (from 監察院), and
attaches a rough per-row value estimate (實價登錄 same-section unit-price median x owned
area). Consumed by build_sections.py and build_xlsx.py."""
import json, os, re, csv, sys
import pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
R = str(HERE / 'inputs' / 'candidate_wealth')
T = R + '/transcriptions'
idx = [c for c in json.load(open(R + '/candidates_index.json')) if c.get('City_ID_NM') == '宜蘭縣' and c['YEAR'] == '115']
parties = json.load(open(R + '/parties_115.json'))
lvr = json.load(open(R + '/prices/lvr_115.json'))
LAND, HOUSE = lvr['land'], lvr['house']

# 曹天民 filed twice; keep the later corrected filing (3280)
idx = [c for c in idx if c['SEQNO'] != '3279']

CN = '〇一二三四五六七八九'
def cnum(m):
    n = int(m.group(0))
    if n < 10: return CN[n]
    if n < 20: return '十' + (CN[n % 10] if n % 10 else '')
    if n < 100: return CN[n // 10] + '十' + (CN[n % 10] if n % 10 else '')
    return m.group(0)
def norm_sec(s):
    s = re.sub(r'[（(].*?[）)]', '', s).replace('台', '臺').replace('双', '雙').replace('塩', '鹽').replace(' ', '')
    s = re.sub(r'\d+', cnum, s)
    s = re.sub(r'〇小段$', '', s)
    return s

TOWNS = ['宜蘭市','羅東鎮','蘇澳鎮','頭城鎮','礁溪鄉','壯圍鄉','員山鄉','冬山鄉','五結鄉','三星鄉','大同鄉','南澳鄉']
def parse_loc(loc):
    loc = (loc or '').replace('台', '臺').replace(' ', '')
    if any(loc.startswith(t) for t in TOWNS): loc = '宜蘭縣' + loc
    m = re.match(r'^(..[縣市])(.{1,3}?[鄉鎮市區])?(.*)$', loc)
    if not m: return None, None, loc
    county, town, rest = m.group(1), m.group(2), m.group(3)
    if county == '宜蘭市':  # "宜蘭市xx段" with no county
        county, town = '宜蘭縣', '宜蘭市'; rest = m.group(2) and (m.group(2) + rest) or rest
    return county, town, rest

def share_val(s):
    s = re.sub(r'[（(].*?[）)]', '', (s or '')).strip()
    s = s.translate(str.maketrans('一二三四五六七八九', '123456789')).replace('10000之', '10000分之')
    m = re.match(r'^\s*([\d,]+)\s*/\s*([\d,]+)\s*$', s)
    if m:
        a, b = int(m.group(1).replace(',', '')), int(m.group(2).replace(',', ''))
        if b: return a / b
    m = re.match(r'^\s*([\d,.]+)\s*分之\s*([\d,.]+)\s*$', s)
    if m:
        b, a = float(m.group(1).replace(',', '')), float(m.group(2).replace(',', ''))
        if b: return a / b
    m = re.match(r'^0?\.\d+$|^1(\.0+)?$', s)
    if m: return float(s)
    if s in ('全部', '1', '1/1', '所有權全部', '全', '1分之1'): return 1.0
    return None

def price_val(p):
    if p is None: return None
    p = str(p).replace(',', '').strip()
    try: return float(p)
    except: return None

def role(owner, d):
    o = (owner or '').strip()
    if not o or o == d['declarant'] or o in ('本人', '申報人'): return '本人'
    if o == '配偶': return '配偶'
    if d.get('spouse') and o == d['spouse']: return '配偶'
    return '未成年子女' if d.get('minor_children_count') else '其他'

# Fixes checked by eye against the original PDF
OVERRIDES = {('3306', 'buildings', 0): {'area_m2': 203.0}}
def pick(seq):
    for dd in ('y115_pro', 'y115_flash'):
        f = f'{T}/{dd}/{seq}.json'
        if os.path.exists(f):
            rec = json.load(open(f))
            for (s, sec, i), patch in OVERRIDES.items():
                if s == seq: rec['data'][sec][i].update(patch)
            return dd, rec
    return None, None

def look(tbl, key, nmin):
    v = tbl.get(key)
    if v and v[0] >= nmin and v[3] <= v[1] * 1.01 and nmin > 1: return None  # flat split-sale series
    return v if v and v[0] >= nmin else None

def estimate(kind, county, town, sec, owned):
    """Simplified version of the project's method: section-level medians only for land, falls back for buildings."""
    if not (county and town and sec and owned): return None
    full = norm_sec(sec)
    no_sub = re.sub(r'[一二三四五六七八九十]+小段$', '', full)
    if kind == '建物':
        if owned > 300: return ('大型建物(>300㎡)，住宅行情不適用，不計入', None)
        for lvl, key, n in (('段', f'S|{county}|{town}|{full}', 3), ('段(不分小段)', f'S0|{county}|{town}|{no_sub}', 5), ('鄉鎮市', f'T|{county}|{town}', 5)):
            v = look(HOUSE, key, n)
            if v: return (lvl, v)
        return None
    big = owned >= 1000
    keys = ((('段(大面積)', f'SL|{county}|{town}|{full}', 3), ('段(不分小段,大面積)', f'S0L|{county}|{town}|{no_sub}', 5)) if big else
            (('段', f'S|{county}|{town}|{full}', 3), ('段(不分小段)', f'S0|{county}|{town}|{no_sub}', 5)))
    for lvl, key, n in keys:
        v = look(LAND, key, n)
        if v:
            if v[3] > 5 * v[1]: return ('同段價差過大(農地/建地混雜)，不計入', v)
            return (lvl, v)
    return None

people, rows = [], []
for c in idx:
    seq = c['SEQNO']; dd, rec = pick(seq); d = rec['data']
    party = parties.get(seq, {}).get('party') or '無黨籍'
    office = '縣長' if c['ElectType_NM'].startswith('縣') and '長' in c['ElectType_NM'] else '縣議員'
    dist = '全縣' if office == '縣長' else c['Dist_NM'].replace('宜蘭縣', '')
    trust = d.get('trust_items') or []
    items = [('土地', x) for x in d['land']] + [('建物', x) for x in d['buildings']]
    bldg_keys = set()
    for kind, x in items:
        if kind == '建物':
            co, tw, sec = parse_loc(x.get('location'))
            sh0 = share_val(x.get('share')); a0 = x.get('area_m2')
            e0 = estimate('建物', co, tw, sec, round(a0 * sh0, 2) if (a0 and sh0 is not None) else None)
            if not (e0 and e0[1]): continue  # land under an unvalued building keeps its own estimate
            bldg_keys.add((role(x.get('owner'), d), tw, re.sub(r'[一二三四五六七八九十\d]+小段$', '', norm_sec(sec or '')), x.get('acquired')))
    for i, (kind, x) in enumerate(items):
        co, tw, sec = parse_loc(x.get('location'))
        sh = share_val(x.get('share')); area = x.get('area_m2')
        owned = round(area * sh, 2) if (area and sh is not None) else None
        joint = '公同共有' in json.dumps(x, ensure_ascii=False) or '共同共有' in json.dumps(x, ensure_ascii=False)
        rl = role(x.get('owner'), d)
        base = kind == '土地' and (rl, tw, re.sub(r'[一二三四五六七八九十\d]+小段$', '', norm_sec(sec or '')), x.get('acquired')) in bldg_keys
        est = estimate(kind, co, tw, sec, owned) if not joint else None
        lvl = est[0] if est else ''
        v = est[1] if est else None
        counted = bool(v) and not joint and not base and lvl in ('段', '段(不分小段)', '段(大面積)', '段(不分小段,大面積)', '鄉鎮市')
        rows.append(dict(seq=seq, name=c['NAME'], office=office, district=dist, party=party, owner_role=rl, kind=kind,
            county=co or '', town=tw or '', section=sec or '', location_as_written=x.get('location') or '',
            area_m2=area, share=x.get('share') or '', owned_m2=owned, acquired=x.get('acquired') or '', reason=x.get('reason') or '',
            declared_price=price_val(x.get('price')), price_note='' if price_val(x.get('price')) is not None else (x.get('price') or ''),
            note=('公同共有' if joint else ('建物基地(價值含在建物)' if base else '')),
            est_level=lvl, est_n=v[0] if v else None, unit_median=v[2] if v else None,
            est_twd=round(v[2] * owned) if (v and owned) else None, est_low=round(v[1] * owned) if (v and owned) else None,
            est_high=round(v[3] * owned) if (v and owned) else None, est_counted=counted, source=dd))
    people.append(dict(seq=seq, name=c['NAME'], office=office, district=dist, party=party, declare_date=d['declare_date'],
        land_listed=len(d['land']), land_declared_total=d['land_count'], bldg_listed=len(d['buildings']), bldg_declared_total=d['building_count'],
        trust_items=len(trust), trust_raw=trust, notes=d.get('notes') or '', source=dd,
        pdf=f'https://pdps-dec.cec.gov.tw/release/formal/files/{seq}.pdf'))


# ---------- sitting officials not on the 2026 ballot (監察院廉政專刊) ----------
CUR_INCUMBENT_CANDIDATES = set('張勝德 林麗 林錫明 黃定和 林岳賢 林詩穎 賴良洲 林聰池 黃浴沂 黃建勇 陳福山 謝家倫 陳漢鍾 黃琤婷 呂惠卿 林義剛 沈信雄 林佩螢 楊弘旻 邱素梅 陳玉萍 孫湯玉惠 沈志弘'.split())
for p in people: p['status'] = '現任議員・參選' if p['name'] in CUR_INCUMBENT_CANDIDATES else '候選人'
INC = {  # name: office, district, party, declare date, source, spouse
 '林姿妙': ('縣長（停職中）', '全縣', '中國國民黨', '113年11月01日', '廉政專刊第283期（114/09/23）P63-67', ''),
 '林茂盛': ('代理縣長（副縣長）', '全縣', '非選任', '114年11月01日', '廉政專刊第317期（115/05/26）P371-374', '王淑卿'),
 '楊順木': ('縣議員', '第1選舉區', '正神名黨', '114年11月01日', '廉政專刊第310期（115/04/30）P395-398', '吳秀英'),
 '黃惠慈': ('縣議員', '第1選舉區', '民主進步黨', '114年11月01日', '廉政專刊第310期（115/04/30）P370-372', ''),
 '吳宏謀': ('縣議員', '第3選舉區', '民主進步黨', '114年11月01日', '廉政專刊第310期（115/04/30）P231-234', '林阿秀'),
 '黃雯如': ('縣議員', '第4選舉區', '中國國民黨', '114年11月01日', '廉政專刊第310期（115/04/30）P378-382', '張宜樺'),
 '陳鴻禧': ('縣議員', '第6選舉區', '中國國民黨', '114年12月16日', '廉政專刊第310期（115/04/30）P338-342', '李宇惠'),
 '簡松樹': ('縣議員', '第7選舉區', '民主進步黨', '114年11月01日', '廉政專刊第310期（115/04/30）P417-418', '潘寶琴'),
 '謝燦輝': ('縣議員', '第8選舉區', '民主進步黨', '114年11月01日', '廉政專刊第310期（115/04/30）P411-415', '薛美玲'),
 '陳文昌': ('縣議員', '第9選舉區', '民主進步黨', '114年11月01日', '廉政專刊第310期（115/04/30）P321-323', '余玉女'),
 '謝正信': ('縣議員', '第10選舉區', '民主進步黨', '114年11月01日', '廉政專刊第310期（115/04/30）P406-409', '李韻秋'),
 '游吉祥': ('縣議員', '第13選舉區', '中國國民黨', '114年11月01日', '廉政專刊第310期（115/04/30）P384-388', '吳佩琳'),
}
raw = [l.rstrip('\n').split('|') for l in open(str(HERE / 'inputs' / 'incumbents_raw.txt'), encoding='utf-8') if l.strip()]
for k, name in enumerate(INC):
    office, dist, party, ddate, src, spouse = INC[name]
    seq = f'C{k+1:02d}'
    mine = [r for r in raw if r[0] == name]
    people.append(dict(seq=seq, name=name, office=office, district=dist, party=party, declare_date=ddate,
        land_listed=sum(r[1] == '土地' for r in mine), land_declared_total=None, bldg_listed=sum(r[1] == '建物' for r in mine), bldg_declared_total=None,
        trust_items=sum('信託' in r[9] for r in mine), trust_raw=[], notes='', source='監察院廉政專刊', pdf='https://priso.cy.gov.tw/layout/baselist', src_detail=src,
        status='現任・未參選'))
    d = {'declarant': name, 'spouse': spouse, 'minor_children_count': 0}
    bldg_keys = set()
    for r in mine:
        if r[1] == '建物':
            co, tw, sec = parse_loc(r[2]); sh0 = share_val(r[4]); a0 = float(r[3].replace(',', '')) if r[3] else None
            e0 = estimate('建物', co, tw, sec, round(a0 * sh0, 2) if (a0 and sh0 is not None) else None)
            if e0 and e0[1]:
                bldg_keys.add((role(r[5], d), tw, re.sub(r'[一二三四五六七八九十\d]+小段$', '', norm_sec(sec or '')), r[6]))
    for r in mine:
        _, kind, loc, area, share, owner, acq, reason, price, note = r
        co, tw, sec = parse_loc(loc)
        area = float(area.replace(',', '')) if area else None
        sh = share_val(share); owned = round(area * sh, 2) if (area and sh is not None) else None
        rl = role(owner, d)
        base = kind == '土地' and (rl, tw, re.sub(r'[一二三四五六七八九十\d]+小段$', '', norm_sec(sec or '')), acq) in bldg_keys
        est = estimate(kind, co, tw, sec, owned)
        lvl = est[0] if est else ''; v = est[1] if est else None
        counted = bool(v) and not base and lvl in ('段', '段(不分小段)', '段(大面積)', '段(不分小段,大面積)', '鄉鎮市')
        pn = float(price) if price.replace('.', '').isdigit() else None
        notes = [x for x in (note, '建物基地(價值含在建物)' if base else '') if x]
        rows.append(dict(seq=seq, name=name, office=office, district=dist, party=party, owner_role=rl, kind=kind,
            county=co or '', town=tw or '', section=sec or '', location_as_written=loc, area_m2=area, share=share, owned_m2=owned,
            acquired=acq, reason=reason, declared_price=pn, price_note='' if pn is not None else price, note='；'.join(notes),
            est_level=lvl, est_n=v[0] if v else None, unit_median=v[2] if v else None,
            est_twd=round(v[2] * owned) if (v and owned) else None, est_low=round(v[1] * owned) if (v and owned) else None,
            est_high=round(v[3] * owned) if (v and owned) else None, est_counted=counted, source='監察院廉政專刊'))

json.dump(dict(people=people, rows=rows), open(str(HERE / 'output' / 'yilan.json'), 'w'), ensure_ascii=False, indent=1)
print(len(people), len(rows))
bad = [p for p in people if p['land_declared_total'] is not None and p['land_listed'] != (p['land_declared_total'] or 0) or p['bldg_listed'] != (p['bldg_declared_total'] or 0)]
for p in bad: print('COUNT MISMATCH', p['seq'], p['name'], p['land_listed'], p['land_declared_total'], p['bldg_listed'], p['bldg_declared_total'])
print('trusts:', [(p['name'], p['trust_items']) for p in people if p['trust_items']])
