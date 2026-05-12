"""Pruebas de contrato para la integracion de forecasting_v3 en Mage."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forecasting_v3_mage import (  # noqa: E402
    GOLD_PREDICTION_KEY_COLUMNS,
    PREDICTION_KEY_COLUMNS,
    assert_unique_keys,
    validate_forecasting_inputs,
)


class ForecastingV3ContractsTests(unittest.TestCase):
    def test_prediction_duplicate_guard_rejects_product_period_duplicates(self) -> None:
        predictions = pd.DataFrame(
            [
                {"source_type": "PT", "product_id": "A", "periodo": "2026-04-01", "cantidad_predicha": 10},
                {"source_type": "PT", "product_id": "A", "periodo": "2026-04-01", "cantidad_predicha": 12},
            ]
        )

        with self.assertRaises(ValueError):
            assert_unique_keys(predictions, PREDICTION_KEY_COLUMNS, "predicciones_pt")

    def test_gold_duplicate_guard_rejects_product_period_duplicates(self) -> None:
        dashboard = pd.DataFrame(
            [
                {"tipo_producto": "PT", "product_id": "A", "periodo_prediccion": "2026-04-01"},
                {"tipo_producto": "PT", "product_id": "A", "periodo_prediccion": "2026-04-01"},
            ]
        )

        with self.assertRaises(ValueError):
            assert_unique_keys(dashboard, GOLD_PREDICTION_KEY_COLUMNS, "gold.pronostico_produccion_unificado_v1")

    def test_mage_prediction_report_files_have_unique_product_period_keys(self) -> None:
        reports_dir = ROOT / "data" / "forecasting_v3" / "reports"
        for file_name in ["predicciones_pt.csv", "predicciones_pp.csv"]:
            report_path = reports_dir / file_name
            if not report_path.exists():
                self.skipTest(f"No existe {report_path}")
            report = pd.read_csv(report_path)
            assert_unique_keys(report, PREDICTION_KEY_COLUMNS, str(report_path))

    def test_silver_alignment_validation_detects_incomplete_pt(self) -> None:
        incomplete = {
            "pt_mensual_model": pd.DataFrame(
                {
                    "product_id": ["PT1", "PT2"],
                    "periodo": ["2026-03-01", "2026-03-01"],
                    "target_qty": [10.0, 20.0],
                }
            ),
            "pt_productos_model": pd.DataFrame({"product_id": ["PT1", "PT2"]}),
            "pp_mensual_model": pd.DataFrame(
                {
                    "product_id": [f"PP{i}" for i in range(220)],
                    "periodo": ["2026-02-01"] * 220,
                    "target_qty": [150000.0] * 220,
                }
            ),
            "pp_productos_model": pd.DataFrame({"product_id": [f"PP{i}" for i in range(220)]}),
        }

        validation = validate_forecasting_inputs(incomplete)
        self.assertTrue(any(issue.startswith("pt_mensual_model") for issue in validation["issues"]))
        self.assertTrue(any(issue.startswith("pt_productos_model") for issue in validation["issues"]))


if __name__ == "__main__":
    unittest.main()
