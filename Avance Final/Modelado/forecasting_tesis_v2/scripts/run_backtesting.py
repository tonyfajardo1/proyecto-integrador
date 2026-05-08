from pathlib import Path
import sys
import argparse


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.backtesting import BacktestingConfig, run_rolling_backtesting, save_backtesting_outputs

    parser = argparse.ArgumentParser(description="Run rolling backtesting for forecasting pipeline")
    parser.add_argument(
        "--source",
        default="dwh_forecasting_v1",
        choices=["dwh", "dwh_forecasting_v1"],
        help="Dataset source to use",
    )
    parser.add_argument(
        "--initial-train-periods",
        type=int,
        default=18,
        help="Cantidad inicial de periodos de entrenamiento",
    )
    parser.add_argument(
        "--val-window",
        type=int,
        default=3,
        help="Tamaño de la ventana de validación",
    )
    parser.add_argument(
        "--test-window",
        type=int,
        default=3,
        help="Tamaño de la ventana de test",
    )
    parser.add_argument(
        "--step-size",
        type=int,
        default=3,
        help="Cuántos periodos se mueve la ventana rolling",
    )
    args = parser.parse_args()

    cfg = BacktestingConfig(
        source=args.source,
        min_periods_product=4,
        initial_train_periods=args.initial_train_periods,
        val_window=args.val_window,
        test_window=args.test_window,
        step_size=args.step_size,
        seasonal_active_months=3,
        seasonal_active_share=0.45,
        cap_quantile=0.995,
        top_n_pilot=100,
        pilot_tipo="PT",
    )

    result = run_rolling_backtesting(cfg)
    artifacts = root / "artifacts"
    save_backtesting_outputs(result, artifacts)

    print("\n=== ROLLING BACKTESTING ===")
    print("Folds generados:")
    print(result["folds"].to_string(index=False))

    print("\nResumen agregado por modelo:")
    cols = [
        "modelo",
        "folds_evaluados",
        "folds_ganados",
        "WAPE_test_mean",
        "WAPE_test_median",
        "WAPE_test_std",
        "BIAS_PCT_test_mean",
        "ABS_BIAS_PCT_test_mean",
        "SMAPE_test_mean",
        "MAE_test_mean",
        "RMSE_test_mean",
    ]
    print(result["backtesting_summary"][cols].to_string(index=False))

    best = result["backtesting_summary"].iloc[0]

    print("\nChampion rolling sugerido:")
    print(
        f"- Modelo: {best['modelo']}\n"
        f"- WAPE medio: {best['WAPE_test_mean']:.4f}\n"
        f"- Bias medio: {best['BIAS_PCT_test_mean']:.4f}\n"
        f"- sMAPE medio: {best['SMAPE_test_mean']:.4f}\n"
        f"- Folds ganados: {int(best['folds_ganados'])}"
    )

    print("\nGanador por fold:")
    print(result["winner_by_fold"].to_string(index=False))

    print("\nPiloto PT Top 100 por fold:")
    print(result["pilot_backtesting"].to_string(index=False))

    print(f"\nArtefactos: {artifacts}")


if __name__ == "__main__":
    main()