"""以既有設計結果與已覆核圖面紀錄建立四份成果共用資料；不改動原圖。"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('HVAC_OUTPUT_DIR', ROOT/'outputs/drawing_handoff_20260910'))

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def merge_handoff(base, guidance, followup):
    p=deepcopy(base)
    p['version']='2026-09-10-r4'
    p['equipment_snapshot']['mode']='reused_for_drawing_handoff'
    p['equipment_snapshot']['notice']='本輪沿用2026-09-08保存的設備快照；未重新查詢即時設備資料庫。原查詢日期及來源保持不變。'
    p['drawing_brief']=deepcopy(guidance)
    p['review_actions']=deepcopy(followup['actions'])
    p['fop_actual_checks']=deepcopy(followup['fop_actual_checks'])
    actions={a['id']:a for a in p['review_actions']}
    actions['R01']['steps'].insert(0,'優先核對GF-02：P10/P11未找到試衣間對映；GF-03為開放收銀區，核對是否與GF-01面積及服務重疊。')
    actions['R01']['drawing_impact']+=' GF-02只列系統節點，不建立虛構隔牆或平面定位；GF-03須確認可用安裝面。'
    actions['R02']['steps'].insert(0,'P22一樓試衣間標CH2100，與現行3.0m不同；核對引線範圍及裝修標高後更新1F-02體積與安裝剖面。')
    groups={c['equipment_id']:c for c in p['configuration']}
    units=[]
    seen=set()
    for item in guidance['equipment']:
        group=item['group_id']
        if group not in groups:raise ValueError('不存在的設備群組：'+group)
        c=deepcopy(groups[group]);c.update(item)
        if c['equipment_id'] in seen:raise ValueError('重複單機編號：'+c['equipment_id'])
        seen.add(c['equipment_id'])
        c['quantity']=1
        c['group_id']=group
        c['model']=groups[group]['model']
        c['brand']=groups[group]['brand']
        c['room_ids']=groups[group]['room_ids']
        c['requirement_id']=next(e['id'] for e in p['equipment'] if any(x['equipment_id']==group for x in e['configuration']))
        if c['role']=='室內機':
            parent=next(e for e in p['equipment'] if e['id']==c['requirement_id'])
            c['paired_to']=next(x['equipment_id'] for x in parent['configuration'] if x['role']=='室外機')
        units.append(c)
    for gid,c in groups.items():
        members=[u for u in units if u['group_id']==gid]
        if len(members)!=c['quantity']:raise ValueError(f'{gid}單機數與設備表不一致')
        c['drawing_unit_ids']=[u['equipment_id'] for u in members]
        for requirement in p['equipment']:
            for nested in requirement['configuration']:
                if nested['equipment_id']==gid:nested['drawing_unit_ids']=c['drawing_unit_ids'][:]
    if any(c.get('status')=='已核實' and not c.get('evidence') for c in p['fop_actual_checks']):
        raise ValueError('實際核實無證據，不能因固定模板是而完成')
    p['drawing_equipment']=units
    return p

def text(value):
    if value is None:return '未確定'
    if isinstance(value,list):return '；'.join(text(x) for x in value)
    if isinstance(value,dict):return '；'.join(f'{k}：{text(v)}' for k,v in value.items())
    return str(value).replace('|','／')

def markdown(p):
    g=p['drawing_brief'];rooms={r['room_id']:r for r in p['input']['rooms']}
    result={r['room_id']:r for r in p['result']['rooms']}
    lines=['# 零售展廳空調通風工程：畫圖工作指引', '',f"版本：{p['version']}", '',
        '## 1. 使用底圖與定位方法','',
        '原建築PDF只作唯讀參照。頁碼是PDF頁序，並非圖紙編號。先按圖內文字轉正，再以同頁牆、門、樓梯及尺寸線辨識位置；圖面上方不代表地理北方。未完成尺度校準前，不將紙面座標或像素換成工程尺寸。',
        '',f"來源：{g['source']['file']}；PDF頁 {text(g['source']['pages'])}。{g['source']['method']}。", '',
        '計算房間編號是設計資料對映，不保證原圖有相同房名或獨立房界。沒有可靠對映的設備先列在圖外待定位清單，不自行建立隔牆、房間或豎井。',
        '', '## 2. 設計要求與圖面標示','',
        '室內23°C／55%RH；夏季室外34°CDB／28°CWB。新風10L/s／人；衛生間排風15h⁻¹（ACH）。末端冷量與新風處理冷量分開，風量不乘冷負荷安全係數。',
        '',f"室內末端含SF冷量需求合計 {sum(s['sizing_peak']['total_kw'] for s in p['result']['systems']):.2f}kW；新風 {p['air_treatment']['airflow_ls']:.0f}L/s（{p['air_treatment']['airflow_ls']*3.6:.0f}m³/h），盤管含SF選型需求 {p['air_treatment']['sizing_coil']['total_kw']:.2f}kW，再熱需求 {p['air_treatment']['reheat_kw']:.2f}kW。這些是需求，不是原廠已確認的設備設計點性能。", '',
        '暫定採分層VRF、壁掛室內機及獨立新風冷卻除濕再熱。物業接口與壁掛形式未核准；所有候選型號及尺寸均按設備明細表狀態引用。室內外機連線表示建議配對，原廠相容性未確認。', '',
        '新設建議設備加「P／暫定」標記，原有設備沿用底圖識別並標明待核對保留／拆除，禁止把原有天花空調符號默認為本輪壁掛機。無法定位的設備只畫系統圖節點，不畫成已確認平面位置。', '',
        '## 3. 原圖辨識與房間對映','']
    for floor in g.get('floors',[]):
        lines += [f"### {text(floor.get('floor_id'))}", '']
        lines += [f"圖框編號：{g['source']['drawing_labels'][floor['floor_id']]}", '']
        for obs in floor.get('observed',[]):lines += [f"- PDF第{obs['page']}頁／{obs['feature']}：{obs['description']}"]
        for r in floor.get('rooms',[]):lines += [f"- **{r['room_id']}**：{r['evidence']} 佈置指引：{r['placement_guidance']}"]
        lines += ['']
    lines += ['## 4. 逐台设备定位及接駁','', '同型多台已分配單機編號；群組編號保留作設備表及計算結果對映。所有位置文字為設計建議，不是已核准施工定位。','']
    for u in p['drawing_equipment']:
        names='、'.join(f"{r} {rooms[r]['room_metadata']['name_zh']}" for r in u['room_ids'])
        dimensions=u.get('dimensions') or ('×'.join(str(x) for x in [u['dimensions_hwd_mm'][1],u['dimensions_hwd_mm'][0],u['dimensions_hwd_mm'][2]]) if u.get('dimensions_hwd_mm') else '未確定')
        performance=(f"單機標稱冷量：{text(u.get('nominal_cooling_kw'))} kW；" if u['role'] in ('室內機','室外機') else '')
        pairing=(f"建議室外機配對：{u['paired_to']}。" if u['role']=='室內機' else ('冷源另設，接口待核。' if u['role']=='新風處理機' else ''))
        lines += [f"### {u['equipment_id']}　{u['role']}", '',
            f"- 群組／需求：{u['group_id']}／{u['requirement_id']}；數量：1台。",
            f"- 候選：{u['brand']} {u['model']}；服務：{names}。",
            f"- {performance}尺寸W×H×D：{dimensions} mm。標稱資料不代表本工程設計點能力。",
            f"- 圖面依據：PDF {text(u.get('source_pages'))}；觀察基準：{text(u.get('observed_anchor'))}。",
            f"- 建議位置：{text(u.get('proposed_location'))}",
            f"- 安裝／送回風方向：{text(u.get('proposed_direction'))}",
            f"- 檢修及維修空間：{text(u.get('service_access'))}",
            f"- 接駁：{text(u.get('connections'))} {pairing}",
            f"- 定位狀態：{'有條件建議位置' if u.get('proposed_location') else '位置未確定，僅列系統節點'}；定案條件：{text(u.get('unresolved_impact'))}", '']
    lines += ['## 5. 新排風分配、管線走向及尺寸','',
        '| 房間 | 新風需求（L/s） | 新風需求（m³/h） | 排風需求（L/s） | 排風需求（m³/h） |',
        '|---|---:|---:|---:|---:|']
    for rid,r in rooms.items():
        v=result[rid]['ventilation']
        lines.append(f"| {rid} {r['room_metadata']['name_zh']} | {v['fresh_air_ls']:.1f} | {v['fresh_air_ls']*3.6:.1f} | {v['exhaust_ls']:.1f} | {v['exhaust_m3h']:.1f} |")
    lines += ['', '每房風口總風量須等於表中需求。支管分支按下游房間需求相加；送風口數量及位置依房間遮擋和覆蓋範圍提出，未經分配不得自行平均到既有符號。衛生間由鄰接空間補風，排風不回流空調回風。', '']
    for route in g.get('routing_guidance',[]):
        lines += [f"### {text(route.get('id'))}　{text(route.get('system_type'))}", '']
        for key,label in [('source_pages','來源頁'),('start','起點'),('end','終點'),('proposed_route','建議走向'),('branches','分支／接口'),('penetrations','穿越位置'),('elevation_basis','標高依據'),('size_basis','尺寸依據'),('hold_points','暫緩定案事項')]:
            lines.append(f"- {label}：{text(route.get(key))}")
        lines += ['']
    lines += ['尺寸標註分為「計算值」「原廠值」「暫定建議」三類。風管先依風量與路由計算尺寸及阻力，冷媒管依原廠配對、長度與高差選徑，凝結水管依排水量、坡度及接駁標高定徑。未有依據時只標風量與待核定尺寸，不用梁尺寸或型錄機組接口代替管道計算。', '',
        '## 6. 系統圖、控制及出圖清單','',
        '- 分層畫VRF系統圖：每台室內機連回對應室外機，註群組編號、单機編號、服務房間及原廠配對待核。新風機組冷源另外保留接口，不默認接入三組末端室外機。',
        '- 新風控制序列：室外新風→盤管冷卻除濕→再熱→各房間。盤管離風目標14.27°C／95%RH，再熱後23°C／55%RH；凝結水接排水系統。熱回收再熱屬設計方向，不畫成已確認的原廠管路。',
        '- 平面圖分列設備、新風、排風、冷媒及凝結水；系統圖標流向、風量、分支、冷源及控制接口。排風風機設隔離／調速接口，火警停機與閥門聯鎖以物業及消防核定矩陣為準。',
        '- 詳圖至少涵蓋壁掛機安裝與維修、風機吊裝隔振、穿牆封堵、凝結水接駁及新風機組檢修。防火閥／封堵位置須由已辨識防火分區決定，不因符號庫有標準詳圖便自動聲稱合規。',
        '- 尺寸及標高核定前可完成系統拓撲、設備清單、風量分配及可辨識區域的暫定平面；不能完成的接口在相應圖上設待核定標記，不把整套圖紙標為已定案。', '',
        '## 7. 跟進事項與圖紙定案條件','',
        '設計說明第5章是固定標準核實表模板，預填「是」不構成本工程完成核實的證據。實際核實以計算工作簿的「第5章實際核實」頁及來源記錄為準。', '']
    for a in p['review_actions']:
        lines += [f"### {a['id']}　{a['item']}",f"- 本輪暫定處理：{a['provisional_action']}",f"- 畫圖影響：{a['drawing_impact']}",f"- 完成判準：{text(a['completion_criteria'])}",'']
    lines += ['## 8. 出圖前核對','',
        '- 逐台編號唯一，與設備表群組及台數相符；房間對映不明者仍在圖外待定位清單。',
        '- 每個管線起終點及跨層接口可追溯，不把同側井位視為已證實的連通豎井。',
        '- 新風、排風的分支合計與計算表一致；冷量不再加一次SF。',
        '- 設備、風口與門扇、樑、燈具、展架及維修範圍完成協調後，才移除相應暫定標記。',
        '- 原廠配對、管徑、工作點及物業接口未確認處有對應跟進編號，無虛構數值或符合聲明。','']
    return '\n'.join(lines).replace('设备','設備').replace('单機','單機').replace('。。','。').replace('。；','；')

def main():
    base_path=ROOT/'outputs/selected_20260908/design_package.json'
    guidance=read(ROOT/'data/reference/retail_drawing_guidance.json')
    followup=read(ROOT/'data/reference/review_followup_actions.json')
    p=merge_handoff(read(base_path),guidance,followup)
    p['handoff_sources']={'base_package_sha256':hashlib.sha256(base_path.read_bytes()).hexdigest(),
        'drawing_pdf_sha256':hashlib.sha256((ROOT/'data/raw/完整設計測試圖紙.pdf').read_bytes()).hexdigest()}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'design_package.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'畫圖工作指引.md').write_text(markdown(p),encoding='utf-8')
    print(f'已建立資料包與畫圖指引：{len(p["drawing_equipment"])}台')

if __name__=='__main__':main()

