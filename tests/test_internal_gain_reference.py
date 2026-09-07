"""防止來源候選被誤作無條件預設。"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InternalGainReferenceTests(unittest.TestCase):
    def test_approval_and_reference_boundaries(self):
        standard = json.loads((ROOT / 'config/company_standard.json').read_text(encoding='utf-8'))
        r = standard['approved_rules']
        self.assertEqual((r['indoor_design_db_c'], r['indoor_design_rh_percent'],
                          r['summer_outdoor_design_db_c'], r['summer_outdoor_design_wb_c'],
                          r['toilet_exhaust_ach']), (23, 55, 34, 28, 15))
        data = json.loads((ROOT / 'data/reference/internal_gains_by_function.json').read_text(encoding='utf-8'))
        self.assertFalse(data['policy']['automatic_application'])
        self.assertFalse(data['policy']['missing_is_zero'])
        self.assertFalse(data['policy']['has_safety_factor'])
        self.assertFalse(data['source']['project_application_approved'])
        self.assertTrue(all(p['reference_db_c'] == 23.9 for p in data['people_references']))
        for key, ref in [('people_candidates', 'people_references'),
                         ('lighting_candidates', 'lighting_references'),
                         ('equipment_candidates', 'office_equipment_references')]:
            ids = [p['id'] for p in data[ref]]
            self.assertEqual(len(ids), len(set(ids)))
            for room in data['room_function_profiles']:
                self.assertTrue(set(room[key]) <= set(ids))
                if room['id'] != 'office' and key == 'equipment_candidates':
                    self.assertEqual(room[key], [])
