from pathlib import Path
import pandas as pd


def _format_value(v):
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def export_markdown_summary(
    results_df: pd.DataFrame,
    experiment_name: str,
    baseline_name: str,
    output_md_path,
    notes=None,
):
    notes = notes or []
    p = Path(output_md_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    if len(results_df) == 0:
        text = f"# {experiment_name}\n\nNo hay resultados.\n"
        p.write_text(text, encoding="utf-8")
        return p

    top = results_df.iloc[0].to_dict()

    lines = []
    lines.append(f"# {experiment_name}")
    lines.append("")
    lines.append(f"- Baseline: `{baseline_name}`")
    lines.append(f"- Mejor fila: `{_format_value(top.get('modelo', top.get('algoritmo', 'N/A')))}`")
    lines.append("")

    if notes:
        lines.append("## Notas")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## Top 5 resultados")
    lines.append("")

    cols = list(results_df.columns)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines.append(header)
    lines.append(sep)

    for _, row in results_df.head(5).iterrows():
        vals = [_format_value(row[c]) for c in cols]
        lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Archivo fuente")
    lines.append("")
    lines.append(f"Generado desde notebook de {experiment_name}.")

    p.write_text("\n".join(lines), encoding="utf-8")
    return p
