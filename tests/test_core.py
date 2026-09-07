import copy
import math
import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from hvac_engine import (calculate_project, InputError, ventilation,
                         apply_safety_factor, moist_air_state, calculate_pau,
                         cfm_to_ls, select_equipment, surface_load, internal_gains)


def sample():
    keys = [f'2026-07-21T{h:02d}:00' for h in range(24)]
    rooms = []
    for rid, hour in [('A', 10), ('B', 16)]:
        sensible = [1.0] * 24
        sensible[hour] = 10.0
        rooms.append({'room_id': rid, 'system_id': 'S1', 'time_keys': keys[:],
                      'needs_fresh_air': True, 'people': 5, 'volume_m3': 100,
                      'exhaust_ach': 0, 'has_sf': False,
                      'components': [{'name': 'synthetic', 'sensible_kw': sensible,
                                      'latent_kw': [0.5]*24}]})
    return {'schema_version': 1, 'time_keys': keys, 'rooms': rooms}


class CoreTests(unittest.TestCase):
    def test_internal_gains_explicit_schedules(self):
        p = sample()
        schedule = [0]*24
        schedule[11] = 1
        gains = {'name': 'explicit_internal', 'time_keys': p['time_keys'], 'people': 4,
                 'person_sensible_w': 70, 'person_latent_w': 50, 'lighting_w': 120,
                 'equipment_sensible_w': 200, 'equipment_latent_w': 100,
                 'people_schedule': schedule, 'lighting_schedule': schedule,
                 'equipment_schedule': schedule}
        r = internal_gains(gains, p['time_keys'])
        self.assertAlmostEqual(r['sensible_kw'][11], 0.6)
        self.assertAlmostEqual(r['latent_kw'][11], 0.3)
        self.assertEqual(r['sensible_kw'][10], 0)
        p['rooms'][0]['components'] = []
        p['rooms'][0]['internal_gains'] = gains
        self.assertEqual(calculate_project(p)['rooms'][0]['raw_peak']['time_key'], '2026-07-21T11:00')
        invalid = copy.deepcopy(gains)
        del invalid['person_latent_w']
        with self.assertRaises(InputError): internal_gains(invalid, p['time_keys'])
        invalid = copy.deepcopy(gains)
        invalid['people_schedule'][0] = 1.1
        with self.assertRaises(InputError): internal_gains(invalid, p['time_keys'])

    def test_coincident_peak(self):
        data = sample()
        result = calculate_project(data)
        system = result['systems'][0]
        self.assertEqual(system['raw_peak']['total_kw'], 12)
        self.assertEqual(system['raw_peak']['time_key'], '2026-07-21T10:00')
        self.assertAlmostEqual(system['sizing_peak']['total_kw'], 13.8)
        self.assertEqual(sum(r['raw_peak']['total_kw'] for r in result['rooms']), 21)
        self.assertEqual(data, sample(), '純函式不可修改輸入')

    def test_fresh_zero_missing_and_exhaust(self):
        room = sample()['rooms'][0]
        self.assertEqual(ventilation(room)['fresh_air_ls'], 50)
        room['needs_fresh_air'] = False
        room['exhaust_ach'] = 6
        self.assertEqual(ventilation(room)['fresh_air_ls'], 0)
        self.assertEqual(ventilation(room)['exhaust_m3h'], 600)
        del room['needs_fresh_air']
        with self.assertRaises(InputError): ventilation(room)
        room['needs_fresh_air'] = False
        del room['people']
        with self.assertRaises(InputError): ventilation(room)

    def test_nonfinite_negative_bool(self):
        for value in [float('nan'), float('inf'), -1, True, None]:
            p = sample()
            p['rooms'][0]['components'][0]['sensible_kw'][2] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                calculate_project(p)

    def test_sf_no_double(self):
        out = apply_safety_factor({'sensible_kw': 10, 'latent_kw': 2, 'has_sf': False})
        self.assertAlmostEqual(out['total_kw'], 13.8)
        with self.assertRaises(InputError): apply_safety_factor(out)
        p = sample()
        p['rooms'][0]['has_sf'] = True
        with self.assertRaises(InputError): calculate_project(p)

    def test_month_mismatch(self):
        p = sample()
        p['rooms'][1]['time_keys'] = [k.replace('-07-', '-08-') for k in p['time_keys']]
        with self.assertRaises(InputError): calculate_project(p)

    def test_missing_hour_and_array_alignment(self):
        p = sample()
        p['time_keys'].pop()
        with self.assertRaises(InputError): calculate_project(p)
        p = sample()
        p['rooms'][0]['components'][0]['latent_kw'].pop()
        with self.assertRaises(InputError): calculate_project(p)

    def test_multiple_design_days(self):
        p = sample()
        keys = p['time_keys'] + [k.replace('-07-', '-08-') for k in p['time_keys']]
        p['time_keys'] = keys
        for r in p['rooms']:
            r['time_keys'] = keys[:]
            for c in r['components']:
                c['sensible_kw'] *= 2
                c['latent_kw'] *= 2
        self.assertEqual(len(calculate_project(p)['systems'][0]['raw_hourly']), 48)

    def test_psychrometrics_and_pau(self):
        dry = moist_air_state(20, 0, 101325)
        self.assertEqual(dry['humidity_ratio_kgkg'], 0)
        self.assertAlmostEqual(dry['enthalpy_kjkg'], 20.12)
        inlet = {'db_c': 32, 'rh_fraction': 0.6, 'pressure_pa': 101325}
        outlet = {'db_c': 14, 'rh_fraction': 0.9, 'pressure_pa': 101325}
        r = calculate_pau(inlet, outlet, 100)
        self.assertGreater(r['latent_kw'], 0)
        self.assertAlmostEqual(r['total_kw'], r['sensible_kw']+r['latent_kw'])
        self.assertAlmostEqual(calculate_pau(inlet, outlet, 200)['total_kw'], 2*r['total_kw'])
        self.assertFalse(r['has_sf'])
        self.assertEqual(calculate_pau(inlet, inlet, 100)['total_kw'], 0)
        with self.assertRaises(InputError): calculate_pau(outlet, inlet, 100)
        self.assertAlmostEqual(cfm_to_ls(1000), 471.9474432)

    def test_equipment_requires_conditions(self):
        req = {'total_kw': 10, 'sensible_kw': 7, 'airflow_ls': 200, 'esp_pa': 50, 'has_sf': True}
        self.assertEqual(select_equipment(req, [])['status'], 'NeedsReview')
        req.update(equipment_type='chilled_water_fcu',
                   conditions={'entering_air_db_c': 24, 'entering_air_wb_c': 18, 'entering_water_c': 7, 'leaving_water_c': 12},
                   conditions_reference='synthetic-test')
        candidate = dict(req, model='SYNTHETIC-ONLY', performance_source='synthetic-test')
        self.assertEqual(select_equipment(req, [candidate])['status'], 'CandidatesAvailable')
        candidate['esp_pa'] = 20
        self.assertEqual(select_equipment(req, [candidate])['status'], 'NeedsReview')
        candidate['esp_pa'] = 50
        candidate['conditions'] = {'inlet_db_c': 25}
        self.assertEqual(select_equipment(req, [candidate])['status'], 'NeedsReview')

    def test_surface_unknown_never_zero(self):
        keys = sample()['time_keys']
        surf = {'name': 'wall', 'boundary': 'unknown', 'time_keys': keys,
                'area_m2': 10, 'u_w_m2k': 2, 'delta_t_k': [10]*24, 'solar': None}
        with self.assertRaises(InputError): surface_load(surf, keys)
        surf['boundary'] = 'external'
        self.assertEqual(surface_load(surf, keys)['sensible_kw'][0], 0.2)
        surf['solar'] = {'irradiance_w_m2': [100]*24, 'effective_coefficients': [0.5]*24}
        with self.assertRaises(InputError): surface_load(surf, keys)
        surf['solar']['orientation'] = 'E'
        self.assertAlmostEqual(surface_load(surf, keys)['sensible_kw'][0], 0.7)

    def test_equipment_schema_and_physics(self):
        req = {'equipment_type': 'fan', 'airflow_ls': 100, 'esp_pa': 20,
               'has_sf': False, 'conditions_reference': 'synthetic',
               'conditions': {'air_temperature_c': 25, 'air_density_kg_m3': 1.2}}
        candidate = dict(req, model='TEST-FAN', performance_source='synthetic')
        self.assertEqual(select_equipment(req, [candidate])['status'], 'CandidatesAvailable')
        for conditions in [{'foo': {}}, {'air_temperature_c': 25, 'air_density_kg_m3': 0},
                           {'air_temperature_c': {}, 'air_density_kg_m3': 1.2}]:
            invalid = dict(req, conditions=conditions)
            self.assertEqual(select_equipment(invalid, [dict(candidate,conditions=conditions)])['status'], 'NeedsReview')
        invalid = dict(req)
        del invalid['equipment_type']
        self.assertEqual(select_equipment(invalid, [candidate])['status'], 'NeedsReview')
        dx = {'equipment_type': 'dx_unit', 'total_kw': 10, 'sensible_kw': 7,
              'airflow_ls': 100, 'esp_pa': 20, 'has_sf': True, 'conditions_reference': 'synthetic',
              'conditions': {'indoor_db_c': 24, 'indoor_wb_c': 18, 'outdoor_db_c': 35}}
        dc = dict(dx, model='TEST-DX', performance_source='synthetic')
        self.assertEqual(select_equipment(dx, [dc])['status'], 'CandidatesAvailable')
        invalid = dict(dx, conditions={'indoor_db_c': 24, 'indoor_wb_c': 26, 'outdoor_db_c': 35})
        self.assertEqual(select_equipment(invalid, [dc])['status'], 'NeedsReview')
        self.assertEqual(select_equipment(dx, [candidate])['status'], 'NeedsReview')

    def test_derived_components_sf_and_provenance(self):
        keys = sample()['time_keys']
        surf = {'name': 'wall', 'boundary': 'external', 'time_keys': keys,
                'area_m2': 10, 'u_w_m2k': 2, 'delta_t_k': [10]*24, 'solar': None,
                'provenance': {'document': 'SYNTHETIC', 'page': 1}}
        r = surface_load(surf, keys)
        self.assertEqual(r['input_basis'], surf)
        r['input_basis']['delta_t_k'][0] = 999
        r['input_basis']['provenance']['page'] = 2
        self.assertEqual(surf['delta_t_k'][0], 10)
        self.assertEqual(surf['provenance']['page'], 1)
        for flag in [True, None, 1]:
            with self.subTest(flag=flag), self.assertRaises(InputError):
                surface_load(dict(surf, has_sf=flag), keys)
            with self.subTest(flag=flag), self.assertRaises(InputError):
                internal_gains({'time_keys': keys, 'has_sf': flag}, keys)

    def test_bad_shapes_and_cli_exit(self):
        invalid = sample()
        invalid['rooms'][0]['surfaces'] = None
        for payload in [[], invalid]:
            with self.assertRaises(InputError): calculate_project(payload)
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory)/'input.json'
                source.write_text(json.dumps(payload),encoding='utf-8')
                proc = subprocess.run([sys.executable,'-m','hvac_engine',str(source)],
                                      cwd=Path(__file__).resolve().parents[1],
                                      capture_output=True,encoding='utf-8')
                self.assertEqual(proc.returncode,2)
                self.assertNotIn('Traceback',proc.stderr)
                self.assertEqual(proc.stdout,'')


if __name__ == '__main__':
    unittest.main()
