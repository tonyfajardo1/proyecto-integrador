from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.datasets_postgres import load_forecasting_dataset
from src.forecasting import benchmark_forecasting


def main():
    data_path = ROOT / "data" / "forecasting_dataset.csv"
    out_path = ROOT / "models" / "benchmark_forecasting.csv"

    ROOT.joinpath("data").mkdir(exist_ok=True)
    ROOT.joinpath("models").mkdir(exist_ok=True)

    df = load_forecasting_dataset()
    df.to_csv(data_path, index=False)
    res = benchmark_forecasting(df)
    res.to_csv(out_path, index=False)
    print(res)
    print(f"Guardado: {out_path}")


if __name__ == "__main__":
    main()
