"""純 stdlib、顯式輸入；所有冷負荷採 kW，氣象不設公司預設值。"""
import math
from copy import deepcopy
from datetime import datetime

METHOD = 'explicit-hourly-components-v1'


class InputError(ValueError):
    """輸入缺失、無效或與計算契約不一致。"""


def number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f'{name}: 必須提供數值')
    if not math.isfinite(value) or (minimum is not None and value < minimum):
        raise InputError(f'{name}: 非有限值或低於允許下限')
    return float(value)


def required(data, key):
    if not isinstance(data, dict) or key not in data or data[key] is None:
        raise InputError(f'缺少 {key}')
    return data[key]


def vector(data, key, count):
    values = required(data, key)
    if not isinstance(values, list) or len(values) != count:
        raise InputError(f'{key}: 逐時陣列長度必須為 {count}')
    return [number(v, key) for v in values]


def validate_times(keys):
    if not isinstance(keys, list) or len(keys) < 24:
        raise InputError('time_keys: 最少一個完整24小時設計日')
    parsed = []
    for key in keys:
        try:
            value = datetime.strptime(key, '%Y-%m-%dT%H:%M')
            if value.strftime('%Y-%m-%dT%H:%M') != key or value.minute != 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise InputError('time_keys: 必須為 YYYY-MM-DDTHH:00') from None
        parsed.append(value)
    if parsed != sorted(set(parsed)):
        raise InputError('time_keys: 重複或未按時間排序')
    dates = {t.date() for t in parsed}
    if any({t.hour for t in parsed if t.date() == day} != set(range(24)) for day in dates):
        raise InputError('time_keys: 每個設計日必須完整包含00至23時')
    return keys


def cfm_to_ls(cfm):
    return number(cfm, 'cfm') * 0.028316846592 * 1000 / 60


def ventilation(room):
    needs = required(room, 'needs_fresh_air')
    if type(needs) is not bool:
        raise InputError('needs_fresh_air 必須明確為 true/false')
    people = number(required(room, 'people'), 'people')
    volume = number(required(room, 'volume_m3'), 'volume_m3')
    ach = number(required(room, 'exhaust_ach'), 'exhaust_ach')
    return {'fresh_air_ls': people * 10 if needs else 0.0,
            'fresh_air_m3h': people * 36 if needs else 0.0,
            'exhaust_m3h': volume * ach, 'exhaust_ls': volume * ach / 3.6,
            'has_sf': False}


def apply_safety_factor(load):
    if required(load, 'has_sf') is not False:
        raise InputError('負荷已含SF或SF狀態不明，禁止再次放大')
    s = number(required(load, 'sensible_kw'), 'sensible_kw')
    l = number(required(load, 'latent_kw'), 'latent_kw')
    return {'sensible_kw': s * 1.15, 'latent_kw': l * 1.15,
            'total_kw': (s + l) * 1.15, 'has_sf': True, 'sf': 1.15}


def moist_air_state(db_c, rh_fraction, pressure_pa):
    """液態水 Buck 飽和蒸氣壓近似，限0至50°C；RH為0..1。"""
    t = number(db_c, 'db_c')
    rh = number(rh_fraction, 'rh_fraction')
    p = number(pressure_pa, 'pressure_pa', 1)
    if t > 50 or rh > 1:
        raise InputError('濕空氣近似適用0..50°C、RH 0..1')
    pv = rh * 611.21 * math.exp((18.678 - t / 234.5) * (t / (257.14 + t)))
    if pv >= p:
        raise InputError('水蒸氣分壓須小於總壓')
    w = 0.621945 * pv / (p - pv)
    return {'db_c': t, 'rh_fraction': rh, 'pressure_pa': p,
            'humidity_ratio_kgkg': w, 'enthalpy_kjkg': 1.006 * t + w * (2501 + 1.86 * t),
            'specific_volume_m3kg_da': 287.042 * (t + 273.15) * (1 + 1.607858 * w) / p}


def calculate_pau(inlet, outlet, airflow_ls):
    """風量指入口實際體積；結果為未加SF盤管冷量，不自動加到房間。"""
    a, b = [moist_air_state(required(x, 'db_c'), required(x, 'rh_fraction'),
                           required(x, 'pressure_pa')) for x in (inlet, outlet)]
    if not math.isclose(a['pressure_pa'], b['pressure_pa'], abs_tol=1e-6):
        raise InputError('PAU進出風狀態須採同一氣壓基準')
    flow = number(airflow_ls, 'airflow_ls')
    if a['db_c'] < b['db_c'] or a['humidity_ratio_kgkg'] < b['humidity_ratio_kgkg']:
        raise InputError('此PAU模組限冷卻除濕，不含加熱／加濕')
    mass = flow / 1000 / a['specific_volume_m3kg_da']
    total = mass * (a['enthalpy_kjkg'] - b['enthalpy_kjkg'])
    sensible = mass * (1.006 + 1.86 * a['humidity_ratio_kgkg']) * (a['db_c'] - b['db_c'])
    return {'sensible_kw': sensible, 'latent_kw': max(0.0, total - sensible),
            'total_kw': total, 'has_sf': False, 'airflow_ls': flow,
            'dry_air_mass_kgs': mass, 'inlet': a, 'outlet': b}


def surface_load(surface, time_keys):
    """顯式UAΔT或CLTD、日射輻照及係數。限非負冷負荷，非動態傳熱求解器。"""
    required(surface, 'boundary')
    if 'has_sf' in surface and surface['has_sf'] is not False:
        raise InputError('表面負荷不得含SF或未知SF狀態')
    if surface['boundary'] not in ('external', 'adjacent_conditioned', 'adjacent_unconditioned'):
        raise InputError('表面邊界未知，不得視為內牆')
    if required(surface, 'time_keys') != time_keys:
        raise InputError('表面time_keys與項目不一致')
    n = len(time_keys)
    area = number(required(surface, 'area_m2'), 'area_m2')
    u = number(required(surface, 'u_w_m2k'), 'u_w_m2k')
    dt = vector(surface, 'delta_t_k', n)
    result = [area * u * t / 1000 for t in dt]
    if 'solar' not in surface:
        raise InputError('solar須明示為null（無日射）或完整日射資料')
    solar = surface['solar']
    if solar is not None:
        if not isinstance(solar, dict) or not solar.get('orientation'):
            raise InputError('日射必須有明確方位')
        irradiance = vector(solar, 'irradiance_w_m2', n)
        coefficients = vector(solar, 'effective_coefficients', n)
        result = [q + area * i * c / 1000 for q, i, c in zip(result, irradiance, coefficients)]
    return {'name': required(surface, 'name'), 'sensible_kw': result,
            'latent_kw': [0.0] * n, 'input_basis': deepcopy(surface)}


def internal_gains(payload, time_keys):
    """顯式內熱源和排程，無用途／人均散熱預設。"""
    if required(payload, 'time_keys') != time_keys:
        raise InputError('內熱源time_keys與項目不一致')
    if 'has_sf' in payload and payload['has_sf'] is not False:
        raise InputError('內熱源不得含SF或未知SF狀態')
    n = len(time_keys)
    values = {key: number(required(payload, key), key) for key in
              ('people', 'person_sensible_w', 'person_latent_w', 'lighting_w',
               'equipment_sensible_w', 'equipment_latent_w')}
    schedules = {key: vector(payload, key, n) for key in
                 ('people_schedule', 'lighting_schedule', 'equipment_schedule')}
    if any(x > 1 for v in schedules.values() for x in v):
        raise InputError('內熱源排程須介於0與1')
    sensible, latent = [], []
    for ps, ls, es in zip(schedules['people_schedule'], schedules['lighting_schedule'],
                          schedules['equipment_schedule']):
        sensible.append((values['people']*values['person_sensible_w']*ps +
                         values['lighting_w']*ls + values['equipment_sensible_w']*es)/1000)
        latent.append((values['people']*values['person_latent_w']*ps +
                       values['equipment_latent_w']*es)/1000)
    return {'name': required(payload, 'name'), 'sensible_kw': sensible,
            'latent_kw': latent, 'input_basis': deepcopy(payload)}


def summarize(keys, sensible, latent):
    for s, l in zip(sensible, latent):
        number(s + l, '彙總冷負荷')
    hourly = [{'time_key': k, 'sensible_kw': s, 'latent_kw': l,
               'total_kw': s+l, 'has_sf': False} for k, s, l in zip(keys, sensible, latent)]
    raw = dict(max(hourly, key=lambda row: row['total_kw']))
    sizing = apply_safety_factor(raw)
    sizing['time_key'] = raw['time_key']
    # 同一設備必須亦能滿足另一時刻的最大顯熱，保留獨立需求。
    return {'raw_hourly': hourly, 'raw_peak': raw, 'sizing_peak': sizing,
            'raw_sensible_peak': dict(max(hourly, key=lambda row: row['sensible_kw'])),
            'sizing_sensible_peak_kw': max(sensible)*1.15}


def calculate_project(payload):
    if not isinstance(payload, dict):
        raise InputError('項目輸入必須為JSON物件')
    if payload.get('schema_version') != 1:
        raise InputError('只支援 schema_version=1')
    keys = validate_times(required(payload, 'time_keys'))
    rooms = required(payload, 'rooms')
    if not isinstance(rooms, list) or not rooms:
        raise InputError('rooms 必須為非空列表')
    n = len(keys)
    results, sums, seen = [], {}, set()
    for room in rooms:
        rid = required(room, 'room_id')
        sid = required(room, 'system_id')
        if not isinstance(rid, str) or not rid or rid in seen or not isinstance(sid, str) or not sid:
            raise InputError('房間編號須唯一且房間／系統編號不得為空')
        seen.add(rid)
        if required(room, 'time_keys') != keys:
            raise InputError(f'{rid}: time_keys與項目不一致（包含設計日／月份）')
        if required(room, 'has_sf') is not False:
            raise InputError(f'{rid}: 必須輸入未加SF負荷')
        comps = required(room, 'components')
        if not isinstance(comps, list):
            raise InputError(f'{rid}: components必須為列表')
        surfaces = room.get('surfaces', [])
        if not isinstance(surfaces, list):
            raise InputError(f'{rid}: surfaces必須為列表，無表面用空列表')
        comps = deepcopy(comps) + [surface_load(s, keys) for s in surfaces]
        if 'internal_gains' in room:
            comps.append(internal_gains(room['internal_gains'], keys))
        if not comps:
            raise InputError(f'{rid}: 需明確逐時顯熱及潛熱分項，零亦須明示')
        sensible, latent = [0.0]*n, [0.0]*n
        component_names = set()
        for component in comps:
            name = required(component, 'name')
            if not isinstance(name, str) or not name or name in component_names:
                raise InputError(f'{rid}: 分項名稱不得重複或留空')
            component_names.add(name)
            if 'has_sf' in component and component['has_sf'] is not False:
                raise InputError('分項不得含SF')
            sensible = [a+b for a,b in zip(sensible, vector(component, 'sensible_kw', n))]
            latent = [a+b for a,b in zip(latent, vector(component, 'latent_kw', n))]
        vent = ventilation(room)
        row = {'room_id': rid, 'system_id': sid, 'ventilation': vent,
               'components': comps, **summarize(keys, sensible, latent)}
        results.append(row)
        group = sums.setdefault(sid, {'s': [0.0]*n, 'l': [0.0]*n, 'rooms': [], 'fresh': 0.0, 'exhaust': 0.0})
        group['s'] = [a+b for a,b in zip(group['s'], sensible)]
        group['l'] = [a+b for a,b in zip(group['l'], latent)]
        group['rooms'].append(rid)
        group['fresh'] += vent['fresh_air_ls']
        group['exhaust'] += vent['exhaust_ls']
    systems = [{'system_id': sid, 'room_ids': v['rooms'],
                'fresh_air_ls': v['fresh'], 'exhaust_ls': v['exhaust'],
                **summarize(keys, v['s'], v['l'])} for sid,v in sums.items()]
    return {'schema_version': 1, 'method': METHOD, 'status': 'CalculationOnly',
            'project_id': payload.get('project_id'),
            'source_classification': payload.get('source_classification', 'unspecified'),
            'source_notice': payload.get('notice'),
            'time_keys': keys, 'rooms': results, 'systems': systems,
            'limitations': ['顯式逐時負荷基礎，非Carrier HAP或完整動態熱模型',
                            '輸入來源、負荷完整性、通風平衡與工程適用性仍須覆核',
                            '房間及系統SF結果為獨立選型視圖，系統只彙總未加SF分項']}


def equipment_conditions(data):
    kind = required(data, 'equipment_type')
    schemas = {
        'chilled_water_fcu': ('entering_air_db_c', 'entering_air_wb_c', 'entering_water_c', 'leaving_water_c'),
        'dx_unit': ('indoor_db_c', 'indoor_wb_c', 'outdoor_db_c'),
        'fan': ('air_temperature_c', 'air_density_kg_m3'),
    }
    if not isinstance(kind, str) or kind not in schemas:
        raise InputError('equipment_type不支援或未明確')
    conditions = required(data, 'conditions')
    if not isinstance(conditions, dict) or set(conditions) != set(schemas[kind]):
        raise InputError(f'{kind}: 工況必須明確提供 {schemas[kind]}，不接受未知欄位')
    values = {k: number(v, k, minimum=None) for k,v in conditions.items()}
    for key, value in values.items():
        if key.endswith('_c') and not -50 <= value <= 100:
            raise InputError(f'{key}: 超出本介面支援溫度範圍-50..100°C')
    if kind == 'chilled_water_fcu':
        if values['entering_air_wb_c'] > values['entering_air_db_c']:
            raise InputError('進風濕球不得高於乾球')
        if not 0 < values['entering_water_c'] < values['leaving_water_c'] < 100:
            raise InputError('本水盤管篩選限0..100°C液態水冷卻，出水須高於入水')
    elif kind == 'dx_unit' and values['indoor_wb_c'] > values['indoor_db_c']:
        raise InputError('室內濕球不得高於乾球')
    elif kind == 'fan' and not 0 < values['air_density_kg_m3'] <= 10:
        raise InputError('風機空氣密度須大於0且不超過本介面10kg/m³上限')
    return kind, values


def select_equipment(requirement, candidates):
    """精確工況匹配的候選篩選；缺資料不選型、不虛構型號或修正曲線。"""
    issues, eligible = [], []
    try:
        kind, conditions = equipment_conditions(requirement)
        fields = ('airflow_ls', 'esp_pa') if kind == 'fan' else ('total_kw', 'sensible_kw', 'airflow_ls', 'esp_pa')
        demand = {k: number(required(requirement,k), k) for k in fields}
        reference = required(requirement, 'conditions_reference')
        if not isinstance(reference, str) or not reference.strip():
            raise InputError('缺少明確設計工況及其來源')
        if required(requirement, 'has_sf') is not (kind != 'fan'):
            raise InputError('冷量選型須has_sf=true；風機風量／靜壓須has_sf=false')
        if kind != 'fan' and demand['sensible_kw'] > demand['total_kw']:
            raise InputError('顯熱需求不可大於全熱')
        if not isinstance(candidates, list):
            raise InputError('candidates必須為列表')
    except InputError as exc:
        return {'status': 'NeedsReview', 'eligible': [], 'issues': [str(exc)]}
    for candidate in candidates:
        try:
            model = required(candidate, 'model')
            source = required(candidate, 'performance_source')
            if not isinstance(model, str) or not model.strip() or not isinstance(source,str) or not source.strip():
                raise InputError('型號或性能來源缺失')
            candidate_kind, candidate_conditions = equipment_conditions(candidate)
            if candidate_kind != kind:
                raise InputError(f'{model}: 設備類型不一致')
            performance = {k:number(required(candidate,k),k) for k in fields}
            if kind != 'fan' and performance['sensible_kw'] > performance['total_kw']:
                raise InputError('設備顯熱不可大於全熱')
            if candidate_conditions != conditions:
                issues.append(f'{model}: 工況不一致，不自動修正')
                continue
            if all(performance[k] >= demand[k] for k in fields):
                eligible.append(deepcopy(candidate))
            else:
                issues.append(f'{model}: 性能不足')
        except InputError as exc:
            issues.append(str(exc))
    return {'status': 'CandidatesAvailable' if eligible else 'NeedsReview',
            'eligible': eligible, 'issues': issues}
