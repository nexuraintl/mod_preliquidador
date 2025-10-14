"""
PRELIQUIDADOR DE RETEFUENTE - COLOMBIA
====================================

Sistema automatizado para procesar facturas y calcular retención en la fuente
usando Google Gemini AI y FastAPI.

ARQUITECTURA MODULAR:
- Clasificador/: Clasificación de documentos con Gemini
- Liquidador/: Cálculo de retenciones según normativa
- Extraccion/: Extracción de texto de archivos (PDF, OCR, Excel, Word)
- Static/: Frontend y archivos estáticos
- Results/: Almacenamiento de resultados organizados por fecha

 FUNCIONALIDAD INTEGRADA:
- Retención en la fuente (funcionalidad original)
- Estampilla pro universidad nacional - obra publica (nueva funcionalidad)
- IVA y ReteIVA (nueva funcionalidad)
- Procesamiento paralelo cuando ambos impuestos aplican

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import asynccontextmanager

# FastAPI y dependencias web
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuración de logging PROFESIONAL
import logging
import sys

def configurar_logging():
    """
    Configura el logging profesional para la aplicación.
    - Elimina handlers existentes para evitar duplicación.
    - Establece un formato claro con timestamp.
    - Envía logs a la consola (stdout).
    """
    # Evitar duplicación de logs por el reloader de uvicorn
    if logging.getLogger().hasHandlers():
        logging.getLogger().handlers.clear()
        print(" Logging CORREGIDO - Handlers duplicados eliminados")

    # Configurar el formato del log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Configurar un handler para la consola
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)

logger = logging.getLogger(__name__)

# ===============================
# IMPORTAR MÓDULOS LOCALES
# ===============================

# Importar clases desde módulos
from Clasificador import ProcesadorGemini
from Clasificador.clasificador_ica import ClasificadorICA
from Liquidador import LiquidadorRetencion
from Liquidador.liquidador_consorcios import LiquidadorConsorcios, convertir_resultado_a_dict as convertir_consorcio_a_dict
from Liquidador.liquidador_ica import LiquidadorICA
from Extraccion import ProcesadorArchivos

# Importar módulos de base de datos (SOLID: Clean Architecture Module)
from database import (
    DatabaseManager,
    SupabaseDatabase,
    BusinessDataService,
    crear_business_service
)

# Cargar configuración global - INCLUYE ESTAMPILLA Y OBRA PÚBLICA
from config import (
    inicializar_configuracion,
    obtener_nits_disponibles,
    validar_nit_administrativo,
    nit_aplica_retencion_fuente,
    codigo_negocio_aplica_estampilla_universidad,
    codigo_negocio_aplica_obra_publica,
    nit_aplica_iva_reteiva,  #  NUEVA IMPORTACIÓN IVA
    nit_aplica_ICA,  #  NUEVA IMPORTACIÓN ICA
    nit_aplica_tasa_prodeporte,  #  NUEVA IMPORTACIÓN TASA PRODEPORTE
    detectar_impuestos_aplicables_por_codigo,  #  DETECCIÓN AUTOMÁTICA POR CÓDIGO

)

# Dependencias para preprocesamiento Excel
import pandas as pd
import io

# ===============================
# INICIALIZACIÓN DE BASE DE DATOS
# ===============================

# Variable global para el gestor de base de datos
db_manager = None

# Variable global para el servicio de datos de negocio 
business_service = None

def inicializar_database_manager():
    """
    Inicializa el gestor de base de datos y servicios asociados usando variables de entorno.

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Función dedicada solo a inicialización de componentes de base de datos
    - DIP: Servicios dependen de abstracciones inyectadas
    """
    global db_manager, business_service
    try:
        # Obtener credenciales desde variables de entorno
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            logger.warning(" Variables de entorno SUPABASE_URL y SUPABASE_KEY no están configuradas")
            logger.warning(" DatabaseManager y BusinessService no serán inicializados")

            # Crear business service sin database manager (graceful degradation)
            business_service = crear_business_service(None)
            return None

        # Crear la implementación concreta
        supabase_db = SupabaseDatabase(supabase_url, supabase_key)

        # Crear el manager usando el patrón Strategy
        db_manager = DatabaseManager(supabase_db)

        # Crear business service con dependency injection (DIP)
        business_service = crear_business_service(db_manager)

        logger.info(" DatabaseManager y BusinessService inicializados correctamente")
        return db_manager

    except Exception as e:
        logger.error(f" Error inicializando DatabaseManager: {e}")
        db_manager = None

        # Crear business service sin database manager (graceful degradation)
        business_service = crear_business_service(None)
        return None

# ===============================
# FUNCIONES DE PREPROCESAMIENTO
# ===============================

def preprocesar_excel_limpio(contenido: bytes, nombre_archivo: str = "archivo.xlsx") -> str:
    """
    Preprocesa archivo Excel eliminando filas y columnas vacías.
    Mantiene formato tabular limpio con toda la información intacta.
    
    FUNCIONALIDAD:
    Elimina filas completamente vacías
    Elimina columnas completamente vacías
    Mantiene formato tabular pero limpio
    Conserva toda la información relevante
    Óptimo y simple
    Guarda automáticamente el archivo preprocesado
    
    Args:
        contenido: Contenido binario del archivo Excel
        nombre_archivo: Nombre del archivo (para logging)
        
    Returns:
        str: Texto extraído y limpio del Excel
    """
    try:
        logger.info(f" Preprocesando Excel: {nombre_archivo}")
        
        # 1. LEER EXCEL CON TODAS LAS HOJAS
        df_dict = pd.read_excel(io.BytesIO(contenido), sheet_name=None)
        
        texto_completo = ""
        total_hojas = 0
        filas_eliminadas_total = 0
        columnas_eliminadas_total = 0
        
        # 2. PROCESAR CADA HOJA CON LIMPIEZA
        if isinstance(df_dict, dict):
            total_hojas = len(df_dict)
            
            for nombre_hoja, dataframe in df_dict.items():
                # Estadísticas originales
                filas_orig = len(dataframe)
                cols_orig = len(dataframe.columns)
                
                #  LIMPIEZA SIMPLE: Eliminar filas y columnas completamente vacías
                df_limpio = dataframe.dropna(how='all')  # Filas vacías
                df_limpio = df_limpio.dropna(axis=1, how='all')  # Columnas vacías
                
                # Estadísticas después de limpieza
                filas_final = len(df_limpio)
                cols_final = len(df_limpio.columns)
                
                filas_eliminadas = filas_orig - filas_final
                columnas_eliminadas = cols_orig - cols_final
                filas_eliminadas_total += filas_eliminadas
                columnas_eliminadas_total += columnas_eliminadas
                
                # Agregar hoja al texto
                texto_completo += f"\n--- HOJA: {nombre_hoja} ---\n"
                
                if not df_limpio.empty:
                    # Convertir a texto manteniendo formato tabular limpio
                    texto_hoja = df_limpio.to_string(index=False, na_rep='', max_cols=None, max_rows=None)
                    texto_completo += texto_hoja
                else:
                    texto_completo += "[HOJA VACÍA DESPUÉS DE LIMPIEZA]"
                
                texto_completo += "\n"
                
        else:
            # UNA SOLA HOJA
            total_hojas = 1
            dataframe = df_dict
            
            # Estadísticas originales
            filas_orig = len(dataframe)
            cols_orig = len(dataframe.columns)
            
            #  LIMPIEZA SIMPLE: Eliminar filas y columnas vacías
            df_limpio = dataframe.dropna(how='all')  # Filas vacías
            df_limpio = df_limpio.dropna(axis=1, how='all')  # Columnas vacías
            
            # Estadísticas finales
            filas_final = len(df_limpio)
            cols_final = len(df_limpio.columns)
            
            filas_eliminadas_total = filas_orig - filas_final
            columnas_eliminadas_total = cols_orig - cols_final
            
            if not df_limpio.empty:
                texto_completo = df_limpio.to_string(index=False, na_rep='', max_cols=None, max_rows=None)
            else:
                texto_completo = "[ARCHIVO VACÍO DESPUÉS DE LIMPIEZA]"
        
        texto_final = texto_completo.strip()
        
        # 3. GUARDADO AUTOMÁTICO DEL ARCHIVO PREPROCESADO
        _guardar_archivo_preprocesado(nombre_archivo, texto_final, filas_eliminadas_total, columnas_eliminadas_total, total_hojas)
        
        # 4. LOGGING OPTIMIZADO
        logger.info(f" Preprocesamiento completado: {len(texto_final)} caracteres")
        logger.info(f" Hojas: {total_hojas} | Filas eliminadas: {filas_eliminadas_total} | Columnas eliminadas: {columnas_eliminadas_total}")
        logger.info(f" Archivo preprocesado guardado automáticamente")
        
        return texto_final
        
    except Exception as e:
        error_msg = f"Error en preprocesamiento Excel: {str(e)}"
        logger.error(f" {error_msg}")
        return error_msg

def _guardar_archivo_preprocesado(nombre_archivo: str, texto_preprocesado: str, 
                                 filas_eliminadas: int, columnas_eliminadas: int, total_hojas: int):
    """
    Guarda el archivo Excel preprocesado según nomenclatura {archivo_original}_preprocesado.txt
    
    FUNCIONALIDAD:
     Guarda en carpeta extracciones/ 
     Nomenclatura: {archivo_original}_preprocesado.txt
     Logs básicos para confirmar guardado exitoso
     Manejo de errores sin afectar flujo principal
    
    Args:
        nombre_archivo: Nombre del archivo original
        texto_preprocesado: Texto limpio extraído
        filas_eliminadas: Número de filas eliminadas
        columnas_eliminadas: Número de columnas eliminadas
        total_hojas: Número total de hojas procesadas
    """
    try:
        # 1. CREAR CARPETA EXTRACCIONES SIMPLE
        carpeta_extracciones = Path("extracciones")
        carpeta_extracciones.mkdir(exist_ok=True)
        
        # 2. CREAR NOMBRE SEGÚN NOMENCLATURA: {archivo_original}_preprocesado.txt
        # Limpiar nombre de archivo original (quitar caracteres especiales)
        nombre_base = "".join(c for c in nombre_archivo if c.isalnum() or c in "._-")
        
        # Quitar extensión original (.xlsx, .xls)
        if '.' in nombre_base:
            nombre_sin_extension = nombre_base.rsplit('.', 1)[0]
        else:
            nombre_sin_extension = nombre_base
            
        # Crear nombre final: {archivo_original}_preprocesado.txt
        nombre_final = f"{nombre_sin_extension}_preprocesado.txt"
        ruta_archivo = carpeta_extracciones / nombre_final
        
        # 3. CONTENIDO SIMPLE PERO COMPLETO
        contenido_final = f"""ARCHIVO EXCEL PREPROCESADO
=============================

Archivo original: {nombre_archivo}
Fecha procesamiento: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Hojas procesadas: {total_hojas}
Filas vacías eliminadas: {filas_eliminadas}
Columnas vacías eliminadas: {columnas_eliminadas}
Caracteres finales: {len(texto_preprocesado)}

=============================
TEXTO ENVIADO A GEMINI:
=============================

{texto_preprocesado}
"""
        
        # 4. GUARDAR ARCHIVO
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(contenido_final)
        
        # 5. LOG BÁSICO DE CONFIRMACIÓN
        logger.info(f" Archivo preprocesado guardado: extracciones/{nombre_final}")
        logger.info(f" Estadísticas: {filas_eliminadas} filas y {columnas_eliminadas} columnas eliminadas")
        
    except Exception as e:
        logger.error(f" Error guardando archivo preprocesado: {e}")
        # No fallar el preprocesamiento por un error de guardado

# ===============================
# FUNCIÓN PARA GUARDAR ARCHIVOS JSON
# ===============================

def guardar_archivo_json(contenido: dict, nombre_archivo: str, subcarpeta: str = "") -> bool:
    """
    Guarda archivos JSON en la carpeta Results/ organizados por fecha.
    
    FUNCIONALIDAD:
     Crea estructura Results/YYYY-MM-DD/
     Guarda archivos JSON con timestamp
     Manejo de errores sin afectar flujo principal
     Logs de confirmación
    Path absoluto para evitar errores de subpath
    
    Args:
        contenido: Diccionario a guardar como JSON
        nombre_archivo: Nombre base del archivo (sin extensión)
        subcarpeta: Subcarpeta opcional dentro de la fecha
        
    Returns:
        bool: True si se guardó exitosamente, False en caso contrario
    """
    try:
        # 1. CREAR ESTRUCTURA DE CARPETAS CON PATH ABSOLUTO
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        carpeta_base = Path.cwd()  # Path absoluto del proyecto
        carpeta_results = carpeta_base / "Results"
        carpeta_fecha = carpeta_results / fecha_actual
        
        if subcarpeta:
            carpeta_final = carpeta_fecha / subcarpeta
        else:
            carpeta_final = carpeta_fecha
            
        carpeta_final.mkdir(parents=True, exist_ok=True)
        
        # 2. CREAR NOMBRE CON TIMESTAMP
        timestamp = datetime.now().strftime("%H-%M-%S")
        nombre_final = f"{nombre_archivo}_{timestamp}.json"
        ruta_archivo = carpeta_final / nombre_final
        
        # 3. GUARDAR ARCHIVO JSON
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(contenido, f, indent=2, ensure_ascii=False)
        
        # 4. LOG DE CONFIRMACIÓN CON PATH RELATIVO SEGURO
        try:
            ruta_relativa = ruta_archivo.relative_to(carpeta_base)
            logger.info(f" JSON guardado: {ruta_relativa}")
        except ValueError:
            # Fallback si relative_to falla
            logger.info(f" JSON guardado: {nombre_final} en {carpeta_final.name}")
        
        return True
        
    except Exception as e:
        logger.error(f" Error guardando JSON {nombre_archivo}: {e}")
        return False

# ===============================
# CONFIGURACIÓN Y CONSTANTES
# ===============================

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Inicializar configuración global
inicializar_configuracion()

# Configurar APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CLOUD_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY no está configurada en el archivo .env")

# Importar conceptos retefuente  desde configuración
from config import CONCEPTOS_RETEFUENTE

# ===============================
# MODELOS DE DATOS
# ===============================

class DocumentoClasificado(BaseModel):
    nombre_archivo: str
    tipo_documento: str  # FACTURA, RUT, COTIZACION, ANEXO, ANEXO CONCEPTO CONTRATO
    confianza: float

class ConceptoIdentificado(BaseModel):
    concepto: str
    tarifa_retencion: float
    base_gravable: Optional[float] = None

class NaturalezaTercero(BaseModel):
    es_persona_natural: Optional[bool] = None
    es_declarante: Optional[bool] = None
    regimen_tributario: Optional[str] = None  # SIMPLE, ORDINARIO, ESPECIAL
    es_autorretenedor: Optional[bool] = None
    es_responsable_iva: Optional[bool] = None  # NUEVA VALIDACIÓN

# NUEVOS MODELOS PARA ARTÍCULO 383
class DeduccionArticulo383(BaseModel):
    valor: float = 0.0
    tiene_soporte: bool = False
    limite_aplicable: float = 0.0
    
class ConceptoIdentificadoArt383(BaseModel):
    """Concepto identificado específico para Artículo 383"""
    concepto: str
    base_gravable: float = 0.0
    
    
class CondicionesArticulo383(BaseModel):
    """Condiciones cumplidas para aplicar Artículo 383 - NUEVA ESTRUCTURA"""
    es_persona_natural: bool = False
    conceptos_identificados: List[ConceptoIdentificadoArt383] = []
    conceptos_aplicables: bool = False
    ingreso: float = 0.0
    es_primer_pago: bool = False
    documento_soporte: bool = False
    
    
class InteresesVivienda(BaseModel):
    """Información de intereses por vivienda"""
    intereses_corrientes: float = 0.0
    certificado_bancario: bool = False

class DependientesEconomicos(BaseModel):
    """Información de dependientes económicos"""
    nombre_encargado: str = ""
    declaracion_juramentada: bool = False

# 🆕 MODELO PARA MEDICINA PREPAGADA
class MedicinaPrepagada(BaseModel):
    """Información de medicina prepagada"""
    valor_sin_iva_med_prepagada: float = 0.0
    certificado_med_prepagada: bool = False

# 🆕 MODELO PARA AFC (AHORRO PARA FOMENTO A LA CONSTRUCCIÓN)
class AFCInfo(BaseModel):
    """Información de AFC (Ahorro para Fomento a la Construcción)"""
    valor_a_depositar: float = 0.0
    planilla_de_cuenta_AFC: bool = False

# 🆕 MODELO PARA PLANILLA DE SEGURIDAD SOCIAL
class PlanillaSeguridadSocial(BaseModel):
    """Información de planilla de seguridad social"""
    IBC_seguridad_social: float = 0.0
    planilla_seguridad_social: bool = False
    fecha_de_planilla_seguridad_social: str = "0000-00-00"

    
class DeduccionesArticulo383(BaseModel):
    
    intereses_vivienda: InteresesVivienda = InteresesVivienda()
    dependientes_economicos: DependientesEconomicos = DependientesEconomicos()
    medicina_prepagada: MedicinaPrepagada = MedicinaPrepagada()
    AFC: AFCInfo = AFCInfo()
    planilla_seguridad_social: PlanillaSeguridadSocial = PlanillaSeguridadSocial()
    
class CalculoArticulo383(BaseModel):
    ingreso_bruto: float = 0.0
    aportes_seguridad_social: float = 0.0
    total_deducciones: float = 0.0
    deducciones_limitadas: float = 0.0
    base_gravable_final: float = 0.0
    base_gravable_uvt: float = 0.0
    tarifa_aplicada: float = 0.0
    valor_retencion_art383: float = 0.0

class InformacionArticulo383(BaseModel):
    
    condiciones_cumplidas: CondicionesArticulo383 = CondicionesArticulo383()
    deducciones_identificadas: DeduccionesArticulo383 = DeduccionesArticulo383()
    
class AnalisisFactura(BaseModel):
    aplica_retencion: bool  #  CAMPO SINCRONIZADO AGREGADO
    conceptos_identificados: List[ConceptoIdentificado]
    naturaleza_tercero: Optional[NaturalezaTercero]
    articulo_383: Optional[InformacionArticulo383] = None  # NUEVA SECCIÓN
    es_facturacion_exterior: bool
    valor_total: Optional[float]
    iva: Optional[float]
    observaciones: List[str]



# ===============================
#  FUNCIÓN DE LIQUIDACIÓN SEGURA DE RETEFUENTE
# ===============================

def liquidar_retefuente_seguro(analisis_retefuente: Dict[str, Any], nit_administrativo: str) -> Dict[str, Any]:
    """
    Liquida retefuente con manejo seguro de estructura de datos.
    
    SOLUCIONA EL ERROR: 'dict' object has no attribute 'es_facturacion_exterior'
    
    FUNCIONALIDAD:
     Maneja estructura JSON de análisis de Gemini
    Extrae correctamente la sección "analisis" 
    Convierte dict a objeto AnalisisFactura
    Verifica campos requeridos antes de liquidar
    Manejo robusto de errores con logging detallado
    Fallback seguro en caso de errores
    
    Args:
        analisis_retefuente: Resultado del análisis de Gemini (estructura JSON)
        nit_administrativo: NIT administrativo
        
    Returns:
        Dict con resultado de liquidación o información de error
    """
    try:
        logger.info(f" Iniciando liquidación segura de retefuente para NIT: {nit_administrativo}")
        
        #  VERIFICAR ESTRUCTURA Y EXTRAER ANÁLISIS
        if isinstance(analisis_retefuente, dict):
            if "analisis" in analisis_retefuente:
                # Estructura: {"analisis": {...}, "timestamp": ..., etc}
                datos_analisis = analisis_retefuente["analisis"]
                logger.info("Extrayendo análisis desde estructura JSON con clave 'analisis'")
            else:
                # Estructura directa: {"es_facturacion_exterior": ..., etc}
                datos_analisis = analisis_retefuente
                logger.info("Usando estructura directa de análisis")
        else:
            # Ya es un objeto, usar directamente
            datos_analisis = analisis_retefuente
            logger.info("Usando objeto AnalisisFactura directamente")
        
        #  VERIFICAR CAMPOS REQUERIDOS
        campos_requeridos = ["es_facturacion_exterior", "conceptos_identificados", "naturaleza_tercero"]
        campos_faltantes = []
        
        for campo in campos_requeridos:
            if campo not in datos_analisis:
                campos_faltantes.append(campo)
        
        if campos_faltantes:
            error_msg = f"Campos requeridos faltantes: {', '.join(campos_faltantes)}"
            logger.error(f" {error_msg}")
            logger.error(f" Claves disponibles: {list(datos_analisis.keys()) if isinstance(datos_analisis, dict) else 'No es dict'}")
            
            return {
                "aplica": False,
                "error": error_msg,
                "valor_retencion": 0.0,
                "observaciones": [
                    "Error en estructura de datos del análisis",
                    f"Faltan campos: {', '.join(campos_faltantes)}",
                    "Revise el análisis de Gemini"
                ]
            }
        
        #  CREAR OBJETO ANALYSISFACTURA MANUALMENTE
        from Clasificador.clasificador import AnalisisFactura, ConceptoIdentificado, NaturalezaTercero
        
        # Convertir conceptos identificados
        conceptos = []
        conceptos_data = datos_analisis.get("conceptos_identificados", [])
        
        if not isinstance(conceptos_data, list):
            logger.warning(f" conceptos_identificados no es lista: {type(conceptos_data)}")
            conceptos_data = []
        
        for concepto_data in conceptos_data:
            if isinstance(concepto_data, dict):
                concepto_obj = ConceptoIdentificado(
                    concepto=concepto_data.get("concepto", ""),
                    tarifa_retencion=concepto_data.get("tarifa_retencion", 0.0),
                    base_gravable=concepto_data.get("base_gravable", None)
                )
                conceptos.append(concepto_obj)
                logger.info(f" Concepto convertido: {concepto_obj.concepto} - {concepto_obj.tarifa_retencion}%")
        
        # Convertir naturaleza del tercero
        naturaleza_data = datos_analisis.get("naturaleza_tercero", {})
        if not isinstance(naturaleza_data, dict):
            logger.warning(f"⚠️ naturaleza_tercero no es dict: {type(naturaleza_data)}")
            naturaleza_data = {}
        
        naturaleza_obj = NaturalezaTercero(
            es_persona_natural=naturaleza_data.get("es_persona_natural", None),
            regimen_tributario=naturaleza_data.get("regimen_tributario", None),
            es_autorretenedor=naturaleza_data.get("es_autorretenedor", None),
            es_responsable_iva=naturaleza_data.get("es_responsable_iva", None)
        )
        
        # Crear objeto completo
        analisis_obj = AnalisisFactura(
            aplica_retencion=datos_analisis.get("aplica_retencion", True),  # CAMPO OBLIGATORIO 
            conceptos_identificados=conceptos,
            naturaleza_tercero=naturaleza_obj,
            articulo_383=datos_analisis.get("articulo_383", None),  #  CAMPO SINCRONIZADO 
            es_facturacion_exterior=datos_analisis.get("es_facturacion_exterior", False),
            valor_total=datos_analisis.get("valor_total", None),
            iva=datos_analisis.get("iva", None),
            observaciones=datos_analisis.get("observaciones", [])
        )
        
        logger.info(f" Objeto AnalisisFactura creado: {len(conceptos)} conceptos, facturación_exterior={analisis_obj.es_facturacion_exterior}")
        
        # LIQUIDAR CON OBJETO VÁLIDO
        liquidador_retencion = LiquidadorRetencion()
        resultado = liquidador_retencion.liquidar_factura(analisis_obj, nit_administrativo)
        
        #  CONVERTIR RESULTADO CON NUEVA ESTRUCTURA
        resultado_dict = {
            "aplica": resultado.puede_liquidar,
            "valor_retencion": resultado.valor_retencion,
            "base_gravable": resultado.valor_base_retencion,
            "fecha_calculo": resultado.fecha_calculo,
            "observaciones": resultado.mensajes_error,
            "calculo_exitoso": resultado.puede_liquidar,
            #  NUEVOS CAMPOS CON ESTRUCTURA MEJORADA:
            "conceptos_aplicados": [concepto.dict() for concepto in resultado.conceptos_aplicados] if resultado.conceptos_aplicados else [],
            "resumen_conceptos": resultado.resumen_conceptos,
            
        }
        
        if resultado.puede_liquidar:
            logger.info(f" Retefuente liquidada exitosamente: ${resultado.valor_retencion:,.2f}")
        else:
            logger.warning(f" Retefuente no se pudo liquidar: {resultado.mensajes_error}")
        
        return resultado_dict
        
    except ImportError as e:
        error_msg = f"Error importando clases necesarias: {str(e)}"
        logger.error(f" {error_msg}")
        return {
            "aplica": False,
            "error": error_msg,
            "valor_retencion": 0.0,
            "observaciones": ["Error importando módulos de análisis", "Revise la configuración del sistema"]
        }
        
    except Exception as e:
        error_msg = f"Error liquidando retefuente: {str(e)}"
        logger.error(f" {error_msg}")
        logger.error(f" Tipo de estructura recibida: {type(analisis_retefuente)}")
        
        # Log adicional para debugging
        if isinstance(analisis_retefuente, dict):
            logger.error(f" Claves disponibles en análisis: {list(analisis_retefuente.keys())}")
            if "analisis" in analisis_retefuente and isinstance(analisis_retefuente["analisis"], dict):
                logger.error(f" Claves en 'analisis': {list(analisis_retefuente['analisis'].keys())}")
        
        # Log del traceback completo para debugging
        import traceback
        logger.error(f" Traceback completo: {traceback.format_exc()}")
        
        return {
            "aplica": False,
            "error": error_msg,
            "valor_retencion": 0.0,
            "observaciones": [
                "Error en liquidación de retefuente", 
                "Revise estructura de datos",
                f"Error técnico: {str(e)}"
            ]
        }
        
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejador del ciclo de vida de la aplicación.
    Reemplaza los eventos startup/shutdown.
    """
    # Código que se ejecuta ANTES de que la aplicación inicie
    configurar_logging()
    global logger
    logger = logging.getLogger(__name__)
    
    logger.info(" Worker de FastAPI iniciándose... Cargando configuración.")
    if not inicializar_configuracion():
        logger.critical(" FALLO EN LA CARGA DE CONFIGURACIÓN. La aplicación puede no funcionar correctamente.")

    # Inicializar gestor de base de datos
    inicializar_database_manager()
    
    yield # <--- La aplicación se ejecuta aquí

    # Código que se ejecuta DESPUÉS de que la aplicación se detiene (opcional)
    logger.info(" Worker de FastAPI deteniéndose.")

# ===============================
# API FASTAPI
# ===============================

app = FastAPI(
    title="Preliquidador de Retefuente - Colombia",
    description="Sistema automatizado para calcular retención en la fuente con arquitectura modular",
    version="2.0.0",
    lifespan=lifespan
)


@app.post("/api/procesar-facturas")
async def procesar_facturas_integrado(
    archivos: List[UploadFile] = File(...),
    codigo_del_negocio: int = Form(...),
    proveedor: str = Form(...),
    observaciones_tp: Optional[str] = Form(None),
    genera_presupuesto: Optional[str] = Form(None),
    rubro: Optional[str] = Form(None),
    centro_costos: Optional[int] = Form(None),
    numero_contrato: Optional[str] = Form(None),
    valor_contrato_municipio: Optional[float] = Form(None)
) -> JSONResponse:
    """
     ENDPOINT PRINCIPAL - SISTEMA INTEGRADO v3.0

    Procesa facturas y calcula múltiples impuestos en paralelo:
     RETENCIÓN EN LA FUENTE (funcionalidad original)
     ESTAMPILLA PRO UNIVERSIDAD NACIONAL (integrada)
     CONTRIBUCIÓN A OBRA PÚBLICA 5% (integrada)
     IVA Y RETEIVA (nueva funcionalidad)
     PROCESAMIENTO PARALELO cuando múltiples impuestos aplican
     GUARDADO AUTOMÁTICO de JSONs en Results/
     CONSULTA DE BASE DE DATOS para información del negocio
     CONTEXTO DEL PROVEEDOR para mejor identificación (v3.0)

    Args:
        archivos: Lista de archivos (facturas, RUTs, anexos, contratos)
        codigo_del_negocio: Código del negocio para consultar en base de datos (el NIT administrativo se obtiene de la DB)
        proveedor: Nombre del proveedor que emite la factura (OBLIGATORIO - mejora identificación de consorcios y retenciones)

    Returns:
        JSONResponse: Resultado consolidado de todos los impuestos aplicables
    """
    logger.info(f" ENDPOINT PRINCIPAL INTEGRADO v3.0 - Procesando {len(archivos)} archivos")
    logger.info(f" Código negocio: {codigo_del_negocio} | Proveedor: {proveedor}")

    try:
        # =================================
        # PASO 1: VALIDACIÓN Y CONFIGURACIÓN
        # =================================

        # Consultar información del negocio usando BusinessService (SOLID: SRP)
        resultado_negocio = business_service.obtener_datos_negocio(codigo_del_negocio)
        datos_negocio = resultado_negocio.get('data') if resultado_negocio.get('success') else None

        # Extraer NIT administrativo de la base de datos
        if not datos_negocio or 'nit' not in datos_negocio:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "No se pudo obtener el NIT administrativo de la base de datos",
                    "codigo_del_negocio": codigo_del_negocio,
                    "datos_negocio": datos_negocio,
                    "mensaje": "Código de negocio no encontrado o sin NIT asociado"
                }
            )

        nit_administrativo = str(datos_negocio['nit'])
        logger.info(f" NIT administrativo obtenido de DB: {nit_administrativo}")

        # Validar NIT administrativo obtenido de DB
        es_valido, nombre_entidad, impuestos_aplicables = validar_nit_administrativo(nit_administrativo)
        if not es_valido:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "NIT administrativo no válido",
                    "nit_recibido": nit_administrativo,
                    "mensaje": "El NIT no está configurado en el sistema",
                    "nits_disponibles": list(obtener_nits_disponibles().keys())
                }
            )
        
        logger.info(f" NIT válido: {nombre_entidad}")
        logger.info(f"Impuestos configurados: {impuestos_aplicables}")

        # Detectar automáticamente qué impuestos aplican usando código de negocio y NIT administrativo
        nombre_negocio = datos_negocio.get('negocio', 'Desconocido')
        deteccion_impuestos = detectar_impuestos_aplicables_por_codigo(
            codigo_del_negocio,
            nombre_negocio,
            nit_administrativo  # Validación doble: NIT + código de negocio
        )
        aplica_retencion = "RETENCION_FUENTE" in impuestos_aplicables
        aplica_estampilla = deteccion_impuestos["aplica_estampilla_universidad"]
        aplica_obra_publica = deteccion_impuestos["aplica_contribucion_obra_publica"]
        aplica_iva = nit_aplica_iva_reteiva(nit_administrativo)  # VALIDACIÓN IVA
        aplica_ica = nit_aplica_ICA(nit_administrativo)  # VALIDACIÓN ICA
        aplica_tasa_prodeporte = nit_aplica_tasa_prodeporte(nit_administrativo)  # VALIDACIÓN TASA PRODEPORTE

        logger.info(f" Código de negocio: {codigo_del_negocio} - {nombre_negocio}")
        logger.info(f" Aplica estampilla: {aplica_estampilla}, Aplica obra pública: {aplica_obra_publica}, Aplica ICA: {aplica_ica}")

        # Determinar estrategia de procesamiento
        impuestos_a_procesar = []
        if aplica_retencion:
            impuestos_a_procesar.append("RETENCION_FUENTE")
        if aplica_estampilla:
            impuestos_a_procesar.append("ESTAMPILLA_UNIVERSIDAD")
        if aplica_obra_publica:
            impuestos_a_procesar.append("CONTRIBUCION_OBRA_PUBLICA")
        if aplica_iva:
            impuestos_a_procesar.append("IVA_RETEIVA")
        if aplica_ica:
            impuestos_a_procesar.append("RETENCION_ICA")

        logger.info(f" Estrategia: PROCESAMIENTO PARALELO (todos los NITs aplican múltiples impuestos)")
        logger.info(f" Impuestos a procesar: {impuestos_a_procesar}")
        
        # =================================
        # PASO 2: EXTRACCIÓN HÍBRIDA DE TEXTO
        # =================================
        
        logger.info(f" Iniciando procesamiento híbrido multimodal: separando archivos por estrategia...")
        
        # SEPARAR ARCHIVOS POR ESTRATEGIA DE PROCESAMIENTO
        archivos_directos = []      # PDFs e imágenes → Gemini directo (multimodal)
        archivos_preprocesamiento = []  # Excel, Email, Word → Procesamiento local
        
        for archivo in archivos:
            try:
                nombre_archivo = archivo.filename
                extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''
                
                # Definir qué archivos van directo a Gemini (multimodal)
                if extension == 'pdf' or extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
                    archivos_directos.append(archivo)
                    logger.info(f" Archivo directo (multimodal): {nombre_archivo}")
                else:
                    # Excel, Email, Word y otros van a procesamiento local
                    archivos_preprocesamiento.append(archivo)
                    logger.info(f" Archivo para preprocesamiento: {nombre_archivo}")
            except Exception as e:
                logger.warning(f" Error clasificando archivo: {e}")
                # En caso de error, enviar a preprocesamiento (más seguro)
                logger.warning(f"Enviando a preprocesamiento por seguridad: {archivo.filename}")
                archivos_preprocesamiento.append(archivo)
        
        logger.info(f" Estrategia híbrida multimodal definida:")
        logger.info(f" Archivos directos (multimodal): {len(archivos_directos)}")
        logger.info(f" Archivos preprocesamiento local: {len(archivos_preprocesamiento)}")
        
        # PROCESAR SOLO ARCHIVOS QUE NECESITAN PREPROCESAMIENTO LOCAL
        if archivos_preprocesamiento:
            logger.info(f" Iniciando extracción local para {len(archivos_preprocesamiento)} archivos...")
            extractor = ProcesadorArchivos()
            textos_archivos_original = await extractor.procesar_multiples_archivos(archivos_preprocesamiento)
        else:
            logger.info(f" No hay archivos para procesamiento local - Solo archivos directos multimodales")
            textos_archivos_original = {}
        
        # Preprocesamiento específico para Excel (solo archivos locales)
        textos_preprocesados = {}
        for nombre_archivo, contenido_original in textos_archivos_original.items():
            # Si es Excel, aplicar preprocesamiento
            if nombre_archivo.lower().endswith(('.xlsx', '.xls')):
                try:
                    # Obtener contenido binario original del archivo
                    archivo_obj = next((arch for arch in archivos_preprocesamiento if arch.filename == nombre_archivo), None)
                    if archivo_obj:
                        await archivo_obj.seek(0)  # Resetear puntero
                        contenido_binario = await archivo_obj.read()
                        texto_preprocesado = preprocesar_excel_limpio(contenido_binario, nombre_archivo)
                        textos_preprocesados[nombre_archivo] = texto_preprocesado
                        logger.info(f" Excel preprocesado: {nombre_archivo}")
                    else:
                        textos_preprocesados[nombre_archivo] = contenido_original
                except Exception as e:
                    logger.warning(f" Error preprocesando {nombre_archivo}: {e}")
                    textos_preprocesados[nombre_archivo] = contenido_original
            else:
                textos_preprocesados[nombre_archivo] = contenido_original
        
        logger.info(f" Extracción local completada: {len(textos_preprocesados)} textos extraídos")
        
        # =================================
        # PASO 3: CLASIFICACIÓN HÍBRIDA CON MULTIMODALIDAD
        # =================================
        
        # Clasificar documentos usando enfoque híbrido multimodal
        clasificador = ProcesadorGemini()
        logger.info(" Iniciando clasificación híbrida multimodal:")
        logger.info(f" Archivos directos (PDFs/imágenes): {len(archivos_directos)}")
        logger.info(f"Textos preprocesados (Excel/Email/Word): {len(textos_preprocesados)}")
        
        clasificacion, es_consorcio, es_facturacion_extranjera = await clasificador.clasificar_documentos(
            archivos_directos=archivos_directos,
            textos_preprocesados=textos_preprocesados,
            proveedor=proveedor
        )
        
        logger.info(f" Documentos clasificados: {len(clasificacion)}")
        logger.info(f" Es consorcio: {es_consorcio}")
        logger.info(f" Facturación extranjera: {es_facturacion_extranjera}")
        
        # Estructurar documentos clasificados (híbrido: directos + preprocesados)
        documentos_clasificados = {}
        for nombre_archivo, categoria in clasificacion.items():
            # Para archivos directos, el texto no está disponible (se procesó directamente por Gemini)
            if nombre_archivo in textos_preprocesados:
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": textos_preprocesados[nombre_archivo]
                }
            else:
                # Archivo directo (PDF/imagen) - procesado nativamente por Gemini
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": "[ARCHIVO_DIRECTO_MULTIMODAL]",
                    "procesamiento": "directo_gemini"
                }
        
        # Guardar clasificación con información híbrida
        clasificacion_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "clasificacion": clasificacion,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "impuestos_aplicables": impuestos_a_procesar,
            "procesamiento_hibrido": {
                "multimodalidad_activa": True,
                "archivos_directos": len(archivos_directos),
                "archivos_preprocesados": len(textos_preprocesados),
                "total_archivos": len(archivos_directos) + len(textos_preprocesados),
                "nombres_archivos_directos": [archivo.filename for archivo in archivos_directos],
                "nombres_archivos_preprocesados": list(textos_preprocesados.keys()),
                "version_multimodal": "2.8.0"
            }
        }
        guardar_archivo_json(clasificacion_data, "clasificacion_documentos")
        logger.info(f" Clasificación completada: {len(clasificacion)} documentos")
        logger.info(f" Consorcio detectado: {es_consorcio}")
        logger.info(f" Facturación extranjera: {es_facturacion_extranjera}")
        # =================================
        # PASO 4: PROCESAMIENTO PARALELO (TODOS LOS IMPUESTOS)
        # =================================

        logger.info(f" Iniciando procesamiento paralelo: {' + '.join(impuestos_a_procesar)}")
        logger.info(f"Documentos a analizar: {documentos_clasificados}  ")
        # Crear tareas paralelas para análisis con Gemini
        tareas_analisis = []
        logger.info(" Preparando cache para solucionar concurrencia en workers paralelos")
        cache_archivos = await clasificador.preparar_archivos_para_workers_paralelos(archivos_directos)

        # Tarea 1: Análisis de Retefuente (si aplica)
        if aplica_retencion:
            if es_consorcio:
                tarea_retefuente = clasificador.analizar_consorcio(
                    documentos_clasificados,
                    es_facturacion_extranjera,
                    None,
                    cache_archivos,
                    proveedor=proveedor
                )
            else:
                #  MULTIMODALIDAD: Pasar archivos directos para análisis híbrido
                tarea_retefuente = clasificador.analizar_factura(
                    documentos_clasificados,
                    es_facturacion_extranjera,
                    None,
                    cache_archivos,
                    proveedor=proveedor
                )
            tareas_analisis.append(("retefuente", tarea_retefuente))
        
        # Tarea 2: Análisis de Impuestos Especiales (si aplican)
        if aplica_estampilla or aplica_obra_publica:
            tarea_impuestos_especiales = clasificador.analizar_estampilla(documentos_clasificados, None, cache_archivos)
            tareas_analisis.append(("impuestos_especiales", tarea_impuestos_especiales))
        
        # Tarea 3: Análisis de IVA (si aplica) - NUEVA TAREA
        if aplica_iva:
            tarea_iva = clasificador.analizar_iva(documentos_clasificados, None, cache_archivos)
            tareas_analisis.append(("iva_reteiva", tarea_iva))
        
        # Tarea 4: Análisis de Estampillas Generales -  NUEVA FUNCIONALIDAD
        # Las estampillas generales se ejecutan SIEMPRE en paralelo para todos los NITs
        tarea_estampillas_generales = clasificador.analizar_estampillas_generales(documentos_clasificados, None, cache_archivos)
        tareas_analisis.append(("estampillas_generales", tarea_estampillas_generales))

        # Tarea 5: Análisis de Tasa Prodeporte - NUEVA FUNCIONALIDAD
        if aplica_tasa_prodeporte:
            tarea_tasa_prodeporte = clasificador.analizar_tasa_prodeporte(documentos_clasificados, None, cache_archivos, observaciones_tp)
            tareas_analisis.append(("tasa_prodeporte", tarea_tasa_prodeporte))
            logger.info(f"✓ Tasa Prodeporte: Análisis activado para NIT {nit_administrativo}")

        # Tarea 6: Análisis de ICA - NUEVA FUNCIONALIDAD (MULTIMODAL)
        if aplica_ica:
            # ICA requiere procesamiento especial con ClasificadorICA
            async def analizar_ica_async():
                try:
                    clasificador_ica = ClasificadorICA(
                        database_manager=db_manager,
                        procesador_gemini=clasificador  # Procesador completo para multimodal
                    )
                    return await clasificador_ica.analizar_ica(
                        nit_administrativo=nit_administrativo,
                        textos_documentos=documentos_clasificados,
                        cache_archivos=cache_archivos  # Cache para procesamiento híbrido
                    )
                except Exception as e:
                    logger.error(f"Error en análisis ICA: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "aplica": False,
                        "estado": "Preliquidacion sin finalizar",
                        "observaciones": [f"Error en análisis ICA: {str(e)}"]
                    }

            tarea_ica = analizar_ica_async()
            tareas_analisis.append(("ica", tarea_ica))
            logger.info(f"✓ ICA: Análisis activado para NIT {nit_administrativo}")

        # Ejecutar todas las tareas en paralelo
        logger.info(f" Ejecutando {len(tareas_analisis)} análisis paralelos con Gemini...")
        
        # Esperar todos los resultados
        resultados_analisis = {}
        try:

            # 🔧 OPTIMIZACIÓN: Procesamiento con semáforo de 4 workers
            semaforo = asyncio.Semaphore(4)  # Máximo 4 llamados simultáneos a Gemini

            async def ejecutar_tarea_con_worker(nombre_impuesto: str, tarea_async, worker_id: int):
                """
                Ejecuta una tarea de análisis con control de concurrencia.
                
                Args:
                    nombre_impuesto: Nombre del impuesto (retefuente, impuestos_especiales, etc.)
                    tarea_async: Tarea asíncrona a ejecutar
                    worker_id: ID del worker (1 o 2)
                    
                Returns:
                    tuple: (nombre_impuesto, resultado_o_excepcion, tiempo_ejecucion)
                """
                async with semaforo:
                    inicio_worker = datetime.now()
                    logger.info(f" Worker {worker_id}: Iniciando análisis de {nombre_impuesto}")
                    
                    try:
                        resultado = await tarea_async
                        tiempo_ejecucion = (datetime.now() - inicio_worker).total_seconds()
                        logger.info(f" Worker {worker_id}: {nombre_impuesto} completado en {tiempo_ejecucion:.2f}s")
                        return (nombre_impuesto, resultado, tiempo_ejecucion)
                        
                    except Exception as e:
                        tiempo_ejecucion = (datetime.now() - inicio_worker).total_seconds()
                        logger.error(f" Worker {worker_id}: Error en {nombre_impuesto} tras {tiempo_ejecucion:.2f}s: {str(e)}")
                        return (nombre_impuesto, e, tiempo_ejecucion)
            
            # Crear tareas con workers
            inicio_total = datetime.now()
            tareas_con_workers = [
                ejecutar_tarea_con_worker(nombre_impuesto, tarea, i + 1) 
                for i, (nombre_impuesto, tarea) in enumerate(tareas_analisis)
            ]
            
            logger.info(f" Ejecutando {len(tareas_con_workers)} tareas con máximo 2 workers simultáneos...")
            
            # Esperar todos los resultados con workers limitados
            resultados_con_workers = await asyncio.gather(*tareas_con_workers, return_exceptions=True)
            
            # Mapear resultados a sus nombres
            for i, (nombre_impuesto, tarea) in enumerate(tareas_analisis):
                resultado_worker = resultados_con_workers[i]
                if isinstance(resultado_worker, Exception):
                    logger.error(f" Error crítico en worker: {resultado_worker}")
                    resultados_analisis[nombre_impuesto] = {"error": str(resultado_worker)}
                    continue
                
                # Extraer información del worker: (nombre_impuesto, resultado, tiempo)
                _, resultado, tiempo_ejecucion = resultado_worker
                
                if isinstance(resultado, Exception):
                    logger.error(f" Error en análisis de {nombre_impuesto}: {resultado}")
                    resultados_analisis[nombre_impuesto] = {"error": str(resultado)}
                else:
                    resultados_analisis[nombre_impuesto] = resultado.dict() if hasattr(resultado, 'dict') else resultado
                    logger.info(f"Análisis de {nombre_impuesto} completado con éxito")
        except Exception as e:
            logger.error(f" Error ejecutando análisis paralelo: {e}")
            raise HTTPException(status_code=500, detail=
                f"Error ejecutando análisis paralelo : {str(e)}"
            )
           
        # Guardar análisis paralelo
        analisis_paralelo_data = {
            "timestamp": datetime.now().isoformat(),
            "impuestos_analizados": list(resultados_analisis.keys()),
            "resultados_analisis": resultados_analisis
        }
        guardar_archivo_json(analisis_paralelo_data, "analisis_paralelo")
        
        # =================================
        # PASO 5: LIQUIDACIÓN DE IMPUESTOS
        # =================================

        logger.info(f" Iniciando liquidación de impuestos en paralelo...")
        
        resultado_final = {
            "impuestos_procesados": impuestos_a_procesar,
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "timestamp": datetime.now().isoformat(),
            "version": "2.9.3",
            "impuestos": {}  # NUEVA ESTRUCTURA PARA TODOS LOS IMPUESTOS
        }
        
        # Liquidar Retefuente
        if "retefuente" in resultados_analisis and aplica_retencion:
            try:
                if es_consorcio:
                    # Usar nuevo liquidador de consorcios con validaciones manuales
                    liquidador_consorcio = LiquidadorConsorcios()
                    analisis_consorcio_gemini = resultados_analisis["retefuente"]  # Solo extracción de Gemini

                    # Liquidar con validaciones manuales de Python (con caché de archivos)
                    resultado_liquidacion_consorcio = await liquidador_consorcio.liquidar_consorcio(
                        analisis_consorcio_gemini, CONCEPTOS_RETEFUENTE, archivos_directos, cache_archivos
                    )

                    # Convertir resultado a formato de respuesta y extraer la parte retefuente
                    resultado_dict_completo = convertir_consorcio_a_dict(resultado_liquidacion_consorcio)
                    resultado_retefuente = resultado_dict_completo["retefuente"]  # Extraer solo la parte de retefuente
                else:
                    analisis_factura = resultados_analisis["retefuente"]
                    
                    #  USAR FUNCIÓN SEGURA PARA PROCESAMIENTO PARALELO
                    logger.info(" Ejecutando liquidación segura en procesamiento paralelo...")
                    
                    # Crear estructura compatible
                    analisis_retefuente_data = {
                        "timestamp": datetime.now().isoformat(),
                        "tipo_analisis": "retefuente_paralelo",
                        "nit_administrativo": nit_administrativo,
                        "analisis": analisis_factura.dict() if hasattr(analisis_factura, 'dict') else analisis_factura
                    }
                    
                    # Guardar análisis para debugging
                    guardar_archivo_json(analisis_retefuente_data, "analisis_retefuente_paralelo")
                    
                    # Liquidar con función segura
                    resultado_retefuente_dict = liquidar_retefuente_seguro(
                        analisis_retefuente_data, nit_administrativo
                    )
                    
                    #  FIX: Manejar casos válidos sin retención correctamente
                    if resultado_retefuente_dict.get("calculo_exitoso", False) or not resultado_retefuente_dict.get("error"):
                        # Caso exitoso O caso válido sin retención
                       
                        valor_retencion = resultado_retefuente_dict.get('valor_retencion', 0.0)
                        

                        if valor_retencion > 0:
                            logger.info(f" Retefuente paralela liquidada: ${valor_retencion:,.2f}")
                        else:
                            logger.info(f"Retefuente procesada (no aplica retención)")
                        
                        # Crear objeto mock que simula ResultadoLiquidacion
                        resultado_retefuente = type('ResultadoLiquidacion', (object,), {
                            'puede_liquidar': resultado_retefuente_dict.get("aplica", False),
                            'valor_retencion': resultado_retefuente_dict.get('valor_retencion', 0.0),
                            'conceptos_aplicados': resultado_retefuente_dict.get("conceptos_aplicados", []),
                            'valor_base_retencion': resultado_retefuente_dict.get("base_gravable", 0.0),
                            'fecha_calculo': resultado_retefuente_dict.get("fecha_calculo", datetime.now().isoformat()),
                            'mensajes_error': resultado_retefuente_dict.get("observaciones", []),
                            'resumen_conceptos': resultado_retefuente_dict.get("resumen_conceptos", "N/A")
                      
                        })()
                    else:
                        # Solo registrar como error si realmente hay un error técnico
                        error_msg = resultado_retefuente_dict.get('error', 'Error técnico en liquidación')
                        logger.error(f" Error técnico en liquidación paralela: {error_msg}")
                        
                        # Crear objeto con valores por defecto para errores técnicos
                        resultado_retefuente = type('ResultadoLiquidacion', (object,), {
                            'puede_liquidar': False,
                            'valor_retencion': 0.0,
                            'conceptos_aplicados': ["Error técnico en liquidación"],
                            'valor_base_retencion': 0.0,
                            'fecha_calculo': datetime.now().isoformat(),
                            'mensajes_error': [error_msg],
                            'resumen_conceptos': 'N/A'
                        })()
                
                #  ESTRUCTURA FINAL CONSOLIDADA
                if hasattr(resultado_retefuente, 'valor_retencion'):
                    
                    resultado_final["impuestos"]["retefuente"] = {
                    "aplica": resultado_retefuente_dict.get("aplica", False),
                    "valor_retencion": resultado_retefuente_dict.get("valor_retencion", 0.0),
                    "valor_base": resultado_retefuente_dict.get("base_gravable", 0.0),
                    "mensajes_error": resultado_retefuente_dict.get("observaciones", []),
                    "conceptos_aplicados": resultado_retefuente_dict.get("conceptos_aplicados", []),
                    }
                    logger.info(f" Retefuente liquidada: ${resultado_retefuente_dict.get('valor_retencion', 0.0):,.2f}")

                else:
                    # Es un diccionario (resultado de consorcio)
                    resultado_final["impuestos"]["retefuente"] = resultado_retefuente
                    logger.info(f" Retefuente liquidada: ${resultado_retefuente.get('valor_retencion', 0):,.2f}")
            except Exception as e:
                logger.error(f" Error liquidando retefuente: {e}")
                resultado_final["impuestos"]["retefuente"] = {"error": str(e), "aplica": False}

        # Liquidar Impuestos Especiales (Estampilla Pro Universidad Nacional + Obra Pública)
        if "impuestos_especiales" in resultados_analisis and (aplica_estampilla or aplica_obra_publica):
            try:
                from Liquidador.liquidador_estampilla import LiquidadorEstampilla
                liquidador_estampilla = LiquidadorEstampilla()

                analisis_especiales = resultados_analisis["impuestos_especiales"]
                resultado_estampilla = liquidador_estampilla.liquidar_integrado(analisis_especiales, codigo_del_negocio, nombre_negocio)
                
                #  ASIGNAR A NUEVA ESTRUCTURA: Separar resultados por impuesto
                if aplica_estampilla and "estampilla_universidad" in resultado_estampilla:
                    resultado_final["impuestos"]["estampilla_universidad"] = resultado_estampilla["estampilla_universidad"]
                    logger.info(f" Estampilla liquidada: ${resultado_estampilla['estampilla_universidad'].get('valor_estampilla', 0):,.2f}")
                
                if aplica_obra_publica and "contribucion_obra_publica" in resultado_estampilla:
                    resultado_final["impuestos"]["contribucion_obra_publica"] = resultado_estampilla["contribucion_obra_publica"]
                    logger.info(f" Obra pública liquidada: ${resultado_estampilla['contribucion_obra_publica'].get('valor_contribucion', 0):,.2f}")
                    
            except Exception as e:
                logger.error(f" Error liquidando impuestos especiales: {e}")
                if aplica_estampilla:
                    resultado_final["impuestos"]["estampilla_universidad"] = {"error": str(e), "aplica": False}
                if aplica_obra_publica:
                    resultado_final["impuestos"]["contribucion_obra_publica"] = {"error": str(e), "aplica": False}
        
        # Liquidar IVA y ReteIVA - ARQUITECTURA SOLID v2.0
        if "iva_reteiva" in resultados_analisis and aplica_iva:
            try:
                from Liquidador.liquidador_iva import LiquidadorIVA
                liquidador_iva = LiquidadorIVA()

                # Análisis de Gemini (nueva estructura PROMPT_ANALISIS_IVA)
                analisis_iva_gemini = resultados_analisis["iva_reteiva"]

                # Clasificación inicial (para obtener es_facturacion_extranjera)
                clasificacion_inicial = {
                    "es_facturacion_extranjera": es_facturacion_extranjera
                }

                # Liquidar con nueva arquitectura SOLID (requiere 3 parámetros)
                resultado_iva_dict = liquidador_iva.liquidar_iva_completo(
                    analisis_gemini=analisis_iva_gemini,
                    clasificacion_inicial=clasificacion_inicial,
                    nit_administrativo=nit_administrativo
                )

                # El método ahora retorna directamente un diccionario con estructura {"iva_reteiva": {...}}
                resultado_final["impuestos"]["iva_reteiva"] = resultado_iva_dict.get("iva_reteiva", {})

                # Logs actualizados para usar diccionario
                valor_iva = resultado_iva_dict.get("iva_reteiva", {}).get("valor_iva_identificado", 0.0)
                valor_reteiva = resultado_iva_dict.get("iva_reteiva", {}).get("valor_reteiva", 0.0)
                logger.info(f" IVA identificado: ${valor_iva:,.2f}")
                logger.info(f" ReteIVA liquidada: ${valor_reteiva:,.2f}")

            except Exception as e:
                logger.error(f" Error liquidando IVA/ReteIVA: {e}")
                resultado_final["impuestos"]["iva_reteiva"] = {"error": str(e), "aplica": False}
        
        # Liquidar Estampillas Generales - NUEVA LIQUIDACIÓN
        if "estampillas_generales" in resultados_analisis:
            try:
                from Liquidador.liquidador_estampillas_generales import (
                    validar_formato_estampillas_generales, 
                    presentar_resultado_estampillas_generales
                )
                
                analisis_estampillas = resultados_analisis["estampillas_generales"]
                
                # Validar formato de respuesta de Gemini
                validacion = validar_formato_estampillas_generales(analisis_estampillas)
                
                if validacion["formato_valido"]:
                    logger.info(" Formato de estampillas generales válido")
                    respuesta_validada = validacion["respuesta_validada"]
                else:
                    logger.warning(f" Formato de estampillas con errores: {len(validacion['errores'])} errores")
                    logger.warning(f"Errores: {validacion['errores']}")
                    respuesta_validada = validacion["respuesta_validada"]  # Usar respuesta corregida
                
                # Presentar resultado final
                resultado_estampillas = presentar_resultado_estampillas_generales(respuesta_validada)

                #  ASIGNAR A NUEVA ESTRUCTURA: resultado_final["impuestos"]["estampillas_generales"]
                resultado_final["impuestos"]["estampillas_generales"] = resultado_estampillas.get("estampillas_generales", {})

            except Exception as e:
                logger.error(f" Error liquidando estampillas generales: {e}")
                resultado_final["impuestos"]["estampillas_generales"] = {
                    "procesamiento_exitoso": False,
                    "error": str(e),
                    "observaciones_generales": ["Error procesando estampillas generales"]
                }

        # Liquidar ICA - NUEVA FUNCIONALIDAD
        if "ica" in resultados_analisis and aplica_ica:
            try:
                logger.info(" Liquidando ICA...")

                # Obtener análisis de ICA (ya validado por ClasificadorICA)
                analisis_ica = resultados_analisis["ica"]

                # Crear liquidador ICA
                liquidador_ica = LiquidadorICA(database_manager=db_manager)

                # Liquidar ICA
                resultado_ica = liquidador_ica.liquidar_ica(analisis_ica)

                # Agregar resultado al resultado final
                resultado_final["impuestos"]["ica"] = resultado_ica

                # Logs informativos
                estado_ica = resultado_ica.get("estado", "Desconocido")
                valor_ica = resultado_ica.get("valor_total_ica", 0.0)
                logger.info(f" ICA - Estado: {estado_ica}")
                logger.info(f" ICA - Valor total: ${valor_ica:,.2f}")

            except Exception as e:
                logger.error(f" Error liquidando ICA: {e}")
                import traceback
                logger.error(traceback.format_exc())
                resultado_final["impuestos"]["ica"] = {
                    "aplica": False,
                    "estado": "Preliquidacion sin finalizar",
                    "error": str(e),
                    "observaciones": [f"Error en liquidación ICA: {str(e)}"]
                }

        # Liquidar Tasa Prodeporte - NUEVA FUNCIONALIDAD
        if "tasa_prodeporte" in resultados_analisis:
            try:
                from Liquidador.liquidador_TP import LiquidadorTasaProdeporte
                from Liquidador.liquidador_TP import ParametrosTasaProdeporte

                liquidador_tp = LiquidadorTasaProdeporte()

                # Análisis de Gemini (extracción de datos)
                analisis_tp_gemini = resultados_analisis["tasa_prodeporte"]

                # Crear parámetros con los datos del endpoint
                parametros_tp = ParametrosTasaProdeporte(
                    observaciones=observaciones_tp,
                    genera_presupuesto=genera_presupuesto,
                    rubro=rubro,
                    centro_costos=centro_costos,
                    numero_contrato=numero_contrato,
                    valor_contrato_municipio=valor_contrato_municipio
                )

                # Liquidar con arquitectura SOLID (separación IA-Validación)
                resultado_tp = liquidador_tp.liquidar(parametros_tp, analisis_tp_gemini)

                # Convertir Pydantic a dict
                resultado_final["impuestos"]["tasa_prodeporte"] = resultado_tp.dict()

                # Log según resultado
                if resultado_tp.aplica:
                    logger.info(f" Tasa Prodeporte liquidada: ${resultado_tp.valor_imp:,.2f} (Tarifa: {resultado_tp.tarifa*100}%)")
                else:
                    logger.info(f" Tasa Prodeporte: {resultado_tp.estado}")

            except Exception as e:
                logger.error(f" Error liquidando Tasa Prodeporte: {e}")
                resultado_final["impuestos"]["tasa_prodeporte"] = {
                    "error": str(e),
                    "aplica": False,
                    "estado": "Preliquidacion sin finalizar"
                }

        # =================================
        # COMPLETAR IMPUESTOS QUE NO APLICAN
        # =================================

        # Agregar respuesta para impuestos que no aplican según código de negocio
        if not aplica_estampilla and "estampilla_universidad" not in resultado_final["impuestos"]:
            razon_estampilla = deteccion_impuestos.get("razon_no_aplica_estampilla") or f"El negocio {nombre_negocio} no aplica este impuesto"
            resultado_final["impuestos"]["estampilla_universidad"] = {
                "aplica": False,
                "estado": "No aplica el impuesto",
                "razon": razon_estampilla
            }
            logger.info(f" Estampilla Universidad: No aplica - {razon_estampilla}")

        if not aplica_obra_publica and "contribucion_obra_publica" not in resultado_final["impuestos"]:
            razon_obra_publica = deteccion_impuestos.get("razon_no_aplica_obra_publica") or f"El negocio {nombre_negocio} no aplica este impuesto"
            resultado_final["impuestos"]["contribucion_obra_publica"] = {
                "aplica": False,
                "estado": "No aplica el impuesto",
                "razon": razon_obra_publica
            }
            logger.info(f" Contribución Obra Pública: No aplica - {razon_obra_publica}")

        if not aplica_iva and "iva_reteiva" not in resultado_final["impuestos"]:
            resultado_final["impuestos"]["iva_reteiva"] = {
                "aplica": False,
                "estado": "No aplica el impuesto",
                "razon": f"El NIT {nit_administrativo} no está configurado para IVA/ReteIVA"
            }
            logger.info(f" IVA/ReteIVA: No aplica para NIT {nit_administrativo}")

        if not aplica_tasa_prodeporte and "tasa_prodeporte" not in resultado_final["impuestos"]:
            resultado_final["impuestos"]["tasa_prodeporte"] = {
                "estado": "No aplica el impuesto",
                "aplica": False,
                "valor_imp": 0.0,
                "tarifa": 0.0,
                "valor_convenio_sin_iva": 0.0,
                "porcentaje_convenio": 0.0,
                "valor_contrato_municipio": 0.0,
                "factura_sin_iva": 0.0,
                "factura_con_iva": 0.0,
                "municipio_dept": "",
                "numero_contrato": "",
                "observaciones": f"Tasa Prodeporte solo aplica para PATRIMONIO AUTONOMO FONTUR (NIT 900649119). NIT actual: {nit_administrativo}",
                "fecha_calculo": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logger.info(f" Tasa Prodeporte: No aplica para NIT {nit_administrativo} (solo FONTUR 900649119)")

        #  CALCULAR RESUMEN TOTAL CON NUEVAS RUTAS
        valor_total_impuestos = 0.0
        
        # Usar nuevas rutas: resultado_final["impuestos"][nombre_impuesto]
        if "retefuente" in resultado_final["impuestos"] and isinstance(resultado_final["impuestos"]["retefuente"], dict):
            valor_total_impuestos += resultado_final["impuestos"]["retefuente"].get("valor_retencion", 0)
        
        if "estampilla_universidad" in resultado_final["impuestos"] and isinstance(resultado_final["impuestos"]["estampilla_universidad"], dict):
            valor_total_impuestos += resultado_final["impuestos"]["estampilla_universidad"].get("valor_estampilla", 0)
        
        if "contribucion_obra_publica" in resultado_final["impuestos"] and isinstance(resultado_final["impuestos"]["contribucion_obra_publica"], dict):
            valor_total_impuestos += resultado_final["impuestos"]["contribucion_obra_publica"].get("valor_contribucion", 0)
        
        if "iva_reteiva" in resultado_final["impuestos"] and isinstance(resultado_final["impuestos"]["iva_reteiva"], dict):
            valor_total_impuestos += resultado_final["impuestos"]["iva_reteiva"].get("valor_reteiva", 0)

        if "tasa_prodeporte" in resultado_final["impuestos"] and isinstance(resultado_final["impuestos"]["tasa_prodeporte"], dict):
            valor_total_impuestos += resultado_final["impuestos"]["tasa_prodeporte"].get("valor_imp", 0)

        resultado_final["resumen_total"] = {
            "valor_total_impuestos": valor_total_impuestos,
            "impuestos_liquidados": [imp for imp in impuestos_a_procesar if imp.lower().replace("_", "") in [k.lower().replace("_", "") for k in resultado_final["impuestos"].keys()]],
            "procesamiento_exitoso": True
        }
        
        logger.info(f" Total impuestos calculados: ${valor_total_impuestos:,.2f}")

        # =================================
        # PASO 6: CONSOLIDACIÓN Y GUARDADO FINAL
        # =================================
        
        # Agregar metadatos finales
        resultado_final.update({
            "timestamp_procesamiento": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "documentos_procesados": len(archivos),
            "documentos_clasificados": list(clasificacion.keys()),
            "version_sistema": "2.4.0",
            "modulos_utilizados": ["Extraccion", "Clasificador", "Liquidador"]
        })
        
        # Guardar resultado final completo
        guardar_archivo_json(resultado_final, "resultado_final")
        
        # Log final de éxito
        logger.info(f" Procesamiento completado exitosamente")
        logger.info(f"Impuestos procesados: {resultado_final.get('impuestos_procesados', [])}")
        if 'resumen_total' in resultado_final:
            logger.info(f" Total impuestos: ${resultado_final['resumen_total']['valor_total_impuestos']:,.2f}")
        
        return JSONResponse(
            status_code=200,
            content=resultado_final
        )
        
    except HTTPException:
        # Re-lanzar HTTPExceptions directamente
        raise
    except Exception as e:
        # Manejo de errores generales
        error_msg = f"Error en procesamiento integrado: {str(e)}"
        logger.error(f" {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Guardar error para debugging
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "error_mensaje": error_msg,
            "error_tipo": type(e).__name__,
            "traceback": traceback.format_exc(),
            "archivos_recibidos": [archivo.filename for archivo in archivos],
            "version": "2.4.0"
        }
        guardar_archivo_json(error_data, "error_procesamiento")
        
        # Determinar tipo de error para respuesta apropiada
        if "Gemini" in error_msg or "API" in error_msg:
            error_type = "API_ERROR"
            user_message = "Error en el servicio de inteligencia artificial"
        elif "liquidar" in error_msg.lower():
            error_type = "CALCULATION_ERROR"
            user_message = "Error en los cálculos de impuestos"
        elif "extrac" in error_msg.lower():
            error_type = "EXTRACTION_ERROR"
            user_message = "Error extrayendo texto de los archivos"
        else:
            error_type = "GENERAL_ERROR"
            user_message = "Error general en el procesamiento"
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error de procesamiento ({error_type})",
                "mensaje": user_message,
                "detalle_tecnico": error_msg,
                "tipo": error_type,
                "version": "2.4.0",
                "timestamp": datetime.now().isoformat()
            }
        )

# ===============================
# ENDPOINTS ADICIONALES
# ===============================

# este endpoint se va a actualizar con la base de datos de SIFI
@app.get("/api/conceptos")
async def obtener_conceptos():
    """Obtener lista de conceptos de retefuente con sus datos exactos"""
    conceptos_formateados = []
    
    for concepto, datos in CONCEPTOS_RETEFUENTE.items():
        conceptos_formateados.append({
            "concepto": concepto,
            "base_pesos": datos["base_pesos"],
            "tarifa_porcentaje": datos["tarifa_retencion"] * 100,
            "tarifa_decimal": datos["tarifa_retencion"]
        })
    
    return {
        "conceptos": conceptos_formateados,
        "total_conceptos": len(CONCEPTOS_RETEFUENTE),
        "fuente": "RETEFUENTE_CONCEPTOS.xlsx",
        "version": "2.4.0"
    }

@app.get("/api/nits-disponibles")
async def obtener_nits_disponibles_endpoint():
    """Obtener lista de NITs administrativos disponibles"""
    try:
        nits_data = obtener_nits_disponibles()
        
        # Formatear para el frontend
        nits_formateados = []
        for nit, datos in nits_data.items():
            nits_formateados.append({
                "nit": nit,
                "nombre": datos["nombre"],
                "impuestos_aplicables": datos["impuestos_aplicables"],
                "total_impuestos": len(datos["impuestos_aplicables"]),
                "aplica_retencion_fuente": "RETENCION_FUENTE" in datos["impuestos_aplicables"],
                "aplica_estampilla_universidad": "ESTAMPILLA_UNIVERSIDAD" in datos["impuestos_aplicables"]
            })
        
        return {
            "success": True,
            "nits": nits_formateados,
            "total_nits": len(nits_formateados),
            "version": "2.4.0",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo NITs disponibles: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error obteniendo NITs",
                "mensaje": str(e),
                "version": "2.4.0"
            }
        )

@app.get("/api/extracciones")
async def obtener_estadisticas_extracciones():
    """Obtener estadísticas de textos extraídos guardados"""
    try:
        extractor = ProcesadorArchivos()
        estadisticas = extractor.obtener_estadisticas_guardado()
        
        return {
            "success": True,
            "version": "2.4.0",
            "modulo": "Extraccion",
            "estadisticas": estadisticas,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de extracciones: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error obteniendo estadísticas",
                "mensaje": str(e),
                "modulo": "Extraccion"
            }
        )

@app.post("/api/prueba-simple")
async def prueba_simple(nit_administrativo: Optional[str] = Form(None)):
    """Endpoint de prueba simple SIN archivos"""
    logger.info(f" PRUEBA SIMPLE: Recibido NIT: {nit_administrativo}")
    return {
        "success": True,
        "mensaje": "POST sin archivos funciona - Sistema integrado",
        "nit_recibido": nit_administrativo,
        "version": "2.4.0",
        "sistema": "integrado_retefuente_estampilla",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/database/health")
async def database_health_check():
    """
    Verificar el estado de la conexión a la base de datos usando BusinessService.

    PRINCIPIO SRP: Endpoint específico para health check de base de datos
    """
    if not business_service:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "BusinessService no está inicializado",
                "details": "Error en inicialización del sistema de base de datos"
            }
        )

    try:
        # Usar el servicio para validar disponibilidad (SRP)
        is_available = business_service.validar_disponibilidad_database()

        if is_available:
            return {
                "status": "healthy",
                "message": "Conexión a base de datos OK",
                "service": "BusinessDataService",
                "architecture": "SOLID + Strategy Pattern",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "Conexión a base de datos no disponible",
                    "service": "BusinessDataService",
                    "timestamp": datetime.now().isoformat()
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error verificando base de datos: {str(e)}",
                "service": "BusinessDataService",
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/database/test/{codigo_negocio}")
async def test_database_query(codigo_negocio: int):
    """
    Probar consulta de negocio por código usando BusinessService.

    PRINCIPIO SRP: Endpoint específico para testing de consultas de negocio
    """
    if not business_service:
        return JSONResponse(
            status_code=503,
            content={
                "error": "BusinessService no está disponible",
                "details": "Error en inicialización del sistema de base de datos",
                "service": "BusinessDataService"
            }
        )

    try:
        # Usar el servicio para la consulta (SRP + DIP)
        resultado = business_service.obtener_datos_negocio(codigo_negocio)

        return {
            "resultado": resultado,
            "service": "BusinessDataService",
            "architecture": "SOLID + Clean Architecture",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Error consultando negocio: {str(e)}",
                "codigo_consultado": codigo_negocio,
                "service": "BusinessDataService",
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/diagnostico")
async def diagnostico_completo():
    """Endpoint de diagnóstico completo para verificar todos los componentes del sistema"""
    diagnostico = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.4.0",
        "sistema": "integrado_retefuente_estampilla",
        "estado_general": "VERIFICANDO",
        "componentes": {}
    }
    
    try:
        # 1. VERIFICAR VARIABLES DE ENTORNO
        diagnostico["componentes"]["variables_entorno"] = {
            "gemini_api_key": {
                "configurado": bool(GEMINI_API_KEY),
                "status": "OK" if GEMINI_API_KEY else "ERROR",
                "mensaje": "Configurado" if GEMINI_API_KEY else "FALTA GEMINI_API_KEY en .env"
            },
            "google_credentials": {
                "configurado": bool(GOOGLE_CLOUD_CREDENTIALS),
                "archivo_existe": bool(GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS)),
                "status": "OK" if (GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS)) else "WARNING",
                "mensaje": "Configurado correctamente" if (GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS)) else "Vision no disponible (opcional)"
            }
        }
        
        # 2. VERIFICAR IMPORTACIONES DE MÓDULOS
        modulos_status = {}
        
        # Extraccion
        try:
            extractor = ProcesadorArchivos()
            modulos_status["extraccion"] = {
                "importacion": "OK",
                "instanciacion": "OK",
                "mensaje": "Módulo funcionando correctamente"
            }
        except Exception as e:
            modulos_status["extraccion"] = {
                "importacion": "ERROR",
                "instanciacion": "ERROR",
                "mensaje": f"Error: {str(e)}",
                "error_completo": str(e)
            }
            
        # Clasificador
        try:
            clasificador = ProcesadorGemini()
            modulos_status["clasificador"] = {
                "importacion": "OK",
                "instanciacion": "OK",
                "mensaje": "Módulo funcionando correctamente"
            }
        except Exception as e:
            modulos_status["clasificador"] = {
                "importacion": "ERROR",
                "instanciacion": "ERROR",
                "mensaje": f"Error: {str(e)}",
                "error_completo": str(e)
            }
            
        # Liquidador
        try:
            liquidador = LiquidadorRetencion()
            modulos_status["liquidador"] = {
                "importacion": "OK",
                "instanciacion": "OK",
                "mensaje": "Módulo funcionando correctamente"
            }
        except Exception as e:
            modulos_status["liquidador"] = {
                "importacion": "ERROR",
                "instanciacion": "ERROR",
                "mensaje": f"Error: {str(e)}",
                "error_completo": str(e)
            }
            
        diagnostico["componentes"]["modulos"] = modulos_status
        
        # 3. VERIFICAR FUNCIONES DE CONFIG
        config_status = {}
        
        try:
            # Probar obtener NITs
            nits = obtener_nits_disponibles()
            config_status["obtener_nits"] = {
                "status": "OK",
                "cantidad_nits": len(nits),
                "mensaje": f"Se encontraron {len(nits)} NITs configurados"
            }
            
            # Probar validación de NIT (con el primer NIT disponible)
            if nits:
                primer_nit = list(nits.keys())[0]
                es_valido, nombre, impuestos = validar_nit_administrativo(primer_nit)
                config_status["validar_nit"] = {
                    "status": "OK" if es_valido else "ERROR",
                    "nit_prueba": primer_nit,
                    "es_valido": es_valido,
                    "nombre_entidad": nombre if es_valido else None,
                    "mensaje": "Validación de NIT funcionando" if es_valido else "Error en validación"
                }
                
                # Probar verificación retención fuente
                aplica_rf = nit_aplica_retencion_fuente(primer_nit)
                config_status["retencion_fuente"] = {
                    "status": "OK",
                    "aplica_retencion": aplica_rf,
                    "mensaje": f"NIT {primer_nit} {'SÍ' if aplica_rf else 'NO'} aplica retención fuente"
                }
                
                #  VERIFICAR ESTAMPILLA UNIVERSIDAD
                aplica_estampilla = nit_aplica_estampilla_universidad(primer_nit)
                config_status["estampilla_universidad"] = {
                    "status": "OK",
                    "aplica_estampilla": aplica_estampilla,
                    "mensaje": f"NIT {primer_nit} {'SÍ' if aplica_estampilla else 'NO'} aplica estampilla universidad"
                }
                
                #  VERIFICAR CONTRIBUCIÓN OBRA PÚBLICA
                aplica_obra_publica = nit_aplica_contribucion_obra_publica(primer_nit)
                config_status["contribucion_obra_publica"] = {
                    "status": "OK",
                    "aplica_obra_publica": aplica_obra_publica,
                    "mensaje": f"NIT {primer_nit} {'SÍ' if aplica_obra_publica else 'NO'} aplica contribución obra pública 5%"
                }
            
                #  VERIFICAR DETECCIÓN AUTOMÁTICA INTEGRADA
                try:
                    deteccion_auto = detectar_impuestos_aplicables(primer_nit)
                    config_status["deteccion_automatica"] = {
                        "status": "OK",
                        "impuestos_detectados": deteccion_auto['impuestos_aplicables'],
                        "mensaje": f"Detección automática funcionando: {len(deteccion_auto['impuestos_aplicables'])} impuestos detectados"
                    }
                except Exception as e:
                    config_status["deteccion_automatica"] = {
                        "status": "ERROR",
                        "mensaje": f"Error en detección automática: {str(e)}"
                    }
            else:
                config_status["validar_nit"] = {
                    "status": "WARNING",
                    "mensaje": "No hay NITs para probar validación"
                }
                
        except Exception as e:
            config_status["error_general"] = {
                "status": "ERROR",
                "mensaje": f"Error en funciones de config: {str(e)}",
                "error_completo": str(e)
            }
            
        diagnostico["componentes"]["configuracion"] = config_status
        
        # 4. VERIFICAR ESTRUCTURA DE ARCHIVOS
        archivos_status = {
            "carpetas_requeridas": {},
            "archivos_criticos": {}
        }
        
        carpetas_requeridas = ["Clasificador", "Liquidador", "Extraccion", "Static", "Results"]
        for carpeta in carpetas_requeridas:
            existe = os.path.exists(carpeta)
            archivos_py = []
            if existe:
                try:
                    archivos_py = [f.name for f in Path(carpeta).glob("*.py")]
                except:
                    pass
                    
            archivos_status["carpetas_requeridas"][carpeta] = {
                "existe": existe,
                "archivos_python": len(archivos_py),
                "archivos_lista": archivos_py[:5],  # Solo primeros 5
                "status": "OK" if existe else "ERROR"
            }
            
        # Verificar archivos críticos
        archivos_criticos = [".env", "config.py", "RETEFUENTE_CONCEPTOS.xlsx"]
        for archivo in archivos_criticos:
            existe = os.path.exists(archivo)
            archivos_status["archivos_criticos"][archivo] = {
                "existe": existe,
                "status": "OK" if existe else "ERROR"
            }
            
        diagnostico["componentes"]["estructura_archivos"] = archivos_status
        
        # 5. VERIFICAR CONCEPTOS CARGADOS
        diagnostico["componentes"]["conceptos"] = {
            "total_cargados": len(CONCEPTOS_RETEFUENTE),
            "ejemplos": list(CONCEPTOS_RETEFUENTE.keys())[:3],
            "status": "OK" if len(CONCEPTOS_RETEFUENTE) > 0 else "ERROR",
            "mensaje": f"Se cargaron {len(CONCEPTOS_RETEFUENTE)} conceptos de retefuente"
        }
        
        # 6. DETERMINAR ESTADO GENERAL
        errores_criticos = []
        
        # Verificar errores críticos
        if not GEMINI_API_KEY:
            errores_criticos.append("GEMINI_API_KEY no configurado")
            
        for modulo, status in modulos_status.items():
            if status["importacion"] == "ERROR":
                errores_criticos.append(f"Módulo {modulo} no se puede importar")
                
        if len(CONCEPTOS_RETEFUENTE) == 0:
            errores_criticos.append("No se cargaron conceptos de retefuente")
            
        # Estado final
        if errores_criticos:
            diagnostico["estado_general"] = "ERROR"
            diagnostico["errores_criticos"] = errores_criticos
            diagnostico["mensaje"] = f"Se encontraron {len(errores_criticos)} errores críticos"
        else:
            diagnostico["estado_general"] = "OK"
            diagnostico["mensaje"] = "Sistema integrado funcionando correctamente - Retefuente + Estampilla + Obra Pública"
            
        return diagnostico
        
    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "estado_general": "ERROR_DIAGNOSTICO",
            "mensaje": f"Error ejecutando diagnóstico: {str(e)}",
            "error_completo": str(e)
        }

# ===============================
# EJECUCIÓN PRINCIPAL
# ===============================

if __name__ == "__main__":
    import uvicorn
    

    logger.info(" Iniciando Preliquidador de Retefuente v2.0 - Sistema Integrado")
    logger.info(" Funcionalidades: Retención en la fuente + Estampilla universidad + Obra pública 5%")
    logger.info(f" Gemini configurado: {bool(GEMINI_API_KEY)}")
    logger.info(f" Vision configurado: {bool(GOOGLE_CLOUD_CREDENTIALS)}")
    logger.info(f" Conceptos cargados: {len(CONCEPTOS_RETEFUENTE)}")
    
    # Verificar estructura de carpetas
    carpetas_requeridas = ["Clasificador", "Liquidador", "Extraccion", "Static", "Results"]
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            logger.info(f" Módulo {carpeta}/ encontrado")
        else:
            logger.warning(f" Módulo {carpeta}/ no encontrado")
    
    # Verificar funciones de impuestos especiales
    try:
        # Test de importación estampilla
        test_nit = "800000001"  # NIT ficticio para test
        nit_aplica_estampilla_universidad(test_nit)
        logger.info(f" Función nit_aplica_estampilla_universidad importada correctamente")
        
        # Test de importación obra pública
        nit_aplica_contribucion_obra_publica(test_nit)
        logger.info(f" Función nit_aplica_contribucion_obra_publica importada correctamente")
        
        # Test de detección automática
        detectar_impuestos_aplicables(test_nit)
        logger.info(f" Función detectar_impuestos_aplicables funcionando correctamente")
        
    except Exception as e:
        logger.error(f" Error con funciones de impuestos especiales: {e}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        timeout_keep_alive=120,
        limit_max_requests=1000,
        limit_concurrency=100
    )
