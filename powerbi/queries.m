// =============================================================================
// CONSULTAS POWER QUERY (M) — QUICKTRACK ANALÍTICA (EP3 BDY0101)
// =============================================================================
// Instrucciones:
// 1. En Power BI Desktop -> Transformar datos -> Administrar parámetros -> Nuevo parámetro:
//    Nombre: RutaExport | Tipo: Texto | Valor actual: <ruta local a QuickTrack\data\export>
// 2. Cree una "Consulta en blanco" por cada bloque de abajo y pegue el código
//    en el "Editor avanzado".
// Nota: Se usa cultura "en-US" en ChangeType para interpretar el punto decimal (.)
// exportado por pandas sin conflictos en sistemas Windows configurados en español.

// -----------------------------------------------------------------------------
// PARÁMETRO: RutaExport
// -----------------------------------------------------------------------------
"C:\Users\mapap\Desktop\sexto semestre\BD NR\QuickTrack\data\export" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]


// -----------------------------------------------------------------------------
// TABLA 1: fact_ordenes (Tabla de hechos principal — grano: 1 fila por orden)
// -----------------------------------------------------------------------------
let
    Origen = Csv.Document(
        File.Contents(RutaExport & "\fact_ordenes.csv"),
        [Delimiter=",", Columns=22, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(
        Encabezados,
        {
            {"orden_id", type text},
            {"fecha_key", Int64.Type},
            {"fecha_envio", type date},
            {"anio", Int64.Type},
            {"mes", Int64.Type},
            {"anio_mes", type text},
            {"cliente_num_id", Int64.Type},
            {"ruta_id", type text},
            {"zona", type text},
            {"estado", type text},
            {"medio_pago", type text},
            {"total", type number},
            {"puntaje", Int64.Type},
            {"es_entregado", Int64.Type},
            {"es_cancelado", Int64.Type},
            {"es_valoracion_critica", Int64.Type},
            {"num_eventos_seg", Int64.Type},
            {"dias_en_seguimiento", Int64.Type},
            {"dias_hasta_entrega_historial", Int64.Type},
            {"tiene_entregado_historial", Int64.Type},
            {"estado_actual_seg", type text},
            {"discrepancia_estado_seg", Int64.Type}
        },
        "en-US"
    )
in
    Tipos


// -----------------------------------------------------------------------------
// TABLA 2: fact_seguimiento_eventos (Hechos de trazabilidad — $unwind historial)
// -----------------------------------------------------------------------------
let
    Origen = Csv.Document(
        File.Contents(RutaExport & "\fact_seguimiento_eventos.csv"),
        [Delimiter=",", Columns=10, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(
        Encabezados,
        {
            {"evento_id", type text},
            {"seg_id", type text},
            {"orden_id", type text},
            {"ruta_id", type text},
            {"zona", type text},
            {"orden_evento", Int64.Type},
            {"estado_evento", type text},
            {"fecha_evento", type date},
            {"dias_desde_inicio", Int64.Type},
            {"dias_desde_evento_anterior", Int64.Type}
        },
        "en-US"
    )
in
    Tipos


// -----------------------------------------------------------------------------
// TABLA 3: dim_rutas (Dimensión geográfica y de tramos)
// -----------------------------------------------------------------------------
let
    Origen = Csv.Document(
        File.Contents(RutaExport & "\dim_rutas.csv"),
        [Delimiter=",", Columns=7, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(
        Encabezados,
        {
            {"ruta_id", type text},
            {"zona", type text},
            {"ciudad_origen", type text},
            {"ciudad_destino", type text},
            {"distancia_km", type number},
            {"tramo", type text},
            {"rango_distancia", type text}
        },
        "en-US"
    )
in
    Tipos


// -----------------------------------------------------------------------------
// TABLA 4: dim_clientes (Dimensión de clientes sin PII según matriz RICE)
// -----------------------------------------------------------------------------
let
    Origen = Csv.Document(
        File.Contents(RutaExport & "\dim_clientes.csv"),
        [Delimiter=",", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(
        Encabezados,
        {
            {"cliente_num_id", Int64.Type},
            {"cliente_id_str", type text},
            {"pais", type text}
        },
        "en-US"
    )
in
    Tipos


// -----------------------------------------------------------------------------
// TABLA 5: dim_fecha (Dimensión calendario continuo — marcar como Tabla de fechas)
// -----------------------------------------------------------------------------
let
    Origen = Csv.Document(
        File.Contents(RutaExport & "\dim_fecha.csv"),
        [Delimiter=",", Columns=9, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),
    Tipos = Table.TransformColumnTypes(
        Encabezados,
        {
            {"fecha_key", Int64.Type},
            {"fecha", type date},
            {"anio", Int64.Type},
            {"trimestre", type text},
            {"mes", Int64.Type},
            {"nombre_mes", type text},
            {"anio_mes", type text},
            {"dia_semana", type text},
            {"es_fin_de_semana", Int64.Type}
        },
        "en-US"
    )
in
    Tipos


// -----------------------------------------------------------------------------
// ALTERNATIVA CLOUD/API: Consumo directo desde FastAPI (/analitica/ordenes)
// (Requiere levantar la API: uvicorn api.main:app --port 8000)
// -----------------------------------------------------------------------------
/*
let
    UrlApi = "http://localhost:8000/analitica/ordenes",
    Fuente = Json.Document(Web.Contents(UrlApi)),
    Tabla = Table.FromList(Fuente, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    Expandida = Table.ExpandRecordColumn(
        Tabla,
        "Column1",
        {"orden_id", "fecha_envio", "cliente_num_id", "ruta_id", "zona", "estado", "medio_pago", "total", "puntaje", "dias_en_seguimiento"}
    )
in
    Expandida
*/
