# Dashboard QuickTrack en Power BI — guía paso a paso

```
MongoDB Atlas ──(pymongo + agregaciones)──► extraer_quicktrack.py ──► 6 tablas ──► Power BI
 5 colecciones       $lookup / $unwind          (Script de Python)      modelo + DAX     4 páginas
```

Archivos de esta carpeta:

| Archivo | Para qué sirve |
|---|---|
| `extraer_quicktrack.py` | Conecta a Atlas y entrega las 6 tablas a Power BI |
| `medidas_quicktrack.tmdl` | Las 17 medidas DAX, que se pegan de una sola vez en la vista TMDL |
| `tema_quicktrack.json` | Colores del dashboard |
| `csv/` | Plan B: las mismas tablas en CSV (`python powerbi/extraer_quicktrack.py --csv`) |

---

## 1. Configurar Python en Power BI (una sola vez)

1. **Archivo → Opciones y configuración → Opciones → Scripting de Python**.
2. En *Directorio principal de Python* elige **Otro** y pega:
   `C:\Users\Felipe\AppData\Local\Python\pythoncore-3.14-64`
3. Aceptar.

## 2. Conectar con MongoDB Atlas

1. **Inicio → Obtener datos → Más… → Otras → Script de Python → Conectar**.
2. Pega el contenido completo de `extraer_quicktrack.py` y acepta.
3. En el *Navegador*, marca las 6 tablas: `ordenes`, `clientes`, `rutas`, `seguimiento`, `eventos_seguimiento` y `valoraciones`.
4. Presiona **Cargar**. Si pregunta por niveles de privacidad, elige *Omitir* o *Público*.

> Si este paso falla (error de Python o de pandas), usa el **plan B**: en la terminal corre
> `python powerbi/extraer_quicktrack.py --csv` y luego, en Power BI, entra a **Obtener datos → Texto/CSV**
> y carga cada archivo de `powerbi/csv/`. Las tablas y columnas son las mismas.

Para la presentación: el botón **Actualizar** vuelve a consultar Atlas en vivo.

## 3. Revisar las relaciones (vista Modelo, el ícono de la izquierda)

Power BI suele detectarlas solo, porque las columnas tienen el mismo nombre. Debería quedar así:

```
 clientes ──1:*── ordenes ──*:1── rutas
                 │  │  │
          1:1 ───┘  │  └─── 1:1
   seguimiento      │        valoraciones
                   1:*
            eventos_seguimiento
```

| Desde | Hacia | Columna | Cardinalidad | Filtro cruzado |
|---|---|---|---|---|
| ordenes | rutas | ruta_id | Varios a uno | Único |
| ordenes | clientes | cliente_num_id | Varios a uno | Único |
| ordenes | valoraciones | orden_id | Uno a uno | Ambos |
| ordenes | seguimiento | orden_id | Uno a uno | Ambos |
| eventos_seguimiento | ordenes | orden_id | Varios a uno | Único |

- Si falta alguna, arrastra la columna de una tabla hasta la otra.
- Si Power BI crea una relación `eventos_seguimiento → seguimiento`, **elimínala**. Genera un camino ambiguo, y los eventos ya llegan a través de `ordenes`.

## 4. Crear las medidas (KPIs)

**Opción rápida:** usa la **vista TMDL** (ícono `</>` en la barra izquierda). Pega el contenido completo de `medidas_quicktrack.tmdl` y presiona **Aplicar**. Las 17 medidas aparecen en la tabla `ordenes`, ordenadas en 4 carpetas.

**Opción manual** (si no ves la vista TMDL): selecciona la tabla `ordenes` → **Nueva medida** y pega una por una:

```DAX
Total órdenes = COUNTROWS(ordenes)
Órdenes entregadas = CALCULATE(COUNTROWS(ordenes), ordenes[estado] = "Entregado")
Órdenes canceladas = CALCULATE(COUNTROWS(ordenes), ordenes[estado] = "Cancelado")
Órdenes abiertas = CALCULATE(COUNTROWS(ordenes), ordenes[estado] IN {"En preparación", "En tránsito"})
Tasa de entrega = DIVIDE([Órdenes entregadas], [Total órdenes])
Tasa de cancelación = DIVIDE([Órdenes canceladas], [Total órdenes])
Tiempo promedio de entrega (días) = AVERAGE(seguimiento[dias_entrega])
Distancia promedio (km) = AVERAGEX(ordenes, RELATED(rutas[distancia_km]))
Ingresos totales = SUM(ordenes[total])
Ticket promedio = AVERAGE(ordenes[total])
Puntaje promedio = AVERAGE(valoraciones[puntaje])
% clientes satisfechos = DIVIDE(CALCULATE(COUNTROWS(valoraciones), valoraciones[puntaje] >= 4), COUNTROWS(valoraciones))
% valoraciones críticas = DIVIDE(CALCULATE(COUNTROWS(valoraciones), valoraciones[critica] = TRUE()), COUNTROWS(valoraciones))
% reclamos por retraso = DIVIDE(CALCULATE(COUNTROWS(valoraciones), valoraciones[con_retraso] = TRUE()), COUNTROWS(valoraciones))
% estados coherentes = DIVIDE(CALCULATE(COUNTROWS(ordenes), ordenes[estado_coherente] = TRUE()), [Total órdenes])
Órdenes con estado inconsistente = CALCULATE(COUNTROWS(ordenes), ordenes[estado_coherente] = FALSE())
Canceladas con valoración = CALCULATE(COUNTROWS(valoraciones), ordenes[estado] = "Cancelado")
```

Luego, en *Herramientas de medidas*, aplica el formato: **%** a las tasas y **0,00** al puntaje.

## 5. Aplicar el tema

**Vista → Temas → Examinar temas** y elige `tema_quicktrack.json`.

## 6. Armar las 4 páginas

Cada página responde a una necesidad del enunciado:

| Lo que pide la gerencia | Página |
|---|---|
| Indicadores clave para el seguimiento operativo | 1. Resumen ejecutivo |
| Identificar zonas críticas y optimizar rutas | 2. Zonas y rutas |
| Medir la satisfacción del cliente | 3. Satisfacción |
| Entender qué afecta el cumplimiento de plazos | 4. Cumplimiento y calidad de datos |

En todas las páginas pon 3 **segmentaciones** arriba: `rutas[zona]`, `ordenes[fecha_envio]` (por año) y `ordenes[medio_pago]`.
Para que filtren todas las páginas: **Vista → Sincronizar segmentaciones**.

### Página 1 — Resumen ejecutivo
```
┌────────┬────────┬────────┬────────┬────────┬────────┐
│ Total  │ Tasa   │ Tasa   │Órdenes │Puntaje │ % crít.│  ← 6 tarjetas
│ órdenes│ entrega│ cancel.│abiertas│promedio│        │
├────────┴────────┴────┬───┴────────┴────────┴────────┤
│ Anillo: órdenes por  │ Columnas: Ingresos totales   │
│ ordenes[estado]      │ por año de fecha_envio       │
└──────────────────────┴──────────────────────────────┘
```

### Página 2 — Zonas y rutas
- **Barras agrupadas:** eje `rutas[zona]`, valor `Tasa de cancelación`, ordenado de mayor a menor. Centro debería quedar primero.
- **Matriz:** filas `rutas[zona]`; valores `Total órdenes`, `Tasa de cancelación`, `Puntaje promedio`, `% reclamos por retraso`, `Distancia promedio (km)` e `Ingresos totales`. En la tasa de cancelación usa *Formato condicional → Color de fondo* (verde → rojo).
- **Barras:** eje `rutas[ciudad_destino]`, valor `Tasa de cancelación`.
- **Dispersión:** detalle `rutas[zona]`, X `Distancia promedio (km)`, Y `Tasa de cancelación`, tamaño `Total órdenes`.

### Página 3 — Satisfacción
- 3 tarjetas: `Puntaje promedio`, `% clientes satisfechos` y `% valoraciones críticas`.
- **Columnas:** eje `valoraciones[puntaje]` (1 a 5), valor `Total órdenes` (distribución de notas).
- **Barras:** eje `valoraciones[comentario]`, valor `Total órdenes`.
- **Barras agrupadas:** eje `rutas[zona]`, valores `Puntaje promedio` y `% reclamos por retraso`.

### Página 4 — Cumplimiento y calidad de datos
- **Embudo:** grupo `eventos_seguimiento[estado]`, valor recuento de `orden_id`. Muestra cuántas órdenes llegan a cada etapa (100 → 100 → 69 → 33).
- 3 tarjetas: `Tiempo promedio de entrega (días)`, `% estados coherentes` y `Órdenes con estado inconsistente`.
- **Columnas apiladas:** eje `ordenes[estado]`, leyenda `ordenes[estado_seguimiento]` (para ver dónde no coinciden).
- **Barras:** eje `ordenes[medio_pago]`, valor `Tasa de cancelación`.

---

## 7. Cifras esperadas (sin filtros), para comprobar que todo cuadra

Las calculé con pandas el 27-10-2026 sobre los mismos datos de Atlas.

| KPI | Global | Centro | Norte | Oriente | Poniente | Sur |
|---|---|---|---|---|---|---|
| Total órdenes | 100 | 17 | 22 | 26 | 22 | 13 |
| Tasa de cancelación | 23,0 % | **47,1 %** | 36,4 % | 7,7 % | 9,1 % | 23,1 % |
| Tasa de entrega | 27,0 % | 29,4 % | 18,2 % | 26,9 % | 40,9 % | 15,4 % |
| Puntaje promedio | 3,07 | **2,71** | 3,00 | 3,35 | 3,14 | 3,00 |
| % valoraciones críticas | 37,0 % | 47,1 % | 36,4 % | 30,8 % | 31,8 % | 46,2 % |
| % clientes satisfechos | 45,0 % | 35,3 % | 36,4 % | 53,8 % | 50,0 % | 46,2 % |
| % reclamos por retraso | 14,0 % | 17,6 % | 13,6 % | 19,2 % | 4,5 % | 15,4 % |
| Distancia promedio (km) | — | 1.553 | 870 | 986 | 1.415 | 894 |

Otras cifras globales:
- 50 órdenes abiertas.
- Ingresos de $10.939.613 y ticket promedio de $109.396.
- 18 % de estados coherentes, con 82 órdenes inconsistentes.
- 23 órdenes canceladas que igual tienen valoración.
- Tiempo de entrega: 6,0 días en las 33 órdenes con evento «Entregado».
- Cancelación por medio de pago: Transferencia 31,2 %, Tarjeta 20,6 % y Efectivo 17,6 %.
- Ciudades de destino con más cancelación: Puerto Montt (38,9 %) y Arica (37,5 %). La Serena tiene 0 %.

## 8. Qué contar en la presentación

1. **Zona crítica: Centro.** Tiene la mayor cancelación (47 %, el doble del promedio), el peor puntaje (2,71) y las rutas más largas (1.553 km en promedio). Recomendación: revisar esas rutas y dividirlas en tramos o centros de distribución intermedios.
2. **Satisfacción baja:** solo el 45 % de los clientes pone nota 4 o 5, y el 37 % es crítico (nota ≤ 2).
3. **Cumplimiento de plazos:** el tiempo registrado es de 6 días en todas las entregas, así que con estos datos no se distinguen zonas rápidas de lentas. La señal de retraso viene de los reclamos («Tuvo retraso», 14 %; Oriente y Centro son los más altos). Recomendación: guardar una **fecha comprometida (SLA)** en cada orden para medir el % de entregas a tiempo.
4. **Calidad de datos:** solo el 18 % de las órdenes tiene el mismo estado en `ordenes_entrega` y en `seguimiento`. Antes de automatizar decisiones, hay que corregir la sincronización entre colecciones (validaciones con `$jsonSchema` o actualizar ambas en una transacción).
5. **KPIs propuestos para el seguimiento operativo:** tasa de cancelación por zona, % de entregas a tiempo (una vez exista el SLA), puntaje promedio, % de valoraciones críticas y % de estados coherentes.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| «No se encontró MONGO_URI» | Falta el `.env` en la carpeta del proyecto, o el parámetro `RutaProyecto` (*Transformar datos → Administrar parámetros*) no apunta a tu copia del repositorio |
| Timeout de conexión | Tu IP no está permitida en Atlas → *Network Access*, o no tienes internet |
| Error de Python / pandas en Power BI | Revisa el paso 1. Si sigue fallando, usa el plan B con CSV |
| Las tarjetas por zona muestran el mismo valor en todas | Falta una relación o está inactiva (paso 3) |
| La vista TMDL marca error en la medida `Canceladas con valoración` | La relación ordenes ↔ valoraciones no tiene filtro cruzado *Ambos* |
