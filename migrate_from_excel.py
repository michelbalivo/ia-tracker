"""
migrate_from_excel.py
─────────────────────
Vuelca data.xlsx a PostgreSQL con TODAS las columnas del Excel.
Ejecutar cada vez que se quiera re-importar desde Excel:

    python migrate_from_excel.py

Requiere que DATABASE_URL esté definido en .env o como variable de entorno:
    DATABASE_URL=postgresql://usuario:password@localhost:5432/ia_tracker
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
OVERRIDES_PATH = BASE / "status_overrides.json"
DB_URL         = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ia_tracker")

# ── DDL completo (todas las columnas del Excel) ─────────────────────
DDL_CREATE = """
CREATE TABLE IF NOT EXISTS initiatives (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT,
    dept                    TEXT,
    proceso                 TEXT,
    clasificacion_proceso   TEXT,
    volumen_proceso         NUMERIC,
    dominio                 TEXT,
    tipo_ia                 TEXT,
    tip_ocr                 BOOLEAN,
    tip_generativa          BOOLEAN,
    tip_analitica           BOOLEAN,
    tip_predictiva          BOOLEAN,
    modelo_ia               TEXT,
    viabilidad              TEXT,
    score_viabilidad        NUMERIC,
    viabilidad_puntos       NUMERIC,
    datos_requeridos        TEXT,
    disponibilidad          TEXT,
    time_to_value           TEXT,
    complejidad             TEXT,
    score_complejidad       NUMERIC,
    complejidad_tecnica     TEXT,
    complejidad_organizativa TEXT,
    retorno                 TEXT,
    tipo_retorno            TEXT,
    impacto_negocio         TEXT,
    ahorro                  NUMERIC,
    usuarios                TEXT,
    prioridad               TEXT,
    roi_business_case       NUMERIC,
    reach                   NUMERIC,
    impact                  NUMERIC,
    confidence              NUMERIC,
    effort                  NUMERIC,
    ai_complexity           NUMERIC,
    ric                     NUMERIC,
    tier                    NUMERIC,
    riesgos                 TEXT,
    compliance              TEXT,
    objetivo                TEXT,
    fecha_registro          DATE,
    fase_inicio             DATE,
    fase_analisis           DATE,
    fase_priorizacion       DATE,
    fase_piloto             DATE,
    fase_diseno             DATE,
    fase_iteracion          DATE,
    fase_mantenimiento      DATE,
    equipo                  TEXT,
    responsable             TEXT,
    estado_excel            TEXT,
    estado_override         TEXT,
    fecha_fin               DATE,
    fecha_inicio            DATE,
    alerta                  BOOLEAN,
    comp_bbdd               TEXT,
    comp_ocr                TEXT,
    comp_cluster            TEXT,
    comp_api                TEXT,
    comp_backend            TEXT,
    comp_modelo             TEXT,
    comp_frontend           TEXT,
    link_devhub             TEXT,
    desc_ejecutiva          TEXT,
    prioridad_sugerida      TEXT,
    updated_at              TIMESTAMP DEFAULT NOW()
);
"""

# Columnas a añadir si la tabla ya existe (para bases de datos existentes)
ALTER_COLUMNS = [
    ("clasificacion_proceso",    "TEXT"),
    ("volumen_proceso",          "NUMERIC"),
    ("tipo_ia",                  "TEXT"),
    ("tip_ocr",                  "BOOLEAN"),
    ("tip_generativa",           "BOOLEAN"),
    ("tip_analitica",            "BOOLEAN"),
    ("tip_predictiva",           "BOOLEAN"),
    ("viabilidad_puntos",        "NUMERIC"),
    ("datos_requeridos",         "TEXT"),
    ("time_to_value",            "TEXT"),
    ("complejidad_tecnica",      "TEXT"),
    ("complejidad_organizativa", "TEXT"),
    ("impacto_negocio",          "TEXT"),
    ("roi_business_case",        "NUMERIC"),
    ("ric",                      "NUMERIC"),
    ("fecha_registro",           "DATE"),
    ("comp_backend",             "TEXT"),
    ("prioridad_sugerida",       "TEXT"),
]

# comp_* pasan de BOOLEAN a TEXT para guardar el valor real (ej: "Azure AI")
ALTER_TYPE_COLUMNS = [
    "comp_bbdd", "comp_ocr", "comp_cluster", "comp_api", "comp_modelo", "comp_frontend"
]


# ── Helpers ────────────────────────────────────────────────────────
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
    if isinstance(v, (int, float)): return bool(v) if not math.isnan(float(v)) else False
    if isinstance(v, str): return v.strip().lower() in ("sí","si","yes","true","1","x","✓")
    return False

def safe_text_or_none(v):
    """Para columnas de arquitectura: guarda el texto si existe, None si vacío."""
    s = safe(v)
    return s  # puede ser "Azure AI", "KAIA V2", etc. o None


# ── Leer Excel ─────────────────────────────────────────────────────
def load_excel():
    print(f"Leyendo {EXCEL_PATH.name} ...")
    df = pd.read_excel(EXCEL_PATH, sheet_name="Seguimiento IA", header=1)

    # Cargar overrides para preservar estados cambiados manualmente
    overrides = {}
    if OVERRIDES_PATH.exists():
        overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        print(f"  → {len(overrides)} overrides de estado encontrados")

    rows = []
    for _, row in df.iterrows():
        raw_id = row.get("Id")
        if pd.isna(raw_id): continue
        try: iid = int(raw_id)
        except: continue

        def col(name): return safe(row.get(name))
        def flt(name): return safe_float(row.get(name))
        def bl(name):  return to_bool(row.get(name))
        def txt(name): return safe_text_or_none(row.get(name))

        name = col("Descripción resumida de la iniciativa")
        if not name: continue

        estado_excel    = col("Estado Iniciativa") or "Pendiente"
        estado_override = overrides.get(str(iid))

        rows.append((
            iid,
            name,
            col("Departamento"),
            col("Proceso impactado"),
            col("Clasificacion Proceso"),
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
            col("Inicio"),
            col("Análisis"),
            col("Priorización"),
            col("Piloto"),
            col("Diseño"),
            col("Iteración / Pruebas"),
            col("Mantenimiento"),
            col("Equipo IA Asignado"),
            col("Responsable"),
            estado_excel,
            estado_override,
            col("Fin Estimado"),
            col("Inicio"),           # fecha_inicio (alias de Inicio)
            bl("Alerta"),
            txt("BBDD"),
            txt("OCR"),
            txt("Cluster Comp"),
            txt("API"),
            txt("Back End"),
            txt("Modelo IA"),
            txt("Front End"),
            col("Link DevHub"),
            col("Descripción ejecutiva"),
            col("Prioridad sugerida"),  # prioridad_sugerida (alias)
        ))

    print(f"  → {len(rows)} iniciativas leídas")
    return rows


# ── SQL ────────────────────────────────────────────────────────────
COLUMNS = """
    id, name, dept, proceso, clasificacion_proceso, volumen_proceso,
    dominio, tipo_ia, tip_ocr, tip_generativa, tip_analitica, tip_predictiva,
    modelo_ia, viabilidad, score_viabilidad, viabilidad_puntos,
    datos_requeridos, disponibilidad, time_to_value,
    complejidad, score_complejidad, complejidad_tecnica, complejidad_organizativa,
    retorno, tipo_retorno, impacto_negocio,
    ahorro, usuarios, prioridad, roi_business_case,
    reach, impact, confidence, effort, ai_complexity, ric, tier,
    riesgos, compliance, objetivo,
    fecha_registro, fase_inicio, fase_analisis, fase_priorizacion,
    fase_piloto, fase_diseno, fase_iteracion, fase_mantenimiento,
    equipo, responsable, estado_excel, estado_override,
    fecha_fin, fecha_inicio, alerta,
    comp_bbdd, comp_ocr, comp_cluster, comp_api, comp_backend,
    comp_modelo, comp_frontend, link_devhub, desc_ejecutiva, prioridad_sugerida
"""

UPSERT_SQL = f"""
INSERT INTO initiatives ({COLUMNS})
VALUES %s
ON CONFLICT (id) DO UPDATE SET
    name                    = EXCLUDED.name,
    dept                    = EXCLUDED.dept,
    proceso                 = EXCLUDED.proceso,
    clasificacion_proceso   = EXCLUDED.clasificacion_proceso,
    volumen_proceso         = EXCLUDED.volumen_proceso,
    dominio                 = EXCLUDED.dominio,
    tipo_ia                 = EXCLUDED.tipo_ia,
    tip_ocr                 = EXCLUDED.tip_ocr,
    tip_generativa          = EXCLUDED.tip_generativa,
    tip_analitica           = EXCLUDED.tip_analitica,
    tip_predictiva          = EXCLUDED.tip_predictiva,
    modelo_ia               = EXCLUDED.modelo_ia,
    viabilidad              = EXCLUDED.viabilidad,
    score_viabilidad        = EXCLUDED.score_viabilidad,
    viabilidad_puntos       = EXCLUDED.viabilidad_puntos,
    datos_requeridos        = EXCLUDED.datos_requeridos,
    disponibilidad          = EXCLUDED.disponibilidad,
    time_to_value           = EXCLUDED.time_to_value,
    complejidad             = EXCLUDED.complejidad,
    score_complejidad       = EXCLUDED.score_complejidad,
    complejidad_tecnica     = EXCLUDED.complejidad_tecnica,
    complejidad_organizativa = EXCLUDED.complejidad_organizativa,
    retorno                 = EXCLUDED.retorno,
    tipo_retorno            = EXCLUDED.tipo_retorno,
    impacto_negocio         = EXCLUDED.impacto_negocio,
    ahorro                  = EXCLUDED.ahorro,
    usuarios                = EXCLUDED.usuarios,
    prioridad               = EXCLUDED.prioridad,
    roi_business_case       = EXCLUDED.roi_business_case,
    reach                   = EXCLUDED.reach,
    impact                  = EXCLUDED.impact,
    confidence              = EXCLUDED.confidence,
    effort                  = EXCLUDED.effort,
    ai_complexity           = EXCLUDED.ai_complexity,
    ric                     = EXCLUDED.ric,
    tier                    = EXCLUDED.tier,
    riesgos                 = EXCLUDED.riesgos,
    compliance              = EXCLUDED.compliance,
    objetivo                = EXCLUDED.objetivo,
    fecha_registro          = EXCLUDED.fecha_registro,
    fase_inicio             = EXCLUDED.fase_inicio,
    fase_analisis           = EXCLUDED.fase_analisis,
    fase_priorizacion       = EXCLUDED.fase_priorizacion,
    fase_piloto             = EXCLUDED.fase_piloto,
    fase_diseno             = EXCLUDED.fase_diseno,
    fase_iteracion          = EXCLUDED.fase_iteracion,
    fase_mantenimiento      = EXCLUDED.fase_mantenimiento,
    equipo                  = EXCLUDED.equipo,
    responsable             = EXCLUDED.responsable,
    estado_excel            = EXCLUDED.estado_excel,
    fecha_fin               = EXCLUDED.fecha_fin,
    fecha_inicio            = EXCLUDED.fecha_inicio,
    alerta                  = EXCLUDED.alerta,
    comp_bbdd               = EXCLUDED.comp_bbdd,
    comp_ocr                = EXCLUDED.comp_ocr,
    comp_cluster            = EXCLUDED.comp_cluster,
    comp_api                = EXCLUDED.comp_api,
    comp_backend            = EXCLUDED.comp_backend,
    comp_modelo             = EXCLUDED.comp_modelo,
    comp_frontend           = EXCLUDED.comp_frontend,
    link_devhub             = EXCLUDED.link_devhub,
    desc_ejecutiva          = EXCLUDED.desc_ejecutiva,
    prioridad_sugerida      = EXCLUDED.prioridad_sugerida,
    updated_at              = NOW()
    -- estado_override se preserva (no se sobreescribe desde Excel)
"""


# ── Migración ──────────────────────────────────────────────────────
def ensure_database_exists():
    from urllib.parse import urlparse
    parsed  = urlparse(DB_URL)
    db_name = parsed.path.lstrip("/")
    admin_url = DB_URL.replace(f"/{db_name}", "/postgres")
    try:
        conn = psycopg2.connect(admin_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{db_name}"')
            print(f"  → Base de datos '{db_name}' creada ✓")
        else:
            print(f"  → Base de datos '{db_name}' ya existe ✓")
        cur.close(); conn.close()
    except Exception as e:
        print(f"  ⚠  No se pudo verificar/crear la BD: {e}")


def apply_schema_changes(cur):
    """Aplica cambios de schema sobre tabla existente (idempotente)."""

    # 1. Añadir columnas nuevas si no existen
    for col_name, col_type in ALTER_COLUMNS:
        try:
            cur.execute(f"ALTER TABLE initiatives ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"  → Columna '{col_name}' añadida ({col_type})")
        except Exception as e:
            print(f"  ⚠  {col_name}: {e}")

    # 2. Cambiar comp_* de BOOLEAN a TEXT (para guardar texto real)
    for col_name in ALTER_TYPE_COLUMNS:
        try:
            cur.execute(f"""
                ALTER TABLE initiatives
                ALTER COLUMN {col_name} TYPE TEXT
                USING CASE WHEN {col_name} THEN 'true' ELSE NULL END
            """)
            print(f"  → Columna '{col_name}' convertida a TEXT ✓")
        except Exception as e:
            # Si ya es TEXT, el error es esperado — ignorar
            if "already exists" in str(e) or "cannot be cast" in str(e).lower() or "text" in str(e).lower():
                pass
            else:
                print(f"  ⚠  {col_name}: {e}")

    # 3. Añadir comp_backend si no existe
    try:
        cur.execute("ALTER TABLE initiatives ADD COLUMN IF NOT EXISTS comp_backend TEXT")
        print(f"  → Columna 'comp_backend' añadida ✓")
    except Exception as e:
        print(f"  ⚠  comp_backend: {e}")


def migrate():
    rows = load_excel()
    if not rows:
        print("No hay datos para migrar.")
        return

    print(f"Conectando a PostgreSQL: {DB_URL.split('@')[-1]} ...")
    ensure_database_exists()
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    # Crear tabla con schema completo
    cur.execute(DDL_CREATE)
    conn.commit()
    print("  → Tabla 'initiatives' verificada/creada ✓")

    # Aplicar cambios de schema sobre tabla existente
    apply_schema_changes(cur)
    conn.commit()
    print("  → Schema actualizado ✓")

    # Upsert de todos los datos
    execute_values(cur, UPSERT_SQL, rows)
    conn.commit()
    print(f"  → {len(rows)} filas insertadas/actualizadas ✓")

    cur.close()
    conn.close()
    print("\n✅  Migración completada con todas las columnas del Excel.")
    print("   Reinicia el servidor para que la API exponga los nuevos campos.\n")


if __name__ == "__main__":
    migrate()
