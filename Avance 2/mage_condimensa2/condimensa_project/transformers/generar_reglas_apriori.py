"""
Transformer: Generar reglas de asociacion con Apriori (Cross-Selling)
Pipeline: dm_reglas_asociacion
Encuentra patrones de productos que se compran juntos.
Ejemplo: Salsa BBQ + Mostaza -> Marinada para Carnes
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
    Aplica Apriori para encontrar productos que se compran juntos.
    Responde: ¿Que productos se venden juntos? (Cross-Selling)
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

    print(f"\n{'='*70}")
    print(f"REGLAS DE ASOCIACION - CROSS-SELLING")
    print(f"Pregunta: ¿Que productos se venden juntos?")
    print(f"{'='*70}")

    # =========================================================================
    # 1. CREAR LISTA DE TRANSACCIONES (cestas de productos)
    # =========================================================================

    print(f"\n[1] Creando cestas de productos por transaccion...")

    # Parametros anti-oom
    min_support = float(kwargs.get('min_support', 0.02))
    min_confidence = float(kwargs.get('min_confidence', 0.25))
    max_len = int(kwargs.get('max_len', 2))
    max_productos = int(kwargs.get('max_productos', 120))

    # Agrupar productos por transaccion
    transacciones = df.groupby('transaccion_id')['producto'].apply(list).tolist()

    print(f"    Transacciones totales: {len(transacciones)}")

    # Limitar universo de productos por frecuencia para reducir memoria
    freq_prod = df.groupby('producto')['transaccion_id'].nunique().sort_values(ascending=False)
    productos_top = set(freq_prod.head(max_productos).index.tolist())
    transacciones = [[p for p in cesta if p in productos_top] for cesta in transacciones]
    transacciones = [c for c in transacciones if len(c) >= 2]

    if len(transacciones) == 0:
        print("[WARN] Sin transacciones validas despues de filtros de memoria")
        return pd.DataFrame(columns=['antecedente', 'consecuente', 'soporte', 'confianza', 'lift', 'interpretacion', 'accion_sugerida'])

    print(f"    Ejemplo de cesta filtrada: {transacciones[0][:4]}...")

    # =========================================================================
    # 2. CODIFICAR TRANSACCIONES EN MATRIZ BINARIA
    # =========================================================================

    print(f"\n[2] Codificando matriz de transacciones...")

    te = TransactionEncoder()
    te_array = te.fit(transacciones).transform(transacciones, sparse=True)
    df_encoded = pd.DataFrame.sparse.from_spmatrix(te_array, columns=te.columns_)

    print(f"    Matriz: {df_encoded.shape[0]} transacciones x {df_encoded.shape[1]} productos")

    # Mostrar productos mas frecuentes
    frecuencias = df_encoded.sum().sort_values(ascending=False)
    print(f"\n    TOP 5 productos mas frecuentes:")
    for prod, freq in frecuencias.head(5).items():
        print(f"      - {prod}: {freq} transacciones ({freq/len(df_encoded)*100:.1f}%)")

    # =========================================================================
    # 3. ENCONTRAR ITEMSETS FRECUENTES
    # =========================================================================

    print(f"\n[3] Buscando itemsets frecuentes...")

    # Apriori con controles de memoria
    frequent_itemsets = apriori(
        df_encoded,
        min_support=min_support,
        use_colnames=True,
        max_len=max_len,
        low_memory=True,
    )

    print(f"    Itemsets con support >= {min_support}: {len(frequent_itemsets)}")

    if len(frequent_itemsets) == 0:
        print("    Reduciendo min_support a 0.01...")
        min_support = 0.01
        frequent_itemsets = apriori(
            df_encoded,
            min_support=min_support,
            use_colnames=True,
            max_len=max_len,
            low_memory=True,
        )
        print(f"    Itemsets con support >= {min_support}: {len(frequent_itemsets)}")

    # Mostrar itemsets de 2+ productos
    itemsets_multi = frequent_itemsets[frequent_itemsets['itemsets'].apply(len) >= 2]
    print(f"    Pares/grupos de productos frecuentes: {len(itemsets_multi)}")

    # =========================================================================
    # 4. GENERAR REGLAS DE ASOCIACION
    # =========================================================================

    print(f"\n[4] Generando reglas de asociacion...")

    if len(frequent_itemsets) > 0:
        rules = association_rules(
            frequent_itemsets,
            metric="confidence",
            min_threshold=min_confidence,
        )

        # Filtrar solo reglas de productos (no reglas triviales)
        rules = rules[rules['antecedents'].apply(len) >= 1]
        rules = rules[rules['consequents'].apply(len) >= 1]

        print(f"    Reglas generadas: {len(rules)}")

        if len(rules) == 0:
            print("    [INFO] No se generaron reglas con los parametros actuales.")
            return pd.DataFrame(columns=['antecedente', 'consecuente', 'soporte', 'confianza', 'lift', 'interpretacion', 'accion_sugerida'])

        # =========================================================================
        # 5. ELIMINAR REGLAS DUPLICADAS (VICEVERSA)
        # =========================================================================
        
        # Crear una clave unica para cada par de itemsets (ordenada)
        def get_rule_key(antecedents, consequents):
            ant = frozenset(antecedents)
            cons = frozenset(consequents)
            return tuple(sorted([tuple(ant), tuple(cons)]))

        rules['rule_key'] = rules.apply(lambda r: get_rule_key(r['antecedents'], r['consequents']), axis=1)

        # Eliminar duplicados: quedarse solo con la primera ocurrencia (mayor lift)
        rules = rules.drop_duplicates(subset='rule_key', keep='first')
        
        # Ordenar por lift descendente
        rules = rules.sort_values('lift', ascending=False)

        print(f"    Reglas unicas (sin duplicados viceversa): {len(rules)}")
        print(f"    Params -> min_support={min_support}, min_confidence={min_confidence}, max_len={max_len}, max_productos={max_productos}")

        # =========================================================================
        # 6. MOSTRAR MEJORES REGLAS PARA CROSS-SELLING
        # =========================================================================

        print(f"\n{'='*70}")
        print(f"TOP 15 REGLAS DE CROSS-SELLING")
        print(f"(Ordenadas por Lift - indica fuerza de la asociacion)")
        print(f"{'='*70}")

        if len(rules) > 0:
            # Ordenar por lift (relevancia)
            top_rules = rules.nlargest(15, 'lift')

            for idx, (_, rule) in enumerate(top_rules.iterrows(), 1):
                antecedent = ', '.join(list(rule['antecedents']))
                consequent = ', '.join(list(rule['consequents']))

                # Interpretar el lift
                if rule['lift'] > 2:
                    interpretacion = "FUERTE"
                elif rule['lift'] > 1.5:
                    interpretacion = "MODERADA"
                else:
                    interpretacion = "DEBIL"

                print(f"\n  [{idx}] SI compra: {antecedent}")
                print(f"      ENTONCES tambien compra: {consequent}")
                print(f"      Confianza: {rule['confidence']*100:.1f}% | Lift: {rule['lift']:.2f} ({interpretacion})")

            # =========================================================================
            # 6. RECOMENDACIONES DE NEGOCIO
            # =========================================================================

            print(f"\n{'='*70}")
            print(f"RECOMENDACIONES DE CROSS-SELLING")
            print(f"{'='*70}")

            # Encontrar las mejores combinaciones para promociones
            best_rules = rules.nlargest(5, 'lift')
            print("\nPROMOCIONES SUGERIDAS:")
            for idx, (_, rule) in enumerate(best_rules.iterrows(), 1):
                productos = list(rule['antecedents']) + list(rule['consequents'])
                print(f"\n  Combo {idx}: {' + '.join(productos)}")
                print(f"           Probabilidad de compra conjunta: {rule['confidence']*100:.1f}%")

            # Preparar DataFrame de salida
            rules['antecedentes_str'] = rules['antecedents'].apply(lambda x: ', '.join(list(x)))
            rules['consecuentes_str'] = rules['consequents'].apply(lambda x: ', '.join(list(x)))

            df_rules = rules[['antecedentes_str', 'consecuentes_str', 'support', 'confidence', 'lift']].copy()
            df_rules.columns = ['antecedente', 'consecuente', 'soporte', 'confianza', 'lift']
            df_rules = df_rules.sort_values('lift', ascending=False)

            # Agregar interpretacion
            df_rules['interpretacion'] = df_rules['lift'].apply(
                lambda x: 'FUERTE' if x > 2 else ('MODERADA' if x > 1.5 else 'DEBIL')
            )

            # Agregar recomendacion de accion
            df_rules['accion_sugerida'] = df_rules.apply(
                lambda r: f"Crear combo: {r['antecedente']} + {r['consecuente']}" if r['lift'] > 1.5
                else f"Exhibir juntos: {r['antecedente']} y {r['consecuente']}",
                axis=1
            )

            print(f"\n{'='*70}")
            print(f"INTERPRETACION DE METRICAS:")
            print(f"- Support: % de transacciones que contienen la regla")
            print(f"- Confidence: Probabilidad de comprar B dado que compro A")
            print(f"- Lift > 1: Los productos se compran juntos mas de lo esperado")
            print(f"- Lift > 2: Asociacion fuerte (ideal para cross-selling)")
            print(f"{'='*70}\n")

            return df_rules

    # Si no hay reglas, retornar DataFrame vacio
    print("\n[WARN] No se encontraron reglas de asociacion con los parametros actuales")
    return pd.DataFrame(columns=['antecedente', 'consecuente', 'soporte', 'confianza', 'lift', 'interpretacion', 'accion_sugerida'])


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    if len(output) > 0:
        print(f"OK: {len(output)} reglas de cross-selling generadas")
        print(f"    Top regla: {output.iloc[0]['antecedente']} -> {output.iloc[0]['consecuente']} (lift={output.iloc[0]['lift']:.2f})")
    else:
        print("WARN: No se generaron reglas")
