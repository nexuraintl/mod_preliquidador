"""
BackgroundProcessor - Ejecuta el flujo completo de procesamiento en background

SRP: Responsabilidad unica - orquestar flujo de procesamiento
DIP: Depende de abstracciones (WebhookPublisher)
OCP: Extensible sin modificar - inyectar nuevos validadores/liquidadores

PRINCIPIO CLAVE: NO duplica logica, REUTILIZA funciones existentes de main.py
"""

import logging
import traceback
from typing import List, Dict, Any
from datetime import datetime
from io import BytesIO

# Fastapi UploadFile para reconstruir archivos
from fastapi import UploadFile

# Importar componentes de Background
from .webhook_publisher import WebhookPublisher

logger = logging.getLogger(__name__)


class BackgroundProcessor:
    """
    Ejecuta el flujo completo de procesamiento en background.

    SRP: Responsabilidad unica - orquestar flujo de procesamiento
    DIP: Depende de abstracciones (WebhookPublisher)
    OCP: Extensible sin modificar - inyectar nuevos validadores/liquidadores

    PRINCIPIO CLAVE: NO duplica logica, REUTILIZA funciones existentes de main.py
    """

    def __init__(
        self,
        webhook_publisher: WebhookPublisher,
        business_service,
        db_manager
    ):
        """
        Args:
            webhook_publisher: Publicador de webhooks (DIP)
            business_service: Servicio de datos de negocio (DIP)
            db_manager: Database manager (DIP)
        """
        self.webhook_publisher = webhook_publisher
        self.business_service = business_service
        self.db_manager = db_manager

    async def procesar_factura_background(
        self,
        factura_id: int,
        archivos_data: List[Dict[str, Any]],
        parametros: Dict[str, Any]
    ) -> None:
        """
        Ejecuta el procesamiento completo en background.

        FLUJO:
        1. Reconstruir UploadFile desde bytes
        2. Ejecutar flujo completo (REUTILIZAR codigo main.py)
        3. Guardar JSON local
        4. Enviar resultado a webhook (factura_id se agrega en payload del webhook)
        5. Manejar errores

        Args:
            factura_id: ID unico de la factura del cliente (entero)
            archivos_data: Lista de diccionarios con {filename, content_type, content (bytes)}
            parametros: Parametros del endpoint (codigo_negocio, proveedor, etc.)
        """
        try:
            logger.info(f"Factura {factura_id}: Iniciando procesamiento en background")

            # Reconstruir UploadFile desde bytes
            archivos = self._reconstruir_archivos(archivos_data)

            # EJECUTAR FLUJO COMPLETO (REUTILIZAR main.py)
            resultado = await self._ejecutar_flujo_completo(
                archivos=archivos,
                parametros=parametros
            )

            # Guardar JSON local (respaldo)
            from config import guardar_archivo_json
            guardar_archivo_json(resultado, f"resultado_final_{factura_id}")

            # ENVIAR RESULTADO A WEBHOOK
            logger.info(f"Factura {factura_id}: Enviando resultado a webhook")
            webhook_response = await self.webhook_publisher.enviar_resultado(
                factura_id=factura_id,
                resultado=resultado
            )

            # Agregar informacion de webhook al log
            if webhook_response["success"]:
                logger.info(
                    f"Factura {factura_id}: Webhook exitoso "
                    f"(intentos: {webhook_response['intentos']})"
                )
            else:
                logger.warning(
                    f"Factura {factura_id}: Webhook fallo - {webhook_response['message']}"
                )

            logger.info(f"Factura {factura_id}: Procesamiento completado exitosamente")

        except Exception as e:
            error_msg = f"Error en procesamiento background: {str(e)}"
            error_traceback = traceback.format_exc()

            logger.error(f"Factura {factura_id}: {error_msg}")
            logger.error(f"Traceback: {error_traceback}")

            # Guardar error en JSON local
            from config import guardar_archivo_json
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": error_msg,
                "error_traceback": error_traceback,
                "parametros": parametros
            }
            guardar_archivo_json(error_data, f"error_procesamiento_{factura_id}")

            # Intentar enviar error a webhook
            try:
                await self.webhook_publisher.enviar_resultado(
                    factura_id=factura_id,
                    resultado=error_data
                )
            except Exception as webhook_error:
                logger.error(
                    f"Factura {factura_id}: Error adicional enviando error a webhook: {webhook_error}"
                )

    def _reconstruir_archivos(self, archivos_data: List[Dict[str, Any]]) -> List[UploadFile]:
        """
        Reconstruye objetos UploadFile desde bytes.

        Args:
            archivos_data: Lista de diccionarios con {filename, content_type, content}

        Returns:
            Lista de UploadFile reconstruidos
        """
        archivos = []
        for archivo_data in archivos_data:
            # Crear BytesIO desde bytes
            file_obj = BytesIO(archivo_data["content"])

            # Crear UploadFile
            # NOTA: content_type es read-only, no se puede asignar despues
            # El content_type original ya fue usado para validacion antes de guardar bytes
            upload_file = UploadFile(
                filename=archivo_data["filename"],
                file=file_obj
            )

            archivos.append(upload_file)

        return archivos

    async def _ejecutar_flujo_completo(
        self,
        archivos: List[UploadFile],
        parametros: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el flujo completo de procesamiento.

        IMPORTANTE: REUTILIZA codigo existente de main.py
        NO duplica logica - IMPORTA funciones modulares

        Args:
            archivos: Lista de archivos
            parametros: Parametros del endpoint

        Returns:
            Dict con resultado completo del procesamiento
        """
        # ================================
        # IMPORTAR FUNCIONES DE main.py
        # ================================
        from app.validacion_negocios import validar_negocio
        from app.validacion_archivos import ValidadorArchivos
        from app.extraccion_hibrida import ExtractorHibrido
        from app.clasificacion_documentos import clasificar_archivos
        from app.preparacion_tareas_analisis import preparar_tareas_analisis
        from app.ejecucion_tareas_paralelo import ejecutar_tareas_paralelo
        from app.validar_retefuente import validar_retencion_en_la_fuente
        from app.validar_impuestos_esp import validar_impuestos_especiales
        from app.validar_iva_reteiva import validar_iva_reteiva
        from app.validar_estampillas_generales import validar_estampillas_generales
        from app.validar_ica import validar_ica
        from app.validar_bomberil import validar_sobretasa_bomberil
        from app.validar_tasa_prodeporte import validar_tasa_prodeporte
        from app.validar_timbre import validar_timbre
        from app.impuestos_no_aplicados import agregar_impuestos_no_aplicados
        from Clasificador.clasificador import ProcesadorGemini
        from config import guardar_archivo_json

        # Extraer parametros
        codigo_del_negocio = parametros["codigo_del_negocio"]
        proveedor = parametros["proveedor"]
        nit_proveedor = parametros["nit_proveedor"]
        estructura_contable = parametros["estructura_contable"]
        observaciones_tp = parametros.get("observaciones_tp")
        genera_presupuesto = parametros.get("genera_presupuesto")
        rubro = parametros.get("rubro")
        centro_costos = parametros.get("centro_costos")
        numero_contrato = parametros.get("numero_contrato")
        valor_contrato_municipio = parametros.get("valor_contrato_municipio")
        tipoMoneda = parametros.get("tipoMoneda", "COP")

        # ================================
        # PASO 1: VALIDACION Y CONFIGURACION
        # ================================
        resultado_negocio = self.business_service.obtener_datos_negocio(codigo_del_negocio)

        resultado_validacion = validar_negocio(
            resultado_negocio=resultado_negocio,
            codigo_del_negocio=codigo_del_negocio,
            business_service=self.business_service
        )

        # Manejar resultado de validacion
        from fastapi.responses import JSONResponse

        if isinstance(resultado_validacion, JSONResponse):
            # Error de validacion
            error_detail = resultado_validacion.body.decode('utf-8')
            raise Exception(f"Error en validacion de negocio: {error_detail}")

        # Unpacking directo - funciona gracias a __iter__ del dataclass ResultadoValidacion
        (impuestos_a_procesar, aplica_retencion, aplica_estampilla,
         aplica_obra_publica, aplica_iva, aplica_ica, aplica_timbre,
         aplica_tasa_prodeporte, nombre_negocio, nit_administrativo,
         deteccion_impuestos, nombre_entidad) = resultado_validacion

        # ================================
        # PASO 2: FILTRADO Y VALIDACION DE ARCHIVOS
        # ================================
        validador_archivos = ValidadorArchivos()
        archivos_validos, archivos_ignorados = validador_archivos.validar(archivos)

        # ================================
        # PASO 3: EXTRACCION HIBRIDA DE TEXTO
        # ================================
        extractor_hibrido = ExtractorHibrido()
        archivos_directos, textos_preprocesados = await extractor_hibrido.extraer(archivos_validos)

        # ================================
        # PASO 4: CLASIFICACION HIBRIDA CON MULTIMODALIDAD
        # ================================
        clasificador = ProcesadorGemini(
            estructura_contable=estructura_contable,
            db_manager=self.db_manager
        )

        resultado_clasificacion = await clasificar_archivos(
            clasificador=clasificador,
            archivos_directos=archivos_directos,
            textos_preprocesados=textos_preprocesados,
            provedor=proveedor,
            nit_administrativo=nit_administrativo,
            nombre_entidad=nombre_entidad,
            impuestos_a_procesar=impuestos_a_procesar
        )

        documentos_clasificados, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera, clasificacion = resultado_clasificacion

        # ================================
        # PASO 4.1: PREPARACION DE TAREAS
        # ================================
        resultado_preparacion = await preparar_tareas_analisis(
            clasificador=clasificador,
            estructura_contable=estructura_contable,
            db_manager=self.db_manager,
            documentos_clasificados=documentos_clasificados,
            archivos_directos=archivos_directos,
            aplica_retencion=aplica_retencion,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            aplica_iva=aplica_iva,
            aplica_ica=aplica_ica,
            aplica_timbre=aplica_timbre,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            proveedor=proveedor,
            nit_administrativo=nit_administrativo,
            observaciones_tp=observaciones_tp,
            impuestos_a_procesar=impuestos_a_procesar
        )

        cache_archivos = resultado_preparacion.cache_archivos

        # ================================
        # PASO 4.2: EJECUCION PARALELA
        # ================================
        resultado_ejecucion = await ejecutar_tareas_paralelo(
            tareas_analisis=resultado_preparacion.tareas_analisis,
            max_workers=4
        )

        resultados_analisis = resultado_ejecucion.resultados_analisis

        # Guardar analisis paralelo
        analisis_paralelo_data = {
            "timestamp": datetime.now().isoformat(),
            "impuestos_analizados": resultado_ejecucion.impuestos_procesados,
            "resultados_analisis": resultado_ejecucion.resultados_analisis,
            "metricas": {
                "total_tareas": resultado_ejecucion.total_tareas,
                "exitosas": resultado_ejecucion.tareas_exitosas,
                "fallidas": resultado_ejecucion.tareas_fallidas,
                "tiempo_total_segundos": resultado_ejecucion.tiempo_total
            }
        }
        guardar_archivo_json(analisis_paralelo_data, "analisis_paralelo")

        # ================================
        # PASO 5: LIQUIDACION DE IMPUESTOS
        # ================================
        resultado_final = {
            "impuestos_procesados": impuestos_a_procesar,
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "impuestos": {}
        }

        # Liquidar todos los impuestos (REUTILIZAR funciones existentes)
        resultado_retefuente = await validar_retencion_en_la_fuente(
            resultados_analisis=resultados_analisis,
            aplica_retencion=aplica_retencion,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            estructura_contable=estructura_contable,
            db_manager=self.db_manager,
            nit_administrativo=nit_administrativo,
            tipoMoneda=tipoMoneda,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos
        )
        if resultado_retefuente:
            resultado_final["impuestos"]["retefuente"] = resultado_retefuente

        resultado_especiales = await validar_impuestos_especiales(
            resultados_analisis=resultados_analisis,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            codigo_del_negocio=codigo_del_negocio,
            nombre_negocio=nombre_negocio,
            database_manager=self.db_manager
        )
        if resultado_especiales:
            if "estampilla_universidad" in resultado_especiales:
                resultado_final["impuestos"]["estampilla_universidad"] = resultado_especiales["estampilla_universidad"]
            if "contribucion_obra_publica" in resultado_especiales:
                resultado_final["impuestos"]["contribucion_obra_publica"] = resultado_especiales["contribucion_obra_publica"]

        resultado_iva_reteiva = await validar_iva_reteiva(
            resultados_analisis=resultados_analisis,
            aplica_iva=aplica_iva,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            nit_administrativo=nit_administrativo,
            tipoMoneda=tipoMoneda
        )
        if resultado_iva_reteiva:
            resultado_final["impuestos"]["iva_reteiva"] = resultado_iva_reteiva

        resultado_estampillas_generales = await validar_estampillas_generales(
            resultados_analisis=resultados_analisis
        )
        if resultado_estampillas_generales:
            resultado_final["impuestos"]["estampillas_generales"] = resultado_estampillas_generales

        resultado_ica = await validar_ica(
            resultados_analisis=resultados_analisis,
            aplica_ica=aplica_ica,
            estructura_contable=estructura_contable,
            db_manager=self.db_manager,
            tipoMoneda=tipoMoneda
        )
        if resultado_ica:
            resultado_final["impuestos"]["ica"] = resultado_ica

        resultado_sobretasa = await validar_sobretasa_bomberil(
            resultado_final=resultado_final,
            db_manager=self.db_manager
        )
        if resultado_sobretasa:
            resultado_final["impuestos"]["sobretasa_bomberil"] = resultado_sobretasa

        resultado_tasa_prodeporte = await validar_tasa_prodeporte(
            resultados_analisis=resultados_analisis,
            db_manager=self.db_manager,
            observaciones_tp=observaciones_tp,
            genera_presupuesto=genera_presupuesto,
            rubro=rubro,
            centro_costos=centro_costos,
            numero_contrato=numero_contrato,
            valor_contrato_municipio=valor_contrato_municipio
        )
        if resultado_tasa_prodeporte:
            resultado_final["impuestos"]["tasa_prodeporte"] = resultado_tasa_prodeporte

        resultado_timbre = await validar_timbre(
            resultados_analisis=resultados_analisis,
            aplica_timbre=aplica_timbre,
            db_manager=self.db_manager,
            clasificador_gemini=clasificador,
            nit_administrativo=nit_administrativo,
            codigo_del_negocio=codigo_del_negocio,
            proveedor=proveedor,
            documentos_clasificados=documentos_clasificados,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos
        )
        if resultado_timbre:
            resultado_final["impuestos"]["timbre"] = resultado_timbre

        # ================================
        # COMPLETAR IMPUESTOS QUE NO APLICAN
        # ================================
        agregar_impuestos_no_aplicados(
            resultado_final=resultado_final,
            deteccion_impuestos=deteccion_impuestos,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            aplica_iva=aplica_iva,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte,
            aplica_timbre=aplica_timbre,
            nit_administrativo=nit_administrativo,
            nombre_negocio=nombre_negocio
        )

        # ================================
        # AGREGAR METADATOS FINALES
        # ================================
        resultado_final.update({
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "documentos_procesados": len(archivos),
            "documentos_clasificados": list(clasificacion.keys()),
        })

        return resultado_final
