# QuickTrack — Plataforma Logística NoSQL y Analítica BI (BDY0101)

Proyecto de la asignatura **BDY0101 — Base de Datos No Relacionales (Duoc UC)**, **Caso Forma B: QuickTrack** (logística express nacional). Integra la capa operacional NoSQL de la Evaluación Parcial N°2 (MongoDB Atlas + API REST FastAPI) con el flujo completo de explotación analítica de la **Evaluación Parcial N°3**: extracción multi-colección, auditoría empírica **RICE**, exportación en **modelo estrella CSV**, activos de **Power BI**, automatización de refresco y documentación técnica final.

---

## Entregables Principales (EP3)

- **Informe Técnico Final (PDF A4):** [`docs/informe_tecnico_EP3.pdf`](docs/informe_tecnico_EP3.pdf) *(fuente Markdown: [`docs/informe_tecnico_EP3.md`](docs/informe_tecnico_EP3.md))*
- **Auditoría inicial y brechas IE1–IE8:** [`docs/auditoria.md`](docs/auditoria.md)
- **Automatización y alcance IE8:** [`docs/automatizacion.md`](docs/automatizacion.md)
- **Activos de Power BI:** [`powerbi/queries.m`](powerbi/queries.m), [`powerbi/medidas.dax`](powerbi/medidas.dax), [`powerbi/modelo.md`](powerbi/modelo.md), [`powerbi/guia_construccion.md`](powerbi/guia_construccion.md) y [`powerbi/boceto_dashboard.png`](powerbi/boceto_dashboard.png)
- **Diagramas (Mermaid + SVG/PNG):** [`docs/diagramas/`](docs/diagramas/)

---

## KPIs Verificados sobre los Datos Reales (`data/*.json`)

| Indicador | Valor Verificado | Rol |
|---|---:|---|
| **Facturación Total** | `$10.939.612,72` | KPI Principal 1 |
| **Volumen de Órdenes** | `100` *(Ene 2022 – Jun 2024)* | KPI Principal 2 |
| **Tasa de Cumplimiento (`% Entregado`)** | `27,0 %` *(27/100)* | KPI Principal 3 |
| **Satisfacción Promedio (`1–5`)** | `3,07 / 5,00` *(37 críticas ≤ 2)* | KPI Principal 4 |
| *Ticket Promedio* | `$109.396,13` | Indicador secundario |
| *Eventos de Seguimiento (`$unwind historial`)* | `302` *(media `4,04` días)* | Trazabilidad derivada |

---

## Estructura del Repositorio

```text
QuickTrack/
├── .github/workflows/
│   └── refresh_analytics.yml          # Workflow programado (cron diario) con fallback local
├── api/
│   ├── main.py                        # API FastAPI (CRUD EP2 + endpoints /analitica/*)
│   ├── middlewares.py                 # Trazabilidad de tiempos y control de excepciones
│   └── models.py                      # Modelos Pydantic de validación
├── config/
│   └── database.py                    # Conexión segura a MongoDB Atlas vía .env + certifi
├── data/
│   ├── clientes.json                  # 100 clientes (JSON Array)
│   ├── ordenes_entrega.json           # 100 órdenes (JSON Lines)
│   ├── rutas.json                     # 100 rutas (JSON Lines)
│   ├── seguimiento.json               # 100 seguimientos / 302 eventos (JSON Lines)
│   ├── valoraciones.json              # 100 valoraciones (JSON Lines)
│   └── export/                        # Modelo estrella CSV (UTF-8 BOM) + auditoría RICE y logs
│       ├── fact_ordenes.csv
│       ├── fact_seguimiento_eventos.csv
│       ├── dim_rutas.csv
│       ├── dim_clientes.csv
│       ├── dim_fecha.csv
│       ├── rice_auditoria.csv
│       ├── etl_metadata.json
│       └── ultimo_refresh.json
├── docs/
│   ├── informe_tecnico_EP3.pdf        # Informe Técnico final EP3 (A4)
│   ├── informe_tecnico_EP3.md         # Fuente Markdown del informe
│   ├── auditoria.md                   # Diagnóstico inicial y correcciones del borrador
│   ├── automatizacion.md              # Guía de refresco (Actions, Task Scheduler, Power BI Service)
│   ├── Informe Tecnico QuickTrack NoSQL.pdf  # Informe previo EP2
│   ├── capturas/                      # Carpeta para capturas de Power BI / Atlas / Azure
│   └── diagramas/                     # Arquitectura y Modelo Estrella (.mmd, .svg, .png)
├── powerbi/
│   ├── queries.m                      # Consultas Power Query M parametrizadas (RutaExport)
│   ├── medidas.dax                    # 4 KPIs oficiales + indicadores secundarios
│   ├── modelo.md                      # Relaciones 1:*, 4 características IE3 y matriz IE7
│   ├── guia_construccion.md           # Guía paso a paso para construir/alinear el .pbix
│   ├── boceto_dashboard.html          # Fuente HTML del wireframe
│   └── boceto_dashboard.png           # Wireframe renderizado con datos reales
├── scripts/
│   ├── rice_audit.py                  # Cálculo empírico de cobertura R y matriz RICE (3 ejes)
│   ├── etl_analitica.py               # Pipelines MongoDB ($lookup 5 col., $unwind) + CSV estrella
│   ├── validar_etl.py                 # 12 controles de conteos, integridad, sumas y RICE
│   ├── refresh_pipeline.py            # Comando único: RICE + ETL + Validación + log JSON
│   ├── cargar_atlas.py                # Ingesta inicial EP2 hacia MongoDB Atlas
│   ├── consultas_nosql.py             # Consultas e índices EP2
│   └── crud_operations.py             # Pruebas CRUD EP2
├── .env.example                       # Plantilla segura sin credenciales reales
├── .gitignore                         # Excluye .env, .venv/, __pycache__/, *.log
└── requirements.txt                   # Dependencias Python 3.11+
```

---

## Instalación y Configuración

```powershell
# 1. Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar credenciales (solo si conectará a MongoDB Atlas)
Copy-Item .env.example .env
# Edite .env con su MONGO_URI real. NUNCA suba .env a Git.
```

> **Seguridad:** `.env` está protegido por `.gitignore`. Nunca hardcodee contraseñas en código ni en `.env.example`.

---

## Uso: Regenerar y Validar Datos Analíticos

### Comando único recomendado (RICE + ETL + Validación 12/12)

```powershell
# Modo automático: intenta MongoDB Atlas si .env está configurado; sino usa data/*.json
python scripts/refresh_pipeline.py --source auto

# Modo reproducible sin credenciales (lee data/*.json)
python scripts/refresh_pipeline.py --source local

# Modo solo lectura obligatorio contra MongoDB Atlas
python scripts/refresh_pipeline.py --source atlas
```

### Ejecución individual de scripts

```powershell
python scripts/rice_audit.py --source local
python scripts/etl_analitica.py --source local
python scripts/validar_etl.py --source local
```

### Levantar la API REST FastAPI (CRUD + Endpoints `/analitica/*`)

```powershell
uvicorn api.main:app --reload --port 8000
```

Endpoints analíticos disponibles como fuente JSON alternativa para Power BI:
- `GET /analitica/kpis?source=auto`
- `GET /analitica/rendimiento-zonas?source=auto`
- `GET /analitica/ordenes?source=auto`
- `GET /analitica/seguimiento-eventos?source=auto`

---

## Integración en Power BI Desktop

Sigue la guía paso a paso en [`powerbi/guia_construccion.md`](powerbi/guia_construccion.md) para cargar los 5 CSV de `data/export/` usando [`powerbi/queries.m`](powerbi/queries.m) (parámetro `RutaExport`) y aplicar las medidas de [`powerbi/medidas.dax`](powerbi/medidas.dax).
