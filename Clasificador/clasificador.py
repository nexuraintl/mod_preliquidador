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

# Configuración de logging
logger = logging.getLogger(__name__)

# Importar prompts
from .prompt_clasificador import (
    PROMPT_CLASIFICACION, 
    PROMPT_ANALISIS_FACTURA, 
    PROMPT_ANALISIS_CONSORCIO,
    PROMPT_ANALISIS_FACTURA_EXTRANJERA,
    PROMPT_ANALISIS_CONSORCIO_EXTRANJERO
)

# Importar procesador de consorcios
from .consorcio_processor import ProcesadorConsorcios

# ===============================
# MODELOS DE DATOS LOCALES
# ===============================

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
            'gemini-2.0-flash',
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=2048,
                candidate_count=1
            )
        )
        
        # Configuración especial para consorcios (más tokens)
        self.modelo_consorcio = genai.GenerativeModel(
            'gemini-2.5-flash-lite',
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,  # Menos temperatura para más consistencia
                max_output_tokens=65536,  # 4x más tokens para consorcios grandes
                candidate_count=1
            )
        )
        
        logger.info("ProcesadorGemini inicializado correctamente")
        
        # Inicializar procesador de consorcios
        self.procesador_consorcios = ProcesadorConsorcios()
    
    async def clasificar_documentos(self, textos_archivos: Dict[str, str]) -> Tuple[Dict[str, str], bool, bool]:
        """
        Primera llamada a Gemini: clasificar documentos en categorías, detectar consorcios y facturación extranjera.
        
        Args:
            textos_archivos: Diccionario {nombre_archivo: texto_extraido}
            
        Returns:
            Tuple[Dict[str, str], bool, bool]: (clasificacion_documentos, es_consorcio, es_facturacion_extranjera)
            
        Raises:
            ValueError: Si hay error en el procesamiento con Gemini
        """
        logger.info(f"Clasificando {len(textos_archivos)} documentos con Gemini")
        
        try:
            # Generar prompt usando la función del módulo de prompts
            prompt = PROMPT_CLASIFICACION(textos_archivos)
            
            # Llamar a Gemini
            respuesta = await self._llamar_gemini(prompt)
            logger.info(f"Respuesta cruda de Gemini: {respuesta[:500]}...")  # Log para debugging
            
            # Limpiar respuesta si viene con texto extra
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Extraer clasificación y detección de consorcio
            clasificacion = resultado.get("clasificacion", resultado)  # Fallback para formato anterior
            es_consorcio = self.procesador_consorcios.detectar_consorcio(resultado)
            
            # NUEVA FUNCIONALIDAD: Detectar facturación extranjera
            es_facturacion_extranjera = resultado.get("es_facturacion_extranjera", False)
            indicadores_extranjera = resultado.get("indicadores_extranjera", [])
            
            # Guardar respuesta de clasificación en Results
            await self._guardar_respuesta("clasificacion_documentos.json", resultado)
            
            logger.info(f"Clasificación exitosa: {len(clasificacion)} documentos clasificados")
            logger.info(f"Consorcio detectado: {es_consorcio}")
            logger.info(f"Facturación extranjera detectada: {es_facturacion_extranjera}")
            if es_facturacion_extranjera and indicadores_extranjera:
                logger.info(f"Indicadores extranjera: {indicadores_extranjera}")
            
            # Modificar la respuesta para incluir detección extranjera
            return clasificacion, es_consorcio, es_facturacion_extranjera
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            # Fallback: clasificar manualmente basado en nombres
            clasificacion_fb = self._clasificacion_fallback(textos_archivos)
            return clasificacion_fb, False, False  # Asumir que no es consorcio ni extranjera en fallback
        except Exception as e:
            logger.error(f"Error en clasificación de documentos: {e}")
            raise ValueError(f"Error clasificando documentos: {str(e)}")

    async def analizar_factura(self, documentos_clasificados: Dict[str, Dict], es_facturacion_extranjera: bool = False) -> AnalisisFactura:
        """
        Segunda llamada a Gemini: analizar factura y extraer información para retención.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera (usa prompts especializados)
            
        Returns:
            AnalisisFactura: Análisis completo de la factura
            
        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        logger.info("Analizando factura con Gemini para extracción de información")
        
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
            elif info["categoria"] == "RUT":
                rut_texto = info["texto"]
                logger.info(f"RUT encontrado: {nombre_archivo}")
            elif info["categoria"] == "ANEXO":
                anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
            elif info["categoria"] == "COTIZACION":
                cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
            elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
        
        if not factura_texto:
            raise ValueError("No se encontró una FACTURA en los documentos proporcionados")
        
        try:
            if es_facturacion_extranjera:
                # NUEVA FUNCIONALIDAD: Usar prompts especializados para facturación extranjera
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
                # Flujo original para facturación nacional
                logger.info("Usando prompt para facturación nacional")
                conceptos_dict = self._obtener_conceptos_retefuente()
                
                prompt = PROMPT_ANALISIS_FACTURA(
                    factura_texto, rut_texto, anexos_texto, 
                    cotizaciones_texto, anexo_contrato, conceptos_dict
                )
            
            # Llamar a Gemini
            respuesta = await self._llamar_gemini(prompt)
            logger.info(f"Respuesta análisis de Gemini: {respuesta[:500]}...")  # Log para debugging
            
            # Limpiar respuesta si viene con texto extra
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_factura.json", resultado)
            
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
    
    async def analizar_consorcio(self, documentos_clasificados: Dict[str, Dict], es_facturacion_extranjera: bool = False) -> Dict[str, Any]:
        """
        Llamada a Gemini especializada para analizar consorcios.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera (usa prompts especializados)
            
        Returns:
            Dict[str, Any]: Análisis completo del consorcio en formato compatible
            
        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        logger.info("Analizando CONSORCIO con Gemini")
        
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
        
        if not factura_texto:
            raise ValueError("No se encontró una FACTURA en los documentos del consorcio")
        
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
                    conceptos_extranjeros_dict, paises_convenio, preguntas_fuente
                )
            else:
                # Flujo original para consorcios nacionales
                logger.info("Usando prompt para consorcio nacional")
                conceptos_dict = self._obtener_conceptos_retefuente()
                
                prompt = PROMPT_ANALISIS_CONSORCIO(
                    factura_texto, rut_texto, anexos_texto, 
                    cotizaciones_texto, anexo_contrato, conceptos_dict
                )
            
            # Llamar a Gemini con modelo especial para consorcios
            respuesta = await self._llamar_gemini(prompt, usar_modelo_consorcio=True)
            logger.info(f"Respuesta análisis consorcio: {respuesta}...")
            
            # Validar si la respuesta está truncada
            if self._es_respuesta_truncada(respuesta):
                logger.warning("Respuesta de consorcio truncada, intentando con prompt reducido")
                # Intentar con menos documentos anexos
                prompt_reducido = PROMPT_ANALISIS_CONSORCIO(
                    factura_texto[:2000], rut_texto[:1000] if rut_texto else "", 
                    "", "", "", conceptos_dict
                )
                respuesta = await self._llamar_gemini(prompt_reducido, usar_modelo_consorcio=True)
            
            # Limpiar respuesta
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self._guardar_respuesta("analisis_consorcio.json", resultado)
            
            # Procesar con el procesador de consorcios
            analisis_consorcio = self.procesador_consorcios.procesar_respuesta_consorcio(resultado)
            
            # Validar cantidad de consorciados
            if 'consorciados' in resultado and len(resultado['consorciados']) > 20:
                logger.warning(f"Consorcio muy grande ({len(resultado['consorciados'])} consorciados), puede requerir procesamiento especial")
            
            # Calcular retenciones individuales
            conceptos_retefuente = self._obtener_conceptos_completos()
            analisis_final = self.procesador_consorcios.calcular_retenciones_consorcio(
                analisis_consorcio, conceptos_retefuente
            )
            
            # Convertir a formato compatible
            respuesta_compatible = self.procesador_consorcios.convertir_a_formato_compatible(analisis_final)
            
            logger.info(f"Análisis de consorcio exitoso: {analisis_final.consorcio_info.total_consorciados} consorciados")
            return respuesta_compatible
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de consorcio: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._consorcio_fallback()
        except Exception as e:
            logger.error(f"Error en análisis de consorcio: {e}")
            return self._consorcio_fallback(str(e))
    
    async def _llamar_gemini(self, prompt: str, usar_modelo_consorcio: bool = False) -> str:
        """
        Realiza llamada a Gemini con manejo de errores y timeout.
        
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
            timeout_segundos = 60.0 if usar_modelo_consorcio else 30.0
            
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
                
            return texto_respuesta
            
        except asyncio.TimeoutError:
            logger.error("Timeout llamando a Gemini (30s)")
            raise ValueError("Gemini tardó demasiado en responder")
        except Exception as e:
            logger.error(f"Error llamando a Gemini: {e}")
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
    
    def _es_respuesta_truncada(self, respuesta: str) -> bool:
        """
        Detecta si una respuesta de Gemini está truncada.
        
        Args:
            respuesta: Respuesta de Gemini
            
        Returns:
            bool: True si parece truncada, False si no
        """
        indicadores_truncado = [
            '...',  # Tres puntos al final
            '..."',  # Tres puntos antes de comillas
            ', ...',  # Coma seguida de tres puntos
            '"..."',  # Tres puntos entre comillas
        ]
        
        # Verificar si termina con algún indicador de truncado
        respuesta_limpia = respuesta.strip()
        for indicador in indicadores_truncado:
            if respuesta_limpia.endswith(indicador):
                return True
        
        # Verificar si no tiene cierre de JSON completo
        conteo_llaves_abiertas = respuesta.count('{')
        conteo_llaves_cerradas = respuesta.count('}')
        if conteo_llaves_abiertas > conteo_llaves_cerradas:
            return True
        
        # Verificar si termina abruptamente dentro de un string
        if respuesta_limpia.endswith('":') or respuesta_limpia.endswith('": '):
            return True
        
        return False
    
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
            elif 'contrato' in nombre_lower and 'concepto' in nombre_lower:
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
            # Importar conceptos desde config global (main.py)
            import sys
            sys.path.append('..')
            
            # Intentar importar desde main
            try:
                from config import obtener_conceptos, obtener_tarifa_concepto
                conceptos = obtener_conceptos()
                
                conceptos_dict = {}
                for concepto in conceptos:
                    tarifa = obtener_tarifa_concepto(concepto)
                    conceptos_dict[concepto] = {
                        "base_minima_pesos": 0,  # Se obtendría del Excel
                        "tarifa_retencion_porcentaje": tarifa
                    }
                
                return conceptos_dict
                
            except ImportError:
                # Fallback: usar conceptos hardcodeados
                logger.warning("No se pudo importar config, usando conceptos hardcodeados")
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
            # Crear carpeta por fecha si no existe
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            carpeta_results = Path("../Results") / fecha_hoy
            carpeta_results.mkdir(parents=True, exist_ok=True)
            
            # Guardar archivo
            ruta_archivo = carpeta_results / nombre_archivo
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(contenido, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Respuesta guardada en {ruta_archivo}")
            
        except Exception as e:
            logger.error(f"Error guardando respuesta: {e}")
            # Intentar guardar en directorio actual como fallback
            try:
                with open(nombre_archivo, "w", encoding="utf-8") as f:
                    json.dump(contenido, f, indent=2, ensure_ascii=False)
                logger.info(f"Respuesta guardada en directorio actual: {nombre_archivo}")
            except Exception as e2:
                logger.error(f"Error guardando fallback: {e2}")
    
    def _obtener_conceptos_completos(self) -> dict:
        """
        Obtiene los conceptos completos de retefuente con bases mínimas y tarifas.
        
        Returns:
            dict: Conceptos con estructura completa {concepto: {base_pesos, tarifa_retencion}}
        """
        try:
            # 🔧 CORREGIDO: Importar desde main.py donde están definidos
            import sys
            sys.path.append('..')
            
            # Intentar importar CONCEPTOS_RETEFUENTE desde main.py
            try:
                from main import CONCEPTOS_RETEFUENTE
                logger.info(f"✅ CONCEPTOS_RETEFUENTE importados exitosamente: {len(CONCEPTOS_RETEFUENTE)} conceptos")
                return CONCEPTOS_RETEFUENTE
            except ImportError as e:
                logger.warning(f"⚠️ No se pudo importar desde main.py: {e}")
                # Fallback: intentar desde config por compatibilidad
                try:
                    from config import CONCEPTOS_RETEFUENTE
                    logger.info("✅ CONCEPTOS_RETEFUENTE importados desde config.py")
                    return CONCEPTOS_RETEFUENTE
                except ImportError:
                    logger.warning("⚠️ No se pudo importar CONCEPTOS_RETEFUENTE, usando hardcodeados")
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
        
        Args:
            error_msg: Mensaje de error
            
        Returns:
            Dict[str, Any]: Respuesta básica de consorcio
        """
        logger.warning(f"Usando fallback de consorcio: {error_msg}")
        
        return {
            "aplica_retencion": False,
            "es_consorcio": True,
            "valor_total_factura": 0,
            "iva_total": 0,
            "valor_retencion": 0,
            "concepto": "CONCEPTO_NO_IDENTIFICADO",
            "tarifa_retencion": 0,
            "consorcio_info": {
                "nombre_consorcio": "Consorcio no identificado",
                "nit_consorcio": "000000000",
                "total_consorciados": 0
            },
            "consorciados": [],
            "resumen_retencion": {
                "valor_total_factura": 0,
                "iva_total": 0,
                "total_retenciones": 0,
                "consorciados_con_retencion": 0,
                "consorciados_sin_retencion": 0,
                "suma_porcentajes_original": 0,
                "porcentajes_normalizados": False
            },
            "es_facturacion_exterior": False,
            "observaciones": [
                f"Error procesando consorcio: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique porcentajes de participación en anexos"
            ],
            "tipo_procesamiento": "CONSORCIO_FALLBACK",
            "error": error_msg
        }
