from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.pipeline import run_imputation_ab_test

    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)

    summary, details = run_imputation_ab_test(alpha=0.95, lead_time=1.0, source="dwh")
    summary.to_csv(artifacts / "imputation_ab_summary.csv", index=False)

    for cfg_id, res in details.items():
        res["benchmark"].to_csv(artifacts / f"benchmark_{cfg_id}.csv", index=False)
        res["wrangling_report"].to_csv(artifacts / f"wrangling_report_{cfg_id}.csv", index=False)
        res["drift"].to_csv(artifacts / f"drift_{cfg_id}.csv", index=False)

    print("\n=== IMPUTATION A/B TEST ===")
    print(summary.to_string(index=False))
    print(f"\nArtefactos guardados en: {artifacts}")


if __name__ == "__main__":
    main()
