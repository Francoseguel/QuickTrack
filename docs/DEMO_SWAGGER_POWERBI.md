# Demostración en vivo: Swagger → MongoDB Atlas → Power BI

Guion para probar frente al profesor que la API escribe en Atlas en tiempo real y que el dashboard de Power BI refleja esos cambios al actualizar.

**La historia que se cuenta:** llegan 7 envíos nuevos a la zona **Sur** y todos se cancelan. Al actualizar Power BI, **Sur pasa a ser la zona crítica (50,0 %) y supera a Centro (47,1 %)**.

```
Swagger (POST / PUT / DELETE) ──al instante──► MongoDB Atlas ──botón Actualizar──► Power BI
```

> ⚠️ **La base es compartida con el grupo.** Al terminar, siempre ejecuta el **Acto 4 (limpieza)**. Si no, Power BI va a mostrar 107 órdenes.

---

## 0. Preparación (antes de la presentación)

1. Abre una terminal **dentro de la carpeta del proyecto** y levanta la API:
   ```
   cd C:\Users\Felipe\Desktop\exp2_bdnorelacional\QuickTrack
   python -m uvicorn api.main:app --reload
   ```
   Espera a ver `Application startup complete.` y no cierres esa terminal.
2. En el navegador, abre **http://localhost:8000/docs** (Swagger).
3. Abre Power BI (`mongoBD_ev2.pbip`) y presiona **Actualizar**. Comprueba que estén las cifras de partida (tabla de abajo).
4. Abre una **segunda terminal de PowerShell** para los bloques rápidos de los actos 2, 3 y 4.

### Cifras de partida (sin filtros)

| KPI | Valor |
|---|---|
| Total órdenes | 100 |
| Tasa de cancelación | 23,0 % |
| Órdenes abiertas | 50 |
| Ingresos totales | 10.939.613 |
| Zona más crítica | **Centro 47,1 %** · Norte 36,4 % · Sur 23,1 % · Poniente 9,1 % · Oriente 7,7 % |
| Cancelación con Transferencia | 31,2 % |
| % estados coherentes | 18,0 % (82 inconsistentes) |

---

## Acto 1: crear una orden desde Swagger (POST)

En Swagger: **POST /ordenes** → **Try it out** → pega esto → **Execute**.

```json
{
  "_id": "orden_demo_1",
  "cliente_id": "cli_15",
  "ruta_id": "ruta_15",
  "medio_pago": "Transferencia",
  "total": 285000
}
```

Respuesta esperada: **201** `"Orden creada exitosamente"`.

Comprobación inmediata: **GET /ordenes/{orden_id}** → `orden_demo_1` → **Execute**. Debe responder **200** con `"estado": "En preparación"` y su seguimiento con 1 evento.

**Qué decir:** «La API insertó la orden en `ordenes_entrega` y su seguimiento en `seguimiento`, y el GET la lee al instante desde Atlas con un `$lookup` (`api/main.py:43` y `:70`).»

---

## Acto 2: cargar las otras 6 órdenes y actualizar Power BI

Para no repetir el POST 6 veces a mano, se llama **al mismo endpoint** desde PowerShell. Esto también demuestra que la API sirve a cualquier cliente HTTP, no solo a Swagger.

Pega este bloque completo en la **segunda terminal**:

```powershell
$api = "http://localhost:8000"
$ordenes = @(
  @{ _id = "orden_demo_2"; cliente_id = "cli_22"; ruta_id = "ruta_26"; medio_pago = "Transferencia"; total = 310000 },
  @{ _id = "orden_demo_3"; cliente_id = "cli_37"; ruta_id = "ruta_28"; medio_pago = "Transferencia"; total = 295000 },
  @{ _id = "orden_demo_4"; cliente_id = "cli_48"; ruta_id = "ruta_48"; medio_pago = "Transferencia"; total = 320000 },
  @{ _id = "orden_demo_5"; cliente_id = "cli_53"; ruta_id = "ruta_56"; medio_pago = "Transferencia"; total = 305000 },
  @{ _id = "orden_demo_6"; cliente_id = "cli_61"; ruta_id = "ruta_62"; medio_pago = "Transferencia"; total = 290000 },
  @{ _id = "orden_demo_7"; cliente_id = "cli_79"; ruta_id = "ruta_65"; medio_pago = "Transferencia"; total = 315000 }
)
foreach ($o in $ordenes) {
  Invoke-RestMethod -Method Post -Uri "$api/ordenes" -ContentType "application/json" -Body ($o | ConvertTo-Json)
}
```

Deben salir 6 líneas `Orden creada exitosamente`. Las 7 rutas usadas son de la zona **Sur**.

Ahora, en Power BI, presiona **Actualizar** (tarda entre 30 y 60 segundos).

### Qué cambia en Power BI

| KPI | Antes | Después del Acto 2 |
|---|---|---|
| Total órdenes | 100 | **107** |
| Órdenes abiertas | 50 | **57** |
| Ingresos totales | 10,94 mill. | **13,06 mill.** |
| Ingresos por año | 2022 · 2023 · 2024 | Aparece una barra nueva de **2026: 2,12 mill.** (la API pone esa fecha de envío) |
| Tasa de cancelación | 23,0 % | **21,5 %** (más órdenes y ninguna cancelada todavía) |
| Sur: órdenes y cancelación | 13 · 23,1 % | **20 · 15,0 %** |
| % estados coherentes | 18,0 % | **23,4 %** |

**Qué decir:** «Las 7 órdenes nuevas son coherentes porque la API escribe el mismo estado en las dos colecciones. Las 82 inconsistencias siguen ahí porque vienen de los datos de origen.»

---

## Acto 3: cancelar las órdenes (PUT) y ver la zona crítica cambiar

En Swagger: **PUT /ordenes/{orden_id}/estado** → **Try it out** → en `orden_id` escribe `orden_demo_1` → pega esto → **Execute**.

```json
{
  "nuevo_estado": "Cancelado",
  "fecha_evento": "2026-10-28T10:05:00"
}
```

Respuesta esperada: **200**. Haz de nuevo el **GET** de `orden_demo_1`: ahora dice `"Cancelado"` y el historial tiene **2 eventos** (el `$push` agregó uno).

> ⚠️ Respeta el formato de `fecha_evento` (`AAAA-MM-DDTHH:MM:SS`). Con otro formato, el script de Power BI no puede leer la fecha y la actualización falla.

Cancela las otras 6 desde la segunda terminal:

```powershell
$api = "http://localhost:8000"
$cuerpo = '{"nuevo_estado": "Cancelado", "fecha_evento": "2026-10-28T10:05:00"}'
2..7 | ForEach-Object {
  Invoke-RestMethod -Method Put -Uri "$api/ordenes/orden_demo_$_/estado" -ContentType "application/json" -Body $cuerpo
}
```

En Power BI, presiona **Actualizar**.

### Qué cambia en Power BI (el momento clave)

| KPI | Inicio | Después del Acto 3 |
|---|---|---|
| Tasa de cancelación | 23,0 % | **28,0 %** |
| Órdenes abiertas | 50 | 50 (las 7 pasaron a canceladas) |
| **Zona más crítica** | **Centro 47,1 %** | **Sur 50,0 %**, que supera a Centro (47,1 %) |
| Cancelación con Transferencia | 31,2 % | **43,6 %** |
| Embudo de etapas (página 4) | 4 etapas | Aparece la etapa **«Cancelado»** con 7 órdenes |

Muestra la página **Zonas y rutas**: Sur queda primera en el gráfico de barras y en la matriz.

**Qué decir:** «Con 7 operaciones por la API, el dashboard detecta que Sur se volvió la zona crítica. Así se usaría en la operación real: la gerencia actualiza y ve dónde intervenir.»

> La página **Satisfacción** no cambia porque la API no tiene un endpoint para crear valoraciones. Si lo preguntan, es una mejora propuesta.

---

## Acto 4: limpieza (DELETE), obligatorio

Muestra uno en Swagger: **DELETE /ordenes/{orden_id}** → `orden_demo_1` → **Execute** → **200**. Luego un **GET** de `orden_demo_1` debe responder **404**, lo que prueba que se borró.

Borra el resto desde la segunda terminal:

```powershell
$api = "http://localhost:8000"
1..7 | ForEach-Object {
  try { Invoke-RestMethod -Method Delete -Uri "$api/ordenes/orden_demo_$_" }
  catch { "orden_demo_$_ ya estaba borrada" }
}
```

En Power BI, presiona **Actualizar**: todo debe volver a las **cifras de partida** (100 órdenes, 23,0 %, Centro 47,1 %).

**Qué decir:** «El DELETE borra en cascada la valoración, el seguimiento y la orden (`api/main.py:111`), así que no quedan documentos huérfanos.»

---

## Extra: errores controlados (si preguntan por validaciones)

| Prueba en Swagger | Qué pegar | Respuesta |
|---|---|---|
| Orden duplicada | El POST del Acto 1 otra vez, **antes** de la limpieza | **400** `La orden 'orden_demo_1' ya existe.` |
| Total negativo | POST con `"total": -5` | **422** (Pydantic la rechaza antes de tocar la base) |
| Falta un campo | POST sin `"ruta_id"` | **422** |
| Orden inexistente | GET con `orden_que_no_existe` | **404** |

---

## Si algo falla

| Problema | Solución |
|---|---|
| `ModuleNotFoundError: No module named 'api'` | La terminal no está en la carpeta `QuickTrack`. Usa `cd QuickTrack` y vuelve a levantar la API |
| PowerShell: `No es posible conectar con el servidor remoto` | La API no está corriendo: revisa la primera terminal |
| Power BI da error al actualizar | Ejecuta la limpieza (Acto 4) y vuelve a actualizar |
| Se cerró la API antes de limpiar | Desde la carpeta `QuickTrack`, borra directo en Atlas: `python -c "from config.database import get_database as g; db=g(); [db[c].delete_many({k: {'`$regex': '^orden_demo_'}}) for c, k in [('valoraciones','orden_id'), ('seguimiento','orden_id'), ('ordenes_entrega','_id')]]; print('limpio')"` |
| Quieres comprobar que la base quedó limpia | `python -c "from config.database import get_database as g; print(g().ordenes_entrega.count_documents({}))"` debe mostrar **100** |
