# Guía de Construcción / Alineación del Dashboard en Power BI Desktop

Esta guía permite armar el archivo `.pbix` desde cero en ~15 minutos o alinear el dashboard ya creado por tu compañero para que coincida 100 % con los datos exportados, las fórmulas DAX y el Informe Técnico.

> **Estado actual en el repositorio:** No se encontró ningún archivo `.pbix` ni capturas de pantalla en `docs/` al momento de la auditoría. Una vez construido o adaptado el `.pbix`, guarda las capturas en `docs/capturas/` y el archivo en `powerbi/QuickTrack_Dashboard.pbix`.

---

## Paso 1 — Regenerar y validar los datos CSV

Desde la raíz del repositorio `QuickTrack/`:

```powershell
.\.venv\Scripts\python.exe scripts\refresh_pipeline.py --source auto
```

Verifica que existan los 5 archivos en `data/export/`:
- `fact_ordenes.csv` (100 filas)
- `fact_seguimiento_eventos.csv` (302 filas)
- `dim_rutas.csv` (100 filas)
- `dim_clientes.csv` (100 filas)
- `dim_fecha.csv` (890 filas)

---

## Paso 2 — Cargar tablas con Power Query (`powerbi/queries.m`)

1. Abre **Power BI Desktop** y crea un informe nuevo (o abre el `.pbix` de tu compañero).
2. Haz clic en **Transformar datos** para abrir Power Query.
3. Crea el parámetro **RutaExport**:
   - Menú **Administrar parámetros → Nuevo parámetro**.
   - Nombre: `RutaExport` · Tipo: `Texto` · Valor actual: ruta completa a tu carpeta `QuickTrack\data\export`.
4. Crea 5 consultas en blanco (**Nuevo origen → Consulta en blanco**), nómbralas exactamente `fact_ordenes`, `fact_seguimiento_eventos`, `dim_rutas`, `dim_clientes` y `dim_fecha`, y pega cada bloque correspondiente desde [queries.m](queries.m) en el **Editor avanzado**.
5. Haz clic en **Cerrar y aplicar**.

---

## Paso 3 — Configurar el Modelo Estrella

En la vista **Modelo** de Power BI Desktop:

1. Marca `dim_fecha` como **Tabla de fechas** (clic derecho en `dim_fecha` → *Marcar como tabla de fechas* → columna `fecha`).
2. Verifica o crea exactamente estas 4 relaciones activas (cardinalidad `1:*`, dirección de filtro **Única**):
   - `dim_fecha[fecha_key]` → `fact_ordenes[fecha_key]`
   - `dim_rutas[ruta_id]` → `fact_ordenes[ruta_id]`
   - `dim_clientes[cliente_num_id]` → `fact_ordenes[cliente_num_id]`
   - `fact_ordenes[orden_id]` → `fact_seguimiento_eventos[orden_id]`
3. Asegúrate de **no** activar una relación directa entre `dim_rutas[ruta_id]` y `fact_seguimiento_eventos[ruta_id]` (evita ambigüedad de filtros).
4. Toma una captura de pantalla de esta vista y guárdala en `docs/capturas/01_modelo_estrella_powerbi.png`.

---

## Paso 4 — Cargar las Medidas DAX (`powerbi/medidas.dax`)

1. En la vista **Informe**, haz clic en **Especificar datos**, nombra la tabla `_Medidas` y presiona **Cargar**.
2. Crea cada medida definida en [medidas.dax](medidas.dax), priorizando los **4 KPIs oficiales**:
   - `Facturacion Total` → Formato moneda `$#,##0` (valor total esperado sin filtros: **$10.939.613**)
   - `Volumen Ordenes` → Formato entero `#,##0` (valor esperado: **100**)
   - `Tasa Cumplimiento` → Formato porcentaje `0,0%` (valor esperado: **27,0 %**)
   - `Satisfaccion Promedio` → Formato decimal `0,00` (valor esperado: **3,07**)
   - `Ticket Promedio` (secundario) → Formato moneda `$#,##0` (valor esperado: **$109.396**)

---

## Paso 5 — Construir el Lienzo del Dashboard (Alineado al Boceto)

Usa como referencia visual `powerbi/boceto_dashboard.png` (lienzo 16:9, fondo `#F4F6F9`, tarjetas blancas con bordes sutiles y paleta institucional azul marino `#0F2942` / azul `#1D6FA5` / verde `#1E8E5A` / ámbar `#D97706` / rojo `#C0392B`):

1. **Barra superior:** Título *"QuickTrack — Tablero Ejecutivo de Logística y Satisfacción"* + 4 segmentadores horizontales (`dim_fecha[anio]`, `dim_rutas[zona]`, `fact_ordenes[estado]`, `fact_ordenes[medio_pago]`).
2. **Fila de KPIs (arriba):** 4 tarjetas principales (`Facturacion Total`, `Volumen Ordenes`, `Tasa Cumplimiento`, `Satisfaccion Promedio`) + 1 tarjeta secundaria (`Ticket Promedio`).
3. **Fila central (2 gráficos):**
   - Izquierda: **Barras agrupadas** — `dim_rutas[zona]` vs `Facturacion Total` y `Volumen Ordenes`.
   - Derecha: **Líneas y columnas agrupadas** — `dim_fecha[anio_mes]` vs `Facturacion Total` (columnas) y `Volumen Ordenes` (línea).
4. **Fila inferior (3 visuales):**
   - Izquierda: **Barras apiladas 100 %** (o Anillo) — `dim_rutas[zona]` × `fact_ordenes[medio_pago]` por `Facturacion Total`.
   - Centro: **Matriz con formato condicional** — Filas: `dim_rutas[zona]` | Valores: `Volumen Ordenes`, `Tasa Cumplimiento`, `Tasa Cancelacion`, `Satisfaccion Promedio`, `Dias Promedio Seguimiento`.
   - Derecha: **Barras agrupadas / Embudo** — `fact_seguimiento_eventos[estado_evento]` (ordenado por `orden_evento`) vs `Total Eventos Seguimiento` (o `Satisfaccion Promedio` por `fact_ordenes[estado]`).

---

## Paso 6 — Si ya existe el `.pbix` de tu compañero (Checklist de alineación)

Si vas a adaptar el archivo de tu compañero en vez de crearlo desde cero:
- [ ] Reemplaza la fuente de datos antigua por los 5 CSV de `data/export/` usando `queries.m`.
- [ ] Verifica que los 4 KPIs visibles en las tarjetas superiores muestren exactamente: `$10.939.613`, `100`, `27,0 %` y `3,07 / 5,00` (sin filtros).
- [ ] Comprueba que existan visuales que cubran las **3 preguntas de negocio** (zonas/meses, medios de pago y cumplimiento + satisfacción/seguimiento).
- [ ] Guarda el archivo en `powerbi/QuickTrack_Dashboard.pbix`.
- [ ] Guarda capturas reales en `docs/capturas/`:
  - `01_modelo_estrella_powerbi.png`
  - `02_dashboard_general.png`
  - `03_dashboard_filtro_interactivo.png` (ejemplo: filtrado por Zona Norte o Centro)
