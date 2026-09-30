# 03 Extractor de Datos Estructurados desde Documentos 

import json
import re  
from queue import Full
import ollama
from typing import Literal, Annotated 
from fastapi import FastAPI, UploadFile, File, HTTPException # pyright: ignore[reportMissingImports]
from fastapi.responses import PlainTextResponse, RedirectResponse # type: ignore
from pydantic import BaseModel, Field, field_validator, ValidationError
from datetime import date
from typing import Literal
from typing import List 

app = FastAPI(
    title="03 Extractor de Datos Estructurados desde Documentos Curso llm",
    description="API para procesar lotes de documentos usando Ollama(llama3) y Validación de Pydantic proyecto 03 "
)

# Inicializamos el cliente de Ollama apuntando al servicio local
client = ollama.Client(host='http://127.0.0.1:11434')

# Modelo a utilizar
MODELO_OLLAMA = "llama3"  

# busqueda de carpeta de docs
@app.get("/", include_in_schema=False)
async def redirigir_a_docs():
    return RedirectResponse(url="/docs")

# ==========================================
#  ESQUEMA DE DATOS Pydantic  
# ==========================================
class FacturaExtraida(BaseModel):
    proveedor: str = Field(description="Nombre o razón social de la empresa emisora")
    fecha_emision: date = Field(description="Fecha de emisión del documento en formato YYYY-MM-DD")
    monto_total: float = Field(description="Monto total del cobro expresado en número flotante")
    moneda: Literal["MXN", "USD", "EUR"] = Field(description="Código ISO de la divisa utilizada (estrictamente MXN, USD o EUR)")
    rfc_emisor: str = Field(description="Registro Federal de Contribuyentes (RFC) de quien emite")
    concepto_principal: Literal["Renta", "Papelería", "Gasto Comercial", "Otros"] = Field(
        description="Categoría conceptual del gasto de acuerdo a la naturaleza descrita en el documento"
    )
    numero_doc: str = Field(description="El número de folio o identificador único de la factura (ej. A-4592, Folio 883)")
   

    @field_validator('monto_total')
    @classmethod
    def validar_monto(cls, valor: float) -> float:
        if valor <= 0:
            raise ValueError("El monto total debe ser un número positivo.")
        return valor
    
    @field_validator('numero_doc')
    @classmethod
    def validar_folio_documento(cls, valor: str) -> str:
        folio_limpio = valor.strip()

        # El folio debe tener max 20 caracteres para evitar frases largas como "INVOICE DATE" o "FACTURA NO"
        # Si el LLM extrae una frase larga (como "INVOICE DATE"), trona aquí.
        if len(folio_limpio) > 20:
            raise ValueError(
                f"Estructura de folio incorrecta. El texto es demasiado largo para ser un folio válido "
                f"({len(folio_limpio)} caracteres). Valor recibido: '{valor}'"
            )

        # Regla de Caracteres Permitidos:
        patron_correcto = r"^[A-Z0-9#_\-]+$"
        #Expresiones Regulares para validar el folio: Solo letras mayúsculas, números, guiones y guion bajo. No se permiten espacios ni caracteres especiales.
        if not re.match(patron_correcto, folio_limpio.upper()):
            raise ValueError(
                f"Estructura de folio incorrecta. Un folio válido solo debe contener caracteres alfanuméricos "
                f"sin espacios (ej. A-4592, 883, INV_2026, AR5656). Valor recibido: '{valor}'"
            )

        # Debe conetener un numero 
        if not any(char.isdigit() for char in folio_limpio):
            raise ValueError(f"El folio debe contener al menos un caracter numérico. Valor recibido: '{valor}'")

        return folio_limpio

 