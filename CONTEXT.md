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

## Historial de cambios solicitados por el usuario

Este historial recoge qué se pidió y qué se hizo, para retomar contexto fácilmente.

---

### Mar 10, 2026 — Animación del asistente

**Petición:** Mejorar la animación del botón/widget del asistente, usando como referencia el proyecto `spa-esmsweb-develop` (se proporcionó un zip con el código de `AIAssistantChat`).

**Iteraciones:**
1. Se interpretó erróneamente el zip como el proyecto principal en lugar de referencia → se corrigió.
2. Se añadió `lottie-web` via CDN y se copiaron `loading.json` y `standby.json` a `static/animations/`.
3. Primer intento: animación Lottie `loading` en el typing indicator + puntitos CSS en mensajes → el usuario indicó que esa animación debería ir en el **botón FAB**, no en el chat.
4. Se limpió el chat (sin iconos en burbujas, typing indicator vuelve a `…`) y se puso el Lottie en el botón FAB.
5. Se usó `loading.json` en el FAB → el usuario indicó que esa es la animación de "ejecutando", no la inicial → se cambió a `standby.json`.
6. Se movió el botón FAB de **esquina inferior derecha** a **esquina superior derecha** (dentro del header) porque se cruzaba con datos.
7. Se corrigieron 2 warnings de VS Code: `display: none` mezclado con propiedades flex en la misma regla CSS.
8. Se limpió la función `toggleChat` que sobreescribía `innerHTML` del icono (código obsoleto del sistema anterior).

**Estado resultante:** FAB en `top: 4px; right: 16px` con animación `standby.json`. Panel abre hacia abajo desde el header. Chat interior limpio.

---

### Mar 11, 2026 — Dark Mode

**Petición:** Añadir dark mode a la app.

**Implementación:**
- Variables dark mode en `[data-theme="dark"]` sobre `<html>` — invierte escala de grises y ajusta azul a `#4d8eff` y blue-light a `#0d1f40`.
- Botón toggle (icono luna/sol) en `.header-right`, controlado con CSS puro + selector `[data-theme="dark"]`.
- JS: función `toggleTheme()` en el primer `<script>` + IIFE de inicialización que lee `localStorage('theme')` antes del render.
- Overrides adicionales para los colores hardcodeados más visibles (prioridades, banners de descarte, chat, kanban, export button).
- La preferencia persiste en `localStorage`.

**Estado:** Completado. Botón luna/sol en header superior derecho.

---

## Estado actual (última actualización: Mar 11, 2026)

- Botón FAB del asistente en esquina superior derecha con animación Lottie `standby.json`.
- CSS limpio: sin warnings de VS Code en el bloque del chat widget.
- Panel de chat funcional con sugerencias, historial, y conexión a `/api/chat`.
- **Dark mode** implementado con toggle luna/sol en el header. Persiste en localStorage.
