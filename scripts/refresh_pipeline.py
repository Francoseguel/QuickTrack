"""
Orquestador de actualización automatizada de QuickTrack (IE8 — EP3 BDY0101).

Ejecuta en un solo comando todo el flujo analítico:
1. Auditoría empírica RICE (scripts/rice_audit.py).
2. Extracción NoSQL y transformación a modelo estrella CSV (scripts/etl_analitica.py).
3. Validación de conteos, integridad y cuadre de KPIs (scripts/validar_etl.py).
4. Registro estructurado de la ejecución en data/export/ultimo_refresh.json.

Uso:
    python scripts/refresh_pipeline.py --source auto
    python scripts/refresh_pipeline.py --source local
    python scripts/refresh_pipeline.py --source atlas
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.etl_analitica import EXPORT_DIR, ejecutar_etl
from scripts.rice_audit import ejecutar_auditoria
from scripts.validar_etl import validar_etl


def ejecutar_refresh(source: str = "auto") -> int:
    inicio = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    print("=" * 72)
    print(f"QUICKTRACK — PIPELINE AUTOMATIZADO DE ACTUALIZACIÓN ({timestamp})")
    print(f"Origen solicitado: {source}")
    print("=" * 72)

    # Paso 1: Auditoría RICE
    print("\n[PASO 1/3] Ejecutando auditoría empírica RICE...")
    _, modo_rice = ejecutar_auditoria(source=source)

    # Paso 2: ETL analítico y regeneración de CSV
    print("\n[PASO 2/3] Ejecutando extracción, transformación y exportación CSV...")
    metadata = ejecutar_etl(source=source)
    modo_etl = metadata["modo_origen"]

    # Paso 3: Validación contra la fuente
    print("\n[PASO 3/3] Ejecutando validación de integridad y cuadre de KPIs...")
    validacion_ok = validar_etl(source=modo_etl)

    duracion_seg = round(time.perf_counter() - inicio, 2)
    registro = {
        "timestamp_utc": timestamp,
        "source_solicitado": source,
        "modo_ejecutado": modo_etl,
        "modo_rice": modo_rice,
        "validacion_aprobada": bool(validacion_ok),
        "duracion_segundos": duracion_seg,
        "archivos_actualizados": metadata["archivos_generados"],
        "kpis": metadata["kpis_resumen"],
    }

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = EXPORT_DIR / "ultimo_refresh.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 72)
    if validacion_ok:
        print(
            f"[OK] Refresh completado en {duracion_seg}s (modo={modo_etl}). "
            f"Log: {log_path.relative_to(BASE_DIR)}"
        )
        print("=" * 72)
        return 0

    print(f"[ERROR] La validación falló tras {duracion_seg}s. Revise los mensajes anteriores.")
    print("=" * 72)
    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta RICE + ETL + Validación de QuickTrack en un solo comando."
    )
    parser.add_argument(
        "--source",
        choices=["auto", "atlas", "local"],
        default="auto",
        help="Origen de extracción: auto (Atlas con fallback local), atlas o local.",
    )
    args = parser.parse_args()
    sys.exit(ejecutar_refresh(source=args.source))


if __name__ == "__main__":
    main()
