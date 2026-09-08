"""需求對映須按識別碼，未知選型不可轉成零或預設一台。"""
import importlib.util
from copy import deepcopy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_builder', ROOT/'scripts/build_design_package.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def fixture():
    inp = {'rooms': [{'room_id': 'BF-01', 'system_id': 'DX-BF', 'exhaust_ach': 15},
                     {'room_id': 'BF-02', 'system_id': 'DX-BF', 'exhaust_ach': 15},
                     {'room_id': 'GF-01', 'system_id': 'DX-GF', 'exhaust_ach': 0}]}
    result = {'rooms': [
        {'room_id': rid, 'system_id': system, 'ventilation': {'fresh_air_ls': fresh, 'exhaust_ls': exhaust}}
        for rid, system, fresh, exhaust in [('BF-01','DX-BF',0,50), ('BF-02','DX-BF',0,25), ('GF-01','DX-GF',100,0)]],
        'systems': [{'system_id': s, 'raw_peak': {'total_kw': q}, 'sizing_peak': {'total_kw': q*1.15}, 'fresh_air_ls': f}
                    for s,q,f in [('DX-BF',10,0), ('DX-GF',20,100)]]}
    return inp, result


class PackageTests(unittest.TestCase):
    def test_system_capacity_keeps_single_sf_and_unknown_selection(self):
        inp,result = fixture()
        package = builder.build_package(inp,result)
        systems = {s['system_id']:s for s in result['systems']}
        for e in package['equipment']:
            self.assertIsNone(e['quantity'])
            if e['category'] == 'AC':
                self.assertAlmostEqual(e['required_cooling_kw'], systems[e['system_id']]['raw_peak']['total_kw']*1.15)
                self.assertIsNone(e['required_airflow_ls'])
                self.assertEqual(set(e['room_ids']), {r['room_id'] for r in result['rooms'] if r['system_id']==e['system_id']})
            else:
                self.assertIsNone(e['required_cooling_kw'])
        fau = next(e for e in package['equipment'] if e['category']=='FAU')
        self.assertEqual(fau['room_ids'], ['GF-01'])
        self.assertEqual(fau['required_airflow_ls'],100)

    def test_multiple_toilets_same_floor_have_unique_ids(self):
        p = builder.build_package(*fixture())
        ids = [e['id'] for e in p['equipment']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(sorted(e['required_airflow_ls'] for e in p['equipment'] if e['category']=='TEF'),[25,50])

    def test_independent_room_sorting_preserves_mapping(self):
        inp,result = fixture()
        a = builder.build_package(inp,result)
        inp = deepcopy(inp); result = deepcopy(result)
        inp['rooms'].reverse();result['rooms'] = result['rooms'][1:]+result['rooms'][:1]
        b = builder.build_package(inp,result)
        def normalized(package):
            return {e['id']:{**e,'room_ids':sorted(e['room_ids'])} for e in package['equipment']}
        self.assertEqual(normalized(a),normalized(b))

    def test_duplicate_room_ids_rejected(self):
        inp,result = fixture();inp['rooms'].append(deepcopy(inp['rooms'][0]))
        with self.assertRaises((ValueError,AssertionError)):
            builder.build_package(inp,result)

    def test_unknown_system_rejected(self):
        inp,result = fixture();result['rooms'][0]['system_id']='UNKNOWN'
        with self.assertRaises((ValueError,AssertionError)):
            builder.build_package(inp,result)

    def test_double_sf_rejected(self):
        inp,result = fixture();result['systems'][0]['sizing_peak']['total_kw'] *= 1.15
        with self.assertRaises((ValueError,AssertionError)):
            builder.build_package(inp,result)


if __name__ == '__main__':
    unittest.main()
