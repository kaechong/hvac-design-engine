import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = path.resolve(root, process.env.HVAC_OUTPUT_DIR || 'outputs/revised_20260908');
const pkg = JSON.parse(await fs.readFile(path.join(outputDir, 'design_package.json'), 'utf8'));
const {input, result, equipment} = pkg;
await fs.mkdir(outputDir, {recursive: true});

const wb = Workbook.create();
const names = ['概覽','建築參數','通風計算','冷負荷計算','系統負荷密度','逐時系統負荷','待覆核事項'];
const sh = Object.fromEntries(names.map(name => [name, wb.worksheets.add(name)]));
const font = {name: 'Arial', size: 10, color: '#111111'};
const navy = '#D9D9D9';
const pale = '#EEEEEE';
function col(n) { let r=''; while(n){n--; r=String.fromCharCode(65+n%26)+r; n=Math.floor(n/26);} return r; }
function setup(sheet, title, subtitle, headers, widths, rows=40) {
  const end = col(headers.length);
  sheet.showGridLines = false;
  sheet.getRange(`A1:${end}${rows}`).format.font = font;
  sheet.mergeCells(`A1:${end}1`);
  sheet.getRange('A1').values=[[title+'｜'+pkg.version]];
  sheet.getRange('A1').format.font={...font,size:15,bold:true,color:'#000000'};
  sheet.getRange('A1').format.fill=navy;
  sheet.getRange('A1').format.rowHeight=30;
  sheet.mergeCells(`A2:${end}2`);
  sheet.getRange('A2').values=[[subtitle]];
  sheet.getRange('A2').format.font={...font,size:10,italic:true,color:'#444444'};
  sheet.getRange('A2').format.rowHeight=28;
  sheet.getRange(`A4:${end}4`).values=[headers];
  sheet.getRange(`A4:${end}4`).format.fill=navy;
  sheet.getRange(`A4:${end}4`).format.font={...font,bold:true,color:'#000000'};
  sheet.getRange(`A4:${end}4`).format.horizontalAlignment='center';
  sheet.getRange(`A4:${end}4`).format.wrapText=true;
  sheet.getRange(`A4:${end}4`).format.rowHeight=58;
  sheet.getRange(`A5:${end}${rows}`).format.rowHeight=46;
  sheet.getRange(`A4:${end}${rows}`).format.borders={preset:'all',style:'thin',color:'#000000'};
  sheet.getRange(`A4:${end}${rows}`).format.verticalAlignment='center';
  sheet.getRange(`A4:${end}${rows}`).format.wrapText=true;
  widths.forEach((w,i)=>sheet.getRange(`${col(i+1)}1:${col(i+1)}${rows}`).format.columnWidth=w);
  sheet.freezePanes.freezeRows(4);
}
function section(sheet, cell, text, end) {
  sheet.mergeCells(`${cell}:${end}${cell.match(/\d+/)[0]}`);
  sheet.getRange(cell).values=[[text]];
  sheet.getRange(cell).format.fill=pale;
  sheet.getRange(cell).format.font={...font,bold:true,color:'#17365D'};
}
const inputById = new Map(input.rooms.map(r=>[r.room_id,r]));
const rooms = result.rooms.map(row => ({...row, input: inputById.get(row.room_id)}));
const systems = result.systems;

setup(sh['概覽'], '零售展廳HVAC完整設計測試', '2024-06-03 圖紙試點｜設計輸入含明示假設，僅供流程與工程覆核測試。', ['項目','數值','單位','說明'], [28,25,18,62], 23);
sh['概覽'].getRange('A5:D12').values=[
 ['圖紙範圍','地庫、地面層、一樓',null,'28頁A3 1:50圖紙。建築平面：P1、P10、P20；天花圖：P3、P12、P22。'],
 ['室內設計條件','23 / 55','°C / %RH','已核准公司基準。'],
 ['室外設計條件','34DB / 28WB','°C','澳門夏季，已核准公司基準。'],
 ['新風率',10,'L/s/人','人數為本試點明示假設，正式項目需確認。'],
 ['衛生間排風',15,'ACH','按假設淨高3.0m計算。'],
 ['冷負荷安全係數',1.15,'倍','只在未加SF系統最終冷負荷套用一次。'],
 ['計算方法','顯式逐時分項',null,'非Carrier HAP，未包含完整動態傳熱。'],
 ['設備選型狀態','需求已建立',null,'型號性能資料不足，未發出最終選型。'],
];
section(sh['概覽'],'A14','系統設計摘要','D');
sh['概覽'].getRange('A15:D15').values=[['系統','已建模設計需求\n含15%SF（kW）','新風（L/s）','排風（L/s）']];
sh['概覽'].getRange('A15:D15').format.fill=navy; sh['概覽'].getRange('A15:D15').format.font={...font,bold:true,color:'#000000'};
sh['概覽'].getRange('A15:D15').format.rowHeight=52;
sh['概覽'].getRange('A15:D15').format.wrapText=true;
sh['概覽'].getRange('A16:D18').values=systems.map(s=>[s.system_id,s.sizing_peak.total_kw,s.fresh_air_ls,s.exhaust_ls]);
sh['概覽'].getRange('B16:B18').format.numberFormat='0.00'; sh['概覽'].getRange('C16:D18').format.numberFormat='0.0';
sh['概覽'].getRange('A20:D20').values=[['總計','=SUM(B16:B18)','=SUM(C16:C18)','=SUM(D16:D18)']];
sh['概覽'].getRange('B20:D20').format.numberFormat='0.00';
sh['概覽'].mergeCells('A22:D23');
sh['概覽'].getRange('A22').values=[['版本：'+pkg.version+'。本總量不包含未建模的新風盤管冷量；設備明細另檔。粗估W/m²見系統負荷密度。']];
sh['概覽'].getRange('A22').format.wrapText=true;
sh['概覽'].getRange('A20:D20').format.font={...font,bold:true}; sh['概覽'].getRange('A20:D20').format.fill='#E2F0D9';


setup(sh['建築參數'], '建築參數', '面積、淨高與人數沿用明示測試假設。體積(m³)＝面積(m²)×淨高(m)。', ['房間編號','房間名稱','樓層','面積\n(m²)','淨高\n(m)','體積\n(m³)','定員\n(人)','用途','朝向','圖紙依據','資料狀態'], [16,18,14,14,14,16,12,16,15,26,34], 13);
const drawingEvidence={'地庫':'P1/P2/P3','地面層':'P10/P11/P12','一樓':'P20/P21/P22'};
sh['建築參數'].getRange('A5:K13').values=rooms.map((r,i)=>{
 const m=r.input.room_metadata,k=i+5;
 return [r.room_id,m.name_zh,m.floor,m.area_m2,r.input.volume_m3/m.area_m2,`=D${k}*E${k}`,r.input.people,m.function,'待確定',drawingEvidence[m.floor],m.review_status];
});
sh['建築參數'].getRange('D5:F13').format.numberFormat='0.00';
setup(sh['通風計算'], '通風計算', '排風(m³/h)＝體積(m³)×ACH(h⁻¹)；L/s＝m³/h÷3.6；新風＝人數×10L/s／人。其他房間0ACH為原試點假設。', ['房間編號','房間名稱','樓層','面積\n(m²)','淨高\n(m)','體積\n(m³)','用途','換氣次數\n(h⁻¹／ACH)','排風量\n(m³/h)','排風量\n(L/s)','人數\n(人)','人均新風\n(L/s／人)','新風量\n(L/s)','排風需求編號','機外靜壓\n(Pa)','新風量\n(m³/h)'],[16,18,14,14,14,16,16,18,16,16,12,18,16,25,18,16],15);
sh['通風計算'].getRange('A5:P13').values=rooms.map((r,i)=>{
 const k=i+5,m=r.input.room_metadata;
 return [r.room_id,m.name_zh,m.floor,`='建築參數'!D${k}`,`='建築參數'!E${k}`,`=D${k}*E${k}`,m.function,r.input.exhaust_ach>0?"='概覽'!$B$9":0,`=F${k}*H${k}`,`=I${k}/3.6`,`='建築參數'!G${k}`,"='概覽'!$B$8",`=K${k}*L${k}`,equipment.find(e=>e.category==='TEF'&&e.room_ids.includes(r.room_id))?.id??'不適用',r.input.exhaust_ach>0?'待計算':'不適用',`=M${k}*3.6`];
});
sh['通風計算'].getRange('D5:M13').format.numberFormat='0.0';
sh['通風計算'].getRange('P5:P13').format.numberFormat='0.0';
sh['通風計算'].getRange('A15:P15').values=[['總計','','','','','','','','=SUM(I5:I13)','=SUM(J5:J13)','=SUM(K5:K13)','','=SUM(M5:M13)','','','=SUM(P5:P13)']];
setup(sh['冷負荷計算'], '冷負荷計算', '同一房間全熱峰值時刻的分項；G只含D＋E。新風盤管F未計算，不能把G當完整總冷量。W/m²僅供本試點粗估，未含SF。', ['房間編號','房間名稱','面積\n(m²)','圍護及日射\n(kW)','內部發熱\n(kW)','新風盤管\n(kW)','已建模房間負荷\n未含SF(kW)','供暖負荷\n(kW)','負荷密度\n未含SF(W/m²)','容量換算\n未含SF(RT)','設備需求對映','顯熱\n(kW)','潛熱\n(kW)','峰值時刻','資料狀態'],[16,18,14,18,18,18,23,18,23,21,36,16,16,27,35],13);
sh['冷負荷計算'].getRange('A5:O13').values=rooms.map((r,i)=>{
 const k=i+5,t=input.time_keys.indexOf(r.raw_peak.time_key);
 const env=r.input.components.reduce((a,x)=>a+x.sensible_kw[t]+x.latent_kw[t],0);
 return [r.room_id,r.input.room_metadata.name_zh,`='建築參數'!D${k}`,env,`=L${k}+M${k}-D${k}`,'未計算',`=D${k}+E${k}`,'未計算',`=G${k}*1000/C${k}`,`=G${k}/3.517`,equipment.filter(e=>e.room_ids.includes(r.room_id)).map(e=>e.id).join('\n'),r.raw_peak.sensible_kw,r.raw_peak.latent_kw,r.raw_peak.time_key,'明示假設，待覆核'];
});
for(const rng of ['C5:E13','G5:G13','I5:J13','L5:M13'])sh['冷負荷計算'].getRange(rng).format.numberFormat='0.00';
sh['冷負荷計算'].getRange('A5:O13').format.rowHeight=62;
setup(sh['系統負荷密度'], '系統負荷及粗估密度', '面積包含原試點系統所屬全部房間（含衛生間），未必等同最終空調面積。W/m²＝kW×1000÷m²，非通用負荷標準；不含新風盤管。', ['系統','服務面積\n(m²)','同時峰值\n未含SF(kW)','SF\n(倍)','設計需求\n含SF(kW)','粗估密度\n未含SF(W/m²)','粗估密度\n含SF(W/m²)','新風\n(L/s)','排風\n(L/s)','需求記錄','峰值時刻'],[16,18,22,12,22,23,23,16,16,25,27],10);
sh['系統負荷密度'].getRange('A5:K7').values=systems.map((s,i)=>{
 const k=i+5;return [s.system_id,rooms.filter(r=>r.system_id===s.system_id).reduce((n,r)=>n+r.input.room_metadata.area_m2,0),s.raw_peak.total_kw,"='概覽'!$B$10",`=C${k}*D${k}`,`=C${k}*1000/B${k}`,`=E${k}*1000/B${k}`,s.fresh_air_ls,s.exhaust_ls,equipment.find(e=>e.category==='AC'&&e.system_id===s.system_id).id,s.raw_peak.time_key];
});
sh['系統負荷密度'].getRange('A9:K9').values=[['各系統峰值合計','=SUM(B5:B7)','=SUM(C5:C7)','', '=SUM(E5:E7)','=C9*1000/B9','=E9*1000/B9','=SUM(H5:H7)','=SUM(I5:I7)','非建築同時峰值','']];
sh['系統負荷密度'].getRange('B5:I9').format.numberFormat='0.00';
setup(sh['逐時系統負荷'], '逐時系統負荷', '同一時刻彙總系統房間負荷，避免將各房獨立峰值直接相加。', ['時間',...systems.flatMap(s=>[`${s.system_id} 顯熱(kW)`,`${s.system_id} 潛熱(kW)`,`${s.system_id} 全熱(kW)`])], [25,...systems.flatMap(()=>[16,16,16])], 28);
sh['逐時系統負荷'].getRange('A5:J28').values=input.time_keys.map((t,i)=>[t,...systems.flatMap(s=>{const x=s.raw_hourly[i];return [x.sensible_kw,x.latent_kw,x.total_kw];})]);
sh['逐時系統負荷'].getRange('B5:J28').format.numberFormat='0.000';

setup(sh['待覆核事項'], '待覆核事項', '以下未決輸入會改變設計結果；表內沒有以零取代缺值。', ['編號','未決項','影響','所需資料/行動','狀態'], [12,32,44,68,24], 14);
sh['待覆核事項'].getRange('A5:E14').values=[
 ['R01','房間面積及邊界','圍護、照明、設備及風量','提供原CAD或實量面積，確認各房間分區。','待確認'],
 ['R02','淨高','衛生間排風量','提供天花/梁下淨高及可用機電淨空。','待確認'],
 ['R03','外牆、玻璃及方位','圍護及日射冷負荷','提供外牆/窗表、U值、SHGC、遮陽及正北方位。','待確認'],
 ['R04','人數及營業排程','新風、內熱源及峰值','確認職員、顧客設計人數及逐時佔用。','待確認'],
 ['R05','燈具及設備功率','內部顯熱','提供燈具回路功率、收銀/展示設備及排熱去向。','待確認'],
 ['R06','空調系統邊界','新風與盤管冷量','確認使用VRF、冷凍水或樓宇供冷，及新風處理責任。','待確認'],
 ['R07','既有AC及低抽排氣','設備更新/改造範圍','核對P3/P12/P22符號對應設備、型號、容量及保留/拆除。','待確認'],
 ['R08','風管路由與靜壓','EAF/FAU選型','確認豎井、風口位置、路由及噪音限制。','待確認'],
 ['R09','設備性能資料','最終選型','取得原廠同工況性能表、曲線、水/冷媒及電力資料。','待確認'],
 ['R10','防火及法規','系統交接','確認當地消防、排煙、通風及機電審批要求。','待確認'],
];
sh['待覆核事項'].getRange('E5:E14').format.fill='#FFF2CC';

if(pkg.air_treatment){
 const a=pkg.air_treatment;
 sh['概覽'].getRange('A1').values=[['零售展廳 HVAC 設計計算｜'+pkg.version]];
 sh['概覽'].getRange('A2').values=[['設計值、來源與內部覆核分頁管理；末端與新風盤管分列。']];
 sh['概覽'].getRange('B12:D12').values=[['暫定配置及原廠候選','—','按原廠工況核對後定案，資料來源見設備選型依據。']];
 sh['概覽'].getRange('A20').values=[['室內末端合計']];
 sh['概覽'].getRange('A22').values=[['末端負荷不含新風。新風另設冷卻除濕及再熱，盤管需求見新風處理計算；再熱不另計冷負荷。']];
 sh['冷負荷計算'].getRange('A2').values=[['房間峰值分項；G＝D＋E。新風由FAU獨立處理。冷負荷密度＝房間未含SF冷負荷÷房間面積。']];
 for(let r=5;r<=13;r++){sh['冷負荷計算'].getRange(`F${r}`).values=[['由FAU處理']];sh['冷負荷計算'].getRange(`H${r}`).values=[['不適用']];}
 sh['系統負荷密度'].getRange('A1').values=[['系統冷負荷密度｜'+pkg.version]];
 sh['系統負荷密度'].getRange('F4:G4').values=[['冷負荷密度\n未含SF(W/m²)','冷負荷密度\n含SF(W/m²)']];
 function extra(name,title,subtitle,headers,widths,rows){names.push(name);const s=wb.worksheets.add(name);sh[name]=s;setup(s,title,subtitle,headers,widths,rows.length+4);s.getRange(`A5:${col(headers.length)}${rows.length+4}`).values=rows;return s;}
 const h=s=>s.enthalpy_kjkg,w=s=>s.humidity_ratio_kgkg;
 extra('新風處理計算','新風冷卻除濕及再熱','流量按入口實際體積；焓以每kg乾空氣為基準。SF只用於盤管選型冷量。',['項目','數量／公式','單位','計算口徑'],[32,26,22,82],[
 ['入口新風量',a.airflow_ls,'L/s','設計人數×10 L/s/人'],
 ['入口新風量','=B5*3.6','m³/h','L/s×3.6'],
 ['入口比容',a.inlet.specific_volume_m3kg_da,'m³/kg_da','34°CDB／28°CWB，101325Pa'],
 ['乾空氣質量流量','=B5/1000/B7','kg_da/s','體積流量÷入口比容'],
 ['入口焓',h(a.inlet),'kJ/kg_da','室外設計工況'],
 ['盤管出口焓',h(a.coil_outlet),'kJ/kg_da',`${a.coil_outlet.db_c.toFixed(2)}°C／95%RH`],
 ['室內中性送風焓',h(a.supply),'kJ/kg_da','23°C／55%RH'],
 ['原始盤管冷量','=B8*(B9-B10)','kW','乾空氣質量流量×盤管進出風焓差'],
 ['冷負荷安全係數',"='概覽'!B10",'倍','只乘一次'],
 ['盤管選型冷量','=B12*B13','kW','原始盤管冷量×1.15'],
 ['再熱量','=B8*(B11-B10)','kW','乾空氣質量流量×送風與盤管出口焓差；不再乘冷負荷SF'],
 ['新風淨焓差負荷','=B8*(B9-B11)','kW','盤管原始冷量−再熱量'],
 ['焓差平衡校核','=B12-B15-B16','kW','應為0'],
 ['入口含濕量',w(a.inlet),'kg/kg_da','34°CDB／28°CWB'],
 ['盤管出口含濕量',w(a.coil_outlet),'kg/kg_da','盤管目標95%RH'],
 ['送風含濕量',w(a.supply),'kg/kg_da','23°C／55%RH，純再熱不改變含濕量'],
 ['凝結水量','=B8*(B18-B19)*3600','kg/h','乾空氣質量流量×含濕量差×3600'],
 ['室內末端選型冷量',"='概覽'!B20",'kW','原房間負荷加SF，不包括新風'],
 ['末端與新風盤管需求合計','=B14+B22','kW','兩類設備需求之和，非建築同時峰值；不再乘SF'],
 ['工況及風機熱',a.assumptions.join('；'),'—','設計工況待原廠盤管選型驗證'],
 ]).getRange('B5:B23').format.numberFormat='0.0000';
 sh['新風處理計算'].getRange('A24:D24').format.rowHeight=88;
 const cfg=pkg.configuration||[];
 extra('設備選型依據','設備配置與性能依據','標稱性能與本工程設計點性能分開。候選不代表已核准配對。',['編號／系統','品牌及型號','角色／數量（台）','標稱冷量（kW）','服務房間','工況及核對狀態','來源'],[24,32,20,18,28,65,65],cfg.map(c=>[c.equipment_id,c.brand+' '+c.model,`${c.role}／${c.quantity}`,c.nominal_cooling_kw??'待核對',(c.room_ids||[]).join('、'),[c.rating_condition,...(c.rating_conditions||[]),c.selection_status,...(c.missing||[])].filter(Boolean).join('；'),c.source_url||c.source_id||'來源待核對']));
 sh['設備選型依據'].getUsedRange().format.rowHeight=70;sh['設備選型依據'].getRange('A1:G3').format.rowHeight=25;sh['設備選型依據'].getRange('A4:G4').format.rowHeight=48;
 const review=pkg.internal_review||[];
 extra('內部覆核','內部覆核與設計決策','助手完成一般查證；以下集中保留會改變方案的邊界及計算假設。',['編號','事項','目前採用','改變方案的影響'],[12,28,85,75],review.map(r=>[r.id,r.item,r.adopted,r.impact])).getRange(`A5:D${review.length+4}`).format.rowHeight=100;
 const sup=pkg.source_supplement||{};
 const sources=sup.sources||[];
 const srcRows=[['SNAPSHOT',pkg.snapshot?.queried_at||pkg.equipment_snapshot?.queried_at||'見資料快照',pkg.snapshot?.path||pkg.equipment_snapshot?.path||'data/local/equipment_snapshot_20260908.json',pkg.equipment_snapshot?.notice||'唯讀查詢，保留快照日期及原始資料'],...sources.map(s=>[s.id,s.title||s.method,s.url,`頁次 ${s.reviewed_pages||s.pages||s.printed_page||'原廠網頁'}；${s.method||''}`]),['PSYCHROMETRIC','新風濕空氣公式',a.source,'採ASHRAE SI濕球關係；盤管離風目標95%RH'],...(sup.database_quality_findings||[]).map((q,i)=>['QUALITY-'+(i+1),q.local_status,q.mat_id_range||(q.mat_ids||[]).join('、'),q.reason])];
 extra('資料來源','來源與資料品質','關聯型錄名稱差異只在本專案記錄，不回寫既有資料庫。',['來源編號','來源／查詢日期','路徑／網址','核對內容'],[26,48,80,75],srcRows).getRange(`A5:D${srcRows.length+4}`).format.rowHeight=100;
 sh['資料來源'].getRange('B5').format.numberFormat='yyyy-mm-dd hh:mm:ss" UTC"';
 cfg.forEach((c,i)=>{if(c.published_operating_point){const d=c.published_operating_point;sh['設備選型依據'].getRange(`F${i+5}`).values=[[`原廠參考工作點：${d.airflow_m3h}m³/h、${d.static_pressure_pa}Pa、${d.rpm}rpm、${d.power_w}W、控制${d.control_v}V。屬同一公開工作點；本工程工作點及選速仍須核對。`]];}});
 const comparisons=[];
 for(const p of pkg.selection_plan||[]){
  comparisons.push([p.system_id,p.recommended_provisional||'見設備配置',p.reason||'候選未完成設計點核對','暫定推薦']);
  for(const x of p.alternatives||[])comparisons.push([p.system_id,x.model,x.reason||'見名義容量與連接率核對','備選']);
  for(const x of p.rejected||[])comparisons.push([p.system_id,x.model,x.reason,'淘汰']);
  for(const r of p.nominal_comparisons?.rooms||[]){
   for(const [items,status] of [[[r.provisional],'房間暫定配置'],[r.alternatives||[],'房間備選'],[r.rejected||[],'房間淘汰']]){
    for(const x of items)comparisons.push([r.room_id,`${x.model} × ${x.quantity}台`,`標稱${x.nominal_total_kw.toFixed(2)}kW／需求${x.required_kw.toFixed(2)}kW；名義風量${x.nominal_airflow_ls.toFixed(1)}L/s／需求${x.required_airflow_ls.toFixed(1)}L/s。${x.reasons?.join('；')||r.reason}。${r.airflow_basis}` ,status]);
   }
  }
 }
 if(comparisons.length)extra('配置比較','配置比較及淘汰理由','先比較同用途容量與分區；未知效率、噪音及單價不参与排序。',['系統','配置／型號','理由','狀態'],[24,48,105,22],comparisons).getRange(`A5:D${comparisons.length+4}`).format.rowHeight=85;
 sh['待覆核事項'].getRange('A2').values=[['內部資料追查清單；一般資料核對由助手處理，關鍵決策集中見內部覆核頁。']];
 sh['待覆核事項'].getRange('D5:E14').values=[
  ['由原建築圖核對邊界及尺寸；沿用輸入的面積保留原證據狀態。','助手追查'],
  ['核對剖面及天花標高；目前採3.0m。','助手追查'],
  ['由建築詳圖及既有資料核對外牆、玻璃與方位；差異列入重算條件。','助手追查'],
  ['按用途及營業排程整理人數；如營運條件不同則集中調整。','內部覆核'],
  ['按燈具及設備表追查功率，缺表時保留用途基準。','助手追查'],
  ['暫採分層VRF及自設全新風處理，供冷邊界列為集中決策。','集中決策'],
  ['由現有圖紙與設備記錄判讀保留／拆除範圍。','助手追查'],
  ['按路由計算阻力後核對原廠曲線；不以最大靜壓代替需求。','工程深化'],
  ['已查資料庫及原廠型錄，按本工程工況繼續核對顯熱、配對及調節能力。','候選已整理'],
  ['核對本項目適用條文與物業標準，版本差異不擅改固定原文。','內部覆核'],
 ];
 sh['待覆核事項'].getRange('D13:E13').values=[['已查現有資料庫及關聯原廠型錄，候選及缺項見設備選型依據。','候選已整理']];
}
for (const sheet of Object.values(sh)) sheet.getUsedRange().format.verticalAlignment='center';
await fs.mkdir(path.join(outputDir,'qa'),{recursive:true});
wb.recalculate();
const summary = await wb.inspect({kind:'table',range:'系統負荷密度!A5:K9',include:'values,formulas',tableMaxRows:12,tableMaxCols:11});
console.log(summary.ndjson);
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'formula error scan'});
console.log(errors.ndjson);
for (const name of names) {
  const image = await wb.render({sheetName:name,autoCrop:'all',scale:1.3,format:'png'});
  await fs.writeFile(path.join(outputDir, 'qa', `${name}.png`), new Uint8Array(await image.arrayBuffer()));
  if(name==='配置比較'){
   const last=sh[name].getUsedRange().values.length;
   for(let start=1;start<=last;start+=14){const part=await wb.render({sheetName:name,range:`A${start}:D${Math.min(start+13,last)}`,scale:1.2,format:'png'});await fs.writeFile(path.join(outputDir,'qa',`配置比較_${start}.png`),new Uint8Array(await part.arrayBuffer()));}
  }
}
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(outputDir,'設計計算表.xlsx'));
