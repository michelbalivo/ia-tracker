"""
migrate_from_excel.py
─────────────────────
Resetea la tabla y vuelca data.xlsx completo a PostgreSQL.
Ejecutar cada vez que se quiera re-importar desde Excel:

    python migrate_from_excel.py

Requiere DATABASE_URL en .env o como variable de entorno.
"""

import os, math, json
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

BASE           = Path(__file__).parent
EXCEL_PATH     = BASE / "data.xlsx"
DB_URL         = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ia_tracker")

# ── Schema completo ─────────────────────────────────────────────────
DDL = """
DROP TABLE IF EXISTS initiatives;
CREATE TABLE initiatives (
    id                       INTEGER PRIMARY KEY,
    name                     TEXT,
    dept                     TEXT,
    proceso                  TEXT,
    clasificacion_proceso    TEXT,
    criticidad_proceso       TEXT,
    volumen_proceso          NUMERIC,
    dominio                  TEXT,
    tipo_ia                  TEXT,
    tip_ocr                  BOOLEAN,
    tip_generativa           BOOLEAN,
    tip_analitica            BOOLEAN,
    tip_predictiva           BOOLEAN,
    modelo_ia                TEXT,
    viabilidad               TEXT,
    score_viabilidad         NUMERIC,
    viabilidad_puntos        NUMERIC,
    datos_requeridos         TEXT,
    disponibilidad           TEXT,
    madurez_funcional        TEXT,
    time_to_value            TEXT,
    complejidad              TEXT,
    score_complejidad        NUMERIC,
    complejidad_tecnica      TEXT,
    complejidad_organizativa TEXT,
    retorno                  TEXT,
    tipo_retorno             TEXT,
    impacto_negocio          TEXT,
    ahorro                   NUMERIC,
    usuarios                 TEXT,
    prioridad                TEXT,
    roi_business_case        NUMERIC,
    reach                    NUMERIC,
    impact                   NUMERIC,
    confidence               NUMERIC,
    effort                   NUMERIC,
    ai_complexity            NUMERIC,
    ric                      NUMERIC,
    tier                     NUMERIC,
    riesgos                  TEXT,
    compliance               TEXT,
    objetivo                 TEXT,
    fecha_registro           DATE,
    powerapps_id             TEXT,
    fase_inicio              DATE,
    fase_analisis            DATE,
    fase_priorizacion        DATE,
    fase_piloto              DATE,
    fase_diseno              DATE,
    fase_iteracion           DATE,
    fase_produccion       DATE,
    equipo                   TEXT,
    responsable              TEXT,
    estado_excel             TEXT,
    estado_override          TEXT,
    fecha_fin                DATE,
    fecha_inicio             DATE,
    alerta                   BOOLEAN,
    comp_bbdd                TEXT,
    comp_ocr                 TEXT,
    comp_cluster             TEXT,
    comp_api                 TEXT,
    comp_backend             TEXT,
    comp_modelo              TEXT,
    comp_mcp                 TEXT,
    comp_rag                 TEXT,
    comp_prompting           TEXT,
    comp_frontend            TEXT,
    link_devhub              TEXT,
    desc_ejecutiva           TEXT,
    updated_at               TIMESTAMP DEFAULT NOW()
);
"""

COLUMNS = """
    id, name, dept, proceso, clasificacion_proceso, criticidad_proceso, volumen_proceso,
    dominio, tipo_ia, tip_ocr, tip_generativa, tip_analitica, tip_predictiva,
    modelo_ia, viabilidad, score_viabilidad, viabilidad_puntos,
    datos_requeridos, disponibilidad, madurez_funcional, time_to_value,
    complejidad, score_complejidad, complejidad_tecnica, complejidad_organizativa,
    retorno, tipo_retorno, impacto_negocio, ahorro, usuarios, prioridad,
    roi_business_case, reach, impact, confidence, effort, ai_complexity, ric, tier,
    riesgos, compliance, objetivo, fecha_registro, powerapps_id,
    fase_inicio, fase_analisis, fase_priorizacion, fase_piloto,
    fase_diseno, fase_iteracion, fase_produccion,
    equipo, responsable, estado_excel, estado_override,
    fecha_fin, fecha_inicio, alerta,
    comp_bbdd, comp_ocr, comp_cluster, comp_api, comp_backend,
    comp_modelo, comp_mcp, comp_rag, comp_prompting, comp_frontend,
    link_devhub, desc_ejecutiva
"""

INSERT_SQL = f"INSERT INTO initiatives ({COLUMNS}) VALUES %s"


# ── Helpers ─────────────────────────────────────────────────────────
def safe(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    if hasattr(v, "strftime"):
        try: return v.strftime("%Y-%m-%d")
        except: return None
    s = str(v).strip()
    return s if s not in ("nan", "None", "") else None

def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except: return None

def to_bool(v):
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)):
        try: return bool(v) if not math.isnan(float(v)) else False
        except: return False
    if isinstance(v, str): return v.strip().lower() in ("sí","si","yes","true","1","x","✓")
    return False


# ── Leer Excel ───────────────────────────────────────────────────────
def load_excel():
    print(f"Leyendo {EXCEL_PATH.name} ...")
    df = pd.read_excel(EXCEL_PATH, sheet_name="Seguimiento IA", header=1)
    rows = []
    for _, row in df.iterrows():
        raw_id = row.get("Id")
        if pd.isna(raw_id): continue
        try: iid = int(raw_id)
        except: continue

        def col(name): return safe(row.get(name))
        def flt(name): return safe_float(row.get(name))
        def bl(name):  return to_bool(row.get(name))

        name = col("Descripción resumida de la iniciativa")
        if not name: continue

        rows.append((
            iid,
            name,
            col("Departamento"),
            col("Proceso impactado"),
            col("Clasificacion Proceso"),
            col("Criticidad Proceso"),
            flt("Volumen del proceso (M€)"),
            col("Dominio funcional de IA"),
            col("Tipo IA"),
            bl("Procesamiento de documentos / Visión"),
            bl("IA Generativa / Conversacional"),
            bl("Analítica / Diagnóstica / Recomendación"),
            bl("Predictiva / Forecasting"),
            col("Modelo / Proveedor de IA"),
            col("Viabilidad"),
            flt("Socre Viabilidad"),
            flt("Viabilidad puntos"),
            col("Datos Requeridos"),
            col("Disponibilidad de datos"),
            col("Madurez Funcional"),
            col("Time to value"),
            col("Complejidad"),
            flt("Score Complejidad"),
            col("Complejidad técnica (esfuerzo)"),
            col("Complejidad organizativa"),
            col("Retorno esperado"),
            col("Tipo de Retorno"),
            col("Impacto en negocio"),
            flt("Ahorro estimado (€ / año)"),
            col("Usuarios Impactados"),
            col("Prioridad sugerida"),
            flt("ROI Business Case"),
            flt("Reach"),
            flt("Impact"),
            flt("Confidence"),
            flt("Effort"),
            flt("AI Complexity"),
            flt("RIC"),
            flt("TIER"),
            col("Principales riesgos"),
            col("Impacto en compliance"),
            col("Objetivo estratégico"),
            col("Fecha Registro"),
            col("__PowerAppsId__"),
            col("Inicio"),
            col("Análisis"),
            col("Priorización"),
            col("Piloto"),
            col("Diseño"),
            col("Iteración / Pruebas"),
            col("Producción"),
            col("Equipo IA Asignado"),
            col("Responsable"),
            col("Estado Iniciativa") or "Pendiente",
            None,                          # estado_override (reset limpio)
            col("Fin Estimado"),
            col("Inicio"),                 # fecha_inicio
            bl("Alerta"),
            safe(row.get("BBDD")),
            safe(row.get("OCR")),
            safe(row.get("Cluster Comp")),
            safe(row.get("API")),
            safe(row.get("Back End")),
            safe(row.get("Modelo IA")),
            safe(row.get("MCP")),
            safe(row.get("RAG")),
            safe(row.get("Prompting")),
            safe(row.get("Front End")),
            col("Link DevHub"),
            col("Descripción ejecutiva"),
        ))

    print(f"  → {len(rows)} iniciativas leídas")
    return rows


# ── Migración ────────────────────────────────────────────────────────
def migrate():
    rows = load_excel()
    if not rows:
        print("No hay datos para migrar."); return

    print(f"Conectando a: {DB_URL.split('@')[-1]} ...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True          # DDL requiere autocommit
    cur = conn.cursor()

    print("Recreando tabla...")
    cur.execute(DDL)
    print("  → DROP + CREATE TABLE ✓")

    conn.autocommit = False         # Transacción para los datos
    execute_values(cur, INSERT_SQL, rows)
    conn.commit()
    print(f"  → {len(rows)} filas insertadas ✓")

    cur.close(); conn.close()
    print("\n✅  Migración completada.\n")


if __name__ == "__main__":
    migrate()
