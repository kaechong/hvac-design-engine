import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dir=path.resolve(root,process.env.HVAC_OUTPUT_DIR||'outputs/revised_20260908');
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
if(pkg.air_treatment){
 const a=pkg.air_treatment;
 for(const s of wb.worksheets.items){
  s.getRange('A1').values=[['零售展廳 HVAC 工程']];
  s.getRange('A3').values=[[`版本：${pkg.version}　暫定配置；候選型號按設計工況核對後定案`]];
  const items=pkg.equipment.filter(e=>e.category===({'空調設備':'AC','風機':'TEF','新風處理':'FAU'}[s.name]));
  const last=9+items.length;
  s.getRange(`A${last}`).values=[['註 1：REQ為系統需求編號；機組配置另頁列設備編號、暫定台數、型號及對應服務房間。']];
  s.getRange(`A${last+1}`).values=[['註 2：末端及新風盤管原始冷負荷各乘一次1.15；風量不加冷負荷SF，額定性能不等同本工程可用性能。']];
  s.getRange(`A${last+2}`).values=[['註 3：候選型號及額定性能來源見計算工作簿。未取得設計工況證據的單機性能列「待確定」。']];
  items.forEach((e,i)=>{
   const r=i+8,configs=e.configuration||[],ou=configs.filter(c=>c.role==='室外機'),iu=configs.filter(c=>c.role==='室內機');
   if(s.name==='空調設備'){
    s.getRange('D6').values=[['室內機數量']];
    s.getRange('G6:J6').values=[['候選室外機\n標稱單機冷量','候選室內機\n標稱單機冷量','候選室外機\n額定輸入功率','候選室內機\n額定輸入功率']];
    s.getRange(`C${r}`).values=[[e.selected_model||configs.map(c=>c.model).join('\n')||'見機組配置']];
    s.getRange(`E${r}`).values=[[`${iu.map(c=>c.equipment_id).join('、')}\n→${ou.map(c=>c.equipment_id).join('、')}\n配對待原廠核對`]];
    s.getRange(`P${r}`).values=[['有條件候選\n'+(e.selection_notes||[e.reason]).join('\n')]];
    const distinct=(list,key)=>[...new Set(list.map(c=>c[key]??pending))].join('／');
    s.getRange(`G${r}:O${r}`).values=[[ou[0]?.nominal_cooling_kw??pending,distinct(iu,'nominal_cooling_kw'),ou[0]?.nominal_power_kw??pending,distinct(iu,'nominal_power_kw'),distinct(ou,'power_supply'),distinct(iu,'power_supply'),pending,'外：'+distinct(ou,'dimensions')+'\n內：'+distinct(iu,'dimensions'),distinct(configs,'refrigerant')]];
   }else if(s.name==='風機'){
    s.getRange(`G${r}`).values=[[e.selected_model||e.model||'Systemair K 125 EC sileo\n有條件候選']];
    s.getRange(`N${r}`).values=[['1台獨立排風；實際管路阻力及原廠同轉速工作點核對後定案。公開工作點不代入本工程選定性能。']];
   }else{
    s.getRange(`G${r}`).values=[[e.selected_model||e.model||'Systemair Geniox\n模組化系列候選']];
    s.getRange(`H${r}`).values=[[a.sizing_coil.total_kw]];
    s.getRange(`J${r}`).values=[['34／28']];
    s.getRange(`K${r}`).values=[['盤管14.27°C／95%RH\n再熱23°C／55%RH']];
    s.getRange('K7').values=[['°C DB／%RH']];
    s.getRange('K6').values=[['盤管出口／再熱送風\n乾球及相對濕度']];
    s.getRange(`P${r}`).values=[[`盤管${a.sizing_coil.total_kw.toFixed(2)}kW（含SF）；再熱${a.reheat_kw.toFixed(2)}kW。系列涵蓋風量，機組尺寸、盤管及冷源按設計點核對。`]];
   }
  });
 }
 const s=wb.worksheets.add('機組配置'),cfg=pkg.configuration||[],headers=['設備編號','需求／系統','品牌及候選型號','角色','數量','服務房間／配對','標稱單機冷量','標稱單機功率','標稱風量','機外靜壓','電源','尺寸 W×H×D','冷媒','性能基準及狀態'];
 s.showGridLines=false;s.getRange(`A1:N${cfg.length+9}`).format.font={name:'Arial',size:10};s.getRange(`A1:N${cfg.length+9}`).format.wrapText=true;
 [23,22,32,15,10,30,16,16,16,16,22,25,13,65].forEach((w,i)=>s.getRange(`${col(i+1)}1:${col(i+1)}${cfg.length+9}`).format.columnWidth=w);
 for(const [r,t] of [[1,'零售展廳 HVAC 工程'],[2,'T4 機組配置及候選性能'],[3,`版本：${pkg.version}；額定性能未作無依據的工況修正`]]){s.mergeCells(`A${r}:N${r}`);s.getRange(`A${r}`).values=[[t]];s.getRange(`A${r}`).format.rowHeight=28;}
 s.getRange('A6:N6').values=[headers];s.getRange('A7:N7').values=[['—','—','—','—','台','—','kW','kW','m³/h','Pa','V/Ph/Hz','mm','—','—']];
 s.getRange('A6:N7').format.font={name:'Arial',size:10,bold:true};s.getRange('A6:N7').format.rowHeight=38;
 s.getRange(`A8:N${cfg.length+7}`).values=cfg.map(c=>[c.equipment_id,c.requirement_id||pkg.equipment.find(e=>(e.configuration||[]).some(x=>x.equipment_id===c.equipment_id))?.id||c.system_id||'—',c.brand+' '+c.model,c.role,c.quantity,(c.room_ids||[]).map(r=>roomNames.get(r)||r).join('\n')+(c.paired_to?'\n→'+c.paired_to:''),c.nominal_cooling_kw??pending,c.nominal_power_kw??pending,c.nominal_airflow_m3h??c.high_speed_airflow_m3h??pending,c.nominal_esp_pa??pending,c.power_supply||pending,c.dimensions|| (c.dimensions_hwd_mm?[c.dimensions_hwd_mm[1],c.dimensions_hwd_mm[0],c.dimensions_hwd_mm[2]].join('×'):pending),c.refrigerant||pending,['有條件候選',c.rating_condition,...(c.rating_conditions||[]),...(c.missing||[])].filter(Boolean).join('；')]);
 s.getRange(`A8:N${cfg.length+7}`).format.rowHeight=76;s.getRange(`A6:N${cfg.length+7}`).format.borders={preset:'all',style:'thin',color:'#000000'};
 s.getUsedRange().format.verticalAlignment='center';
 cfg.forEach((c,i)=>{if((c.room_ids||[]).length>4)s.getRange(`A${i+8}:N${i+8}`).format.rowHeight=110;});
 s.freezePanes.freezeRows(7);
}
for(const s of wb.worksheets.items){
 s.getUsedRange().format.numberFormat='0.00';
 if(s.name==='空調設備')s.getRange('D8:D10').format.numberFormat='0';
 else if(s.name==='機組配置')s.getRange(`E8:E${(pkg.configuration||[]).length+7}`).format.numberFormat='0';
 else s.getRange('C8:C9').format.numberFormat='0';
}
wb.recalculate();
for(const name of ['空調設備','風機','新風處理'])console.log((await wb.inspect({kind:'table',range:`${name}!A6:H10`,include:'values,formulas',tableMaxRows:5,tableMaxCols:8,maxChars:3500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},summary:'equipment formula error scan'})).ndjson);
await fs.mkdir(dir,{recursive:true});
for(const name of wb.worksheets.items.map(s=>s.name)){
 const blob=await wb.render({sheetName:name,autoCrop:'all',scale:1.2,format:'png'});
 await fs.writeFile(path.join(dir,`${name}_設備預覽.png`),new Uint8Array(await blob.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(dir,'設備明細表.xlsx'));
