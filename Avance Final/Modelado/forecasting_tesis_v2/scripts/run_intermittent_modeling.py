from pathlib import Path
import sys
import argparse


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.intermitencia import (
        IntermittentModelingConfig,
        run_intermittent_modeling,
        save_intermittent_outputs,
    )

    parser = argparse.ArgumentParser(description="Run intermittent-demand mixed modeling")
    parser.add_argument(
        "--source",
        default="dwh_forecasting_v1",
        choices=["dwh", "dwh_forecasting_v1"],
        help="Dataset source to use",
    )
    parser.add_argument(
        "--regular-model",
        default="LinearRegression",
        help="Modelo para demanda regular",
    )
    parser.add_argument(
        "--intermittent-model",
        default="Baseline_Lag1",
        help="Modelo para demanda intermitente",
    )
    parser.add_argument(
        "--zero-share-threshold",
        type=float,
        default=0.50,
        help="Umbral de porcentaje de ceros para clasificar intermitencia",
    )
    parser.add_argument(
        "--avg-gap-threshold",
        type=float,
        default=1.50,
        help="Umbral del gap promedio entre periodos positivos",
    )
    parser.add_argument(
        "--low-history-threshold",
        type=int,
        default=12,
        help="Umbral de poca historia para clasificar como intermitente",
    )
    args = parser.parse_args()

    cfg = IntermittentModelingConfig(
        source=args.source,
        min_periods_product=4,
        train_frac=0.6,
        val_frac=0.2,
        seasonal_active_months=3,
        seasonal_active_share=0.45,
        cap_quantile=0.995,
        intermittent_zero_share_threshold=args.zero_share_threshold,
        intermittent_avg_gap_threshold=args.avg_gap_threshold,
        low_history_threshold=args.low_history_threshold,
        regular_model=args.regular_model,
        intermittent_model=args.intermittent_model,
    )

    result = run_intermittent_modeling(cfg)
    artifacts = root / "artifacts"
    save_intermittent_outputs(result, artifacts)

    print("\n=== INTERMITTENT DEMAND MODELING ===")

    print("\nDistribución de clases de demanda:")
    print(result["class_distribution"].to_string(index=False))

    print("\nBenchmark validación - REGULAR:")
    print(
        result["regular_val_benchmark"][
            ["modelo", "WAPE_val", "BIAS_PCT_val", "SMAPE_val", "MAE_val", "RMSE_val"]
        ].to_string(index=False)
    )

    print("\nBenchmark validación - INTERMITTENT:")
    print(
        result["intermittent_val_benchmark"][
            ["modelo", "WAPE_val", "BIAS_PCT_val", "SMAPE_val", "MAE_val", "RMSE_val"]
        ].to_string(index=False)
    )

    print("\nResumen final mixto en test:")
    print(result["mixed_summary_test"].to_string(index=False))

    print("\nComparación mixto vs global:")
    print(result["comparison_vs_global"].to_string(index=False))

    print("\nEvaluación test por clase de demanda:")
    print(result["demand_class_test_eval"].to_string(index=False))

    print(f"\nArtefactos: {artifacts}")


if __name__ == "__main__":
    main()