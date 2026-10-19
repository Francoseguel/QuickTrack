from pydantic import BaseModel, Field
from typing import Optional, List

class OrdenCrear(BaseModel):
    id: str = Field(..., alias="_id", description="Identificador único de la orden (ej. orden_999)")
    cliente_id: str = Field(..., description="ID del cliente asociado")
    ruta_id: str = Field(..., description="ID de la ruta logística")
    medio_pago: str = Field(..., description="Medio de pago (Tarjeta, Efectivo, Transferencia)")
    total: float = Field(..., gt=0, description="Monto total de la orden")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "orden_101",
                "cliente_id": "cli_15",
                "ruta_id": "ruta_2",
                "medio_pago": "Tarjeta",
                "total": 125000.0
            }
        }

class ActualizarEstado(BaseModel):
    nuevo_estado: str = Field(..., description="Nuevo estado (En preparación, En tránsito, Entregado, Cancelado)")
    fecha_evento: str = Field(..., description="Fecha y hora del cambio de estado (ISO 8601)")

    class Config:
        json_schema_extra = {
            "example": {
                "nuevo_estado": "En tránsito",
                "fecha_evento": "2026-03-30T14:30:00"
            }
        }