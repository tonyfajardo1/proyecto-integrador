from pathlib import Path
import sys
import argparse


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.segmentacion import (
        SegmentedModelingConfig,
        run_segmented_modeling,
        save_segmented_outputs,
    )

    parser = argparse.ArgumentParser(description="Run segmented champion selection for forecasting")
    parser.add_argument(
        "--source",
        default="dwh_forecasting_v1",
        choices=["dwh", "dwh_forecasting_v1"],
        help="Dataset source to use",
    )
    parser.add_argument(
        "--min-rows-segment-train",
        type=int,
        default=60,
        help="Mínimo de filas train por segmento para permitir champion propio",
    )
    parser.add_argument(
        "--min-rows-segment-val",
        type=int,
        default=10,
        help="Mínimo de filas val por segmento para permitir champion propio",
    )
    parser.add_argument(
        "--min-rows-segment-test",
        type=int,
        default=10,
        help="Mínimo de filas test por segmento para permitir champion propio",
    )
    parser.add_argument(
        "--fallback-model",
        default="LinearRegression",
        help="Modelo fallback si un segmento no tiene suficiente historia",
    )
    args = parser.parse_args()

    cfg = SegmentedModelingConfig(
        source=args.source,
        min_periods_product=4,
        train_frac=0.6,
        val_frac=0.2,
        seasonal_active_months=3,
        seasonal_active_share=0.45,
        cap_quantile=0.995,
        min_rows_segment_train=args.min_rows_segment_train,
        min_rows_segment_val=args.min_rows_segment_val,
        min_rows_segment_test=args.min_rows_segment_test,
        fallback_model=args.fallback_model,
    )

    result = run_segmented_modeling(cfg)
    artifacts = root / "artifacts"
    save_segmented_outputs(result, artifacts)

    print("\n=== CHAMPION POR SEGMENTO ===")
    print(f"Champion global de referencia (validación): {result['global_winner']}")

    print("\nBenchmark global en validación:")
    print(
        result["global_val_benchmark"][
            [
                "modelo",
                "WAPE_val",
                "BIAS_PCT_val",
                "SMAPE_val",
                "MAE_val",
                "RMSE_val",
            ]
        ].to_string(index=False)
    )

    print("\nGanadores por tipo_producto:")
    print(result["segment_winners"].to_string(index=False))

    print("\nResumen del modelo segmentado en test:")
    print(result["segmentado_summary_test"].to_string(index=False))

    print("\nComparación segmentado vs global:")
    print(result["comparison_vs_global"].to_string(index=False))

    print("\nEvaluación test por tipo_producto usando champion segmentado:")
    print(result["segment_test_eval"].to_string(index=False))

    print(f"\nArtefactos: {artifacts}")


if __name__ == "__main__":
    main()