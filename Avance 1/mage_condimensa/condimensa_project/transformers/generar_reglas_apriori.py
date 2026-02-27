"""
Transformer: Generar reglas de asociacion con Apriori
Pipeline: dm_reglas_asociacion
Encuentra patrones como: agencia X + producto Y -> devolucion alta
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def generar_reglas_apriori(data, *args, **kwargs):
    """
    Aplica analisis de asociacion para encontrar patrones de devolucion.
    """
    df = data.copy()

    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder
    except ImportError:
        print("Instalando mlxtend...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'mlxtend', '-q'])
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder

    # =========================================================================
    # 1. CREAR TRANSACCIONES PARA APRIORI
    # =========================================================================

    # Crear lista de items por transaccion
    transacciones = []

    for _, row in df.iterrows():
        items = []

        # Agregar agencia
        items.append(f"AGENCIA_{row['centro_costo'].upper()}")

        # Agregar categoria de producto (simplificada)
        cat = str(row['categoria'])[:20].replace(' ', '_').upper()
        items.append(f"PROD_{cat}")

        # Agregar mes
        items.append(f"MES_{row['mes']}")

        # Agregar flags de devolucion
        if row['devolucion_alta'] == 1:
            items.append("DEVOLUCION_ALTA")
        if row['devolucion_critica'] == 1:
            items.append("DEVOLUCION_CRITICA")
        if row['tiene_devolucion'] == 1:
            items.append("CON_DEVOLUCION")

        # Agregar flags de rentabilidad
        if row['rentabilidad_baja'] == 1:
            items.append("RENTAB_BAJA")
        if row['rentabilidad_alta'] == 1:
            items.append("RENTAB_ALTA")

        if row['volumen_alto'] == 1:
            items.append("VOLUMEN_ALTO")

        transacciones.append(items)

    # =========================================================================
    # 2. CODIFICAR TRANSACCIONES
    # =========================================================================

    te = TransactionEncoder()
    te_array = te.fit_transform(transacciones)
    df_encoded = pd.DataFrame(te_array, columns=te.columns_)

    print(f"\n{'='*70}")
    print(f"REGLAS DE ASOCIACION - APRIORI")
    print(f"{'='*70}")
    print(f"\nTransacciones codificadas: {len(df_encoded)}")
    print(f"Items unicos: {len(te.columns_)}")

    # =========================================================================
    # 3. ENCONTRAR ITEMSETS FRECUENTES
    # =========================================================================

    print(f"\n[1] Buscando itemsets frecuentes (min_support=0.05)...")

    frequent_itemsets = apriori(df_encoded, min_support=0.05, use_colnames=True)
    print(f"    Itemsets encontrados: {len(frequent_itemsets)}")

    if len(frequent_itemsets) == 0:
        print("    No se encontraron itemsets frecuentes. Reduciendo min_support...")
        frequent_itemsets = apriori(df_encoded, min_support=0.02, use_colnames=True)
        print(f"    Itemsets con min_support=0.02: {len(frequent_itemsets)}")

    # =========================================================================
    # 4. GENERAR REGLAS DE ASOCIACION
    # =========================================================================

    print(f"\n[2] Generando reglas de asociacion (min_confidence=0.5)...")

    if len(frequent_itemsets) > 0:
        rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.5)

        # Filtrar reglas que tengan devolucion en consecuente
        rules_devolucion = rules[
            rules['consequents'].apply(lambda x: any('DEVOLUCION' in str(i) for i in x))
        ]

        print(f"    Reglas totales: {len(rules)}")
        print(f"    Reglas relacionadas a devolucion: {len(rules_devolucion)}")

        # =========================================================================
        # 5. MOSTRAR REGLAS MAS IMPORTANTES
        # =========================================================================

        print(f"\n[3] TOP 10 REGLAS RELACIONADAS A DEVOLUCIONES")
        print(f"    (Ordenadas por lift - relevancia)")
        print(f"    " + "-"*65)

        if len(rules_devolucion) > 0:
            top_rules = rules_devolucion.nlargest(10, 'lift')

            for idx, rule in top_rules.iterrows():
                antecedent = ', '.join(list(rule['antecedents']))
                consequent = ', '.join(list(rule['consequents']))
                print(f"\n    Regla: SI {antecedent}")
                print(f"           ENTONCES {consequent}")
                print(f"           Support: {rule['support']:.3f} | Confidence: {rule['confidence']:.3f} | Lift: {rule['lift']:.3f}")

        # Preparar DataFrame de salida con reglas
        if len(rules) > 0:
            rules['antecedents_str'] = rules['antecedents'].apply(lambda x: ', '.join(list(x)))
            rules['consequents_str'] = rules['consequents'].apply(lambda x: ', '.join(list(x)))

            df_rules = rules[['antecedents_str', 'consequents_str', 'support', 'confidence', 'lift']].copy()
            df_rules.columns = ['antecedente', 'consecuente', 'soporte', 'confianza', 'lift']
            df_rules = df_rules.sort_values('lift', ascending=False)

            print(f"\n{'='*70}")
            print(f"INTERPRETACION:")
            print(f"- Support: Frecuencia de la regla en los datos")
            print(f"- Confidence: Probabilidad del consecuente dado el antecedente")
            print(f"- Lift > 1: La regla es mas frecuente de lo esperado por azar")
            print(f"{'='*70}\n")

            return df_rules

    # Si no hay reglas, retornar DataFrame vacio
    return pd.DataFrame(columns=['antecedente', 'consecuente', 'soporte', 'confianza', 'lift'])


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    print(f"OK: {len(output)} reglas de asociacion generadas")
