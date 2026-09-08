"""新風除濕、再熱及單次安全係數的物理守恆驗證。"""
import unittest
from hvac_engine.air_treatment import from_db_wb, wet_bulb, neutral_fresh_air
from hvac_engine.core import InputError, apply_safety_factor


class AirTreatmentTests(unittest.TestCase):
    def test_macau_design_state_has_plausible_moisture(self):
        state=from_db_wb(34,28,101325)
        self.assertGreater(state['humidity_ratio_kgkg'],0.020)
        self.assertLess(state['humidity_ratio_kgkg'],0.022)
        self.assertGreater(state['rh_fraction'],0.62)
        self.assertLess(state['rh_fraction'],0.66)

    def test_inverse_wet_bulb_round_trip(self):
        for db,rh in [(23,.55),(34,.64),(28,.85),(30,1.0)]:
            with self.subTest(db=db,rh=rh):
                wb=wet_bulb(db,rh)
                self.assertLessEqual(wb,db)
                self.assertAlmostEqual(from_db_wb(db,wb,101325)['rh_fraction'],rh,places=8)

    def test_invalid_wet_bulb_rejected(self):
        for db,wb in [(23,24),(34,-1),(51,28)]:
            with self.subTest(db=db,wb=wb),self.assertRaises(InputError):
                from_db_wb(db,wb,101325)

    def test_coil_reheat_energy_and_water_balance(self):
        p=neutral_fresh_air(920)
        self.assertAlmostEqual(p['raw_coil']['total_kw']-p['reheat_kw'],p['net_outdoor_to_supply_kw'],places=9)
        self.assertAlmostEqual(p['coil_outlet']['humidity_ratio_kgkg'],p['supply']['humidity_ratio_kgkg'],places=10)
        self.assertGreater(p['inlet']['humidity_ratio_kgkg'],p['coil_outlet']['humidity_ratio_kgkg'])
        self.assertAlmostEqual(p['dry_air_mass_kg_s']*p['inlet']['specific_volume_m3kg_da'],.920,places=10)
        self.assertGreater(p['reheat_kw'],0)
        self.assertGreater(p['raw_coil']['total_kw'],50)
        self.assertLess(p['raw_coil']['total_kw'],54)

    def test_safety_factor_once_and_airflow_unchanged(self):
        p=neutral_fresh_air(920)
        self.assertFalse(p['raw_coil']['has_sf'])
        self.assertTrue(p['sizing_coil']['has_sf'])
        self.assertEqual(p['airflow_ls'],920)
        for key in ('total_kw','sensible_kw','latent_kw'):
            self.assertAlmostEqual(p['sizing_coil'][key],1.15*p['raw_coil'][key],places=10)
        with self.assertRaises(InputError):apply_safety_factor(p['sizing_coil'])

    def test_airflow_scales_energy_not_air_conditions(self):
        full=neutral_fresh_air(920);half=neutral_fresh_air(460)
        self.assertAlmostEqual(full['raw_coil']['total_kw'],2*half['raw_coil']['total_kw'],places=9)
        self.assertAlmostEqual(full['reheat_kw'],2*half['reheat_kw'],places=9)
        self.assertEqual(full['coil_outlet'],half['coil_outlet'])


if __name__=='__main__':unittest.main()
