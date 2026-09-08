"""從 FOP 原母本複製版式，固定章原文經版本化模板逐段核驗。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates/fop_narrative_v1.1.json"


def full_text(element):
    return ''.join(t.text or '' for t in element.iter(qn('w:t')))


def replace_text(element, text):
    """保留段落和內容控制結構；只替換文字節點，不重建母本樣式。"""
    nodes = list(element.iter(qn('w:t')))
    if not nodes:
        target = element
        if element.tag == qn('w:tc'):
            target = element.find(qn('w:p'))
            if target is None:
                target = OxmlElement('w:p')
                element.append(target)
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        r.append(t)
        target.append(r)
        nodes = [t]
    nodes[0].text = str(text)
    for node in nodes[1:]:
        node.text = ''


def populate_table(table, headers, rows):
    samples = list(table._tbl.iterchildren(qn('w:tr')))
    header, body = deepcopy(samples[0]), deepcopy(samples[1])
    for row in samples:
        table._tbl.remove(row)
    for index, values in enumerate([headers, *rows]):
        row = deepcopy(header if index == 0 else body)
        # 母本 Google 內容控制具有唯一 ID；複製房間列不可複製識別碼。
        for node in list(row.iter()):
            if node.tag in (qn('w:bookmarkStart'), qn('w:bookmarkEnd'), qn('w:id')):
                node.getparent().remove(node)
        cells = list(row.iterchildren(qn('w:tc')))
        for cell, value in zip(cells, values):
            replace_text(cell, value)
        props = row.find(qn('w:trPr'))
        if props is None:
            props = OxmlElement('w:trPr')
            row.insert(0, props)
        for tag in ('w:trHeight', 'w:cantSplit', 'w:tblHeader'):
            for existing in list(props.findall(qn(tag))):
                props.remove(existing)
        props.append(OxmlElement('w:cantSplit'))
        if index == 0:
            props.append(OxmlElement('w:tblHeader'))
        table._tbl.append(row)


def build_document(package, reference=None):
    contract = json.loads(TEMPLATE.read_text(encoding='utf-8'))
    reference = reference or next((ROOT / 'data/local').rglob('*Design_Narrative_v1.1.docx'))
    expected = next(x['sha256'] for x in contract['source_files'] if x['name'].endswith('.docx'))
    if hashlib.sha256(reference.read_bytes()).hexdigest() != expected:
        raise ValueError('FOP 母本 SHA256 不符，須重新覆核版本。')
    doc = Document(reference)
    for paragraphs in contract['fixed_chapters'].values():
        for item in paragraphs:
            element = doc.paragraphs[item['paragraph_index']]._p
            if full_text(element) != item['text']:
                raise ValueError('固定章原文與版本化模板不一致。')
            replace_text(element, item['text'])

    inp, result = package['input'], package['result']
    rooms = {r['room_id']: r for r in inp['rooms']}
    outcomes = {r['room_id']: r for r in result['rooms']}
    equipment = package['equipment']
    area = sum(r['room_metadata']['area_m2'] for r in rooms.values())
    cooling = sum(s['sizing_peak']['total_kw'] for s in result['systems'])
    raw = sum(s['raw_peak']['total_kw'] for s in result['systems'])
    fresh = sum(s['fresh_air_ls'] for s in result['systems'])
    exhaust = sum(s['exhaust_ls'] for s in result['systems'])
    def refs(room_id, prefix):
        return '、'.join(e['id'] for e in equipment if room_id in e['room_ids'] and e['id'].startswith(prefix)) or '未設需求記錄'
    values = {
        0: '機械通風和空調系統設計說 明 及 解 釋 備 忘 錄',
        1: f"零售展廳三層設計測試\n專案編號：{inp['project_id']}｜版本：{package['version']}｜CalculationOnly",
        3: '1.1 項目名稱：零售展廳地庫、地面層及一樓 HVAC 設計測試',
        4: '1.2 項目地點：澳門設計氣象條件；實際工程地址待確認。',
        5: f'1.3 工程範圍與邊界：本次按建築 PDF 辨識的九個房間進行空調通風計算，計算面積 {area:.2f} m² 為測試估算。成果供設計覆核及後續畫圖交接，尚未完成施工設計或設備採購選型。各房面積、淨高、人數、圍護性能及排程仍屬明示測試假設。',
        39: '• 室外設計氣象條件 (Outdoor Design Temperature)：澳門夏季。',
        40: '• 夏季 (Summer)：34°C 乾球／28°C 濕球；室內 23°C、55% RH。',
        41: '• 冬季 (Winter)：本次未建立冬季熱負荷及設計工況，未計算。',
        42: '• 室內空間設計參數與負荷摘要：下表為房間未含 SF 個別峰值；密度＝房間未含 SF 峰值 × 1,000／房間面積，只供本試點粗估比較，不作通用 W/m² 標準。',
        44: '3.2.1 空調系統與直接膨脹式冷源規範 (DX Provision)',
        45: f'暫定每層獨立 DX／VRF 分區，台數、型號及室內外機對應待選型。系統按同一時刻房間原始負荷相加後取峰值，只在系統最終負荷乘 1.15 一次。系統冷量合計未含 SF {raw:.2f} kW，含 SF {cooling:.2f} kW；以計算面積 {area:.2f} m² 換算合计密度分別為 {raw*1000/area:.2f} 及 {cooling*1000/area:.2f} W/m²。此為各系統選型需求合計，不冒充整棟同時尖峰或單機性能。',
        47: '本測試採用已確認新風 10 L/s／人及衛生間排風 15 h⁻¹（ACH）。新排風量不乘冷負荷安全係數。法規、用途最低通風及噪音要求須於正式設計覆核。',
        48: '母本標準待核對事項：歷史第 3.2.2 節同時提及 ASHRAE 62.1-2019 與 2013；本次保留第 2 章固定原文，但不據此宣稱標準版本一致或工程已符合。',
        49: f'• 鮮風供應原則：新風需求 {fresh:.2f} L/s（{fresh*3.6:.2f} m³/h），共用需求記錄 FAU-REQ-ALL。新風處理機台數、盤管冷量及進出風工況未確定；未建模的新風盤管負荷仍為未計算，以上房間及系統冷量不包含該盤管負荷。',
        50: f'• 排風必要性與設備編號：地庫及地面層衛生間採 15 h⁻¹（ACH）；合計 {exhaust:.2f} L/s（{exhaust*3.6:.2f} m³/h）。體積（m³）×換氣次數（h⁻¹）＝排風量（m³/h），再除 3.6 得 L/s。需求記錄 TEF-REQ-BF／TEF-REQ-GF 的數量（台）及型號待確定；補風路徑與靜壓尚待設計。',
        53: '• 天花板安裝設備：DX 室內機及風機須核對天花淨空、檢修空間、吊架承載及隔振；現圖未提供完整設備尺寸與重量，安裝構造待選型後確認。',
        54: '• 軟連接：風管與風機／風管式室內機連接處採柔性連接，規格由正式設備及安裝要求確定。',
        55: '• 空調末端設備：須取得同一額定工況下冷量、顯熱、風量、功率、噪音及性能資料；需求記錄不代表單台設備，數量（台）不得由樓層數代填。詳見同版本設備明細表。',
        56: '• 風管與閘閥：管道尺寸、阻力、機外靜壓（Pa）及穿越防火分區位置尚未建立，防火閥、檢修口及消防連動須在配置完成後覆核。',
        57: '• 管道與保溫：本暫定 DX 方案需冷媒及凝結水管，未沿用母本中央冰水管配置。材質、保溫厚度、冷媒及防火性能待原廠與工程條件確認。',
        59: '• 動力和控制材料須依本項目電氣技術規範選定；本次未取得該規範及配電容量。',
        60: '• 設備供電、隔離開關、電纜及控制線路待選型；功率（kW）及電源（V/Ph/Hz）均以設備明細表待確認欄位追蹤。',
        61: '• 溫度控制：暫定 DX／VRF 原廠控制器維持室內設定 23°C；55% RH 目標須另驗證除濕及新風處理能力，不套用冰水二通／三通閥條文。',
        62: '• 火警連動：對應設備停機及閥門聯鎖邏輯待消防分區與控制接口確認，現階段未作已完成聲明。',
    }
    for index, text in values.items():
        replace_text(doc.paragraphs[index]._p, text)
    doc.paragraphs[0].style = doc.styles['Title']
    for holder in (doc.paragraphs[0]._p.get_or_add_pPr(), doc.styles['Title'].element.get_or_add_pPr()):
        for border in list(holder.findall(qn('w:pBdr'))):
            holder.remove(border)
    for index in [2,7,8,19,37,38,43,44,46,51,52,58,63,70,72,74]:
        doc.paragraphs[index].paragraph_format.keep_with_next = True
    # 對照母本頁面設定；不增加封面或額外裝飾。
    for section in doc.sections:
        section.page_width, section.page_height = Inches(8.5), Inches(11)
        section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)
    spec = json.loads((ROOT/'data/reference/fop_template_spec.json').read_text(encoding='utf-8'))['docx']
    populate_table(doc.tables[0], spec['tables'][0]['rows'][0], [
        [rid, r['room_metadata']['name_zh'], r['room_metadata']['floor'], f"{r['room_metadata']['area_m2']:.2f}", f"{r['volume_m3']/r['room_metadata']['area_m2']:.2f}", r['room_metadata']['name_zh']]
        for rid, r in rooms.items()])
    summary = []
    for rid, r in rooms.items():
        m, o = r['room_metadata'], outcomes[rid]
        summary.append([f"{rid}\n{m['name_zh']}", f"{m['area_m2']:.2f}", str(r['people']), f"{o['ventilation']['exhaust_m3h']:.2f}", f"{o['ventilation']['fresh_air_ls']:.2f}", f"{o['raw_peak']['total_kw']:.2f}", f"{o['raw_peak']['total_kw']*1000/m['area_m2']:.2f}", refs(rid,'AC-')+'\n台數待定'])
    populate_table(doc.tables[1], ['房間名稱','面積\n(m²)','人數\n(人)','排風\n(m³/h)','新風\n(L/s)','原始峰值\n(kW)','原始密度\n(W/m²)','本工程空調通風配置'], summary)
    populate_table(doc.tables[2], ['樓層','區域名稱','空間用途','空調需求記錄','新風需求記錄','排風需求記錄'], [
        [r['room_metadata']['floor'], rid+'\n'+r['room_metadata']['name_zh'],r['room_metadata']['name_zh'],refs(rid,'AC-'), refs(rid,'FAU-'),refs(rid,'TEF-')]
        for rid,r in rooms.items()])
    reasons=['文件數值已統一；施工圖未建立，整體資訊待協調','設備及管道未定位，待核對逃生和隔火空間','未完成風口配置及噪音評估','尚欠設備選型及消防安裝覆核','管道路徑未定，防火穿越待核對','現圖淨高不完整；3.0 m 為測試假設']
    populate_table(doc.tables[3], ['項次','內容','核實狀態','證據／待辦'], [
        [row[0],row[1],'待核實',reasons[i]] for i,row in enumerate(spec['tables'][3]['rows'][1:])])
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=ROOT/'outputs/revised_20260908/design_package.json')
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/revised_20260908/設計說明.docx')
    args = parser.parse_args()
    package = json.loads(args.package.read_text(encoding='utf-8'))
    doc = build_document(package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
