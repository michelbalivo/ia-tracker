"""
IA Portfolio Tracker — Backend FastAPI (PostgreSQL)
────────────────────────────────────────────────────
Requiere DATABASE_URL en .env o como variable de entorno:
    DATABASE_URL=postgresql://usuario:password@localhost:5432/ia_tracker

Para poblar la base de datos desde Excel (primera vez):
    python migrate_from_excel.py
"""

import os, math, threading, json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

BASE        = Path(__file__).parent
STATIC_PATH = BASE / "static"
DB_URL      = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ia_tracker")


def run_migration():
    """Ejecuta la migración en un hilo separado para no bloquear el startup."""
    try:
        import migrate_from_excel
        migrate_from_excel.migrate()
        print("✅ Migración completada en background.")
    except Exception as e:
        print(f"⚠️  Error en migración background: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migración automática DESACTIVADA — los datos ya están en PostgreSQL.
    # Para resetear desde Excel ejecutar manualmente: python migrate_from_excel.py
    # t = threading.Thread(target=run_migration, daemon=True)
    # t.start()
    yield
    # (shutdown — nada que limpiar)


app = FastAPI(title="IA Portfolio Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")


# ── Conexión ────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


# ── Helpers de cálculo (misma lógica que antes) ────────────────────
def normalize_10(v, scale=1.0):
    try:
        f = float(v or 0) * scale
        return round(min(10.0, max(0.0, f)), 1)
    except:
        return 0.0

def to_bool(v):
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return v > 0
    if isinstance(v, str): return v.strip().lower() not in ("", "none", "false", "0", "nan")
    return False

def safe_get(row, key, default=None):
    """Lee un campo del row sin error si la columna aún no existe."""
    try:
        return row.get(key, default)
    except Exception:
        return default

def row_to_initiative(row: dict) -> dict:
    """Convierte una fila de PostgreSQL al modelo que espera el frontend."""

    tier_raw   = float(row["tier"] or 0)
    tier_pct   = round(tier_raw * 100)

    reach      = normalize_10(row["reach"])
    impact     = normalize_10(row["impact"])
    confidence = normalize_10(row["confidence"])
    effort     = normalize_10(row["effort"])
    ai_comp    = normalize_10(row["ai_complexity"])
    sc_viab    = normalize_10(row["score_viabilidad"], scale=3.33)
    sc_comp    = normalize_10((4 - float(row["score_complejidad"] or 2)), scale=3.33)
    tier10     = normalize_10(tier_raw * 10)

    radar = [reach, impact, confidence, normalize_10(10 - effort),
             normalize_10(10 - float(row["ai_complexity"] or 0)),
             sc_viab, sc_comp, tier10]
    has_radar = any(v > 0 for v in radar)

    viab_bars = [reach, impact, confidence, sc_viab, tier10]
    has_viab  = any(v > 0 for v in viab_bars)

    comp_bars = [effort, ai_comp,
                 normalize_10(float(row["score_complejidad"] or 0), scale=3.33),
                 normalize_10(10 - float(row["confidence"] or 0)),
                 normalize_10(10 - tier_raw * 10)]
    has_comp  = any(v > 0 for v in comp_bars)

    # comp_* son ahora TEXT con el nombre real de la herramienta (o None)
    componentes = {
        "ocr":       safe_get(row, "comp_ocr"),
        "frontend":  safe_get(row, "comp_frontend"),
        "modelo":    safe_get(row, "comp_modelo"),
        "bbdd":      safe_get(row, "comp_bbdd"),
        "api":       safe_get(row, "comp_api"),
        "cluster":   safe_get(row, "comp_cluster"),
        "backend":   safe_get(row, "comp_backend"),
        "mcp":       safe_get(row, "comp_mcp"),
        "rag":       safe_get(row, "comp_rag"),
        "prompting": safe_get(row, "comp_prompting"),
    }

    def fmt_date(d):
        if d is None: return None
        try: return d.strftime("%Y-%m-%d")
        except: return None

    fases = {
        "Inicio":              fmt_date(row["fase_inicio"]),
        "Análisis":            fmt_date(row["fase_analisis"]),
        "Priorización":        fmt_date(row["fase_priorizacion"]),
        "Diseño":              fmt_date(row["fase_diseno"]),
        "Piloto":              fmt_date(row["fase_piloto"]),
        "Iteración / Pruebas": fmt_date(row["fase_iteracion"]),
        "Mantenimiento":       fmt_date(row["fase_mantenimiento"]),
    }

    # Estado: override manual tiene prioridad sobre el del Excel
    estado = row["estado_override"] or row["estado_excel"] or "Pendiente"

    return {
        # ── Identificación ──────────────────────────────────────────
        "id":                     row["id"],
        "name":                   row["name"],
        "dept":                   row["dept"],
        "estado":                 estado,
        "estado_excel":           row["estado_excel"],
        "desc":                   row["desc_ejecutiva"],

        # ── Proceso ─────────────────────────────────────────────────
        "proceso":                row["proceso"],
        "clasificacion_proceso":  safe_get(row, "clasificacion_proceso"),
        "criticidad_proceso":     safe_get(row, "criticidad_proceso"),
        "volumen_proceso":        float(safe_get(row, "volumen_proceso") or 0) or None,

        # ── Tipología IA ────────────────────────────────────────────
        "dominio":                row["dominio"],
        "tipo_ia":                safe_get(row, "tipo_ia"),
        "tip_ocr":                to_bool(safe_get(row, "tip_ocr")),
        "tip_generativa":         to_bool(safe_get(row, "tip_generativa")),
        "tip_analitica":          to_bool(safe_get(row, "tip_analitica")),
        "tip_predictiva":         to_bool(safe_get(row, "tip_predictiva")),
        "modelo_ia":              row["modelo_ia"],

        # ── Viabilidad ──────────────────────────────────────────────
        "viabilidad":             row["viabilidad"],
        "viabilidad_puntos":      float(safe_get(row, "viabilidad_puntos") or 0) or None,
        "datos_requeridos":       safe_get(row, "datos_requeridos"),
        "disponibilidad":         row["disponibilidad"],
        "madurez_funcional":      safe_get(row, "madurez_funcional"),

        # ── Complejidad ─────────────────────────────────────────────
        "time_to_value":          safe_get(row, "time_to_value"),
        "complejidad":            row["complejidad"],
        "complejidad_tecnica":    safe_get(row, "complejidad_tecnica"),
        "complejidad_organizativa": safe_get(row, "complejidad_organizativa"),

        # ── Retorno / ROI ───────────────────────────────────────────
        "retorno":                row["retorno"],
        "tipo_retorno":           row["tipo_retorno"],
        "impacto_negocio":        safe_get(row, "impacto_negocio"),
        "ahorro":                 float(row["ahorro"]) if row["ahorro"] else 0,
        "roi_business_case":      float(safe_get(row, "roi_business_case") or 0) or None,

        # ── Priorización ────────────────────────────────────────────
        "prioridad":              row["prioridad"],
        "usuarios":               row["usuarios"],
        "objetivo":               row["objetivo"],

        # ── Scores y tier ───────────────────────────────────────────
        "tier":                   tier_pct,
        "ric":                    float(safe_get(row, "ric") or 0) or None,
        "radar":                  radar if has_radar else None,
        "viabilidadBars":         viab_bars if has_viab else None,
        "complejidadBars":        comp_bars if has_comp else None,

        # ── Riesgos / Compliance ────────────────────────────────────
        "riesgos":                row["riesgos"],
        "compliance":             row["compliance"],

        # ── Fechas ──────────────────────────────────────────────────
        "fecha":                  fmt_date(row["fecha_fin"]),
        "fecha_inicio":           fmt_date(row["fecha_inicio"]),
        "fecha_registro":         fmt_date(safe_get(row, "fecha_registro")),
        "powerapps_id":           safe_get(row, "powerapps_id"),
        "fases":                  fases,

        # ── Equipo ──────────────────────────────────────────────────
        "equipo":                 row["equipo"],
        "responsable":            row["responsable"],

        # ── Arquitectura (texto real de la herramienta) ─────────────
        "componentes":            componentes if any(v for v in componentes.values()) else None,

        # ── Misc ────────────────────────────────────────────────────
        "alerta":                 to_bool(row["alerta"]),
        "link_devhub":            row["link_devhub"],
    }


# ── Endpoints ───────────────────────────────────────────────────────

@app.get("/api/initiatives")
def get_initiatives():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM initiatives ORDER BY id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [row_to_initiative(dict(r)) for r in rows]
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=503,
            detail=f"No se puede conectar a PostgreSQL: {e}. ¿Está corriendo la base de datos?")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/initiatives/{iid}")
def get_initiative(iid: int):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM initiatives WHERE id = %s", (iid,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="No encontrado")
        return row_to_initiative(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InitiativeCreate(BaseModel):
    name: str
    dept: str | None = None
    proceso: str | None = None
    dominio: str | None = None
    estado: str = "Pendiente"
    desc: str | None = None
    tipo_retorno: str | None = None
    objetivo: str | None = None
    ahorro: float = 0
    usuarios: str | None = None
    equipo: str | None = None
    responsable: str | None = None
    modelo_ia: str | None = None
    prioridad: str | None = None
    reach: float | None = None
    impact: float | None = None
    confidence: float | None = None
    effort: float | None = None
    ai_complexity: float | None = None
    tier: float | None = None
    fase_inicio: str | None = None
    fase_analisis: str | None = None
    fase_priorizacion: str | None = None
    fase_diseno: str | None = None
    fase_piloto: str | None = None
    fase_iteracion: str | None = None
    fase_mantenimiento: str | None = None
    fecha_fin: str | None = None

@app.post("/api/initiatives", status_code=201)
def create_initiative(body: InitiativeCreate):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        # Auto-asignar el siguiente ID
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM initiatives")
        new_id = cur.fetchone()["next_id"]
        cur.execute("""
            INSERT INTO initiatives (
                id, name, dept, proceso, dominio, estado_excel,
                desc_ejecutiva, tipo_retorno, objetivo, ahorro, usuarios,
                equipo, responsable, modelo_ia, prioridad,
                reach, impact, confidence, effort, ai_complexity, tier,
                fase_inicio, fase_analisis, fase_priorizacion, fase_diseno,
                fase_piloto, fase_iteracion, fase_mantenimiento, fecha_fin
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
        """, (
            new_id, body.name, body.dept, body.proceso, body.dominio, body.estado,
            body.desc, body.tipo_retorno, body.objetivo, body.ahorro, body.usuarios,
            body.equipo, body.responsable, body.modelo_ia, body.prioridad,
            body.reach, body.impact, body.confidence, body.effort, body.ai_complexity,
            body.tier,
            body.fase_inicio, body.fase_analisis, body.fase_priorizacion, body.fase_diseno,
            body.fase_piloto, body.fase_iteracion, body.fase_mantenimiento, body.fecha_fin,
        ))
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InitiativeUpdate(BaseModel):
    # Identificación
    name:                     str | None = None
    dept:                     str | None = None
    desc:                     str | None = None   # → desc_ejecutiva
    objetivo:                 str | None = None
    dominio:                  str | None = None
    proceso:                  str | None = None
    clasificacion_proceso:    str | None = None
    criticidad_proceso:       str | None = None
    volumen_proceso:          float | None = None
    tipo_ia:                  str | None = None
    tip_ocr:                  bool | None = None
    tip_generativa:           bool | None = None
    tip_analitica:            bool | None = None
    tip_predictiva:           bool | None = None
    modelo_ia:                str | None = None
    usuarios:                 str | None = None
    powerapps_id:             str | None = None
    link_devhub:              str | None = None
    # Evaluación
    viabilidad:               str | None = None
    score_viabilidad:         float | None = None
    viabilidad_puntos:        float | None = None
    datos_requeridos:         str | None = None
    disponibilidad:           str | None = None
    madurez_funcional:        str | None = None
    time_to_value:            str | None = None
    complejidad:              str | None = None
    score_complejidad:        float | None = None
    complejidad_tecnica:      str | None = None
    complejidad_organizativa: str | None = None
    riesgos:                  str | None = None
    compliance:               str | None = None
    # ROI & Prioridad
    retorno:                  str | None = None
    tipo_retorno:             str | None = None
    impacto_negocio:          str | None = None
    ahorro:                   float | None = None
    prioridad:                str | None = None
    roi_business_case:        float | None = None
    reach:                    float | None = None
    impact:                   float | None = None
    confidence:               float | None = None
    effort:                   float | None = None
    ai_complexity:            float | None = None
    ric:                      float | None = None
    tier:                     float | None = None
    # Seguimiento
    estado:                   str | None = None   # → estado_override
    alerta:                   bool | None = None
    equipo:                   str | None = None
    responsable:              str | None = None
    fecha_registro:           str | None = None
    fecha_inicio:             str | None = None
    fecha_fin:                str | None = None
    # Fases
    fase_inicio:              str | None = None
    fase_analisis:            str | None = None
    fase_priorizacion:        str | None = None
    fase_piloto:              str | None = None
    fase_diseno:              str | None = None
    fase_iteracion:           str | None = None
    fase_mantenimiento:       str | None = None
    # Componentes técnicos
    comp_bbdd:                str | None = None
    comp_ocr:                 str | None = None
    comp_cluster:             str | None = None
    comp_api:                 str | None = None
    comp_backend:             str | None = None
    comp_modelo:              str | None = None
    comp_mcp:                 str | None = None
    comp_rag:                 str | None = None
    comp_prompting:           str | None = None
    comp_frontend:            str | None = None

@app.patch("/api/initiatives/{iid}")
def update_initiative(iid: int, body: InitiativeUpdate):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        fields = []
        values = []
        data = body.dict(exclude_none=True)
        # Mapeo de nombres de payload → columnas reales en DB
        col_map = {
            "desc":     "desc_ejecutiva",
            "estado":   "estado_override",
        }
        for k, v in data.items():
            col = col_map.get(k, k)
            fields.append(f"{col} = %s")
            values.append(v)
        if not fields:
            cur.close(); conn.close()
            return {"ok": True, "id": iid}
        fields.append("updated_at = NOW()")
        values.append(iid)
        cur.execute(f"UPDATE initiatives SET {', '.join(fields)} WHERE id = %s", values)
        if cur.rowcount == 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="No encontrado")
        conn.commit()
        # Devolver la iniciativa actualizada completa
        cur.execute("SELECT * FROM initiatives WHERE id = %s", (iid,))
        updated = cur.fetchone()
        cur.close(); conn.close()
        return row_to_initiative(dict(updated))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/initiatives/{iid}")
def delete_initiative(iid: int):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("DELETE FROM initiatives WHERE id = %s", (iid,))
        if cur.rowcount == 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="No encontrado")
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": iid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class StatusUpdate(BaseModel):
    status: str

@app.post("/api/initiatives/{iid}/status")
def update_status(iid: int, body: StatusUpdate):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE initiatives SET estado_override = %s, updated_at = NOW() WHERE id = %s",
            (body.status, iid)
        )
        if cur.rowcount == 0:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="No encontrado")
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": iid, "status": body.status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/initiatives/{iid}/status")
def reset_status(iid: int):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE initiatives SET estado_override = NULL, updated_at = NOW() WHERE id = %s",
            (iid,)
        )
        conn.commit()
        cur.close(); conn.close()
        return {"ok": True, "id": iid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ── Asistente IA ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    history: list[dict] = []   # [{role, content}, ...]

def _build_context(conn) -> str:
    """Serializa todas las iniciativas a texto estructurado para el contexto."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM initiatives ORDER BY id")
    rows = cur.fetchall()
    cur.close()

    lines = [f"Hay {len(rows)} iniciativas en el portfolio de IA:\n"]
    for r in rows:
        r = dict(r)
        estado = r.get("estado_override") or r.get("estado_excel") or "Pendiente"
        lines.append(
            f"- ID {r['id']}: {r['name'] or '(sin nombre)'} | "
            f"Dept: {r['dept'] or '—'} | Estado: {estado} | "
            f"Prioridad: {r['prioridad'] or '—'} | "
            f"Dominio: {r['dominio'] or '—'} | "
            f"Proceso: {r['proceso'] or '—'} | "
            f"Equipo: {r['equipo'] or '—'} | "
            f"Responsable: {r['responsable'] or '—'} | "
            f"Tipo IA: {r.get('tipo_ia') or '—'} | "
            f"Viabilidad: {r.get('viabilidad') or '—'} | "
            f"Complejidad: {r.get('complejidad') or '—'} | "
            f"Prioridad: {r.get('prioridad') or '—'} | "
            f"Alerta: {'Sí' if r.get('alerta') else 'No'} | "
            f"Retorno: {r.get('retorno') or '—'} | "
            f"Ahorro: {r.get('ahorro') or '—'} | "
            f"RIC: {r.get('ric') or '—'} | "
            f"TIER: {r.get('tier') or '—'} | "
            f"Fecha fin: {r.get('fecha_fin') or '—'} | "
            f"Objetivo: {(r.get('objetivo') or '')[:120] or '—'} | "
            f"Desc: {(r.get('desc_ejecutiva') or '')[:150] or '—'}"
        )
    return "\n".join(lines)

SYSTEM_PROMPT = """Eres un asistente especializado en el portfolio de iniciativas de Inteligencia Artificial de SSCC (Servicios Corporativos).
Tienes acceso a todos los datos actuales del portfolio. Responde siempre en español, de forma concisa y directa.
Puedes analizar, resumir, comparar y responder preguntas sobre las iniciativas.
Cuando listes iniciativas usa formato de lista clara. Si la pregunta no tiene relación con el portfolio, indícalo amablemente.
No inventes datos que no estén en el contexto."""

@app.post("/api/chat")
def chat_endpoint(body: ChatMessage):
    import traceback
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY no configurada")
    try:
        import anthropic
        conn = get_conn()
        context = _build_context(conn)
        conn.close()

        client = anthropic.Anthropic(api_key=api_key)

        # Historial + mensaje actual
        messages = []
        for h in body.history[-10:]:
            role    = h.get("role")    if isinstance(h, dict) else getattr(h, "role",    None)
            content = h.get("content") if isinstance(h, dict) else getattr(h, "content", None)
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": body.message})

        system = SYSTEM_PROMPT + "\n\n## DATOS ACTUALES DEL PORTFOLIO\n" + context

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=messages
        )
        return {"reply": resp.content[0].text}
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[chat] ERROR: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Servir frontend ─────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    html = STATIC_PATH / "index.html"
    if not html.exists():
        return HTMLResponse("<h1>Error: no se encuentra static/index.html</h1>", 500)
    return HTMLResponse(html.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    print("\n🚀  IA Portfolio Tracker → http://localhost:8000")
    print(f"    BD: {DB_URL.split('@')[-1]}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
