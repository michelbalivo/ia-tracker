"""
migrate_from_excel.py
─────────────────────
Vuelca data.xlsx a PostgreSQL y crea la tabla si no existe.
Ejecutar UNA VEZ (o cuando se quiera re-importar desde Excel):

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

BASE         = Path(__file__).parent
EXCEL_PATH   = BASE / "data.xlsx"
OVERRIDES_PATH = BASE / "status_overrides.json"
DB_URL       = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ia_tracker")

# ── DDL ────────────────────────────────────────────────────────────
DDL = """
CREATE TABLE IF NOT EXISTS initiatives (
    id                  INTEGER PRIMARY KEY,
    name                TEXT,
    dept                TEXT,
    proceso             TEXT,
    dominio             TEXT,
    estado_excel        TEXT,
    estado_override     TEXT,           -- override manual (reemplaza status_overrides.json)
    desc_ejecutiva      TEXT,
    retorno             TEXT,
    tipo_retorno        TEXT,
    modelo_ia           TEXT,
    equipo              TEXT,
    responsable         TEXT,
    disponibilidad      TEXT,
    riesgos             TEXT,
    compliance          TEXT,
    complejidad         TEXT,
    viabilidad          TEXT,
    fecha_fin           DATE,
    fecha_inicio        DATE,
    prioridad           TEXT,
    ahorro              NUMERIC,
    usuarios            TEXT,
    objetivo            TEXT,
    alerta              BOOLEAN,
    link_devhub         TEXT,
    tier                NUMERIC,        -- 0-1 (raw del Excel)
    reach               NUMERIC,
    impact              NUMERIC,
    confidence          NUMERIC,
    effort              NUMERIC,
    ai_complexity       NUMERIC,
    score_viabilidad    NUMERIC,
    score_complejidad   NUMERIC,
    comp_ocr            BOOLEAN,
    comp_frontend       BOOLEAN,
    comp_modelo         BOOLEAN,
    comp_bbdd           BOOLEAN,
    comp_api            BOOLEAN,
    comp_cluster        BOOLEAN,
    fase_inicio         DATE,
    fase_analisis       DATE,
    fase_priorizacion   DATE,
    fase_diseno         DATE,
    fase_piloto         DATE,
    fase_iteracion      DATE,
    fase_mantenimiento  DATE,
    updated_at          TIMESTAMP DEFAULT NOW()
);
"""


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
    if isinstance(v, (int, float)): return v > 0
    if isinstance(v, str): return v.strip().lower() in ("sí","si","yes","true","1","x","✓")
    return False


# ── Leer Excel ─────────────────────────────────────────────────────
def load_excel():
    print(f"Leyendo {EXCEL_PATH.name} ...")
    df = pd.read_excel(EXCEL_PATH, sheet_name="Seguimiento IA", header=1)

    # Cargar overrides existentes para no perder estados cambiados manualmente
    overrides = {}
    if OVERRIDES_PATH.exists():
        overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        print(f"  → {len(overrides)} overrides de estado encontrados en {OVERRIDES_PATH.name}")

    rows = []
    for _, row in df.iterrows():
        raw_id = row.get("Id")
        if pd.isna(raw_id): continue
        try: iid = int(raw_id)
        except: continue

        def col(name): return safe(row.get(name))
        def flt(name): return safe_float(row.get(name))

        name = col("Descripción resumida de la iniciativa")
        if not name: continue

        estado_excel = col("Estado Iniciativa") or "Pendiente"
        estado_override = overrides.get(str(iid))   # None si no hay override

        rows.append((
            iid,
            name,
            col("Departamento"),
            col("Proceso impactado"),
            col("Dominio funcional de IA"),
            estado_excel,
            estado_override,
            col("Descripción ejecutiva"),
            col("Retorno esperado"),
            col("Tipo de Retorno"),
            col("Modelo / Proveedor de IA"),
            col("Equipo IA Asignado"),
            col("Responsable"),
            col("Disponibilidad de datos"),
            col("Principales riesgos"),
            col("Impacto en compliance"),
            col("Complejidad"),
            col("Viabilidad"),
            col("Fin Estimado"),
            col("Inicio"),
            col("Prioridad sugerida"),
            flt("Ahorro estimado (€ / año)"),
            col("Usuarios Impactados"),
            col("Objetivo estratégico"),
            to_bool(row.get("Alerta")),
            col("Link DevHub"),
            flt("TIER"),
            flt("Reach"),
            flt("Impact"),
            flt("Confidence"),
            flt("Effort"),
            flt("AI Complexity"),
            flt("Socre Viabilidad"),
            flt("Score Complejidad"),
            to_bool(row.get("OCR")),
            to_bool(row.get("Front End")),
            to_bool(row.get("Modelo IA")),
            to_bool(row.get("BBDD")),
            to_bool(row.get("API")),
            to_bool(row.get("Cluster Comp")),
            col("Inicio"),
            col("Análisis"),
            col("Priorización"),
            col("Diseño"),
            col("Piloto"),
            col("Iteración / Pruebas"),
            col("Mantenimiento"),
        ))

    print(f"  → {len(rows)} iniciativas leídas")
    return rows


# ── Insertar en PostgreSQL ─────────────────────────────────────────
COLUMNS = """
    id, name, dept, proceso, dominio,
    estado_excel, estado_override, desc_ejecutiva, retorno, tipo_retorno,
    modelo_ia, equipo, responsable, disponibilidad, riesgos, compliance,
    complejidad, viabilidad, fecha_fin, fecha_inicio,
    prioridad, ahorro, usuarios, objetivo, alerta, link_devhub,
    tier, reach, impact, confidence, effort, ai_complexity,
    score_viabilidad, score_complejidad,
    comp_ocr, comp_frontend, comp_modelo, comp_bbdd, comp_api, comp_cluster,
    fase_inicio, fase_analisis, fase_priorizacion, fase_diseno,
    fase_piloto, fase_iteracion, fase_mantenimiento
"""

UPSERT_SQL = f"""
INSERT INTO initiatives ({COLUMNS})
VALUES %s
ON CONFLICT (id) DO UPDATE SET
    name               = EXCLUDED.name,
    dept               = EXCLUDED.dept,
    proceso            = EXCLUDED.proceso,
    dominio            = EXCLUDED.dominio,
    estado_excel       = EXCLUDED.estado_excel,
    desc_ejecutiva     = EXCLUDED.desc_ejecutiva,
    retorno            = EXCLUDED.retorno,
    tipo_retorno       = EXCLUDED.tipo_retorno,
    modelo_ia          = EXCLUDED.modelo_ia,
    equipo             = EXCLUDED.equipo,
    responsable        = EXCLUDED.responsable,
    disponibilidad     = EXCLUDED.disponibilidad,
    riesgos            = EXCLUDED.riesgos,
    compliance         = EXCLUDED.compliance,
    complejidad        = EXCLUDED.complejidad,
    viabilidad         = EXCLUDED.viabilidad,
    fecha_fin          = EXCLUDED.fecha_fin,
    fecha_inicio       = EXCLUDED.fecha_inicio,
    prioridad          = EXCLUDED.prioridad,
    ahorro             = EXCLUDED.ahorro,
    usuarios           = EXCLUDED.usuarios,
    objetivo           = EXCLUDED.objetivo,
    alerta             = EXCLUDED.alerta,
    link_devhub        = EXCLUDED.link_devhub,
    tier               = EXCLUDED.tier,
    reach              = EXCLUDED.reach,
    impact             = EXCLUDED.impact,
    confidence         = EXCLUDED.confidence,
    effort             = EXCLUDED.effort,
    ai_complexity      = EXCLUDED.ai_complexity,
    score_viabilidad   = EXCLUDED.score_viabilidad,
    score_complejidad  = EXCLUDED.score_complejidad,
    comp_ocr           = EXCLUDED.comp_ocr,
    comp_frontend      = EXCLUDED.comp_frontend,
    comp_modelo        = EXCLUDED.comp_modelo,
    comp_bbdd          = EXCLUDED.comp_bbdd,
    comp_api           = EXCLUDED.comp_api,
    comp_cluster       = EXCLUDED.comp_cluster,
    fase_inicio        = EXCLUDED.fase_inicio,
    fase_analisis      = EXCLUDED.fase_analisis,
    fase_priorizacion  = EXCLUDED.fase_priorizacion,
    fase_diseno        = EXCLUDED.fase_diseno,
    fase_piloto        = EXCLUDED.fase_piloto,
    fase_iteracion     = EXCLUDED.fase_iteracion,
    fase_mantenimiento = EXCLUDED.fase_mantenimiento,
    updated_at         = NOW()
    -- estado_override se preserva en el UPDATE (no se sobreescribe desde Excel)
"""


def ensure_database_exists():
    """Crea la base de datos si no existe, conectándose primero a 'postgres'."""
    from urllib.parse import urlparse
    parsed  = urlparse(DB_URL)
    db_name = parsed.path.lstrip("/")
    # URL apuntando a la BD 'postgres' (siempre existe)
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


def migrate():
    rows = load_excel()
    if not rows:
        print("No hay datos para migrar.")
        return

    print(f"Conectando a PostgreSQL: {DB_URL.split('@')[-1]} ...")
    ensure_database_exists()
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    # Crear tabla
    cur.execute(DDL)
    conn.commit()
    print("  → Tabla 'initiatives' verificada/creada")

    # Upsert
    execute_values(cur, UPSERT_SQL, rows)
    conn.commit()
    print(f"  → {len(rows)} filas insertadas/actualizadas en PostgreSQL ✓")

    cur.close()
    conn.close()
    print("\n✅  Migración completada.")
    print("   Puedes arrancar el servidor: python main.py")
    print("   (El archivo data.xlsx ya no es necesario para el funcionamiento)\n")


if __name__ == "__main__":
    migrate()
