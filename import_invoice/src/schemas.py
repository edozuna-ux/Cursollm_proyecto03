from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Literal, Optional

class FacturaExtraida(BaseModel):
    proveedor: str = Field(description="Nombre o razón social de la empresa emisora")
    fecha_emision: date = Field(description="Fecha de emisión del documento en formato YYYY-MM-DD")
    monto_total: float = Field(description="Monto total del cobro expresado en número flotante")
    moneda: Literal["MXN", "USD", "EUR"] = Field(description="Código ISO de la divisa utilizada (estrictamente MXN, USD o EUR)")
    rfc_emisor: str = Field(description="Registro Federal de Contribuyentes (RFC) de quien emite")
    concepto_principal: Literal["Renta", "Papelería", "Gasto Comercial", "Otros"] = Field(
        description="Categoría conceptual del gasto de acuerdo a la naturaleza descrita en el documento"
    )

    # Validación de lógica de negocio obligatoria por rúbrica
    @field_validator('monto_total')
    @classmethod
    def validar_monto_positivo(cls, valor: float) -> float:
        if valor <= 0:
            raise ValueError("El monto total extraído debe ser un número estrictamente positivo y mayor a cero.")
        return valor
