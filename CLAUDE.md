# QuickTrack — EP2 BDY0101 (Base de Datos No Relacionales)

Evaluación Parcial 2, **Forma B**, caso QuickTrack (logística de entregas express). Grupo: Franco Seguel, Martin Papic y Felipe Angel. El repo es de Franco (`github.com/Francoseguel/QuickTrack`); Felipe trabaja sobre su copia local.

- Pauta y enunciado: `docs/EP2_BDY0101_Estudiante_B.pdf` (rúbrica IE1–IE11).
- Entrega: informe PDF + link al repo, vía AVA.

## Stack y cómo ejecutar

MongoDB Atlas (AWS SA_EAST_1, replica set de 3 nodos, MongoDB 8.0) · Python · PyMongo · FastAPI.

```
python config/database.py              # ping a Atlas
python scripts/cargar_atlas.py         # ETL: BORRA y recarga las 5 colecciones (no correr sin avisar)
python scripts/consultas_nosql.py      # crea índices + consultas C1–C3
python scripts/crud_operations.py      # ciclo CRUD con orden_test_999 (crea y borra)
python -m uvicorn api.main:app --reload   # API → http://localhost:8000/docs
python powerbi/extraer_quicktrack.py   # prueba la extracción para Power BI
```

- Credenciales en `.env` (gitignored): `MONGO_URI`, `DB_NAME=quicktrack_db`, `PORT`. Nunca escribir la URI en archivos versionados.
- En el PC de Felipe: Python 3.14 con versiones nuevas (fastapi 0.162, pydantic 2.14, pandas 3.0). `requirements.txt` fija versiones viejas que no instalan en 3.14. Usar `python -m uvicorn`, porque `Scripts/` no está en el PATH.

## Reglas de trabajo con Felipe

- Responder en español. Llamarlo solo «Felipe».
- **No modificar el código existente** (api/, config/, scripts/): Felipe decidió dejarlo como está. Se pueden agregar archivos nuevos si los pide.
- No hacer commits: Felipe los hace. Nunca agregar atribución de Claude.
- No abrir ventanas o apps (VS Code, navegador, Power BI) sin preguntar; darle la ruta.
- Antes de escribir en Atlas, recordar que la base es compartida con el grupo: las pruebas deben usar ids de prueba y dejar todo limpio (100 docs por colección).
- Las cifras del informe salen de mediciones reales: no inventar números; medir de nuevo si hace falta.

## Estado (26-10-2026)

Hecho:
- `docs/Informe Tecnico QuickTrack NoSQL v2.pdf` (17 págs, cubre los 7 apartados de la pauta). Fuente: `docs/fuente_informe/informe_tecnico.html`. Para regenerar el PDF, usar Edge headless (`--headless=new --print-to-pdf`, con `--user-data-dir` temporal). El informe antiguo fue borrado.
- Presentación de 13 slides con notas del orador: artifact https://claude.ai/artifact/Tjek2aN9GzmUmVCoXT8rCB (privado; se descarga como PPTX/PDF). Incluye capturas de las pruebas (ETL, consultas, CRUD, Swagger).
- `powerbi/extraer_quicktrack.py`: script para *Obtener datos → Script de Python* en Power BI. Genera 6 tablas (ordenes, clientes, rutas, seguimiento, eventos_seguimiento, valoraciones). La Atlas Data API ya no existe (dada de baja en septiembre de 2025), por eso se usa el script.

**Power BI (27-10-2026):** Power BI Desktop 2.159 ya está instalado. Material listo en `powerbi/`:
- `GUIA_POWERBI.md`: pasos, relaciones, 4 páginas y cifras esperadas por zona.
- `medidas_quicktrack.tmdl`: 17 medidas para pegar en la vista TMDL.
- `tema_quicktrack.json`: tema de colores.
- `csv/`: plan B, se genera con `extraer_quicktrack.py --csv`.

El script ahora agrega `seguimiento.dias_entrega` y `valoraciones.con_retraso`, y fija `future.infer_string=False` para que pandas 3 funcione con Power BI. El tiempo de entrega es 6 días en todas las órdenes (dato sintético), así que el retraso se mide con los reclamos «Tuvo retraso». Falta que Felipe arme el .pbix siguiendo la guía.

**Reproducibilidad (28-10-2026), rama `felipe`:** `README.md` con pasos y mapa pauta → archivo; scripts nuevos `consultas_complementarias.py` (C4–C5), `evaluar_eficiencia.py` (IE6), `validar_datos.py` (IE8) y `probar_api.py` (TestClient, 12 pruebas); `requirements.txt` con versiones mínimas; `.env.example` sin credenciales; dashboard en `powerbi/mongoBD_ev2.pbip` con el parámetro `RutaProyecto` (la copia del Escritorio queda como respaldo); capturas en `docs/evidencias/`. Probado desde copia limpia con Python 3.11 y 3.14 en una base aparte: cifras idénticas al informe.

Pendientes del grupo:
- `.env.example` contiene la contraseña real de Atlas y el repo es público: hay que cambiar la contraseña y dejar un placeholder.
- Opcional: agregar al repo las consultas C4–C5, las mediciones con `explain()` y las validaciones como script (hoy solo están en el informe).
- Opcional: verificar en Atlas el tier del clúster (el informe dice «clúster compartido»).

## Datos clave (medidos)

- 5 colecciones × 100 documentos. `ordenes.cliente_id` es texto («cli_73») y `clientes._id` es entero: el ETL crea `cliente_num_id`.
- Centro: 47,1 % de cancelación, puntaje 2,71/5. Global: 23 % de cancelación, 3,07 de puntaje, 37 % de valoraciones críticas, 50 órdenes abiertas.
- Inconsistencias de origen: 82 órdenes con estado ≠ seguimiento; 72 con `estado_actual` ≠ último evento; 51 con historial antes del envío; 32 con comentario que contradice el puntaje; 23 canceladas con valoración.
- Rendimiento: el índice compuesto baja de 100 a 27 los documentos examinados en C1; `MongoClient` por request es ~20× más lento (1689 vs 82 ms).
