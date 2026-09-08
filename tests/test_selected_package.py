import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('selected_package',ROOT/'scripts/build_selected_package.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class NominalAirflowTests(unittest.TestCase):
    def test_similar_capacity_prefers_fewer_units(self):
        candidates=[dict(model='small',equipment_type='VRF_INDOOR',nominal_cooling_kw=2.2,high_speed_airflow_m3h=588),
                    dict(model='large',equipment_type='VRF_INDOOR',nominal_cooling_kw=7.1,high_speed_airflow_m3h=1200)]
        accepted,_=builder.room_options(5.21249,4.398,candidates)
        self.assertEqual((accepted[0]['model'],accepted[0]['quantity']),('large',1))

    def test_capacity_only_cannot_pass_airflow(self):
        candidates=[dict(model='small',equipment_type='VRF_INDOOR',nominal_cooling_kw=5.6,high_speed_airflow_m3h=972),
                    dict(model='large',equipment_type='VRF_INDOOR',nominal_cooling_kw=7.1,high_speed_airflow_m3h=1200)]
        accepted,rejected=builder.room_options(15.15,12.78,candidates)
        self.assertEqual(accepted[0]['model'],'large')
        self.assertEqual(accepted[0]['quantity'],3)
        self.assertTrue(all(x['nominal_airflow_ls']>=x['required_airflow_ls'] for x in accepted))
        self.assertEqual(rejected[0]['model'],'small')
        self.assertIn('名義風量不足',rejected[0]['reasons'][0])
