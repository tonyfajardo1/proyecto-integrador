import csv
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


BASE_DIR = Path(__file__).resolve().parents[1]
CSV_DETALLE = BASE_DIR / 'Kronos' / 'Ventas_netas_2026_01.csv'
XLSX_RESUMEN = BASE_DIR / 'Kronos' / 'Ventas_general (4).xlsx'


def conn_kronos():
    return psycopg2.connect(
        host='your-kronos-host.supabase.com',
        port=6543,
        dbname='postgres',
        user='postgres.your-kronos-project-ref',
        password=os.getenv('KRONOS_PASSWORD'),
        sslmode='require',
    )


def cargar_detalle(cur):
    cur.execute('DROP TABLE IF EXISTS kronos.ventas_detalle')
    cur.execute(
        '''
        CREATE TABLE kronos.ventas_detalle (
            id_factura TEXT,
            serie TEXT,
            numero_factura TEXT,
            fecha_ingreso TEXT,
            fecha_factura TEXT,
            fecha_vencimiento TEXT,
            vendedor TEXT,
            empleado TEXT,
            titulo_gratuito TEXT,
            id_detalle TEXT,
            cantidad TEXT,
            valor_unitario TEXT,
            valor_total TEXT,
            descuento TEXT,
            id_producto TEXT,
            id_unidad TEXT,
            costo TEXT,
            id_promocion TEXT,
            tipo_precio TEXT,
            tipo_producto TEXT,
            id_motivo TEXT,
            id_cliente TEXT,
            id_sucursal TEXT,
            vendedor_name_rutero TEXT,
            supervisor_name TEXT,
            cod_rutero TEXT,
            nombre_rutero TEXT,
            ci_empleado TEXT,
            ci_empleado_s TEXT,
            razon_social TEXT,
            nombre_comercial TEXT,
            codigo_producto TEXT,
            descripcion_producto TEXT,
            nombre_subgrupo TEXT,
            descripcion_grupo TEXT,
            nombre_marca TEXT,
            linea_name TEXT,
            tipo TEXT
        )
        '''
    )

    columns = [
        'id_factura', 'serie', 'numero_factura', 'fecha_ingreso', 'fecha_factura', 'fecha_vencimiento',
        'vendedor', 'empleado', 'titulo_gratuito', 'id_detalle', 'cantidad', 'valor_unitario', 'valor_total',
        'descuento', 'id_producto', 'id_unidad', 'costo', 'id_promocion', 'tipo_precio', 'tipo_producto',
        'id_motivo', 'id_cliente', 'id_sucursal', 'vendedor_name_rutero', 'supervisor_name', 'cod_rutero',
        'nombre_rutero', 'ci_empleado', 'ci_empleado_s', 'razon_social', 'nombre_comercial', 'codigo_producto',
        'descripcion_producto', 'nombre_subgrupo', 'descripcion_grupo', 'nombre_marca', 'linea_name', 'tipo',
    ]

    rows = []
    with open(CSV_DETALLE, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            rows.append(tuple((r.get(c.upper()) or '').strip() or None for c in columns))

    execute_values(
        cur,
        f"INSERT INTO kronos.ventas_detalle ({', '.join(columns)}) VALUES %s",
        rows,
        page_size=5000,
    )
    return len(rows)


def cargar_resumen(cur):
    cur.execute('DROP TABLE IF EXISTS kronos.ventas_resumen')
    cur.execute(
        '''
        CREATE TABLE kronos.ventas_resumen (
            centro_costo TEXT,
            codigo_producto TEXT,
            codigo_alterno TEXT,
            producto TEXT,
            mes TEXT,
            anio INTEGER,
            cant_venta NUMERIC,
            total_venta NUMERIC,
            cant_nc NUMERIC,
            total_nc NUMERIC,
            cant_devolucion NUMERIC,
            total_devolucion NUMERIC,
            cant_neto NUMERIC,
            total_neto NUMERIC,
            costo_venta NUMERIC,
            rentabilidad NUMERIC,
            prc_rentabilidad NUMERIC
        )
        '''
    )

    df = pd.read_excel(XLSX_RESUMEN, header=7)
    df.columns = [str(c).strip().upper() for c in df.columns]
    mapeo = {
        'CENTRO_COSTO': 'centro_costo',
        'CODIGO_PRODUCTO': 'codigo_producto',
        'ALTERNO': 'codigo_alterno',
        'PRODUCTO': 'producto',
        'MES': 'mes',
        'CANT': 'cant_venta',
        'TOTAL': 'total_venta',
        'CANT NC': 'cant_nc',
        'TOTAL NC': 'total_nc',
        'CANT NC DV': 'cant_devolucion',
        'TOTAL NC DV': 'total_devolucion',
        'CANT. NETO': 'cant_neto',
        'TOTAL NETO': 'total_neto',
        'COSTO VENTA': 'costo_venta',
        'VALOR RENTAB': 'rentabilidad',
        'PRC': 'prc_rentabilidad',
    }
    df = df[list(mapeo.keys())].rename(columns=mapeo)
    df = df[df['mes'].notna()].copy()
    df['anio'] = 2026

    for c in [
        'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
        'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
        'costo_venta', 'rentabilidad', 'prc_rentabilidad',
    ]:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    df['centro_costo'] = df['centro_costo'].astype(str).str.strip().str.lower()
    df['codigo_producto'] = df['codigo_producto'].astype(str).str.strip().str.upper()
    df['codigo_alterno'] = df['codigo_alterno'].astype(str).str.strip()
    df['producto'] = df['producto'].astype(str).str.strip()
    df['mes'] = df['mes'].astype(str).str.strip().str.upper()

    cols = [
        'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
        'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
        'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
        'costo_venta', 'rentabilidad', 'prc_rentabilidad',
    ]

    execute_values(
        cur,
        f"INSERT INTO kronos.ventas_resumen ({', '.join(cols)}) VALUES %s",
        [tuple(None if pd.isna(v) else v for v in row) for row in df[cols].itertuples(index=False, name=None)],
        page_size=2000,
    )
    return len(df), float(df['total_venta'].sum())


if __name__ == '__main__':
    if not os.getenv('KRONOS_PASSWORD'):
        raise RuntimeError('Falta KRONOS_PASSWORD en variables de entorno')

    conn = conn_kronos()
    conn.autocommit = True
    with conn.cursor() as cur:
        det_rows = cargar_detalle(cur)
        res_rows, res_total = cargar_resumen(cur)

    conn.close()
    print(f'ventas_detalle cargado: {det_rows} filas')
    print(f'ventas_resumen cargado: {res_rows} filas')
    print(f'total_venta resumen: {res_total:,.2f}')
