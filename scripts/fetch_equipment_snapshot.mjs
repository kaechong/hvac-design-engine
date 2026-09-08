/** 唯讀設備資料快照。使用既有 Retool MCP client；不輸出或複製憑證。 */
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const helper=process.env.RETOOL_EXEC_HELPER || resolve(root,'../HVAC資料庫/tools/retool-mcp-client/exec_helper.mjs');
const resource='bf43c988-519f-49e6-9b75-aca6f483a88b';
const local=resolve(root,'data/local');mkdirSync(local,{recursive:true});
const args=resolve(local,'equipment_query_args.json');
function call(name,body){writeFileSync(args,JSON.stringify(body));const r=spawnSync(process.execPath,[helper,name,args],{encoding:'utf8',maxBuffer:20*1024*1024});if(r.status!==0)throw new Error('Retool request failed; verify local OAuth session.');const out=JSON.parse(r.stdout.replace(/^\uFEFF/,''));if(out.isError)throw new Error('Retool returned an error.');for(const item of out.content||[]){try{const p=JSON.parse(item.text);if(p.success===false)throw new Error('Retool query failed');if(p.data)return p.data;}catch(e){if(e.message==='Retool query failed')throw e;}}if(out.structuredContent)return out.structuredContent;throw new Error('Unexpected Retool result shape');}
call('retool_get_resource_ts_definitions',{resourceNames:[resource]});
// Fixed SELECT-only statement: one database statement makes the four tables consistent.
const sql="SELECT json_build_object('materials',(SELECT json_agg(m ORDER BY mat_id) FROM material_master m),'specs',(SELECT json_agg(s ORDER BY spec_id) FROM material_spec s),'certifications',(SELECT json_agg(c) FROM material_certification c),'documents',(SELECT json_agg(d ORDER BY document_id) FROM document_master d)) AS snapshot";
const data=call('retool_execute_resource_ts',{resourceNames:[resource],code:`const r = await retool.query(${JSON.stringify(sql)}); return r.data[0].snapshot;`});
const snapshot=data.result??data;
if(!Array.isArray(snapshot.materials))throw new Error('Snapshot shape invalid: materials missing');
const queried_at=new Date().toISOString();
const out=resolve(local,`equipment_snapshot_${queried_at.replace(/[-:.]/g,'')}.json`);
writeFileSync(out,JSON.stringify({queried_at,source:'live_retool',resource_id:resource,...snapshot},null,2),{flag:'wx'});
console.log(JSON.stringify({path:out,queried_at,counts:Object.fromEntries(['materials','specs','certifications','documents'].map(k=>[k,snapshot[k].length]))}));
