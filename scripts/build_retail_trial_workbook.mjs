import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const input = JSON.parse(await fs.readFile(path.join(root, 'data/local/trial_2024_06_03_retail_input.json'), 'utf8'));
const result = JSON.parse(await fs.readFile(path.join(root, 'outputs/review/retail_trial_result.json'), 'utf8'));
const outputDir = path.join(root, 'outputs/retail_trial_20260907');
await fs.mkdir(outputDir, {recursive: true});

const wb = Workbook.create();
const names = ['概覽','建築及假設','通風及排風','冷負荷','系統設備需求','逐時系統負荷','待覆核事項'];
const sh = Object.fromEntries(names.map(name => [name, wb.worksheets.add(name)]));
const font = {name: 'Arial', size: 10, color: '#111111'};
const navy = '#1F4E78';
const pale = '#D9EAF7';
function col(n) { let r=''; while(n){n--; r=String.fromCharCode(65+n%26)+r; n=Math.floor(n/26);} return r; }
function setup(sheet, title, subtitle, headers, widths, rows=40) {
  const end = col(headers.length);
  sheet.showGridLines = false;
  sheet.getRange(`A1:${end}${rows}`).format.font = font;
  sheet.mergeCells(`A1:${end}1`);
  sheet.getRange('A1').values=[[title]];
  sheet.getRange('A1').format.font={...font,size:15,bold:true,color:'#FFFFFF'};
  sheet.getRange('A1').format.fill=navy;
  sheet.getRange('A1').format.rowHeight=30;
  sheet.mergeCells(`A2:${end}2`);
  sheet.getRange('A2').values=[[subtitle]];
  sheet.getRange('A2').format.font={...font,size:10,italic:true,color:'#444444'};
  sheet.getRange('A2').format.rowHeight=28;
  sheet.getRange(`A4:${end}4`).values=[headers];
  sheet.getRange(`A4:${end}4`).format.fill=navy;
  sheet.getRange(`A4:${end}4`).format.font={...font,bold:true,color:'#FFFFFF'};
  sheet.getRange(`A4:${end}4`).format.horizontalAlignment='center';
  sheet.getRange(`A4:${end}4`).format.wrapText=true;
  sheet.getRange(`A4:${end}4`).format.rowHeight=34;
  sheet.getRange(`A4:${end}${rows}`).format.borders={preset:'all',style:'thin',color:'#D9D9D9'};
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
const rooms = result.rooms.map((row, i) => ({...row, input: input.rooms[i]}));
const systems = result.systems;

setup(sh['概覽'], '零售展廳HVAC完整設計測試', '2024-06-03 圖紙試點｜設計輸入含明示假設，僅供流程與工程覆核測試。', ['項目','數值','單位','說明'], [28,18,14,78], 32);
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
sh['概覽'].getRange('A15:D15').values=[['系統','設計冷量（含15%SF）','新風','排風']];
sh['概覽'].getRange('A15:D15').format.fill=navy; sh['概覽'].getRange('A15:D15').format.font={...font,bold:true,color:'#FFFFFF'};
sh['概覽'].getRange('A16:D18').values=systems.map(s=>[s.system_id,s.sizing_peak.total_kw,s.fresh_air_ls,s.exhaust_ls]);
sh['概覽'].getRange('B16:B18').format.numberFormat='0.00'; sh['概覽'].getRange('C16:D18').format.numberFormat='0.0';
sh['概覽'].getRange('A20:D20').values=[['總計','=SUM(B16:B18)','=SUM(C16:C18)','=SUM(D16:D18)']];
sh['概覽'].getRange('A20:D20').format.font={...font,bold:true}; sh['概覽'].getRange('A20:D20').format.fill='#E2F0D9';

setup(sh['建築及假設'], '建築參數及假設登記冊', '圖紙有空間分布及局部尺寸，面積與淨高的估算均不可作竣工量度。', ['房間','樓層','用途','面積','淨高','人數','圖紙證據','假設/狀態'], [15,14,16,12,12,12,38,62], 24);
const drawingEvidence = {
  '地庫': 'P1 平面；P2 家具尺寸；P3 天花／空調符號',
  '地面層': 'P10 平面；P11 家具尺寸；P12 天花／空調符號',
  '一樓': 'P20 平面；P21 家具尺寸；P22 天花／空調符號',
};
sh['建築及假設'].getRange('A5:H13').values=rooms.map(r=>[r.room_id,r.input.room_metadata.floor,r.input.room_metadata.name_zh,r.input.room_metadata.area_m2,3.0,r.input.people,drawingEvidence[r.input.room_metadata.floor],r.input.room_metadata.review_status]);
sh['建築及假設'].getRange('D5:F13').format.numberFormat='0.0';
sh['建築及假設'].getRange('A15:H15').values=[['來源記錄','完整設計測試圖紙.pdf','','','','','Google Drive file 1RvowEGCkZnWpAyhuccUFQsQmEYT5kDT9','原圖不入Git，檔案本機快取並由本次試點檢視。']];

setup(sh['通風及排風'], '通風及排風計算', '新風=設計人數×10L/s；衛生間排風=體積×15ACH。未完成補風路徑及壓差設計。', ['房間','用途','人數','體積','新風','排風','補風/壓差狀態'], [15,18,12,15,16,16,60], 18);
sh['通風及排風'].getRange('A5:G13').values=rooms.map(r=>[r.room_id,r.input.room_metadata.name_zh,r.input.people,r.input.volume_m3,r.ventilation.fresh_air_ls,r.ventilation.exhaust_ls,r.input.room_metadata.name_zh==='衛生間'?'待確認補風路徑及負壓目標':'待與新風系統平衡']);
sh['通風及排風'].getRange('C5:F13').format.numberFormat='0.0';
sh['通風及排風'].getRange('A15:G15').values=[['總計','','=SUM(C5:C13)','','=SUM(E5:E13)','=SUM(F5:F13)','排風量不加15%冷負荷SF']];
sh['通風及排風'].getRange('A15:G15').format.font={...font,bold:true}; sh['通風及排風'].getRange('A15:G15').format.fill='#E2F0D9';

setup(sh['冷負荷'], '冷負荷計算', '峰值時刻為2026-07-15 15:00，來自明示24小時測試輪廓；冷負荷為房間負荷，不含未建模的新風盤管。', ['房間','系統','顯熱峰值','潛熱峰值','未加SF全熱','含15%SF全熱','峰值時間','資料狀態'], [15,14,16,16,18,18,22,38], 18);
sh['冷負荷'].getRange('A5:D13').values=rooms.map(r=>[r.room_id,r.system_id,r.raw_peak.sensible_kw,r.raw_peak.latent_kw]);
sh['冷負荷'].getRange('E5:E13').formulas=rooms.map((_,i)=>[`=C${5+i}+D${5+i}`]);
sh['冷負荷'].getRange('F5:F13').formulas=rooms.map((_,i)=>[`=E${5+i}*1.15`]);
sh['冷負荷'].getRange('G5:H13').values=rooms.map(r=>[r.raw_peak.time_key,'測試假設，待項目覆核']);
sh['冷負荷'].getRange('C5:F13').format.numberFormat='0.00';
sh['冷負荷'].getRange('A15:H15').values=[['系統同時峰值','','','','','',null,null]]; sh['冷負荷'].getRange('A15:H15').format.fill=pale; sh['冷負荷'].getRange('A15:H15').format.font={...font,bold:true};
sh['冷負荷'].getRange('A16:H18').values=systems.map(s=>[s.system_id,'系統',s.raw_peak.sensible_kw,s.raw_peak.latent_kw,s.raw_peak.total_kw,s.sizing_peak.total_kw,s.raw_peak.time_key,'同時峰值，未加房間SF後相加']);
sh['冷負荷'].getRange('C16:F18').format.numberFormat='0.00';

setup(sh['系統設備需求'], '系統及設備需求表', '建議以每層獨立DX/VRF室內機分區加集中新風及衛生間排風。此表是需求規格，不是設備型號選定。', ['系統','服務範圍','冷量需求','新風','排風','暫定方案','選型狀態'], [15,32,16,16,16,52,48], 18);
sh['系統設備需求'].getRange('A5:G7').values=systems.map(s=>{
 const floors = [...new Set(rooms.filter(r=>r.system_id===s.system_id).map(r=>r.input.room_metadata.floor))].join('、');
 return [s.system_id,floors,s.sizing_peak.total_kw,s.fresh_air_ls,s.exhaust_ls,'每層DX/VRF室內機分區；小型集中新風處理及衛生間EAF','待原廠性能表、冷媒/冷凝水路徑、ESP及供回風布置覆核'];
});
sh['系統設備需求'].getRange('C5:E7').format.numberFormat='0.0';
sh['系統設備需求'].getRange('A10:G13').values=[
 ['新風處理單元','全項目',null,'=SUM(D5:D7)','=SUM(E5:E7)','新風需求約3,312m³/h；需核對樓宇預處理或自設FAU/DOAS','現有資料庫PAU最小風量10,000m³/h，未匹配本試點需求'],
 ['衛生間EAF','BF/GF',null,0,'=SUM(E5:E6)','按各衛生間15ACH，確認補風後選風機','待風管阻力、原廠曲線及噪音覆核'],
 ['FCU/AHU候選','各層',null,null,null,'設備庫有風量及ESP資料，但欠同工況冷量/顯熱結構化數據','不可完成最終型號選定'],
 ['施工圖交接','各層',null,null,null,'需輸出設備位置、風口、風管/冷媒管及冷凝水路由','本期只完成設計資料，未製圖'],
];
sh['系統設備需求'].getRange('D10:E13').format.numberFormat='0.0';

setup(sh['逐時系統負荷'], '逐時系統負荷', '同一時刻彙總系統房間負荷，避免將各房獨立峰值直接相加。', ['時間',...systems.flatMap(s=>[`${s.system_id} 顯熱`,`${s.system_id} 潛熱`,`${s.system_id} 全熱`])], [20,...systems.flatMap(()=>[16,16,16])], 30);
sh['逐時系統負荷'].getRange('A5:J28').values=input.time_keys.map((t,i)=>[t,...systems.flatMap(s=>{const x=s.raw_hourly[i];return [x.sensible_kw,x.latent_kw,x.total_kw];})]);
sh['逐時系統負荷'].getRange('B5:J28').format.numberFormat='0.000';

setup(sh['待覆核事項'], '待覆核事項', '以下未決輸入會改變設計結果；表內沒有以零取代缺值。', ['編號','未決項','影響','所需資料/行動','狀態'], [12,32,44,68,24], 20);
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

for (const sheet of Object.values(sh)) sheet.getUsedRange().format.verticalAlignment='center';
wb.recalculate();
const summary = await wb.inspect({kind:'table',range:'概覽!A14:D20',include:'values,formulas',tableMaxRows:12,tableMaxCols:6});
console.log(summary.ndjson);
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'formula error scan'});
console.log(errors.ndjson);
for (const name of names) {
  const image = await wb.render({sheetName:name,autoCrop:'all',scale:1.3,format:'png'});
  await fs.writeFile(path.join(outputDir, `${name}.png`), new Uint8Array(await image.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(outputDir,'零售展廳_HVAC設計測試.xlsx'));
