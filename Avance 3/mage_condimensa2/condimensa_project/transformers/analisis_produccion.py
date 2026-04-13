"""
Transformer: Análisis de producción para Data Mining
Responde: ¿Existen patrones de producción que expliquen desviaciones plan vs real?
"""
import pandas as pd

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform(data, *args, **kwargs):
    """
    Transforma los datos de producción para análisis de desviaciones
    """
    df = data.copy()

    # Convertir fecha a datetime si no lo es
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

        # Extraer características temporales
        df['dia_semana'] = df['fecha'].dt.dayofweek
        df['mes'] = df['fecha'].dt.month
        df['semana_ano'] = df['fecha'].dt.isocalendar().week

    # Calcular métricas de análisis
    print(f"\n📊 ANÁLISIS DE PRODUCCIÓN")
    print(f"=" * 50)
    print(f"Total de órdenes: {len(df)}")

    if 'estado' in df.columns:
        print(f"\nDistribución por estado:")
        print(df['estado'].value_counts())

    if 'numitems' in df.columns:
        print(f"\nEstadísticas de items por orden:")
        print(df['numitems'].describe())

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'La transformación falló'
    print(f"✓ Datos transformados: {len(output)} registros")
