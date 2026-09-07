import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { FileBlob, SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'outputs/review');
const refdir = path.join(root, 'data/local/legacy/00_標準範例_standard_example');
const py = process.env.HVAC_PYTHON || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
await fs.mkdir(out, { recursive: true });
await fs.mkdir(path.join(root, 'data/reference'), { recursive: true });
const extractCode = String.raw`
import json,sys,hashlib,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from openpyxl import load_workbook
p=Path(sys.argv[1]); x=next(p.glob('*.xlsx')); d=next(p.glob('*.docx'))
w=load_workbook(x,data_only=False)
spec={'schema_version':1,'source_files':[{'name':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in [x,d]],'sheets':[]}
for s in w:
 spec['sheets'].append({'name':s.title,'rows':s.max_row,'columns':s.max_column,'headers':[s.cell(4,c).value for c in range(1,s.max_column+1)],'merges':[str(v) for v in s.merged_cells],'column_widths':{k:v.width for k,v in s.column_dimensions.items()},'font':s['A4'].font.name,'font_size':s['A4'].font.sz,'header_fill':s['A4'].fill.fgColor.rgb,'body_border':s['A5'].border.bottom.style,'formulas':{c.coordinate:c.value for row in s for c in row if c.data_type=='f'}})
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}; W='{'+ns['w']+'}'
with ZipFile(d) as z:
 r=etree.fromstring(z.read('word/document.xml'))
 paragraphs=[]
 for i,p in enumerate(r.xpath('//w:body/w:p',namespaces=ns)):
  text=''.join(p.xpath('.//w:t/text()',namespaces=ns))
  if text:
   paragraphs.append({'paragraph_index':i,'text':text,'font_sizes_half_points':sorted(set(p.xpath('.//w:sz/@w:val',namespaces=ns))),'fonts':sorted(set(p.xpath('.//w:rFonts/@w:eastAsia',namespaces=ns)))})
 tables=[]
 for i,t in enumerate(r.xpath('//w:body/w:tbl',namespaces=ns)):
  rows=[[''.join(c.xpath('.//w:t/text()',namespaces=ns)) for c in tr.xpath('./w:tc',namespaces=ns)] for tr in t.xpath('./w:tr',namespaces=ns)]
  tables.append({'table_index':i,'rows':rows,'border_styles':sorted(set(t.xpath('.//w:tcBorders/*/@w:val',namespaces=ns))),'border_colors':sorted(set(t.xpath('.//w:tcBorders/*/@w:color',namespaces=ns)))})
 sect=r.find('.//'+W+'sectPr'); pg=sect.find(W+'pgSz'); margin=sect.find(W+'pgMar')
 spec['docx']={'paragraphs':paragraphs,'chapters':[p for p in paragraphs if re.match(r'^[1-7] –',p['text'])],'tables':tables,'page_twips':{etree.QName(k).localname:v for k,v in pg.attrib.items()},'margin_twips':{etree.QName(k).localname:v for k,v in margin.attrib.items()},'extraction_note':'Google w:sdt content controls contain Chinese text; extraction includes all descendant w:t, not only python-docx paragraph.text.'}
print(json.dumps(spec,ensure_ascii=False))
`;
const spec = JSON.parse(execFileSync(py, ['-X','utf8','-c', extractCode, refdir], {encoding:'utf8',maxBuffer:4*1024*1024}));
await fs.writeFile(path.join(root, 'data/reference/fop_template_spec.json'), JSON.stringify(spec,null,2)+'\n');

if (process.argv.includes('--inspect-template')) {
  const template = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(refdir,spec.source_files[0].name)));
  console.log((await template.inspect({kind:'workbook,sheet',maxChars:4000})).ndjson);
  for (const s of spec.sheets) {
    const img = await template.render({sheetName:s.name,range:`A1:${column(s.columns)}7`,scale:1,format:'png'});
    await fs.writeFile(path.join(out,`FOP母本_${s.name}.png`),new Uint8Array(await img.arrayBuffer()));
  }
  console.log('母本三表預覽及結構索引已建立。');
  process.exit(0);
}

function column(n){let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);}return s;}

const hap = JSON.parse(await fs.readFile(path.join(root,'data/reference/hap_reference.json'),'utf8'));
if (hap.spaces.length !== 55) throw new Error('本次核准基準須有55個空間。');
const rooms = hap.spaces;
const company = JSON.parse(await fs.readFile(path.join(root,'config/company_standard.json'),'utf8'));
const approved = company.approved_rules;
if (approved.fresh_air_lps_per_person!==10 || approved.cooling_safety_factor!==1.15 || approved.safety_factor_scope!=='final_raw_cooling_load_once') throw new Error('公司已核准參數變更，須重新核對本工作簿規格。');
const wb = Workbook.create();
const names = ['建築參數','通風計算','冷熱負荷計算','核准標準','設備需求','HAP原報表'];
const sheets = Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const first=5, last=first+rooms.length-1, total=last+1;
const font = {name:'Arial',size:10,color:'#111111'};
const formula = (sh,cell,f) => sh.getRange(cell).formulas=[[f]];
const value = (sh,cell,v) => sh.getRange(cell).values=[[v]];
const sourceURL='https://drive.google.com/file/d/1EmE2AYiKq3HXbbkRZ8WEk6LM-CDnu0QR/view';
function frame(sh, title, subtitle, headers, rows, widths) {
  const end=column(headers.length);
  sh.getRange(`A1:${end}${rows}`).format.font=font;
  sh.getRange(`A1:${end}${rows}`).format.verticalAlignment='center';
  sh.getRange(`A1:${end}${rows}`).format.rowHeight=30;
  sh.mergeCells(`A1:${end}1`); value(sh,'A1',title);
  sh.getRange('A1').format.font={...font,size:15,bold:true};
  sh.getRange('A1').format.rowHeight=32;
  sh.mergeCells(`A2:${end}2`); value(sh,'A2',subtitle);
  sh.getRange('A2').format.font={...font,size:10,italic:true,color:'#555555'};
  sh.getRange('A2').format.rowHeight=28;
  sh.getRange(`A4:${end}4`).values=[headers];
  sh.getRange(`A4:${end}${rows}`).format.borders={preset:'all',style:'thin',color:'#000000'};
  sh.getRange(`A4:${end}4`).format.fill='#D9D9D9';
  sh.getRange(`A4:${end}4`).format.font={...font,bold:true};
  sh.getRange(`A4:${end}4`).format.horizontalAlignment='center';
  sh.getRange(`A4:${end}${rows}`).format.wrapText=true;
  sh.getRange(`A4:${end}4`).format.rowHeight=64;
  widths.forEach((w,i)=>sh.getRange(`${column(i+1)}1:${column(i+1)}${rows}`).format.columnWidth=w);
  sh.showGridLines=true;
  if(rows>25) {sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(2);}
}
function totalStyle(sh, end) {
  sh.getRange(`A${total}:${end}${total}`).format.font={...font,bold:true};
  sh.getRange(`A${total}:${end}${total}`).format.borders={preset:'doubleBottom',style:'thin',color:'#000000'};
  sh.getRange(`A${total}:${end}${total}`).format.rowHeight=42;
}
const std=sheets['核准標準'];
frame(std,'設計資料與公司標準覆核','內部覆核版｜慕拉士原始計算為歷史基準；本工作簿尚未完成新設計冷負荷與選型。',
 ['項目','設定值','單位','核准／使用狀態','適用說明'],19,[32,18,18,28,90]);
std.getRange('A5:E19').values=[
 ['人均新風率',approved.fresh_air_lps_per_person,'L/s／人','用戶已確認','以原報表人數試算；空間用途與直接新風／轉移風安排仍待設計核對。'],
 ['最終冷負荷安全係數',approved.cooling_safety_factor,'倍','用戶已確認','只施於未含裕量的最終冷負荷一次；不放大新排風量。'],
 ['風量單位換算',3.6,'m³/h ÷ L/s','單位定義','1 L/s = 3.6 m³/h。'],
 ['冷噸單位換算',3.517,'kW／RT','沿用FOP顯示精度','只作已完成冷負荷的單位換算，不代表完成設備選型。'],
 ['格式與內容深度','FOP v1.1',null,'用戶已確認','保留三主表與七章說明結構；不複製範例數值及預填符合狀態。'],
 ['歷史計算基準','2023-11-18',null,'用戶已確認','55個空間分別於不同時刻達峰；不加總為新系統冷量。'],
 ['歷史冷量裕量',0.10,'顯／潛熱比例','原報表記錄','歷史值保留10%；不得將原含裕量總量直接乘1.15。'],
 ['新冷負荷重算','未計算',null,'待同範圍輸入確認','冷熱負荷表L欄只接受已完成新標準重算、未加SF的最終冷負荷。'],
 ['淨高／樓層／用途','待核對',null,'待圖紙對照','HAP面積與人數可用於基準閱讀，不能取代新設計條件確認。'],
 ['排風／補風／壓差','待確認',null,'待公司標準整理','沒有核准ACH或房間體積時，不填排風結果為零。'],
 ['設備性能及靜壓','待計算',null,'待系統方案與工況','不填虛構型號、台數、容量或機外靜壓。'],
 ['公司工況與負荷參數','待集中核准',null,'由用戶最終確認','包括室內外工況、使用排程、人員顯潛熱、燈光設備與圍護資料。'],
 ['新設計冷量輸入方式','L欄留空',null,'未完成前保持空白','未計算值顯示「未計算」；只有真實零輸入才顯示數值零。'],
 ['歷史人數用途','計算基準',null,'非已核准新設計定員','通風表的10 L/s／人結果為基準人數試算，並非已確定全案新風需求。'],
 ['檔案版本','2026-09-07',null,'內部覆核工作簿','原報表頁碼列在輸入處；所有新設計冷量與設備需求尚待完整驗證。']
];
std.getRange('B6').setNumberFormat('0.00');std.getRange('B11').setNumberFormat('0%');
std.getRange('A5:E19').format.rowHeight=44;
std.getRange('B5:B6').format.fill='#FFF2CC';

const src=sheets['HAP原報表'];
frame(src,'慕拉士55個空間原始計算','歷史冷量含原10%裕量。各房峰值非同時，不設冷量總計。來源：慕拉士_冷量計算_2_20231118.pdf',
 ['來源編號','原房間名稱','Zone','原面積\n(m²)','原人數','峰值月份','峰值時間','原顯熱\n(W)','原潛熱\n(W)','原顯熱裕量\n(W)','原潛熱裕量\n(W)','原顯熱裕量\n(%)','原潛熱裕量\n(%)','來源頁','來源表編號'],last,[19,36,8,13,11,12,12,16,16,16,16,14,14,10,13]);
src.getRange('A3:O3').merge();value(src,'A3',sourceURL);src.getRange('A3').format.rowHeight=22;
src.getRange(`A${first}:O${last}`).values=rooms.map(r=>[r.reference_id,r.name,r.zone,r.floor_area_m2,r.people,r.peak.month,r.peak.hour_hhmm,r.cooling_sensible_W,r.cooling_latent_W,r.safety_factor.sensible_W,r.safety_factor.latent_W,r.safety_factor.sensible_percent/100,r.safety_factor.latent_percent/100,r.provenance.page,r.table_id]);
src.getRange(`D5:E${last}`).setNumberFormat('#,##0.0');src.getRange(`H5:K${last}`).setNumberFormat('#,##0');src.getRange(`L5:M${last}`).setNumberFormat('0%');

const b=sheets['建築參數'];
frame(b,'慕拉士建築參數覆核','以原報表55個空間建立對照；樓層、淨高、用途及朝向仍待圖面確認。',
 [...spec.sheets[0].headers,'來源頁','資料狀態'],total,[19,36,15,14,14,16,14,24,20,10,32]);
const v=sheets['通風計算'];
const ventHeaders=[...spec.sheets[1].headers];ventHeaders[12]='13. 基準人數鮮風試算\nReq. FA (L/s)';
frame(v,'慕拉士通風計算覆核','基準人數 × 10 L/s／人。直接供風用途待確認；本表不代表已核准全案新風或排風／補風平衡。',
 [...ventHeaders,'來源頁'],total,[19,36,14,13,13,15,22,13,15,15,13,19,20,22,17,10]);
const c=sheets['冷熱負荷計算'];
const coldHeaders=[...spec.sheets[2].headers];coldHeaders[6]='7. 最終冷負荷（含15%SF）\nQ_cooling (kW)';
frame(c,'慕拉士新設計冷負荷覆核','新標準冷負荷尚未計算。L欄保留經確認、未含SF的最終冷負荷輸入；不套用歷史峰值。',
 [...coldHeaders,'最終冷負荷（未含SF）\n經覆核輸入(kW)','SF','未決事項'],total,[19,36,14,17,17,17,22,18,18,18,24,24,10,31]);
for(let i=0;i<rooms.length;i++){
  const row=first+i,r=rooms[i];
  b.getRange(`A${row}:K${row}`).values=[[r.reference_id,null,'待核對',null,null,null,null,'待用途分類','待圖面核對',r.provenance.page,'原面積／人數為歷史輸入']];
  formula(b,`B${row}`,`='HAP原報表'!B${row}`);
  formula(b,`D${row}`,`=IF(ISNUMBER('HAP原報表'!D${row}),'HAP原報表'!D${row},"待確認")`);
  formula(b,`G${row}`,`=IF(ISNUMBER('HAP原報表'!E${row}),'HAP原報表'!E${row},"待確認")`);
  formula(b,`F${row}`,`=IF(AND(ISNUMBER(D${row}),ISNUMBER(E${row})),D${row}*E${row},"未計算")`);
  v.getRange(`A${row}:P${row}`).values=[[null,null,null,null,null,null,null,null,null,null,null,null,null,'待系統分區',null,r.provenance.page]];
  for(const [to,from] of [['A','A'],['B','B'],['C','C'],['D','D'],['F','F'],['G','H'],['K','G']]) formula(v,`${to}${row}`,`='建築參數'!${from}${row}`);
  formula(v,`E${row}`,`=IF(ISNUMBER('建築參數'!E${row}),'建築參數'!E${row},"待確認")`);
  formula(v,`L${row}`,`='核准標準'!$B$5`);
  formula(v,`M${row}`,`=IF(ISNUMBER(K${row}),K${row}*L${row},"未計算")`);
  formula(v,`I${row}`,`=IF(AND(ISNUMBER(F${row}),ISNUMBER(H${row})),F${row}*H${row},"未計算")`);
  formula(v,`J${row}`,`=IF(ISNUMBER(I${row}),I${row}/'核准標準'!$B$7,"未計算")`);
  c.getRange(`A${row}:N${row}`).values=[[null,null,null,'未計算','未計算','未計算',null,'未計算',null,null,'待選型',null,null,'待同範圍工況與逐時計算']];
  for(const [to,from] of [['A','A'],['B','B'],['C','D']]) formula(c,`${to}${row}`,`='建築參數'!${from}${row}`);
  formula(c,`M${row}`,`='核准標準'!$B$6`);
  formula(c,`G${row}`,`=IF(ISNUMBER(L${row}),L${row}*M${row},"未計算")`);
  formula(c,`I${row}`,`=IF(AND(ISNUMBER(G${row}),ISNUMBER(C${row}),C${row}>0),G${row}*1000/C${row},"未計算")`);
  formula(c,`J${row}`,`=IF(ISNUMBER(G${row}),G${row}/'核准標準'!$B$8,"未計算")`);
}
b.getRange(`E5:E${last}`).format.fill='#FFF2CC';v.getRange(`H5:H${last}`).format.fill='#FFF2CC';v.getRange(`O5:O${last}`).format.fill='#FFF2CC';c.getRange(`L5:L${last}`).format.fill='#FFF2CC';
b.getRange(`D5:G${total}`).setNumberFormat('#,##0.0');v.getRange(`D5:M${total}`).setNumberFormat('#,##0.0');c.getRange(`C5:L${last}`).setNumberFormat('#,##0.00');c.getRange(`M5:M${last}`).setNumberFormat('0.00');
value(b,`A${total}`,'歷史基準合計');formula(b,`D${total}`,`=IF(COUNT(D5:D${last})=${rooms.length},SUM(D5:D${last}),"資料未齊")`);formula(b,`G${total}`,`=IF(COUNT(G5:G${last})=${rooms.length},SUM(G5:G${last}),"資料未齊")`);value(b,`F${total}`,'未計算');
value(v,`A${total}`,'基準人數試算合計');formula(v,`K${total}`,`=IF(COUNT(K5:K${last})=${rooms.length},SUM(K5:K${last}),"資料未齊")`);formula(v,`M${total}`,`=IF(COUNT(M5:M${last})=${rooms.length},SUM(M5:M${last}),"資料未齊")`);value(v,`I${total}`,'未計算');value(v,`J${total}`,'未計算');
value(c,`A${total}`,'系統冷量');value(c,`G${total}`,'未計算');value(c,`L${total}`,'待同時峰值計算');
totalStyle(b,'K');totalStyle(v,'P');totalStyle(c,'N');

const e=sheets['設備需求'];
const zones=[...new Set(rooms.map(r=>r.zone))];
frame(e,'系統服務範圍與設備需求','先核對原報表Zone與新設計系統對應；Zone不代表已確定的一台設備。',
 ['歷史分區','基準空間數','新設計系統','設備類型','未含SF冷量(kW)','含15%SF冷量(kW)','風量(m³/h)','ESP(Pa)','型號／工況','待確認'],4+zones.length,[16,14,23,18,23,23,19,16,26,50]);
e.getRange(`A5:J${4+zones.length}`).values=zones.map(z=>[`Zone ${z}`,rooms.filter(r=>r.zone===z).length,'待服務關係確認','待系統方案',null,'未計算',null,null,'待性能需求核定','先核對房間、同時峰值、顯潛熱責任與設備工況']);
for(let i=0;i<zones.length;i++)formula(e,`F${5+i}`,`=IF(ISNUMBER(E${5+i}),E${5+i}*'核准標準'!$B$6,"未計算")`);
e.getRange(`E5:E${4+zones.length}`).format.fill='#FFF2CC';e.getRange(`A5:J${4+zones.length}`).format.rowHeight=48;

// All checks observe the model; no check output is used by any design formula.
wb.recalculate();
const observed = sh => sh.getRange(`M${total}`).values[0][0];
const expectedPeople=rooms.reduce((a,r)=>a+r.people,0);
if(observed(v)!==expectedPeople*10)throw new Error(`新風合計錯誤:${observed(v)}`);
const changed=[];
function expectValue(sh,cell,expected,label){const actual=sh.getRange(cell).values[0][0];const ok=typeof actual==='number'&&typeof expected==='number'?Math.abs(actual-expected)<1e-9:actual===expected;if(!ok)throw new Error(`${label}:${JSON.stringify(actual)} != ${expected}`);changed.push({label,actual,expected});}
const oldPeople=src.getRange('E5').values[0][0];
value(src,'E5',null);wb.recalculate();expectValue(v,'M5','未計算','缺人數不變零');
expectValue(v,`M${total}`,'資料未齊','缺人數不可低報合計');
value(src,'E5',0);wb.recalculate();expectValue(v,'M5',0,'真實零人數保留零');
value(src,'E5',oldPeople+1);wb.recalculate();expectValue(v,'M5',(oldPeople+1)*10,'人數變更重算');
value(src,'E5',oldPeople);
value(c,'L5',100);wb.recalculate();expectValue(c,'G5',115,'最終負荷只加一次SF');
value(c,'L5',0);wb.recalculate();expectValue(c,'G5',0,'真實零負荷保留零');
value(c,'L5',null);wb.recalculate();expectValue(c,'G5','未計算','未完成冷負荷不變零');
const check = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'formula error scan'});
console.log(check.ndjson);
console.log((await wb.inspect({kind:'table',range:`通風計算!K${last}:M${total}`,include:'values,formulas',tableMaxRows:2,tableMaxCols:3,maxChars:2000})).ndjson);
await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({rooms:rooms.length,source_people:expectedPeople,fresh_air_lps:observed(v),checks:changed,error_scan:check.ndjson,new_cooling_status:'未計算',verified_in:'artifact-tool calculation engine; not native Excel application'},null,2));
for(const n of names){
 const sh=sheets[n],cols=n==='建築參數'?11:n==='通風計算'?16:n==='冷熱負荷計算'?14:n==='核准標準'?5:n==='設備需求'?10:15;
 const rows=n==='核准標準'?19:n==='設備需求'?4+zones.length:n==='HAP原報表'?last:total;
 const chunks=rows>30?[[1,22],[23,41],[42,rows]]:[[1,rows]];
 for(let i=0;i<chunks.length;i++){
  const [start,end]=chunks[i];const img=await wb.render({sheetName:n,range:`A${start}:${column(cols)}${end}`,scale:1,format:'png'});
  await fs.writeFile(path.join(out,`${n}_${i+1}.png`),new Uint8Array(await img.arrayBuffer()));
 }
}
const exportFile=await SpreadsheetFile.exportXlsx(wb);
const final=path.join(out,'設計資料與公司標準覆核.xlsx');await exportFile.save(final);
console.log(JSON.stringify({output:final,rooms:rooms.length,people:expectedPeople,freshAirLps:observed(v),newCooling:'未計算'}));
