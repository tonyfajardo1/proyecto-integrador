"""Plantilla de bloque exportador para personalizaciones futuras en Mage."""

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def export_data(data, *args, **kwargs):
    """Recibe la salida del bloque anterior y la devuelve sin modificaciones."""
    return data

