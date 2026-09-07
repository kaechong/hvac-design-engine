"""Evidence tests: exact historical extraction and fail-closed corruption checks."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hap_extract", ROOT / "scripts/extract_hap_reference.py")
hap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hap)


class HistoricalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = json.loads((ROOT / "data/reference/hap_reference.json").read_text(encoding="utf-8"))
        cls.mapping = json.loads((ROOT / "data/reference/hap_reconciliation.json").read_text(encoding="utf-8"))

    def test_reference_all_pages_and_original_margin(self):
        rooms = self.ref["spaces"]
        self.assertEqual([s["provenance"]["page"] for s in rooms], list(range(1, 56)))
        self.assertEqual(len({s["reference_id"] for s in rooms}), 55)
        for s in rooms:
            self.assertEqual(s["safety_factor"]["sensible_percent"], 10)
            self.assertEqual(s["safety_factor"]["latent_percent"], 10)
            self.assertEqual(len(s["components"]), 15)
            self.assertEqual(len(s["provenance"]["sha256"]), 64)

    def test_visual_baseline_room_and_system_are_distinct(self):
        s = self.ref["spaces"][0]
        self.assertEqual((s["floor_area_m2"], s["people"], s["cooling_sensible_W"], s["cooling_latent_W"]), (239, 60, 45160, 13595))
        self.assertEqual(s["peak"], {"month": "Jul", "hour_hhmm": "1700"})
        system = self.ref["system"]
        self.assertEqual(system["peak"], {"month": "Jun", "hour_hhmm": "0900"})
        self.assertEqual(system["totals"][">> Total System Loads"]["cooling_latent_W"], 278581)
        self.assertEqual(system["totals"][">> Total Conditioning"]["cooling_latent_W"], 278333)
        self.assertNotEqual(sum(r["cooling_sensible_W"] for r in self.ref["spaces"]), system["totals"][">> Total System Loads"]["cooling_sensible_W"])

    def test_legacy_distillation_equal_but_geometry_not_approved(self):
        self.assertEqual(self.mapping["counts"]["legacy_reference_equal"], 55)
        self.assertEqual(self.mapping["counts"]["legacy_input_rooms"], 84)
        self.assertEqual(self.mapping["counts"]["verified_same_scope_engine_comparisons"], 0)
        for record in self.mapping["building_mapping"]:
            for candidate in record["candidates"]:
                self.assertFalse(candidate["comparison_allowed"])
        self.assertTrue(any(r["status"] == "ambiguous" for r in self.mapping["building_mapping"]))

    def test_missing_duplicate_and_shifted_columns_rejected(self):
        for text in ["", "People 60 4308 3606 0 0 0\nPeople 60 4308 3606 0 0 0", "People 60 4308 3606 0 0"]:
            with self.assertRaises(ValueError):
                hap.row(text, "People")

    def test_dash_preserved_as_not_applicable(self):
        r = hap.row("Wall Transmission 18 m2 723 - 18 m2 490 -", "Wall Transmission")
        self.assertIsNone(r["cooling_latent_W"])
        self.assertEqual(r["detail"], 18)


@unittest.skipUnless((ROOT / "data/raw/慕拉士_冷量計算_2_20231118.pdf").exists(), "Local original PDFs required for integration tests")
class OriginalPDFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pypdf import PdfReader
        cls.path = ROOT / "data/raw/慕拉士_冷量計算_2_20231118.pdf"
        cls.text = PdfReader(cls.path).pages[0].extract_text()

    def test_reextract_matches_committed_evidence(self):
        actual = hap.extract(self.path, ROOT / "data/raw/慕拉士_冷量計算_1_20231118.pdf")
        expected = json.loads((ROOT / "data/reference/hap_reference.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_duplicate_page_and_corrupt_total_rejected(self):
        for text, page in [(self.text, 2), (self.text.replace("45160 13595", "95160 13595"), 1)]:
            with self.assertRaises(ValueError):
                hap.parse_space(text, page, hap.source_info(self.path))


if __name__ == "__main__":
    unittest.main()
