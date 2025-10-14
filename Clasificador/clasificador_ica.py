"""
CLASIFICADOR ICA (INDUSTRIA Y COMERCIO)
=======================================

Módulo para analizar facturas y determinar retención de ICA según ubicaciones
y actividades económicas. Combina análisis de IA (Gemini) con validaciones
manuales exhaustivas en Python.

ARQUITECTURA SEPARADA (v3.0):
- Gemini: SOLO identifica datos (ubicaciones, actividades)
- Python: TODAS las validaciones según normativa

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo análisis de ICA
- DIP: Depende de abstracciones (database_manager, gemini_model)
- OCP: Abierto para extensión (nuevas validaciones)
- LSP: Puede sustituirse por otras implementaciones

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture + Validaciones Manuales
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# Importar prompts especializados
from .prompt_ica import (
    crear_prompt_identificacion_ubicaciones,
    crear_prompt_relacionar_actividades,
    limpiar_json_gemini,
    validar_estructura_ubicaciones,
    validar_estructura_actividades
)

# Configuración de logging
logger = logging.getLogger(__name__)


class ClasificadorICA:
    """
    Clasificador especializado para retención de ICA.

    RESPONSABILIDADES (SRP):
    - Obtener ubicaciones de la base de datos
    - Coordinar análisis de Gemini (2 llamadas)
    - Aplicar validaciones manuales según normativa
    - Generar resultado estructurado para el liquidador

    DEPENDENCIAS (DIP):
    - database_manager: Para consultas a tablas ICA
    - procesador_gemini: ProcesadorGemini completo para análisis con IA
    """

    def __init__(self, database_manager: Any, procesador_gemini: Any):
        """
        Inicializa el clasificador ICA con inyección de dependencias.

        Args:
            database_manager: Gestor de base de datos (abstracción)
            procesador_gemini: ProcesadorGemini completo para análisis
        """
        self.database_manager = database_manager
        self.procesador_gemini = procesador_gemini
        logger.info("ClasificadorICA inicializado siguiendo principios SOLID")

    def _guardar_respuesta_gemini(
        self,
        respuesta_texto: str,
        data_parseada: Dict[str, Any],
        tipo_llamada: str,
        nit_administrativo: str = None
    ) -> None:
        """
        Guarda las respuestas de Gemini en archivos JSON para trazabilidad.

        RESPONSABILIDAD (SRP):
        - Solo guarda respuestas en formato JSON
        - Crea estructura de carpetas si no existe
        - Genera nombres de archivo con timestamp

        Args:
            respuesta_texto: Respuesta cruda de Gemini
            data_parseada: JSON parseado y limpio
            tipo_llamada: "ubicaciones" o "actividades"
            nit_administrativo: NIT para organizar archivos (opcional)
        """
        try:
            # Crear carpeta para respuestas ICA
            fecha_actual = datetime.now()
            carpeta_fecha = fecha_actual.strftime("%Y-%m-%d")
            carpeta_base = Path("Results") / carpeta_fecha / "ICA_Respuestas_Gemini"
            
            if nit_administrativo:
                carpeta_base = carpeta_base / nit_administrativo
            
            carpeta_base.mkdir(parents=True, exist_ok=True)

            # Generar nombre de archivo con timestamp
            timestamp = fecha_actual.strftime("%H-%M-%S-%f")[:-3]  # Milisegundos
            nombre_base = f"ica_{tipo_llamada}_{timestamp}"

            # Guardar respuesta cruda
            archivo_crudo = carpeta_base / f"{nombre_base}_raw.txt"
            with open(archivo_crudo, 'w', encoding='utf-8') as f:
                f.write(respuesta_texto)

            # Guardar JSON parseado
            archivo_json = carpeta_base / f"{nombre_base}_parsed.json"
            with open(archivo_json, 'w', encoding='utf-8') as f:
                json.dump(data_parseada, f, ensure_ascii=False, indent=2)

            logger.info(f"💾 Respuesta Gemini guardada: {tipo_llamada} → {archivo_json.name}")

        except Exception as e:
            logger.error(f"❌ Error guardando respuesta Gemini ({tipo_llamada}): {e}")
            # No fallar el proceso si no se puede guardar el archivo

    async def analizar_ica(
        self,
        nit_administrativo: str,
        textos_documentos: Dict[str, str],
        cache_archivos: Optional[Dict[str, bytes]] = None
    ) -> Dict[str, Any]:
        """
        Analiza una factura para determinar retención de ICA.

        FLUJO COMPLETO (SRP - Coordinación):
        1. Validar que el NIT aplica para ICA
        2. Obtener ubicaciones de la base de datos
        3. Primera llamada Gemini: identificar ubicaciones de la actividad (MULTIMODAL)
        4. Validaciones manuales de ubicaciones (Python)
        5. Consultar actividades por ubicación en la BD
        6. Segunda llamada Gemini: relacionar actividades (MULTIMODAL)
        7. Validaciones manuales de actividades (Python)
        8. Retornar resultado estructurado

        Args:
            nit_administrativo: NIT de la entidad administrativa
            textos_documentos: Diccionario con textos de documentos
            cache_archivos: Cache de archivos para procesamiento híbrido multimodal

        Returns:
            Dict con resultado completo del análisis ICA
        """
        logger.info(f"Iniciando análisis ICA para NIT: {nit_administrativo}")

        # MANEJO HÍBRIDO MULTIMODAL: Obtener archivos desde cache
        archivos_directos = []
        if cache_archivos:
            logger.info(f"ICA usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        else:
            logger.info("ICA sin archivos directos")

        resultado_base = {
            "aplica": False,
            "estado": "No aplica impuesto",
            "valor_total_ica": 0.0,
            "actividades_facturadas": [],
            "observaciones": [],
            "fecha_analisis": datetime.now().isoformat()
        }

        try:
            # PASO 1: Validar NIT aplica ICA
            from config import nit_aplica_ICA

            if not nit_aplica_ICA(nit_administrativo):
                resultado_base["observaciones"].append(
                    f"El NIT administrado {nit_administrativo} no aplica ICA"
                )
                logger.warning(f"NIT {nit_administrativo} no aplica ICA")
                return resultado_base

            logger.info("NIT aplica ICA - continuando análisis")

            # PASO 2: Obtener ubicaciones de la BD
            ubicaciones_bd = self._obtener_ubicaciones_bd()
            if not ubicaciones_bd:
                resultado_base["estado"] = "Preliquidacion sin finalizar"
                resultado_base["observaciones"].append(
                    "No se pudieron obtener ubicaciones de la base de datos"
                )
                logger.error("Error obteniendo ubicaciones de BD")
                return resultado_base

            logger.info(f"Ubicaciones obtenidas de BD: {len(ubicaciones_bd)}")

            # PASO 3: Primera llamada Gemini - Identificar ubicaciones (MULTIMODAL)
            ubicaciones_identificadas = await self._identificar_ubicaciones_gemini(
                ubicaciones_bd, textos_documentos, archivos_directos, nit_administrativo
            )

            if not ubicaciones_identificadas:
                resultado_base["estado"] = "Preliquidacion sin finalizar"
                resultado_base["observaciones"].append(
                    "No se pudieron identificar ubicaciones de la actividad"
                )
                logger.error("Gemini no identificó ubicaciones")
                return resultado_base

            logger.info(f"Ubicaciones identificadas por Gemini: {len(ubicaciones_identificadas)}")

            # PASO 4: Validaciones manuales de ubicaciones (Python)
            validacion_ubicaciones = self._validar_ubicaciones_manualmente(
                ubicaciones_identificadas
            )

            if not validacion_ubicaciones["valido"]:
                resultado_base["estado"] = "Preliquidacion sin finalizar"
                resultado_base["observaciones"].extend(validacion_ubicaciones["errores"])
                logger.warning(f"Validación de ubicaciones falló: {validacion_ubicaciones['errores']}")
                return resultado_base

            # Agregar observaciones no críticas
            if validacion_ubicaciones["advertencias"]:
                resultado_base["observaciones"].extend(validacion_ubicaciones["advertencias"])

            logger.info("Validaciones de ubicaciones exitosas")

            # PASO 5: Consultar actividades por ubicación en BD
            actividades_bd_por_ubicacion = self._obtener_actividades_por_ubicacion(
                ubicaciones_identificadas
            )

            if not actividades_bd_por_ubicacion:
                resultado_base["estado"] = "Preliquidacion sin finalizar"
                resultado_base["observaciones"].append(
                    "No se pudieron obtener actividades de la base de datos"
                )
                logger.error("Error obteniendo actividades de BD")
                return resultado_base

            logger.info(f"Actividades obtenidas para {len(actividades_bd_por_ubicacion)} ubicaciones")

            # PASO 6: Segunda llamada Gemini - Relacionar actividades (MULTIMODAL)
            actividades_relacionadas = await self._relacionar_actividades_gemini(
                ubicaciones_identificadas,
                actividades_bd_por_ubicacion,
                textos_documentos,
                archivos_directos,
                nit_administrativo
            )

            if not actividades_relacionadas:
                resultado_base["estado"] = "No aplica impuesto"
                resultado_base["observaciones"].append(
                    "No se pudieron identificar actividades facturadas en la documentación"
                )
                logger.warning("Gemini no identificó actividades facturadas")
                return resultado_base

            logger.info(f"Actividades relacionadas por Gemini: {len(actividades_relacionadas)}")

            # PASO 7: Validaciones manuales de actividades (Python)
            validacion_actividades = self._validar_actividades_manualmente(
                actividades_relacionadas,
                ubicaciones_identificadas
            )

            if not validacion_actividades["valido"]:
                # Determinar estado según el tipo de error
                if validacion_actividades.get("todas_no_aplican", False):
                    resultado_base["estado"] = "No aplica impuesto"
                else:
                    resultado_base["estado"] = "Preliquidacion sin finalizar"

                resultado_base["observaciones"].extend(validacion_actividades["errores"])
                resultado_base["observaciones"].extend(validacion_actividades.get("advertencias", []))
                logger.warning(f"Validación de actividades falló: {validacion_actividades['errores']}")
                return resultado_base

            # Agregar observaciones no críticas de actividades
            if validacion_actividades.get("advertencias"):
                resultado_base["observaciones"].extend(validacion_actividades["advertencias"])

            logger.info("Validaciones de actividades exitosas - pasando a liquidador")

            # PASO 8: Preparar datos validados para liquidador
            resultado_base["aplica"] = True
            resultado_base["estado"] = "Validado - Listo para liquidación"
            resultado_base["ubicaciones_identificadas"] = ubicaciones_identificadas
            resultado_base["actividades_facturadas"] = actividades_relacionadas

            # Aquí el liquidador se encargará del cálculo
            logger.info("Análisis ICA completado exitosamente")
            return resultado_base

        except Exception as e:
            logger.error(f"Error en análisis ICA: {e}")
            resultado_base["estado"] = "Preliquidacion sin finalizar"
            resultado_base["observaciones"].append(f"Error en análisis: {str(e)}")
            return resultado_base

    def _obtener_ubicaciones_bd(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las ubicaciones de la tabla UBICACIONES ICA.

        RESPONSABILIDAD (SRP):
        - Solo obtiene ubicaciones de la base de datos
        - No valida ni procesa datos

        Returns:
            List[Dict]: Lista de ubicaciones con codigo y nombre
        """
        logger.info("Consultando tabla UBICACIONES ICA...")

        try:
            # Consultar tabla UBICACIONES ICA
            response = self.database_manager.db_connection.supabase.table("UBICACIONES ICA").select(
                "CODIGO_UBICACION, NOMBRE_UBICACION"
            ).execute()

            if not response.data:
                logger.warning("No se encontraron ubicaciones en la BD")
                return []

            # Mapear a formato estándar
            ubicaciones = [
                {
                    "codigo_ubicacion": ub["CODIGO_UBICACION"],
                    "nombre_ubicacion": ub["NOMBRE_UBICACION"]
                }
                for ub in response.data
            ]

            logger.info(f"Ubicaciones obtenidas exitosamente: {len(ubicaciones)}")
            return ubicaciones

        except Exception as e:
            logger.error(f"Error consultando UBICACIONES ICA: {e}")
            return []

    async def _procesar_archivos_para_gemini(self, archivos_directos: List[Any]) -> List[Dict[str, Any]]:
        """
        Procesa archivos UploadFile para convertirlos al formato esperado por Gemini.
        
        RESPONSABILIDAD (SRP):
        - Convierte UploadFile a formato {"mime_type": ..., "data": bytes}
        - Determina MIME type correcto según extensión
        
        Args:
            archivos_directos: Lista de archivos (UploadFile, bytes o dict)
            
        Returns:
            List[Dict]: Archivos en formato Gemini
        """
        archivos_procesados = []
        
        for i, archivo_elemento in enumerate(archivos_directos):
            try:
                archivo_objeto = None
                
                # Caso 1: Ya es un dict con formato correcto
                if isinstance(archivo_elemento, dict) and "mime_type" in archivo_elemento:
                    archivo_objeto = archivo_elemento
                    logger.debug(f"Archivo {i+1} ya está en formato Gemini")
                
                # Caso 2: Es bytes directamente
                elif isinstance(archivo_elemento, bytes):
                    archivo_objeto = {
                        "mime_type": "application/octet-stream",
                        "data": archivo_elemento
                    }
                    logger.debug(f"Archivo {i+1} convertido desde bytes")
                
                # Caso 3: Es UploadFile (starlette)
                elif hasattr(archivo_elemento, 'read'):
                    await archivo_elemento.seek(0)
                    archivo_bytes = await archivo_elemento.read()
                    
                    # Determinar MIME type por extensión
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
                    logger.debug(f"Archivo {i+1} ({nombre_archivo}): {len(archivo_bytes):,} bytes, {mime_type}")
                
                else:
                    logger.warning(f"Tipo de archivo desconocido: {type(archivo_elemento)}")
                    archivo_objeto = {
                        "mime_type": "application/octet-stream",
                        "data": bytes(archivo_elemento) if not isinstance(archivo_elemento, bytes) else archivo_elemento
                    }
                
                if archivo_objeto:
                    archivos_procesados.append(archivo_objeto)
                    
            except Exception as e:
                logger.error(f"Error procesando archivo {i+1} para Gemini: {e}")
                continue
        
        logger.info(f"Archivos procesados para Gemini: {len(archivos_procesados)}/{len(archivos_directos)}")
        return archivos_procesados

    async def _identificar_ubicaciones_gemini(
        self,
        ubicaciones_bd: List[Dict[str, Any]],
        textos_documentos: Dict[str, str],
        archivos_directos: List[Any],
        nit_administrativo: str = None
    ) -> List[Dict[str, Any]]:
        """
        Primera llamada a Gemini para identificar ubicaciones de la actividad (MULTIMODAL).

        RESPONSABILIDAD (SRP):
        - Solo coordina la llamada a Gemini
        - No valida resultados (eso lo hace _validar_ubicaciones_manualmente)

        PROCESAMIENTO HÍBRIDO:
        - Textos extraídos (Excel, Word) se incluyen en el prompt
        - Archivos directos (PDF, imágenes) se envían a Gemini para análisis multimodal

        Args:
            ubicaciones_bd: Ubicaciones de la base de datos
            textos_documentos: Textos de documentos preprocesados
            archivos_directos: Archivos clonados desde cache para procesamiento multimodal
            nit_administrativo: NIT para organizar archivos guardados (opcional)

        Returns:
            List[Dict]: Ubicaciones identificadas por Gemini
        """
        logger.info("Primera llamada Gemini: identificando ubicaciones (MULTIMODAL)...")

        try:
            # Preparar nombres de archivos directos para el prompt
            archivos_directos = archivos_directos or []
            nombres_archivos_directos = [
                archivo.filename if hasattr(archivo, 'filename') else (archivo.name if hasattr(archivo, 'name') else f"archivo_{i}")
                for i, archivo in enumerate(archivos_directos)
            ]

            # Crear prompt con información de archivos directos
            prompt = crear_prompt_identificacion_ubicaciones(
                ubicaciones_bd=ubicaciones_bd,
                textos_documentos=textos_documentos,
                nombres_archivos_directos=nombres_archivos_directos if archivos_directos else None
            )

            # Preparar contenido para Gemini (MULTIMODAL)
            contenido_gemini = [prompt]

            # Agregar archivos directos para análisis multimodal
            if archivos_directos:
                # CORRECCIÓN: Procesar archivos al formato esperado por Gemini
                archivos_procesados = await self._procesar_archivos_para_gemini(archivos_directos)
                contenido_gemini.extend(archivos_procesados)
                logger.info(f"📎 ICA - Enviando {len(archivos_procesados)} archivos procesados a Gemini para identificar ubicaciones")

            # Llamar a Gemini con contexto completo
            loop = asyncio.get_event_loop()
            respuesta = await loop.run_in_executor(
                None,
                lambda: self.procesador_gemini.modelo.generate_content(contenido_gemini)
            )

            # Limpiar y parsear respuesta
            respuesta_texto = respuesta.text
            json_limpio = limpiar_json_gemini(respuesta_texto)
            data = json.loads(json_limpio)

            # 💾 GUARDAR RESPUESTA DE GEMINI (Primera llamada - ubicaciones)
            self._guardar_respuesta_gemini(
                respuesta_texto=respuesta_texto,
                data_parseada=data,
                tipo_llamada="ubicaciones",
                nit_administrativo=nit_administrativo
            )

            # Validar estructura
            if not validar_estructura_ubicaciones(data):
                logger.error("Estructura de JSON de ubicaciones inválida")
                return []

            ubicaciones = data.get("ubicaciones", [])
            logger.info(f"Gemini identificó {len(ubicaciones)} ubicaciones")
            return ubicaciones

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini (ubicaciones): {e}")
            return []
        except Exception as e:
            logger.error(f"Error en llamada a Gemini (ubicaciones): {e}")
            return []

    def _validar_ubicaciones_manualmente(
        self,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Valida manualmente las ubicaciones identificadas por Gemini.

        VALIDACIONES MANUALES (Python):
        1. Una ubicación sin nombre identificado
        2. Texto identificador vacío
        3. Código ubicación no encontrado en BD
        4. Múltiples ubicaciones sin porcentajes
        5. Suma de porcentajes != 100%

        Args:
            ubicaciones_identificadas: Ubicaciones de Gemini

        Returns:
            Dict con validación: {"valido": bool, "errores": List[str], "advertencias": List[str]}
        """
        logger.info("Aplicando validaciones manuales a ubicaciones...")

        errores = []
        advertencias = []

        # VALIDACIÓN 0: Debe haber al menos una ubicación
        if not ubicaciones_identificadas or len(ubicaciones_identificadas) == 0:
            errores.append("No se identificaron ubicaciones en los documentos")
            return {"valido": False, "errores": errores, "advertencias": advertencias}

        # Caso: Una sola ubicación
        if len(ubicaciones_identificadas) == 1:
            ubicacion = ubicaciones_identificadas[0]

            # VALIDACIÓN 1.1: Nombre ubicación vacío
            if not ubicacion.get("nombre_ubicacion") or ubicacion["nombre_ubicacion"].strip() == "":
                errores.append(
                    "No se identificó la ubicación de la actividad en los documentos adjuntos"
                )
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            # VALIDACIÓN 1.2: Asignar porcentaje 100% si no está asignado
            if ubicacion.get("porcentaje_ejecucion", 0.0) != 100.0:
                ubicacion["porcentaje_ejecucion"] = 100.0
                logger.info("Porcentaje asignado a 100% para única ubicación")

            # VALIDACIÓN 2: Texto identificador vacío
            if not ubicacion.get("texto_identificador") or ubicacion["texto_identificador"].strip() == "":
                errores.append(
                    "No se pudo identificar con certeza la ubicación de la actividad. "
                    "Por favor revisar la documentación manualmente"
                )
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            # VALIDACIÓN 3: Código ubicación <= 0
            if ubicacion.get("codigo_ubicacion", 0) <= 0:
                advertencias.append(
                    f"La ubicación '{ubicacion['nombre_ubicacion']}' fue identificada "
                    "pero no está parametrizada en la base de datos"
                )
                errores.append(
                    f"La ubicación '{ubicacion['nombre_ubicacion']}' no está parametrizada "
                    "en la base de datos. Por favor agregar esta ubicación"
                )
                return {"valido": False, "errores": errores, "advertencias": advertencias}

            logger.info("Validaciones de ubicación única exitosas")
            return {"valido": True, "errores": [], "advertencias": advertencias}

        # Caso: Múltiples ubicaciones
        logger.info(f"Validando {len(ubicaciones_identificadas)} ubicaciones...")

        ubicaciones_sin_porcentaje = []
        ubicaciones_no_parametrizadas = []
        suma_porcentajes = 0.0

        for ubicacion in ubicaciones_identificadas:
            # VALIDACIÓN 1: Nombre ubicación vacío
            if not ubicacion.get("nombre_ubicacion") or ubicacion["nombre_ubicacion"].strip() == "":
                errores.append(
                    f"Una de las ubicaciones no tiene nombre identificado"
                )
                continue

            # VALIDACIÓN 2: Texto identificador vacío
            if not ubicacion.get("texto_identificador") or ubicacion["texto_identificador"].strip() == "":
                errores.append(
                    f"No se pudo identificar con certeza la ubicación '{ubicacion['nombre_ubicacion']}'. "
                    "Por favor revisar la documentación manualmente"
                )

            # VALIDACIÓN 3: Código ubicación <= 0
            if ubicacion.get("codigo_ubicacion", 0) <= 0:
                ubicaciones_no_parametrizadas.append(ubicacion['nombre_ubicacion'])
                advertencias.append(
                    f"La ubicación '{ubicacion['nombre_ubicacion']}' no está parametrizada en la base de datos"
                )

            # VALIDACIÓN 4: Porcentaje de ejecución
            porcentaje = ubicacion.get("porcentaje_ejecucion", 0.0)
            if porcentaje <= 0.0:
                ubicaciones_sin_porcentaje.append(ubicacion['nombre_ubicacion'])
            else:
                suma_porcentajes += porcentaje

        # VALIDACIÓN 4.1: Ubicaciones sin porcentaje
        if ubicaciones_sin_porcentaje:
            errores.append(
                f"No se identificó el porcentaje de ejecución para las ubicaciones: "
                f"{', '.join(ubicaciones_sin_porcentaje)}. "
                "Por favor revisar la documentación manualmente"
            )

        # VALIDACIÓN 4.2: Suma de porcentajes != 100%
        if abs(suma_porcentajes - 100.0) > 0.01:  # Tolerancia de 0.01%
            errores.append(
                f"Hay inconsistencia en la sumatoria de los porcentajes de participación "
                f"para cada ubicación (suma: {suma_porcentajes}%, esperado: 100%)"
            )

        # VALIDACIÓN 5: Ubicaciones no parametrizadas
        if ubicaciones_no_parametrizadas:
            errores.append(
                f"Las siguientes ubicaciones no están parametrizadas en la base de datos: "
                f"{', '.join(ubicaciones_no_parametrizadas)}"
            )

        # Determinar si las validaciones pasaron
        if errores:
            logger.warning(f"Validaciones de ubicaciones fallaron: {len(errores)} errores")
            return {"valido": False, "errores": errores, "advertencias": advertencias}

        logger.info("Validaciones de múltiples ubicaciones exitosas")
        return {"valido": True, "errores": [], "advertencias": advertencias}

    def _obtener_actividades_por_ubicacion(
        self,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Obtiene actividades de la BD para cada ubicación identificada.

        RESPONSABILIDAD (SRP):
        - Solo obtiene actividades de la base de datos
        - No valida ni procesa datos

        Args:
            ubicaciones_identificadas: Ubicaciones validadas

        Returns:
            Dict: Actividades agrupadas por codigo_ubicacion
        """
        logger.info("Consultando actividades por ubicación...")

        actividades_por_ubicacion = {}

        try:
            for ubicacion in ubicaciones_identificadas:
                codigo_ubicacion = ubicacion.get("codigo_ubicacion")
                nombre_ubicacion = ubicacion.get("nombre_ubicacion")

                if codigo_ubicacion <= 0:
                    logger.warning(f"Saltando ubicación sin código: {nombre_ubicacion}")
                    continue

                # Consultar tabla ACTIVIDADES IK
                # NOTA: Usar comillas dobles para escapar nombres con espacios
                response = self.database_manager.db_connection.supabase.table("ACTIVIDADES IK").select(
                    "CODIGO_UBICACION, NOMBRE_UBICACION, CODIGO_DE_LA_ACTIVIDAD, "
                    "DESCRIPCION_DE_LA_ACTIVIDAD, PORCENTAJE_ICA, TIPO_DE_ACTIVIDAD"
                ).eq("CODIGO_UBICACION", codigo_ubicacion).execute()

                if not response.data:
                    logger.warning(f"No se encontraron actividades para ubicación {codigo_ubicacion}")
                    continue

                # Mapear a formato estándar
                actividades = [
                    {
                        "codigo_ubicacion": act["CODIGO_UBICACION"],
                        "nombre_ubicacion": act["NOMBRE_UBICACION"],
                        "codigo_actividad": act["CODIGO_DE_LA_ACTIVIDAD"],
                        "descripcion_actividad": act["DESCRIPCION_DE_LA_ACTIVIDAD"],
                        "porcentaje_ica": act["PORCENTAJE_ICA"],
                        "tipo_actividad": act["TIPO_DE_ACTIVIDAD"]
                    }
                    for act in response.data
                ]

                # Validar que el nombre de ubicación coincida
                if actividades and actividades[0]["nombre_ubicacion"] != nombre_ubicacion:
                    logger.error(
                        f"El nombre de ubicación de BD '{actividades[0]['nombre_ubicacion']}' "
                        f"no coincide con el identificado por Gemini '{nombre_ubicacion}'"
                    )
                    continue

                actividades_por_ubicacion[str(codigo_ubicacion)] = actividades
                logger.info(f"Actividades obtenidas para ubicación {codigo_ubicacion}: {len(actividades)}")

            return actividades_por_ubicacion

        except Exception as e:
            logger.error(f"Error consultando ACTIVIDADES IK: {e}")
            return {}

    async def _relacionar_actividades_gemini(
        self,
        ubicaciones_identificadas: List[Dict[str, Any]],
        actividades_bd_por_ubicacion: Dict[str, List[Dict[str, Any]]],
        textos_documentos: Dict[str, str],
        archivos_directos: List[Any] = None,
        nit_administrativo: str = None
    ) -> List[Dict[str, Any]]:
        """
        Segunda llamada a Gemini para relacionar actividades facturadas con BD (MULTIMODAL).

        RESPONSABILIDAD (SRP):
        - Solo coordina la llamada a Gemini
        - No valida resultados (eso lo hace _validar_actividades_manualmente)

        PROCESAMIENTO HÍBRIDO:
        - Textos extraídos (Excel, Word) se incluyen en el prompt
        - Archivos directos (PDF, imágenes) se envían a Gemini para análisis multimodal

        Args:
            ubicaciones_identificadas: Ubicaciones validadas
            actividades_bd_por_ubicacion: Actividades de BD por ubicación
            textos_documentos: Textos de documentos preprocesados
            archivos_directos: Archivos clonados desde cache para procesamiento multimodal (opcional)
            nit_administrativo: NIT para organizar archivos guardados (opcional)

        Returns:
            List[Dict]: Actividades facturadas relacionadas con BD
        """
        logger.info("Segunda llamada Gemini: relacionando actividades (MULTIMODAL)...")

        try:
            # Preparar nombres de archivos directos para el prompt
            archivos_directos = archivos_directos or []
            nombres_archivos_directos = [
                archivo.filename if hasattr(archivo, 'filename') else (archivo.name if hasattr(archivo, 'name') else f"archivo_{i}")
                for i, archivo in enumerate(archivos_directos)
            ]

            # Crear prompt con información de archivos directos
            prompt = crear_prompt_relacionar_actividades(
                ubicaciones_identificadas=ubicaciones_identificadas,
                actividades_bd_por_ubicacion=actividades_bd_por_ubicacion,
                textos_documentos=textos_documentos,
                nombres_archivos_directos=nombres_archivos_directos if archivos_directos else None
            )

            # Preparar contenido para Gemini (MULTIMODAL)
            contenido_gemini = [prompt]

            # Agregar archivos directos para análisis multimodal
            if archivos_directos:
                # CORRECCIÓN: Procesar archivos al formato esperado por Gemini
                archivos_procesados = await self._procesar_archivos_para_gemini(archivos_directos)
                contenido_gemini.extend(archivos_procesados)
                logger.info(f"📎 ICA - Enviando {len(archivos_procesados)} archivos procesados a Gemini para relacionar actividades")

            # Llamar a Gemini con contexto completo
            loop = asyncio.get_event_loop()
            respuesta = await loop.run_in_executor(
                None,
                lambda: self.procesador_gemini.modelo.generate_content(contenido_gemini)
            )

            # Limpiar y parsear respuesta
            respuesta_texto = respuesta.text
            json_limpio = limpiar_json_gemini(respuesta_texto)
            data = json.loads(json_limpio)

            # 💾 GUARDAR RESPUESTA DE GEMINI (Segunda llamada - actividades)
            self._guardar_respuesta_gemini(
                respuesta_texto=respuesta_texto,
                data_parseada=data,
                tipo_llamada="actividades",
                nit_administrativo=nit_administrativo
            )

            # Validar estructura
            if not validar_estructura_actividades(data):
                logger.error("Estructura de JSON de actividades inválida")
                return []

            actividades_facturadas = data.get("actividades_facturadas", [])
            logger.info(f"Gemini identificó {len(actividades_facturadas)} actividades facturadas")
            return actividades_facturadas

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini (actividades): {e}")
            return []
        except Exception as e:
            logger.error(f"Error en llamada a Gemini (actividades): {e}")
            return []

    def _validar_actividades_manualmente(
        self,
        actividades_facturadas: List[Dict[str, Any]],
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Valida manualmente las actividades identificadas por Gemini.

        VALIDACIONES MANUALES (Python):
        1. Nombre actividad vacío
        2. Base gravable <= 0
        3. Actividades relacionadas vacías
        4. Códigos actividad/ubicación <= 0
        5. Una sola actividad relacionada por ubicación

        Args:
            actividades_facturadas: Actividades de Gemini
            ubicaciones_identificadas: Ubicaciones validadas

        Returns:
            Dict con validación: {"valido": bool, "errores": List[str], "advertencias": List[str], "todas_no_aplican": bool}
        """
        logger.info("Aplicando validaciones manuales a actividades...")

        errores = []
        advertencias = []
        actividades_no_aplican = []

        for act_fact in actividades_facturadas:
            nombre_actividad = act_fact.get("nombre_actividad", "").strip()

            # VALIDACIÓN 1: Nombre actividad vacío
            if not nombre_actividad:
                errores.append(
                    "No se pudo identificar una actividad facturada de la documentación"
                )
                continue

            # VALIDACIÓN 2: Base gravable <= 0
            base_gravable = act_fact.get("base_gravable", 0.0)
            if base_gravable <= 0:
                errores.append(
                    f"No se pudo identificar la base gravable para la actividad facturada '{nombre_actividad}'"
                )
                continue

            # VALIDACIÓN 3: Actividades relacionadas
            actividades_relacionadas = act_fact.get("actividades_relacionadas", [])

            if not actividades_relacionadas or len(actividades_relacionadas) == 0:
                advertencias.append(f"La actividad facturada '{nombre_actividad}' no tiene actividades relacionadas")
                actividades_no_aplican.append(nombre_actividad)
                continue

            # Validar cada actividad relacionada
            tiene_relacion_valida = False
            ubicaciones_validadas = set()

            for act_rel in actividades_relacionadas:
                nombre_act_rel = act_rel.get("nombre_act_rel", "").strip()

                # Si nombre vacío, marcar como no aplica
                if not nombre_act_rel:
                    continue

                # VALIDACIÓN 4: Códigos <= 0
                codigo_actividad = act_rel.get("codigo_actividad", 0)
                codigo_ubicacion = act_rel.get("codigo_ubicacion", 0)

                if codigo_actividad <= 0 or codigo_ubicacion <= 0:
                    errores.append(
                        f"No se pudo relacionar correctamente la actividad '{nombre_act_rel}' "
                        f"con su código de actividad y código de ubicación"
                    )
                    return {"valido": False, "errores": errores, "advertencias": advertencias, "todas_no_aplican": False}

                # VALIDACIÓN 5: Solo una actividad relacionada por ubicación
                if codigo_ubicacion in ubicaciones_validadas:
                    errores.append(
                        f"La actividad '{nombre_actividad}' tiene múltiples actividades relacionadas "
                        f"para la misma ubicación {codigo_ubicacion}. Solo puede haber UNA por ubicación"
                    )
                    return {"valido": False, "errores": errores, "advertencias": advertencias, "todas_no_aplican": False}

                ubicaciones_validadas.add(codigo_ubicacion)
                tiene_relacion_valida = True

            # Si no tiene ninguna relación válida, marcar como no aplica
            if not tiene_relacion_valida:
                actividades_no_aplican.append(nombre_actividad)
                advertencias.append(f"La actividad facturada '{nombre_actividad}' no aplica ICA")

        # Determinar resultado
        if errores:
            logger.warning(f"Validaciones de actividades fallaron: {len(errores)} errores")
            return {"valido": False, "errores": errores, "advertencias": advertencias, "todas_no_aplican": False}

        # Si todas las actividades no aplican
        if len(actividades_no_aplican) == len(actividades_facturadas):
            errores.append(
                f"Las actividades facturadas {', '.join(actividades_no_aplican)} no aplican ICA"
            )
            return {"valido": False, "errores": errores, "advertencias": advertencias, "todas_no_aplican": True}

        logger.info("Validaciones de actividades exitosas")
        return {"valido": True, "errores": [], "advertencias": advertencias, "todas_no_aplican": False}
