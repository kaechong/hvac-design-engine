"""可追溯的候選評估；不作無來源工況修正，不自動拼接額定性能。"""
from copy import deepcopy
from .core import InputError, equipment_conditions, number, select_equipment


def assess_candidates(requirement, candidates):
    """傳回 recommended / alternatives / conditional / rejected。

    每筆含 candidate、eligible、reasons。性能採單一 operating_point_id；
    performance_point_ids 逐欄追溯至同一點。quantity 為同型機數量（預設1），
    核心性能欄須是整組能力，不在此函式自動倍乘額定值。
    """
    result = dict(recommended=None, alternatives=[], conditional=[], rejected=[])
    validation = select_equipment(requirement, [])
    if validation['issues']:
        result['issues'] = validation['issues']
        return result
    if not isinstance(candidates, list):
        result['issues'] = ['candidates 必須為列表']
        return result
    if requirement.get('maximum_capacity_ratio') is not None:
        try:
            number(requirement['maximum_capacity_ratio'], 'maximum_capacity_ratio', 1)
        except InputError as exc:
            result['issues'] = [str(exc)]
            return result
    kind, conditions = equipment_conditions(requirement)
    fields = ['airflow_ls', 'esp_pa'] if kind == 'fan' else ['total_kw', 'sensible_kw', 'airflow_ls', 'esp_pa']
    accepted = []
    for original in candidates:
        if not isinstance(original, dict):
            result['rejected'].append(dict(candidate=original, eligible=False, reasons=['候選須為物件']))
            continue
        c = deepcopy(original)
        reasons, reject = [], False
        status = c.get('review_status')
        if status == 'Flagged':
            reasons.append('資料已標記異常，禁止自動採用')
            reject = True
        elif status != 'Confirmed':
            reasons.append('資料尚未確認')
        if c.get('equipment_type') != kind:
            reasons.append('設備類型不一致')
            reject = True
        if not c.get('model') or not c.get('performance_source'):
            reasons.append('缺型號或性能來源')
        point = c.get('operating_point_id')
        mapping = c.get('performance_point_ids', {})
        if not point or any(not mapping.get(f) for f in fields):
            reasons.append('缺完整同一運行點性能追溯')
        elif any(mapping[f] != point for f in fields):
            reasons.append('性能來自不同運行點，禁止拼接')
            reject = True
        try:
            _, actual_conditions = equipment_conditions(c)
            if actual_conditions != conditions:
                reasons.append('工況不一致，不自動修正')
                reject = True
        except InputError as exc:
            reasons.append(str(exc))
        for f in fields:
            try:
                value = number(c.get(f), f)
                if value < requirement[f]:
                    reasons.append(f'{f} 性能不足')
                    reject = True
            except InputError as exc:
                reasons.append(str(exc))
        if kind != 'fan' and all(isinstance(c.get(k), (int, float)) for k in ('sensible_kw', 'total_kw')):
            if c['sensible_kw'] > c['total_kw']:
                reasons.append('顯熱高於全熱')
                reject = True
            # 潛熱亦須獨立滿足，不能僅以總冷量及顯熱下限判定。
            if c['total_kw'] - c['sensible_kw'] < requirement['total_kw'] - requirement['sensible_kw'] - 1e-9:
                reasons.append('潛熱能力不足')
                reject = True
            ceiling = requirement.get('maximum_capacity_ratio')
            if ceiling is not None and requirement['total_kw'] > 0 and c['total_kw'] / requirement['total_kw'] > ceiling:
                reasons.append('容量超過本項目允許匹配比例')
                reject = True
        extras = []
        if kind == 'fan':
            extras = ['speed_rpm', 'operating_point_source']
            if not point or mapping.get('speed_rpm') != point:
                reasons.append('轉速缺同一運行點依據')
        elif kind == 'chilled_water_fcu':
            extras = ['water_flow_ls', 'water_pressure_drop_kpa']
            for f in extras:
                if mapping.get(f) != point or not point:
                    reasons.append(f'{f} 缺同一運行點依據')
        for f in extras:
            if c.get(f) is None or c.get(f) == '':
                reasons.append(f'缺 {f}')
            elif f != 'operating_point_source':
                try:
                    number(c[f], f, 0)
                except InputError as exc:
                    reasons.append(str(exc))
                    reject = True
        if kind == 'dx_unit':
            pair = c.get('pairing_evidence') or {}
            keys = ['source', 'indoor_model', 'outdoor_model', 'connection_ratio', 'min_ratio', 'max_ratio']
            if any(pair.get(k) is None or pair.get(k) == '' for k in keys):
                reasons.append('缺原廠室內外機配對及連接率依據')
            else:
                try:
                    lo, actual, hi = [number(pair[k], k) for k in ('min_ratio', 'connection_ratio', 'max_ratio')]
                    if not lo <= actual <= hi or pair['indoor_model'] != c['model']:
                        reasons.append('室內外機配對或連接率不符合原廠限制')
                        reject = True
                except InputError as exc:
                    reasons.append(str(exc))
                    reject = True
        quantity = c.get('quantity', 1)
        if type(quantity) is not int or quantity < 1:
            reasons.append('設備數量須為正整數')
            reject = True
        # 核心再次確認，策略不放寬既有嚴格要求。
        core = select_equipment(requirement, [c])
        if not core['eligible']:
            reasons.extend(x for x in core['issues'] if x not in reasons)
        item = dict(candidate=c, eligible=not reasons, reasons=reasons)
        if reject:
            result['rejected'].append(item)
        elif reasons:
            result['conditional'].append(item)
        else:
            accepted.append(item)
    # 只有所有合格候選都有該數據才比較；不把缺值當作零或排名優勢。
    optional = [k for k in ('minimum_capacity_kw', 'installation_score')
                if accepted and all(type(x['candidate'].get(k)) in (int, float) and x['candidate'][k] >= 0 for x in accepted)]
    primary = 'airflow_ls' if kind == 'fan' else 'total_kw'
    def rank(item):
        c = item['candidate']
        values = [c[primary] - requirement[primary]]
        if 'minimum_capacity_kw' in optional:
            values.append(c['minimum_capacity_kw'])
        values.append(c.get('quantity', 1))
        if 'installation_score' in optional:
            values.append(c['installation_score'])
        return (*values, str(c['model']))
    accepted.sort(key=rank)
    unique, seen = [], set()
    for item in accepted:
        c = item['candidate']
        identity = (c.get('brand'), c['model'], c.get('quantity', 1), str(c.get('pairing_evidence')))
        if identity not in seen:
            seen.add(identity)
            item['reasons'] = ['工況及性能核對通過；按容量匹配、可比調節能力及配置排序']
            unique.append(item)
    if unique:
        result['recommended'], result['alternatives'] = unique[0], unique[1:3]
    return result
