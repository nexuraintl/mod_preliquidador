"""
PRELIQUIDADOR DE RETEFUENTE - COLOMBIA
====================================

Sistema automatizado para procesar facturas y calcular retención en la fuente
usando Google Gemini AI y FastAPI.

ARQUITECTURA MODULAR:
- Clasificador/: Clasificación de documentos con Gemini
- Liquidador/: Cálculo de retenciones según normativa
- Extraccion/: Extracción de texto de archivos (PDF, OCR, Excel, Word)
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
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

# Configuración de logging - INFRASTRUCTURE LAYER
import logging
from app_logging import configurar_logging

logger = logging.getLogger(__name__)

# ===============================
# IMPORTAR MÓDULOS LOCALES
# ===============================

# Importar clases desde módulos
from app.validacion_archivos import ValidadorArchivos
from Clasificador.clasificador_obra_uni import ClasificadorObraUni
from Clasificador.clasificador_iva import ClasificadorIva   
from Clasificador.clasificador_estampillas_g import ClasificadorEstampillasGenerales
from Clasificador.clasificador_tp import ClasificadorTasaProdeporte
from Clasificador import ProcesadorGemini, ClasificadorRetefuente
from Clasificador.clasificador_ica import ClasificadorICA
from Clasificador.clasificador_timbre import ClasificadorTimbre
from Liquidador import LiquidadorRetencion
from Liquidador.liquidador_consorcios import LiquidadorConsorcios, convertir_resultado_a_dict as convertir_consorcio_a_dict
from Liquidador.liquidador_ica import LiquidadorICA
from Liquidador.liquidador_sobretasa_b import LiquidadorSobretasaBomberil
from Liquidador.liquidador_timbre import LiquidadorTimbre
from Extraccion import ProcesadorArchivos, preprocesar_excel_limpio

# Importar módulos de base de datos (SOLID: Clean Architecture Module)
from database import (
    DatabaseManager,
    SupabaseDatabase,
    BusinessDataService,
    crear_business_service,
    inicializar_database_manager  # INFRASTRUCTURE SETUP
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
    nit_aplica_timbre,  #  NUEVA IMPORTACIÓN TIMBRE
    detectar_impuestos_aplicables_por_codigo,  #  DETECCIÓN AUTOMÁTICA POR CÓDIGO
    crear_resultado_recurso_extranjero_retefuente,  #  HELPER RECURSO EXTRANJERO
    crear_resultado_recurso_extranjero_iva,  #  HELPER RECURSO EXTRANJERO
    guardar_archivo_json,  # FUNCIÓN DE UTILIDAD PARA GUARDAR JSON

)

from app.validacion_negocios import validar_negocio

# Dependencias para preprocesamiento Excel
import pandas as pd
import io

# Importar utilidades - Respuestas mock para validaciones (SRP)
from utils.mockups import crear_respuesta_negocio_no_parametrizado
from utils.error_handlers import registrar_exception_handler

# ===============================
# INICIALIZACIÓN DE BASE DE DATOS
# ===============================

# Variables globales para el gestor de base de datos y servicio de negocio
# NOTA: Inicializadas en el lifespan de FastAPI
db_manager = None
business_service = None

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


if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY no está configurada en el archivo .env")

# Importar conceptos retefuente  desde configuración
from config import CONCEPTOS_RETEFUENTE

# ===============================
# NOTA: Los modelos Pydantic fueron movidos a modelos/modelos.py (Domain Layer - Clean Architecture)
# Este archivo trabaja directamente con diccionarios en lugar de modelos Pydantic
# ===============================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejador del ciclo de vida de la aplicación.
    Reemplaza los eventos startup/shutdown.

    PRINCIPIOS SOLID:
    - SRP: Solo maneja ciclo de vida de la aplicación
    - DIP: Usa funciones de infraestructura inyectadas
    """
    # Código que se ejecuta ANTES de que la aplicación inicie
    configurar_logging()
    global logger, db_manager, business_service
    logger = logging.getLogger(__name__)

    logger.info(" Worker de FastAPI iniciándose... Cargando configuración.")
    if not inicializar_configuracion():
        logger.critical(" FALLO EN LA CARGA DE CONFIGURACIÓN. La aplicación puede no funcionar correctamente.")

    # Inicializar gestor de base de datos usando Infrastructure Layer
    db_manager, business_service = inicializar_database_manager()

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

# Registrar exception handler para validaciones (SRP)
# Convierte errores 422 de validación Pydantic en respuestas 200 OK con estructura mockup
registrar_exception_handler(app)


@app.post("/api/procesar-facturas")
async def procesar_facturas_integrado(
    archivos: List[UploadFile] = File(...),
    codigo_del_negocio: int = Form(...),
    proveedor: str = Form(...),
    nit_proveedor: str = Form(...),
    estructura_contable: int = Form(...),
    observaciones_tp: Optional[str] = Form(None),
    genera_presupuesto: Optional[str] = Form(None),
    rubro: Optional[str] = Form(None),
    centro_costos: Optional[int] = Form(None),
    numero_contrato: Optional[str] = Form(None),
    valor_contrato_municipio: Optional[float] = Form(None),
    tipoMoneda: Optional[str] = Form("COP")
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

        # Consultar información del negocio usando BusinessService 
        resultado_negocio = business_service.obtener_datos_negocio(codigo_del_negocio)
        
        #validacion de de impuestos a procesar dada la naturaleza del proovedor 
        
        resultado_validacion = validar_negocio(resultado_negocio=resultado_negocio,codigo_del_negocio=codigo_del_negocio, business_service=business_service)
        
        if isinstance(resultado_validacion,JSONResponse):
            return resultado_validacion
        
        (impuestos_a_procesar, aplica_retencion, aplica_estampilla, aplica_obra_publica, aplica_iva, aplica_ica, aplica_timbre, aplica_tasa_prodeporte, nombre_negocio, nit_administrativo, deteccion_impuestos,nombre_entidad) = resultado_validacion
        
        
       
        # =================================
        # PASO 2: FILTRADO Y VALIDACIÓN DE ARCHIVOS
        # =================================
                
        validador_archivos = ValidadorArchivos()
        
        archivos_validos, archivos_ignorados = validador_archivos.validar(archivos)
   
        # =================================
        # PASO 3: EXTRACCIÓN HÍBRIDA DE TEXTO
        # =================================
        
        logger.info(" Iniciando procesamiento híbrido multimodal: separando archivos por estrategia...")
        
        # SEPARAR ARCHIVOS POR ESTRATEGIA DE PROCESAMIENTO
        archivos_directos = []      # PDFs e imágenes → Gemini directo (multimodal)
        archivos_preprocesamiento = []  # Excel, Email, Word → Procesamiento local
        
        for archivo in archivos_validos:
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
        
        logger.info(" Estrategia híbrida multimodal definida:")
        logger.info(f" Archivos directos (multimodal): {len(archivos_directos)}")
        logger.info(f" Archivos preprocesamiento local: {len(archivos_preprocesamiento)}")
        
        # PROCESAR SOLO ARCHIVOS QUE NECESITAN PREPROCESAMIENTO LOCAL
        if archivos_preprocesamiento:
            logger.info(f" Iniciando extracción local para {len(archivos_preprocesamiento)} archivos...")
            extractor = ProcesadorArchivos()
            textos_archivos_original = await extractor.procesar_multiples_archivos(archivos_preprocesamiento)
        else:
            logger.info(" No hay archivos para procesamiento local - Solo archivos directos multimodales")
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
        # PASO 4: CLASIFICACIÓN HÍBRIDA CON MULTIMODALIDAD
        # =================================

        # Clasificar documentos usando enfoque híbrido multimodal
        clasificador = ProcesadorGemini(estructura_contable=estructura_contable, db_manager=db_manager)

        # Instanciar clasificadores especializados
        clasificador_retefuente = ClasificadorRetefuente(
            procesador_gemini=clasificador,
            estructura_contable=estructura_contable,
            db_manager=db_manager
        )
        
        clasificador_tasa_prodeporte = ClasificadorTasaProdeporte(procesador_gemini=clasificador )
        
        clasificador_estampillas_generales = ClasificadorEstampillasGenerales(procesador_gemini=clasificador )
        
        clasificador_iva = ClasificadorIva(procesador_gemini=clasificador )
        
        clasificador_obra_uni = ClasificadorObraUni(procesador_gemini=clasificador )

        logger.info(" Iniciando clasificación híbrida multimodal:")
        logger.info(f" Archivos directos (PDFs/imágenes): {len(archivos_directos)}")
        logger.info(f"Textos preprocesados (Excel/Email/Word): {len(textos_preprocesados)}")

        clasificacion, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera = await clasificador.clasificar_documentos(
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
            "es_recurso_extranjero": es_recurso_extranjero,
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

        # Log resumido de documentos (sin mostrar contenido completo)
        docs_resumen = {nombre: {"categoria": info["categoria"], "chars": len(info["texto"])}
                       for nombre, info in documentos_clasificados.items()}
        logger.info(f"Documentos a analizar: {docs_resumen}")
        # Crear tareas paralelas para análisis con Gemini
        tareas_analisis = []
        logger.info(" Preparando cache para solucionar concurrencia en workers paralelos")
        cache_archivos = await clasificador.preparar_archivos_para_workers_paralelos(archivos_directos)

        # Tarea 1: Análisis de Retefuente (si aplica y no es recurso extranjero)
        if aplica_retencion and not es_recurso_extranjero:
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
                # SOLID v3.1: Usar clasificador especializado de retefuente
                tarea_retefuente = clasificador_retefuente.analizar_factura(
                    documentos_clasificados,
                    es_facturacion_extranjera,
                    None,
                    cache_archivos,
                    proveedor=proveedor
                )
            tareas_analisis.append(("retefuente", tarea_retefuente))
        elif aplica_retencion and es_recurso_extranjero:
            logger.info(" Retefuente: No se procesará - Recurso de fuente extranjera detectado")
        
        # Tarea 2: Análisis de Impuestos Especiales (si aplican)
        if aplica_estampilla or aplica_obra_publica:
            tarea_impuestos_especiales = clasificador_obra_uni.analizar_estampilla(documentos_clasificados, None, cache_archivos)
            tareas_analisis.append(("impuestos_especiales", tarea_impuestos_especiales))
        
        # Tarea 3: Análisis de IVA (si aplica y no es recurso extranjero) - NUEVA TAREA
        if aplica_iva and not es_recurso_extranjero:
            tarea_iva = clasificador_iva.analizar_iva(documentos_clasificados, None, cache_archivos)
            tareas_analisis.append(("iva_reteiva", tarea_iva))
        elif aplica_iva and es_recurso_extranjero:
            logger.info(" IVA/ReteIVA: No se procesará - Recurso de fuente extranjera detectado")
        
        # Tarea 4: Análisis de Estampillas Generales -  NUEVA FUNCIONALIDAD
        # Las estampillas generales se ejecutan SIEMPRE en paralelo para todos los NITs
        tarea_estampillas_generales = clasificador_estampillas_generales.analizar_estampillas_generales(documentos_clasificados, None, cache_archivos)
        tareas_analisis.append(("estampillas_generales", tarea_estampillas_generales))

        # Tarea 5: Análisis de Tasa Prodeporte - NUEVA FUNCIONALIDAD
        if aplica_tasa_prodeporte:
            tarea_tasa_prodeporte = clasificador_tasa_prodeporte.analizar_tasa_prodeporte(documentos_clasificados, None, cache_archivos, observaciones_tp)
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
                        estructura_contable=estructura_contable,
                        cache_archivos=cache_archivos  # Cache para procesamiento híbrido
                    )
                except Exception as e:
                    logger.error(f"Error en análisis ICA: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "aplica": False,
                        "estado": "preliquidacion_sin_finalizar",
                        "observaciones": [f"Error en análisis ICA: {str(e)}"]
                    }

            tarea_ica = analizar_ica_async()
            tareas_analisis.append(("ica", tarea_ica))
            logger.info(f"✓ ICA: Análisis activado para NIT {nit_administrativo}")

        # Tarea 7: Análisis de Timbre - NUEVA FUNCIONALIDAD
        if aplica_timbre:
            # Timbre requiere procesamiento especial con ClasificadorTimbre
            async def analizar_timbre_async():
                try:
                    clasificador_timbre = ClasificadorTimbre(
                        procesador_gemini=clasificador  # Procesador completo para reutilizar funciones
                    )
                    # Primera llamada: analizar observaciones
                    return await clasificador_timbre.analizar_observaciones_timbre(
                        observaciones=observaciones_tp or ""
                    )
                except Exception as e:
                    logger.error(f"Error en análisis Timbre (observaciones): {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "aplica_timbre": False,
                        "base_gravable_obs": 0.0,
                        "observaciones_analisis": f"Error en análisis Timbre: {str(e)}"
                    }

            tarea_timbre = analizar_timbre_async()
            tareas_analisis.append(("timbre", tarea_timbre))
            logger.info(f"✓ Timbre: Análisis activado para NIT {nit_administrativo}")

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

        logger.info(" Iniciando liquidación de impuestos en paralelo...")
        
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
                    liquidador_consorcio = LiquidadorConsorcios(estructura_contable=estructura_contable, db_manager=db_manager)
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
                        "es_facturacion_exterior": es_facturacion_extranjera,  # Pasar desde clasificación
                        "analisis": analisis_factura.dict() if hasattr(analisis_factura, 'dict') else analisis_factura
                    }
                    
                    # Guardar análisis para debugging
                    guardar_archivo_json(analisis_retefuente_data, "analisis_retefuente_paralelo")

                    # Liquidar con método seguro de la clase
                    liquidador_retencion = LiquidadorRetencion(estructura_contable=estructura_contable, db_manager=db_manager)
                    resultado_retefuente_dict = liquidador_retencion.liquidar_retefuente_seguro(
                        analisis_retefuente_data, nit_administrativo, tipoMoneda=tipoMoneda
                    )
                    
                    # Verificar solo si hay error técnico (excepción de liquidador)
                    if "error" in resultado_retefuente_dict:
                        # Error técnico - excepción durante liquidación
                        error_msg = resultado_retefuente_dict.get('error')
                        logger.error(f"Error técnico en liquidación: {error_msg}")

                        resultado_retefuente = type('ResultadoLiquidacion', (object,), {
                            'aplica': False,
                            'valor_retencion': 0.0,
                            'valor_factura_sin_iva': 0.0,
                            'conceptos_aplicados': [],
                            'valor_base_retencion': 0.0,
                            'fecha_calculo': datetime.now().isoformat(),
                            'mensajes_error': [error_msg],
                            'resumen_conceptos': 'Error técnico',
                            'estado': 'preliquidacion_sin_finalizar'
                        })()
                    else:
                        # Caso normal - confiar en liquidador.py
                        resultado_retefuente = type('ResultadoLiquidacion', (object,), {
                            'aplica': resultado_retefuente_dict.get("aplica", False),
                            'valor_retencion': resultado_retefuente_dict.get('valor_retencion', 0.0),
                            'valor_factura_sin_iva': resultado_retefuente_dict.get('valor_factura_sin_iva', 0.0),
                            'conceptos_aplicados': resultado_retefuente_dict.get("conceptos_aplicados", []),
                            'valor_base_retencion': resultado_retefuente_dict.get("base_gravable", 0.0),
                            'fecha_calculo': resultado_retefuente_dict.get("fecha_calculo", datetime.now().isoformat()),
                            'mensajes_error': resultado_retefuente_dict.get("observaciones", []),
                            'resumen_conceptos': resultado_retefuente_dict.get("resumen_conceptos", "N/A"),
                            'estado': resultado_retefuente_dict.get("estado", "preliquidado")
                        })()

                        # Log apropiado según resultado
                        if resultado_retefuente.valor_retencion > 0:
                            logger.info(f"Retefuente liquidada: ${resultado_retefuente.valor_retencion:,.2f}")
                        else:
                            logger.info(f"Retefuente procesada - Estado: {resultado_retefuente.estado}")
                
                #  ESTRUCTURA FINAL CONSOLIDADA
                if hasattr(resultado_retefuente, 'valor_retencion'):

                    resultado_final["impuestos"]["retefuente"] = {
                    "aplica": resultado_retefuente_dict.get("aplica", False),
                    "estado": resultado_retefuente_dict.get("estado", "preliquidacion_sin_finalizar"),
                    "valor_factura_sin_iva": resultado_retefuente_dict.get("valor_factura_sin_iva", 0.0),
                    "valor_retencion": resultado_retefuente_dict.get("valor_retencion", 0.0),
                    "valor_base": resultado_retefuente_dict.get("base_gravable", 0.0),
                    "conceptos_aplicados": resultado_retefuente_dict.get("conceptos_aplicados", []),
                    "observaciones": resultado_retefuente_dict.get("observaciones", []),
                    }

                    # Agregar pais_proveedor si es facturación extranjera
                    if es_facturacion_extranjera and "pais_proveedor" in resultado_retefuente_dict:
                        resultado_final["impuestos"]["retefuente"]["pais_proveedor"] = resultado_retefuente_dict.get("pais_proveedor", "")
                        logger.info(f" País proveedor: {resultado_retefuente_dict.get('pais_proveedor')}")

                    logger.info(f" Retefuente liquidada: ${resultado_retefuente_dict.get('valor_retencion', 0.0):,.2f}")

                else:
                    # Es un diccionario (resultado de consorcio)
                    resultado_final["impuestos"]["retefuente"] = resultado_retefuente
                    logger.info(f" Retefuente liquidada: ${resultado_retefuente.get('valor_retencion', 0):,.2f}")
            except Exception as e:
                logger.error(f" Error liquidando retefuente: {e}")
                resultado_final["impuestos"]["retefuente"] = {"error": str(e), "aplica": False}

        elif aplica_retencion and es_recurso_extranjero:
            # Recurso extranjero: crear estructura vacía sin procesamiento
            logger.info(" Retefuente: Aplicando estructura de recurso extranjero")
            resultado_retefuente = crear_resultado_recurso_extranjero_retefuente()

            resultado_final["impuestos"]["retefuente"] = {
                "aplica": resultado_retefuente.aplica,
                "estado": resultado_retefuente.estado,
                "valor_factura_sin_iva": resultado_retefuente.valor_factura_sin_iva,
                "valor_retencion": resultado_retefuente.valor_retencion,
                "valor_base": resultado_retefuente.valor_base_retencion,
                "conceptos_aplicados": resultado_retefuente.conceptos_aplicados,
                "observaciones": resultado_retefuente.mensajes_error,
            }
            logger.info(" Retefuente: No aplica (Recurso de fuente extranjera)")

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

                # Liquidar con nueva arquitectura SOLID (requiere 3 parámetros + tipoMoneda)
                resultado_iva_dict = liquidador_iva.liquidar_iva_completo(
                    analisis_gemini=analisis_iva_gemini,
                    clasificacion_inicial=clasificacion_inicial,
                    nit_administrativo=nit_administrativo,
                    tipoMoneda=tipoMoneda
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

        elif aplica_iva and es_recurso_extranjero:
            # Recurso extranjero: crear estructura vacía sin procesamiento
            logger.info(" IVA/ReteIVA: Aplicando estructura de recurso extranjero")
            resultado_iva = crear_resultado_recurso_extranjero_iva()

            resultado_final["impuestos"]["iva_reteiva"] = resultado_iva.get("iva_reteiva", {})
            logger.info(" IVA/ReteIVA: No aplica (Recurso de fuente extranjera)")

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

                # Liquidar ICA con tipoMoneda
                resultado_ica = liquidador_ica.liquidar_ica(analisis_ica, estructura_contable, tipoMoneda=tipoMoneda)

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
                    "estado": "preliquidacion_sin_finalizar",
                    "error": str(e),
                    "observaciones": [f"Error en liquidación ICA: {str(e)}"]
                }

        # Liquidar Sobretasa Bomberil - NUEVA FUNCIONALIDAD (Solo si ICA fue procesado)
        if "ica" in resultado_final["impuestos"]:
            try:
                logger.info(" Liquidando Sobretasa Bomberil...")

                # Obtener resultado de ICA
                resultado_ica = resultado_final["impuestos"]["ica"]

                # Crear liquidador Sobretasa Bomberil
                liquidador_sobretasa = LiquidadorSobretasaBomberil(database_manager=db_manager)

                # Liquidar Sobretasa Bomberil
                resultado_sobretasa = liquidador_sobretasa.liquidar_sobretasa_bomberil(resultado_ica)

                # Agregar resultado al resultado final
                resultado_final["impuestos"]["sobretasa_bomberil"] = resultado_sobretasa

                # Logs informativos
                estado_sobretasa = resultado_sobretasa.get("estado", "Desconocido")
                valor_sobretasa = resultado_sobretasa.get("valor_total_sobretasa", 0.0)
                logger.info(f" Sobretasa Bomberil - Estado: {estado_sobretasa}")
                logger.info(f" Sobretasa Bomberil - Valor total: ${valor_sobretasa:,.2f}")

            except Exception as e:
                logger.error(f" Error liquidando Sobretasa Bomberil: {e}")
                import traceback
                logger.error(traceback.format_exc())
                resultado_final["impuestos"]["sobretasa_bomberil"] = {
                    "aplica": False,
                    "estado": "preliquidacion_sin_finalizar",
                    "error": str(e),
                    "observaciones": f"Error en liquidación Sobretasa Bomberil: {str(e)}"
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
                    "estado": "preliquidacion_sin_finalizar"
                }

        # Liquidar Timbre - NUEVA FUNCIONALIDAD
        if "timbre" in resultados_analisis and aplica_timbre:
            try:
                logger.info(" Liquidando Impuesto al Timbre...")

                # Obtener análisis de observaciones de timbre
                analisis_observaciones_timbre = resultados_analisis["timbre"]
                aplica_timbre_obs = analisis_observaciones_timbre.get("aplica_timbre", False)

                # Si no aplica según observaciones, registrar como no aplica
                if not aplica_timbre_obs:
                    resultado_final["impuestos"]["timbre"] = {
                        "aplica": False,
                        "estado": "no_aplica_impuesto",
                        "valor": 0.0,
                        "tarifa": 0.0,
                        "tipo_cuantia": "",
                        "base_gravable": 0.0,
                        "ID_contrato": "",
                        "observaciones": "No se identifico aplicacion del impuesto al timbre en observaciones"
                    }
                    logger.info(" Timbre: No aplica según observaciones de PGD")
                else:
                    # Segunda llamada a Gemini: extraer datos del contrato
                    logger.info(" Timbre aplica - Extrayendo datos del contrato...")

                    clasificador_timbre = ClasificadorTimbre(procesador_gemini=clasificador)
                    datos_contrato = await clasificador_timbre.extraer_datos_contrato(
                        documentos_clasificados=documentos_clasificados,
                        archivos_directos=archivos_directos,
                        cache_archivos=cache_archivos
                    )

                    # Crear liquidador y liquidar (el liquidador se encarga de consultar BD)
                    liquidador_timbre = LiquidadorTimbre(db_manager=db_manager)
                    resultado_timbre = liquidador_timbre.liquidar_timbre(
                        nit_administrativo=nit_administrativo,
                        codigo_negocio=str(codigo_del_negocio),
                        nit_proveedor=proveedor,
                        analisis_observaciones=analisis_observaciones_timbre,
                        datos_contrato=datos_contrato
                    )

                    # Convertir Pydantic a dict
                    resultado_final["impuestos"]["timbre"] = resultado_timbre.dict()

                    # Log según resultado
                    if resultado_timbre.aplica:
                        logger.info(f" Timbre liquidado: ${resultado_timbre.valor:,.2f} (Tarifa: {resultado_timbre.tarifa*100}%)")
                    else:
                        logger.info(f" Timbre: {resultado_timbre.estado}")

            except Exception as e:
                logger.error(f" Error liquidando Timbre: {e}")
                import traceback
                logger.error(traceback.format_exc())
                resultado_final["impuestos"]["timbre"] = {
                    "aplica": False,
                    "estado": "preliquidacion_sin_finalizar",
                    "error": str(e),
                    "observaciones": f"Error en liquidación Timbre: {str(e)}"
                }

        # =================================
        # COMPLETAR IMPUESTOS QUE NO APLICAN
        # =================================

        # Agregar respuesta para impuestos que no aplican según código de negocio
        if not aplica_estampilla and "estampilla_universidad" not in resultado_final["impuestos"]:
            razon_estampilla = deteccion_impuestos.get("razon_no_aplica_estampilla") or f"El negocio {nombre_negocio} no aplica este impuesto"
            estado_estampilla = deteccion_impuestos.get("estado_especial") or "no_aplica_impuesto"

            # Construir mensajes_error sin duplicados
            # Si hay observaciones, usar solo esas; si no, usar la razón
            if deteccion_impuestos.get("validacion_recurso") and deteccion_impuestos["validacion_recurso"].get("observaciones"):
                mensajes_error_estampilla = [deteccion_impuestos["validacion_recurso"]["observaciones"]]
            else:
                mensajes_error_estampilla = [razon_estampilla]

            resultado_final["impuestos"]["estampilla_universidad"] = {
                "aplica": False,
                "estado": estado_estampilla,
                "valor_estampilla": 0.0,
                "tarifa_aplicada": 0.0,
                "valor_factura_sin_iva": 0.0,
                "rango_uvt": "",
                "valor_contrato_pesos": 0.0,
                "valor_contrato_uvt": 0.0,
                "mensajes_error": mensajes_error_estampilla,
                "razon": razon_estampilla,
            }
            logger.info(f" Estampilla Universidad: {estado_estampilla} - {razon_estampilla}")

        if not aplica_obra_publica and "contribucion_obra_publica" not in resultado_final["impuestos"]:
            razon_obra_publica = deteccion_impuestos.get("razon_no_aplica_obra_publica") or f"El negocio {nombre_negocio} no aplica este impuesto"
            estado_obra_publica = deteccion_impuestos.get("estado_especial") or "no_aplica_impuesto"

            # Construir mensajes_error sin duplicados
            # Si hay observaciones, usar solo esas; si no, usar la razón
            if deteccion_impuestos.get("validacion_recurso") and deteccion_impuestos["validacion_recurso"].get("observaciones"):
                mensajes_error_obra_publica = [deteccion_impuestos["validacion_recurso"]["observaciones"]]
            else:
                mensajes_error_obra_publica = [razon_obra_publica]

            resultado_final["impuestos"]["contribucion_obra_publica"] = {
                "aplica": False,
                "estado": estado_obra_publica,
                "tarifa_aplicada": 0.0,
                "valor_contribucion": 0.0,
                "valor_factura_sin_iva": 0.0,
                "mensajes_error": mensajes_error_obra_publica,
                "razon": razon_obra_publica,
            }
            logger.info(f" Contribución Obra Pública: {estado_obra_publica} - {razon_obra_publica}")

        if not aplica_iva and "iva_reteiva" not in resultado_final["impuestos"]:
            resultado_final["impuestos"]["iva_reteiva"] = {
                "aplica": False,
                "valor_iva_identificado": 0,
                "valor_subtotal_sin_iva": 0,
                "valor_reteiva": 0,
                "porcentaje_iva": 0,
                "tarifa_reteiva": 0,
                "es_fuente_nacional": False,
                "estado_liquidacion": "no_aplica_impuesto",
                "observaciones": [f"El NIT {nit_administrativo} no está configurado para IVA/ReteIVA"],
                "calculo_exitoso": False
            }
            logger.info(f" IVA/ReteIVA: No aplica para NIT {nit_administrativo}")

        if not aplica_tasa_prodeporte and "tasa_prodeporte" not in resultado_final["impuestos"]:
            resultado_final["impuestos"]["tasa_prodeporte"] = {
                "estado": "no_aplica_impuesto",
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

        if not aplica_timbre and "timbre" not in resultado_final["impuestos"]:
            resultado_final["impuestos"]["timbre"] = {
                "aplica": False,
                "estado": "no_aplica_impuesto",
                "valor": 0.0,
                "tarifa": 0.0,
                "tipo_cuantia": "",
                "base_gravable": 0.0,
                "ID_contrato": "",
                "observaciones": f"Nit {nit_administrativo} no aplica impuesto al timbre"
            }
            logger.info(f" Timbre: No aplica para NIT {nit_administrativo}")

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

        if "timbre" in resultado_final["impuestos"] and isinstance(resultado_final["impuestos"]["timbre"], dict):
            valor_total_impuestos += resultado_final["impuestos"]["timbre"].get("valor", 0)

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
    #logger.info(f" Vision configurado: {bool(GOOGLE_CLOUD_CREDENTIALS)}")
    
    # Verificar estructura de carpetas
    carpetas_requeridas = ["Clasificador", "Liquidador", "Extraccion",  "Results"]
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            logger.info(f" Módulo {carpeta}/ encontrado")
        else:
            logger.warning(f" Módulo {carpeta}/ no encontrado")
    

    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        timeout_keep_alive=120,
        limit_max_requests=1000,
        limit_concurrency=100
    )
