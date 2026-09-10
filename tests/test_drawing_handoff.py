"""防止單機展開遺漏、服務變更及模板勾選冒充實核。"""
import importlib.util
from copy import deepcopy
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoff',ROOT/'scripts/build_drawing_handoff.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

class HandoffTests(unittest.TestCase):
    def setUp(self):
        c={'equipment_id':'FAN','role':'排風機','quantity':2,'brand':'B','model':'M','room_ids':['R']}
        self.base={'equipment_snapshot':{},'configuration':[c], 'equipment':[{'id':'REQ','configuration':[deepcopy(c)]}]}
        self.guide={'equipment':[{'equipment_id':'FAN-01','group_id':'FAN'},{'equipment_id':'FAN-02','group_id':'FAN'}]}
        self.follow={'actions':[{'id':'R01','steps':[],'drawing_impact':''},{'id':'R02','steps':[]}], 'fop_actual_checks':[{'status':'待核實','evidence':[]}]}

    def test_expand_preserves_source_and_nested_mapping(self):
        result=h.merge_handoff(self.base,self.guide,self.follow)
        self.assertEqual(len(result['drawing_equipment']),2)
        self.assertEqual(result['equipment'][0]['configuration'][0]['drawing_unit_ids'],['FAN-01','FAN-02'])
        self.assertEqual(self.base['configuration'][0]['quantity'],2)
        self.assertNotIn('drawing_unit_ids',self.base['configuration'][0])
        self.assertEqual(result['fop_actual_checks'][0]['status'],'待核實')

    def test_missing_unit_rejected(self):
        self.guide['equipment'].pop()
        with self.assertRaises(ValueError):h.merge_handoff(self.base,self.guide,self.follow)

    def test_duplicate_unit_rejected(self):
        self.guide['equipment'][1]['equipment_id']='FAN-01'
        with self.assertRaises(ValueError):h.merge_handoff(self.base,self.guide,self.follow)

    def test_unknown_group_rejected(self):
        self.guide['equipment'][1]['group_id']='FAKE'
        with self.assertRaises(ValueError):h.merge_handoff(self.base,self.guide,self.follow)

    def test_no_evidence_cannot_complete_check(self):
        self.follow['fop_actual_checks'][0]['status']='已核實'
        with self.assertRaises(ValueError):h.merge_handoff(self.base,self.guide,self.follow)

if __name__=='__main__':unittest.main()
