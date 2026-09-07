"""建立零售展廳HVAC設計測試的七章式Word設計說明。"""
from __future__ import annotations

import json
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "retail_trial_20260907"
result = json.loads((ROOT / "outputs" / "review" / "retail_trial_result.json").read_text(encoding="utf-8"))
inp = json.loads((ROOT / "data" / "local" / "trial_2024_06_03_retail_input.json").read_text(encoding="utf-8"))


def set_font(run, size=10.5, bold=False, color=None):
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft JhengHei")
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    node = OxmlElement("w:shd")
    node.set(qn("w:fill"), fill)
    tc_pr.append(node)


def border_table(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        item = OxmlElement(f"w:{side}")
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:color"), "D9D9D9")
        borders.append(item)
    tbl_pr.append(borders)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    border_table(table)
    for i, title in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = title
        shade(cell, "1F4E78")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            set_font(run, 9.5, True, (255, 255, 255))
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for idx, row in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if idx % 2:
                shade(cells[i], "F2F7FB")
            for paragraph in cells[i].paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    set_font(run, 9)
    if widths:
        for row in table.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Cm(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table


def heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(13)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(text)
    set_font(r, 13, True, (0, 0, 0))


def para(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.22
    set_font(p.add_run(text), 10.5)
    return p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(52)
    title.paragraph_format.space_after = Pt(12)
    set_font(title.add_run("零售展廳空調通風系統\n設計測試說明"), 22, True, (0, 0, 0))
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(sub.add_run("地庫、地面層及一樓｜2024-06-03建築圖試點"), 12, False, (80, 80, 80))
    doc.add_paragraph()
    add_table(doc, ["項目", "內容"], [
        ["設計階段", "端到端設計測試"],
        ["圖紙來源", "Google Drive圖紙 1RvowEGCkZnWpAyhuccUFQsQmEYT5kDT9"],
        ["適用範圍", "地庫、地面層及一樓零售展廳。"],
        ["成果狀態", "測試計算及設備需求規格。未作施工圖或最終設備選型。"],
    ], [4.0, 12.5])
    doc.add_page_break()

    heading(doc, "1. 工程範圍")
    para(doc, "本設計測試涵蓋地庫、地面層及一樓的零售展示、收銀、試衣、倉庫及衛生間空調通風需要。圖紙可辨識空間配置、局部尺寸、天花空調及低抽排氣符號；不包括風管、冷媒管、冷凝水管及控制施工圖。")
    heading(doc, "2. 設計條件")
    add_table(doc, ["項目", "採用值", "狀態"], [
        ["室內", "23°C，55%RH", "公司已確認"],
        ["室外夏季", "澳門34°CDB / 28°CWB", "公司已確認"],
        ["新風", "10 L/s/人", "公司已確認"],
        ["衛生間排風", "15 ACH", "公司已確認"],
        ["冷負荷安全係數", "最終未加SF冷負荷×1.15一次", "公司已確認"],
        ["計算法", "顯式24小時分項及同時峰值", "試點計算法，不等同HAP"],
    ], [4.0, 7.0, 5.5])
    para(doc, "圖紙未提供外牆與玻璃熱工性能、方位、遮陽、房間淨高、人數、實際照明及設備功率、營運時間或系統接口。計算書中的面積、淨高、人數、排程及圍護分項已明示為測試假設。")
    heading(doc, "3. 空間及負荷輸入")
    rows=[]
    for i, r in enumerate(result['rooms']):
        meta=inp['rooms'][i]['room_metadata']
        rows.append([r['room_id'], meta['floor'], meta['name_zh'], f"{meta['area_m2']:.1f}", r['ventilation']['fresh_air_ls'], f"{r['raw_peak']['total_kw']:.2f}"])
    add_table(doc, ["房間", "樓層", "用途", "面積m²", "新風L/s", "未加SF峰值kW"], rows, [2.0, 2.5, 3.0, 2.0, 2.6, 3.1])
    para(doc, "人員發熱採ASHRAE 2025 Fundamentals SI第18章Table 4的相應活動值作測試參考。照明採Table 5所列用途功率密度參考。設備熱及逐時排程則為明示測試輸入，須由業主或設計資料取代。")
    heading(doc, "4. 空調系統方案")
    para(doc, "暫定方案為每層獨立DX/VRF室內機分區，另以小型集中新風處理單元供應新風，衛生間設獨立排風。各系統以同一時刻的房間未加SF負荷相加後取峰值；不將房間個別含SF峰值相加。")
    add_table(doc, ["系統", "服務樓層", "未加SF峰值kW", "設計冷量kW", "新風L/s", "排風L/s"], [
        [s['system_id'], {'DX-BF':'地庫','DX-GF':'地面層','DX-1F':'一樓'}[s['system_id']], f"{s['raw_peak']['total_kw']:.2f}", f"{s['sizing_peak']['total_kw']:.2f}", f"{s['fresh_air_ls']:.1f}", f"{s['exhaust_ls']:.1f}"] for s in result['systems']
    ], [2.2, 2.5, 3.0, 3.0, 2.7, 2.7])
    heading(doc, "5. 通風、排風及空氣平衡")
    para(doc, "本測試的總新風需求為920 L/s，即3,312 m³/h；衛生間總排風為87.5 L/s，即315 m³/h。排風量由衛生間假設體積及15ACH計算，未加冷負荷安全係數。補風路徑、負壓目標、豎井可用風量、風管阻力及防火閥配置尚未有資料，必須在施工圖前完成。")
    heading(doc, "6. 設備需求及選型限制")
    para(doc, "設備表已建立各層設計冷量、風量與服務範圍。現有資料庫可提供部分FCU、PAU及風機候選的風量、外部靜壓及認證資料；但FCU/PAU欠缺同一額定工況下完整冷量、顯熱、盤管及性能曲線資料。故本測試不指定設備型號或台數。選型時須取得原廠同工況性能表，並核對供回風、靜壓、冷媒或冷凍水、冷凝水、電源、噪音及維修空間。")
    heading(doc, "7. 待覆核事項及畫圖交接")
    para(doc, "下一個畫圖助手可使用本成果的系統分區、設計冷量、新風及衛生間排風需求作為設計輸入。畫圖前須補齊：原CAD及正式面積、淨高與天花限制、北向與圍護性能、設計人數與營業排程、照明及設備功率、現有空調及低抽排氣設備資料、機房/豎井位置、系統接口、設備型錄性能與風管靜壓。未補齊前，不應繪製最終風管尺寸或簽發設備採購表。")
    heading(doc, "附錄：計算結果")
    para(doc, "含15%安全係數的三個樓層系統冷量合計為38.83 kW。結果由設計助手顯式逐時計算核心產生，計算峰值為2026-07-15 15:00，純為測試日與輸入輪廓，並非歷史或氣象設計日。詳細房間、逐時負荷、通風、設備需求及待覆核事項見同版本Excel工作簿。")
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run("零售展廳 HVAC 設計測試｜2026-09-07"), 8, False, (90,90,90))
    path = OUT / "零售展廳_HVAC設計測試說明.docx"
    doc.save(path)
    print(path)


if __name__ == "__main__":
    main()
