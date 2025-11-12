"""
PROCESADOR GEMINI - CLASIFICADOR DE DOCUMENTOS
==============================================

Maneja todas las interacciones con Google Gemini AI para:
1. Clasificar documentos en categorías (FACTURA, RUT, COTIZACION, ANEXO, etc.)
2. Analizar facturas y extraer información para retención en la fuente

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Tuple
from pathlib import Path

# Google Gemini
import google.generativeai as genai

# Modelos de datos (importar desde main)
from pydantic import BaseModel
from typing import List, Optional

# Importación adicional para archivos directos
from fastapi import UploadFile

#  NUEVAS IMPORTACIONES PARA VALIDACIÓN ROBUSTA DE PDF
import PyPDF2
from io import BytesIO

# Configuración de logging
logger = logging.getLogger(__name__)

# Importar prompts clasificador general
from prompts.prompt_clasificador import PROMPT_CLASIFICACION

# Importar prompts retefuente
from prompts.prompt_retefuente import (
    PROMPT_ANALISIS_FACTURA,
    PROMPT_EXTRACCION_CONSORCIO,  # NUEVO: Primera llamada extraccion
    PROMPT_MATCHING_CONCEPTOS,    # NUEVO: Segunda llamada matching
    PROMPT_ANALISIS_FACTURA_EXTRANJERA
)

# Importar prompts especializados
from prompts.prompt_iva import PROMPT_ANALISIS_IVA
from prompts.prompt_estampillas_generales import PROMPT_ANALISIS_ESTAMPILLAS_GENERALES

# ===============================
# IMPORTAR MODELOS DESDE DOMAIN LAYER (Clean Architecture - SRP)
# ===============================

from modelos import (
    # Modelos para Retencion General
    ConceptoIdentificado,
    NaturalezaTercero,

    # Modelos para Articulo 383 - Deducciones Personales
    ConceptoIdentificadoArt383,
    CondicionesArticulo383,
    InteresesVivienda,
    DependientesEconomicos,
    MedicinaPrepagada,
    AFCInfo,
    PlanillaSeguridadSocial,
    DeduccionesArticulo383,
    InformacionArticulo383,

    # Modelos Agregadores - Entrada/Salida
    AnalisisFactura,
)

# ===============================
# PROCESADOR GEMINI
# ===============================

class ProcesadorGemini:
    """Maneja las llamadas a la API de Gemini para clasificación y análisis"""
    
    def __init__(self, estructura_contable: int = None, db_manager = None):
        """
        Inicializa el procesador con configuración de Gemini

        Args:
            estructura_contable: Código de estructura contable para consultas de conceptos
            db_manager: Instancia de DatabaseManager para consultas a BD
        """
        # Cargar API key desde variables de entorno
        from dotenv import load_dotenv
        load_dotenv()

        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en el archivo .env")

        # Configurar Gemini
        genai.configure(api_key=self.api_key)

        # Configurar modelo con configuración estándar
        self.modelo = genai.GenerativeModel(
            'gemini-2.5-flash-preview-09-2025',
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=65536,
                candidate_count=1
                )
        )

        # Configuración especial para consorcios (más tokens)
        self.modelo_consorcio = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,  # Menos temperatura para más consistencia
                max_output_tokens=65536,  # 4x más tokens para consorcios grandescandidate_count=1
            )
        )

        # Nuevos parámetros para consultas BD
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager

        logger.info("ProcesadorGemini inicializado correctamente")

        # ARQUITECTURA SOLID: Inyección de dependencias para clasificadores especializados
        # Inicializar después de que self esté completamente configurado
        self.clasificador_retefuente = None
        self.clasificador_consorcio = None
        self._inicializar_clasificadores_especializados()

    def _inicializar_clasificadores_especializados(self):
        """
        Inicializa clasificadores especializados con inyección de dependencias.
        Siguiendo principio DIP (Dependency Inversion Principle).
        """
        try:
            # Importar clasificadores especializados
            from .clasificador_retefuente import ClasificadorRetefuente
            from .clasificador_consorcio import ClasificadorConsorcio

            # Crear instancia de ClasificadorRetefuente
            self.clasificador_retefuente = ClasificadorRetefuente(
                procesador_gemini=self,
                estructura_contable=self.estructura_contable,
                db_manager=self.db_manager
            )
            logger.info("ClasificadorRetefuente inicializado correctamente")

            # Crear instancia de ClasificadorConsorcio (depende de ClasificadorRetefuente)
            self.clasificador_consorcio = ClasificadorConsorcio(
                procesador_gemini=self,
                clasificador_retefuente=self.clasificador_retefuente
            )
            logger.info("ClasificadorConsorcio inicializado correctamente")

        except Exception as e:
            logger.error(f"Error inicializando clasificadores especializados: {e}")
            raise

    async def clasificar_documentos(
        self,
        textos_archivos_o_directos = None,  #  COMPATIBILIDAD TOTAL: Acepta cualquier tipo
        archivos_directos: List[UploadFile] = None,  #  NUEVO: Archivos directos
        textos_preprocesados: Dict[str, str] = None,  #  NUEVO: Textos preprocesados
        proveedor: str = None  #  v3.0: Nombre del proveedor para mejor identificacion
    ) -> Tuple[Dict[str, str], bool, bool, bool]:
        """
         FUNCIÓN HÍBRIDA CON COMPATIBILIDAD: Clasificación con archivos directos + textos preprocesados.
        
        MODOS DE USO:
         MODO LEGACY: clasificar_documentos(textos_archivos) - Funciona como antes
         MODO HÍBRIDO: clasificar_documentos(archivos_directos=[], textos_preprocesados={})
        
        ENFOQUE HÍBRIDO IMPLEMENTADO:
         PDFs e Imágenes → Enviados directamente a Gemini (multimodal)
         Excel/Email/Word → Procesados localmente y enviados como texto
         Límite: Máximo 20 archivos directos
         Mantener prompts existentes con modificaciones mínimas
        
        Args:
            textos_archivos: [LEGACY] Diccionario {nombre_archivo: texto_extraido} - Compatibilidad
            archivos_directos: [NUEVO] Lista de archivos para envío directo (PDFs e imágenes)
            textos_preprocesados: [NUEVO] Diccionario {nombre_archivo: texto_extraido} para archivos preprocesados
            
        Returns:
            Tuple[Dict[str, str], bool, bool]: (clasificacion_documentos, es_consorcio, es_facturacion_extranjera)
            
        Raises:
            ValueError: Si hay error en el procesamiento con Gemini
            HTTPException: Si se excede límite de archivos directos
        """
        #  DETECCIÓN AUTOMÁTICA DE MODO MEJORADA
        if textos_archivos_o_directos is not None:
            # DETECTAR TIPO DE ENTRADA
            if isinstance(textos_archivos_o_directos, dict):
                # MODO LEGACY: Dict[str, str] -  original de main.py
                logger.info(f" MODO LEGACY detectado: {len(textos_archivos_o_directos)} textos recibidos")
                logger.info(" Convirtiendo a modo híbrido interno...")
                
                archivos_directos = []
                textos_preprocesados = textos_archivos_o_directos
                
            elif isinstance(textos_archivos_o_directos, list):
                # MODO HÍBRIDO: List[UploadFile] - nueva signatura híbrida
                logger.info(f" MODO HÍBRIDO detectado: {len(textos_archivos_o_directos)} archivos directos")
                
                archivos_directos = textos_archivos_o_directos
                textos_preprocesados = textos_preprocesados or {}
                
            else:
                # MODO DESCONOCIDO: Error
                tipo_recibido = type(textos_archivos_o_directos).__name__
                error_msg = f"Tipo de entrada no soportado: {tipo_recibido}. Se esperaba Dict[str, str] (legacy) o List[UploadFile] (híbrido)"
                logger.error(f"{error_msg}")
                raise ValueError(error_msg)
        
        else:
            # MODO HÍBRIDO EXPLÍCITO: usar parámetros específicos
            logger.info(" MODO HÍBRIDO EXPLÍCITO detectado")
            archivos_directos = archivos_directos or []
            textos_preprocesados = textos_preprocesados or {}
        
        # Continuar con lógica híbrida usando variables normalizadas
        archivos_directos = archivos_directos or []
        textos_preprocesados = textos_preprocesados or {}        
        total_archivos = len(archivos_directos) + len(textos_preprocesados)
        
        logger.info(f" CLASIFICACIÓN HÍBRIDA iniciada:")
        logger.info(f" Archivos directos (PDFs/Imágenes): {len(archivos_directos)}")
        logger.info(f"Textos preprocesados (Excel/Email/Word): {len(textos_preprocesados)}")
        logger.info(f" Total archivos a clasificar: {total_archivos}")
        
        #  VALIDACIÓN: Límite de archivos directos (20)
        if len(archivos_directos) > 20:
            error_msg = f"Límite excedido: {len(archivos_directos)} archivos directos (máximo 20)"
            logger.error(f" {error_msg}")
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Demasiados archivos directos",
                    "detalle": error_msg,
                    "limite_maximo": 20,
                    "archivos_recibidos": len(archivos_directos),
                    "sugerencia": "Reduzca el número de PDFs/imágenes o use procesamiento por lotes"
                }
            )

        #  VALIDACIÓN: Al menos un archivo debe estar presente
        if total_archivos == 0:
            error_msg = "No se recibieron archivos para clasificar"
            logger.error(f" {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # PASO 1: Crear lista de nombres de archivos directos para el prompt (con manejo seguro)
            nombres_archivos_directos = []
            for archivo in archivos_directos:
                try:
                    if hasattr(archivo, 'filename') and archivo.filename:
                        nombres_archivos_directos.append(archivo.filename)
                    else:
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                except Exception as e:
                    logger.warning(f" Error obteniendo filename: {e}")
                    nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
            
            logger.info(f" Archivos directos para Gemini: {nombres_archivos_directos}")
            logger.info(f" Textos preprocesados: {list(textos_preprocesados.keys())}")

            # PASO 2: Generar prompt híbrido usando función modificada (v3.0: con proveedor)
            prompt = PROMPT_CLASIFICACION(textos_preprocesados, nombres_archivos_directos, proveedor)
            
            # PASO 3: Preparar contenido para Gemini (archivos directos + prompt)
            contents = [prompt]
            
            # Agregar archivos directos al contenido (con manejo seguro)
            for i, archivo in enumerate(archivos_directos):
                try:
                    # Resetear el puntero del archivo
                    if hasattr(archivo, 'seek'):
                        await archivo.seek(0)
                    
                    # Leer contenido del archivo
                    if hasattr(archivo, 'read'):
                        archivo_bytes = await archivo.read()
                    else:
                        # Si no es un UploadFile estándar, asumir que es bytes directo
                        archivo_bytes = archivo if isinstance(archivo, bytes) else bytes(archivo)
                    
                    contents.append(archivo_bytes)
                    
                    # Obtener nombre seguro para logging
                    nombre_archivo = nombres_archivos_directos[i] if i < len(nombres_archivos_directos) else f"archivo_{i+1}"
                    logger.info(f" Archivo directo agregado: {nombre_archivo} ({len(archivo_bytes):,} bytes)")
                    
                except Exception as e:
                    logger.error(f" Error procesando archivo directo {i+1}: {e}")
                    # Continuar con el siguiente archivo en lugar de fallar completamente
                    continue
            
            # PASO 4: Llamar a Gemini con contenido híbrido
            logger.info(f"Llamando a Gemini con {len(contents)} elementos: 1 prompt + {len(archivos_directos)} archivos")
            
            # Usar el modelo directamente en lugar de _llamar_gemini para archivos directos
            respuesta = await self._llamar_gemini_hibrido(contents)
            
            logger.info(f" Respuesta híbrida de Gemini recibida: {respuesta[:500]}...")
            
            # PASO 5: Procesar respuesta (igual que antes)
            # Limpiar respuesta si viene con texto extra
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Extraer clasificación y detección de consorcio
            factura_identificada = resultado.get("factura_identificada", False)
            rut_identificado = resultado.get("rut_identificado", False)
            clasificacion = resultado.get("clasificacion", resultado)  # Fallback para formato anterior
            # NUEVO v3.1.2: Detectar consorcio directamente del resultado de Gemini
            es_consorcio = resultado.get("es_consorcio", False)

            # Detectar tipo recurso extranjero usando validación manual (SRP)
            es_recurso_extranjero = self._evaluar_tipo_recurso(resultado)
            indicadores_extranjera = resultado.get("indicadores_extranjera", [])

            # Determinar facturación extranjera basada en ubicación del proveedor
            es_facturacion_extranjera = self._determinar_facturacion_extranjera(resultado)
            
            # PASO 6: Guardar respuesta con metadatos del procesamiento híbrido
            clasificacion_data_hibrida = {
                **resultado,
                "metadatos_hibridos": {
                    "procesamiento_hibrido": True,
                    "archivos_directos": nombres_archivos_directos,
                    "archivos_preprocesados": list(textos_preprocesados.keys()),
                    "total_archivos": total_archivos,
                    "timestamp": datetime.now().isoformat(),
                    "version": "2.4.0_hibrido"
                }
            }
            
            await self._guardar_respuesta("clasificacion_documentos_hibrido.json", clasificacion_data_hibrida)
            
            # PASO 7: Logging de resultados
            logger.info(f"factura_identificada: {factura_identificada}, rut_identificado: {rut_identificado}")
            logger.info(f" Clasificación híbrida exitosa: {len(clasificacion)} documentos clasificados")
            logger.info(f" Consorcio detectado: {es_consorcio}")
            logger.info(f" Tipo recurso extranjero detectado: {es_recurso_extranjero}")
            logger.info(f" Facturación extranjera detectada: {es_facturacion_extranjera}")
            if es_recurso_extranjero and indicadores_extranjera:
                logger.info(f" Indicadores extranjera: {indicadores_extranjera}")
            
            # PASO 8: Logging detallado por archivo
            for nombre_archivo, categoria in clasificacion.items():
                origen = "DIRECTO" if nombre_archivo in nombres_archivos_directos else "PREPROCESADO"
                logger.info(f" {nombre_archivo} → {categoria} ({origen})")
            
            return clasificacion, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera
            
        except json.JSONDecodeError as e:
            logger.error(f" Error parseando JSON híbrido de Gemini: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            
            raise ValueError(f"Error en JSON clasificación híbrida: {str(e)}")
        
        except Exception as e:
            logger.error(f" Error en clasificación híbrida de documentos: {e}")
            # Logging seguro de archivos directos fallidos
            archivos_fallidos_nombres = []
            for archivo in archivos_directos:
                try:
                    if hasattr(archivo, 'filename') and archivo.filename:
                        archivos_fallidos_nombres.append(archivo.filename)
                    else:
                        archivos_fallidos_nombres.append("archivo_sin_nombre")
                except Exception:
                    archivos_fallidos_nombres.append("archivo_con_error")
            
            logger.error(f" Archivos directos fallidos: {archivos_fallidos_nombres}")
            logger.error(f" Textos preprocesados fallidos: {list(textos_preprocesados.keys())}")
            raise ValueError(f"Error en clasificación híbrida: {str(e)}")

    # ===============================
    # NUEVA FUNCIÓN: _llamar_gemini_hibrido
    # ===============================
    
    async def _llamar_gemini_hibrido(self, contents: List) -> str:
        """
        Llamada especial a Gemini para contenido híbrido (prompt + archivos directos).
        
        CORREGIDO: Ahora crea objetos con formato correcto para Gemini multimodal.
        
        Args:
            contents: Lista con prompt + archivos UploadFile [prompt_str, archivo1_UploadFile, archivo2_UploadFile, ...]
            
        Returns:
            str: Respuesta de Gemini
            
        Raises:
            ValueError: Si hay error en la llamada a Gemini
        """
        try:
            timeout_segundos = 90.0
            
            logger.info(f" Llamada híbrida a Gemini con timeout de {timeout_segundos}s")
            logger.info(f" Contenido: 1 prompt + {len(contents) - 1} archivos directos")
            
            #  CREAR CONTENIDO MULTIMODAL CORRECTO
            contenido_multimodal = []
            
            # Agregar prompt (primer elemento)
            if contents:
                prompt_texto = contents[0]
                contenido_multimodal.append(prompt_texto)
                logger.info(f" Prompt agregado: {len(prompt_texto):,} caracteres")
            
            #  PROCESAR ARCHIVOS DIRECTOS CORRECTAMENTE
            archivos_directos = contents[1:] if len(contents) > 1 else []
            for i, archivo_elemento in enumerate(archivos_directos):
                try:
                    # Si es bytes (resultado de archivo.read()), necesitamos crear objeto correcto
                    if isinstance(archivo_elemento, bytes):
                        # Este es el problema: bytes raw sin información de tipo
                        # Intentar detectar tipo de archivo por magic bytes
                        if archivo_elemento.startswith(b'%PDF'):
                            # Es un PDF
                            archivo_objeto = {
                                "mime_type": "application/pdf",
                                "data": archivo_elemento
                            }
                            logger.info(f" PDF detectado por magic bytes: {len(archivo_elemento):,} bytes")
                        elif archivo_elemento.startswith((b'\xff\xd8\xff', b'\x89PNG')):
                            # Es imagen JPEG o PNG
                            if archivo_elemento.startswith(b'\xff\xd8\xff'):
                                mime_type = "image/jpeg"
                            else:
                                mime_type = "image/png"
                            archivo_objeto = {
                                "mime_type": mime_type,
                                "data": archivo_elemento
                            }
                            logger.info(f" Imagen detectada por magic bytes: {mime_type}, {len(archivo_elemento):,} bytes")
                        else:
                            # Tipo genérico
                            archivo_objeto = {
                                "mime_type": "application/octet-stream",
                                "data": archivo_elemento
                            }
                            logger.info(f" Archivo genérico: {len(archivo_elemento):,} bytes")
                    
                    elif hasattr(archivo_elemento, 'read'):
                        # Es un UploadFile que no se ha leído aún
                        await archivo_elemento.seek(0)
                        archivo_bytes = await archivo_elemento.read()
                        
                        # Determinar MIME type por extension
                        nombre_archivo = getattr(archivo_elemento, 'filename', f'archivo_{i+1}')
                        extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''
                        
                        if extension == 'pdf':
                            mime_type = "application/pdf"
                        elif extension in ['jpg', 'jpeg']:
                            mime_type = "image/jpeg"
                        elif extension == 'png':
                            mime_type = "image/png"
                        elif extension == 'gif':
                            mime_type = "image/gif"
                        elif extension in ['bmp']:
                            mime_type = "image/bmp"
                        elif extension in ['tiff', 'tif']:
                            mime_type = "image/tiff"
                        elif extension == 'webp':
                            mime_type = "image/webp"
                        else:
                            mime_type = "application/octet-stream"
                        
                        archivo_objeto = {
                            "mime_type": mime_type,
                            "data": archivo_bytes
                        }
                        logger.info(f" Archivo {i+1} procesado: {nombre_archivo} ({len(archivo_bytes):,} bytes, {mime_type})")
                    
                    else:
                        # Tipo desconocido, intentar convertir
                        logger.warning(f" Tipo de archivo desconocido: {type(archivo_elemento)}")
                        archivo_objeto = {
                            "mime_type": "application/octet-stream",
                            "data": bytes(archivo_elemento) if not isinstance(archivo_elemento, bytes) else archivo_elemento
                        }
                    
                    contenido_multimodal.append(archivo_objeto)
                    
                except Exception as e:
                    logger.error(f" Error procesando archivo {i+1}: {e}")
                    continue
            
            # ✅ LLAMAR A GEMINI CON CONTENIDO MULTIMODAL CORRECTO
            logger.info(f" Enviando a Gemini: {len(contenido_multimodal)} elementos multimodales")
            
            loop = asyncio.get_event_loop()
            
            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None, 
                    lambda: self.modelo.generate_content(contenido_multimodal)
                ),
                timeout=timeout_segundos
            )
            
            if not respuesta:
                raise ValueError("Gemini devolvió respuesta None en modo híbrido")
                
            if not hasattr(respuesta, 'text') or not respuesta.text:
                raise ValueError("Gemini devolvió respuesta sin texto en modo híbrido")
                
            texto_respuesta = respuesta.text.strip()
            
            if not texto_respuesta:
                raise ValueError("Gemini devolvió texto vacío en modo híbrido")
                
            logger.info(f" Respuesta híbrida de Gemini recibida: {len(texto_respuesta):,} caracteres")
            return texto_respuesta
            
        except asyncio.TimeoutError:
            error_msg = f"Gemini tardó más de {timeout_segundos}s en procesar archivos directos"
            logger.error(f" Timeout híbrido: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f" Error llamando a Gemini en modo híbrido: {e}")
            logger.error(f" Tipo de contenido enviado: {[type(item) for item in contents[:2]]}")
            raise ValueError(f"Error híbrido de Gemini: {str(e)}")

    # ===============================
    # NOTA: Funciones de Retefuente movidas a clasificador_retefuente.py (SRP)
    # Funciones movidas: analizar_factura, _analizar_articulo_383, _obtener_campo_art383_default,
    # _art383_fallback, _analisis_fallback, funciones de conceptos retefuente y extranjeros
    # ===============================

    async def analizar_consorcio(self,
                                  documentos_clasificados: Dict[str, Dict],
                                  es_facturacion_extranjera: bool = False,
                                  archivos_directos: List[UploadFile] = None,
                                  cache_archivos: Dict[str, bytes] = None,
                                  proveedor: str = None) -> Dict[str, Any]:
        """
        DELEGACIÓN A CLASIFICADOR ESPECIALIZADO (Principio SRP + DIP).

        Delega el análisis de consorcios al ClasificadorConsorcio especializado.
        Siguiendo arquitectura SOLID con separación de responsabilidades.

        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera
            archivos_directos: Lista de archivos directos
            cache_archivos: Cache de archivos para workers paralelos
            proveedor: Nombre del proveedor/consorcio

        Returns:
            Dict[str, Any]: Análisis completo del consorcio

        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        logger.info("DELEGANDO análisis de consorcio a ClasificadorConsorcio (SOLID - SRP)")

        # DIP: Delegar a clasificador especializado
        return await self.clasificador_consorcio.analizar_consorcio(
            documentos_clasificados=documentos_clasificados,
            es_facturacion_extranjera=es_facturacion_extranjera,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos,
            proveedor=proveedor
        )

    async def analizar_estampilla(self, documentos_clasificados: Dict[str, Dict], archivos_directos: List[str] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
        Análisis integrado de impuestos especiales (estampilla + obra pública) Multimodal CON CACHE.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            archivos_directos: Lista de archivos directos (para compatibilidad)
            cache_archivos: Cache de archivos para workers paralelos
            
        Returns:
            Dict[str, Any]: Análisis completo integrado
            
        Raises:
            ValueError: Si hay error en el procesamiento
        """
        logger.info(" Analizando IMPUESTOS ESPECIALES INTEGRADOS con Gemini")
        logger.info(" Impuestos: ESTAMPILLA_UNIVERSIDAD + CONTRIBUCION_OBRA_PUBLICA")
        
        # 💾 USAR CACHE SI ESTÁ DISPONIBLE
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f"Estampillas usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" Estampillas usando archivos directos originales: {len(archivos_directos)} archivos")
        
        # Importar liquidador integrado
        try:
            from Liquidador.liquidador_estampilla import LiquidadorEstampilla
            liquidador = LiquidadorEstampilla()
        except ImportError:
            logger.error("No se pudo importar LiquidadorEstampilla")
            raise ValueError("Error cargando liquidador de impuestos especiales")
        
        # Combinar todo el texto de los documentos
        texto_completo = ""
        for nombre_archivo, info in documentos_clasificados.items():
            texto_completo += f"\n\n--- {info['categoria']}: {nombre_archivo} ---\n{info['texto']}"
        
        logger.info(f" Analizando impuestos especiales con TEXTO COMPLETO: {len(texto_completo):,} caracteres (sin límites)")
        
        try:
            # Extraer documentos por categoría
            factura_texto = ""
            rut_texto = ""
            anexos_texto = ""
            cotizaciones_texto = ""
            anexo_contrato = ""
            
            for nombre_archivo, info in documentos_clasificados.items():
                if info["categoria"] == "FACTURA":
                    factura_texto = info["texto"]
                elif info["categoria"] == "RUT":
                    rut_texto = info["texto"]
                elif info["categoria"] == "ANEXO":
                    anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "COTIZACION":
                    cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                    anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
                    
            # ✅ VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)
            hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
            nombres_archivos_directos = [archivo.filename for archivo in archivos_directos]
            posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
        
            if not hay_factura_texto and not posibles_facturas_directas:
                raise ValueError("No se encontró una FACTURA en los documentos (ni texto ni archivo directo)")
            
            nombres_archivos_directos = []
            for archivo  in archivos_directos:
                try:
                    if hasattr(archivo, 'filename') and archivo.filename:
                        nombres_archivos_directos.append(archivo.filename)
                    else:
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                except Exception as e:
                    logger.warning(f" Error obteniendo nombre de archivo: {e}")
                    nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")


            # Modo multimodal
            prompt = liquidador.obtener_prompt_integrado_desde_clasificador(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nit_administrativo="", nombres_archivos_directos=nombres_archivos_directos # Se puede obtener del contexto si es necesario
            )
            
            # Llamar a Gemini
            respuesta = await self._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            logger.info(f"Respuesta análisis impuestos especiales: {respuesta[:500]}...")
            
            # Limpiar respuesta
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)

            # Parsear JSON
            resultado = json.loads(respuesta_limpia)

            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_impuestos_especiales.json", resultado)

            # ✅ ARQUITECTURA v3.0: Retornar JSON simple de extracción y clasificación
            # El liquidador hará todas las validaciones manuales con Python
            logger.info(" Análisis de Gemini completado - Retornando extracción y clasificación para validaciones Python")
            logger.info(f" Estructura: extraccion={bool(resultado.get('extraccion'))}, clasificacion={bool(resultado.get('clasificacion'))}")

            # Validar que la estructura sea la correcta
            if "extraccion" not in resultado or "clasificacion" not in resultado:
                logger.warning("⚠️ Respuesta de Gemini no tiene estructura esperada v3.0")
                logger.warning(f"Claves encontradas: {list(resultado.keys())}")

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de impuestos especiales: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            raise ValueError(f"Error parseando respuesta de Gemini para impuestos especiales: {str(e)}")
        except Exception as e:
            logger.error(f"Error en análisis de impuestos especiales: {e}")
            raise ValueError(f"Error analizando impuestos especiales: {str(e)}")
        
    async def _llamar_gemini_hibrido_factura(self, prompt: str, archivos_directos: List[UploadFile]) -> str:
        
             
        """
         FUNCIÓN HÍBRIDA PARA ANÁLISIS DE FACTURA: Prompt + Archivos directos para análisis de retefuente.
         
         FUNCIONALIDAD:
         ✅ Análisis especializado de facturas con multimodalidad
         ✅ Combina prompt de análisis + archivos PDFs/imágenes
         ✅ Optimizado para análisis de retefuente, consorcios y extranjera
         ✅ Reutilizable para todos los tipos de análisis de facturas
         ✅ Timeout extendido para análisis complejo
         
         Args:
             prompt: Prompt especializado para análisis (PROMPT_ANALISIS_FACTURA, etc.)
             archivos_directos: Lista de archivos para envío directo a Gemini
             
         Returns:
             str: Respuesta de Gemini con análisis completo
             
         Raises:
             ValueError: Si hay error en la llamada a Gemini
         """
        try:
            # Normalizar archivos_directos (puede ser None)
            if archivos_directos is None:
                archivos_directos = []

            # Timeout extendido para análisis de facturas (más complejo que clasificación)
            timeout_segundos = 280.0  # 4 minutos para análisis detallado

            logger.info(f" Análisis híbrido de factura con timeout de {timeout_segundos}s")
            logger.info(f" Contenido: 1 prompt de análisis + {len(archivos_directos)} archivos directos")

            # ✅ CREAR CONTENIDO MULTIMODAL CORRECTO PARA ANÁLISIS
            contenido_multimodal = []

            # Agregar prompt de análisis (primer elemento)
            contenido_multimodal.append(prompt)
            logger.info(f"Prompt de análisis agregado: {len(prompt):,} caracteres")

            # ✅ PROCESAR ARCHIVOS DIRECTOS CON VALIDACIÓN ROBUSTA
            for i, archivo in enumerate(archivos_directos):
                try:
                    # 🔍 LOGGING INICIAL PARA DIAGNÓSTICO
                    nombre_archivo_debug = getattr(archivo, 'filename', f'archivo_sin_nombre_{i+1}')
                    tipo_archivo = type(archivo).__name__
                    logger.info(f" Procesando archivo {i+1}/{len(archivos_directos)}: {nombre_archivo_debug} (Tipo: {tipo_archivo})")
                    
                    # 🆕 PASO 1: LECTURA SEGURA CON RETRY MEJORADA
                    archivo_bytes, nombre_archivo = await self._leer_archivo_seguro(archivo)
                    
                    # 🆕 PASO 2: VALIDACIÓN ESPECÍFICA PARA PDFs
                    if archivo_bytes.startswith(b'%PDF'):
                        # 🚨 VALIDACIÓN CRÍTICA: Verificar que el PDF tiene páginas
                        if not await self._validar_pdf_tiene_paginas(archivo_bytes, nombre_archivo):
                            logger.error(f"PDF inválido o sin páginas, omitiendo: {nombre_archivo}")
                            continue  # Saltar este archivo problemaático
                        
                        archivo_objeto = {
                            "mime_type": "application/pdf",
                            "data": archivo_bytes
                        }
                        logger.info(f" PDF VALIDADO para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes)")
                        
                    elif archivo_bytes.startswith((b'\xff\xd8\xff', b'\x89PNG')):
                        # Imágenes - validación básica
                        if archivo_bytes.startswith(b'\xff\xd8\xff'):
                            mime_type = "image/jpeg"
                        else:
                            mime_type = "image/png"
                        
                        archivo_objeto = {
                            "mime_type": mime_type,
                            "data": archivo_bytes
                        }
                        logger.info(f" Imagen validada para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes, {mime_type})")
                        
                    else:
                        # Detectar por extensión y validar tamaño mínimo
                        extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''
                        
                        mime_type_map = {
                            'pdf': 'application/pdf',
                            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                            'png': 'image/png', 'gif': 'image/gif',
                            'bmp': 'image/bmp', 'tiff': 'image/tiff', 'tif': 'image/tiff',
                            'webp': 'image/webp'
                        }
                        mime_type = mime_type_map.get(extension, 'application/octet-stream')
                        
                        # 🚨 VALIDACIÓN ADICIONAL PARA PDFs POR EXTENSIÓN
                        if extension == 'pdf':
                            if not await self._validar_pdf_tiene_paginas(archivo_bytes, nombre_archivo):
                                logger.error(f" PDF detectado por extensión inválido, omitiendo: {nombre_archivo}")
                                continue
                        
                        archivo_objeto = {
                            "mime_type": mime_type,
                            "data": archivo_bytes
                        }
                        logger.info(f" Archivo validado para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes, {mime_type})")
                    
                    contenido_multimodal.append(archivo_objeto)
                    
                except ValueError as ve:
                    # Errores específicos de validación
                    logger.error(f" Error de validación en archivo {i+1}: {ve}")
                    logger.warning(f" Omitiendo archivo problemaático: {getattr(archivo, 'filename', f'archivo_{i+1}')}")
                    continue
                except Exception as e:
                    # Otros errores inesperados
                    logger.error(f" Error inesperado procesando archivo {i+1}: {e}")
                    logger.warning(f" Omitiendo archivo con error: {getattr(archivo, 'filename', f'archivo_{i+1}')}")
                    continue
            
            # 🚨 VALIDACIÓN FINAL: Verificar que tenemos archivos válidos para enviar
            archivos_validos = len(contenido_multimodal) - 1  # -1 porque el primer elemento es el prompt
            
            if archivos_validos == 0:
                error_msg = "No se pudo validar ningún archivo para análisis - todos los archivos presentaron problemas"
                logger.error(f" {error_msg}")
                raise ValueError(error_msg)
            
            if archivos_validos < len(archivos_directos):
                archivos_omitidos = len(archivos_directos) - archivos_validos
                logger.warning(f"Se omitieron {archivos_omitidos} archivos problemáticos de {len(archivos_directos)} archivos totales")
            
            # ✅ LLAMAR A GEMINI CON CONTENIDO MULTIMODAL VALIDADO
            logger.info(f" Enviando análisis a Gemini: {len(contenido_multimodal)} elementos ({archivos_validos} archivos validados)")
            
            loop = asyncio.get_event_loop()
            
            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None, 
                    lambda: self.modelo.generate_content(contenido_multimodal)
                ),
                timeout=timeout_segundos
            )
            
            if not respuesta:
                raise ValueError("Gemini devolvió respuesta None en análisis híbrido - posible problema de validación de archivos")
                
            if not hasattr(respuesta, 'text') or not respuesta.text:
                raise ValueError(" Gemini devolvió respuesta sin texto - archivos validados correctamente pero sin respuesta")
                
            texto_respuesta = respuesta.text.strip()
            
            if not texto_respuesta:
                raise ValueError(" Gemini devolvió texto vacío - validación exitosa pero respuesta vacía")
                
            logger.info(f" Análisis híbrido de factura completado: {len(texto_respuesta):,} caracteres")
            return texto_respuesta
            
        except asyncio.TimeoutError:
            error_msg = f"Análisis híbrido tardó más de {timeout_segundos}s en completarse"
            logger.error(f" Timeout en análisis híbrido: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f" Error en análisis híbrido de factura: {e}")
            # Manejar archivos_directos que puede ser None
            archivos_info = []
            if archivos_directos:
                archivos_info = [getattr(archivo, 'filename', 'sin_nombre') for archivo in archivos_directos]
            logger.error(f" Archivos enviados: {archivos_info}")
            raise ValueError(f"Error híbrido en análisis de factura: {str(e)}")
    
    # ===============================
    # 🆕 NUEVAS FUNCIONES DE VALIDACIÓN ROBUSTA - SINGLE RETRY
    # ===============================
    
    def _clonar_uploadfile_para_worker(self, archivo_bytes: bytes, nombre_archivo: str) -> 'UploadFile':
        """
        Crea un UploadFile clonado a partir de bytes para uso independiente en workers paralelos.
        
        SOLUCIÓN PARA CONCURRENCIA: Cada worker necesita su propia copia del archivo.
        
        Args:
            archivo_bytes: Contenido del archivo en bytes
            nombre_archivo: Nombre del archivo
            
        Returns:
            UploadFile: Nuevo objeto UploadFile independiente
        """
        from io import BytesIO
        from starlette.datastructures import UploadFile
        
        # Crear un nuevo stream independiente
        stream = BytesIO(archivo_bytes)
        
        # Crear nuevo UploadFile con el stream clonado
        archivo_clonado = UploadFile(
            filename=nombre_archivo,
            file=stream,
            content_type="application/pdf" if nombre_archivo.lower().endswith('.pdf') else "application/octet-stream"
        )
        
        logger.info(f" Archivo clonado para worker independiente: {nombre_archivo} ({len(archivo_bytes):,} bytes)")
        return archivo_clonado
    
    async def _crear_cache_archivos_para_workers(self, archivos_directos: List[UploadFile]) -> Dict[str, bytes]:
        """
        Crea cache de archivos en memoria para uso independiente por múltiples workers.
        
        SOLUCIÓN CONCURRENCIA: Leer todos los archivos UNA VEZ y cachearlos para workers paralelos.
        
        Args:
            archivos_directos: Lista de archivos UploadFile originales
            
        Returns:
            Dict[str, bytes]: Cache {nombre_archivo: contenido_bytes}
        """
        cache_archivos = {}
        
        logger.info(f" Creando cache de archivos para workers paralelos: {len(archivos_directos)} archivos")
        
        for i, archivo in enumerate(archivos_directos):
            try:
                # Leer archivo UNA VEZ usando nuestra función segura
                archivo_bytes, nombre_archivo = await self._leer_archivo_seguro(archivo)
                
                # Validar PDF si corresponde
                if archivo_bytes.startswith(b'%PDF'):
                    if not await self._validar_pdf_tiene_paginas(archivo_bytes, nombre_archivo):
                        logger.error(f" PDF inválido en cache, omitiendo: {nombre_archivo}")
                        continue
                
                # Guardar en cache
                cache_archivos[nombre_archivo] = archivo_bytes
                logger.info(f" Archivo cacheado: {nombre_archivo} ({len(archivo_bytes):,} bytes)")
                
            except Exception as e:
                logger.error(f" Error cacheando archivo {i+1}: {e}")
                continue
        
        logger.info(f" Cache creado exitosamente: {len(cache_archivos)} archivos listos para workers")
        return cache_archivos
    
    def _obtener_archivos_clonados_desde_cache(self, cache_archivos: Dict[str, bytes]) -> List[UploadFile]:
        """
        Genera lista de UploadFiles clonados desde cache para un worker específico.
        
        Args:
            cache_archivos: Cache de archivos {nombre: bytes}
            
        Returns:
            List[UploadFile]: Lista de archivos clonados independientes
        """
        archivos_clonados = []
        
        for nombre_archivo, archivo_bytes in cache_archivos.items():
            try:
                archivo_clonado = self.crear_archivo_clon_para_worker(archivo_bytes, nombre_archivo)
                archivos_clonados.append(archivo_clonado)
            except Exception as e:
                logger.error(f" Error clonando archivo {nombre_archivo}: {e}")
                continue
        
        logger.info(f" {len(archivos_clonados)} archivos clonados para worker independiente")
        return archivos_clonados
    
    # ===============================
    # 🆕 FUNCIÓN COORDINADORA PARA CONCURRENCIA
    # ===============================
    
    async def preparar_archivos_para_workers_paralelos(self, archivos_directos: List[UploadFile]) -> Dict[str, bytes]:
        """
        SOLUCIÓN CONCURRENCIA: Lee archivos UNA VEZ y crea cache para workers paralelos.
        
        Esta función soluciona el problema donde múltiples workers paralelos
        intentan leer el mismo objeto UploadFile simultáneamente.
        
        Args:
            archivos_directos: Lista de archivos UploadFile originales
            
        Returns:
            Dict[str, bytes]: Cache {nombre_archivo: contenido_bytes}
        """
        if not archivos_directos:
            return {}
            
        logger.info(f" SOLUCIONANDO CONCURRENCIA: Preparando cache para workers paralelos")
        logger.info(f" Archivos a procesar: {len(archivos_directos)}")
        
        cache_archivos = {}
        
        for i, archivo in enumerate(archivos_directos):
            try:
                # Leer archivo UNA SOLA VEZ usando validación robusta
                archivo_bytes, nombre_archivo = await self._leer_archivo_seguro(archivo)
                
                # Validar PDF si es necesario
                if archivo_bytes.startswith(b'%PDF'):
                    if not await self._validar_pdf_tiene_paginas(archivo_bytes, nombre_archivo):
                        logger.error(f" PDF inválido omitido del cache: {nombre_archivo}")
                        continue
                
                # Guardar en cache para workers
                cache_archivos[nombre_archivo] = archivo_bytes
                logger.info(f" Archivo cacheado para workers: {nombre_archivo} ({len(archivo_bytes):,} bytes)")
                
            except Exception as e:
                logger.error(f" Error cacheando archivo {i+1}: {e}")
                continue
        
        logger.info(f" Cache preparado: {len(cache_archivos)} archivos listos para workers paralelos")
        return cache_archivos
    
    def crear_archivo_clon_para_worker(self, archivo_bytes: bytes, nombre_archivo: str) -> UploadFile:
        """
        Crea un UploadFile independiente para un worker específico.
        
        CORREGIDO: Compatible con todas las versiones de Starlette/FastAPI.
        
        Args:
            archivo_bytes: Contenido del archivo
            nombre_archivo: Nombre del archivo
            
        Returns:
            UploadFile: Archivo clonado independiente
        """
        from io import BytesIO
        from starlette.datastructures import UploadFile
        
        # Stream independiente para este worker 
        stream = BytesIO(archivo_bytes)
        
        # ✅ SOLUCIÓN: UploadFile sin content_type (compatible con todas las versiones)
        try:
            # Intentar con content_type (versiones más nuevas)
            archivo_clonado = UploadFile(
                filename=nombre_archivo,
                file=stream,
                content_type="application/pdf" if nombre_archivo.lower().endswith('.pdf') else "application/octet-stream"
            )
        except TypeError:
            # Fallback sin content_type (versiones más antiguas)
            archivo_clonado = UploadFile(
                filename=nombre_archivo,
                file=stream
            )
        
        return archivo_clonado
    
    def obtener_archivos_para_worker_desde_cache(self, cache_archivos: Dict[str, bytes]) -> List[UploadFile]:
        """
        Obtiene lista de archivos clonados para un worker específico.
        
        Args:
            cache_archivos: Cache de archivos
            
        Returns:
            List[UploadFile]: Archivos independientes para el worker
        """
        archivos_worker = []
        
        for nombre_archivo, archivo_bytes in cache_archivos.items():
            try:
                archivo_clon = self.crear_archivo_clon_para_worker(archivo_bytes, nombre_archivo)
                archivos_worker.append(archivo_clon)
            except Exception as e:
                logger.error(f" Error clonando {nombre_archivo} para worker: {e}")
                continue
        
        return archivos_worker
    
    async def _leer_archivo_seguro(self, archivo: UploadFile) -> tuple[bytes, str]:
        """
        Lectura segura de archivo con single retry para prevenir errores de "archivo sin páginas".
        
        CORREGIDO: Manejo mejorado de UploadFile para evitar falsos positivos de "archivo vacío".
        
        Returns:
            tuple: (archivo_bytes, nombre_archivo)
            
        Raises:
            ValueError: Si no se pudo leer el archivo después del retry
        """
        nombre_archivo = getattr(archivo, 'filename', 'sin_nombre')
        
        #  SINGLE RETRY como solicitado 
        for intento in range(1, 3):  # Solo 2 intentos
            try:
                # 🔧 RESETEAR POSICIÓN DE FORMA MÁS ROBUSTA
                if hasattr(archivo, 'seek'):
                    try:
                        await archivo.seek(0)
                        logger.info(f" Archivo posicionado al inicio: {nombre_archivo} - Intento {intento}")
                    except Exception as seek_error:
                        logger.warning(f" Error en seek para {nombre_archivo}: {seek_error}")
                        # Continuar de todas formas, algunos UploadFile no soportan seek
                
                # 📖 LEER CONTENIDO CON MANEJO MEJORADO
                if hasattr(archivo, 'read'):
                    archivo_bytes = await archivo.read()
                elif hasattr(archivo, 'file') and hasattr(archivo.file, 'read'):
                    # Algunos UploadFile tienen el contenido en .file
                    archivo_bytes = archivo.file.read()
                    if not isinstance(archivo_bytes, bytes):
                        archivo_bytes = archivo_bytes.encode('utf-8') if isinstance(archivo_bytes, str) else bytes(archivo_bytes)
                else:
                    # Fallback: intentar convertir directamente
                    archivo_bytes = bytes(archivo) if not isinstance(archivo, bytes) else archivo
                
                logger.info(f" Lectura completada: {nombre_archivo} - {len(archivo_bytes) if archivo_bytes else 0} bytes leídos")
                
                #  VALIDACIÓN CRÍTICA MEJORADA
                if not archivo_bytes:
                    logger.error(f"Archivo vacío en intento {intento}: {nombre_archivo} - 0 bytes")
                    if intento < 2:  # Solo un retry más
                        logger.info(f" Reintentando lectura para: {nombre_archivo}")
                        await asyncio.sleep(0.1)  # Pequeña pausa
                        continue
                    else:
                        raise ValueError(f"Archivo {nombre_archivo} está vacío después de {intento} intentos")
                
                if len(archivo_bytes) < 50:  # Reducido de 100 a 50 para ser menos restrictivo
                    logger.error(f" Archivo demasiado pequeño en intento {intento}: {nombre_archivo} ({len(archivo_bytes)} bytes)")
                    if intento < 2:
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        raise ValueError(f"Archivo {nombre_archivo} demasiado pequeño: {len(archivo_bytes)} bytes")
                
                # ✅ VALIDACIÓN ADICIONAL PARA PDFs
                if archivo_bytes.startswith(b'%PDF'):
                    logger.info(f" PDF detectado con magic bytes: {nombre_archivo}")
                elif nombre_archivo.lower().endswith('.pdf'):
                    logger.warning(f" Archivo con extensión PDF pero sin magic bytes: {nombre_archivo}")
                    # Aún así intentar procesarlo
                
                logger.info(f" Archivo leído exitosamente: {nombre_archivo} ({len(archivo_bytes):,} bytes) - Intento {intento}")
                return archivo_bytes, nombre_archivo
                
            except Exception as e:
                logger.error(f" Error leyendo archivo en intento {intento}: {e}")
                logger.error(f"Tipo de archivo: {type(archivo)}, Atributos: {dir(archivo)[:5]}...")  # Limitar debug info
                if intento < 2:  # Solo un retry más
                    await asyncio.sleep(0.2)
                    continue
                else:
                    raise ValueError(f"No se pudo leer el archivo {nombre_archivo}: {str(e)}")
        
        raise ValueError(f"Error inesperado leyendo archivo {nombre_archivo}")                
    
    async def _validar_pdf_tiene_paginas(self, pdf_bytes: bytes, nombre_archivo: str) -> bool:
        """
        Valida que el PDF tenga páginas antes de enviarlo a Gemini para prevenir error "no tiene páginas".
        
        Args:
            pdf_bytes: Contenido del PDF en bytes
            nombre_archivo: Nombre del archivo para logging
            
        Returns:
            bool: True si el PDF es válido y tiene páginas
            
        Raises:
            ValueError: Si hay error crítico en la validación
        """
        try:
            pdf_stream = BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            # 🚨 VALIDACIÓN CRÍTICA: Verificar número de páginas
            num_paginas = len(pdf_reader.pages)
            
            if num_paginas == 0:
                logger.error(f" PDF sin páginas: {nombre_archivo}")
                return False
            
            # ✅ VALIDACIÓN ADICIONAL: Verificar que al menos una página tenga contenido
            try:
                primera_pagina = pdf_reader.pages[0]
                contenido = primera_pagina.extract_text()
                
                if not contenido.strip():
                    logger.warning(f" PDF posiblemente escaneado (sin texto extraíble): {nombre_archivo}")
                    # ✅ Aún así es válido para Gemini (puede leer imágenes en PDFs)
                    logger.info(f" PDF escaneado aceptado para Gemini: {nombre_archivo}")
                else:
                    logger.info(f" PDF con texto extraíble validado: {nombre_archivo}")
                    
            except Exception as e:
                logger.warning(f" No se pudo extraer texto de {nombre_archivo}: {e}")
                # No es crítico, Gemini puede procesar PDFs sin texto extraíble
            
            # ✅ VALIDACIÓN FINAL EXITOSA
            logger.info(f" PDF validado correctamente: {nombre_archivo} - {num_paginas} páginas")
            return True
            
        except Exception as e:
            logger.error(f" Error validando PDF {nombre_archivo}: {e}")
            # 🚨 Por seguridad, considerar inválido si no se puede validar
            return False
        finally:
            # Limpiar stream
            try:
                pdf_stream.close()
            except:
                pass
    
    async def _llamar_gemini(self, prompt: str, usar_modelo_consorcio: bool = False) -> str:
        """
        Realiza llamada a Gemini con manejo de errores y timeout MEJORADO.
        
        Args:
            prompt: Prompt para enviar a Gemini
            usar_modelo_consorcio: Si usar modelo con más tokens para consorcios
            
        Returns:
            str: Respuesta de Gemini
            
        Raises:
            ValueError: Si hay error en la llamada a Gemini
        """
        try:
            # Seleccionar modelo según el caso
            modelo_a_usar = self.modelo_consorcio if usar_modelo_consorcio else self.modelo
            
            # ✅ CORREGIDO: Timeout escalonado según complejidad
            if usar_modelo_consorcio:
                timeout_segundos = 120.0  # 2 minutos para consorcios grandes
            elif "impuestos_especiales" in prompt.lower() or "estampilla" in prompt.lower():
                timeout_segundos = 90.0   # 90s para análisis de impuestos especiales
            else:
                timeout_segundos = 60.0   # 60s para análisis estándar (antes 30s)
            
            logger.info(f" Llamando a Gemini con timeout de {timeout_segundos}s")
            
            # Crear tarea con timeout
            loop = asyncio.get_event_loop()
            
            # Timeout variable según el tipo de llamada
            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None, 
                    lambda: modelo_a_usar.generate_content(prompt)
                ),
                timeout=timeout_segundos
            )
            
            if not respuesta:
                raise ValueError("Gemini devolvió respuesta None")
                
            if not hasattr(respuesta, 'text') or not respuesta.text:
                raise ValueError("Gemini devolvió respuesta sin texto")
                
            texto_respuesta = respuesta.text.strip()
            
            if not texto_respuesta:
                raise ValueError("Gemini devolvió texto vacío")
                
            logger.info(f" Respuesta de Gemini recibida: {len(texto_respuesta):,} caracteres")
            return texto_respuesta
            
        except asyncio.TimeoutError:
            # ✅ MEJORADO: Mensaje específico con timeout usado
            error_msg = f"Gemini tardó más de {timeout_segundos}s en responder"
            logger.error(f" Timeout llamando a Gemini ({timeout_segundos}s)")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f" Error llamando a Gemini: {e}")
            raise ValueError(f"Error de Gemini: {str(e)}")

    def _evaluar_tipo_recurso(self, resultado: Dict[str, Any]) -> bool:
        """
        Evalua si es tipo de recurso extranjero basado en analisis_fuente_ingreso.

        SRP: Unica responsabilidad - determinar tipo de recurso extranjero segun reglas de negocio.

        REGLA DE DECISION:
        - Si TODAS las respuestas son false (con evidencia) -> es_recurso_extranjero = true
        - Si ALGUNA respuesta es true -> es_recurso_extranjero = false
        - Si alguna respuesta es null (sin info clara) -> es_recurso_extranjero = false

        Campos evaluados de analisis_fuente_ingreso:
        - servicio_uso_colombia: Servicio usado en Colombia
        - ejecutado_en_colombia: Servicio ejecutado en Colombia
        - asistencia_tecnica_colombia: Asistencia tecnica prestada en Colombia
        - bien_ubicado_colombia: Bien ubicado fisicamente en Colombia

        Args:
            resultado: Diccionario con respuesta completa de Gemini

        Returns:
            bool: True si es facturacion extranjera, False en caso contrario

        Examples:
            >>> # Caso 1: Todo false (con evidencia) -> Extranjera
            >>> resultado = {"analisis_fuente_ingreso": {
            ...     "servicio_uso_colombia": False,
            ...     "ejecutado_en_colombia": False,
            ...     "asistencia_tecnica_colombia": False,
            ...     "bien_ubicado_colombia": False
            ... }}
            >>> self._evaluar_facturacion_extranjera(resultado)
            True

            >>> # Caso 2: Alguno true -> NO extranjera
            >>> resultado = {"analisis_fuente_ingreso": {
            ...     "servicio_uso_colombia": True,
            ...     "ejecutado_en_colombia": False,
            ...     "asistencia_tecnica_colombia": False,
            ...     "bien_ubicado_colombia": False
            ... }}
            >>> self._evaluar_facturacion_extranjera(resultado)
            False

            >>> # Caso 3: Alguno null (sin info) -> NO extranjera (conservador)
            >>> resultado = {"analisis_fuente_ingreso": {
            ...     "servicio_uso_colombia": None,
            ...     "ejecutado_en_colombia": False,
            ...     "asistencia_tecnica_colombia": False,
            ...     "bien_ubicado_colombia": False
            ... }}
            >>> self._evaluar_facturacion_extranjera(resultado)
            False
        """
        # Obtener analisis_fuente_ingreso del resultado de Gemini
        analisis = resultado.get("analisis_fuente_ingreso", {})

        # Fallback: Si no existe analisis_fuente_ingreso, usar campo legacy (compatibilidad)
        if not analisis:
            legacy_value = resultado.get("es_facturacion_extranjera", False)
            logger.warning(" analisis_fuente_ingreso no encontrado, usando valor legacy")
            return legacy_value

        # Extraer los 4 criterios de evaluacion
        servicio_uso = analisis.get("servicio_uso_colombia")
        ejecutado = analisis.get("ejecutado_en_colombia")
        asistencia = analisis.get("asistencia_tecnica_colombia")
        bien_ubicado = analisis.get("bien_ubicado_colombia")

        criterios = [servicio_uso, ejecutado, asistencia, bien_ubicado]

        # REGLA 1: Si ALGUNO es true -> NO es recurso extranjero
        if any(criterio is True for criterio in criterios):
            logger.info(" recurso NACIONAL detectada: al menos un criterio es true")
            return False

        # REGLA 2: Si ALGUNO es null -> NO es recurso extranjero (enfoque conservador)
        if any(criterio is None for criterio in criterios):
            logger.info(" recurso NACIONAL por defecto: informacion incompleta (null detectado)")
            return False

        # REGLA 3: Si TODOS son false -> ES recurso extranjero  
        if all(criterio is False for criterio in criterios):
            logger.info(" recurso EXTRANJERO confirmada: todos los criterios son false")
            logger.info(f" Evidencias: servicio_uso={servicio_uso}, ejecutado={ejecutado}, "
                       f"asistencia={asistencia}, bien_ubicado={bien_ubicado}")
            return True

        # Fallback: No deberia llegar aqui, pero por seguridad retornar False
        logger.warning(" Caso no contemplado en evaluacion, retornando False por defecto")
        return False

    def _determinar_facturacion_extranjera(self, resultado: Dict[str, Any]) -> bool:
        """
        Determina si es facturación extranjera basándose en la ubicación del proveedor.

        SRP: Responsabilidad única - evaluar si el proveedor está fuera de Colombia.

        Args:
            resultado: Resultado completo de Gemini con ubicacion_proveedor y es_fuera_colombia

        Returns:
            bool: True si es facturación extranjera, False en caso contrario
        """
        # Extraer campos de ubicación del proveedor
        ubicacion_proveedor = resultado.get("ubicacion_proveedor", "")
        es_fuera_colombia = resultado.get("es_fuera_colombia", False)

        # Mostrar ubicación en logs
        if ubicacion_proveedor:
            logger.info(f" Ubicación proveedor: {ubicacion_proveedor}")
        else:
            logger.info(" Ubicación proveedor: No especificada")

        # Determinar si es facturación extranjera
        if es_fuera_colombia:
            logger.info("🌍 Facturación extranjera detectada: Proveedor fuera de Colombia")
            return True
        else:
            logger.info("🇨🇴 Facturación nacional: Proveedor en Colombia")
            return False

    def _limpiar_respuesta_json(self, respuesta: str) -> str:
        """
        Limpia la respuesta de Gemini para extraer y corregir JSON.

        Correcciones aplicadas:
        1. Extrae JSON de bloques markdown
        2. Corrige comillas dobles duplicadas
        3. Remueve comas antes de } o ]
        4. Corrige guiones Unicode (– a -)

        Args:
            respuesta: Respuesta cruda de Gemini

        Returns:
            str: JSON limpio y corregido

        Raises:
            ValueError: Si no se puede extraer JSON válido
        """
        try:
            # PASO 1: Eliminar bloques de código markdown si existen
            if '```json' in respuesta:
                inicio_json = respuesta.find('```json') + 7
                fin_json = respuesta.find('```', inicio_json)
                if fin_json != -1:
                    respuesta = respuesta[inicio_json:fin_json].strip()

            # PASO 2: Buscar el primer { y el último }
            inicio = respuesta.find('{')
            fin = respuesta.rfind('}') + 1

            if inicio != -1 and fin != 0:
                json_limpio = respuesta[inicio:fin]

                # PASO 3: Correcciones de sintaxis JSON comunes
                # 3.1: Corregir comillas dobles duplicadas (CHOCÓ"" -> CHOCÓ")
                import re
                json_limpio = re.sub(r'""', '"', json_limpio)

                # 3.2: Remover comas antes de cierre de objeto o array
                json_limpio = re.sub(r',\s*}', '}', json_limpio)  # , } -> }
                json_limpio = re.sub(r',\s*]', ']', json_limpio)  # , ] -> ]

                # 3.3: Corregir guiones Unicode (– a -)
                json_limpio = json_limpio.replace('–', '-')

                # PASO 4: Verificar que sea JSON válido
                json.loads(json_limpio)
                logger.info(" JSON limpio y validado correctamente")
                return json_limpio
            else:
                raise ValueError("No se encontró JSON válido en la respuesta")

        except json.JSONDecodeError as e:
            # Intentar correcciones adicionales
            logger.warning(f"Error de sintaxis JSON: {e}")
            logger.warning(f"JSON problemático (primeros 500 chars): {json_limpio[:500] if 'json_limpio' in locals() else respuesta[:500]}")

            try:
                # Intento de corrección agresiva: remover líneas problemáticas
                if 'json_limpio' in locals():
                    logger.info(" Intentando corrección agresiva de JSON...")
                    # Remover saltos de línea y espacios extras
                    json_limpio_agresivo = ' '.join(json_limpio.split())
                    json.loads(json_limpio_agresivo)
                    logger.info(" Corrección agresiva exitosa")
                    return json_limpio_agresivo
            except:
                pass

            # Si todo falla, devolver respuesta original
            logger.error(" No se pudo corregir el JSON, usando respuesta original")
            return respuesta

        except Exception as e:
            logger.error(f" Error limpiando JSON: {e}")
            return respuesta

    def _reparar_json_malformado(self, json_str: str) -> str:
        """
        Repara errores comunes en JSON generado por Gemini.

        Args:
            json_str: JSON string potencialmente malformado

        Returns:
            str: JSON string reparado
        """
        try:
            # Reparaciones comunes para errores de Gemini
            json_reparado = json_str

            # 1. Reparar llaves faltantes al final de objetos en arrays
            # Buscar patrones como: "valor": 123.45, seguido directamente por {
            import re

            # Patrón: número o string seguido de coma y luego { (falta })
            patron_llave_faltante = r'(\"[^\"]+\":\s*[0-9.]+)\s*,\s*\n\s*\{'
            coincidencias = list(re.finditer(patron_llave_faltante, json_reparado))

            # Reparar desde el final hacia el inicio para no afectar posiciones
            for match in reversed(coincidencias):
                inicio = match.start()
                fin = match.end()
                # Insertar } antes de la coma
                posicion_coma = json_reparado.find(',', inicio)
                if posicion_coma != -1:
                    json_reparado = json_reparado[:posicion_coma] + '\n    }' + json_reparado[posicion_coma:]

            # 2. Reparar números de punto flotante malformados
            # Convertir 3.5000000000000004 a 3.5
            patron_float_largo = r'(\d+\.\d{10,})'
            def reparar_float(match):
                numero = float(match.group(1))
                return str(round(numero, 2))

            json_reparado = re.sub(patron_float_largo, reparar_float, json_reparado)

            # 3. Verificar si el JSON es válido ahora
            json.loads(json_reparado)
            logger.info("✅ JSON reparado exitosamente")
            return json_reparado

        except json.JSONDecodeError as e:
            logger.warning(f"No se pudo reparar JSON: {e}")
            return json_str
        except Exception as e:
            logger.error(f"Error reparando JSON: {e}")
            return json_str

    # ✅ ELIMINADA: Función _es_respuesta_truncada - Ya no necesaria con modelo mejorado
    
    def _clasificacion_fallback(self, textos_archivos: Dict[str, str]) -> Dict[str, str]:
        """
        Clasificación de emergencia basada en nombres de archivo.
        
        Args:
            textos_archivos: Diccionario con textos de archivos
            
        Returns:
            Dict[str, str]: Clasificación basada en nombres
        """
        resultado = {}
        
        for nombre_archivo in textos_archivos.keys():
            nombre_lower = nombre_archivo.lower()
            
            if 'factura' in nombre_lower or 'fact' in nombre_lower:
                resultado[nombre_archivo] = "FACTURA"
            elif 'rut' in nombre_lower:
                resultado[nombre_archivo] = "RUT"
            elif 'cotiz' in nombre_lower or 'presupuesto' in nombre_lower:
                resultado[nombre_archivo] = "COTIZACION"
            elif 'contrato' in nombre_lower :
                resultado[nombre_archivo] = "ANEXO CONCEPTO DE CONTRATO"
            else:
                resultado[nombre_archivo] = "ANEXO"
        
        logger.warning("Usando clasificación fallback basada en nombres de archivo")
        return resultado

    # ===============================
    # NOTA: Funciones auxiliares de conceptos de retefuente movidas a clasificador_retefuente.py
    # Funciones movidas: _analisis_fallback, _obtener_conceptos_retefuente, _conceptos_hardcodeados,
    # _obtener_conceptos_completos, _conceptos_completos_hardcodeados, _obtener_conceptos_extranjeros,
    # _obtener_conceptos_extranjeros_simplificado, _conceptos_extranjeros_simplificados_hardcodeados,
    # _obtener_paises_convenio, _paises_convenio_hardcodeados, _obtener_preguntas_fuente_nacional,
    # _preguntas_fuente_hardcodeadas, _conceptos_extranjeros_hardcodeados
    # ===============================

    # ===============================
    # NOTA: Lógica de consorcios movida a clasificador_consorcio.py
    # Funciones movidas: analizar_consorcio (implementación completa), _consorcio_fallback
    # ===============================
    
  
    
    async def _guardar_respuesta(self, nombre_archivo: str, contenido: dict):
        """
        Guarda la respuesta de Gemini en archivo JSON en la carpeta Results.
        
        Args:
            nombre_archivo: Nombre del archivo JSON
            contenido: Contenido a guardar
        """
        try:
            # ✅ CORREGIDO: Usar rutas absolutas para evitar errores de subpath
            directorio_base = Path.cwd()  # Directorio actual del proyecto
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            
            # Crear carpeta Results en el directorio base
            carpeta_results = directorio_base / "Results" / fecha_hoy
            carpeta_results.mkdir(parents=True, exist_ok=True)
            
            # Generar timestamp para nombre único
            timestamp = datetime.now().strftime("%H-%M-%S")
            nombre_base = nombre_archivo.replace('.json', '')
            nombre_final = f"{nombre_base}_{timestamp}.json"
            
            # Guardar archivo con ruta absoluta
            ruta_archivo = carpeta_results / nombre_final
            
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(contenido, f, indent=2, ensure_ascii=False)
            
            logger.info(f" Respuesta guardada en {ruta_archivo}")
            
        except Exception as e:
            logger.error(f" Error guardando respuesta: {e}")
            # Fallback mejorado: usar directorio actual
            try:
                timestamp = datetime.now().strftime("%H-%M-%S")
                nombre_fallback = f"fallback_{nombre_archivo.replace('.json', '')}_{timestamp}.json"
                ruta_fallback = Path.cwd() / nombre_fallback
                
                with open(ruta_fallback, "w", encoding="utf-8") as f:
                    json.dump(contenido, f, indent=2, ensure_ascii=False)
                
                logger.info(f" Respuesta guardada en fallback: {ruta_fallback}")
                
            except Exception as e2:
                logger.error(f" Error guardando fallback: {e2}")
    
 

    # ===============================
    # ✅ NUEVA FUNCIONALIDAD: ANÁLISIS DE IVA Y RETEIVA
    # ===============================

    async def analizar_iva(self, documentos_clasificados: Dict[str, Dict], archivos_directos: List[UploadFile] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
        Nueva funcionalidad: Análisis especializado de IVA y ReteIVA CON CACHE.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            archivos_directos: Lista de archivos directos (para compatibilidad)
            cache_archivos: Cache de archivos para workers paralelos
            
            
        Returns:
            Dict[str, Any]: Análisis completo de IVA y ReteIVA
            
        Raises:
            ValueError: Si hay error en el procesamiento
        """
        logger.info(" Analizando IVA y ReteIVA con Gemini")
        
        # 💾 USAR CACHE SI ESTÁ DISPONIBLE
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f" IVA usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" IVA usando archivos directos originales: {len(archivos_directos)} archivos")
        
        try:
            # Extraer documentos por categoría
            factura_texto = ""
            rut_texto = ""
            anexos_texto = ""
            cotizaciones_texto = ""
            anexo_contrato = ""
            
            for nombre_archivo, info in documentos_clasificados.items():
                if info["categoria"] == "FACTURA":
                    factura_texto = info["texto"]
                    logger.info(f" Factura encontrada para análisis IVA: {nombre_archivo}")
                elif info["categoria"] == "RUT":
                    rut_texto = info["texto"]
                    logger.info(f" RUT encontrado para análisis IVA: {nombre_archivo}")
                elif info["categoria"] == "ANEXO":
                    anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "COTIZACION":
                    cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                    anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
            
                    #  VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)

            hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
            nombres_archivos_directos = [archivo.filename for archivo in archivos_directos]
            posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
            
            if not factura_texto and not posibles_facturas_directas:
                raise ValueError("No se encontró una FACTURA en los documentos para análisis de IVA")

            logger.info(f"Factura encontrada para analisis IVA")
            for archivo in archivos_directos:
                try:
                    if hasattr(archivo, 'filename') and archivo.filename:
                        nombres_archivos_directos.append(archivo.filename)
                    else:
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                except Exception as e:
                    logger.warning(f" Error obteniendo nombre de archivo: {e}")
                    nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")

            # Generar prompt especializado de IVA
            prompt = PROMPT_ANALISIS_IVA(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nombres_archivos_directos=nombres_archivos_directos
            )
            
            # Llamar a Gemini
            respuesta = await self._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            logger.info(f"Respuesta análisis IVA: {respuesta[:500]}...")
            
            # Limpiar respuesta
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_iva_reteiva.json", resultado)
            
            # Validar estructura NUEVA del PROMPT_ANALISIS_IVA (v2.0 - SOLID)
            campos_requeridos = ["extraccion_rut", "extraccion_factura", "clasificacion_concepto", "validaciones"]
            campos_faltantes = [campo for campo in campos_requeridos if campo not in resultado]

            if campos_faltantes:
                logger.warning(f" Campos faltantes en respuesta de IVA: {campos_faltantes}")
                # Agregar campos por defecto para los faltantes
                for campo in campos_faltantes:
                    resultado[campo] = self._obtener_campo_iva_default_v2(campo)

            # Extraer información clave para logging (NUEVA ESTRUCTURA)
            extraccion_factura = resultado.get("extraccion_factura", {})
            extraccion_rut = resultado.get("extraccion_rut", {})
            validaciones = resultado.get("validaciones", {})

            valor_iva = extraccion_factura.get("valor_iva", 0.0)
            es_responsable_iva = extraccion_rut.get("es_responsable_iva")
            rut_disponible = validaciones.get("rut_disponible", False)

            logger.info(f" Análisis IVA completado (v2.0 SOLID):")
            logger.info(f"   - Valor IVA: ${valor_iva:,.2f}")
            logger.info(f"   - Responsable IVA: {es_responsable_iva}")
            logger.info(f"   - RUT disponible: {rut_disponible}")

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f" Error parseando JSON de análisis IVA: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._iva_fallback("Error parseando respuesta JSON de Gemini")
        except Exception as e:
            logger.error(f" Error en análisis de IVA: {e}")
            return self._iva_fallback(str(e))
    
    def _obtener_campo_iva_default(self, campo: str) -> Dict[str, Any]:
        """
        Obtiene valores por defecto para campos faltantes en análisis de IVA.
        
        Args:
            campo: Nombre del campo faltante
            
        Returns:
            Dict con estructura por defecto
        """
        defaults = {
            "analisis_iva": {
                "iva_identificado": {
                    "tiene_iva": False,
                    "valor_iva_total": 0.0,
                    "porcentaje_iva": 0.0,
                    "detalle_conceptos_iva": [],
                    "metodo_identificacion": "no_identificado"
                },
                "responsabilidad_iva_rut": {
                    "rut_disponible": False,
                    "es_responsable_iva": None,
                    "codigo_encontrado": "no_encontrado",
                    "texto_referencia": "No disponible"
                },
                "concepto_facturado": {
                    "descripcion": "No identificado",
                    "aplica_iva": False,
                    "razon_exencion_exclusion": "No determinado",
                    "categoria": "no_identificado"
                }
            },
            "analisis_fuente_ingreso": {
                "validaciones_fuente": {
                    "uso_beneficio_colombia": False,
                    "ejecutado_en_colombia": False,
                    "asistencia_tecnica_colombia": False,
                    "bien_ubicado_colombia": False
                },
                "es_fuente_nacional": True,
                "validacion_iva_extranjero": {
                    "es_extranjero": False,
                    "iva_esperado_19": False,
                    "iva_encontrado": 0.0
                }
            },
            "calculo_reteiva": {
                "aplica_reteiva": False,
                "porcentaje_reteiva": "0%",
                "tarifa_decimal": 0.0,
                "valor_reteiva_calculado": 0.0,
                "metodo_calculo": "no_aplica"
            },
            "estado_liquidacion": {
                "estado": "Error en procesamiento",
                "observaciones": ["Campo faltante en respuesta de Gemini"]
            }
        }
        
        return defaults.get(campo, {})

    def _obtener_campo_iva_default_v2(self, campo: str) -> Dict[str, Any]:
        """
        Obtiene valores por defecto para campos faltantes en análisis de IVA v2.0 (SOLID).

        Nueva estructura del PROMPT_ANALISIS_IVA refactorizado.

        Args:
            campo: Nombre del campo faltante

        Returns:
            Dict con estructura por defecto v2.0
        """
        defaults = {
            "extraccion_rut": {
                "es_responsable_iva": None,
                "codigo_encontrado": 0.0,
                "texto_evidencia": "No disponible"
            },
            "extraccion_factura": {
                "valor_iva": 0.0,
                "porcentaje_iva": 0,
                "valor_subtotal_sin_iva": 0.0,
                "valor_total_con_iva": 0.0,
                "concepto_facturado": "No identificado"
            },
            "clasificacion_concepto": {
                "categoria": "no_clasificado",
                "justificacion": "Campo faltante en respuesta de Gemini",
                "coincidencia_encontrada": ""
            },
            "validaciones": {
                "rut_disponible": False
            }
        }

        return defaults.get(campo, {})

    def _iva_fallback(self, error_msg: str = "Error procesando IVA") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de IVA v2.0 (SOLID).

        Retorna estructura compatible con PROMPT_ANALISIS_IVA refactorizado.

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica de IVA con nueva estructura v2.0
        """
        logger.warning(f"Usando fallback de IVA v2.0 (SOLID): {error_msg}")

        return {
            "extraccion_rut": {
                "es_responsable_iva": None,
                "codigo_encontrado": 0.0,
                "texto_evidencia": f"Error en procesamiento: {error_msg}"
            },
            "extraccion_factura": {
                "valor_iva": 0.0,
                "porcentaje_iva": 0,
                "valor_subtotal_sin_iva": 0.0,
                "valor_total_con_iva": 0.0,
                "concepto_facturado": "Error en identificación"
            },
            "clasificacion_concepto": {
                "categoria": "error",
                "justificacion": f"Error en análisis: {error_msg}",
                "coincidencia_encontrada": ""
            },
            "validaciones": {
                "rut_disponible": False
            },
            "tipo_procesamiento": "IVA_FALLBACK_v2.0",
            "error": error_msg,
            "observaciones": [
                f"Error procesando IVA: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique responsabilidad de IVA en el RUT",
                "Valide conceptos facturados y aplicabilidad de IVA"
            ]
        }
    
    # ===============================
    # 🆕 NUEVA FUNCIONALIDAD: ANÁLISIS DE ESTAMPILLAS GENERALES
    # ===============================

    async def analizar_estampillas_generales(self, documentos_clasificados: Dict[str, Dict], archivos_directos: list[UploadFile] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
         Nueva funcionalidad: Análisis de 6 Estampillas Generales.
        
        Analiza documentos para identificar información de estampillas:
        - Procultura
        - Bienestar
        - Adulto Mayor
        - Prouniversidad Pedagógica
        - Francisco José de Caldas
        - Prodeporte
        
        Solo identificación, NO cálculos.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            
        Returns:
            Dict[str, Any]: Análisis completo de estampillas generales
            
        Raises:
            ValueError: Si hay error en el procesamiento
        """
        logger.info(" Analizando 6 estampillas generales con Gemini")
        
        #  USAR CACHE SI ESTÁ DISPONIBLE (igual que otras funciones)
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f" Estampillas generales usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" Estampillas generales usando archivos directos originales: {len(archivos_directos)} archivos")
        
        try:
            # Extraer documentos por categoría
            factura_texto = ""
            rut_texto = ""
            anexos_texto = ""
            cotizaciones_texto = ""
            anexo_contrato = ""
            
            for nombre_archivo, info in documentos_clasificados.items():
                if info["categoria"] == "FACTURA":
                    factura_texto = info["texto"]
                    logger.info(f" Factura encontrada para análisis estampillas: {nombre_archivo}")
                elif info["categoria"] == "RUT":
                    rut_texto = info["texto"]
                    logger.info(f" RUT encontrado para análisis estampillas: {nombre_archivo}")
                elif info["categoria"] == "ANEXO":
                    anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "COTIZACION":
                    cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                    anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
            
            #  VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)
            hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
            
            # 💾 OBTENER NOMBRES DE ARCHIVOS (compatible con cache)
            nombres_archivos_directos = []
            if archivos_directos:
                for archivo in archivos_directos:
                    try:
                        if hasattr(archivo, 'filename') and archivo.filename:
                            nombres_archivos_directos.append(archivo.filename)
                        else:
                            nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                    except Exception as e:
                        logger.warning(f" Error obteniendo nombre de archivo: {e}")
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
            
            posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
            
            if not hay_factura_texto and not posibles_facturas_directas:
                raise ValueError("No se encontró una FACTURA en los documentos para análisis de estampillas")
            logger.info(f"Factura encontrada para análisis estampillas generales")
            
            # Generar prompt especializado de estampillas generales
            prompt = PROMPT_ANALISIS_ESTAMPILLAS_GENERALES(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nombres_archivos_directos=nombres_archivos_directos
            )
            
            # Llamar a Gemini
            respuesta = await self._llamar_gemini_hibrido_factura(prompt,archivos_directos)
            logger.info(f" Respuesta análisis estampillas: {respuesta[:500]}...")
            
            # Limpiar respuesta
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_estampillas_generales.json", resultado)
            
            # Validar estructura mínima requerida
            if "estampillas_generales" not in resultado:
                logger.warning(" Campo 'estampillas_generales' no encontrado en respuesta")
                resultado["estampillas_generales"] = self._obtener_estampillas_default()

            # Extraer información clave para logging (usar resumen interno si existe)
            estampillas_data = resultado.get("estampillas_generales", [])
            resumen_data = resultado.get("resumen_analisis", {})

            # Si no hay resumen en la respuesta de Gemini, generarlo solo para logging
            if not resumen_data:
                resumen_data = self._obtener_resumen_default(estampillas_data)

            total_identificadas = resumen_data.get("total_estampillas_identificadas", 0)
            completas = resumen_data.get("estampillas_completas", 0)
            incompletas = resumen_data.get("estampillas_incompletas", 0)

            logger.info(f" Análisis estampillas completado: {total_identificadas} identificadas, {completas} completas, {incompletas} incompletas")

            # Eliminar resumen_analisis del resultado final - solo se usa internamente para logging
            if "resumen_analisis" in resultado:
                del resultado["resumen_analisis"]

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f" Error parseando JSON de análisis estampillas: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._estampillas_fallback("Error parseando respuesta JSON de Gemini")
        except Exception as e:
            logger.error(f" Error en análisis de estampillas: {e}")
            return self._estampillas_fallback(str(e))
    
    def _obtener_estampillas_default(self) -> List[Dict[str, Any]]:
        """
        Obtiene estructura por defecto para las 6 estampillas generales.
        
        Returns:
            List con estructura por defecto de las 6 estampillas
        """
        estampillas_nombres = [
            "Procultura",
            "Bienestar", 
            "Adulto Mayor",
            "Prouniversidad Pedagógica",
            "Francisco José de Caldas",
            "Prodeporte"
        ]
        
        return [
            {
                "nombre_estampilla": nombre,
                "porcentaje": None,
                "valor": None,
                "estado": "no_aplica_impuesto",
                "texto_referencia": None,
                "observaciones": "Error en procesamiento - no se pudo analizar"
            }
            for nombre in estampillas_nombres
        ]
    
    def _obtener_resumen_default(self, estampillas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Genera resumen por defecto basado en lista de estampillas.
        
        Args:
            estampillas: Lista de estampillas procesadas
            
        Returns:
            Dict con resumen por defecto
        """
        total = len(estampillas)
        completas = sum(1 for e in estampillas if e.get("estado") == "preliquidado")
        incompletas = sum(1 for e in estampillas if e.get("estado") == "preliquidacion_sin_finalizar")
        no_aplican = sum(1 for e in estampillas if e.get("estado") == "no_aplica_impuesto")
        
        return {
            "total_estampillas_identificadas": completas + incompletas,
            "estampillas_completas": completas,
            "estampillas_incompletas": incompletas,
            "estampillas_no_aplican": no_aplican,
            "documentos_revisados": ["FACTURA", "ANEXOS", "ANEXO_CONTRATO", "RUT"]
        }
    
    def _estampillas_fallback(self, error_msg: str = "Error procesando estampillas") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de estampillas.

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica de estampillas
        """
        logger.warning(f"Usando fallback de estampillas: {error_msg}")

        estampillas_default = self._obtener_estampillas_default()

        return {
            "estampillas_generales": estampillas_default,
            "tipo_procesamiento": "ESTAMPILLAS_FALLBACK",
            "error": error_msg,
            "observaciones": [
                f"Error procesando estampillas: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique si los documentos contienen información de estampillas",
                "Busque menciones de: Procultura, Bienestar, Adulto Mayor, Universidad Pedagógica, Caldas, Prodeporte"
            ]
        }

    async def analizar_tasa_prodeporte(
        self,
        documentos_clasificados: Dict[str, Dict],
        archivos_directos: list[UploadFile] = None,
        cache_archivos: Dict[str, bytes] = None,
        observaciones_tp: str = None
    ) -> Dict[str, Any]:
        """
        Analiza documentos para extracción de datos de Tasa Prodeporte usando Gemini AI.

        ARQUITECTURA: Separación IA-Validación
        - Gemini: SOLO extrae datos (factura, IVA, menciones, municipio)
        - Python: Realiza todas las validaciones y cálculos (en liquidador_TP.py)

        SRP: Solo coordina el análisis con Gemini para Tasa Prodeporte

        Args:
            documentos_clasificados: Diccionario de documentos clasificados
            archivos_directos: Lista de archivos directos para procesamiento multimodal
            cache_archivos: Cache de archivos para workers paralelos
            observaciones_tp: Observaciones del usuario (opcional)

        Returns:
            Dict con análisis de Gemini: {
                "factura_con_iva": float,
                "factura_sin_iva": float,
                "iva": float,
                "aplica_tasa_prodeporte": bool,
                "texto_mencion_tasa": str,
                "municipio_identificado": str,
                "texto_municipio": str
            }
        """
        logger.info("Analizando Tasa Prodeporte con Gemini AI...")

        # USAR CACHE SI ESTÁ DISPONIBLE (igual que estampillas_generales)
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f"Tasa Prodeporte usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f"Tasa Prodeporte usando archivos directos originales: {len(archivos_directos)} archivos")

        try:
            # Extraer textos de documentos clasificados
            factura_texto = ""
            anexos_texto = ""

            for nombre_archivo, datos_doc in documentos_clasificados.items():
                categoria = datos_doc.get("categoria", "")
                texto = datos_doc.get("texto", "")

                if categoria == "FACTURA":
                    factura_texto += f"\n=== {nombre_archivo} ===\n{texto}\n"
                    logger.info(f"Factura encontrada para análisis Tasa Prodeporte: {nombre_archivo}")
                elif categoria in ["ANEXO", "ANEXO_CONTRATO", "ANEXO CONCEPTO CONTRATO"]:
                    anexos_texto += f"\n=== {nombre_archivo} ===\n{texto}\n"

            # Normalizar textos vacíos
            factura_texto = factura_texto.strip() if factura_texto else "NO DISPONIBLE"
            anexos_texto = anexos_texto.strip() if anexos_texto else "NO DISPONIBLE"

            # Obtener nombres de archivos directos (compatible con cache)
            nombres_archivos_directos = []
            if archivos_directos:
                for archivo in archivos_directos:
                    try:
                        if hasattr(archivo, 'filename') and archivo.filename:
                            nombres_archivos_directos.append(archivo.filename)
                        else:
                            nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                    except Exception as e:
                        logger.warning(f"Error obteniendo nombre de archivo: {e}")
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")

            # Generar prompt especializado
            from prompts.prompt_tasa_prodeporte import PROMPT_ANALISIS_TASA_PRODEPORTE

            prompt = PROMPT_ANALISIS_TASA_PRODEPORTE(
                factura_texto=factura_texto,
                anexos_texto=anexos_texto,
                observaciones_texto=observaciones_tp if observaciones_tp else "",
                nombres_archivos_directos=nombres_archivos_directos
            )

            logger.info(f"Prompt generado para Tasa Prodeporte ({len(prompt)} caracteres)")

            # Llamar a Gemini con soporte multimodal
            respuesta = await self._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            logger.info(f"Respuesta análisis Tasa Prodeporte: {respuesta[:500]}...")

            # Limpiar respuesta
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)

            # Parsear JSON
            analisis_dict = json.loads(respuesta_limpia)

            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_tasa_prodeporte.json", analisis_dict)

            # Validar estructura esperada
            campos_esperados = [
                "factura_con_iva", "factura_sin_iva", "iva",
                "aplica_tasa_prodeporte", "texto_mencion_tasa",
                "municipio_identificado", "texto_municipio"
            ]

            campos_faltantes = [campo for campo in campos_esperados if campo not in analisis_dict]

            if campos_faltantes:
                logger.warning(f"Campos faltantes en análisis Tasa Prodeporte: {campos_faltantes}")
                # Agregar campos faltantes con valores por defecto
                for campo in campos_faltantes:
                    if campo in ["factura_con_iva", "factura_sin_iva", "iva"]:
                        analisis_dict[campo] = 0.0
                    elif campo == "aplica_tasa_prodeporte":
                        analisis_dict[campo] = False
                    else:
                        analisis_dict[campo] = ""

            logger.info(f"Análisis Tasa Prodeporte completado:")
            logger.info(f"- Factura sin IVA: ${analisis_dict.get('factura_sin_iva', 0):,.2f}")
            logger.info(f"- Aplica Tasa Prodeporte: {analisis_dict.get('aplica_tasa_prodeporte', False)}")
            logger.info(f"- Municipio identificado: {analisis_dict.get('municipio_identificado', 'N/A')}")

            return analisis_dict

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Tasa Prodeporte: {e}")
            logger.error(f"Respuesta recibida: {respuesta_limpia[:500]}...")

            # Retornar estructura por defecto
            return {
                "factura_con_iva": 0.0,
                "factura_sin_iva": 0.0,
                "iva": 0.0,
                "aplica_tasa_prodeporte": False,
                "texto_mencion_tasa": "",
                "municipio_identificado": "",
                "texto_municipio": "",
                "error": f"Error parseando respuesta de Gemini: {str(e)}"
            }

        except Exception as e:
            logger.error(f"Error analizando Tasa Prodeporte: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Retornar estructura por defecto en caso de error
            return {
                "factura_con_iva": 0.0,
                "factura_sin_iva": 0.0,
                "iva": 0.0,
                "aplica_tasa_prodeporte": False,
                "texto_mencion_tasa": "",
                "municipio_identificado": "",
                "texto_municipio": "",
                "error": f"Error técnico: {str(e)}"
            }
