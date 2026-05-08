from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.datasets_postgres import load_anomaly_dataset
from src.anomaly import benchmark_anomaly


def main():
    data_path = ROOT / "data" / "anomaly_dataset.csv"
    out_path = ROOT / "models" / "benchmark_anomaly.csv"

    ROOT.joinpath("data").mkdir(exist_ok=True)
    ROOT.joinpath("models").mkdir(exist_ok=True)

    df = load_anomaly_dataset()
    df.to_csv(data_path, index=False)
    res = benchmark_anomaly(df)
    res.to_csv(out_path, index=False)
    print(res)
    print(f"Guardado: {out_path}")


if __name__ == "__main__":
    main()
