"""由即時資料庫快照形成可追溯的暫定配置；庫內標稱性能不冒充設計點性能。"""
import json, sys, hashlib, os, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_design_package import build_package
from hvac_engine.air_treatment import neutral_fresh_air, wet_bulb
from hvac_engine.selection import assess_candidates

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('HVAC_OUTPUT_DIR',ROOT/'outputs/selected_20260908'))

def room_options(demand, sensible_kw, candidates):
    """12°C送風情境；同時核對名義冷量與高速風量，非設計點性能認可。"""
    airflow=sensible_kw*1000/(1.2*1.006*(23-12))
    accepted,rejected=[],[]
    for c in candidates:
        if c['equipment_type']!='VRF_INDOOR':continue
        qty=max(1,math.ceil(demand/c['nominal_cooling_kw']))
        row={'model':c['model'],'quantity':qty,'nominal_total_kw':qty*c['nominal_cooling_kw'],
             'required_kw':demand,'required_airflow_ls':airflow,'nominal_airflow_ls':qty*c['high_speed_airflow_m3h']/3.6,
             'capacity_ratio':qty*c['nominal_cooling_kw']/demand}
        reasons=[]
        if qty>3:reasons.append('超過每房3台配置上限')
        if row['nominal_airflow_ls']<airflow:reasons.append('12°C送風情境下名義風量不足')
        if reasons:rejected.append(dict(row,reasons=reasons))
        else:accepted.append(row)
    accepted.sort(key=lambda x:(x['nominal_total_kw']-demand,x['quantity']))
    if accepted:
        # 本工程政策：與最佳容量匹配差不超過需求10%的配置視為同級，先減少台數。
        limit=accepted[0]['nominal_total_kw']+demand*.1
        first=[x for x in accepted if x['nominal_total_kw']<=limit+1e-9]
        rest=[x for x in accepted if x['nominal_total_kw']>limit+1e-9]
        first.sort(key=lambda x:(x['quantity'],x['nominal_total_kw']))
        accepted=first+rest
    return accepted,rejected

def main():
    inp=json.loads((ROOT/'data/local/trial_2024_06_03_retail_input.json').read_text(encoding='utf-8'))
    result=json.loads((ROOT/'outputs/review/retail_trial_result.json').read_text(encoding='utf-8'))
    snapshot_path=Path(os.environ.get('HVAC_EQUIPMENT_SNAPSHOT', ROOT/'data/local/equipment_snapshot_20260908.json'))
    snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
    p=build_package(inp,result);p['version']='2026-09-08-r3';p['air_treatment']=neutral_fresh_air(920)
    p['equipment_snapshot']={'queried_at':snapshot['queried_at'],'source':snapshot['source'],
        'sha256':hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),'path':str(snapshot_path),
        'mode':os.environ.get('HVAC_SNAPSHOT_MODE','fallback_snapshot'), 'notice':os.environ.get('HVAC_SNAPSHOT_NOTICE','使用保存快照，查詢日期見queried_at'),
        'counts':{k:len(snapshot[k]) for k in ['materials','specs','certifications','documents']}}
    supplement_path=ROOT/'data/reference/equipment_source_supplement.json'
    p['source_supplement']=json.loads(supplement_path.read_text(encoding='utf-8')) if supplement_path.exists() else {}
    supplement=p['source_supplement']; sources={s['id']:s for s in supplement['sources']}
    verified={c['model']:c for c in supplement['candidates']}
    # 只採原PDF完整型號，資料庫名稱矛盾不視為別名。
    normalized={}
    for model,c in verified.items():
        normalized[model]=dict(c,mat_id=c.get('database_mat_id'),source_url=sources[c['source_id']]['url'],
            nominal_power_kw=c.get('nominal_power_kw',c.get('power_kw')), nominal_airflow_m3h=c.get('high_speed_airflow_m3h',c.get('nominal_airflow_m3h')),
            dimensions=' × '.join(str(c['dimensions_hwd_mm'][i]) for i in (1,0,2)) if c.get('dimensions_hwd_mm') else None,
            selection_status='有條件候選',review_status='PendingReview',missing=c.get('pending',[]),
            performance_basis='原廠額定工況數據，非本工程設計点性能')
    layouts={}; nominal_comparisons={}
    for system in result['systems']:
        sid=system['system_id']; floor=sid.removeprefix('DX-'); layout=[]; comparisons=[]
        for rid in system['room_ids']:
            room=next(r for r in inp['rooms'] if r['room_id']==rid)
            if room['exhaust_ach']>0:continue
            rr=next(r for r in result['rooms'] if r['room_id']==rid)
            demand=rr['sizing_peak']['total_kw']
            options,rejected_options=room_options(demand,rr['sizing_sensible_peak_kw'],verified.values())
            if not options:raise ValueError(f'{rid}:名義冷量及風量均滿足的配置不存在')
            chosen=options[0]; layout.append(('IU-'+rid,chosen['model'],chosen['quantity'],[rid],'室內機'))
            alternatives=[x for x in options[1:] if x['nominal_total_kw']<=chosen['nominal_total_kw']+demand*.10][:2]
            rejected_options.extend(dict(x,reasons=['超過本次備選容量匹配範圍，不列推薦備選']) for x in options[1:] if x not in alternatives)
            comparisons.append({'room_id':rid,'provisional':chosen,'alternatives':alternatives,'rejected':rejected_options,'eligible':False,
                'airflow_basis':'V(L/s)=Qs(kW)×1000/[1.2kg/m³×1.006kJ/(kg·K)×(23−12)K]',
                'reason':'每房最多3台；先核對12°C情境名義冷量及風量。與最佳匹配容量差不超過需求10%視為同級，台數較少優先，屬本工程政策非ASHRAE標準。容量裕量及最低調節能力待原廠核對。'})
        total=sum(normalized[x[1]]['nominal_cooling_kw']*x[2] for x in layout);count=sum(x[2] for x in layout)
        ods=[]
        for c in verified.values():
            if c['equipment_type']!='VRF_OUTDOOR':continue
            ratio=total/c['nominal_cooling_kw']
            ok=c['nominal_cooling_kw']>=system['sizing_peak']['total_kw'] and c['connection_ratio_min']<=ratio<=c['connection_ratio_max'] and count<=c['max_idu_count']
            ods.append({'model':c['model'],'nominal_cooling_kw':c['nominal_cooling_kw'],'connection_ratio':ratio,'passes_nominal_checks':ok})
        possible=sorted([x for x in ods if x['passes_nominal_checks']],key=lambda x:x['nominal_cooling_kw'])
        if not possible:raise ValueError(f'{sid}:無可成立的名義配置')
        layout.append(('OU-'+floor,possible[0]['model'],1,[x for x in system['room_ids'] if any(x in a[3] for a in layout)],'室外機'))
        layouts[sid]=layout;nominal_comparisons[sid]={'rooms':comparisons,'outdoors':ods}
    configurations=[];assessments=[]
    for e in p['equipment']:
        if e['category']=='AC':
            config=[]
            for eid,model,qty,rids,role in layouts[e['system_id']]:
                n=dict(normalized[model]);n.update(equipment_id=eid,quantity=qty,room_ids=rids,role=role)
                if n['review_status']=='Flagged':raise ValueError('不能推薦Flagged型號')
                config.append(n)
            e['configuration']=config;e['quantity']=sum(c['quantity'] for c in config if c['role']=='室內機')
            e['brand']='Hitachi';e['selected_model']=' / '.join(c['model'] for c in config)
            e['selection_status']='有條件候選';e['status']='暫定配置';e['reason']='按負荷及服務分區配置；同工況性能與室內外機搭配核對後定案。'
            outdoor=next(c for c in config if c['role']=='室外機');indoor=[c for c in config if c['role']=='室內機']
            indoor_cap=sum(c['nominal_cooling_kw']*c['quantity'] for c in indoor)
            connection=indoor_cap/outdoor['nominal_cooling_kw']
            e['connection_ratio']=connection;e['outdoor_capacity_ratio']=outdoor['nominal_cooling_kw']/e['required_cooling_kw']
            e['selection_notes']=['衛生間只設排風，不接空調回風；原系統負荷保留其小量負荷作容量餘量。',f'室內總標稱冷量{indoor_cap:.2f}kW；連接率{connection:.1%}僅為計算值，尚非原廠搭配核准。']
            configurations.extend(config)
            s=next(s for s in result['systems'] if s['system_id']==e['system_id'])
            requirement={'equipment_type':'dx_unit','total_kw':s['sizing_peak']['total_kw'],'sensible_kw':s['sizing_sensible_peak_kw'],
                'airflow_ls':s['sizing_sensible_peak_kw']*1000/(1.2*1.006*11),'esp_pa':0,'has_sf':True,'conditions':{'indoor_db_c':23,'indoor_wb_c':wet_bulb(23,.55),'outdoor_db_c':34},
                'conditions_reference':'23°C/55%RH；初選送風12°C、密度1.2kg/m³；壁掛不接外風管ESP=0Pa'}
            # 只供有條件候選原因整理，未確認的設計風量/ESP不得用零通過嚴格篩選。
            actual_candidates=[dict(model=c['model'],equipment_type='dx_unit',review_status='PendingReview',
                total_kw=c['nominal_cooling_kw'],performance_source=sources[c['source_id']]['url'],
                conditions={'indoor_db_c':27,'indoor_wb_c':19,'outdoor_db_c':35}) for c in verified.values() if c['equipment_type']=='VRF_OUTDOOR']
            assessments.append({'system_id':e['system_id'],'requirement':requirement,'assessment':assess_candidates(requirement,actual_candidates),
                'recommended_provisional':outdoor['model'],'reason':'同品牌系列、分區需要與標稱容量初選；額定點未驗證不得標示合格。',
                'nominal_comparisons':nominal_comparisons[e['system_id']],
                'alternatives':[x for x in nominal_comparisons[e['system_id']]['outdoors'] if x['passes_nominal_checks'] and x['model']!=outdoor['model']][:2],
                'rejected':[dict(x,reason='名義容量、連接率或接機數不滿足') for x in nominal_comparisons[e['system_id']]['outdoors'] if not x['passes_nominal_checks']]})
        elif e['category']=='TEF':
            e.update(quantity=1,status='獨立排風配置',selection_status='待工作點選型',reason='按獨立衛生間設1台；型號按原廠風量／靜壓工作點初選。',configuration=[])
            n=dict(next(x for x in normalized.values() if x.get('id')=='SYSTEMAIR-K125'))
            n.update(equipment_id=e['id'].replace('-REQ',''),quantity=1,room_ids=e['room_ids'],role='排風機')
            e.update(configuration=[n],brand=n['brand'],selected_model=n['model'],required_esp_pa=75)
            configurations.append(n)
            duty=n['published_operating_point']
            req={'equipment_type':'fan','airflow_ls':e['required_airflow_ls'],'esp_pa':75,'has_sf':False,
                 'conditions':{'air_temperature_c':23,'air_density_kg_m3':1.2},'conditions_reference':'排風支管及格柵初選阻力75Pa，按路由重算'}
            c={'model':n['model'],'equipment_type':'fan','review_status':'PendingReview','performance_source':n['source_url'],
               'airflow_ls':duty['airflow_m3h']/3.6,'esp_pa':duty['static_pressure_pa'],'speed_rpm':duty['rpm'],
               'operating_point_id':'10V','operating_point_source':n['source_url'],
               'performance_point_ids':{k:'10V' for k in ['airflow_ls','esp_pa','speed_rpm']}}
            assessments.append({'system_id':e['id'],'requirement':req,'assessment':assess_candidates(req,[c]),'recommended_provisional':n['model'],
                'reason':'原廠已發布同點風量及靜壓，但本工程所需轉速工作點未確認','alternatives':[],'rejected':[]})
        else:
            e.update(quantity=1,required_cooling_kw=p['air_treatment']['sizing_coil']['total_kw'],status='新風處理機組配置',selection_status='待盤管選型',
                reason='3312m³/h、冷卻除濕後再熱至室內中性工況；原廠盤管工作點選型。',configuration=[])
            n=dict(next(x for x in normalized.values() if x.get('id')=='SYSTEMAIR-GENIOX'))
            n.update(equipment_id='FAU-ALL',quantity=1,room_ids=e['room_ids'],role='新風處理機')
            e.update(configuration=[n],brand=n['brand'],selected_model=n['model'],required_esp_pa=150)
            configurations.append(n)
            state=p['air_treatment']['coil_outlet'];coil=p['air_treatment']['sizing_coil']
            req={'equipment_type':'fresh_air_unit','airflow_ls':920,'esp_pa':150,'total_kw':coil['total_kw'],'sensible_kw':coil['sensible_kw'],'has_sf':True,
                'conditions':{'entering_air_db_c':34,'entering_air_wb_c':28,'leaving_air_db_c':state['db_c'],'leaving_air_wb_c':wet_bulb(state['db_c'],state['rh_fraction'])},
                'conditions_reference':'盤管計算工況；外静壓150Pa為路由前情境'}
            cs=[{'model':x['model'],'equipment_type':'fresh_air_unit','review_status':'PendingReview','performance_source':x['source_url']} for x in normalized.values() if x.get('equipment_type')=='OUTDOOR_AIR_PROCESSOR']
            assessments.append({'system_id':e['id'],'requirement':req,'assessment':assess_candidates(req,cs),'recommended_provisional':n['model'],
                'reason':'系列風量範圍涵蓋需求，盤管及尺寸待原廠選型','alternatives':[],
                'rejected':[{'model':x['model'],'reason':x['reason']} for x in normalized.values() if x.get('status')=='RejectedForCurrentDuty']})
    p['selection_plan']=assessments
    p['configuration']=configurations
    p['internal_review']=[
        {'id':'D01','item':'冷源與新風供應邊界','adopted':'分層DX／VRF，自設全新風冷卻除濕及再熱','impact':'如物業提供預處理新風或冰水，重選新風機組及冷源。'},
        {'id':'D02','item':'設備配置及型錄性能','adopted':f"{sum(c['quantity'] for c in configurations if c['role']=='室內機')}台室內機、3台室外機，2台衛生間風機，1台新風處理機；候選型號見設備表",'impact':'Hitachi系列與具體地區版本配對、實際顯潛熱及最低調節能力須原廠選型確認。'},
        {'id':'D03','item':'建築與運行輸入','adopted':'沿用本工程房間面積、3m淨高、人數及運行時表','impact':'圖紙或使用條件改變時重算負荷，來源與假設不轉為現場事實。'}]
    p['internal_review'].append({'id':'A01','item':'新風盤管工況','adopted':';'.join(p['air_treatment']['assumptions']),'impact':'含SF盤管59.61kW；再熱9.13kW，不扣減末端38.83kW，不能把再熱當另一份冷負荷。'})
    p['internal_review'].append({'id':'A02','item':'送風量與靜壓初選','adopted':'每房最多3台；與最佳容量匹配差不超過需求10%視同級，再以台數少優先，屬本工程政策非ASHRAE標準。末端送風12°C、室內23°C為初選情境；按Qs/(ρCpΔT)核對名義高速風量。壁掛ESP0Pa；排風75Pa、新風150Pa為路由前阻力情境。','impact':'容量過大及最低調節能力仍須核對；路由與原廠工作點確定後重算。'})
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'design_package.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    print('selected package built')

if __name__=='__main__':main()
