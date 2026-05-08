from pathlib import Path
import sys
import argparse


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.modeling import ModelingConfig, run_full_modeling, save_outputs

    parser = argparse.ArgumentParser(description="Run forecasting modeling pipeline")
    parser.add_argument(
        "--source",
        default="dwh_forecasting_v1",
        choices=["dwh", "dwh_forecasting_v1"],
        help="Dataset source to use",
    )
    args = parser.parse_args()

    cfg = ModelingConfig(
        source=args.source,
        min_periods_product=4,
        train_frac=0.6,
        val_frac=0.2,
        seasonal_active_months=3,
        seasonal_active_share=0.45,
        cap_quantile=0.995,
    )

    result = run_full_modeling(cfg)
    artifacts = root / "artifacts"
    save_outputs(result, artifacts)

    print("\n=== MODELING V2 ===")
    print(f"Modelo ganador: {result['winner']}")
    print(result["benchmark"][
        [
            "modelo",
            "WAPE_val",
            "WAPE_test",
            "MAE_test",
            "RMSE_test",
            "gap_wape_train_val",
            "gap_wape_val_test",
        ]
    ].to_string(index=False))
    print("\nLeakage report:")
    print(result["leakage_report"].to_string(index=False))
    print("\nControl de outliers (resumen wrangling):")
    wr = result["wrangling_report"].set_index("metric")
    for k in [
        "rows_outlier_extremo_fabricada",
        "rows_outlier_extremo_planificada",
        "rows_outlier_sospechoso_fabricada",
        "rows_outlier_sospechoso_planificada",
        "rows_outlier_caps_aplicados",
        "products_with_caps",
    ]:
        if k in wr.index:
            print(f"- {k}: {wr.loc[k, 'value']}")
    print("\nPiloto PT Top 100 por volumen:")
    print(result["pilot_top_pt"].to_string(index=False))
    print(f"\nArtefactos: {artifacts}")


if __name__ == "__main__":
    main()
