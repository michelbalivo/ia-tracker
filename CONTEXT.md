# CONTEXT — IA Portfolio Tracker

> **Instrucción para Claude:** Al inicio de cada sesión, lee este fichero. Al final de cada iteración que implique una decisión de diseño, arquitectura, UX o técnica relevante, actualiza las secciones correspondientes. No añadas ruido — solo lo que cambia o se decide por primera vez.

---

## ¿Qué es este proyecto?

Aplicación web para el seguimiento y gestión del portfolio de iniciativas de Inteligencia Artificial de SSCC (Servicios Corporativos). Permite visualizar, filtrar, editar y analizar iniciativas IA con vistas de lista, Kanban, Gantt y detalle.

Incluye un **asistente IA conversacional** integrado como widget flotante que tiene acceso completo a la base de datos del portfolio y responde en español.

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Backend | Python · FastAPI |
| Base de datos | PostgreSQL (Railway) |
| Frontend | HTML + CSS + JS vanilla — **todo en un único fichero** `static/index.html` |
| Asistente IA | Anthropic API · modelo `claude-haiku-4-5-20251001` |
| Animaciones | `lottie-web` 5.12.2 via CDN (cdnjs) |
| Despliegue | Railway (auto-deploy desde GitHub) |
| Repo | github.com/michelbalivo/ia-tracker |

---

## Estructura de ficheros relevante

```
ia-tracker/
├── main.py                  # FastAPI app, endpoints API y endpoint /api/chat
├── static/
│   ├── index.html           # TODO el frontend (HTML + CSS + JS en un solo fichero)
│   └── animations/
│       ├── standby.json     # Animación idle del asistente (usada en botón FAB)
│       └── loading.json     # Animación de carga/pensando (disponible, actualmente no usada en UI)
├── migrate_from_excel.py
├── requirements.txt
└── CONTEXT.md               # Este fichero
```

---

## Decisiones tomadas

### Frontend / Arquitectura
- **Un solo fichero HTML.** Todo el CSS y JS vive en `static/index.html`. Es una decisión deliberada para simplificar el despliegue. No hay bundler ni framework.
- **El backend sirve el HTML directamente** desde la ruta `/` via FastAPI `HTMLResponse`. Los estáticos se sirven en `/static/`.

### Asistente IA (chat widget)
- El widget es un **botón FAB circular** en la esquina **superior derecha** del header, fijo en pantalla.
- Al abrirse, muestra un panel de chat que se despliega hacia abajo desde el header.
- Posición actual del FAB: `position: fixed; top: 4px; right: 16px` — centrado en el header de 56px.
- El panel abre con `top: 60px; right: 16px` y `transform-origin: top right`.
- La visibilidad del icono X y la animación Lottie se controla **solo con CSS** (clase `.open`), sin manipulación de `innerHTML` desde JS.

### Animaciones del asistente
- La referencia de animaciones viene del proyecto `spa-esmsweb-develop` (repo React/TS con microfrontends), específicamente de `GreetingWithAnimation/animations/blue/`.
- Estados disponibles en esa librería: `standby`, `loading`, `speaking`, `listening`, `icon`.
- **Botón FAB (cerrado):** usa `standby.json` — la animación de reposo del asistente.
- **Botón FAB (abierto):** muestra una X sobre fondo azul `#1a1aff`, gestionado por CSS.
- **Typing indicator:** actualmente muestra `…` en texto. El `loading.json` está disponible en `/static/animations/` si se quiere usar en el futuro.
- Decisión: **no hay iconos ni animaciones dentro de las burbujas del chat** — el panel queda limpio.

### CSS
- Regla: nunca mezclar `display: none` con propiedades flex (`align-items`, `justify-content`) en la misma regla CSS — VS Code lo marca como warning. Separar siempre en dos reglas.
- Los estilos responsive usan `@media` queries — los selectores duplicados entre media queries son intencionados, no son errores.

### Despliegue
- Railway hace auto-deploy al hacer push a `master`.
- El entorno sandbox de Claude **no puede hacer push a GitHub** (proxy bloquea con 403). Los commits se hacen desde el sandbox pero el push debe hacerlo el usuario desde su terminal.
- Flujo habitual: Claude hace cambios + commit → usuario hace `git push origin master`.

---

## Estado actual (última actualización: Mar 10, 2026)

- Botón FAB del asistente reposicionado a esquina superior derecha con animación Lottie `standby.json`.
- CSS limpio: sin duplicados en el bloque del chat widget, sin warnings de VS Code en ese bloque.
- Panel de chat funcional con sugerencias, historial, y conexión a `/api/chat`.
