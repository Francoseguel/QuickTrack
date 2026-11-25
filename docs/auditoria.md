# Auditoría Técnica Inicial — Evaluación Parcial N°3 (QuickTrack)

**Fecha de auditoría:** 2026-11-24  
**Repositorio auditado:** `https://github.com/Francoseguel/QuickTrack` (commit base `cc68f88`)  
**Fuente de verdad de evaluación:** `EP3_BDY0101_Estudiante_B.pdf` (BDY0101 — Base de Datos No Relacionales, Duoc UC, Forma B)  
**Fuente de verdad de datos:** `data/*.json` (5 colecciones: `clientes`, `ordenes_entrega`, `rutas`, `seguimiento`, `valoraciones`)

---

## 1. Hallazgos Críticos de Seguridad

1. **Credencial real expuesta en `.env.example` (commit `cc68f88`):**
   - El archivo `.env.example` contenía una cadena `MONGO_URI` con usuario, contraseña real y host de clúster MongoDB Atlas.
   - Adicionalmente, las credenciales aparecen en el historial de conversaciones (`gemini1.txt` / `gemini2.txt`).
   - **Acción inmediata en el repo:** Sanitizar `.env.example` con placeholders genéricos (`<usuario>`, `<password>`, `<cluster>`) y reforzar `.gitignore` para cubrir `.env`, `.env.*` (con excepción `!.env.example`) y `*.log`.
   - **Acción manual obligatoria del equipo:** Rotar la contraseña del usuario de base de datos en MongoDB Atlas y, si se desea limpiar el historial Git público, evaluar un rewrite controlado (no se ejecutará `force push` sin confirmación explícita).

---

## 2. Verificación del Esquema Real (`data/*.json`)

| Colección | Formato | Docs | Campos reales verificados | Nulos/Vacíos | Integridad referencial |
|---|---|---:|---|---:|---|
| `clientes` | JSON Array | 100 | `_id` (int), `nombre`, `correo`, `pais`, `fecha_registro` (AAAA-MM-DD) | 0 | 100% enlazable con `cliente_num_id` |
| `ordenes_entrega` | JSON Lines | 100 | `_id` (`orden_N`), `cliente_id` (`cli_N`), `ruta_id` (`ruta_N`), `fecha_envio` (ISO), `estado`, `medio_pago`, `total` (float) | 0 | 0 huérfanos en `rutas` y `clientes` (normalizando `cli_N` → `N`) |
| `rutas` | JSON Lines | 100 | `_id` (`ruta_N`), `zona`, `ciudad_origen`, `ciudad_destino`, `distancia_km` (float) | 0 | 100% enlazable con `ordenes_entrega.ruta_id` |
| `seguimiento` | JSON Lines | 100 | `_id` (`seg_N`), `orden_id`, `estado_actual`, `historial` (`[{estado, fecha}]`, 302 eventos totales) | 0 | 0 huérfanos (`1:1` con `ordenes_entrega`) |
| `valoraciones` | JSON Lines | 100 | `_id` (`val_N`), `orden_id`, `puntaje` (1–5), `comentario` | 0 | 0 huérfanos (`1:1` con `ordenes_entrega`) |

### Hallazgos de calidad y métricas base reales
- **Período de `ordenes_entrega.fecha_envio`:** `2022-01-15` a `2024-06-22` (38 órdenes en 2022, 45 en 2023, 17 en 2024).
- **Facturación total:** `$10.939.612,72` | **Volumen:** `100` órdenes | **Ticket promedio:** `$109.396,13`.
- **Tasa de cumplimiento (`ordenes_entrega.estado == "Entregado"`):** `27,0 %` (27 Entregado, 29 En preparación, 21 En tránsito, 23 Cancelado).
- **Satisfacción promedio (`valoraciones.puntaje`):** `3,07 / 5,00` (37 valoraciones críticas ≤ 2).
- **Anomalía detectada en datos simulados:** En `82/100` órdenes existe discrepancia entre `ordenes_entrega.estado` y `seguimiento.estado_actual`, y las fechas del `historial` fueron generadas de forma independiente a `fecha_envio`. El ETL debe documentar esta discrepancia con transparencia (`discrepancia_estado_seg`), usar `ordenes_entrega.estado` como estado oficial de la orden y calcular la duración del ciclo (`dias_en_seguimiento` y `dias_hasta_entrega_historial`) exclusivamente desde `seguimiento.historial`.
- **Campos del enunciado ausentes en los datos:** `tiempo estimado`, `condiciones climáticas`, `motivo de retraso`, `recomendación`, `tipo de cliente`, `peso`, `tipo de envío`, `fecha_entrega`. No se inventarán; toda métrica de demora se derivará explícitamente de `seguimiento.historial`.

---

## 3. Errores Detectados en el Borrador (`Informe Técnico Evaluación Parcial 3 — QuickTrack.pdf`)

1. **ETL roto por campos inexistentes:** El script del borrador usa `ruta.id`, `ruta.zona`, `ruta.distancia_km` y `detalle_cliente.zona_geografica` (ninguno existe en `data/*.json`) y cruza `ordenes_entrega.cliente_id` (`"cli_N"`) contra `clientes._id` (`int`), lo que produce un `$lookup` vacío.
2. **Matriz RICE basada en atributos ficticios:** Incluye `foto_evidencia_url` y `color_tema_app` (provenientes del ejemplo clínico de la Actividad 3.1.1) y valores `R` inventados en lugar de cobertura empírica sobre las 5 colecciones reales.
3. **Cobertura incompleta de colecciones y consultas:** Solo cruza 3 colecciones (`ordenes_entrega`, `rutas`, `clientes`), omitiendo `valoraciones` (satisfacción) y `seguimiento` (`$unwind` sobre `historial` anidado), ambos críticos para responder al caso Forma B e IE1.
4. **Incoherencia en los 4 KPIs:** El borrador usa *Ticket Promedio* como 4° KPI y omite *Satisfacción Promedio*. Los 4 KPIs oficiales deben ser: (1) Facturación Total, (2) Volumen de Órdenes, (3) Tasa de Cumplimiento (% Entregado) y (4) Satisfacción Promedio; *Ticket Promedio* pasa a indicador secundario.
5. **Automatización (IE8, 20%) insuficiente:** Solo menciona "se actualiza al refrescar el dataset ETL" sin pipeline reproducible, sin programación (GitHub Actions / Task Scheduler) ni diseño de actualización en Power BI Service.
6. **Ausencia de activos de Power BI en el repositorio:** No existen `.pbix`, consultas M, medidas DAX, capturas ni boceto del dashboard en `docs/` o `powerbi/`.
7. **Placeholders sin resaltar:** Integrantes, fecha y captura del dashboard aparecen como texto plano sin listado formal de pendientes.

---

## 4. Brechas frente a la Rúbrica Oficial (IE1–IE8)

| IE | Ponderación | Estado inicial en repo/borrador | Plan de cierre |
|---|---:|---|---|
| **IE1** Consultas complejas NoSQL | 15% | Parcial (solo consultas EP2; borrador con ETL roto y 3 colecciones) | Pipelines MongoDB reales en `scripts/etl_analitica.py` cruzando las 5 colecciones, con `$lookup`, `$unwind` sobre `seguimiento.historial`, `$match`, `$addFields` y `$project` + modo `--source local` reproducible. |
| **IE2** Documentación y justificación de transformaciones | 15% | Deficiente (RICE con campos ficticios) | `scripts/rice_audit.py` empírico sobre las 5 colecciones, 3 tablas RICE por eje analítico (Preguntas 1, 2 y 3) y documentación de transformaciones estructurales, semánticas y de formato con conteos antes/después. |
| **IE3** Selección y justificación de Power BI | 5% | Aceptable en borrador (4 características) | Consolidar y afinar exactamente 4 características técnicas/funcionales vinculadas al caso QuickTrack en `powerbi/` y Sección 5 del informe. |
| **IE4** Conexiones funcionales NoSQL → BI | 5% | Roto en borrador | Exportación validada en modelo estrella (`data/export/*.csv`, UTF-8 con BOM), `scripts/validar_etl.py`, `powerbi/queries.m` parametrizado y endpoints `/analitica/*` en FastAPI como fuente alternativa. |
| **IE5** Modelado de datos para 4 KPIs | 10% | Incompleto (tabla plana sin modelo estrella ni satisfacción) | Modelo estrella (`fact_ordenes`, `fact_seguimiento_eventos`, `dim_rutas`, `dim_clientes`, `dim_fecha`) en `powerbi/modelo.md`, diagrama Mermaid exportado a PNG/SVG y 4 KPIs coherentes en DAX. |
| **IE6** Diseño de dashboard funcional e interactivo | 20% | Pendiente (.pbix del compañero no está en el repo) | Wireframe de alta fidelidad (`powerbi/boceto_dashboard.html` + SVG/PNG), `powerbi/medidas.dax`, `powerbi/guia_construccion.md` y marcador explícito `[PENDIENTE: captura del .pbix]`. |
| **IE7** Justificación del 100% de visualizaciones | 10% | Parcial (sin visualizaciones de satisfacción ni tiempos de seguimiento) | Matriz de justificación del 100% de visuales (tipo de dato, objetivo analítico, pregunta de negocio y área funcional). |
| **IE8** Reportes automatizados con KPIs | 20% | Ausente | `scripts/refresh_pipeline.py` (comando único ETL + validación + resumen), GitHub Actions `.github/workflows/refresh_analytics.yml` con cron y fallback local, guía de Windows Task Scheduler y arquitectura propuesta de Power BI Service / ADF. |

---

## 5. Plan de Ejecución

1. **Fase 1 (Extracción, RICE y Validación):** Crear `scripts/rice_audit.py`, `scripts/etl_analitica.py` (Atlas + `--source local`) y `scripts/validar_etl.py`; generar `data/export/*.csv` y verificar conteos y sumas.
2. **Fase 2 (Power BI):** Generar `powerbi/queries.m`, `powerbi/medidas.dax`, `powerbi/modelo.md`, `powerbi/guia_construccion.md` y `powerbi/boceto_dashboard.{html,png}`.
3. **Fase 3 (Automatización y API):** Crear `scripts/refresh_pipeline.py`, `.github/workflows/refresh_analytics.yml`, revisar/ampliar `/analitica/*` en `api/main.py` y documentar actualización programada.
4. **Fase 4 (Diagramas):** Generar diagramas Mermaid y exportarlos a PNG/SVG en `docs/diagramas/` (arquitectura del flujo de datos y modelo estrella).
5. **Fase 5 (Informe Técnico PDF):** Redactar `docs/informe_tecnico_EP3.md` (fuente) y renderizar `docs/informe_tecnico_EP3.pdf` (A4, diseño sobrio y profesional) con cifras reales y Anexos A y B.
6. **Fase 6 (Repositorio y Seguridad):** Actualizar `README.md`, `requirements.txt`, `.env.example`, `.gitignore` y organizar commits convencionales locales (sin `push`).
