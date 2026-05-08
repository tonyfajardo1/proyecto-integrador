"""
Script para generar el Documento Final usando la plantilla de biblioteca USFQ
Mantiene el formato original de la plantilla
"""

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
import shutil

# Rutas
PLANTILLA = r"F:\proyecto-integrador\Avance 2\guia-biblioteca-pregrado (1).docx"
SALIDA = r"F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\DOCUMENTO_FINAL_ENTREGABLE2.docx"
IMAGENES_DIR = r"F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes"

def crear_documento():
    """Crea el documento final basado en la plantilla"""

    # Copiar plantilla
    shutil.copy(PLANTILLA, SALIDA)
    doc = Document(SALIDA)

    # === LIMPIAR Y REEMPLAZAR CONTENIDO ===

    # Encontrar y reemplazar texto en la portada
    reemplazos = {
        "Colegio de xxxx": "Colegio de Ciencias e Ingenierias",
        "Titulo del trabajo": "Sistema de forecasting de produccion para soporte a la planificacion operativa en CONDIMENSA",
        "Nombre completo del autor del trabajo": "Anthony Fajardo",
        "Licenciatura/Ingenieria en xxxx": "Ingenieria en Ciencias de la Computacion",
        "Licenciado/Ingeniero en xxxx": "Ingeniero en Ciencias de la Computacion",
        "Quito, XX de xxxx de XXXX": "Quito, 29 de marzo de 2026",
        "Nombre del tutor, titulo academico": "Jose David Vega Sanchez, M.Sc.",
    }

    for p in doc.paragraphs:
        for old_text, new_text in reemplazos.items():
            if old_text in p.text:
                for run in p.runs:
                    if old_text in run.text:
                        run.text = run.text.replace(old_text, new_text)

    # Guardar documento inicial
    doc.save(SALIDA)
    print(f"[OK] Documento base guardado: {SALIDA}")
    print()
    print("NOTA: Este documento tiene la estructura de la plantilla.")
    print("Debes completar manualmente:")
    print("  1. Contenido de cada seccion (RESUMEN, ABSTRACT, etc.)")
    print("  2. Insertar las imagenes en los lugares indicados")
    print("  3. Actualizar la tabla de contenido")
    print()
    print("Usa el archivo DOCUMENTO_FINAL_AVANCE2.md como referencia del contenido.")

if __name__ == "__main__":
    crear_documento()
