import os
import json
import ollama
import oracledb 
from datetime import datetime
from pydantic import ValidationError
from extractor import FacturaExtraida

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
CARPETA_DOCUMENTOS = "./documentos"
MODELO_OLLAMA = "llama3"  
MAX_REINTENTOS = 3
client = ollama.Client(host='http://127.0.0.1:11434')

# ==========================================
# CONFIGURACIÓN DE CONEXIÓN ORACLE 
# ==========================================
ORACLE_USER = "XXFAH_INTERFACE"
ORACLE_PASSWORD = "f4h_1nTFAQ4"
ORACLE_DSN = "172.25.7.4:1522/FAQA12"  

try:
    oracledb.init_oracle_client(lib_dir=r"C:\Oracle\instantclient_23_26")
    print("✔ Inicialización de Oracle ...........")
except Exception as e:
    print(f" No se pudieron cargar las librerías de Oracle: {str(e)}")
    

def guardar_en_oracle(datos: dict, nombre_archivo) -> bool:
    """Se encarga de insertar de forma segura los datos validados en la base de datos Oracle."""
    connection = None
    cursor = None
    try:
   
        connection = oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)
        cursor = connection.cursor()
        
        sql = """
            INSERT INTO XXFAH_INTERFACE.FACTURAS_EXTRAIDAS 
            (proveedor, fecha_emision, monto_total, moneda, rfc_emisor, concepto_principal, numero_doc,nombre_archivo)
            VALUES (:1, TO_DATE(:2, 'YYYY-MM-DD'), :3, :4, :5, :6, :7, :8)
        """
        # valores de la tabla interface para insertar en la base de datos Oracle
        valores = (
            str(datos["proveedor"]),
            str(datos["fecha_emision"]),  
            float(datos["monto_total"]),
            str(datos["moneda"]),
            str(datos["rfc_emisor"]),
            str(datos["concepto_principal"]),
            str(datos["numero_doc"])   ,
            nombre_archivo
        )
        
        cursor.execute(sql, valores)
        connection.commit()
        return True
        
    except oracledb.DatabaseError as e:
        # Control de Errores
        error_obj, = e.args
        codigo_oracle = error_obj.code  # Devuelve el número (ej. 1 para ORA-00001)
        mensaje_oracle = error_obj.message
        
        # Cach de errores específicos de Oracle
        if codigo_oracle == 1:
            print(f"    !  Registro duplicado. El folio de factura '{datos['numero_doc']}' ya existe en Tabla de interface.")
            # Retornamos False para que el pipeline lo registre en el reporte final .txt sin tronar
            return False
        else:
            # Cualquier otro error de base de datos 
            print(f"    ! Error general de Base de Datos (ORA-{codigo_oracle:05d}): {mensaje_oracle}")
            return False
            
    except Exception as e:
        print(f"    ! Error inesperado del sistema : {str(e)}")
        return False
        
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
# ==========================================
# PIPELINE DE EJECUCIÓN
# ==========================================
def ejecutar_pipeline_directo():
    print("==========================================================================")
    print("  INICIANDO EXTRACCIÓN y CARGA DE DOC A ORACLE EBS------------------------")
    print("==========================================================================\n")
    
    if not os.path.exists(CARPETA_DOCUMENTOS):
        print(f"! Error: La carpeta '{CARPETA_DOCUMENTOS}' no existe.")
        return

    archivos = [f for f in os.listdir(CARPETA_DOCUMENTOS) if f.endswith('.txt')]
    archivos.sort()
    
    if not archivos:
        print(f"! No se encontraron archivos .txt en '{CARPETA_DOCUMENTOS}'.")
        return

    conteo_exito = 0
    conteo_fallo = 0
    esquema_json = FacturaExtraida.model_json_schema()
    reporte_final = {}

    for nombre_archivo in archivos:
        print(f"Procesando archivo: --> [{nombre_archivo}]")
        
        try:
            with open(os.path.join(CARPETA_DOCUMENTOS, nombre_archivo), 'r', encoding='utf-8') as f:
                texto_documento = f.read()
                
            intento = 0
            resultado_doc = {"estado": "Fallo", "datos": None, "motivo": "No procesado"}
            
            while intento < MAX_REINTENTOS:
                intento += 1
                try:
                    respuesta = client.chat(
                        model=MODELO_OLLAMA,
                        messages=[
                            {"role": "system", "content": "Extrae los datos en estricto formato JSON coincidente con el esquema."},
                            {"role": "user", "content": texto_documento}
                        ],
                        format=esquema_json,
                        options={"temperature": 0.0}
                    )
                    
                    datos_dict = json.loads(respuesta['message']['content'])
                    objeto_validado = FacturaExtraida(**datos_dict)
                      
                    resultado_doc = {
                        "estado": "Éxito",
                        "datos": objeto_validado.model_dump(mode="json"),
                        "motivo": f"✔ Extracción exitosa y validada en el intento {intento}."
                    }
                    break
                    
                except json.JSONDecodeError:
                    resultado_doc["motivo"] = "El LLM no retornó una estructura JSON válida."
                except ValidationError as e:
                    errores = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
                    resultado_doc["motivo"] = f"!Fallo de esquema Pydantic -> {', '.join(errores)}"
                except Exception as e:
                    resultado_doc["motivo"] = f"!Error de comunicación con Ollama: {str(e)}"
            
            # --- SECCIÓN DE BASE DE DATOS ---
            if resultado_doc["estado"] == "Éxito":
                print("    ✔ Extracción Inteligente: OK.")
                # Intentamos guardar los datos validados directamente en Oracle
                db_guardado = guardar_en_oracle(resultado_doc["datos"], nombre_archivo)
                if db_guardado:
                    print("    ✔ Persistencia en Oracle local: EXITOSA.\n")
                    conteo_exito += 1
                else:
                    resultado_doc["estado"] = "Fallo"
                    resultado_doc["motivo"] += " -->! Fallo al insertar en Oracle. Verifique la base de datos."
                    conteo_fallo += 1
            else:
                conteo_fallo += 1
                print(f"    ! Resultado: FALLO. Motivo: {resultado_doc['motivo']}\n")
                
            reporte_final[nombre_archivo] = resultado_doc
                
        except Exception as e:
            conteo_fallo += 1
            print(f"    ! Error crítico al leer el archivo físico: {str(e)}\n")

    # ==========================================
    # GENERACIÓN DEL REPORTE FINAL EN TEXTO PLANO
    # ==========================================
    tasa_exito = (conteo_exito / len(archivos)) * 100
    reporte_txt = "==========================================================================\n"
    reporte_txt += "        Reporte Log de Proceso de Carga y Extracion de datos              \n"
    reporte_txt += "==========================================================================\n"
    reporte_txt += f" Total Documentos            : {len(archivos)}\n"
    reporte_txt += f" Docs Cargado con Exito      : {conteo_exito} \n"
    reporte_txt += f" Docs  Fallidos              : {conteo_fallo} \n"
    reporte_txt += "==========================================================================\n"
    reporte_txt += "\n"
    
    for doc, resultado in reporte_final.items():
        reporte_txt += f"\n----------------------------- Archivo: {doc}-----------------------------\n"
        reporte_txt += f"   • Estatus: {resultado['estado']}\n"
        reporte_txt += f"   • Mensaje: {resultado['motivo']}\n"
        if resultado['datos']:
            datos_formateados = json.dumps(resultado['datos'], ensure_ascii=False, indent=4).replace('\n', '\n     ')
            reporte_txt += f"   • Datos Extraídos:\n     {datos_formateados}\n"
      #  reporte_txt += "-" * 50 + "\n"
        
    print(reporte_txt)
    
    timestamp_log = datetime.now().strftime("%y%m%d%H%M%S")
    nombre_archivo_log = f"reporte_log_{timestamp_log}.txt"
    
    with open(nombre_archivo_log, "w", encoding="utf-8") as f_txt:
        f_txt.write(reporte_txt)
    print(f" Reporte LOG: ---->>> {nombre_archivo_log}")

if __name__ == "__main__":
    ejecutar_pipeline_directo()
