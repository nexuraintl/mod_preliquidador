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

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# FastAPI y dependencias web
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuración de logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
# IMPORTAR MÓDULOS LOCALES
# ===============================

# Importar clases desde módulos
from Clasificador import ProcesadorGemini
from Liquidador import LiquidadorRetencion
from Extraccion import ProcesadorArchivos

# Cargar configuración global
from config import inicializar_configuracion, obtener_nits_disponibles, validar_nit_administrativo, nit_aplica_retencion_fuente

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
    deducciones_identificadas: DeduccionesArticulo383 = DeduccionesArticulo383()
    calculo: CalculoArticulo383 = CalculoArticulo383()

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
# API FASTAPI
# ===============================

app = FastAPI(
    title="Preliquidador de Retefuente - Colombia",
    description="Sistema automatizado para calcular retención en la fuente con arquitectura modular",
    version="2.0.0"
)

# Servir archivos estáticos desde la carpeta Static
app.mount("/static", StaticFiles(directory="Static"), name="static")

@app.get("/")
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
    Endpoint principal para procesar documentos de facturas.
    
    NUEVO: Maneja automáticamente facturación nacional y extranjera.
    """
    inicio_tiempo = datetime.now()
    logger.info(f"\n{'='*50}")
    logger.info(f"📄 PROCESANDO {len(archivos)} ARCHIVOS")
    logger.info(f"{'='*50}")
    
    try:
        # 1. VALIDAR NIT ADMINISTRATIVO
        es_valido, nombre_entidad, impuestos_aplicables = validar_nit_administrativo(nit_administrativo)
        if not es_valido:
            raise HTTPException(
                status_code=400, 
                detail=f"NIT administrativo '{nit_administrativo}' no válido"
            )
        
        aplica_retencion_fuente = nit_aplica_retencion_fuente(nit_administrativo)
        if not aplica_retencion_fuente:
            return {
                "mensaje": "NO aplica retención en la fuente",
                "razon": f"El NIT {nit_administrativo} ({nombre_entidad}) no tiene retención en la fuente configurada",
                "nit_administrativo": nit_administrativo,
                "entidad": nombre_entidad,
                "impuestos_aplicables": impuestos_aplicables
            }
        
        logger.info(f"✅ NIT válido: {nombre_entidad}")
        
        # 2. EXTRAER TEXTO DE ARCHIVOS (EXTRACTOR ORIGINAL + PREPROCESAMIENTO EXCEL)
        logger.info(f"🔍 Extrayendo texto de {len(archivos)} archivos...")
        extractor = ProcesadorArchivos()
        
        # PASO 2A: Usar extractor original con procesar_multiples_archivos (FUNCIONA)
        logger.info("🔍 Usando extractor original para todos los archivos...")
        textos_archivos_original = {}
        
        # Crear una lista temporal de archivos para el extractor
        archivos_para_extractor = []
        for archivo in archivos:
            # Resetear posición del archivo
            await archivo.seek(0)
            archivos_para_extractor.append(archivo)
        
        try:
            # Usar la función que sabemos que funciona
            textos_archivos_original = await extractor.procesar_multiples_archivos(archivos_para_extractor)
            logger.info(f"✅ Extractor original completó procesamiento de {len(textos_archivos_original)} archivos")
        except Exception as e:
            logger.error(f"❌ Error en extractor original: {e}")
            # Fallback manual si falla el extractor
            for archivo in archivos:
                textos_archivos_original[archivo.filename] = f"ERROR EXTRACTOR: {str(e)}"
        
        # PASO 2B: Aplicar preprocesamiento SOLO a Excel exitosos
        logger.info("🧹 Aplicando preprocesamiento a archivos Excel exitosos...")
        textos_archivos = {}
        archivos_excel_preprocesados = 0
        
        for archivo in archivos:
            nombre_archivo = archivo.filename
            
            if nombre_archivo in textos_archivos_original:
                texto_original = textos_archivos_original[nombre_archivo]
                
                # 🧹 PREPROCESAMIENTO EXCEL (solo si es Excel exitoso)
                if (nombre_archivo.lower().endswith(('.xlsx', '.xls')) and 
                    not texto_original.startswith("ERROR")):
                    
                    logger.info(f"📊 Aplicando preprocesamiento a Excel: {nombre_archivo}")
                    try:
                        # Re-leer el archivo para preprocesamiento
                        await archivo.seek(0)  # Resetear posición
                        contenido = await archivo.read()
                        texto_preprocesado = preprocesar_excel_limpio(contenido, nombre_archivo)
                        
                        # ✅ USAR TEXTO PREPROCESADO si es exitoso
                        if not texto_preprocesado.startswith("Error"):
                            textos_archivos[nombre_archivo] = texto_preprocesado
                            archivos_excel_preprocesados += 1
                            logger.info(f"✅ Excel preprocesado exitosamente: {nombre_archivo}")
                            logger.info(f"📊 Enviando a Gemini: TEXTO PREPROCESADO ({len(texto_preprocesado)} caracteres)")
                        else:
                            # 🔄 FALLBACK: usar texto original si falla preprocesamiento
                            textos_archivos[nombre_archivo] = texto_original
                            logger.warning(f"⚠️ Preprocesamiento falló, usando original: {nombre_archivo}")
                            logger.warning(f"📌 Enviando a Gemini: TEXTO ORIGINAL ({len(texto_original)} caracteres)")
                            
                    except Exception as e:
                        # 🔄 FALLBACK SEGURO: usar texto original
                        logger.warning(f"⚠️ Error en preprocesamiento Excel {nombre_archivo}: {e}")
                        logger.info(f"📋 Usando texto original para {nombre_archivo}")
                        textos_archivos[nombre_archivo] = texto_original
                else:
                    # 📄 Para no-Excel o archivos con error, usar resultado original
                    textos_archivos[nombre_archivo] = texto_original
                    logger.info(f"📄 Archivo no-Excel: {nombre_archivo} - Enviando texto original ({len(texto_original)} caracteres)")
                    
            else:
                # No debería pasar, pero por seguridad
                textos_archivos[nombre_archivo] = "ERROR: Archivo no procesado"
                logger.error(f"❌ Archivo {nombre_archivo} no encontrado en resultados originales")
        
        logger.info(f"🧹 Preprocesamiento aplicado a {archivos_excel_preprocesados} archivos Excel")
        
        # 3. CLASIFICAR DOCUMENTOS Y DETECTAR TIPO
        logger.info(f"🤖 Clasificando documentos con Gemini...")
        clasificador = ProcesadorGemini()
        
        # NUEVA FUNCIONALIDAD: La función ahora retorna 3 valores
        clasificacion, es_consorcio, es_facturacion_extranjera = await clasificador.clasificar_documentos(textos_archivos)
        
        logger.info(f"📅 Clasificación completada:")
        for archivo, categoria in clasificacion.items():
            logger.info(f"  - {archivo}: {categoria}")
        logger.info(f"🏢 Es consorcio: {es_consorcio}")
        logger.info(f"🌍 Es facturación extranjera: {es_facturacion_extranjera}")
        
        # 4. PREPARAR DOCUMENTOS CLASIFICADOS
        documentos_clasificados = {}
        for nombre_archivo, categoria in clasificacion.items():
            documentos_clasificados[nombre_archivo] = {
                "categoria": categoria,
                "texto": textos_archivos.get(nombre_archivo, "")
            }
        
        # 5. ANALIZAR FACTURAS SEGUN TIPO
        if es_consorcio:
            logger.info(f"🏢 Procesando como CONSORCIO {'EXTRANJERO' if es_facturacion_extranjera else 'NACIONAL'}")
            # NUEVA FUNCIONALIDAD: Pasar parámetro de facturación extranjera
            resultado_analisis = await clasificador.analizar_consorcio(
                documentos_clasificados, es_facturacion_extranjera
            )
        else:
            logger.info(f"🏢 Procesando como EMPRESA {'EXTRANJERA' if es_facturacion_extranjera else 'NACIONAL'}")
            # NUEVA FUNCIONALIDAD: Pasar parámetro de facturación extranjera
            analisis_factura = await clasificador.analizar_factura(
                documentos_clasificados, es_facturacion_extranjera
            )
            
            # 6. LIQUIDAR RETENCIÓN
            logger.info(f"💰 Liquidando retención...")
            liquidador = LiquidadorRetencion()
            
            if es_facturacion_extranjera:
                # NUEVA FUNCIONALIDAD: Liquidación para facturación extranjera
                resultado_liquidacion = liquidador.liquidar_factura_extranjera(
                    analisis_factura, nit_administrativo
                )
            else:
                # Liquidación normal para facturación nacional
                resultado_liquidacion = liquidador.liquidar_factura(
                    analisis_factura, nit_administrativo
                )
            
            # Convertir a formato compatible para respuesta
            resultado_analisis = {
                "aplica_retencion": resultado_liquidacion.puede_liquidar,
                "valor_total_factura": analisis_factura.valor_total or 0,
                "iva_total": analisis_factura.iva or 0,
                "valor_retencion": resultado_liquidacion.valor_retencion,
                "concepto": resultado_liquidacion.concepto_aplicado,
                "tarifa_retencion": resultado_liquidacion.tarifa_aplicada,
                "observaciones": analisis_factura.observaciones + resultado_liquidacion.mensajes_error,
                "es_facturacion_extranjera": es_facturacion_extranjera,
                "naturaleza_tercero": analisis_factura.naturaleza_tercero.dict() if analisis_factura.naturaleza_tercero else None
            }
        
        # 7. RESPUESTA FINAL
        tiempo_total = (datetime.now() - inicio_tiempo).total_seconds()
        
        respuesta_final = {
            "exito": True,
            "tiempo_procesamiento_segundos": tiempo_total,
            "archivos_procesados": len(archivos),
            "nit_administrativo": nit_administrativo,
            "entidad_administrativa": nombre_entidad,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,  # NUEVO CAMPO
            "documentos_clasificados": {
                nombre: info["categoria"] for nombre, info in documentos_clasificados.items()
            },
            **resultado_analisis
        }
        
        logger.info(f"✅ Procesamiento completado en {tiempo_total:.2f} segundos")
        logger.info(f"{'='*50}\n")
        
        return respuesta_final
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        tiempo_total = (datetime.now() - inicio_tiempo).total_seconds()
        logger.error(f"❌ Error procesando documentos: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            "exito": False,
            "error": str(e),
            "tiempo_procesamiento_segundos": tiempo_total,
            "archivos_procesados": len(archivos) if archivos else 0,
            "mensaje": "Error interno del servidor durante el procesamiento"
        }

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

@app.post("/api/procesar-facturas")
async def procesar_facturas(
    archivos: List[UploadFile] = File(...),
    nit_administrativo: Optional[str] = Form(None)
):
    """
    Endpoint principal para procesar facturas usando arquitectura modular.
    
    FLUJO:
    0. Validación: Verificar NIT administrativo y impuestos aplicables
    1. Extraccion/: Extraer texto de archivos
    2. Clasificador/: Clasificar documentos con Gemini
    3. Clasificador/: Analizar factura con Gemini
    4. Liquidador/: Calcular retención según normativa
    
    Args:
        archivos: Lista de archivos a procesar (facturas, RUT, etc.)
        nit_administrativo: (Opcional) NIT de la entidad que realiza la liquidación.
                           Si no se especifica, usa el primer NIT disponible.
                           
    COMPATIBILIDAD: Funciona con frontends antiguos que no envían NIT.
    """
    
    try:
        logger.info(f"🚀 Iniciando procesamiento de {len(archivos)} archivos con arquitectura modular")
        
        # VALIDACIÓN DE NIT ADMINISTRATIVO
        nit_por_defecto = False
        if nit_administrativo is None:
            # COMPATIBILIDAD: Si no se envía NIT, usar el primero disponible
            nits_disponibles = obtener_nits_disponibles()
            for nit, datos in nits_disponibles.items():
                if "RETENCION_FUENTE" in datos["impuestos_aplicables"]:
                    nit_administrativo = nit
                    nit_por_defecto = True
                    logger.info(f"⚠️ NIT no especificado. Usando por defecto: {nit_administrativo}")
                    break
            
            if nit_administrativo is None:
                raise ValueError("No se encontró ningún NIT configurado con retención en la fuente")
        
        logger.info(f"🔍 Validando NIT administrativo: {nit_administrativo}")
        es_valido, nombre_entidad, impuestos_aplicables = validar_nit_administrativo(nit_administrativo)
        
        if not es_valido:
            raise ValueError(f"NIT administrativo '{nit_administrativo}' no existe en la configuración")
        
        # Verificar si aplica retención en la fuente
        if not nit_aplica_retencion_fuente(nit_administrativo):
            raise ValueError(f"El NIT '{nit_administrativo}' no tiene configurada la retención en la fuente")
        
        logger.info(f"✅ NIT validado: {nombre_entidad}")
        logger.info(f"📋 Impuestos aplicables: {', '.join(impuestos_aplicables)}")
        logger.info(f"💰 Procesando retención en la fuente (único impuesto implementado)")
        
        # PASO 1: EXTRACCIÓN DE TEXTO (EXTRACTOR ORIGINAL + PREPROCESAMIENTO EXCEL)
        logger.info("📄 Paso 1: Extrayendo texto de archivos (híbrido)...")
        extractor = ProcesadorArchivos()
        
        try:
            # PASO 1A: Usar extractor original (FUNCIONA para todos los tipos)
            logger.info("🔍 Usando extractor original para todos los archivos...")
            textos_archivos_original = await asyncio.wait_for(
                extractor.procesar_multiples_archivos(archivos),
                timeout=60.0  # 60 segundos para extracción
            )
            
            # PASO 1B: Aplicar preprocesamiento SOLO a Excel exitosos
            logger.info("🧹 Aplicando preprocesamiento a archivos Excel exitosos...")
            textos_archivos = {}
            archivos_excel_preprocesados = 0
            
            for archivo in archivos:
                nombre_archivo = archivo.filename
                
                if nombre_archivo in textos_archivos_original:
                    texto_original = textos_archivos_original[nombre_archivo]
                    
                    # 📊 PREPROCESAMIENTO EXCEL (solo si es Excel exitoso)
                    if (nombre_archivo.lower().endswith(('.xlsx', '.xls')) and 
                        not texto_original.startswith("ERROR")):
                        
                        logger.info(f"📊 Aplicando preprocesamiento a Excel: {nombre_archivo}")
                        try:
                            # Re-leer el archivo para preprocesamiento
                            await archivo.seek(0)  # Resetear posición
                            contenido = await archivo.read()
                            texto_preprocesado = preprocesar_excel_limpio(contenido, nombre_archivo)
                            
                            # ✅ USAR TEXTO PREPROCESADO si es exitoso
                            if not texto_preprocesado.startswith("Error"):
                                textos_archivos[nombre_archivo] = texto_preprocesado
                                archivos_excel_preprocesados += 1
                                logger.info(f"✅ Excel preprocesado exitosamente: {nombre_archivo}")
                            else:
                                # 🔄 FALLBACK: usar texto original si falla preprocesamiento
                                textos_archivos[nombre_archivo] = texto_original
                                logger.warning(f"⚠️ Preprocesamiento falló, usando original: {nombre_archivo}")
                                
                        except Exception as e:
                            # 🔄 FALLBACK SEGURO: usar texto original
                            logger.warning(f"⚠️ Error en preprocesamiento Excel {nombre_archivo}: {e}")
                            logger.info(f"📋 Usando texto original para {nombre_archivo}")
                            textos_archivos[nombre_archivo] = texto_original
                    else:
                        # 📄 Para no-Excel o archivos con error, usar resultado original
                        textos_archivos[nombre_archivo] = texto_original
                        
                else:
                    # No debería pasar, pero por seguridad
                    textos_archivos[nombre_archivo] = "ERROR: Archivo no procesado"
                    logger.error(f"❌ Archivo {nombre_archivo} no encontrado en resultados originales")
            
            logger.info(f"🧹 Preprocesamiento aplicado a {archivos_excel_preprocesados} archivos Excel")
                    
        except asyncio.TimeoutError:
            logger.error("⏰ TIMEOUT: Extracción de texto tardó más de 60 segundos")
            raise ValueError("Timeout en extracción de texto. Los archivos tardaron demasiado en procesarse.")
        except Exception as e:
            logger.error(f"❌ ERROR en extracción: {str(e)}")
            raise ValueError(f"Error extrayendo texto de archivos: {str(e)}")
        
        # Verificar que se extrajo texto de al menos un archivo
        archivos_exitosos = {k: v for k, v in textos_archivos.items() if not v.startswith("ERROR")}
        if not archivos_exitosos:
            raise ValueError("No se pudo extraer texto de ningún archivo")
        
        logger.info(f"✅ Extracción completada: {len(archivos_exitosos)}/{len(archivos)} archivos exitosos")
        logger.info(f"🧹 Preprocesamiento Excel híbrido aplicado correctamente")
        
        # PASO 2: CLASIFICACIÓN DE DOCUMENTOS Y DETECCIÓN DE CONSORCIOS
        logger.info("🏷️ Paso 2: Clasificando documentos y detectando consorcios con Gemini...")
        clasificador = ProcesadorGemini()
        
        try:
            # TIMEOUT Y RETRY PARA GEMINI
            clasificacion, es_consorcio, es_facturacion_extranjera = await asyncio.wait_for(
                clasificador.clasificar_documentos(archivos_exitosos),
                timeout=60.0  # 60 segundos timeout
            )
            logger.info(f"✅ Clasificación completada: {len(clasificacion)} documentos clasificados")
            logger.info(f"🏢 Consorcio detectado: {es_consorcio}")
            logger.info(f"🌍 Facturación extranjera detectada: {es_facturacion_extranjera}")
            
        except asyncio.TimeoutError:
            logger.error("⏰ TIMEOUT: Gemini tardó más de 60 segundos en clasificar")
            raise ValueError("Timeout en clasificación de documentos. La IA tardó demasiado en responder.")
        except Exception as e:
            logger.error(f"❌ ERROR en clasificación Gemini: {str(e)}")
            raise ValueError(f"Error en clasificación de documentos: {str(e)}")
        
        # PASO 3: PREPARAR DOCUMENTOS PARA ANÁLISIS
        logger.info("📋 Paso 3: Preparando documentos clasificados...")
        documentos_clasificados = {}
        for nombre_archivo, categoria in clasificacion.items():
            if nombre_archivo in archivos_exitosos:
                documentos_clasificados[nombre_archivo] = {
                    "categoria": categoria,
                    "texto": archivos_exitosos[nombre_archivo]
                }
        
        # PASO 4: ANÁLISIS CON GEMINI (FACTURA NORMAL O CONSORCIO)
        if es_consorcio:
            logger.info("🏢 Paso 4: Analizando CONSORCIO con Gemini...")
            try:
                resultado_analisis = await asyncio.wait_for(
                    clasificador.analizar_consorcio(documentos_clasificados, es_facturacion_extranjera),
                    timeout=120.0  # 2 minutos para consorcios (más complejo)
                )
                logger.info(f"✅ Análisis de consorcio completado: {resultado_analisis.get('consorcio_info', {}).get('total_consorciados', 0)} consorciados")
            except asyncio.TimeoutError:
                logger.error("⏰ TIMEOUT: Gemini tardó más de 2 minutos analizando consorcio")
                raise ValueError("Timeout en análisis de consorcio. La IA tardó demasiado en procesar.")
            except Exception as e:
                logger.error(f"❌ ERROR en análisis de consorcio: {str(e)}")
                raise ValueError(f"Error en análisis de consorcio: {str(e)}")
            
            # Respuesta final para consorcios (no necesita liquidador separado)
            respuesta = {
                "success": True,
                "version": "2.0.0",
                "arquitectura": "modular",
                "tipo_procesamiento": "CONSORCIO",
                "nit_administrativo": {
                    "nit": nit_administrativo,
                    "nombre_entidad": nombre_entidad,
                    "impuestos_aplicables": impuestos_aplicables,
                    "impuestos_procesados": ["RETENCION_FUENTE"],
                    "usado_por_defecto": nit_por_defecto
                },
                "flujo_completado": [
                    "validacion_nit",
                    "extraccion_texto",
                    "clasificacion_documentos",
                    "deteccion_consorcio",
                    "analisis_consorcio",
                    "calculo_retenciones_distribuidas"
                ],
                "estadisticas": {
                    "archivos_procesados": len(archivos),
                    "archivos_exitosos": len(archivos_exitosos),
                    "documentos_clasificados": len(clasificacion),
                    "es_consorcio": True,
                    "es_facturacion_extranjera": es_facturacion_extranjera,
                    "total_consorciados": resultado_analisis.get('consorcio_info', {}).get('total_consorciados', 0)
                },
                "resultados": {
                    "clasificacion_documentos": clasificacion,
                    "consorcio": resultado_analisis
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("🎉 Procesamiento de consorcio completado exitosamente")
            return respuesta
        
        else:
            logger.info("🧠 Paso 4: Analizando factura normal con Gemini...")
            try:
                analisis = await asyncio.wait_for(
                    clasificador.analizar_factura(documentos_clasificados, es_facturacion_extranjera),
                    timeout=90.0  # 90 segundos para facturas normales
                )
                logger.info(f"✅ Análisis completado: {len(analisis.conceptos_identificados)} conceptos identificados")
            except asyncio.TimeoutError:
                logger.error("⏰ TIMEOUT: Gemini tardó más de 90 segundos analizando factura")
                raise ValueError("Timeout en análisis de factura. La IA tardó demasiado en responder.")
            except Exception as e:
                logger.error(f"❌ ERROR en análisis de factura: {str(e)}")
                raise ValueError(f"Error en análisis de factura: {str(e)}")
        
        # PASO 5: CÁLCULO DE RETENCIÓN
        logger.info("💰 Paso 5: Calculando retención en la fuente...")
        liquidador = LiquidadorRetencion()
        
        if es_facturacion_extranjera:
            # Liquidación especializada para facturación extranjera
            resultado_liquidacion = liquidador.liquidar_factura_extranjera(
                analisis, nit_administrativo
            )
            logger.info(f"🌍 Liquidación extranjera completada: ${resultado_liquidacion.valor_retencion:,.0f} de retención")
        else:
            # Liquidación normal para facturación nacional
            resultado_liquidacion = liquidador.calcular_retencion(analisis)
            logger.info(f"🇨🇴 Liquidación nacional completada: ${resultado_liquidacion.valor_retencion:,.0f} de retención")
        
        # RESPUESTA FINAL
        respuesta = {
            "success": True,
            "version": "2.0.0",
            "arquitectura": "modular",
            "nit_administrativo": {
                "nit": nit_administrativo,
                "nombre_entidad": nombre_entidad,
                "impuestos_aplicables": impuestos_aplicables,
                "impuestos_procesados": ["RETENCION_FUENTE"],  # Solo este por ahora
                "usado_por_defecto": nit_por_defecto
            },
            "flujo_completado": [
                "validacion_nit",
                "extraccion_texto",
                "clasificacion_documentos",
                "deteccion_consorcio", 
                "analisis_factura",
                "calculo_retencion"
            ],
            "tipo_procesamiento": "FACTURA_NORMAL",
            "estadisticas": {
                "archivos_procesados": len(archivos),
                "archivos_exitosos": len(archivos_exitosos),
                "documentos_clasificados": len(clasificacion),
                "conceptos_identificados": len(analisis.conceptos_identificados),
                "es_consorcio": False,
                "es_facturacion_extranjera": es_facturacion_extranjera
            },
            "resultados": {
                "clasificacion_documentos": clasificacion,
                "analisis_factura": analisis.dict(),
                "liquidacion": resultado_liquidacion.dict()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("🎉 Procesamiento completado exitosamente")
        return respuesta
        
    except ValueError as e:
        # Errores de validación, Gemini timeout, o lógica de negocio
        error_msg = str(e)
        logger.error(f"❌ Error de procesamiento: {error_msg}")
        
        # Categorizar errores para mejor UX
        if "timeout" in error_msg.lower() or "tardó demasiado" in error_msg.lower():
            status_code = 408  # Request Timeout
            error_type = "timeout_error"
            user_message = "La IA está tardando más de lo normal. Por favor inténtalo de nuevo en unos minutos."
        elif "gemini" in error_msg.lower() or "clasificación" in error_msg.lower() or "análisis" in error_msg.lower():
            status_code = 502  # Bad Gateway (AI service error)
            error_type = "ai_error"
            user_message = "Error en el servicio de inteligencia artificial. Verifica tu conexión e inténtalo de nuevo."
        elif "extraer" in error_msg.lower() or "archivo" in error_msg.lower():
            status_code = 422  # Unprocessable Entity
            error_type = "file_error"
            user_message = "Error procesando los archivos. Verifica que sean válidos y legibles."
        elif "nit" in error_msg.lower():
            status_code = 422
            error_type = "validation_error"
            user_message = error_msg  # Usar mensaje original para errores de NIT
        else:
            status_code = 422
            error_type = "validation_error"
            user_message = error_msg
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": f"Error de procesamiento ({error_type})",
                "mensaje": user_message,
                "detalle_tecnico": error_msg,
                "tipo": error_type,
                "version": "2.0.0",
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"❌ Error interno: {e}")
        logger.error(traceback.format_exc())
        
        # Mensaje más user-friendly
        if "json" in str(e).lower():
            error_msg = "Error procesando respuesta de IA. Inténtalo de nuevo."
        elif "timeout" in str(e).lower():
            error_msg = "La IA tardó demasiado en responder. Inténtalo de nuevo."
        elif "api" in str(e).lower() or "gemini" in str(e).lower():
            error_msg = "Error de conexión con servicios de IA. Verifica tu conexión."
        else:
            error_msg = f"Error interno del servidor: {str(e)}"
            
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Error interno",
                "mensaje": error_msg,
                "tipo": "server_error",
                "version": "2.0.0"
            }
        )

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
                "aplica_retencion_fuente": "RETENCION_FUENTE" in datos["impuestos_aplicables"]
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
        "descripcion": "Sistema dividido en módulos especializados",
        "modulos": {
            "Clasificador": {
                **verificar_modulo("Clasificador"),
                "funcion": "Clasificación y análisis de documentos con Gemini"
            },
            "Liquidador": {
                **verificar_modulo("Liquidador"),
                "funcion": "Cálculo de retenciones según normativa colombiana"
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
                "funcion": "Almacenamiento de resultados por fecha",
                "carpetas_fecha": [d.name for d in Path("Results").iterdir() if d.is_dir()] if os.path.exists("Results") else []
            }
        },
        "archivos_principales": {
            "main.py": "Orquestador principal",
            "config.py": "Configuración global",
            ".env": "Variables de entorno"
        },
        "flujo_procesamiento": [
            "1. Extraccion/: Extraer texto de archivos",
            "2. Clasificador/: Clasificar documentos", 
            "3. Clasificador/: Analizar factura",
            "4. Liquidador/: Calcular retención"
        ]
    }

@app.post("/api/prueba-simple")
async def prueba_simple(nit_administrativo: Optional[str] = Form(None)):
    """Endpoint de prueba simple SIN archivos"""
    logger.info(f"🔥 PRUEBA SIMPLE: Recibido NIT: {nit_administrativo}")
    return {
        "success": True,
        "mensaje": "POST sin archivos funciona",
        "nit_recibido": nit_administrativo,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/prueba-procesamiento")
async def prueba_procesamiento_simple(
    archivos: List[UploadFile] = File(...),
    nit_administrativo: Optional[str] = Form(None)
):
    """Endpoint de prueba para verificar el flujo básico sin IA"""
    
    try:
        logger.info(f"🧪 PRUEBA: Iniciando procesamiento de {len(archivos)} archivos")
        
        # Simular validación de NIT
        if nit_administrativo is None:
            nits_disponibles = obtener_nits_disponibles()
            for nit, datos in nits_disponibles.items():
                if "RETENCION_FUENTE" in datos["impuestos_aplicables"]:
                    nit_administrativo = nit
                    break
        
        logger.info(f"🧪 PRUEBA: NIT administrativo: {nit_administrativo}")
        
        # Verificar archivos recibidos
        archivos_info = []
        for archivo in archivos:
            contenido = await archivo.read()
            archivos_info.append({
                "nombre": archivo.filename,
                "tamaño": len(contenido),
                "tipo": archivo.content_type,
                "tamaño_mb": round(len(contenido) / (1024*1024), 2)
            })
            # Resetear posición del archivo
            await archivo.seek(0)
            
        logger.info(f"🧪 PRUEBA: Archivos procesados correctamente")
        
        # Simular extracción (SIN IA)
        logger.info(f"🧪 PRUEBA: Simulando extracción de texto...")
        import time
        time.sleep(1)  # Simular procesamiento
        
        # Simular clasificación (SIN IA)  
        logger.info(f"🧪 PRUEBA: Simulando clasificación...")
        time.sleep(1)
        
        # Simular análisis (SIN IA)
        logger.info(f"🧪 PRUEBA: Simulando análisis...")
        time.sleep(1)
        
        # Respuesta de prueba
        respuesta = {
            "success": True,
            "tipo_prueba": "PROCESAMIENTO_SIMULADO",
            "version": "2.0.0",
            "mensaje": "Prueba completada exitosamente - flujo básico funcionando",
            "archivos_recibidos": len(archivos),
            "archivos_info": archivos_info,
            "nit_usado": nit_administrativo,
            "tiempo_total_segundos": 3,
            "pasos_completados": [
                "recepcion_archivos",
                "validacion_nit", 
                "lectura_contenido",
                "simulacion_extraccion",
                "simulacion_clasificacion",
                "simulacion_analisis"
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("🎉 PRUEBA: Completada exitosamente")
        return respuesta
        
    except Exception as e:
        logger.error(f"❌ PRUEBA: Error - {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error en prueba de procesamiento",
                "mensaje": str(e),
                "tipo": "test_error"
            }
        )

@app.get("/api/diagnostico")
async def diagnostico_completo():
    """Endpoint de diagnóstico completo para verificar todos los componentes del sistema"""
    diagnostico = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
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
            diagnostico["mensaje"] = "Todos los componentes están funcionando correctamente"
            
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
    
    logger.info("🚀 Iniciando Preliquidador de Retefuente v2.0 - Arquitectura Modular")
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
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        log_level="info",
        timeout_keep_alive=120,
        limit_max_requests=1000,
        limit_concurrency=100
    )
