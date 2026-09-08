import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dir=path.join(root,'outputs/revised_20260908');
const pkg=JSON.parse(await fs.readFile(path.join(dir,'design_package.json'),'utf8'));
const wb=Workbook.create();
const pending='待確定';
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const roomNames=new Map(pkg.input.rooms.map(r=>[r.room_id,`${r.room_id} ${r.room_metadata.name_zh}`]));
function sheet(name,category,headers,units,widths,makeRow){
 const s=wb.worksheets.add(name),items=pkg.equipment.filter(e=>e.category===category),end=col(headers.length),last=9+items.length;
 s.showGridLines=false;
 const all=s.getRange(`A1:${end}${last+5}`);
 all.format.font={name:'Arial',size:10,color:'#000000'};
 all.format.fill='#FFFFFF';all.format.verticalAlignment='center';all.format.wrapText=true;
 widths.forEach((w,i)=>s.getRange(`${col(i+1)}1:${col(i+1)}${last+5}`).format.columnWidth=w);
 for(const [r,t] of [[1,'零售展廳 HVAC 設計測試'],[2,'T4 設備明細表'],[3,`版本：${pkg.version}　狀態：計算需求，選型待確定`],[5,name==='空調設備'?'空調設備 AC UNITS':name==='風機'?'衛生間排風機 TOILET EXHAUST FANS':'新風處理設備 FRESH AIR HANDLING UNITS']]){
  s.mergeCells(`A${r}:${end}${r}`);s.getRange(`A${r}`).values=[[t]];s.getRange(`A${r}`).format.rowHeight=r===1?30:25;s.getRange(`A${r}`).format.font={name:'Arial',size:r===1?16:12,bold:true};s.getRange(`A${r}`).format.horizontalAlignment='center';
 }
 s.getRange(`A6:${end}6`).values=[headers];s.getRange(`A7:${end}7`).values=[units];
 s.getRange(`A6:${end}7`).format.font={name:'Arial',size:10,bold:true};s.getRange(`A6:${end}7`).format.horizontalAlignment='center';s.getRange(`A6:${end}6`).format.rowHeight=42;s.getRange(`A7:${end}7`).format.rowHeight=25;
 s.getRange(`A8:${end}${7+items.length}`).values=items.map(makeRow);
 s.getRange(`A8:${end}${7+items.length}`).format.rowHeight=104;
 s.getRange(`A5:${end}${7+items.length}`).format.borders={preset:'all',style:'thin',color:'#000000'};
 s.getRange(`A5:${end}7`).format.borders={preset:'outside',style:'medium',color:'#000000'};
 const notes=[
  '註 1：REQ 為需求編號。設備正式編號、型號、數量及室內外機配對均待選型後確定。需求值不代表單台設備性能。',
  '註 2：冷量為系統最終原始負荷一次乘 1.15；新風及排風不加冷負荷安全係數。新風盤管負荷未建模。',
  '註 3：台數、單機性能、電力、噪音及尺寸須按原廠同工況性能及實際分區補齊；缺值以「待確定」顯示。',
 ];
 notes.forEach((t,i)=>{const r=last+i;s.mergeCells(`A${r}:${end}${r}`);s.getRange(`A${r}`).values=[[t]];s.getRange(`A${r}`).format.rowHeight=28;});
 s.freezePanes.freezeRows(7);
 return s;
}
const room=e=>e.room_ids.map(id=>roomNames.get(id)||id).join('\n');
sheet('空調設備','AC',
 ['需求編號','系統／服務房間','設備類型／型號','數量','室內外機配對','系統冷量需求\n含 15% SF','選定室外機\n單機冷量','選定室內機\n單機冷量','室外機\n輸入功率','室內機\n輸入功率','室外機電源','室內機電源','噪音 SPL\n室內／外機','尺寸 W×H×D\n室內／外機','冷媒','狀態及備註'],
 ['—','—','—','台','—','kW','kW','kW','kW','kW','V/Ph/Hz','V/Ph/Hz','dB(A)','mm','—','—'],
 [19,29,16,10,16,13,13,13,12,12,14,14,14,19,11,42],
 e=>[e.id,`${e.system_id}\n${room(e)}`,'DX／VRF\n待系統確認\n型號待確定',e.quantity??pending,pending,e.required_cooling_kw??pending,pending,pending,pending,pending,pending,pending,pending,pending,pending,`${e.status}\n${e.reason}`]);
sheet('風機','TEF',
 ['需求編號','系統／服務房間','數量','排風量需求','選定單機風量','機外靜壓','風機類型／型號','啟動方式','轉速','輸入功率','電源','噪音 SPL','尺寸 W×H×D','狀態及備註'],
 ['—','—','台','L/s','L/s','Pa','—','—','rpm','kW','V/Ph/Hz','dB(A)','mm','—'],
 [20,28,11,13,14,12,16,14,12,13,15,13,20,48],
 e=>[e.id,`${e.system_id}\n${room(e)}`,e.quantity??pending,e.required_airflow_ls??pending,pending,pending,pending,pending,pending,pending,pending,pending,pending,`${e.status}\n${e.reason}`]);
sheet('新風處理','FAU',
 ['需求編號','系統／服務房間','數量','新風量需求','選定單機風量','機外靜壓','設備類型／型號','盤管冷量需求','選定盤管冷量','進風乾球／濕球','出風乾球／濕球','輸入功率','電源','噪音 SPL','尺寸 W×H×D','狀態及備註'],
 ['—','—','台','L/s','L/s','Pa','—','kW','kW','°C DB／°C WB','°C DB／°C WB','kW','V/Ph/Hz','dB(A)','mm','—'],
 [21,34,10,13,13,12,16,14,14,18,18,13,14,13,20,42],
 e=>[e.id,`${e.system_id}\n${room(e)}`,e.quantity??pending,e.required_airflow_ls??pending,pending,pending,'FAU／DOAS\n待方案確認\n型號待確定','未計算',pending,'待確認\n室外基準 34／28',pending,pending,pending,pending,pending,`${e.status}\n${e.reason}`]);
for(const s of wb.worksheets.items){
 s.getUsedRange().format.numberFormat='0.00';
 if(s.name==='空調設備')s.getRange('D8:D10').format.numberFormat='0';
 else s.getRange('C8:C9').format.numberFormat='0';
}
wb.recalculate();
for(const name of ['空調設備','風機','新風處理'])console.log((await wb.inspect({kind:'table',range:`${name}!A6:H10`,include:'values,formulas',tableMaxRows:5,tableMaxCols:8,maxChars:3500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'equipment formula error scan'})).ndjson);
await fs.mkdir(dir,{recursive:true});
for(const name of ['空調設備','風機','新風處理']){
 const blob=await wb.render({sheetName:name,autoCrop:'all',scale:1.2,format:'png'});
 await fs.writeFile(path.join(dir,`${name}_設備預覽.png`),new Uint8Array(await blob.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(dir,'設備明細表.xlsx'));
