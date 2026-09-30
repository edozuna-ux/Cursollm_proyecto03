-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Fundamentos de Arquitectura LLM 
# Name: Extractor de Datos Estructurados desde Documentos 03
# Descripcion: 
             Este proyecto implementa un pipeline  diseñado para transformar texto desestructurado (transcripciones de facturas y recibos comerciales) en un objeto de datos estructurado y validado mediante Pydantic v2. 

            el alcance de este programa asgura la carga de los registros a una base de datos Oracle, Evita que los errores de datos o alucinaciones del modelo sean interceptados programacion sin detener el procesamiento del lote.
 # Fecha    Name         Vers   Descripcion           
 # 20260928 Edgar Ozuna  1.0    Carga de Archivos como tickets de facturas y recibos.           

------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

##  Arquitectura del Sistema 

1. `Cargalote.py` main principal del programa para extraer e insertar informacion a la base de datos Oracle
   - Se conecta al servidor local de `Ollama` utilizando el SDK oficial.
   - Aplica decodificación restringida (`format=esquema_json`) y temperatura `0.0` para mayor precision.
   - Asegurar la ejecución en un interceptor de resiliencia con un límite máximo de 2 reintentos por documento.
   - Maneja el control de las excepciones de lectura y validación para evitar que un documento para no interrumpir el proceso de los demas archivos.
2. `Extractor.py`  : API para procesar lotes de documentos usando Ollama(llama3) y Validación de Pydantic    
3. `documentos/` (Datos):  Carpeta física con un lote de 5  archivos  de prueba  3 casos con datos correctos y 2 con datos incorrectos .
4. `reporte_log_sysdate.txt` (Reporte Log):  Reporte LOG del proceso de carga de archivo a detalle.

---

##  Justificación del Esquema de Datos

El dominio seleccionado fue el de  Facturación y Recibos Comerciales .  de 8 campos detallados , cubriendo los requisitos obligatorios de tipos:

| Campo | Tipo de Dato | Descripción / Regla de Validación |
| :--- | :--- | :--- |
| `proveedor` | `str` (Texto) | Nombre o razón social de la empresa emisora. |
| `fecha_emision` | `date` (Fecha) | Forzado estrictamente en formato ISO `YYYY-MM-DD`. |
| `monto_total` | `float` (Numérico) | Validador custom: Debe ser estrictamente un número positivo mayor a cero (`> 0`). Intercepta notas de crédito o montos negativos erróneos. |
| `moneda` | `Literal["MXN", "USD", "EUR"]` (Categórico) | Enum restringido. Filtra divisas no soportadas por el sistema contable (ej. YEN). |
| `rfc_emisor` | `str` (Texto) | Registro Federal de Contribuyentes para validación hacendaria. |
| `concepto_principal` | `Literal["Renta", "Papelería", "Gasto Comercial", "Otros"]` (Categórico) | Clasificación automática del tipo de gasto para fines de CRM/ERP. |
  `numero_doc` | `numero alfanumerico folio ticket etc`  | determinar el tipo de documento se esta procesando |  
| `nombre_archivo` | `nombre del archivo a procesar`  | para identificacion en base de datos de oracle |  
---

Los datos seran insertados en un tabla de Base de datos Oracle con la siguiente estructura, en caso de no tener conexion solo procesar los archivos:

`CREATE TABLE XXFAH_INTERFACE.FACTURAS_EXTRAIDAS`
(
  ID                  NUMBER                    DEFAULT "XXFAH_INTERFACE"."ISEQ$$_8400180".nextval NOT NULL,  --secuencia automatica
  NUMERO_DOC          VARCHAR2(250 BYTE),
  PROVEEDOR           VARCHAR2(150 BYTE),
  FECHA_EMISION       DATE,
  MONTO_TOTAL         NUMBER(15,2),
  MONEDA              VARCHAR2(10 BYTE),
  RFC_EMISOR          VARCHAR2(20 BYTE),
  CONCEPTO_PRINCIPAL  VARCHAR2(50 BYTE),
  FECHA_REGISTRO      DATE                      DEFAULT SYSDATE               NOT NULL, --por default fecha del sistema
  NOMBRE_ARCHIVO      VARCHAR2(100 BYTE)
)
NOLOGGING 
COMPRESS 
NOCACHE
NOPARALLEL
NOMONITORING;

##  Gestión de Errores y Estrategia de Resiliencia

El extractor de juguete tradicional asume un "camino feliz" donde el LLM siempre responde correctamente. Este sistema de producción implementa un **Mecanismo de Reintentos Limitados con Intercepción:**

- JSONDecodeError:  en caso de un un JSON mal escrito o formado se interpreta como Fallo para intentar nuevamente.
- ValidationError (Pydantic): Si el LLM alucina un campo, utiliza una categoria erronea o entrega un monto negativo. validador de Pydantic lanza una excepción estructurada. El módulo extractor lee el error, lo reporta en consola y consume un intento del ciclo de reintento. 
- asegurr la carga del Lote:  Si tras 2 intentos el documento sigue fallando, el estado del archivo se marca explícitamente como `Fallo`, se adjunta el motivo del error, y el pipeline  continúa con el siguiente archivo sin terminar la ejecucion.
- oracledb.DatabaseError: en caso de un error de insercion de base de datos  u otro error se mostrara el mensaje, los mas comunes para este caso son duplicidad , 
  en caso de reproceso de los mismos archivos.  la llave unica es el campo numero_doc y RFC.
---

#  Instrucciones de Ejecución

# Requisitos Previos
- Tener instalado Python 3.10.12
- Tener la aplicación de escritorio Ollama activa en segundo plano con el modelo `llama3` descargado (`ollama run llama3`).
- Tener conexion a base de datos oracle (en caso que no solo procesara los archivos sin insertar a alguna bd.)

# Pasos para Correr el Proyecto

1. Clona o posiciona tu terminal en el directorio raíz del proyecto:
     cd C:\proyect\import_invoice
2. Instala las dependencias necesarias:
   pip install ollama pydantic
3. Ejecuta el pipeline del lote de forma directa:
   python cargalote.py

al finaliza se creara un reporte log con fecha hora y segundos tipo txt.
