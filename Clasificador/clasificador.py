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

# ✅ NUEVAS IMPORTACIONES PARA VALIDACIÓN ROBUSTA DE PDF
import PyPDF2
from io import BytesIO

# Configuración de logging
logger = logging.getLogger(__name__)

# Importar prompts
from .prompt_clasificador import (
    PROMPT_CLASIFICACION, 
    PROMPT_ANALISIS_FACTURA, 
    PROMPT_ANALISIS_CONSORCIO,
    PROMPT_ANALISIS_FACTURA_EXTRANJERA,
    PROMPT_ANALISIS_CONSORCIO_EXTRANJERO,
    PROMPT_ANALISIS_IVA,  # ✅ NUEVO PROMPT IVA
    PROMPT_ANALISIS_ESTAMPILLAS_GENERALES  # 🆕 NUEVO PROMPT ESTAMPILLAS GENERALES
)

# v3.1.2: Procesador de consorcios removido - Se usa liquidador_consorcios.py directamente
# from .consorcio_processor import ProcesadorConsorcios

# ===============================
# MODELOS DE DATOS LOCALES
# ===============================

class ConceptoIdentificado(BaseModel):
    concepto: str
    tarifa_retencion: float
    base_gravable: Optional[float] = None

class NaturalezaTercero(BaseModel):
    es_persona_natural: Optional[bool] = None
    regimen_tributario: Optional[str] = None  # SIMPLE, ORDINARIO, ESPECIAL
    es_autorretenedor: Optional[bool] = None
    es_responsable_iva: Optional[bool] = None  # NUEVA VALIDACIÓN

# NUEVOS MODELOS PARA ARTÍCULO 383 - ESTRUCTURA ACTUALIZADA PARA GEMINI

# 🆕 MODELO PARA CONCEPTOS IDENTIFICADOS EN ART 383
class ConceptoIdentificadoArt383(BaseModel):
    """Concepto identificado específico para Artículo 383"""
    concepto: str
    base_gravable: float = 0.0

# 🆕 MODELO ACTUALIZADO PARA CONDICIONES ART 383
class CondicionesArticulo383(BaseModel):
    """Condiciones cumplidas para aplicar Artículo 383 - NUEVA ESTRUCTURA"""
    es_persona_natural: bool = False
    conceptos_identificados: List[ConceptoIdentificadoArt383] = []
    conceptos_aplicables: bool = False
    ingreso: float = 0.0
    es_primer_pago: bool = False
    documento_soporte: bool = False

# 🆕 MODELO PARA INTERESES POR VIVIENDA
class InteresesVivienda(BaseModel):
    """Información de intereses por vivienda"""
    intereses_corrientes: float = 0.0
    certificado_bancario: bool = False

# 🆕 MODELO PARA DEPENDIENTES ECONÓMICOS
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

# 🆕 MODELO ACTUALIZADO PARA DEDUCCIONES ART 383
class DeduccionesArticulo383(BaseModel):
    """Deducciones identificadas para Artículo 383 - NUEVA ESTRUCTURA"""
    intereses_vivienda: InteresesVivienda = InteresesVivienda()
    dependientes_economicos: DependientesEconomicos = DependientesEconomicos()
    medicina_prepagada: MedicinaPrepagada = MedicinaPrepagada()
    AFC: AFCInfo = AFCInfo()
    planilla_seguridad_social: PlanillaSeguridadSocial = PlanillaSeguridadSocial()

# 🆕 MODELO ACTUALIZADO PARA INFORMACIÓN ART 383
class InformacionArticulo383(BaseModel):
    """Información completa del Artículo 383 - NUEVA ESTRUCTURA SIN CÁLCULO"""
    # NOTA: Ya no hay campo 'aplica' porque Python decide eso ahora
    condiciones_cumplidas: CondicionesArticulo383 = CondicionesArticulo383()
    deducciones_identificadas: DeduccionesArticulo383 = DeduccionesArticulo383()
    # ELIMINADO: calculo - Gemini ya no calcula, solo identifica

class AnalisisFactura(BaseModel):
    aplica_retencion: bool
    conceptos_identificados: List[ConceptoIdentificado]
    naturaleza_tercero: Optional[NaturalezaTercero]
    articulo_383: Optional[InformacionArticulo383] = None  # 🆕 NUEVO CAMPO SINCRONIZADO
    es_facturacion_exterior: bool
    valor_total: Optional[float]
    iva: Optional[float]
    observaciones: List[str]

# ===============================
# PROCESADOR GEMINI
# ===============================

class ProcesadorGemini:
    """Maneja las llamadas a la API de Gemini para clasificación y análisis"""
    
    def __init__(self):
        """Inicializa el procesador con configuración de Gemini"""
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
            'gemini-2.5-flash',
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
        
        logger.info("ProcesadorGemini inicializado correctamente")

        # v3.1.2: Procesador de consorcios removido - Nueva arquitectura SOLID con liquidador_consorcios.py
    
    async def clasificar_documentos(
        self, 
        textos_archivos_o_directos = None,  #  COMPATIBILIDAD TOTAL: Acepta cualquier tipo
        archivos_directos: List[UploadFile] = None,  #  NUEVO: Archivos directos
        textos_preprocesados: Dict[str, str] = None  #  NUEVO: Textos preprocesados
    ) -> Tuple[Dict[str, str], bool, bool]:
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
        
        # ✅ VALIDACIÓN: Límite de archivos directos (20)
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
        
        # ✅ VALIDACIÓN: Al menos un archivo debe estar presente
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
            
            # PASO 2: Generar prompt híbrido usando función modificada
            prompt = PROMPT_CLASIFICACION(textos_preprocesados, nombres_archivos_directos)
            
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
            
            # Detectar facturación extranjera
            es_facturacion_extranjera = resultado.get("es_facturacion_extranjera", False)
            indicadores_extranjera = resultado.get("indicadores_extranjera", [])
            
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
            logger.info(f" Facturación extranjera detectada: {es_facturacion_extranjera}")
            if es_facturacion_extranjera and indicadores_extranjera:
                logger.info(f" Indicadores extranjera: {indicadores_extranjera}")
            
            # PASO 8: Logging detallado por archivo
            for nombre_archivo, categoria in clasificacion.items():
                origen = "DIRECTO" if nombre_archivo in nombres_archivos_directos else "PREPROCESADO"
                logger.info(f" {nombre_archivo} → {categoria} ({origen})")
            
            return clasificacion, es_consorcio, es_facturacion_extranjera
            
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

   
    async def analizar_factura(
        self, 
        documentos_clasificados: Dict[str, Dict], 
        es_facturacion_extranjera: bool = False,
        archivos_directos: List[UploadFile] = None,  #  NUEVO: Soporte multimodal
        cache_archivos: Dict[str, bytes] = None  #  NUEVO: Cache para workers paralelos
    ) -> AnalisisFactura:
        """
         ANÁLISIS HÍBRIDO MULTIMODAL: Analizar factura con archivos directos + textos preprocesados.
        
        FUNCIONALIDAD HÍBRIDA CON CACHE:
         Archivos directos (PDFs/imágenes): Enviados nativamente a Gemini
         Textos preprocesados: Documentos ya extraidos localmente
         Cache para workers: Solución a problemas de concurrencia en workers paralelos
         Combinación inteligente: Una sola llamada con contenido mixto
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera (usa prompts especializados)
            archivos_directos: Lista de archivos para envío directo a Gemini (PDFs/imágenes)
            cache_archivos: Cache de archivos para workers paralelos (evita problemas de concurrencia)
            
        Returns:
            AnalisisFactura: Análisis completo de la factura
            
        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        #  LOGGING HÍBRIDO CON CACHE: Identificar estrategia de procesamiento
        archivos_directos = archivos_directos or []
        cache_archivos = cache_archivos or {}
        
        #  USAR CACHE SI ESTÁ DISPONIBLE (para workers paralelos)
        if cache_archivos:
            logger.info(f" Usando cache de archivos para análisis (workers paralelos): {len(cache_archivos)} archivos")
            archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
            total_archivos_directos = len(archivos_directos)
        else:
            total_archivos_directos = len(archivos_directos)
            logger.info(f" Usando archivos directos originales (sin cache): {total_archivos_directos} archivos")
        
        total_textos_preprocesados = len(documentos_clasificados)
        
        if total_archivos_directos > 0:
            logger.info(f" Analizando factura HÍBRIDO: {total_archivos_directos} directos + {total_textos_preprocesados} preprocesados")
        else:
            logger.info(f" Analizando factura TRADICIONAL: {total_textos_preprocesados} textos preprocesados")
        
        # Extraer documentos por categoría
        factura_texto = ""
        rut_texto = ""
        anexos_texto = ""
        cotizaciones_texto = ""
        anexo_contrato = ""
        
        for nombre_archivo, info in documentos_clasificados.items():
            if info["categoria"] == "FACTURA":
                factura_texto = info["texto"]
                logger.info(f"Factura encontrada: {nombre_archivo}")
                logger.info(f"Extracto factura: {factura_texto[:30]}")
            elif info["categoria"] == "RUT":
                rut_texto = info["texto"]
                logger.info(f"RUT encontrado: {nombre_archivo}")
                logger.info(f"Extracto RUT: {rut_texto[:30]}")  
            elif info["categoria"] == "ANEXO":
                anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                logger.info(f"Anexo encontrado: {nombre_archivo}")
                logger.info(f"Extracto anexo: {info['texto'][:30]}")
            elif info["categoria"] == "COTIZACION":
                cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                logger.info(f"Cotización encontrada: {nombre_archivo}")
                logger.info(f"Extracto cotización: {info['texto'][:30]}")
            elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
                logger.info(f"Anexo concepto de contrato encontrado: {nombre_archivo}")
                logger.info(f"Extracto anexo concepto de contrato: {info['texto'][:30]}")

        #  VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)
        hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
        nombres_archivos_directos = [archivo.filename for archivo in archivos_directos]
        posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
        
        if not hay_factura_texto and not posibles_facturas_directas:
            raise ValueError("No se encontró una FACTURA en los documentos (ni texto ni archivo directo)")
        
        try:
            #  DECIDIR ESTRATEGIA: HÍBRIDO vs TRADICIONAL
            usar_hibrido = total_archivos_directos > 0 or bool(cache_archivos)
            
            if usar_hibrido:
                logger.info(" Usando análisis HÍBRIDO con archivos directos + textos preprocesados")
                
                #  CREAR LISTA DE NOMBRES DE ARCHIVOS DIRECTOS PARA PROMPT
                nombres_archivos_directos = []
                for archivo in archivos_directos:
                    try:
                        if hasattr(archivo, 'filename') and archivo.filename:
                            nombres_archivos_directos.append(archivo.filename)
                        else:
                            nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                    except Exception as e:
                        logger.warning(f" Error obteniendo nombre de archivo: {e}")
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                
                # GENERAR PROMPT HÍBRIDO
                if es_facturacion_extranjera:
                    logger.info(" Prompt híbrido para facturación extranjera")
                    conceptos_extranjeros_dict = self._obtener_conceptos_extranjeros()
                    paises_convenio = self._obtener_paises_convenio()
                    preguntas_fuente = self._obtener_preguntas_fuente_nacional()
                    
                    prompt = PROMPT_ANALISIS_FACTURA_EXTRANJERA(
                        factura_texto, rut_texto, anexos_texto, 
                        cotizaciones_texto, anexo_contrato, 
                        conceptos_extranjeros_dict, paises_convenio, preguntas_fuente,
                        nombres_archivos_directos  #  NUEVO PARÁMETRO
                    )
                else:
                    logger.info("🇨🇴 Prompt híbrido para facturación nacional")
                    conceptos_dict = self._obtener_conceptos_retefuente()
                    
                    prompt = PROMPT_ANALISIS_FACTURA(
                        factura_texto, rut_texto, anexos_texto, 
                        cotizaciones_texto, anexo_contrato, conceptos_dict,
                        nombres_archivos_directos  #  NUEVO PARÁMETRO
                    )
                
                #  LLAMAR A GEMINI HÍBRIDO
                respuesta = await self._llamar_gemini_hibrido_factura(prompt, archivos_directos)
                
            else:
                #  FLUJO TRADICIONAL (solo textos preprocesados)
                logger.info(" Usando análisis TRADICIONAL con solo textos preprocesados")
                
                if es_facturacion_extranjera:
                    logger.info("Usando prompt especializado para facturación extranjera")
                    conceptos_extranjeros_dict = self._obtener_conceptos_extranjeros()
                    paises_convenio = self._obtener_paises_convenio()
                    preguntas_fuente = self._obtener_preguntas_fuente_nacional()
                    
                    prompt = PROMPT_ANALISIS_FACTURA_EXTRANJERA(
                        factura_texto, rut_texto, anexos_texto, 
                        cotizaciones_texto, anexo_contrato, 
                        conceptos_extranjeros_dict, paises_convenio, preguntas_fuente
                    )
                else:
                    logger.info("Usando prompt para facturación nacional")
                    conceptos_dict = self._obtener_conceptos_retefuente()
                    
                    prompt = PROMPT_ANALISIS_FACTURA(
                        factura_texto, rut_texto, anexos_texto, 
                        cotizaciones_texto, anexo_contrato, conceptos_dict
                    )
                
                #  LLAMAR A GEMINI TRADICIONAL
                respuesta = await self._llamar_gemini(prompt)
            #  LOG DE RESPUESTA SEGÚN ESTRATEGIA
            if usar_hibrido:
                logger.info(f" Respuesta análisis HÍBRIDO: {len(respuesta):,} caracteres")
            else:
                logger.info(f" Respuesta análisis tradicional: {len(respuesta):,} caracteres")
            
            # Log de muestra para debugging (primeros 500 caracteres)
            logger.info(f" Muestra de respuesta: {respuesta[:500]}...")
            
            # Limpiar respuesta si viene con texto extra
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_factura.json", resultado)
            
            #  NUEVO: ANÁLISIS SEPARADO DEL ARTÍCULO 383 PARA PERSONAS NATURALES
            if (resultado.get("naturaleza_tercero") and 
                resultado["naturaleza_tercero"].get("es_persona_natural") == True and resultado["aplica_retencion"] == True ):
                
                logger.info(" PERSONA NATURAL detectada - Iniciando análisis separado del Artículo 383")
                
                try:
                    # Segunda llamada a Gemini con prompt específico de Art 383
                    # ✅ CORRECCIÓN: Convertir objetos ConceptoIdentificado a diccionarios para evitar error de serialización JSON
                    conceptos_identificados_objetos = [ConceptoIdentificado(**c) for c in resultado.get("conceptos_identificados", [])]
                    conceptos_identificados_dict = [concepto.dict() for concepto in conceptos_identificados_objetos] if conceptos_identificados_objetos else []
                    
                    logger.info(f" Pasando {len(conceptos_identificados_dict)} conceptos como diccionarios al Art 383")
                    
                    analisis_art383 = await self._analizar_articulo_383(
                        factura_texto, rut_texto, anexos_texto, 
                        cotizaciones_texto, anexo_contrato, archivos_directos, cache_archivos, conceptos_identificados_dict
                    )
                    
                    # Integrar resultado del Art 383 en el resultado principal
                    resultado["articulo_383"] = analisis_art383
                    
                    # Guardar análisis combinado
                    resultado_combinado = {
                        "timestamp": datetime.now().isoformat(),
                        "analisis_retefuente": resultado,
                        "analisis_art383_separado": analisis_art383,
                        "persona_natural_detectada": True
                    }
                    await self._guardar_respuesta("analisis_factura_con_art383.json", resultado_combinado)
                    
                    logger.info(f"✅ Análisis Art 383 completado: aplica={analisis_art383.get('aplica', False)}")
                    
                except Exception as e:
                    logger.error(f" Error en análisis Art 383: {e}")
                    # Si falla el análisis del Art 383, continuar sin él
                    resultado["articulo_383"] = {
                        "aplica": False,
                        "error": str(e),
                        "observaciones": ["Error procesando Artículo 383 - usar tarifa convencional"]
                    }
            else:
                # No es persona natural, no se analiza Art 383
                resultado["articulo_383"] = {
                    "aplica": False,
                    "razon": "No es persona natural o no se pudo determinar"
                }
                logger.info(" NO es persona natural - Artículo 383 no aplica - no aplica retefuente")
            
            # Crear objeto AnalisisFactura
            analisis = AnalisisFactura(**resultado)
            logger.info(f"Análisis exitoso: {len(analisis.conceptos_identificados)} conceptos identificados")
            
            return analisis
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de análisis: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            # Fallback: crear análisis básico
            return self._analisis_fallback()
        except Exception as e:
            logger.error(f"Error en análisis de factura: {e}")
            raise ValueError(f"Error analizando factura: {str(e)}")
    
    async def _analizar_articulo_383(self, factura_texto: str, rut_texto: str, anexos_texto: str, 
                                   cotizaciones_texto: str, anexo_contrato: str,
                                   archivos_directos: List[UploadFile] = None, 
                                   cache_archivos: Dict[str, bytes] = None, conceptos_identificados: List[Dict] = None) -> Dict[str, Any]:
        """
        🆕 NUEVA FUNCIÓN: Análisis separado del Artículo 383 para personas naturales.
        
        Esta función realiza una segunda llamada a Gemini específicamente para analizar
        si aplica el Artículo 383 del Estatuto Tributario con tarifas progresivas.
        
        ✅ CORREGIDO: Ahora acepta conceptos como diccionarios para evitar errores de serialización JSON.
        
        Args:
            factura_texto: Texto extraído de la factura principal
            rut_texto: Texto del RUT (si está disponible)
            anexos_texto: Texto de anexos adicionales
            cotizaciones_texto: Texto de cotizaciones
            anexo_contrato: Texto del anexo de concepto de contrato
            archivos_directos: Lista de archivos para envío directo a Gemini
            cache_archivos: Cache de archivos para workers paralelos
            conceptos_identificados: Lista de conceptos como diccionarios (no objetos Pydantic)
            
        Returns:
            Dict[str, Any]: Análisis completo del Artículo 383
            
        Raises:
            ValueError: Si hay error en el procesamiento con Gemini
        """
        logger.info(" Iniciando análisis separado del Artículo 383")
        
        try:
            # 💾 USAR CACHE SI ESTÁ DISPONIBLE (para workers paralelos)
            archivos_directos = archivos_directos or []
            if cache_archivos:
                logger.info(f"📄 Art 383 usando cache de archivos: {len(cache_archivos)} archivos")
                archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
            elif archivos_directos:
                logger.info(f"📄 Art 383 usando archivos directos originales: {len(archivos_directos)} archivos")
            
            # ✅ CREAR LISTA DE NOMBRES DE ARCHIVOS DIRECTOS PARA PROMPT
            nombres_archivos_directos = []
            for archivo in archivos_directos:
                try:
                    if hasattr(archivo, 'filename') and archivo.filename:
                        nombres_archivos_directos.append(archivo.filename)
                    else:
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                except Exception as e:
                    logger.warning(f" Error obteniendo nombre de archivo: {e}")
                    nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
            
            # Importar el prompt específico del Art 383
            from .prompt_clasificador import PROMPT_ANALISIS_ART_383
            
            # Generar prompt específico para Art 383
            prompt_art383 = PROMPT_ANALISIS_ART_383(
                factura_texto, rut_texto, anexos_texto, 
                cotizaciones_texto, anexo_contrato, nombres_archivos_directos, conceptos_identificados
            )
            
            logger.info(" Llamando a Gemini para análisis específico del Artículo 383")
            
            # Decidir estrategia: HÍBRIDO vs TRADICIONAL
            usar_hibrido = len(archivos_directos) > 0 or bool(cache_archivos)
            
            if usar_hibrido:
                logger.info(" Usando análisis HÍBRIDO para Art 383")
                respuesta = await self._llamar_gemini_hibrido_factura(prompt_art383, archivos_directos)
            else:
                logger.info(" Usando análisis TRADICIONAL para Art 383")
                respuesta = await self._llamar_gemini(prompt_art383)
            
            logger.info(f" Respuesta Art 383 recibida: {len(respuesta):,} caracteres")
            
            # Limpiar respuesta si viene con texto extra
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado_art383 = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis Art 383 por separado
            await self._guardar_respuesta("analisis_art383_separado.json", resultado_art383)
            # Extraer el diccionario  del Art 383
            resultado_art383 = resultado_art383["articulo_383"]
            # Validar estructura mínima del resultado
            campos_requeridos = ["condiciones_cumplidas", "deducciones_identificadas"]
            for campo in campos_requeridos:
                if campo not in resultado_art383:
                    logger.warning(f" Campo '{campo}' no encontrado en respuesta Art 383")
                    resultado_art383[campo] = self._obtener_campo_art383_default(campo)
            
            # Extraer información clave para logging
            
            condiciones = resultado_art383.get("condiciones_cumplidas", {})
            deducciones = resultado_art383.get("deducciones_identificadas", {})
            logger.info(f" condiciones cumplidas: {condiciones}")
            logger.info(f" deducciones identificadas: {deducciones}")
            
            return resultado_art383
            
        except json.JSONDecodeError as e:
            logger.error(f"💥 Error parseando JSON de Art 383: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._art383_fallback("Error parseando respuesta JSON de Gemini")
        except Exception as e:
            logger.error(f"💥 Error en análisis Art 383: {e}")
            return self._art383_fallback(str(e))
    
    def _obtener_campo_art383_default(self, campo: str) -> Dict[str, Any]:
        """
        Obtiene valores por defecto para campos faltantes en análisis del Art 383.
        
        Args:
            campo: Nombre del campo faltante
            
        Returns:
            Dict con estructura por defecto
        """
        defaults = {
            "aplica": False,
            "condiciones_cumplidas": {
                "es_persona_natural": False,
                "concepto_aplicable": False,
                "es_primer_pago": False,
                "planilla_seguridad_social": False,
                "cuenta_cobro": False
            },
            "deducciones_identificadas": {
                "intereses_vivienda": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "dependientes_economicos": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "medicina_prepagada": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "rentas_exentas": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                }
            }
        }
        
        return defaults.get(campo, {})
    
    def _art383_fallback(self, error_msg: str = "Error procesando Art 383") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento del Art 383.
        
        Args:
            error_msg: Mensaje de error
            
        Returns:
            Dict[str, Any]: Respuesta básica del Art 383
        """
        logger.warning(f"🚨 Usando fallback de Art 383: {error_msg}")
        
        return {
            "aplica": False,
            "condiciones_cumplidas": {
                "es_persona_natural": False,
                "concepto_aplicable": False,
                "es_primer_pago": False,
                "planilla_seguridad_social": False,
                "cuenta_cobro": False
            },
            "deducciones_identificadas": {
                "intereses_vivienda": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "dependientes_economicos": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "medicina_prepagada": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "rentas_exentas": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                }
            },
            "error": error_msg,
            "observaciones": [
                f"Error procesando Artículo 383: {error_msg}",
                "Se aplicará tarifa convencional",
                "Revise manualmente si aplica Art 383"
            ]
        }
    
    async def analizar_consorcio(self, documentos_clasificados: Dict[str, Dict], es_facturacion_extranjera: bool = False, archivos_directos : List[UploadFile] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
        Llamada a Gemini especializada para analizar consorcios CON CACHE.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera (usa prompts especializados)
            archivos_directos: Lista de archivos directos (para compatibilidad)
            cache_archivos: Cache de archivos para workers paralelos
            
        Returns:
            Dict[str, Any]: Análisis completo del consorcio en formato compatible
            
        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        logger.info("Analizando CONSORCIO con Gemini")
        
        #  USAR CACHE SI ESTÁ DISPONIBLE
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f" Consorcio usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" Consorcio usando archivos directos originales: {len(archivos_directos)} archivos")
        
        # Extraer documentos por categoría (mismo proceso que factura normal)
        factura_texto = ""
        rut_texto = ""
        anexos_texto = ""
        cotizaciones_texto = ""
        anexo_contrato = ""
        
        for nombre_archivo, info in documentos_clasificados.items():
            if info["categoria"] == "FACTURA":
                factura_texto = info["texto"]
                logger.info(f"Factura de consorcio encontrada: {nombre_archivo}")
            elif info["categoria"] == "RUT":
                rut_texto = info["texto"]
                logger.info(f"RUT encontrado: {nombre_archivo}")
            elif info["categoria"] == "ANEXO":
                anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
            elif info["categoria"] == "COTIZACION":
                cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
            elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
        
        hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
        nombres_archivos_directos = [archivo.filename for archivo in archivos_directos]
        posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
        
        if not factura_texto and not posibles_facturas_directas:
            raise ValueError("No se encontró una FACTURA en los documentos del consorcio")
        logger.info("Se identificó correctamente la factura del consorcio")
       
        for archivo in archivos_directos:
            try:
                if hasattr(archivo, 'filename') and archivo.filename:
                    nombres_archivos_directos.append(archivo.filename)
                else:
                    nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
            except Exception as e: 
                logger.warning(f" Error obteniendo nombre de archivo: {e}")
                nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")
                
        try:
            if es_facturacion_extranjera:
                # NUEVA FUNCIONALIDAD: Usar prompts especializados para consorcios extranjeros
                logger.info("Usando prompt especializado para consorcio extranjero")
                conceptos_extranjeros_dict = self._obtener_conceptos_extranjeros()
                paises_convenio = self._obtener_paises_convenio()
                preguntas_fuente = self._obtener_preguntas_fuente_nacional()
                
                prompt = PROMPT_ANALISIS_CONSORCIO_EXTRANJERO(
                    factura_texto, rut_texto, anexos_texto, 
                    cotizaciones_texto, anexo_contrato, 
                    conceptos_extranjeros_dict, paises_convenio, preguntas_fuente, nombres_archivos_directos=nombres_archivos_directos
                )
            else:
                # Flujo original para consorcios nacionales
                logger.info("Usando prompt para consorcio nacional")
                conceptos_dict = self._obtener_conceptos_retefuente()
                
                prompt = PROMPT_ANALISIS_CONSORCIO(
                    factura_texto, rut_texto, anexos_texto, 
                    cotizaciones_texto, anexo_contrato, conceptos_dict, nombres_archivos_directos=nombres_archivos_directos 
                )
            
            # Llamar a Gemini con modelo especial para consorcios
            respuesta = await self._llamar_gemini_hibrido_factura(prompt, archivos_directos=archivos_directos)
            logger.info(f"Respuesta análisis consorcio: {respuesta}...")


            # Limpiar respuesta
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)

            # Parsear JSON con auto-reparación
            try:
                resultado = json.loads(respuesta_limpia)
            except json.JSONDecodeError as first_error:
                logger.warning(f"JSON malformado detectado, intentando reparar: {first_error}")
                # Intentar reparar JSON automáticamente
                respuesta_reparada = self._reparar_json_malformado(respuesta_limpia)
                resultado = json.loads(respuesta_reparada)
            
            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_consorcio.json", resultado)
            
            # NUEVO FLUJO v3.1.2: Solo extracción de datos por Gemini
            # La validación y cálculo se realizará en liquidador_consorcios.py

            # Validar cantidad de consorciados
            if 'consorciados' in resultado and len(resultado['consorciados']) > 20:
                logger.warning(f"Consorcio muy grande ({len(resultado['consorciados'])} consorciados), puede requerir procesamiento especial")

            # Retornar resultado directo de Gemini para el nuevo liquidador
            logger.info(f"Análisis de consorcio exitoso: {len(resultado.get('consorciados', []))} consorciados identificados")
            logger.info("✅ Datos extraídos por Gemini - Validaciones y cálculos serán realizados por liquidador_consorcios.py")

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de consorcio: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._consorcio_fallback()
        except Exception as e:
            logger.error(f"Error en análisis de consorcio: {e}")
            return self._consorcio_fallback(str(e))

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
            logger.error(f" Archivos enviados: {[getattr(archivo, 'filename', 'sin_nombre') for archivo in archivos_directos]}")
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
    
    def _limpiar_respuesta_json(self, respuesta: str) -> str:
        """
        Limpia la respuesta de Gemini para extraer solo el JSON.
        
        Args:
            respuesta: Respuesta cruda de Gemini
            
        Returns:
            str: JSON limpio
            
        Raises:
            ValueError: Si no se puede extraer JSON válido
        """
        try:
            # Primero, eliminar bloques de código markdown si existen
            if '```json' in respuesta:
                inicio_json = respuesta.find('```json') + 7
                fin_json = respuesta.find('```', inicio_json)
                if fin_json != -1:
                    respuesta = respuesta[inicio_json:fin_json].strip()
            
            # Buscar el primer { y el último }
            inicio = respuesta.find('{')
            fin = respuesta.rfind('}') + 1
            
            if inicio != -1 and fin != 0:
                json_limpio = respuesta[inicio:fin]
                # Verificar que sea JSON válido
                json.loads(json_limpio)
                return json_limpio
            else:
                raise ValueError("No se encontró JSON válido en la respuesta")
                
        except json.JSONDecodeError:
            # Si falla la limpieza, devolver respuesta original
            logger.warning("No se pudo limpiar JSON, usando respuesta original")
            return respuesta
        except Exception as e:
            logger.error(f"Error limpiando JSON: {e}")
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
    
    def _analisis_fallback(self) -> AnalisisFactura:
        """
        Análisis de emergencia cuando falla Gemini.
        
        Returns:
            AnalisisFactura: Análisis básico de fallback
        """
        logger.warning("Usando análisis fallback - Gemini no pudo procesar")
        
        return AnalisisFactura(
            conceptos_identificados=[
                ConceptoIdentificado(
                    concepto="CONCEPTO_NO_IDENTIFICADO",
                    tarifa_retencion=0.0
                )
            ],
            naturaleza_tercero=NaturalezaTercero(
                es_responsable_iva=None  # No se pudo identificar
            ),
            es_facturacion_exterior=False,
            valor_total=None,
            iva=None,
            observaciones=[
                "Error procesando con Gemini - No se pudo extraer información",
                "Por favor revise manualmente los documentos",
                "IMPORTANTE: Verifique si el tercero es responsable de IVA en el RUT"
            ]
        )
    
    def _obtener_conceptos_retefuente(self) -> dict:
        """
        Obtiene los conceptos de retefuente desde el config global.
        
        Returns:
            dict: Conceptos formateados para Gemini
        """
        try:
            # ✅ OPCIÓN A: Importar directamente CONCEPTOS_RETEFUENTE desde config.py
            from config import CONCEPTOS_RETEFUENTE
            
            conceptos_dict = {}
            for concepto, datos in CONCEPTOS_RETEFUENTE.items():
                conceptos_dict[concepto] = {
                    "base_minima_pesos": datos["base_pesos"],
                    "tarifa_retencion_porcentaje": datos["tarifa_retencion"] * 100  # Convertir a porcentaje
                }
            
            logger.info(f" CONCEPTOS_RETEFUENTE importados exitosamente desde confi.py: {len(conceptos_dict)} conceptos")
            return conceptos_dict
                
        except ImportError as e:
            logger.warning(f" No se pudo importar desde config.py: {e}")
            # Fallback: usar conceptos hardcodeados
            logger.warning(" Usando conceptos hardcodeados como fallback")
            return self._conceptos_hardcodeados()
        except Exception as e:
            logger.error(f"Error obteniendo conceptos: {e}")
            return self._conceptos_hardcodeados()
    
    def _conceptos_hardcodeados(self) -> dict:
        """
        Conceptos de emergencia si no se puede acceder al config global.
        
        Returns:
            dict: Conceptos básicos hardcodeados
        """
        # Importar conceptos desde el archivo principal si es posible
        # Por ahora, retornar diccionario básico
        return {
            "Servicios generales (declarantes)": {
                "base_minima_pesos": 100000,
                "tarifa_retencion_porcentaje": 4.0
            },
            "Honorarios y comisiones por servicios (declarantes)": {
                "base_minima_pesos": 0,
                "tarifa_retencion_porcentaje": 11.0
            }
        }
    
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
    
    def _obtener_conceptos_completos(self) -> dict:
        """
        Obtiene los conceptos completos de retefuente con bases mínimas y tarifas.
        
        Returns:
            dict: Conceptos con estructura completa {concepto: {base_pesos, tarifa_retencion}}
        """
        try:
            # ✅ OPCIÓN A: Importar directamente CONCEPTOS_RETEFUENTE desde config.py
            from config import CONCEPTOS_RETEFUENTE
            logger.info(f" CONCEPTOS_RETEFUENTE importados exitosamente desde config.py: {len(CONCEPTOS_RETEFUENTE)} conceptos")
            return CONCEPTOS_RETEFUENTE
                
        except ImportError as e:
            logger.warning(f" No se pudo importar desde config.py: {e}")
            # Fallback: usar conceptos hardcodeados
            logger.warning(" Usando conceptos completos hardcodeados como fallback")
            return self._conceptos_completos_hardcodeados()
        except Exception as e:
            logger.error(f"Error obteniendo conceptos completos: {e}")
            return self._conceptos_completos_hardcodeados()
    
    # ===============================
    # NUEVAS FUNCIONES PARA FACTURACIÓN EXTRANJERA
    # ===============================
    
    def _obtener_conceptos_extranjeros(self) -> dict:
        """
        Obtiene los conceptos de retención para facturación extranjera.
        
        Returns:
            dict: Conceptos extranjeros con tarifas normal y convenio
        """
        try:
            # Importar desde config global
            import sys
            sys.path.append('..')
            
            try:
                from config import obtener_conceptos_extranjeros
                return obtener_conceptos_extranjeros()
            except ImportError:
                logger.warning("No se pudo importar conceptos extranjeros, usando hardcodeados")
                return self._conceptos_extranjeros_hardcodeados()
                
        except Exception as e:
            logger.error(f"Error obteniendo conceptos extranjeros: {e}")
            return self._conceptos_extranjeros_hardcodeados()
    
    def _obtener_paises_convenio(self) -> list:
        """
        Obtiene la lista de países con convenio de doble tributación.
        
        Returns:
            list: Lista de países con convenio
        """
        try:
            import sys
            sys.path.append('..')
            
            try:
                from config import obtener_paises_con_convenio
                return obtener_paises_con_convenio()
            except ImportError:
                logger.warning("No se pudo importar países con convenio, usando hardcodeados")
                return self._paises_convenio_hardcodeados()
                
        except Exception as e:
            logger.error(f"Error obteniendo países con convenio: {e}")
            return self._paises_convenio_hardcodeados()
    
    def _obtener_preguntas_fuente_nacional(self) -> list:
        """
        Obtiene las preguntas para determinar fuente nacional.
        
        Returns:
            list: Lista de preguntas para validar fuente nacional
        """
        try:
            import sys
            sys.path.append('..')
            
            try:
                from config import obtener_preguntas_fuente_nacional
                return obtener_preguntas_fuente_nacional()
            except ImportError:
                logger.warning("No se pudo importar preguntas fuente nacional, usando hardcodeadas")
                return self._preguntas_fuente_hardcodeadas()
                
        except Exception as e:
            logger.error(f"Error obteniendo preguntas fuente nacional: {e}")
            return self._preguntas_fuente_hardcodeadas()
    
    def _conceptos_extranjeros_hardcodeados(self) -> dict:
        """
        Conceptos extranjeros de emergencia.
        
        Returns:
            dict: Conceptos básicos extranjeros
        """
        return {
            "Pagos por servicios al exterior": {
                "base_pesos": 0,
                "tarifa_normal": 0.20,
                "tarifa_convenio": 0.10
            }
        }
    
    def _paises_convenio_hardcodeados(self) -> list:
        """
        Países con convenio de emergencia.
        
        Returns:
            list: Lista básica de países
        """
        return ["España", "Francia", "Italia", "Chile", "México", "Perú", "Ecuador", "Bolivia"]
    
    def _preguntas_fuente_hardcodeadas(self) -> list:
        """
        Preguntas de fuente nacional de emergencia.
        
        Returns:
            list: Lista básica de preguntas
        """
        return [
            "¿El servicio tiene uso o beneficio económico en Colombia?",
            "¿La actividad se ejecutó en Colombia?",
            "¿Es asistencia técnica usada en Colombia?",
            "¿El bien está ubicado en Colombia?"
        ]
    
    def _conceptos_completos_hardcodeados(self) -> dict:
        """
        Conceptos completos de emergencia con bases mínimas y tarifas.
        
        Returns:
            dict: Conceptos básicos con estructura completa
        """
        return {
            "Servicios generales (declarantes)": {
                "base_pesos": 498000,
                "tarifa_retencion": 0.04
            },
            "Honorarios y comisiones por servicios (declarantes)": {
                "base_pesos": 2490000,
                "tarifa_retencion": 0.11
            },
            "Servicios de construcción y urbanización (declarantes)": {
                "base_pesos": 1490000,
                "tarifa_retencion": 0.01
            }
        }
    
    def _consorcio_fallback(self, error_msg: str = "Error procesando consorcio") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de consorcio.
        NUEVA ESTRUCTURA v3.1.2: Compatible con liquidador_consorcios.py

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica de consorcio compatible con nuevo liquidador
        """
        logger.warning(f"Usando fallback de consorcio: {error_msg}")

        return {
            "es_consorcio": True,
            "nombre_consorcio": "Consorcio no identificado",
            "tipo_entidad": "CONSORCIO",
            "conceptos_identificados": [
                {
                    "nombre_concepto": "CONCEPTO_NO_IDENTIFICADO",
                    "concepto": "CONCEPTO_NO_IDENTIFICADO",
                    "tarifa_retencion": 0.0,
                    "base_gravable": 0.0
                }
            ],
            "consorciados": [],
            "validacion_porcentajes": {
                "suma_total": 0.0,
                "es_valido": False
            },
            "valor_total_factura": 0.0,
            "observaciones": [
                f"Error procesando consorcio: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique porcentajes de participación en anexos"
            ],
            "tipo_procesamiento": "CONSORCIO_FALLBACK",
            "error": error_msg
        }
    
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
            
            # Validar estructura mínima requerida
            campos_requeridos = ["analisis_iva", "analisis_fuente_ingreso", "calculo_reteiva", "estado_liquidacion"]
            for campo in campos_requeridos:
                if campo not in resultado:
                    logger.warning(f" Campo '{campo}' no encontrado en respuesta de IVA")
                    resultado[campo] = self._obtener_campo_iva_default(campo)
            
            # Extraer información clave para logging
            iva_data = resultado.get("analisis_iva", {})
            estado_data = resultado.get("estado_liquidacion", {})
            
            iva_identificado = iva_data.get("iva_identificado", {})
            valor_iva = iva_identificado.get("valor_iva_total", 0.0)
            estado = estado_data.get("estado", "No definido")
            
            logger.info(f" Análisis IVA completado: Valor IVA=${valor_iva:,.2f}, Estado={estado}")
            
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
    
    def _iva_fallback(self, error_msg: str = "Error procesando IVA") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de IVA.
        
        Args:
            error_msg: Mensaje de error
            
        Returns:
            Dict[str, Any]: Respuesta básica de IVA
        """
        logger.warning(f"Usando fallback de IVA: {error_msg}")
        
        return {
            "analisis_iva": {
                "iva_identificado": {
                    "tiene_iva": False,
                    "valor_iva_total": 0.0,
                    "porcentaje_iva": 0.0,
                    "detalle_conceptos_iva": [],
                    "metodo_identificacion": "error"
                },
                "responsabilidad_iva_rut": {
                    "rut_disponible": False,
                    "es_responsable_iva": None,
                    "codigo_encontrado": "error",
                    "texto_referencia": "Error en procesamiento"
                },
                "concepto_facturado": {
                    "descripcion": "Error en identificación",
                    "aplica_iva": False,
                    "razon_exencion_exclusion": error_msg,
                    "categoria": "error"
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
                "metodo_calculo": "error"
            },
            "estado_liquidacion": {
                "estado": "Error en procesamiento",
                "observaciones": [
                    f"Error procesando IVA: {error_msg}",
                    "Por favor revise manualmente los documentos",
                    "Verifique responsabilidad de IVA en el RUT",
                    "Valide conceptos facturados y aplicabilidad de IVA"
                ]
            },
            "tipo_procesamiento": "IVA_FALLBACK",
            "error": error_msg
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
