"""Pruebas unitarias de feature engineering temporal."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quickbooks_forecast.features import make_features  # noqa: E402


class FeatureLeakageTests(unittest.TestCase):
    def test_estado_y_ultima_actividad_no_miran_meses_futuros(self) -> None:
        monthly = pd.DataFrame(
            {
                "product_id": ["P1"] * 6,
                "periodo": pd.date_range("2025-01-01", periods=6, freq="MS"),
                "target_qty": [10.0, 0.0, 0.0, 0.0, 8.0, 0.0],
            }
        )

        features = make_features(
            monthly,
            pd.DataFrame(),
            inactive_months=2,
            seasonal_top_3_month_share=0.60,
            seasonal_max_active_months_per_year=4,
        )

        april = features.loc[features["periodo"].eq(pd.Timestamp("2025-04-01"))].iloc[0]
        june = features.loc[features["periodo"].eq(pd.Timestamp("2025-06-01"))].iloc[0]

        self.assertEqual(pd.Timestamp(april["ultima_actividad"]), pd.Timestamp("2025-01-01"))
        self.assertEqual(april["estado_producto"], "inactivo")
        self.assertEqual(pd.Timestamp(june["ultima_actividad"]), pd.Timestamp("2025-05-01"))
        self.assertEqual(june["estado_producto"], "activo")

    def test_estacionalidad_se_activa_solo_con_historial_pasado(self) -> None:
        monthly = pd.DataFrame(
            {
                "product_id": ["P2"] * 25,
                "periodo": pd.date_range("2024-01-01", periods=25, freq="MS"),
                "target_qty": [0.0] * 11 + [100.0] + [0.0] * 11 + [100.0] + [0.0],
            }
        )

        features = make_features(
            monthly,
            pd.DataFrame(),
            inactive_months=12,
            seasonal_top_3_month_share=0.60,
            seasonal_max_active_months_per_year=4,
        )

        june_2025 = features.loc[features["periodo"].eq(pd.Timestamp("2025-06-01"))].iloc[0]
        jan_2026 = features.loc[features["periodo"].eq(pd.Timestamp("2026-01-01"))].iloc[0]

        self.assertFalse(bool(june_2025["es_estacional"]))
        self.assertEqual(float(june_2025["share_top_3_meses"]), 1.0)
        self.assertTrue(bool(jan_2026["es_estacional"]))
        self.assertIn("12", str(jan_2026["meses_estacionales_num"]))


if __name__ == "__main__":
    unittest.main()
