"""只補充 artifact-tool 未提供的 OOXML 列印設定；保留公式及重算快取。"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import os

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
Q=lambda s:'{'+NS+'}'+s
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/os.environ.get('HVAC_OUTPUT_DIR','outputs/revised_20260908')

def configure(path, ranges, title_rows):
    with ZipFile(path) as z: files={n:z.read(n) for n in z.namelist()}
    book=E.fromstring(files['xl/workbook.xml'])
    names=book.find(Q('definedNames'))
    if names is None:
        names=E.Element(Q('definedNames'))
        book.insert(list(book).index(book.find(Q('sheets')))+1,names)
    for n in list(names):
        if n.get('name') in ('_xlnm.Print_Area','_xlnm.Print_Titles'): names.remove(n)
    rels=E.fromstring(files['xl/_rels/workbook.xml.rels'])
    targets={r.get('Id'):r.get('Target') for r in rels}
    for i,s in enumerate(book.find(Q('sheets'))):
        name=s.get('name')
        target=targets[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        sheet=E.fromstring(files[target])
        populated=[c.get('r') for c in sheet.iter(Q('c')) if any(c.find(Q(t)) is not None for t in ['v','f','is'])]
        import re
        def column_number(ref):
            n=0
            for ch in re.match('[A-Z]+',ref)[0]:n=n*26+ord(ch)-64
            return n
        last_row=max(int(re.search(r'\d+',c)[0]) for c in populated)
        last_col=re.match('[A-Z]+',max(populated,key=column_number))[0]
        rng=f'$A$1:${last_col}${last_row}'
        for label,value in [('_xlnm.Print_Area',rng),('_xlnm.Print_Titles',f'$1:${title_rows}')]:
            E.SubElement(names,Q('definedName'),name=label,localSheetId=str(i)).text=f"'{name}'!{value}"
        target=targets[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        sheet=E.fromstring(files[target])
        prop=sheet.find(Q('sheetPr'))
        if prop is None: prop=E.Element(Q('sheetPr'));sheet.insert(0,prop)
        pageprop=prop.find(Q('pageSetUpPr'))
        if pageprop is None: pageprop=E.SubElement(prop,Q('pageSetUpPr'))
        pageprop.set('fitToPage','1')
        for tag in ['printOptions','pageMargins','pageSetup']:
            old=sheet.find(Q(tag))
            if old is not None:sheet.remove(old)
        # These generated workbooks have no drawings/headerFooter; insert before later OOXML nodes if present.
        later={'headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
        pos=next((j for j,c in enumerate(sheet) if E.QName(c).localname in later),len(sheet))
        nodes=[E.Element(Q('printOptions'),horizontalCentered='1'),E.Element(Q('pageMargins'),left='0.25',right='0.25',top='0.35',bottom='0.35',header='0.15',footer='0.15'),E.Element(Q('pageSetup'),paperSize='8',orientation='landscape',fitToWidth='1',fitToHeight='0')]
        for j,node in enumerate(nodes):sheet.insert(pos+j,node)
        files[target]=E.tostring(sheet,xml_declaration=True,encoding='UTF-8')
    files['xl/workbook.xml']=E.tostring(book,xml_declaration=True,encoding='UTF-8')
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for n,b in files.items():z.writestr(n,b)

if __name__=='__main__':
    configure(OUT/'設計計算表.xlsx',dict(zip(['概覽','建築參數','通風計算','冷負荷計算','系統負荷密度','逐時系統負荷','待覆核事項'],['$A$1:$D$23','$A$1:$K$13','$A$1:$P$15','$A$1:$O$13','$A$1:$K$9','$A$1:$J$28','$A$1:$E$14'])),4)
    configure(OUT/'設備明細表.xlsx',{'空調設備':'$A$1:$P$14','風機':'$A$1:$N$13','新風處理':'$A$1:$P$12'},7)
