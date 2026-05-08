# Instrucciones para Generar Documentos Word Finales

## Archivos Generados

```
DOCUMENTO_FINAL_WORD/
├── DOCUMENTO_FINAL_AVANCE2.md              # Documento tecnico completo
├── ENTREGABLE_2_PLANTILLA_ACTIVIDADES.md   # Plantilla de actividades
├── CATALOGO_COMPLETO_24_FIGURAS.md         # Catalogo con descripciones
├── README_INSTRUCCIONES.md                 # Este archivo
└── imagenes/                               # 24 FIGURAS TOTALES
    ├── fig01_arquitectura.png              # Diagrama de arquitectura
    ├── fig02_pipelines.png                 # Lista de pipelines Mage
    ├── fig03_etl_bronze.png                # Ejecucion ETL Bronze
    ├── fig04_sql_gold.png                  # Validacion SQL Gold
    ├── fig05_kpis.png                      # Dashboard KPIs principales
    ├── fig06_agencias.png                  # Ventas por agencia
    ├── fig07_benchmark.png                 # Benchmark modelos ML
    ├── fig08_pronosticos.png               # Dashboard pronosticos
    ├── fig09_apriori.png                   # Reglas de asociacion
    ├── fig10_anomalias.png                 # Deteccion anomalias
    ├── fig11_etl_silver.png                # Pipeline ETL Silver
    ├── fig12_etl_gold.png                  # Pipeline ETL Gold
    ├── fig13_scatter.png                   # Scatter Pronostico vs Plan
    ├── fig14_anomalias_detalle.png         # Mapa Devolucion vs Rentabilidad
    ├── fig15_apriori_detalle.png           # Lift por regla + Recomendaciones
    ├── fig16_sql_silver.png                # Query Silver muestra
    ├── fig17_sql_silver_conteos.png        # Conteos Silver
    ├── fig18_sql_gold_muestra.png          # Query Gold muestra
    ├── fig19_wrangling.png                 # Reporte calidad: 14,670 rows
    ├── fig20_inactivos.png                 # Productos excluidos
    ├── fig21_estructura.png                # Estructura proyecto ML
    ├── fig22_artefactos.png                # Artefactos MLflow
    ├── fig23_documentacion.png             # Documentacion E2E
    └── fig24_qty_planificada.png           # Qty planificada analisis
```

---

## OPCION 1: Copiar Manualmente a Word (Recomendado)

### Paso 1: Abrir plantilla oficial de biblioteca
1. Abrir `guia-biblioteca-pregrado (1).docx` de la carpeta Avance 2
2. Guardar como: `Documento_Final_Avance2_AnthonyFajardo.docx`

### Paso 2: Copiar contenido
1. Abrir `DOCUMENTO_FINAL_AVANCE2.md` en un editor
2. Copiar cada seccion al documento Word
3. Aplicar los estilos de la plantilla (Titulo 1, Titulo 2, etc.)

### Paso 3: Insertar imagenes
1. En cada lugar marcado `[INSERTAR FIGURA X]`:
   - Ir a Insertar > Imagen
   - Seleccionar la imagen de la carpeta `imagenes/`
   - Agregar pie de figura con el texto indicado

### Paso 4: Plantilla de Entregables
1. Abrir `plantilla_entregables (1).docx`
2. Guardar como: `Entregable_2_AnthonyFajardo.docx`
3. Copiar contenido de `ENTREGABLE_2_PLANTILLA_ACTIVIDADES.md`

---

## OPCION 2: Usar Pandoc (Automatico)

### Instalar Pandoc
```powershell
# Con Chocolatey
choco install pandoc

# O descargar de: https://pandoc.org/installing.html
```

### Convertir a Word
```powershell
cd "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD"

# Documento tecnico
pandoc DOCUMENTO_FINAL_AVANCE2.md -o Documento_Final_Avance2.docx --reference-doc="../guia-biblioteca-pregrado (1).docx"

# Plantilla entregables
pandoc ENTREGABLE_2_PLANTILLA_ACTIVIDADES.md -o Entregable_2_Actividades.docx --reference-doc="../plantilla_entregables (1).docx"
```

**Nota:** Despues de convertir, revisar formato e insertar imagenes manualmente.

---

## CHECKLIST FINAL ANTES DE SUBIR A D2L

### Documento 1: Plantilla de Entregables
- [ ] Completar codigo de estudiante
- [ ] Verificar todas las actividades listadas
- [ ] **OBTENER FIRMA DEL TUTOR** (obligatorio)
- [ ] Guardar como PDF

### Documento 2: Documento Final Tecnico
- [ ] Insertar las 10 figuras en las secciones indicadas
- [ ] Verificar formato de la plantilla de biblioteca
- [ ] Revisar numeracion de paginas
- [ ] Verificar referencias en formato correcto
- [ ] Guardar como PDF

### Repositorio GitHub
- [ ] Hacer commit del Avance 2
- [ ] Hacer push al repositorio
- [ ] Verificar que el link funcione

### Subir a D2L
- [ ] Subir antes del 29 marzo 22:00
- [ ] Verificar que ambos archivos esten subidos
- [ ] Confirmar recepcion

---

## Contacto

Si tienes problemas con la conversion, puedes:
1. Copiar manualmente (mas seguro para mantener formato)
2. Usar un convertidor online de Markdown a Word
3. Pedir ayuda al tutor

**Fecha limite:** Domingo 29 de marzo de 2026, 22:00
