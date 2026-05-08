from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.pipeline import run_forecasting_thesis

    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)

    result = run_forecasting_thesis(
        alpha=0.95,
        lead_time=1.0,
        use_mlflow=True,
        max_prophet_products=120,
        source="dwh",
    )

    benchmark = result["benchmark"]
    pred = result["predicciones"]
    drift = result["drift"]
    wrangled = result["dataset_wrangled"]
    wrangling_report = result["wrangling_report"]

    benchmark.to_csv(artifacts / "benchmark_forecasting_thesis.csv", index=False)
    pred.to_csv(artifacts / "predicciones_ganador.csv", index=False)
    drift.to_csv(artifacts / "drift_log.csv", index=False)
    wrangled.to_csv(artifacts / "dataset_wrangled_forecasting.csv", index=False)
    wrangling_report.to_csv(artifacts / "wrangling_report.csv", index=False)

    print("\n=== FORECASTING TESIS ===")
    print(f"Modelo ganador: {result['winner']}")
    print("\nTop benchmark (val/test):")
    cols = [
        "modelo",
        "WAPE_val",
        "WAPE_test",
        "MAE_test",
        "RMSE_test",
        "mejora_vs_baseline_test_wape",
        "gap_wape_train_val",
        "gap_wape_val_test",
    ]
    print(benchmark[cols].head(10).to_string(index=False))

    print("\nWrangling report:")
    print(wrangling_report.to_string(index=False))

    print("\nDrift (PSI train vs test) - top 10:")
    print(drift.head(10).to_string(index=False))

    print(f"\nArtefactos guardados en: {artifacts}")


if __name__ == "__main__":
    main()
