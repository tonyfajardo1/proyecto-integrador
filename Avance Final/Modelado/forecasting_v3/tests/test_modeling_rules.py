"""Pruebas de reglas operativas y consistencia del forecasting final."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quickbooks_forecast.modeling import (  # noqa: E402
    _assert_unique_prediction_keys,
    _add_decision_fields,
    _choose_model_from_comparisons,
    _temporal_cv_folds,
    _walk_forward_folds,
)


def _base_config(reports_dir: Path) -> dict:
    return {
        "resolved_paths": {"reports_dir": reports_dir},
        "model": {
            "min_rows_to_train": 12,
            "validation_months": 3,
            "test_months": 3,
            "selection_metric": "wape",
            "forecast_model": "best_ml_temporal_cv",
            "temporal_cv": {"enabled": True, "folds": 3, "validation_months": 3},
            "walk_forward": {"enabled": True, "windows": 4, "step_months": 1, "test_months": 2},
        },
        "decision": {
            "automation_thresholds": {
                "max_segment_wape": 0.10,
                "max_segment_wape_std": 0.03,
                "min_folds_below_wape_threshold": 0.67,
                "min_confidence": "media",
                "allow_seasonal_auto": False,
            }
        },
    }


def _monthly_rows(months: int = 18, rows_per_month: int = 4) -> pd.DataFrame:
    periods = pd.date_range("2024-01-01", periods=months, freq="MS")
    rows = []
    for period in periods:
        for i in range(rows_per_month):
            rows.append({"periodo": period, "product_id": f"P{i}", "target_qty": float(i + 1)})
    return pd.DataFrame(rows)


class ModelingRulesTests(unittest.TestCase):
    def test_temporal_cv_folds_do_not_leak_future(self) -> None:
        config = _base_config(Path("."))
        df = _monthly_rows(months=20, rows_per_month=4)

        folds = _temporal_cv_folds(config, df)
        self.assertGreater(len(folds), 0)
        for train_df, val_df, val_start, val_end in folds:
            self.assertLess(train_df["periodo"].max(), val_df["periodo"].min())
            self.assertEqual(pd.Timestamp(val_start), pd.Timestamp(val_df["periodo"].min()))
            self.assertEqual(pd.Timestamp(val_end), pd.Timestamp(val_df["periodo"].max()))

    def test_walk_forward_folds_do_not_leak_future(self) -> None:
        config = _base_config(Path("."))
        df = _monthly_rows(months=22, rows_per_month=4)

        folds = _walk_forward_folds(config, df)
        self.assertGreater(len(folds), 0)
        for fold_id, train_df, test_df, test_start, test_end in folds:
            self.assertGreaterEqual(fold_id, 1)
            self.assertLess(train_df["periodo"].max(), test_df["periodo"].min())
            self.assertEqual(pd.Timestamp(test_start), pd.Timestamp(test_df["periodo"].min()))
            self.assertEqual(pd.Timestamp(test_end), pd.Timestamp(test_df["periodo"].max()))

    def test_model_selection_rejects_test_based_strategy(self) -> None:
        config = _base_config(Path("."))
        config["model"]["forecast_model"] = "best_ml_test"
        validation = pd.DataFrame(
            [
                {"model_name": "random_forest", "wape": 0.10, "rank_wape": 1},
                {"model_name": "extra_trees", "wape": 0.12, "rank_wape": 2},
            ]
        )
        test = validation.copy()

        with self.assertRaises(ValueError):
            _choose_model_from_comparisons(config, validation, test)

    def test_decision_rules_apply_segment_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            config = _base_config(reports_dir)

            pd.DataFrame(
                [
                    {"model_name": "random_forest", "wape": 0.05},
                    {"model_name": "extra_trees", "wape": 0.08},
                ]
            ).to_csv(reports_dir / "model_comparison_pt.csv", index=False)

            pd.DataFrame(
                [
                    {
                        "segmento": "activos_no_estacionales",
                        "segmento_apto_automatizacion": True,
                        "mean_wape": 0.06,
                        "std_wape": 0.01,
                        "pct_folds_below_wape_threshold": 1.0,
                    },
                    {
                        "segmento": "activos_estacionales",
                        "segmento_apto_automatizacion": False,
                        "mean_wape": 0.11,
                        "std_wape": 0.04,
                        "pct_folds_below_wape_threshold": 0.5,
                    },
                    {
                        "segmento": "inactivos",
                        "segmento_apto_automatizacion": False,
                        "mean_wape": 0.20,
                        "std_wape": 0.05,
                        "pct_folds_below_wape_threshold": 0.0,
                    },
                ]
            ).to_csv(reports_dir / "walk_forward_segment_summary_pt.csv", index=False)

            pd.DataFrame(
                [
                    {
                        "product_id": "D",
                        "error_absoluto_total": 999.0,
                        "wape_producto": 0.20,
                        "prioridad_revision": "alta",
                    }
                ]
            ).to_csv(reports_dir / "high_error_products_pt.csv", index=False)

            pred = pd.DataFrame(
                [
                    {"product_id": "A", "cantidad_predicha": 100.0, "estado_producto": "activo", "es_estacional": False},
                    {"product_id": "B", "cantidad_predicha": 100.0, "estado_producto": "activo", "es_estacional": True},
                    {"product_id": "C", "cantidad_predicha": 100.0, "estado_producto": "inactivo", "es_estacional": False},
                    {"product_id": "D", "cantidad_predicha": 100.0, "estado_producto": "activo", "es_estacional": False},
                ]
            )

            out = _add_decision_fields(config, "PT", pred, "random_forest")
            by_id = out.set_index("product_id")

            self.assertEqual(by_id.loc["A", "confianza_prediccion"], "alta")
            self.assertTrue(bool(by_id.loc["A", "apto_automatizacion"]))
            self.assertEqual(by_id.loc["A", "recomendacion_decision"], "usar como cantidad sugerida")

            self.assertEqual(by_id.loc["B", "confianza_prediccion"], "media")
            self.assertFalse(bool(by_id.loc["B", "apto_automatizacion"]))
            self.assertTrue(bool(by_id.loc["B", "requiere_revision"]))
            self.assertEqual(by_id.loc["B", "recomendacion_decision"], "revisar antes de ordenar")

            self.assertEqual(by_id.loc["C", "confianza_prediccion"], "no_aplica")
            self.assertFalse(bool(by_id.loc["C", "apto_automatizacion"]))
            self.assertEqual(by_id.loc["C", "recomendacion_decision"], "no producir por inactividad")

            self.assertEqual(by_id.loc["D", "confianza_prediccion"], "baja")
            self.assertFalse(bool(by_id.loc["D", "apto_automatizacion"]))
            self.assertTrue(bool(by_id.loc["D", "requiere_revision"]))

    def test_high_error_merge_keeps_one_prediction_row_per_product(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            config = _base_config(reports_dir)

            pd.DataFrame(
                [
                    {"model_name": "random_forest", "wape": 0.05},
                ]
            ).to_csv(reports_dir / "model_comparison_pt.csv", index=False)

            pd.DataFrame(
                [
                    {
                        "product_id": "D",
                        "cantidad_real_total": 100.0,
                        "error_absoluto_total": 10.0,
                        "wape_producto": 0.10,
                        "prioridad_revision": "normal",
                    },
                    {
                        "product_id": "D",
                        "cantidad_real_total": 200.0,
                        "error_absoluto_total": 20.0,
                        "wape_producto": 0.10,
                        "prioridad_revision": "alta",
                    },
                ]
            ).to_csv(reports_dir / "high_error_products_pt.csv", index=False)

            pred = pd.DataFrame(
                [
                    {"product_id": "D", "cantidad_predicha": 100.0, "estado_producto": "activo", "es_estacional": False},
                    {"product_id": "E", "cantidad_predicha": 50.0, "estado_producto": "activo", "es_estacional": False},
                ]
            )

            out = _add_decision_fields(config, "PT", pred, "random_forest")
            by_id = out.set_index("product_id")

            self.assertEqual(out.shape[0], pred.shape[0])
            self.assertEqual(by_id.loc["D", "prioridad_revision"], "alta")
            self.assertAlmostEqual(float(by_id.loc["D", "error_absoluto_total"]), 30.0)
            self.assertAlmostEqual(float(by_id.loc["D", "wape_producto"]), 0.10)

    def test_prediction_report_files_have_unique_product_period_keys(self) -> None:
        reports_dir = ROOT / "reports"
        for file_name in ["predicciones_pt.csv", "predicciones_pp.csv"]:
            report_path = reports_dir / file_name
            if not report_path.exists():
                self.skipTest(f"No existe {report_path}")
            report = pd.read_csv(report_path)
            _assert_unique_prediction_keys(report, str(report_path))


if __name__ == "__main__":
    unittest.main()
