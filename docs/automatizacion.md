# Automatización de Reportes y Actualización Programada (IE8)

Este documento describe con transparencia el alcance real de la automatización implementada en QuickTrack y la arquitectura propuesta para el refresco programado en **Power BI Service**, diferenciando claramente lo **implementado y verificado** de lo **propuesto/configurado en nube**.

> **Nota sobre latencia ("tiempo real" vs actualización programada):**  
> Los reportes de QuickTrack operan bajo un esquema de **actualización automatizada programada (*batch*) y refresco bajo demanda**, no *streaming* en tiempo real sub-segundo. Cuando una nueva orden o cambio de estado entra a MongoDB Atlas (vía API FastAPI o carga operativa), el pipeline automatizado regenera y valida las tablas del modelo estrella y Power BI actualiza los KPIs al ejecutar el siguiente refresco programado o manual.

---

## 1. Mecanismos Implementados y Verificados en el Repositorio

### 1.1 Orquestador de Comando Único (`scripts/refresh_pipeline.py`)
Unifica en un solo comando la cadena completa **RICE → ETL → Validación → Log de Auditoría**:

```powershell
# Intenta MongoDB Atlas si .env tiene MONGO_URI; si no, usa data/*.json
.\.venv\Scripts\python.exe scripts\refresh_pipeline.py --source auto

# Modo explícito reproducible sin credenciales
.\.venv\Scripts\python.exe scripts\refresh_pipeline.py --source local

# Modo producción solo lectura sobre MongoDB Atlas
.\.venv\Scripts\python.exe scripts\refresh_pipeline.py --source atlas
```

Salidas verificadas:
- Regenera los 5 CSV del modelo estrella en `data/export/` (`UTF-8` con BOM).
- Ejecuta `12` comprobaciones automáticas de conteo, claves, integridad referencial, cuadre monetario y cumplimiento RICE (`exit code 0` si aprueba; `1` si falla).
- Registra marca de tiempo, modo de origen, duración y snapshot de KPIs en `data/export/ultimo_refresh.json`.

### 1.2 Programación en la Nube con GitHub Actions (`.github/workflows/refresh_analytics.yml`)
- **Disparador automático:** `cron: "0 9 * * *"` (diario a las 06:00 CLT / 09:00 UTC).
- **Disparador manual:** `workflow_dispatch` con selector de origen (`auto`, `local`, `atlas`).
- **Manejo seguro de secretos:** Lee `secrets.MONGO_URI` desde GitHub Secrets; si el secreto aún no está configurado en el repositorio, ejecuta automáticamente `--source local`, documenta el modo usado en `GITHUB_STEP_SUMMARY` y publica `data/export/` como artefacto descargable.

### 1.3 Programación Local con Programador de Tareas de Windows (*Task Scheduler*)
Para equipos Windows con Power BI Desktop conectado a `RutaExport`, se puede registrar una tarea programada diaria:

```powershell
schtasks /Create /SC DAILY /TN "QuickTrack_ETL_Refresh" /ST 07:00 ^
  /TR "\"C:\Users\mapap\Desktop\sexto semestre\BD NR\QuickTrack\.venv\Scripts\python.exe\" \"C:\Users\mapap\Desktop\sexto semestre\BD NR\QuickTrack\scripts\refresh_pipeline.py\" --source auto" /F
```

### 1.4 Fuente Alternativa Dinámica vía API REST FastAPI (`api/main.py`)
La API FastAPI ya implementada en la EP2 fue extendida con endpoints de solo lectura bajo `/analitica/*` que ejecutan los mismos pipelines sobre MongoDB Atlas (con fallback opcional `?source=local` para pruebas locales sin conexión a Atlas):
- `GET /analitica/kpis`: devuelve los 4 KPIs oficiales + indicadores secundarios en formato JSON.
- `GET /analitica/rendimiento-zonas`: devuelve facturación, volumen, tasa de cumplimiento y satisfacción por zona.
- `GET /analitica/ordenes`: devuelve las filas planas equivalentes a `fact_ordenes.csv`, consumibles desde Power BI mediante `Json.Document(Web.Contents("http://localhost:8000/analitica/ordenes"))`.
- `GET /analitica/seguimiento-eventos`: devuelve los eventos desplegados (`$unwind historial`).

> **Evaluación técnica de la API como fuente de Power BI:** Es útil para consultas bajo demanda en entornos de desarrollo o despliegues en la nube con HTTPS público; sin embargo, para el modelo estrella completo y refresco desacoplado de la base operativa se prioriza el **archivo intermedio CSV/Blob Storage** porque evita latencia por paginación HTTP y protege el clúster gratuito M0 de Atlas.

---

## 2. Arquitectura Propuesta para Actualización Programada en Power BI Service

| Componente | Estado | Descripción |
|---|---|---|
| **Opción A — Power BI Service + On-Premises Data Gateway (CSV local)** | Propuesto | Instalar el *On-Premises Data Gateway (Standard)* en el equipo donde corre `Task Scheduler`, vincular la ruta de `data/export/` y habilitar *Scheduled Refresh* en Power BI Service (hasta 8 refrescos/día en licencia Pro). |
| **Opción B — Flujo Cloud Azure (Cosmos DB → Azure Data Factory → Blob Storage → Power BI Service)** | Configurado parcialmente por el equipo (Lab 3.1.2) / Propuesto para producción | El equipo configuró el pipeline `pl_cosmos_a_datalake_quicktrack` en Azure Data Factory con actividad *Copy Data* hacia Azure Blob Storage. Agregando un *Schedule Trigger* en ADF y conectando Power BI Service directamente al conector nativo de **Azure Blob Storage** (sin gateway local), el dashboard en la nube se actualiza automáticamente tras cada ejecución del trigger. |

---

## 3. Separación de Alcance (Honestidad Técnica)

- **Implementado y verificado en este repositorio:** Orquestador Python `refresh_pipeline.py`, validación automática `12/12`, workflow de GitHub Actions con cron, comandos de Windows Task Scheduler y endpoints `/analitica/*` en FastAPI.
- **Pendiente de configuración/evidencia en cuentas personales del equipo:** Publicación del `.pbix` en Power BI Service, configuración de `MONGO_URI` en GitHub Secrets (si se desea que Actions consulte Atlas en vivo) y adjuntar capturas del trigger en Azure Data Factory / Blob Storage.
