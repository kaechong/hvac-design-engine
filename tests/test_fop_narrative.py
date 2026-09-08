"""固定章、防誤用母本工程資料及四表結構回歸測試。"""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('narrative', ROOT/'scripts/build_retail_trial_narrative.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class NarrativeTemplateTests(unittest.TestCase):
    def test_fixed_template_matches_reference(self):
        template = json.loads(builder.TEMPLATE.read_text(encoding='utf-8'))
        reference = json.loads((ROOT/'data/reference/fop_template_spec.json').read_text(encoding='utf-8'))
        original = {p['paragraph_index']:p['text'] for p in reference['docx']['paragraphs']}
        self.assertEqual(set(template['fixed_chapters']), {'2','4','6','7'})
        for chapter in template['fixed_chapters'].values():
            for p in chapter:
                self.assertEqual(p['text'], original[p['paragraph_index']])

    def test_build_preserves_fixed_text_and_replaces_project(self):
        package_path = ROOT/'outputs/revised_20260908/design_package.json'
        if not package_path.exists():
            self.skipTest('先建置本地試點 design_package.json')
        package = json.loads(package_path.read_text(encoding='utf-8'))
        doc = builder.build_document(package)
        template = json.loads(builder.TEMPLATE.read_text(encoding='utf-8'))
        for chapter in template['fixed_chapters'].values():
            for p in chapter:
                self.assertEqual(builder.full_text(doc.paragraphs[p['paragraph_index']]._p), p['text'])
        package['input']['project_id'] = 'OTHER-PROJECT-FIXED-TEXT-CHECK'
        other = builder.build_document(package)
        for chapter in template['fixed_chapters'].values():
            for p in chapter:
                self.assertEqual(builder.full_text(other.paragraphs[p['paragraph_index']]._p), p['text'])
        self.assertEqual(len(doc.tables), 4)
        self.assertEqual([len(t.columns) for t in doc.tables], [6,8,6,4])
        self.assertEqual(len(doc.tables[0].rows), len(package['input']['rooms'])+1)
        text = builder.full_text(doc.element)
        self.assertNotIn('PUMA', text)
        self.assertNotIn('中央冰水供回水系統', text)
        self.assertIn('未計算', text)
        self.assertIn('W/m²', text)
        self.assertEqual(doc.sections[0].top_margin.inches, 1)
        for e in package['equipment']:
            self.assertIn(e['id'], text)
        for row in doc.tables[3].rows[1:]:
            self.assertEqual(builder.full_text(row.cells[2]._tc), '待核實')


if __name__ == '__main__':
    unittest.main()
