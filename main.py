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

✅ FUNCIONALIDAD INTEGRADA:
- Retención en la fuente (funcionalidad original)
- Estampilla pro universidad nacional - obra publica (nueva funcionalidad)
- Procesamiento paralelo cuando ambos impuestos aplican

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import asyncio
import traceback
import uvicorn
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


# FastAPI y dependencias web
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuración de logging PROFESIONAL
import logging
import sys

# ===============================
# EJECUCIÓN PRINCIPAL
# ===============================
# Configurar logging profesional
logger = logging.getLogger(__name__)


# ===============================
# API FASTAPI
# ===============================

app = FastAPI(
    title="Preliquidador de Retefuente - Colombia",
    description="Sistema automatizado para calcular retención en la fuente con arquitectura modular",
    version="2.0.0"
)

@app.get("/")


def configurar_logging():
    """
    Configuración profesional de logging para evitar duplicación
    
    BENEFICIOS:
    ✅ Evita duplicación de handlers
    ✅ Formato profesional con timestamp
    ✅ Previene propagación conflictiva
    ✅ Configuración centralizada
    """
    # Evitar duplicación de handlers
    if not logging.getLogger().handlers:
        # Crear handler único para stdout
        handler = logging.StreamHandler(sys.stdout)
        
        # Formato profesional con timestamp
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Configurar root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
        
        # Evitar propagación duplicada de frameworks
        logging.getLogger("uvicorn").propagate = False
        logging.getLogger("fastapi").propagate = False
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").propagate = False
        
        print("✅ Logging profesional configurado - Sin duplicaciones")
    else:
        print("⚠️ Logging ya configurado, evitando duplicación")


if __name__ == "__main__":
    logger.info("Iniciando servidor en puerto 8080...")
    port = int(os.environ.get("PORT", 8080))
    reload_mode = os.environ.get("RELOAD", "false").lower() == "false"

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_mode,
        timeout_keep_alive=120,
        limit_max_requests=1000,
        limit_concurrency=100
    )
    
    logger.info("🚀 Iniciando Preliquidador de Retefuente v2.0 - Sistema Integrado")
    logger.info("✅ Funcionalidades: Retención en la fuente + Estampilla universidad + Obra pública 5%")
    logger.info(f"🔑 Gemini configurado: {bool(GEMINI_API_KEY)}")
    logger.info(f"👁️ Vision configurado: {bool(GOOGLE_CLOUD_CREDENTIALS)}")
    logger.info(f"📊 Conceptos cargados: {len(CONCEPTOS_RETEFUENTE)}")
    
    # Verificar estructura de carpetas
    carpetas_requeridas = ["Clasificador", "Liquidador", "Extraccion", "Static", "Results"]
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            logger.info(f"✅ Módulo {carpeta}/ encontrado")
        else:
            logger.warning(f"⚠️ Módulo {carpeta}/ no encontrado")
    
    # Verificar funciones de impuestos especiales
    try:
        # Test de importación estampilla
        test_nit = "800000001"  # NIT ficticio para test
        nit_aplica_estampilla_universidad(test_nit)
        logger.info(f"✅ Función nit_aplica_estampilla_universidad importada correctamente")
        
        # Test de importación obra pública
        nit_aplica_contribucion_obra_publica(test_nit)
        logger.info(f"✅ Función nit_aplica_contribucion_obra_publica importada correctamente")
        
        # Test de detección automática
        detectar_impuestos_aplicables(test_nit)
        logger.info(f"✅ Función detectar_impuestos_aplicables funcionando correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error con funciones de impuestos especiales: {e}")
    




# ===============================
# IMPORTAR MÓDULOS LOCALES
# ===============================

# Importar clases desde módulos
from Clasificador import ProcesadorGemini
from Liquidador import LiquidadorRetencion
from Extraccion import ProcesadorArchivos

# Cargar configuración global - INCLUYE ESTAMPILLA Y OBRA PÚBLICA
from config import (
    inicializar_configuracion, 
    obtener_nits_disponibles, 
    validar_nit_administrativo, 
    nit_aplica_retencion_fuente,
    nit_aplica_estampilla_universidad,
    nit_aplica_contribucion_obra_publica,  # ✅ NUEVA IMPORTACIÓN
    nit_aplica_iva_reteiva,  # ✅ NUEVA IMPORTACIÓN IVA
    detectar_impuestos_aplicables  # ✅ DETECCIÓN AUTOMÁTICA
)

# Dependencias para preprocesamiento Excel
import pandas as pd
import io

# ===============================
# FUNCIONES DE PREPROCESAMIENTO
# ===============================

def preprocesar_excel_limpio(contenido: bytes, nombre_archivo: str = "archivo.xlsx") -> str:
    """
    Preprocesa archivo Excel eliminando filas y columnas vacías.
    Mantiene formato tabular limpio con toda la información intacta.
    
    FUNCIONALIDAD:
    ✅ Elimina filas completamente vacías
    ✅ Elimina columnas completamente vacías
    ✅ Mantiene formato tabular pero limpio
    ✅ Conserva toda la información relevante
    ✅ Óptimo y simple
    ✅ Guarda automáticamente el archivo preprocesado
    
    Args:
        contenido: Contenido binario del archivo Excel
        nombre_archivo: Nombre del archivo (para logging)
        
    Returns:
        str: Texto extraído y limpio del Excel
    """
    try:
        logger.info(f"🧹 Preprocesando Excel: {nombre_archivo}")
        
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
                
                # 🧹 LIMPIEZA SIMPLE: Eliminar filas y columnas completamente vacías
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
            
            # 🧹 LIMPIEZA SIMPLE: Eliminar filas y columnas vacías
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
        logger.info(f"✅ Preprocesamiento completado: {len(texto_final)} caracteres")
        logger.info(f"📊 Hojas: {total_hojas} | Filas eliminadas: {filas_eliminadas_total} | Columnas eliminadas: {columnas_eliminadas_total}")
        logger.info(f"💾 Archivo preprocesado guardado automáticamente")
        
        return texto_final
        
    except Exception as e:
        error_msg = f"Error en preprocesamiento Excel: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

def _guardar_archivo_preprocesado(nombre_archivo: str, texto_preprocesado: str, 
                                 filas_eliminadas: int, columnas_eliminadas: int, total_hojas: int):
    """
    Guarda el archivo Excel preprocesado según nomenclatura {archivo_original}_preprocesado.txt
    
    FUNCIONALIDAD:
    ✅ Guarda en carpeta extracciones/ 
    ✅ Nomenclatura: {archivo_original}_preprocesado.txt
    ✅ Logs básicos para confirmar guardado exitoso
    ✅ Manejo de errores sin afectar flujo principal
    
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
        logger.info(f"💾 Archivo preprocesado guardado: extracciones/{nombre_final}")
        logger.info(f"📊 Estadísticas: {filas_eliminadas} filas y {columnas_eliminadas} columnas eliminadas")
        
    except Exception as e:
        logger.error(f"❌ Error guardando archivo preprocesado: {e}")
        # No fallar el preprocesamiento por un error de guardado

# ===============================
# FUNCIÓN PARA GUARDAR ARCHIVOS JSON
# ===============================

def guardar_archivo_json(contenido: dict, nombre_archivo: str, subcarpeta: str = "") -> bool:
    """
    Guarda archivos JSON en la carpeta Results/ organizados por fecha.
    
    FUNCIONALIDAD:
    ✅ Crea estructura Results/YYYY-MM-DD/
    ✅ Guarda archivos JSON con timestamp
    ✅ Manejo de errores sin afectar flujo principal
    ✅ Logs de confirmación
    ✅ Path absoluto para evitar errores de subpath
    
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
            logger.info(f"💾 JSON guardado: {ruta_relativa}")
        except ValueError:
            # Fallback si relative_to falla
            logger.info(f"💾 JSON guardado: {nombre_final} en {carpeta_final.name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error guardando JSON {nombre_archivo}: {e}")
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

# Conceptos exactos con base mínima y tarifa específica
# Estructura: {concepto: {base_pesos: int, tarifa_retencion: float}}
CONCEPTOS_RETEFUENTE = {
    "Compras generales (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Compras generales (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Compras con tarjeta débito o crédito": {
        "base_pesos": 0,
        "tarifa_retencion": 0.015
    },
    "Compras de bienes o productos agrícolas o pecuarios sin procesamiento industrial": {
        "base_pesos": 3486000,
        "tarifa_retencion": 0.015
    },
    "Compras de bienes o productos agrícolas o pecuarios con procesamiento industrial (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes o productos agrícolas o pecuarios con procesamiento industrial declarantes (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Compras de café pergamino o cereza": {
        "base_pesos": 3486000,
        "tarifa_retencion": 0.005
    },
    "Compras de combustibles derivados del petróleo": {
        "base_pesos": 0,
        "tarifa_retencion": 0.001
    },
    "Enajenación de activos fijos de personas naturales (notarías y tránsito son agentes retenedores)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Compras de vehículos": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Servicios generales (declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.04
    },
    "Servicios generales (no declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.06
    },
    "Servicios de transporte de carga": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios de transporte nacional de pasajeros por vía terrestre": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Servicios de transporte nacional de pasajeros por vía aérea o marítima": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios prestados por empresas de servicios temporales (sobre AIU)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios prestados por empresas de vigilancia y aseo (sobre AIU)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.02
    },
    "Servicios integrales de salud prestados por IPS": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.02
    },
    "Arrendamiento de bienes muebles": {
        "base_pesos": 0,
        "tarifa_retencion": 0.04
    },
    "Arrendamiento de bienes inmuebles": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Otros ingresos tributarios (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Otros ingresos tributarios (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Honorarios y comisiones por servicios (persona juridica)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
     "Honorarios y comisiones por servicios (declarantes)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
    "Honorarios y comisiones por servicios (no declarantes)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.10
    },
    "Servicios de hoteles y restaurantes (declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.035
    },
    "Servicios de hoteles y restaurantes (no declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.035
    },
     "Servicios de licenciamiento o derecho de uso de software": {
        "base_pesos": 0,
        "tarifa_retencion": 0.035
    },
       "Intereses o rendimientos financieros": {
        "base_pesos": 0,
        "tarifa_retencion": 0.07
    },
    "Loterías, rifas, apuestas y similares": {
        "base_pesos": 2390000,
        "tarifa_retencion": 0.2
    },
    "Emolumentos eclesiásticos (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.04
    },
    "Emolumentos eclesiásticos ( no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Retención en colocación independiente de juegos de suerte y azar": {
        "base_pesos": 249000,
        "tarifa_retencion": 0.03
    },
     "Contratos de construcción y urbanización.": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.02
    },
    "compra de oro por las sociedades de comercialización internacional.": {
        "base_pesos": 0,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes raíces cuya destinación y uso sea vivienda de habitación (por las primeras $497990000 pesos colombianos)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Compras de bienes raíces cuya destinación y uso sea vivienda de habitación (exceso de $497990000 pesos colombianos)": {
        "base_pesos": 497990000,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes raíces cuya destinación y uso sea distinto a vivienda de habitación": {
        "base_pesos": 0,
        "tarifa_retencion": 0.025
    },
    "Servicios de consultoría en informática":{
        "base_pesos":0,
        "tarifa_retencion":0.035
    }
}

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

class CondicionesArticulo383(BaseModel):
    es_persona_natural: bool = False
    concepto_aplicable: bool = False
    es_primer_pago: bool = False  # NUEVO CAMPO
    planilla_seguridad_social: bool = False
    cuenta_cobro: bool = False

class DeduccionesArticulo383(BaseModel):
    intereses_vivienda: DeduccionArticulo383 = DeduccionArticulo383()
    dependientes_economicos: DeduccionArticulo383 = DeduccionArticulo383()
    medicina_prepagada: DeduccionArticulo383 = DeduccionArticulo383()
    rentas_exentas: DeduccionArticulo383 = DeduccionArticulo383()

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
    aplica: bool = False
    condiciones_cumplidas: CondicionesArticulo383 = CondicionesArticulo383()
    deducciones_identificadas: Optional[DeduccionesArticulo383] = DeduccionesArticulo383()
    calculo: Optional[CalculoArticulo383] = CalculoArticulo383()

class AnalisisFactura(BaseModel):
    conceptos_identificados: List[ConceptoIdentificado]
    naturaleza_tercero: Optional[NaturalezaTercero]
    articulo_383: Optional[InformacionArticulo383] = None  # NUEVA SECCIÓN
    es_facturacion_exterior: bool
    valor_total: Optional[float]
    iva: Optional[float]
    observaciones: List[str]

class ResultadoLiquidacion(BaseModel):
    valor_base_retencion: float
    valor_retencion: float
    tarifa_aplicada: float
    concepto_aplicado: str
    fecha_calculo: str
    puede_liquidar: bool
    mensajes_error: List[str]

# ===============================
# ✅ FUNCIÓN DE LIQUIDACIÓN SEGURA DE RETEFUENTE
# ===============================

def liquidar_retefuente_seguro(analisis_retefuente: Dict[str, Any], nit_administrativo: str) -> Dict[str, Any]:
    """
    Liquida retefuente con manejo seguro de estructura de datos.
    
    SOLUCIONA EL ERROR: 'dict' object has no attribute 'es_facturacion_exterior'
    
    FUNCIONALIDAD:
    ✅ Maneja estructura JSON de análisis de Gemini
    ✅ Extrae correctamente la sección "analisis" 
    ✅ Convierte dict a objeto AnalisisFactura
    ✅ Verifica campos requeridos antes de liquidar
    ✅ Manejo robusto de errores con logging detallado
    ✅ Fallback seguro en caso de errores
    
    Args:
        analisis_retefuente: Resultado del análisis de Gemini (estructura JSON)
        nit_administrativo: NIT administrativo
        
    Returns:
        Dict con resultado de liquidación o información de error
    """
    try:
        logger.info(f"🧮 Iniciando liquidación segura de retefuente para NIT: {nit_administrativo}")
        
        # ✅ VERIFICAR ESTRUCTURA Y EXTRAER ANÁLISIS
        if isinstance(analisis_retefuente, dict):
            if "analisis" in analisis_retefuente:
                # Estructura: {"analisis": {...}, "timestamp": ..., etc}
                datos_analisis = analisis_retefuente["analisis"]
                logger.info("📊 Extrayendo análisis desde estructura JSON con clave 'analisis'")
            else:
                # Estructura directa: {"es_facturacion_exterior": ..., etc}
                datos_analisis = analisis_retefuente
                logger.info("📊 Usando estructura directa de análisis")
        else:
            # Ya es un objeto, usar directamente
            datos_analisis = analisis_retefuente
            logger.info("📊 Usando objeto AnalisisFactura directamente")
        
        # ✅ VERIFICAR CAMPOS REQUERIDOS
        campos_requeridos = ["es_facturacion_exterior", "conceptos_identificados", "naturaleza_tercero"]
        campos_faltantes = []
        
        for campo in campos_requeridos:
            if campo not in datos_analisis:
                campos_faltantes.append(campo)
        
        if campos_faltantes:
            error_msg = f"Campos requeridos faltantes: {', '.join(campos_faltantes)}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"🔑 Claves disponibles: {list(datos_analisis.keys()) if isinstance(datos_analisis, dict) else 'No es dict'}")
            
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
        
        # ✅ CREAR OBJETO ANALYSISFACTURA MANUALMENTE
        from Clasificador.clasificador import AnalisisFactura, ConceptoIdentificado, NaturalezaTercero
        
        # Convertir conceptos identificados
        conceptos = []
        conceptos_data = datos_analisis.get("conceptos_identificados", [])
        
        if not isinstance(conceptos_data, list):
            logger.warning(f"⚠️ conceptos_identificados no es lista: {type(conceptos_data)}")
            conceptos_data = []
        
        for concepto_data in conceptos_data:
            if isinstance(concepto_data, dict):
                concepto_obj = ConceptoIdentificado(
                    concepto=concepto_data.get("concepto", ""),
                    tarifa_retencion=concepto_data.get("tarifa_retencion", 0.0),
                    base_gravable=concepto_data.get("base_gravable", None)
                )
                conceptos.append(concepto_obj)
                logger.info(f"✅ Concepto convertido: {concepto_obj.concepto} - {concepto_obj.tarifa_retencion}%")
        
        # Convertir naturaleza del tercero
        naturaleza_data = datos_analisis.get("naturaleza_tercero", {})
        if not isinstance(naturaleza_data, dict):
            logger.warning(f"⚠️ naturaleza_tercero no es dict: {type(naturaleza_data)}")
            naturaleza_data = {}
        
        naturaleza_obj = NaturalezaTercero(
            es_persona_natural=naturaleza_data.get("es_persona_natural", None),
            es_declarante=naturaleza_data.get("es_declarante", None),
            regimen_tributario=naturaleza_data.get("regimen_tributario", None),
            es_autorretenedor=naturaleza_data.get("es_autorretenedor", None),
            es_responsable_iva=naturaleza_data.get("es_responsable_iva", None)
        )
        
        # Crear objeto completo
        analisis_obj = AnalisisFactura(
            conceptos_identificados=conceptos,
            naturaleza_tercero=naturaleza_obj,
            es_facturacion_exterior=datos_analisis.get("es_facturacion_exterior", False),
            valor_total=datos_analisis.get("valor_total", None),
            iva=datos_analisis.get("iva", None),
            observaciones=datos_analisis.get("observaciones", [])
        )
        
        logger.info(f"✅ Objeto AnalisisFactura creado: {len(conceptos)} conceptos, facturación_exterior={analisis_obj.es_facturacion_exterior}")
        
        # ✅ LIQUIDAR CON OBJETO VÁLIDO
        liquidador_retencion = LiquidadorRetencion()
        resultado = liquidador_retencion.liquidar_factura(analisis_obj, nit_administrativo)
        
        # Convertir resultado a dict
        resultado_dict = {
            "aplica": resultado.puede_liquidar,
            "valor_retencion": resultado.valor_retencion,
            "tarifa_aplicada": resultado.tarifa_aplicada,
            "concepto": resultado.concepto_aplicado,
            "base_gravable": resultado.valor_base_retencion,
            "fecha_calculo": resultado.fecha_calculo,
            "observaciones": resultado.mensajes_error,
            "calculo_exitoso": resultado.puede_liquidar
        }
        
        if resultado.puede_liquidar:
            logger.info(f"✅ Retefuente liquidada exitosamente: ${resultado.valor_retencion:,.2f}")
        else:
            logger.warning(f"⚠️ Retefuente no se pudo liquidar: {resultado.mensajes_error}")
        
        return resultado_dict
        
    except ImportError as e:
        error_msg = f"Error importando clases necesarias: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {
            "aplica": False,
            "error": error_msg,
            "valor_retencion": 0.0,
            "observaciones": ["Error importando módulos de análisis", "Revise la configuración del sistema"]
        }
        
    except Exception as e:
        error_msg = f"Error liquidando retefuente: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"📄 Tipo de estructura recibida: {type(analisis_retefuente)}")
        
        # Log adicional para debugging
        if isinstance(analisis_retefuente, dict):
            logger.error(f"🔑 Claves disponibles en análisis: {list(analisis_retefuente.keys())}")
            if "analisis" in analisis_retefuente and isinstance(analisis_retefuente["analisis"], dict):
                logger.error(f"🔑 Claves en 'analisis': {list(analisis_retefuente['analisis'].keys())}")
        
        # Log del traceback completo para debugging
        import traceback
        logger.error(f"🐛 Traceback completo: {traceback.format_exc()}")
        
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


# Servir archivos estáticos desde la carpeta Static
app.mount("/static", StaticFiles(directory="Static"), name="static")

async def inicio():
    """Página de inicio - Servir frontend desde Static/"""
    try:
        with open("Static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Frontend no encontrado</h1><p>Archivo Static/index.html no existe</p>",
            status_code=404
        )

@app.post("/procesar-documentos")
async def procesar_documentos(
    archivos: List[UploadFile] = File(...),
    nit_administrativo: str = Form(...)
):
    """
    Endpoint secundario para procesar documentos de facturas.
    Redirige al endpoint principal manteniendo compatibilidad.
    """
    # Redirigir al endpoint principal
    return await procesar_facturas(archivos, nit_administrativo)

# ===============================
# 🚀 ENDPOINT PRINCIPAL ÚNICO - RETEFUENTE + ESTAMPILLA INTEGRADOS
# ===============================

@app.post("/api/procesar-facturas-test")
async def procesar_facturas(
    archivos: List[UploadFile] = File(...),
    nit_administrativo: str = Form(...)
):
    """
    Endpoint principal para procesar documentos de facturas.
    
    ✅ FUNCIONALIDAD INTEGRADA:
    - Retención en la fuente (funcionalidad original mantenida)
    - Estampilla pro universidad nacional (funcionalidad integrada)
    - Contribución a obra pública 5% (funcionalidad integrada)
    - IVA y ReteIVA (nueva funcionalidad agregada)
    - Procesamiento paralelo cuando múltiples impuestos aplican
    - Guardado automático de JSONs en Results/
    
    ✅ ÚNICO ENDPOINT: Bug crítico corregido - Duplicación eliminada
    """
    inicio_tiempo = datetime.now()
    logger.info(f"\n{'='*60}")
    logger.info(f"🚀 PROCESANDO {len(archivos)} ARCHIVOS - SISTEMA INTEGRADO")
    logger.info(f"📅 {inicio_tiempo.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔍 NIT administrativo: {nit_administrativo}")
    logger.info(f"{'='*60}")
    
    try:
        # 1. VALIDAR NIT ADMINISTRATIVO
        logger.info("🔍 Paso 1: Validando NIT administrativo...")
        es_valido, nombre_entidad, impuestos_aplicables = validar_nit_administrativo(nit_administrativo)
        if not es_valido:
            error_detail = {
                "error": "NIT no válido",
                "mensaje": f"NIT administrativo '{nit_administrativo}' no está configurado",
                "tipo": "validation_error"
            }
            logger.error(f"❌ {error_detail['mensaje']}")
            raise HTTPException(status_code=400, detail=error_detail)
        
        logger.info(f"✅ NIT validado: {nombre_entidad}")
        logger.info(f"📋 Impuestos aplicables: {', '.join(impuestos_aplicables)}")
        
        # Verificar si aplica retefuente
        aplica_retencion_fuente = nit_aplica_retencion_fuente(nit_administrativo)
        if not aplica_retencion_fuente:
            resultado_sin_retencion = {
                "exito": False,
                "error": "NO aplica retención en la fuente",
                "mensaje": f"El NIT {nit_administrativo} ({nombre_entidad}) no tiene retención en la fuente configurada",
                "nit_administrativo": nit_administrativo,
                "entidad": nombre_entidad,
                "impuestos_aplicables": impuestos_aplicables,
                "timestamp": datetime.now().isoformat()
            }
            
            # Guardar resultado en JSON
            guardar_archivo_json(resultado_sin_retencion, "sin_retencion_fuente")
            
            return resultado_sin_retencion
        
        # 2. DETECCIÓN AUTOMÁTICA DE IMPUESTOS APLICABLES (INTEGRADA)
        deteccion_impuestos = detectar_impuestos_aplicables(nit_administrativo)
        
        aplica_retencion_fuente = nit_aplica_retencion_fuente(nit_administrativo)
        aplica_estampilla = deteccion_impuestos['aplica_estampilla_universidad']
        aplica_obra_publica = deteccion_impuestos['aplica_contribucion_obra_publica']  # 🏗️ NUEVO
        procesamiento_paralelo = deteccion_impuestos['procesamiento_paralelo']
        
        logger.info(f"🏛️ Estampilla Pro Universidad Nacional: {'SÍ aplica' if aplica_estampilla else 'NO aplica'}")
        logger.info(f"🏗️ Contribución a Obra Pública 5%: {'SÍ aplica' if aplica_obra_publica else 'NO aplica'}")
        logger.info(f"⚡ Procesamiento paralelo: {'SÍ' if procesamiento_paralelo else 'NO'}")
        
        impuestos_a_procesar = deteccion_impuestos['impuestos_aplicables'].copy()
        if aplica_retencion_fuente and "RETENCION_FUENTE" not in impuestos_a_procesar:
            impuestos_a_procesar.append("RETENCION_FUENTE")
            
        logger.info(f"⚡ Impuestos a procesar: {', '.join(impuestos_a_procesar)}")
        logger.info(f"📊 Total impuestos: {len(impuestos_a_procesar)}")
        
        # Log detallado de detección
        if aplica_obra_publica:
            logger.info(f"🏗️ NIT configurado para obra pública: {deteccion_impuestos.get('nombre_entidad_obra_publica', 'N/A')}")
        if aplica_estampilla:
            logger.info(f"🏛️ NIT configurado para estampilla: {deteccion_impuestos.get('nombre_entidad_estampilla', 'N/A')}")
        
        # 3. EXTRAER TEXTO DE ARCHIVOS
        logger.info(f"📄 Paso 2: Extrayendo texto de {len(archivos)} archivos...")
        extractor = ProcesadorArchivos()
        
        # Crear lista de archivos para el extractor
        archivos_para_extractor = []
        for archivo in archivos:
            await archivo.seek(0)
            archivos_para_extractor.append(archivo)
        
        # Extraer texto usando el extractor original
        logger.info(f"🔍 Usando extractor modular para todos los archivos...")
        textos_archivos_original = await extractor.procesar_multiples_archivos(archivos_para_extractor)
        
        # Aplicar preprocesamiento a Excel
        logger.info("🧹 Aplicando preprocesamiento híbrido a archivos Excel...")
        textos_archivos = {}
        archivos_excel_preprocesados = 0
        
        for archivo in archivos:
            nombre_archivo = archivo.filename
            
            if nombre_archivo in textos_archivos_original:
                texto_original = textos_archivos_original[nombre_archivo]
                
                # Preprocesamiento Excel si es necesario
                if (nombre_archivo.lower().endswith(('.xlsx', '.xls')) and 
                    not texto_original.startswith("ERROR")):
                    
                    logger.info(f"📊 Preprocesando Excel: {nombre_archivo}")
                    try:
                        await archivo.seek(0)
                        contenido = await archivo.read()
                        texto_preprocesado = preprocesar_excel_limpio(contenido, nombre_archivo)
                        
                        if not texto_preprocesado.startswith("Error"):
                            textos_archivos[nombre_archivo] = texto_preprocesado
                            archivos_excel_preprocesados += 1
                            logger.info(f"✅ Excel preprocesado: {nombre_archivo} ({len(texto_preprocesado)} caracteres)")
                        else:
                            textos_archivos[nombre_archivo] = texto_original
                            logger.warning(f"⚠️ Usando original para: {nombre_archivo}")
                    except Exception as e:
                        textos_archivos[nombre_archivo] = texto_original
                        logger.warning(f"⚠️ Error preprocesando {nombre_archivo}: {e}")
                else:
                    textos_archivos[nombre_archivo] = texto_original
            else:
                textos_archivos[nombre_archivo] = "ERROR: Archivo no procesado"
        
        logger.info(f"✅ Extracción completada: {len(textos_archivos)}/{len(archivos)} archivos exitosos")
        logger.info(f"🧹 Excel preprocesados: {archivos_excel_preprocesados}")
        
        # 4. CLASIFICAR DOCUMENTOS Y DETECTAR TIPO
        logger.info(f"🏷️ Paso 3: Clasificando documentos con Gemini...")
        clasificador = ProcesadorGemini()
        
        clasificacion, es_consorcio, es_facturacion_extranjera = await clasificador.clasificar_documentos(textos_archivos)
        
        # Guardar clasificación en JSON
        clasificacion_data = {
            "timestamp": datetime.now().isoformat(),
            "archivos_procesados": len(archivos),
            "nit_administrativo": nit_administrativo,
            "clasificacion": clasificacion,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "textos_extraidos": {nombre: len(texto) for nombre, texto in textos_archivos.items()}
        }
        guardar_archivo_json(clasificacion_data, "clasificacion_documentos")
        
        logger.info(f"✅ Clasificación completada: {len(clasificacion)} documentos")
        logger.info(f"🏢 Consorcio detectado: {es_consorcio}")
        logger.info(f"🌍 Facturación extranjera: {es_facturacion_extranjera}")
        
        # 5. PREPARAR DOCUMENTOS CLASIFICADOS
        documentos_clasificados = {}
        for nombre_archivo, categoria in clasificacion.items():
            documentos_clasificados[nombre_archivo] = {
                "categoria": categoria,
                "texto": textos_archivos.get(nombre_archivo, "")
            }
        
        # 6. PROCESAR SEGÚN TIPO DE FACTURA
        if es_consorcio:
            logger.info(f"🏢 Procesando como CONSORCIO {'EXTRANJERO' if es_facturacion_extranjera else 'NACIONAL'}")
            resultado_analisis = await clasificador.analizar_consorcio(
                documentos_clasificados, es_facturacion_extranjera
            )
            
            # Para consorcios, por ahora solo retefuente
            resultado_analisis.update({
                "procesamiento_paralelo": False,
                "aplica_estampilla_universidad": False,
                "impuestos_procesados": ["RETENCION_FUENTE"],
                "es_consorcio": True
            })
            
        else:
            # 7. PROCESAMIENTO SEGÚN IMPUESTOS APLICABLES
            if len(impuestos_a_procesar) > 1:
                # PROCESAMIENTO PARALELO: RETEFUENTE + ESTAMPILLA + OBRA PÚBLICA
                logger.info(f"⚡ Iniciando procesamiento paralelo: {' + '.join(impuestos_a_procesar)}")
                
                # Mostrar cuáles impuestos se van a procesar en paralelo
                if aplica_estampilla and aplica_obra_publica:
                    logger.info("🔥 PROCESAMIENTO COMPLETO: RETEFUENTE + ESTAMPILLA + OBRA PÚBLICA")
                elif aplica_estampilla:
                    logger.info("⚡ PROCESAMIENTO DUAL: RETEFUENTE + ESTAMPILLA UNIVERSIDAD")
                elif aplica_obra_publica:
                    logger.info("⚡ PROCESAMIENTO DUAL: RETEFUENTE + OBRA PÚBLICA")
                
                # Importar liquidador de estampilla con modelos
                from Liquidador.liquidador_estampilla import LiquidadorEstampilla, AnalisisContrato, TerceroContrato, ObjetoContratoIdentificado
                liquidador_estampilla = LiquidadorEstampilla()
                
                # EJECUTAR EN PARALELO: Retefuente + Estampilla + Obra Pública
                logger.info("🔄 Ejecutando análisis paralelo con Gemini...")
                retefuente_task = clasificador.analizar_factura(documentos_clasificados, es_facturacion_extranjera)
                
                # El análisis de estampilla YA incluye obra pública desde la integración
                # porque analizar_estampilla ahora es analizar_impuestos_especiales
                impuestos_especiales_task = clasificador.analizar_estampilla(documentos_clasificados)
                
                # Esperar ambos resultados
                analisis_factura, analisis_impuestos_especiales = await asyncio.gather(
                    retefuente_task, 
                    impuestos_especiales_task,
                    return_exceptions=True
                )
                
                # ✅ VALIDAR EXCEPCIONES ANTES DE USAR LOS RESULTADOS
                if isinstance(analisis_factura, Exception):
                    logger.error(f"❌ Error en análisis de retefuente: {analisis_factura}")
                    analisis_factura = None
                    
                if isinstance(analisis_impuestos_especiales, Exception):
                    logger.error(f"❌ Error en análisis de impuestos especiales: {analisis_impuestos_especiales}")
                    analisis_impuestos_especiales = {}
                else:
                    # Solo hacer logging si NO es una excepción
                    logger.info(f"✅ Análisis de impuestos especiales exitoso")
                
                # Renombrar para compatibilidad con el código existente
                analisis_estampilla = analisis_impuestos_especiales
                
                # Guardar análisis en JSON
                analisis_data = {
                    "timestamp": datetime.now().isoformat(),
                    "procesamiento_paralelo": True,
                    "impuestos_aplicables": impuestos_a_procesar,
                    "deteccion_automatica": deteccion_impuestos,
                    "retefuente_analisis": analisis_factura.dict() if analisis_factura else None,
                    "impuestos_especiales_analisis": analisis_impuestos_especiales,
                    "es_facturacion_extranjera": es_facturacion_extranjera
                }
                guardar_archivo_json(analisis_data, "analisis_paralelo")
                
                # LIQUIDACIÓN PARALELA (HASTA 3 IMPUESTOS)
                logger.info("💰 Iniciando liquidación paralela de impuestos...")
                liquidador_retencion = LiquidadorRetencion()
                resultado_retefuente = None
                resultado_estampilla = None
                resultado_obra_publica = None
                
                # ✅ LIQUIDAR RETEFUENTE DE FORMA SEGURA
                if analisis_factura:
                    logger.info("🔄 Ejecutando liquidación segura de retefuente...")
                    
                    # Guardar análisis individual de retefuente
                    analisis_retefuente_data = {
                        "timestamp": datetime.now().isoformat(),
                        "tipo_analisis": "retefuente",
                        "nit_administrativo": nit_administrativo,
                        "procesamiento_paralelo": True,
                        "analisis": analisis_factura.dict() if hasattr(analisis_factura, 'dict') else analisis_factura
                    }
                    guardar_archivo_json(analisis_retefuente_data, "analisis_retefuente")
                    logger.info("💾 Análisis individual guardado: analisis_retefuente")
                    
                    # ✅ USAR FUNCIÓN SEGURA EN LUGAR DE LLAMADA DIRECTA
                    resultado_retefuente_dict = liquidar_retefuente_seguro(
                        analisis_retefuente_data, nit_administrativo
                    )
                    
                    if resultado_retefuente_dict.get("calculo_exitoso", False):
                        logger.info(f"✅ Retefuente liquidada: ${resultado_retefuente_dict.get('valor_retencion', 0):,.2f}")
                        
                        # Crear objeto compatible para el resto del código
                        resultado_retefuente = type('obj', (object,), {
                            'puede_liquidar': resultado_retefuente_dict.get("aplica", False),
                            'valor_retencion': resultado_retefuente_dict.get("valor_retencion", 0.0),
                            'concepto_aplicado': resultado_retefuente_dict.get("concepto", ""),
                            'tarifa_aplicada': resultado_retefuente_dict.get("tarifa_aplicada", 0.0),
                            'mensajes_error': resultado_retefuente_dict.get("observaciones", [])
                        })()
                    else:
                        logger.error(f"❌ Error liquidando retefuente: {resultado_retefuente_dict.get('error', 'Error desconocido')}")
                        resultado_retefuente = None
                else:
                    logger.warning("⚠️ No hay análisis de factura para liquidar retefuente")
                    resultado_retefuente = None
                
                # Liquidar impuestos especiales según detección automática
                if analisis_impuestos_especiales:
                    # ADAPTADOR: Convertir respuesta de Gemini a objetos esperados por liquidadores
                    logger.info("🔄 Aplicando adaptadores de datos para liquidación integrada...")
                    logger.info(f"🔍 Procesando {len(analisis_impuestos_especiales)} impuestos especiales detectados")
                    
                    # Liquidar estampilla si aplica
                    if aplica_estampilla and analisis_impuestos_especiales.get("estampilla_universidad"):
                        logger.info("🏦 Procesando estampilla universidad con adaptador de datos...")
                        try:
                            estampilla_data = analisis_impuestos_especiales["estampilla_universidad"]
                            tercero_data = analisis_impuestos_especiales.get("tercero_identificado", {})
                            
                            logger.info(f"🧐 Debug estampilla_data: {estampilla_data}")
                            logger.info(f"🧐 Debug tercero_data: {tercero_data}")
                            
                            # CREAR OBJETO AnalisisContrato desde respuesta de Gemini
                            
                            # Crear objeto tercero
                            tercero = TerceroContrato(
                                nombre=tercero_data.get("nombre", ""),
                                es_consorcio=tercero_data.get("es_consorcio", False),
                                administra_recursos_publicos=tercero_data.get("administra_recursos_publicos", False)
                            )
                            
                            # Crear objeto contrato
                            objeto_contrato = ObjetoContratoIdentificado(
                                objeto=estampilla_data.get("objeto_contrato", {}).get("tipo", "no_identificado"),
                                aplica_estampilla=estampilla_data.get("objeto_contrato", {}).get("aplica_estampilla", False),
                                palabras_clave_encontradas=estampilla_data.get("objeto_contrato", {}).get("palabras_clave_encontradas", [])
                            )
                            
                            # Crear análisis completo
                            analisis_contrato = AnalisisContrato(
                                valor_total_contrato=estampilla_data.get("valor_contrato", {}).get("valor_total_pesos", 0.0),
                                valor_total_uvt=estampilla_data.get("valor_contrato", {}).get("valor_total_uvt", 0.0),
                                objeto_identificado=objeto_contrato,
                                tercero=tercero,
                                observaciones=[]
                            )
                            
                            logger.info(f"📊 Datos estampilla - Valor: ${analisis_contrato.valor_total_contrato:,.2f}, Tercero: {tercero.nombre}, Objeto: {objeto_contrato.objeto}")
                            
                            # LLAMAR LIQUIDADOR CON OBJETO CORRECTO
                            if analisis_contrato.valor_total_contrato and analisis_contrato.valor_total_contrato > 0:
                                resultado_estampilla = liquidador_estampilla.liquidar_estampilla(
                                    analisis_contrato, nit_administrativo
                                )
                                logger.info(f"✅ Estampilla liquidada: ${resultado_estampilla.valor_estampilla:,.2f}")
                            else:
                                logger.warning("⚠️ Valor de contrato es 0 o no identificado para estampilla")
                                resultado_estampilla = None
                            
                        except Exception as e:
                            logger.error(f"❌ Error liquidando estampilla: {e}")
                    
                    # Liquidar obra pública si aplica
                    if aplica_obra_publica and analisis_impuestos_especiales.get("contribucion_obra_publica"):
                        logger.info("🏗️ Procesando contribución obra pública con adaptador de datos...")
                        try:
                            obra_data = analisis_impuestos_especiales["contribucion_obra_publica"]
                            tercero_data = analisis_impuestos_especiales.get("tercero_identificado", {})
                            
                            logger.info(f"🧐 Debug obra_data: {obra_data}")
                            logger.info(f"🧐 Debug tercero_data: {tercero_data}")
                            
                            # EXTRAER PARÁMETROS PARA OBRA PÚBLICA
                            valor_factura_sin_iva = obra_data.get("valor_factura", {}).get("valor_sin_iva", 0.0)
                            nombre_tercero = tercero_data.get("nombre", "")
                            es_consorcio = tercero_data.get("es_consorcio", False)
                            consorciados_info = tercero_data.get("consorciados", [])
                            
                            logger.info(f"📊 Datos extraídos - Valor: ${valor_factura_sin_iva:,.2f}, Tercero: {nombre_tercero}, Consorcio: {es_consorcio}")
                            
                            # Crear descripción del objeto
                            palabras_clave = obra_data.get("objeto_contrato", {}).get("palabras_clave_encontradas", [])
                            objeto_contrato = " ".join(palabras_clave) if palabras_clave else "contrato de obra"
                            
                            # LLAMAR LIQUIDADOR DE OBRA PÚBLICA
                            if valor_factura_sin_iva and valor_factura_sin_iva > 0:
                                resultado_obra_publica = liquidador_estampilla.liquidar_contribucion_obra_publica(
                                    valor_factura_sin_iva=valor_factura_sin_iva,
                                    nit_administrativo=nit_administrativo,
                                    nombre_tercero=nombre_tercero,
                                    objeto_contrato=objeto_contrato,
                                    es_consorcio=es_consorcio,
                                    consorciados_info=consorciados_info
                                )
                                logger.info(f"✅ Obra pública liquidada: ${resultado_obra_publica.valor_contribucion:,.2f}")
                            else:
                                logger.warning("⚠️ Valor de factura es 0 o no identificado para obra pública")
                                resultado_obra_publica = None
                            
                        except Exception as e:
                            logger.error(f"❌ Error liquidando obra pública: {e}")
                
                # Consolidar resultados de todos los impuestos
                valor_total_impuestos = (
                    (resultado_retefuente.valor_retencion if resultado_retefuente else 0) + 
                    (resultado_estampilla.valor_estampilla if resultado_estampilla and hasattr(resultado_estampilla, 'valor_estampilla') else 0) +
                    (resultado_obra_publica.valor_contribucion if resultado_obra_publica and hasattr(resultado_obra_publica, 'valor_contribucion') else 0)
                )
                
                resultado_analisis = {
                    "procesamiento_paralelo": True,
                    "aplica_estampilla_universidad": aplica_estampilla,
                    "impuestos_procesados": impuestos_a_procesar,
                    "exito": True,
                    "aplica_retencion": resultado_retefuente.puede_liquidar if resultado_retefuente else False,
                    "valor_total_factura": analisis_factura.valor_total if analisis_factura else 0,
                    "iva_total": analisis_factura.iva if analisis_factura else 0,
                    "valor_retencion": resultado_retefuente.valor_retencion if resultado_retefuente else 0,
                    "concepto": resultado_retefuente.concepto_aplicado if resultado_retefuente else "No identificado",
                    "tarifa_retencion": resultado_retefuente.tarifa_aplicada if resultado_retefuente else 0,
                    "retefuente": {
                        "aplica": resultado_retefuente.puede_liquidar if resultado_retefuente else False,
                        "valor_retencion": resultado_retefuente.valor_retencion if resultado_retefuente else 0,
                        "concepto": resultado_retefuente.concepto_aplicado if resultado_retefuente else "No identificado",
                        "tarifa_retencion": resultado_retefuente.tarifa_aplicada if resultado_retefuente else 0,
                        "observaciones": resultado_retefuente.mensajes_error if resultado_retefuente else []
                    },
                    "estampilla_universidad": {
                        "aplica": resultado_estampilla.aplica if resultado_estampilla else False,
                        "estado": resultado_estampilla.estado if resultado_estampilla else "No procesada",
                        "valor_estampilla": resultado_estampilla.valor_estampilla if resultado_estampilla else 0,
                        "tarifa_aplicada": resultado_estampilla.tarifa_aplicada if resultado_estampilla else 0,
                        "rango_uvt": resultado_estampilla.rango_uvt if resultado_estampilla else "No calculado",
                        "valor_contrato_pesos": resultado_estampilla.valor_contrato_pesos if resultado_estampilla else 0,
                        "valor_contrato_uvt": resultado_estampilla.valor_contrato_uvt if resultado_estampilla else 0,
                        "observaciones": resultado_estampilla.mensajes_error if resultado_estampilla else ["No se pudo procesar estampilla"]
                    },
                    "contribucion_obra_publica": {
                        "aplica": resultado_obra_publica.aplica if resultado_obra_publica else aplica_obra_publica,
                        "estado": resultado_obra_publica.estado if resultado_obra_publica else ("No procesada" if aplica_obra_publica else "No aplica"),
                        "valor_contribucion": resultado_obra_publica.valor_contribucion if resultado_obra_publica else 0,
                        "tarifa_aplicada": resultado_obra_publica.tarifa_aplicada if resultado_obra_publica else 0.05,
                        "valor_factura_sin_iva": resultado_obra_publica.valor_factura_sin_iva if resultado_obra_publica else 0,
                        "observaciones": resultado_obra_publica.mensajes_error if resultado_obra_publica else (["No se pudo procesar obra pública"] if aplica_obra_publica else ["NIT no configurado para obra pública"])
                    },
                    "es_facturacion_extranjera": es_facturacion_extranjera,
                    "resumen_total": {
                        "valor_total_impuestos": valor_total_impuestos,
                        "impuestos_aplicables": {
                            "retefuente": resultado_retefuente.puede_liquidar if resultado_retefuente else False,
                            "estampilla": resultado_estampilla.aplica if resultado_estampilla else False,
                            "obra_publica": resultado_obra_publica.aplica if resultado_obra_publica else False
                        }
                    },
                    "observaciones": (analisis_factura.observaciones if analisis_factura else []) + (resultado_retefuente.mensajes_error if resultado_retefuente else []),
                    "naturaleza_tercero": analisis_factura.naturaleza_tercero.dict() if analisis_factura and analisis_factura.naturaleza_tercero else None
                }
                
                logger.info("⚡ Procesamiento paralelo completado exitosamente")
                logger.info(f"💰 Total impuestos calculados: ${valor_total_impuestos:,.2f}")
                
            else:
                # FLUJO ORIGINAL: Solo retefuente
                logger.info("🧠 Procesando solo RETEFUENTE (estampilla no aplica)")
                
                analisis_factura = await clasificador.analizar_factura(
                    documentos_clasificados, es_facturacion_extranjera
                )
                
                # Guardar análisis en JSON
                analisis_data = {
                    "timestamp": datetime.now().isoformat(),
                    "procesamiento_paralelo": False,
                    "analisis_factura": analisis_factura.dict(),
                    "es_facturacion_extranjera": es_facturacion_extranjera
                }
                guardar_archivo_json(analisis_data, "analisis_factura")
                
                logger.info(f"✅ Análisis completado: {len(analisis_factura.conceptos_identificados)} conceptos identificados")
                
                # Liquidar retención
                logger.info(f"💰 Calculando retención en la fuente...")
                liquidador = LiquidadorRetencion()
                
                # ✅ LIQUIDACIÓN SEGURA INDIVIDUAL
                logger.info("🔄 Ejecutando liquidación segura individual...")
                
                # Crear estructura de datos compatible
                analisis_retefuente_data = {
                    "timestamp": datetime.now().isoformat(),
                    "tipo_analisis": "retefuente",
                    "nit_administrativo": nit_administrativo,
                    "procesamiento_paralelo": False,
                    "analisis": analisis_factura.dict() if hasattr(analisis_factura, 'dict') else analisis_factura
                }
                guardar_archivo_json(analisis_retefuente_data, "analisis_retefuente")
                
                # ✅ USAR FUNCIÓN SEGURA
                resultado_retefuente_dict = liquidar_retefuente_seguro(
                    analisis_retefuente_data, nit_administrativo
                )
                
                if resultado_retefuente_dict.get("calculo_exitoso", False):
                    if es_facturacion_extranjera:
                        logger.info(f"🌍 Liquidación extranjera segura: ${resultado_retefuente_dict.get('valor_retencion', 0):,.0f}")
                    else:
                        logger.info(f"🇨🇴 Liquidación nacional segura: ${resultado_retefuente_dict.get('valor_retencion', 0):,.0f}")
                    
                    # Crear objeto compatible
                    resultado_liquidacion = type('obj', (object,), {
                        'puede_liquidar': resultado_retefuente_dict.get("aplica", False),
                        'valor_retencion': resultado_retefuente_dict.get("valor_retencion", 0.0),
                        'concepto_aplicado': resultado_retefuente_dict.get("concepto", ""),
                        'tarifa_aplicada': resultado_retefuente_dict.get("tarifa_aplicada", 0.0),
                        'mensajes_error': resultado_retefuente_dict.get("observaciones", [])
                    })()
                else:
                    logger.error(f"❌ Error en liquidación segura: {resultado_retefuente_dict.get('error', 'Error desconocido')}")
                    # Crear objeto con valores por defecto
                    resultado_liquidacion = type('obj', (object,), {
                        'puede_liquidar': False,
                        'valor_retencion': 0.0,
                        'concepto_aplicado': "Error en liquidación",
                        'tarifa_aplicada': 0.0,
                        'mensajes_error': [resultado_retefuente_dict.get('error', 'Error desconocido')]
                    })()
                
                # Convertir a formato compatible para respuesta
                resultado_analisis = {
                    "procesamiento_paralelo": False,
                    "aplica_estampilla_universidad": aplica_estampilla,
                    "impuestos_procesados": ["RETENCION_FUENTE"],
                    "exito": True,
                    "aplica_retencion": resultado_liquidacion.puede_liquidar,
                    "valor_total_factura": analisis_factura.valor_total or 0,
                    "iva_total": analisis_factura.iva or 0,
                    "valor_retencion": resultado_liquidacion.valor_retencion,
                    "concepto": resultado_liquidacion.concepto_aplicado,
                    "tarifa_retencion": resultado_liquidacion.tarifa_aplicada,
                    "observaciones": analisis_factura.observaciones + resultado_liquidacion.mensajes_error,
                    "es_facturacion_extranjera": es_facturacion_extranjera,
                    "naturaleza_tercero": analisis_factura.naturaleza_tercero.dict() if analisis_factura.naturaleza_tercero else None,
                    "estampilla_universidad": {
                        "aplica": aplica_estampilla,
                        "razon": "NIT administrativo no configurado para estampilla pro universidad nacional" if not aplica_estampilla else "No se procesó en modo individual"
                    },
                    "contribucion_obra_publica": {
                        "aplica": aplica_obra_publica,
                        "razon": "NIT administrativo no configurado para obra pública" if not aplica_obra_publica else "No se procesó en modo individual"
                    }
                }
        
        # 8. RESPUESTA FINAL
        tiempo_total = (datetime.now() - inicio_tiempo).total_seconds()
        
        respuesta_final = {
            **resultado_analisis,
            "tiempo_procesamiento_segundos": tiempo_total,
            "archivos_procesados": len(archivos),
            "nit_administrativo": nit_administrativo,
            "entidad_administrativa": nombre_entidad,
            "es_consorcio": es_consorcio,
            "documentos_clasificados": {
                nombre: info["categoria"] for nombre, info in documentos_clasificados.items()
            },
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "sistema": "integrado_retefuente_estampilla"
        }
        
        # Guardar respuesta final en JSON
        guardar_archivo_json(respuesta_final, "resultado_final")
        
        logger.info(f"🎉 Procesamiento completado exitosamente en {tiempo_total:.2f} segundos")
        logger.info(f"💾 Todos los archivos JSON guardados en Results/")
        logger.info(f"{'='*60}\n")
        
        return respuesta_final
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        tiempo_total = (datetime.now() - inicio_tiempo).total_seconds()
        logger.error(f"❌ Error procesando documentos: {e}")
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        
        # Determinar el tipo de error y mensaje user-friendly
        error_msg = str(e)
        user_message = "Error interno del servidor durante el procesamiento"
        error_type = "server_error"
        
        if "json" in error_msg.lower():
            user_message = "Error procesando respuesta de IA. Inténtalo de nuevo."
            error_type = "json_error"
        elif "timeout" in error_msg.lower():
            user_message = "La IA tardó demasiado en responder. Inténtalo de nuevo."
            error_type = "timeout_error"
        elif "api" in error_msg.lower() or "gemini" in error_msg.lower():
            user_message = "Error de conexión con servicios de IA. Verifica tu conexión."
            error_type = "api_error"
        elif "archivo" in error_msg.lower() or "file" in error_msg.lower():
            user_message = "Error procesando uno de los archivos. Verifica que estén en buen estado."
            error_type = "file_error"
        
        # Guardar error en JSON para debugging
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_msg,
            "user_message": user_message,
            "tiempo_procesamiento_segundos": tiempo_total,
            "archivos_procesados": len(archivos) if archivos else 0,
            "nit_administrativo": nit_administrativo,
            "traceback": traceback.format_exc()
        }
        guardar_archivo_json(error_data, "error_procesamiento")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error de procesamiento ({error_type})",
                "mensaje": user_message,
                "detalle_tecnico": error_msg,
                "tipo": error_type,
                "version": "2.0.0",
                "timestamp": datetime.now().isoformat()
            }
        )

# ===============================
# ENDPOINT PRINCIPAL INTEGRADO - SISTEMA PARALELO v2.0
# ===============================

@app.post("/api/procesar-facturas")
async def procesar_facturas_integrado(
    archivos: List[UploadFile] = File(...), 
    nit_administrativo: str = Form(...)
) -> JSONResponse:
    """
    🚀 ENDPOINT PRINCIPAL ÚNICO - SISTEMA INTEGRADO v2.0
    
    Procesa facturas y calcula múltiples impuestos en paralelo:
    ✅ RETENCIÓN EN LA FUENTE (funcionalidad original)
    ✅ ESTAMPILLA PRO UNIVERSIDAD NACIONAL (integrada)
    ✅ CONTRIBUCIÓN A OBRA PÚBLICA 5% (integrada) 
    ✅ IVA Y RETEIVA (nueva funcionalidad)
    ✅ PROCESAMIENTO PARALELO cuando múltiples impuestos aplican
    ✅ GUARDADO AUTOMÁTICO de JSONs en Results/
    
    Args:
        archivos: Lista de archivos (facturas, RUTs, anexos, contratos)
        nit_administrativo: NIT de la entidad administrativa
        
    Returns:
        JSONResponse: Resultado consolidado de todos los impuestos aplicables
    """
    logger.info(f"🚀 ENDPOINT PRINCIPAL INTEGRADO - Procesando {len(archivos)} archivos para NIT: {nit_administrativo}")
    
    try:
        # =================================
        # PASO 1: VALIDACIÓN Y CONFIGURACIÓN
        # =================================
        
        # Validar NIT administrativo
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
        
        logger.info(f"✅ NIT válido: {nombre_entidad}")
        logger.info(f"🏷️ Impuestos configurados: {impuestos_aplicables}")
        
        # Detectar automáticamente qué impuestos aplican
        deteccion_impuestos = detectar_impuestos_aplicables(nit_administrativo)
        aplica_retencion = "RETENCION_FUENTE" in impuestos_aplicables
        aplica_estampilla = deteccion_impuestos["aplica_estampilla_universidad"]
        aplica_obra_publica = deteccion_impuestos["aplica_contribucion_obra_publica"]
        aplica_iva = nit_aplica_iva_reteiva(nit_administrativo)  # ✅ NUEVA VALIDACIÓN IVA
        
        # Determinar estrategia de procesamiento
        impuestos_a_procesar = []
        if aplica_retencion:
            impuestos_a_procesar.append("RETENCION_FUENTE")
        if aplica_estampilla:
            impuestos_a_procesar.append("ESTAMPILLA_UNIVERSIDAD")
        if aplica_obra_publica:
            impuestos_a_procesar.append("CONTRIBUCION_OBRA_PUBLICA")
        if aplica_iva:
            impuestos_a_procesar.append("IVA_RETEIVA")  # ✅ NUEVO IMPUESTO
        
        procesamiento_paralelo = len(impuestos_a_procesar) > 1
        
        logger.info(f"⚡ Estrategia: {'PARALELO' if procesamiento_paralelo else 'INDIVIDUAL'}")
        logger.info(f"🏷️ Impuestos a procesar: {impuestos_a_procesar}")
        
        # =================================
        # PASO 2: EXTRACCIÓN HÍBRIDA DE TEXTO
        # =================================
        
        # Extraer texto de archivos con preprocesamiento Excel
        extractor = ProcesadorArchivos()
        textos_archivos_original = await extractor.procesar_multiples_archivos(archivos)
        
        # Preprocesamiento específico para Excel
        textos_archivos = {}
        for nombre_archivo, contenido_original in textos_archivos_original.items():
            # Si es Excel, aplicar preprocesamiento
            if nombre_archivo.lower().endswith(('.xlsx', '.xls')):
                try:
                    # Obtener contenido binario original del archivo
                    archivo_obj = next((arch for arch in archivos if arch.filename == nombre_archivo), None)
                    if archivo_obj:
                        await archivo_obj.seek(0)  # Resetear puntero
                        contenido_binario = await archivo_obj.read()
                        texto_preprocesado = preprocesar_excel_limpio(contenido_binario, nombre_archivo)
                        textos_archivos[nombre_archivo] = texto_preprocesado
                        logger.info(f"🧡 Excel preprocesado: {nombre_archivo}")
                    else:
                        textos_archivos[nombre_archivo] = contenido_original
                except Exception as e:
                    logger.warning(f"⚠️ Error preprocesando {nombre_archivo}: {e}")
                    textos_archivos[nombre_archivo] = contenido_original
            else:
                textos_archivos[nombre_archivo] = contenido_original
        
        logger.info(f"📄 Textos extraídos de {len(textos_archivos)} archivos")
        
        # =================================
        # PASO 3: CLASIFICACIÓN INTELIGENTE
        # =================================
        
        # Clasificar documentos y detectar consorcios/extranjera
        clasificador = ProcesadorGemini()
        clasificacion, es_consorcio, es_facturacion_extranjera = await clasificador.clasificar_documentos(textos_archivos)
        
        logger.info(f"🏷️ Documentos clasificados: {len(clasificacion)}")
        logger.info(f"🏢 Es consorcio: {es_consorcio}")
        logger.info(f"🌍 Facturación extranjera: {es_facturacion_extranjera}")
        
        # Estructurar documentos clasificados
        documentos_clasificados = {}
        for nombre_archivo, categoria in clasificacion.items():
            if nombre_archivo in textos_archivos:
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": textos_archivos[nombre_archivo]
                }
        
        # Guardar clasificación
        clasificacion_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "clasificacion": clasificacion,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "impuestos_aplicables": impuestos_a_procesar,
            "procesamiento_paralelo": procesamiento_paralelo
        }
        guardar_archivo_json(clasificacion_data, "clasificacion_documentos")
        
        # =================================
        # PASO 4A: PROCESAMIENTO PARALELO (MÚLTIPLES IMPUESTOS)
        # =================================
        
        if procesamiento_paralelo:
            logger.info(f"⚡ Iniciando procesamiento paralelo: {' + '.join(impuestos_a_procesar)}")
            
            # Crear tareas paralelas para análisis con Gemini
            tareas_analisis = []
            
            # Tarea 1: Análisis de Retefuente (si aplica)
            if aplica_retencion:
                if es_consorcio:
                    tarea_retefuente = clasificador.analizar_consorcio(documentos_clasificados, es_facturacion_extranjera)
                else:
                    tarea_retefuente = clasificador.analizar_factura(documentos_clasificados, es_facturacion_extranjera)
                tareas_analisis.append(("retefuente", tarea_retefuente))
            
            # Tarea 2: Análisis de Impuestos Especiales (si aplican)
            if aplica_estampilla or aplica_obra_publica:
                tarea_impuestos_especiales = clasificador.analizar_estampilla(documentos_clasificados)
                tareas_analisis.append(("impuestos_especiales", tarea_impuestos_especiales))
            
            # Tarea 3: Análisis de IVA (si aplica) - ✅ NUEVA TAREA
            if aplica_iva:
                tarea_iva = clasificador.analizar_iva(documentos_clasificados)
                tareas_analisis.append(("iva_reteiva", tarea_iva))
            
            # Ejecutar todas las tareas en paralelo
            logger.info(f"🔄 Ejecutando {len(tareas_analisis)} análisis paralelos con Gemini...")
            
            # Esperar todos los resultados
            resultados_analisis = {}
            try:
                
                tareas_asyncio = [tarea for _, tarea in tareas_analisis]
                resultados_brutos = await asyncio.gather(*tareas_asyncio, return_exceptions=True)
                
                #mapear resultados a sus nombres
                for i, (nombre_impuesto, tarea) in enumerate(tareas_analisis):
                    resultado = resultados_brutos[i]
                    if isinstance(resultado, Exception):
                        logger.error(f"❌ Error en análisis de {nombre_impuesto}: {resultado}")
                        resultados_analisis[nombre_impuesto] = {"error": str(resultado)}
                    else:
                        resultados_analisis[nombre_impuesto] = resultado.dict() if hasattr(resultado, 'dict') else resultado
                        logger.info(f"✅ Análisis de {nombre_impuesto} completado con éxito")
            except Exception as e:
                logger.error(f"❌ Error ejecutando análisis paralelo: {e}")
                raise HTTPException(status_code=500, detail=
                    f"Error ejecutando análisis paralelo : {str(e)}"
                )
           
            # Guardar análisis paralelo
            analisis_paralelo_data = {
                "timestamp": datetime.now().isoformat(),
                "procesamiento_paralelo": True,
                "impuestos_analizados": list(resultados_analisis.keys()),
                "resultados_analisis": resultados_analisis
            }
            guardar_archivo_json(analisis_paralelo_data, "analisis_paralelo")
            
            # =================================
            # PASO 5A: LIQUIDACIÓN PARALELA
            # =================================
            
            logger.info(f"💰 Iniciando liquidación paralela de impuestos...")
            
            resultado_final = {
                "procesamiento_paralelo": True,
                "impuestos_procesados": impuestos_a_procesar,
                "nit_administrativo": nit_administrativo,
                "nombre_entidad": nombre_entidad,
                "timestamp": datetime.now().isoformat(),
                "version": "2.0.0"
            }
            
            # Liquidar Retefuente
            if "retefuente" in resultados_analisis and aplica_retencion:
                try:
                    liquidador_retencion = LiquidadorRetencion()
                    if es_consorcio:
                        resultado_retefuente = resultados_analisis["retefuente"]  # Ya viene liquidado del consorcio
                    else:
                        analisis_factura = resultados_analisis["retefuente"]
                        resultado_retefuente = liquidador_retencion.liquidar_factura(analisis_factura, nit_administrativo)
                    
                    # Convertir objeto ResultadoLiquidacion a diccionario para compatibilidad
                    if hasattr(resultado_retefuente, 'valor_retencion'):
                        resultado_final["retefuente"] = {
                            "aplica": resultado_retefuente.puede_liquidar,
                            "valor_retencion": resultado_retefuente.valor_retencion,
                            "concepto": resultado_retefuente.concepto_aplicado,
                            "tarifa_retencion": resultado_retefuente.tarifa_aplicada,
                            "valor_base": resultado_retefuente.valor_base_retencion,
                            "fecha_calculo": resultado_retefuente.fecha_calculo,
                            "mensajes_error": resultado_retefuente.mensajes_error
                        }
                        logger.info(f"✅ Retefuente liquidada: ${resultado_retefuente.valor_retencion:,.2f}")
                    else:
                        # Es un diccionario (resultado de consorcio)
                        resultado_final["retefuente"] = resultado_retefuente
                        logger.info(f"✅ Retefuente liquidada: ${resultado_retefuente.get('valor_retencion', 0):,.2f}")
                except Exception as e:
                    logger.error(f"❌ Error liquidando retefuente: {e}")
                    resultado_final["retefuente"] = {"error": str(e), "aplica": False}
            
            # Liquidar Impuestos Especiales (Estampilla + Obra Pública)
            if "impuestos_especiales" in resultados_analisis and (aplica_estampilla or aplica_obra_publica):
                try:
                    from Liquidador.liquidador_estampilla import LiquidadorEstampilla
                    liquidador_estampilla = LiquidadorEstampilla()
                    
                    analisis_especiales = resultados_analisis["impuestos_especiales"]
                    resultado_estampilla = liquidador_estampilla.liquidar_integrado(analisis_especiales, nit_administrativo)
                    
                    # Separar resultados por impuesto
                    if aplica_estampilla and "estampilla_universidad" in resultado_estampilla:
                        resultado_final["estampilla_universidad"] = resultado_estampilla["estampilla_universidad"]
                        logger.info(f"✅ Estampilla liquidada: ${resultado_estampilla['estampilla_universidad'].get('valor_estampilla', 0):,.2f}")
                    
                    if aplica_obra_publica and "contribucion_obra_publica" in resultado_estampilla:
                        resultado_final["contribucion_obra_publica"] = resultado_estampilla["contribucion_obra_publica"]
                        logger.info(f"✅ Obra pública liquidada: ${resultado_estampilla['contribucion_obra_publica'].get('valor_contribucion', 0):,.2f}")
                        
                except Exception as e:
                    logger.error(f"❌ Error liquidando impuestos especiales: {e}")
                    if aplica_estampilla:
                        resultado_final["estampilla_universidad"] = {"error": str(e), "aplica": False}
                    if aplica_obra_publica:
                        resultado_final["contribucion_obra_publica"] = {"error": str(e), "aplica": False}
            
            # Liquidar IVA y ReteIVA - ✅ NUEVA LIQUIDACIÓN
            if "iva_reteiva" in resultados_analisis and aplica_iva:
                try:
                    from Liquidador.liquidador_iva import LiquidadorIVA
                    liquidador_iva = LiquidadorIVA()
                    
                    analisis_iva = resultados_analisis["iva_reteiva"]
                    resultado_iva_completo = liquidador_iva.liquidar_iva_completo(analisis_iva, nit_administrativo)
                    
                    # Convertir a formato compatible
                    from Liquidador.liquidador_iva import convertir_resultado_a_dict
                    resultado_final["iva_reteiva"] = convertir_resultado_a_dict(resultado_iva_completo)
                    
                    logger.info(f"✅ IVA identificado: ${resultado_iva_completo.valor_iva_identificado:,.2f}")
                    logger.info(f"✅ ReteIVA liquidada: ${resultado_iva_completo.valor_reteiva:,.2f}")
                    
                except Exception as e:
                    logger.error(f"❌ Error liquidando IVA/ReteIVA: {e}")
                    resultado_final["iva_reteiva"] = {"error": str(e), "aplica": False}
            
            # Calcular resumen total
            valor_total_impuestos = 0.0
            
            if "retefuente" in resultado_final and isinstance(resultado_final["retefuente"], dict):
                valor_total_impuestos += resultado_final["retefuente"].get("valor_retencion", 0)
            
            if "estampilla_universidad" in resultado_final and isinstance(resultado_final["estampilla_universidad"], dict):
                valor_total_impuestos += resultado_final["estampilla_universidad"].get("valor_estampilla", 0)
            
            if "contribucion_obra_publica" in resultado_final and isinstance(resultado_final["contribucion_obra_publica"], dict):
                valor_total_impuestos += resultado_final["contribucion_obra_publica"].get("valor_contribucion", 0)
            
            if "iva_reteiva" in resultado_final and isinstance(resultado_final["iva_reteiva"], dict):
                valor_total_impuestos += resultado_final["iva_reteiva"].get("valor_reteiva", 0)
            
            resultado_final["resumen_total"] = {
                "valor_total_impuestos": valor_total_impuestos,
                "impuestos_liquidados": [imp for imp in impuestos_a_procesar if imp.lower().replace("_", "") in [k.lower().replace("_", "") for k in resultado_final.keys()]],
                "procesamiento_exitoso": True
            }
            
            logger.info(f"💰 Total impuestos calculados: ${valor_total_impuestos:,.2f}")
        
        # =================================
        # PASO 4B: PROCESAMIENTO INDIVIDUAL (SOLO UN IMPUESTO)
        # =================================
        
        else:
            logger.info(f"📄 Procesamiento individual: {impuestos_a_procesar[0]}")
            
            impuesto_unico = impuestos_a_procesar[0]
            
            if impuesto_unico == "RETENCION_FUENTE":
                # Flujo original de retefuente mantenido
                if es_consorcio:
                    analisis_factura = await clasificador.analizar_consorcio(documentos_clasificados, es_facturacion_extranjera)
                else:
                    analisis_factura = await clasificador.analizar_factura(documentos_clasificados, es_facturacion_extranjera)
                
                liquidador_retencion = LiquidadorRetencion()
                if es_consorcio:
                    resultado_liquidacion = analisis_factura  # Ya viene liquidado como dict
                    resultado_final = {
                        "procesamiento_paralelo": False,
                        "impuestos_procesados": ["RETENCION_FUENTE"],
                        **resultado_liquidacion,
                        "estampilla_universidad": {"aplica": False, "razon": "NIT no configurado para estampilla"},
                        "contribucion_obra_publica": {"aplica": False, "razon": "NIT no configurado para obra pública"},
                        "iva_reteiva": {"aplica": False, "razon": "NIT no configurado para IVA/ReteIVA"}
                    }
                else:
                    resultado_liquidacion = liquidador_retencion.liquidar_factura(analisis_factura, nit_administrativo)
                    
                    # Convertir objeto ResultadoLiquidacion a dict
                    resultado_final = {
                        "procesamiento_paralelo": False,
                        "impuestos_procesados": ["RETENCION_FUENTE"],
                        "aplica_retencion": resultado_liquidacion.puede_liquidar,
                        "valor_retencion": resultado_liquidacion.valor_retencion,
                        "concepto": resultado_liquidacion.concepto_aplicado,
                        "tarifa_retencion": resultado_liquidacion.tarifa_aplicada,
                        "valor_base_retencion": resultado_liquidacion.valor_base_retencion,
                        "fecha_calculo": resultado_liquidacion.fecha_calculo,
                        "mensajes_error": resultado_liquidacion.mensajes_error,
                        "retefuente": {
                            "aplica": resultado_liquidacion.puede_liquidar,
                            "valor_retencion": resultado_liquidacion.valor_retencion,
                            "concepto": resultado_liquidacion.concepto_aplicado,
                            "tarifa_retencion": resultado_liquidacion.tarifa_aplicada
                        },
                        "estampilla_universidad": {"aplica": False, "razon": "NIT no configurado para estampilla"},
                        "contribucion_obra_publica": {"aplica": False, "razon": "NIT no configurado para obra pública"},
                        "iva_reteiva": {"aplica": False, "razon": "NIT no configurado para IVA/ReteIVA"}
                    }
            
            elif impuesto_unico == "IVA_RETEIVA":
                # Procesamiento individual de IVA - ✅ NUEVO FLUJO
                analisis_iva = await clasificador.analizar_iva(documentos_clasificados)
                
                from Liquidador.liquidador_iva import LiquidadorIVA, convertir_resultado_a_dict
                liquidador_iva = LiquidadorIVA()
                resultado_iva_completo = liquidador_iva.liquidar_iva_completo(analisis_iva, nit_administrativo)
                
                resultado_final = {
                    "procesamiento_paralelo": False,
                    "impuestos_procesados": ["IVA_RETEIVA"],
                    "iva_reteiva": convertir_resultado_a_dict(resultado_iva_completo),
                    "retefuente": {"aplica": False, "razon": "NIT no configurado para retefuente"},
                    "estampilla_universidad": {"aplica": False, "razon": "NIT no configurado para estampilla"},
                    "contribucion_obra_publica": {"aplica": False, "razon": "NIT no configurado para obra pública"}
                }
            
            else:
                # Otros impuestos individuales (estampilla, obra pública)
                analisis_especiales = await clasificador.analizar_estampilla(documentos_clasificados)
                
                from Liquidador.liquidador_estampilla import LiquidadorEstampilla
                liquidador_estampilla = LiquidadorEstampilla()
                resultado_estampilla = liquidador_estampilla.liquidar_integrado(analisis_especiales, nit_administrativo)
                
                resultado_final = {
                    "procesamiento_paralelo": False,
                    "impuestos_procesados": [impuesto_unico],
                    **resultado_estampilla,
                    "retefuente": {"aplica": False, "razon": "NIT no configurado para retefuente"},
                    "iva_reteiva": {"aplica": False, "razon": "NIT no configurado para IVA/ReteIVA"}
                }
        
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
            "version_sistema": "2.0.0",
            "modulos_utilizados": ["Extraccion", "Clasificador", "Liquidador"]
        })
        
        # Guardar resultado final completo
        guardar_archivo_json(resultado_final, "resultado_final")
        
        # Log final de éxito
        logger.info(f"✅ Procesamiento completado exitosamente")
        logger.info(f"🏷️ Impuestos procesados: {resultado_final.get('impuestos_procesados', [])}")
        if 'resumen_total' in resultado_final:
            logger.info(f"💰 Total impuestos: ${resultado_final['resumen_total']['valor_total_impuestos']:,.2f}")
        
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
        logger.error(f"❌ {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Guardar error para debugging
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "error_mensaje": error_msg,
            "error_tipo": type(e).__name__,
            "traceback": traceback.format_exc(),
            "archivos_recibidos": [archivo.filename for archivo in archivos],
            "version": "2.0.0"
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
                "version": "2.0.0",
                "timestamp": datetime.now().isoformat()
            }
        )

# ===============================
# ENDPOINTS ADICIONALES
# ===============================

@app.get("/health")
async def health_check():
    """Verificar estado del sistema y módulos"""
    # Verificar configuración de APIs
    vision_disponible = bool(GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS))
    
    # Verificar módulos
    try:
        # Intentar instanciar cada módulo
        extractor = ProcesadorArchivos()
        clasificador = ProcesadorGemini()
        liquidador = LiquidadorRetencion()
        
        modulos_status = {
            "extractor": "OK",
            "clasificador": "OK", 
            "liquidador": "OK"
        }
    except Exception as e:
        modulos_status = {
            "extractor": "ERROR",
            "clasificador": "ERROR",
            "liquidador": "ERROR",
            "error": str(e)
        }
    
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "arquitectura": "modular",
        "sistema": "integrado_retefuente_estampilla",
        "apis": {
            "gemini_configurado": bool(GEMINI_API_KEY),
            "vision_configurado": vision_disponible
        },
        "modulos": modulos_status,
        "conceptos_cargados": len(CONCEPTOS_RETEFUENTE),
        "carpetas": {
            "clasificador": os.path.exists("Clasificador"),
            "liquidador": os.path.exists("Liquidador"),
            "extraccion": os.path.exists("Extraccion"),
            "static": os.path.exists("Static"),
            "results": os.path.exists("Results")
        }
    }

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
        "version": "2.0.0"
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
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo NITs disponibles: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error obteniendo NITs",
                "mensaje": str(e),
                "version": "2.0.0"
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
            "version": "2.0.0",
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

@app.get("/api/estructura")
async def obtener_estructura():
    """Obtener información sobre la estructura modular del proyecto"""
    
    def verificar_modulo(carpeta: str) -> Dict[str, Any]:
        """Verifica el estado de un módulo"""
        ruta = Path(carpeta)
        if not ruta.exists():
            return {"existe": False}
        
        archivos = list(ruta.glob("*.py"))
        return {
            "existe": True,
            "archivos": [f.name for f in archivos],
            "total_archivos": len(archivos)
        }
    
    return {
        "version": "2.0.0",
        "arquitectura": "modular",
        "sistema": "integrado_retefuente_estampilla",
        "descripcion": "Sistema dividido en módulos especializados con procesamiento paralelo de impuestos",
        "modulos": {
            "Clasificador": {
                **verificar_modulo("Clasificador"),
                "funcion": "Clasificación y análisis de documentos con Gemini"
            },
            "Liquidador": {
                **verificar_modulo("Liquidador"),
                "funcion": "Cálculo de retenciones y estampillas según normativa colombiana"
            },
            "Extraccion": {
                **verificar_modulo("Extraccion"),
                "funcion": "Extracción de texto de PDFs, imágenes, Excel, Word"
            },
            "Static": {
                **verificar_modulo("Static"),
                "funcion": "Frontend y archivos estáticos"
            },
            "Results": {
                "existe": os.path.exists("Results"),
                "funcion": "Almacenamiento de resultados por fecha con JSONs organizados",
                "carpetas_fecha": [d.name for d in Path("Results").iterdir() if d.is_dir()] if os.path.exists("Results") else []
            }
        },
        "archivos_principales": {
            "main.py": "Orquestador principal con sistema integrado",
            "config.py": "Configuración global incluyendo estampilla",
            ".env": "Variables de entorno"
        },
        "flujo_procesamiento": [
            "1. Extraccion/: Extraer texto de archivos",
            "2. Clasificador/: Clasificar documentos", 
            "3. Clasificador/: Análisis paralelo (retefuente + estampilla)",
            "4. Liquidador/: Calcular impuestos en paralelo",
            "5. Results/: Guardar JSONs organizados por fecha"
        ]
    }

@app.post("/api/prueba-simple")
async def prueba_simple(nit_administrativo: Optional[str] = Form(None)):
    """Endpoint de prueba simple SIN archivos"""
    logger.info(f"🔥 PRUEBA SIMPLE: Recibido NIT: {nit_administrativo}")
    return {
        "success": True,
        "mensaje": "POST sin archivos funciona - Sistema integrado",
        "nit_recibido": nit_administrativo,
        "version": "2.0.0",
        "sistema": "integrado_retefuente_estampilla",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/diagnostico")
async def diagnostico_completo():
    """Endpoint de diagnóstico completo para verificar todos los componentes del sistema"""
    diagnostico = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
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
                
                # ✅ VERIFICAR ESTAMPILLA UNIVERSIDAD
                aplica_estampilla = nit_aplica_estampilla_universidad(primer_nit)
                config_status["estampilla_universidad"] = {
                    "status": "OK",
                    "aplica_estampilla": aplica_estampilla,
                    "mensaje": f"NIT {primer_nit} {'SÍ' if aplica_estampilla else 'NO'} aplica estampilla universidad"
                }
                
                # 🏗️ VERIFICAR CONTRIBUCIÓN OBRA PÚBLICA
                aplica_obra_publica = nit_aplica_contribucion_obra_publica(primer_nit)
                config_status["contribucion_obra_publica"] = {
                    "status": "OK",
                    "aplica_obra_publica": aplica_obra_publica,
                    "mensaje": f"NIT {primer_nit} {'SÍ' if aplica_obra_publica else 'NO'} aplica contribución obra pública 5%"
                }
                
                # ⚡ VERIFICAR DETECCIÓN AUTOMÁTICA INTEGRADA
                try:
                    deteccion_auto = detectar_impuestos_aplicables(primer_nit)
                    config_status["deteccion_automatica"] = {
                        "status": "OK",
                        "impuestos_detectados": deteccion_auto['impuestos_aplicables'],
                        "procesamiento_paralelo": deteccion_auto['procesamiento_paralelo'],
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
