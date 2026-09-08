import unittest
from copy import deepcopy
from hvac_engine.selection import assess_candidates
from hvac_engine.core import select_equipment


def fixture(kind='fan'):
    conditions = {'air_temperature_c': 23, 'air_density_kg_m3': 1.2}
    if kind == 'dx_unit':
        conditions = {'indoor_db_c': 23, 'indoor_wb_c': 17, 'outdoor_db_c': 34}
    elif kind == 'fresh_air_unit':
        conditions = {'entering_air_db_c': 34, 'entering_air_wb_c': 28,
                      'leaving_air_db_c': 16, 'leaving_air_wb_c': 15}
    elif kind == 'chilled_water_fcu':
        conditions = {'entering_air_db_c': 23, 'entering_air_wb_c': 17,
                      'entering_water_c': 7, 'leaving_water_c': 12}
    req = dict(equipment_type=kind, conditions=conditions, conditions_reference='設計基準',
               airflow_ls=100, esp_pa=50, has_sf=kind != 'fan')
    if kind != 'fan':
        req.update(total_kw=10, sensible_kw=7)
    c = dict(req, model='A', performance_source='原廠頁1', review_status='Confirmed',
             operating_point_id='P1', speed_rpm=900, operating_point_source='原廠曲線P1')
    c['performance_point_ids'] = {k: 'P1' for k in ['airflow_ls', 'esp_pa', 'total_kw', 'sensible_kw', 'water_flow_ls', 'water_pressure_drop_kpa', 'speed_rpm']}
    c.update(water_flow_ls=.3, water_pressure_drop_kpa=20)
    c['pairing_evidence'] = dict(source='原廠組合表', indoor_model='A', outdoor_model='OA', connection_ratio=1, min_ratio=.5, max_ratio=1.3)
    return req, c


class SelectionStrategyTests(unittest.TestCase):
    def test_supported_types_and_independent_pau(self):
        for kind in ('fan', 'dx_unit', 'chilled_water_fcu', 'fresh_air_unit'):
            req, c = fixture(kind)
            self.assertTrue(assess_candidates(req, [c])['recommended'])
        req, c = fixture('fresh_air_unit')
        c['conditions']['leaving_air_wb_c'] = 20
        self.assertFalse(select_equipment(req, [c])['eligible'])

    def test_status_and_missing_fields(self):
        req, c = fixture()
        for status, bucket in [('PendingReview', 'conditional'), ('Flagged', 'rejected')]:
            c['review_status'] = status
            self.assertEqual(len(assess_candidates(req, [c])[bucket]), 1)
        c['review_status'] = 'Confirmed'
        del c['esp_pa']
        self.assertEqual(len(assess_candidates(req, [c])['conditional']), 1)

    def test_mixed_points_and_conditions_rejected(self):
        req, c = fixture()
        c['performance_point_ids']['esp_pa'] = 'P2'
        self.assertEqual(len(assess_candidates(req, [c])['rejected']), 1)
        req, c = fixture()
        c['conditions'] = dict(c['conditions'], air_temperature_c=30)
        self.assertEqual(len(assess_candidates(req, [c])['rejected']), 1)

    def test_dx_latent_and_pairing(self):
        req, c = fixture('dx_unit')
        c['sensible_kw'] = 9
        self.assertEqual(len(assess_candidates(req, [c])['rejected']), 1)
        req, c = fixture('dx_unit')
        c['pairing_evidence']['connection_ratio'] = 1.5
        self.assertEqual(len(assess_candidates(req, [c])['rejected']), 1)
        del c['pairing_evidence']
        self.assertEqual(len(assess_candidates(req, [c])['conditional']), 1)

    def test_fcu_water_and_fan_speed_missing(self):
        for kind, key in [('chilled_water_fcu', 'water_flow_ls'), ('fan', 'speed_rpm')]:
            req, c = fixture(kind)
            del c[key]
            self.assertEqual(len(assess_candidates(req, [c])['conditional']), 1)

    def test_ranking_and_limit_without_price(self):
        req, c = fixture()
        candidates = []
        for i in range(5):
            x = deepcopy(c)
            x.update(model=str(i), airflow_ls=100+i, price_mop=5-i)
            candidates.append(x)
        result = assess_candidates(req, candidates[::-1])
        self.assertEqual(result['recommended']['candidate']['model'], '0')
        self.assertEqual(len(result['alternatives']), 2)
        self.assertEqual(candidates[0]['model'], '0')

    def test_oversize_and_invalid_requirement(self):
        req, c = fixture('dx_unit')
        req['maximum_capacity_ratio'] = 1.2
        c['total_kw'] = 15
        self.assertEqual(len(assess_candidates(req, [c])['rejected']), 1)
        req['has_sf'] = False
        self.assertTrue(assess_candidates(req, [c])['issues'])


if __name__ == '__main__':
    unittest.main()
