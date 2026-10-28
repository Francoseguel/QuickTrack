# QuickTrack — Base de datos NoSQL para logística de entregas express

Evaluación Parcial 2 · **BDY0101 Base de Datos No Relacionales** · Forma B (caso QuickTrack)
Integrantes: Franco Seguel, Martin Papic y Felipe Angel

QuickTrack guarda sus órdenes de entrega, rutas, seguimiento de paquetes y valoraciones en **MongoDB Atlas**. Este repositorio contiene la carga de datos (ETL), las consultas de negocio, los scripts CRUD, una **API REST en FastAPI** que lee y escribe en tiempo real, y un **dashboard de Power BI** conectado a la base.

| Entregable | Dónde |
|---|---|
| Informe técnico (PDF) | [`docs/Informe Tecnico QuickTrack NoSQL v2.pdf`](docs/Informe%20Tecnico%20QuickTrack%20NoSQL%20v2.pdf) |
| Scripts de creación e inserción | [`scripts/cargar_atlas.py`](scripts/cargar_atlas.py), [`scripts/consultas_nosql.py`](scripts/consultas_nosql.py) (índices) |
| Capturas de consultas y resultados | [`docs/evidencias/`](docs/evidencias) |
| Código de integración | [`api/`](api) (FastAPI + PyMongo) y [`powerbi/`](powerbi) |

---

## Qué evidencia cada parte (según la pauta)

| Apartado de la pauta | Indicadores | Archivo que lo demuestra | Cómo verlo |
|---|---|---|---|
| 2. Configuración de la base | IE1, IE2, IE3 | [`config/database.py`](config/database.py), [`.env.example`](.env.example) | paso 3 |
| 3. Inserción de datos de prueba | IE1, IE3, IE7 | [`scripts/cargar_atlas.py`](scripts/cargar_atlas.py), [`data/`](data) | paso 4 |
| 4. Consultas (filtros, proyecciones, ordenamientos, agregaciones) | IE4, IE5 | [`scripts/consultas_nosql.py`](scripts/consultas_nosql.py) (índices + C1–C3), [`scripts/consultas_complementarias.py`](scripts/consultas_complementarias.py) (C4–C5) | pasos 5 y 6 |
| 4. Eficiencia de las consultas | IE6 | [`scripts/evaluar_eficiencia.py`](scripts/evaluar_eficiencia.py) (`explain()`, bytes, latencia) | paso 7 |
| 5. Operaciones CRUD completas | IE7, IE8 | [`scripts/crud_operations.py`](scripts/crud_operations.py), [`scripts/validar_datos.py`](scripts/validar_datos.py) | pasos 8 y 9 |
| 6. Integración con aplicación externa | IE9, IE10 | [`api/main.py`](api/main.py) (API REST), [`powerbi/`](powerbi) (dashboard) | pasos 10 a 12 |
| 7. Control de errores y validaciones | IE11 | [`api/models.py`](api/models.py) (Pydantic), [`api/middlewares.py`](api/middlewares.py), [`scripts/probar_api.py`](scripts/probar_api.py) | paso 10 |

---

## Cómo reproducir el proyecto

Probado desde una copia limpia del repositorio con **Python 3.11 y 3.14** en Windows.

### 1. Clonar e instalar

```bash
git clone https://github.com/Francoseguel/QuickTrack.git
cd QuickTrack
git checkout felipe

python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

### 2. Configurar la conexión

Copiar `.env.example` como `.env` y completar `MONGO_URI`. Hay dos opciones:

- **A. Base propia (recomendada para revisar).** Cualquier MongoDB sirve, porque el paso 4 carga los datos desde `data/`:
  - **MongoDB Atlas gratis (M0):** crear un clúster, un usuario de base de datos con permiso de lectura y escritura, permitir la IP en *Network Access* y copiar la URI `mongodb+srv://...`.
  - **MongoDB local:** `MONGO_URI=mongodb://localhost:27017/`
- **B. Clúster del grupo** (AWS São Paulo, replica set de 3 nodos, MongoDB 8.0). La URI con credenciales se entrega por privado y nunca se sube al repositorio.

```
MONGO_URI=mongodb+srv://<usuario>:<contraseña>@<cluster>.mongodb.net/
DB_NAME=quicktrack_db
PORT=8000
```

### 3 a 10. Ejecutar en orden

| Paso | Comando | Resultado esperado |
|---|---|---|
| 3. Probar conexión | `python config/database.py` | `Conexión exitosa…` |
| 4. Cargar los datos (ETL) | `python scripts/cargar_atlas.py` | 5 colecciones × 100 documentos. ⚠️ **Borra y recarga** las colecciones: en el clúster del grupo, no ejecutarlo sin avisar |
| 5. Índices y consultas C1–C3 | `python scripts/consultas_nosql.py` | 3 índices creados y los resultados de C1, C2 y C3 |
| 6. Consultas C4–C5 | `python scripts/consultas_complementarias.py` | Centro es la zona crítica: 47,1 % de cancelación y 2,71/5 de satisfacción |
| 7. Eficiencia (IE6) | `python scripts/evaluar_eficiencia.py` | C1 examina 27 documentos con índice vs. 100 sin índice; −34 % / −78 % de bytes con proyección y límite; un cliente nuevo por operación es ~20× más lento |
| 8. CRUD | `python scripts/crud_operations.py` | Ciclo crear → leer → actualizar → borrar de `orden_test_999`; la orden se borra al final |
| 9. Validaciones (IE8) | `python scripts/validar_datos.py` | 9 controles OK y 5 inconsistencias de origen (82, 72, 51, 32 y 23 de 23) |
| 10. API de punta a punta | `python scripts/probar_api.py` | `12 de 12 pruebas correctas` (lectura/escritura en tiempo real y errores 400/404/422) |

Las cifras corresponden a los datos originales de `data/` y coinciden con el informe. La latencia (paso 7) depende de la red: con una base local los tiempos son mucho menores.

### 11. Levantar la API

```bash
python -m uvicorn api.main:app --reload
```

Abrir **http://localhost:8000/docs** (Swagger) para probar los endpoints:

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/` | Estado del servicio |
| POST | `/ordenes` | Crea una orden y su seguimiento inicial (400 si el `_id` ya existe, 422 si los datos no son válidos) |
| GET | `/ordenes/{orden_id}` | Lee la orden con su seguimiento (`$lookup`) |
| PUT | `/ordenes/{orden_id}/estado` | Cambia el estado (`$set`) y agrega un evento al historial (`$push`) |
| DELETE | `/ordenes/{orden_id}` | Borra en cascada la valoración, el seguimiento y la orden |
| GET | `/analitica/rendimiento-zonas` | Agregación de órdenes y montos por zona |

Cada respuesta incluye el encabezado `X-Process-Time` y Uvicorn registra cada request en su log.

### 12. Dashboard de Power BI

El dashboard está en [`powerbi/mongoBD_ev2.pbip`](powerbi) (proyecto de Power BI en texto, versionable con git). Lee los datos de MongoDB con el script [`powerbi/extraer_quicktrack.py`](powerbi/extraer_quicktrack.py), que genera 6 tablas planas.

1. Instalar los paquetes en el Python que usará Power BI (`pip install -r requirements.txt`) y seleccionarlo en *Archivo → Opciones → Scripting de Python*.
2. Abrir `powerbi/mongoBD_ev2.pbip`.
3. *Transformar datos → Administrar parámetros → **RutaProyecto***: escribir la ruta de la carpeta del repositorio clonado. El script lee el `.env` de esa carpeta.
4. Presionar **Actualizar**.

Sin Python en Power BI, los mismos datos están en [`powerbi/csv/`](powerbi/csv); se regeneran con `python powerbi/extraer_quicktrack.py --csv`. La guía completa (relaciones, medidas y páginas) está en [`powerbi/GUIA_POWERBI.md`](powerbi/GUIA_POWERBI.md), y la demostración en vivo Swagger → Atlas → Power BI, en [`docs/DEMO_SWAGGER_POWERBI.md`](docs/DEMO_SWAGGER_POWERBI.md).

---

## Estructura

```
QuickTrack/
├── api/                    # API REST (FastAPI)
│   ├── main.py             #   endpoints CRUD + analítica
│   ├── models.py           #   validación de entradas (Pydantic)
│   └── middlewares.py      #   X-Process-Time + manejador global de errores
├── config/database.py      # conexión a MongoDB (lee .env, timeout de 5 s)
├── data/                   # 5 archivos JSON del caso (100 documentos cada uno)
├── scripts/
│   ├── cargar_atlas.py              # ETL: carga y normaliza cliente_id → cliente_num_id
│   ├── consultas_nosql.py           # índices + consultas C1–C3
│   ├── consultas_complementarias.py # consultas C4–C5 (satisfacción y cumplimiento por zona)
│   ├── evaluar_eficiencia.py        # explain(), volumen retornado y latencia
│   ├── crud_operations.py           # ciclo CRUD completo
│   ├── validar_datos.py             # 14 controles: duplicados, huérfanos, inconsistencias
│   └── probar_api.py                # pruebas de la API (lectura/escritura y errores)
├── powerbi/                # dashboard .pbip, script de extracción, medidas, tema, CSV y guía
├── docs/                   # informe PDF (+ fuente HTML), pauta, guion de demo y evidencias/
├── .env.example            # plantilla de configuración (sin credenciales)
└── requirements.txt
```

Los scripts de los pasos 6, 7 y 9 solo leen (el 5 crea índices, sin modificar documentos). Los de los pasos 8 y 10 crean órdenes de prueba (`orden_test_*`) y las borran al terminar, así que la base queda con 100 documentos por colección.
