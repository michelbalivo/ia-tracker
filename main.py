"""
IA Portfolio Tracker — Backend FastAPI (PostgreSQL)
────────────────────────────────────────────────────
Requiere DATABASE_URL en .env o como variable de entorno:
    DATABASE_URL=postgresql://usuario:password@localhost:5432/ia_tracker

Para poblar la base de datos desde Excel (primera vez):
    python migrate_from_excel.py
"""

import os, math
from pathlib import Path
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

app = FastAPI(title="IA Portfolio Tracker")
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
    return False

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

    componentes = {
        "ocr":      to_bool(row["comp_ocr"]),
        "frontend": to_bool(row["comp_frontend"]),
        "modelo":   to_bool(row["comp_modelo"]),
        "bbdd":     to_bool(row["comp_bbdd"]),
        "api":      to_bool(row["comp_api"]),
        "cluster":  to_bool(row["comp_cluster"]),
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
        "id":             row["id"],
        "name":           row["name"],
        "dept":           row["dept"],
        "proceso":        row["proceso"],
        "dominio":        row["dominio"],
        "estado":         estado,
        "estado_excel":   row["estado_excel"],
        "desc":           row["desc_ejecutiva"],
        "retorno":        row["retorno"],
        "tipo_retorno":   row["tipo_retorno"],
        "modelo_ia":      row["modelo_ia"],
        "equipo":         row["equipo"],
        "responsable":    row["responsable"],
        "disponibilidad": row["disponibilidad"],
        "riesgos":        row["riesgos"],
        "compliance":     row["compliance"],
        "complejidad":    row["complejidad"],
        "viabilidad":     row["viabilidad"],
        "fecha":          fmt_date(row["fecha_fin"]),
        "fecha_inicio":   fmt_date(row["fecha_inicio"]),
        "tier":           tier_pct,
        "prioridad":      row["prioridad"],
        "ahorro":         float(row["ahorro"]) if row["ahorro"] else 0,
        "usuarios":       row["usuarios"],
        "objetivo":       row["objetivo"],
        "alerta":         to_bool(row["alerta"]),
        "link_devhub":    row["link_devhub"],
        "fases":          fases,
        "componentes":    componentes if any(componentes.values()) else None,
        "radar":          radar if has_radar else None,
        "viabilidadBars": viab_bars if has_viab else None,
        "complejidadBars": comp_bars if has_comp else None,
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
    name:        str | None = None
    dept:        str | None = None
    estado:      str | None = None
    equipo:      str | None = None
    responsable: str | None = None
    prioridad:   str | None = None
    tipo_retorno: str | None = None
    dominio:     str | None = None
    proceso:     str | None = None
    desc:        str | None = None

@app.patch("/api/initiatives/{iid}")
def update_initiative(iid: int, body: InitiativeUpdate):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        fields = []
        values = []
        data = body.dict(exclude_none=True)
        col_map = {"desc": "desc_ejecutiva", "estado": "estado_override", "tipo_retorno": "tipo_retorno"}
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
        cur.close(); conn.close()
        return {"ok": True, "id": iid}
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
