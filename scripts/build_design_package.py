"""所有修訂成果共用的設計資料及設備需求記錄。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/revised_20260908'

def build_package(inp, result):
    inputs = {r['room_id']: r for r in inp['rooms']}
    result_ids = [r['room_id'] for r in result['rooms']]
    system_ids = [s['system_id'] for s in result['systems']]
    if len(inputs) != len(inp['rooms']) or len(set(result_ids)) != len(result_ids):
        raise ValueError('重複房間編號')
    if set(inputs) != set(result_ids):
        raise ValueError('輸入與結果房間不一致')
    if len(system_ids) != len(set(system_ids)) or not system_ids:
        raise ValueError('系統編號重複或缺失')
    for r in result['rooms']:
        if r['system_id'] not in system_ids or r['system_id'] != inputs[r['room_id']]['system_id']:
            raise ValueError('房間系統關係不一致')
    for s in result['systems']:
        if not any(r['system_id'] == s['system_id'] for r in result['rooms']):
            raise ValueError('系統沒有服務房間')
        from math import isclose
        if not isclose(s['sizing_peak']['total_kw'], s['raw_peak']['total_kw']*1.15, rel_tol=1e-9):
            raise ValueError('系統安全係數須只套用一次1.15')
    equipment = []
    for s in result['systems']:
        suffix = s['system_id'].removeprefix('DX-')
        members = [r['room_id'] for r in result['rooms'] if r['system_id'] == s['system_id']]
        equipment.append(dict(id=f'AC-REQ-{suffix}', system_id=s['system_id'], room_ids=members,
            category='AC', quantity=None, required_cooling_kw=s['sizing_peak']['total_kw'], required_airflow_ls=None,
            status='需求記錄，非已選設備', reason='室內外機配置及台數待確定；系統負荷不等同單機容量。'))
    exhaust_floors = [r['room_id'].split('-')[0] for r in result['rooms'] if inputs[r['room_id']]['exhaust_ach'] > 0]
    for r in result['rooms']:
        if inputs[r['room_id']]['exhaust_ach'] > 0:
            floor=r['room_id'].split('-')[0]
            suffix = r['room_id'] if exhaust_floors.count(floor)>1 else floor
            equipment.append(dict(id='TEF-REQ-'+suffix, system_id=r['system_id'],
                room_ids=[r['room_id']], category='TEF', quantity=None, required_cooling_kw=None,
                required_airflow_ls=r['ventilation']['exhaust_ls'], status='需求記錄，非已選設備',
                reason='獨立排風需求；台數、風管路徑及靜壓待確定。'))
    equipment.append(dict(id='FAU-REQ-ALL', system_id='FAU-SYSTEM',
        room_ids=[r['room_id'] for r in result['rooms'] if r['ventilation']['fresh_air_ls'] > 0],
        category='FAU', quantity=None, required_cooling_kw=None,
        required_airflow_ls=sum(s['fresh_air_ls'] for s in result['systems']),
        status='需求記錄，非已選設備', reason='新風供應責任、台數及盤管進出風工況待確定；盤管冷量未計算。'))
    return dict(input=inp, result=result, equipment=equipment, version='2026-09-08-r2')

if __name__ == '__main__':
    inp = json.loads((ROOT/'data/local/trial_2024_06_03_retail_input.json').read_text(encoding='utf-8'))
    result = json.loads((ROOT/'outputs/review/retail_trial_result.json').read_text(encoding='utf-8'))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'design_package.json').write_text(json.dumps(build_package(inp,result), ensure_ascii=False, indent=2), encoding='utf-8')
