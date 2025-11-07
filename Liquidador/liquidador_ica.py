"""
LIQUIDADOR ICA (INDUSTRIA Y COMERCIO)
=====================================

Módulo para calcular la retención de ICA basándose en el análisis
del clasificador ICA. Realiza los cálculos finales según tarifas
parametrizadas en la base de datos.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo cálculos de ICA
- DIP: Depende de abstracciones (database_manager)
- OCP: Abierto para extensión (nuevas tarifas/reglas)
- LSP: Puede sustituirse por otras implementaciones

ARQUITECTURA:
- Clasificador: Identifica y valida datos
- Liquidador: Calcula valores finales

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

# Configuración de logging
logger = logging.getLogger(__name__)


class LiquidadorICA:
    """
    Liquidador especializado para retención de ICA.

    RESPONSABILIDADES (SRP):
    - Recibir datos validados del clasificador
    - Consultar tarifas de la base de datos
    - Realizar cálculos finales de ICA
    - Generar resultado estructurado

    DEPENDENCIAS (DIP):
    - database_manager: Para consultas de tarifas
    """

    def __init__(self, database_manager: Any):
        """
        Inicializa el liquidador ICA con inyección de dependencias.

        Args:
            database_manager: Gestor de base de datos (abstracción)
        """
        self.database_manager = database_manager
        logger.info("LiquidadorICA inicializado siguiendo principios SOLID")

    def liquidar_ica(self, analisis_clasificador: Dict[str, Any], estructura_contable: int) -> Dict[str, Any]:
        """
        Liquida ICA basándose en el análisis del clasificador (NUEVO FORMATO v3.0).

        FLUJO:
        1. Validar estado del análisis
        2. Para cada actividad relacionada:
           - Calcular base_gravable_ubicacion = valor_factura_sin_iva * porcentaje_ubicacion
           - Obtener tarifa de la BD
           - Calcular valor_ica = base_gravable_ubicacion * tarifa
        3. Sumar todos los valores
        4. Generar resultado estructurado con nuevo formato

        Args:
            analisis_clasificador: Resultado del ClasificadorICA (NUEVO FORMATO v3.0)

        Returns:
            Dict con resultado final de liquidación ICA
        """
        logger.info("Iniciando liquidación ICA (NUEVO FORMATO v3.0)...")

        # Resultado base (ESTRUCTURA COMPLETA v3.0)
        resultado = {
            "aplica": False,
            "estado": "no_aplica_impuesto",
            "valor_total_ica": 0.0,
            "actividades_facturadas": [],
            "actividades_relacionadas": [],
            "valor_factura_sin_iva": 0.0,  # NUEVO FORMATO v3.0 - consistencia
            "observaciones": analisis_clasificador.get("observaciones", []),
            "fecha_liquidacion": datetime.now().isoformat()
        }

        try:
            # PASO 1: Validar que el análisis del clasificador es válido
            if not analisis_clasificador.get("aplica", False):
                resultado["estado"] = analisis_clasificador.get("estado", "no_aplica_impuesto")
                logger.info(f"ICA no aplica - Estado: {resultado['estado']}")
                return resultado

            if analisis_clasificador.get("estado") != "Validado - Listo para liquidación":
                resultado["aplica"] = True  # Aplica pero no se puede liquidar
                resultado["estado"] = analisis_clasificador.get("estado", "preliquidacion_sin_finalizar")
                logger.warning(f"No se puede liquidar - Estado: {resultado['estado']}")
                return resultado

            # PASO 2: Extraer datos validados (NUEVO FORMATO v3.0)
            actividades_facturadas = analisis_clasificador.get("actividades_facturadas", [])
            actividades_relacionadas = analisis_clasificador.get("actividades_relacionadas", [])
            valor_factura_sin_iva = analisis_clasificador.get("valor_factura_sin_iva", 0.0)
            ubicaciones_identificadas = analisis_clasificador.get("ubicaciones_identificadas", [])

            if not actividades_relacionadas:
                resultado["estado"] = "preliquidacion_sin_finalizar"
                resultado["observaciones"].append("No hay actividades relacionadas para liquidar")
                resultado["actividades_facturadas"] = actividades_facturadas
                resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa
                logger.error("No hay actividades relacionadas")
                return resultado

            logger.info(f"Liquidando {len(actividades_relacionadas)} actividades relacionadas con valor factura: ${valor_factura_sin_iva:,.2f}")

            # PASO 3: Procesar cada actividad relacionada
            actividades_liquidadas = []
            valor_total_ica = 0.0

            for act_rel in actividades_relacionadas:
                actividad_liquidada = self._liquidar_actividad_facturada(
                    act_rel,
                    valor_factura_sin_iva,
                    ubicaciones_identificadas,
                    estructura_contable
                )

                if actividad_liquidada:
                    # Extraer observaciones de esta actividad y agregarlas al resultado
                    if actividad_liquidada.get("observaciones"):
                        resultado["observaciones"].extend(actividad_liquidada["observaciones"])

                    # Agregar actividad a la lista (sin el campo observaciones interno)
                    actividad_para_resultado = {
                        "nombre_act_rel": actividad_liquidada["nombre_act_rel"],
                        "codigo_actividad": actividad_liquidada["codigo_actividad"],
                        "codigo_ubicacion": actividad_liquidada["codigo_ubicacion"],
                        "nombre_ubicacion": actividad_liquidada["nombre_ubicacion"],
                        "base_gravable_ubicacion": actividad_liquidada["base_gravable_ubicacion"],
                        "tarifa": actividad_liquidada["tarifa"],
                        "porc_ubicacion": actividad_liquidada["porc_ubicacion"],
                        "valor_ica": actividad_liquidada["valor_ica"]
                    }
                    actividades_liquidadas.append(actividad_para_resultado)
                    valor_total_ica += actividad_liquidada["valor_ica"]

            # PASO 4: Validar que se liquidó al menos una actividad
            if not actividades_liquidadas:
                resultado["estado"] = "preliquidacion_sin_finalizar"
                resultado["observaciones"].append(
                    "No se pudo liquidar ninguna actividad (problemas obteniendo tarifas de BD)"
                )
                resultado["actividades_facturadas"] = actividades_facturadas
                resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa
                logger.error("No se liquidó ninguna actividad")
                return resultado

            # PASO 5: Generar resultado final exitoso (NUEVO FORMATO v3.0)
            resultado["aplica"] = True
            resultado["estado"] = "preliquidado"
            resultado["valor_total_ica"] = round(valor_total_ica, 2)
            resultado["actividades_facturadas"] = actividades_facturadas
            resultado["actividades_relacionadas"] = actividades_liquidadas
            resultado["valor_factura_sin_iva"] = valor_factura_sin_iva  # Preservar estructura completa

            logger.info(f"Liquidación ICA exitosa - Total: ${valor_total_ica:,.2f}")
            return resultado

        except Exception as e:
            logger.error(f"Error en liquidación ICA: {e}")
            resultado["estado"] = "preliquidacion_sin_finalizar"
            resultado["observaciones"].append(f"Error en liquidación: {str(e)}")

            # Preservar estructura completa con datos del clasificador si están disponibles
            resultado["actividades_facturadas"] = analisis_clasificador.get("actividades_facturadas", [])
            resultado["actividades_relacionadas"] = analisis_clasificador.get("actividades_relacionadas", [])
            resultado["valor_factura_sin_iva"] = analisis_clasificador.get("valor_factura_sin_iva", 0.0)

            return resultado

    def _liquidar_actividad_facturada(
        self,
        actividad_relacionada: Dict[str, Any],
        valor_factura_sin_iva: float,
        ubicaciones_identificadas: List[Dict[str, Any]],
        estructura_contable: int
    ) -> Dict[str, Any]:
        """
        Liquida una actividad relacionada (NUEVO FORMATO v3.0).

        RESPONSABILIDAD (SRP):
        - Solo calcula valores para una actividad relacionada
        - Usa valor_factura_sin_iva como base única
        - Calcula base_gravable_ubicacion según porcentaje de participación
        - Delega consulta de tarifas a método específico
        - Acumula observaciones de tarifas duplicadas

        CÁLCULOS:
        - base_gravable_ubicacion = valor_factura_sin_iva * (porcentaje_ubicacion / 100)
        - valor_ica = base_gravable_ubicacion * (tarifa / 100)

        Args:
            actividad_relacionada: Actividad relacionada con BD
            valor_factura_sin_iva: Valor total de factura sin IVA
            ubicaciones_identificadas: Ubicaciones validadas con porcentajes

        Returns:
            Dict con actividad liquidada y observaciones:
            {
                "nombre_act_rel": str,
                "codigo_actividad": int,
                "codigo_ubicacion": int,
                "nombre_ubicacion": str,
                "base_gravable_ubicacion": float,
                "tarifa": float,
                "porc_ubicacion": float,
                "valor_ica": float,
                "observaciones": List[str]
            }
        """
        nombre_act_rel = actividad_relacionada.get("nombre_act_rel", "").strip()
        codigo_actividad = actividad_relacionada.get("codigo_actividad", 0)
        codigo_ubicacion = actividad_relacionada.get("codigo_ubicacion", 0)

        logger.info(f"Liquidando actividad relacionada: {nombre_act_rel} (Código: {codigo_actividad}, Ubicación: {codigo_ubicacion})")

        actividad_liquidada = {
            "nombre_act_rel": nombre_act_rel,
            "codigo_actividad": codigo_actividad,
            "codigo_ubicacion": codigo_ubicacion,
            "nombre_ubicacion": "",
            "base_gravable_ubicacion": 0.0,
            "tarifa": 0.0,
            "porc_ubicacion": 0.0,
            "valor_ica": 0.0,
            "observaciones": []
        }

        # Saltar si no hay relación
        if not nombre_act_rel:
            logger.warning("Actividad sin nombre, saltando...")
            return None

        # Obtener porcentaje de ubicación
        porcentaje_ubicacion = self._obtener_porcentaje_ubicacion(
            codigo_ubicacion, ubicaciones_identificadas
        )

        if porcentaje_ubicacion <= 0:
            logger.warning(f"No se encontró porcentaje para ubicación {codigo_ubicacion}")
            return None

        # Calcular base gravable para esta ubicación
        base_gravable_ubicacion = valor_factura_sin_iva * (porcentaje_ubicacion / 100.0)

        logger.info(f"  Base gravable ubicación: ${valor_factura_sin_iva:,.2f} x {porcentaje_ubicacion}% = ${base_gravable_ubicacion:,.2f}")

        # Obtener tarifa de la BD
        resultado_tarifa = self._obtener_tarifa_bd(codigo_ubicacion, codigo_actividad, estructura_contable)

        if resultado_tarifa["tarifa"] is None:
            logger.error(
                f"No se pudo obtener tarifa para actividad {codigo_actividad} "
                f"en ubicación {codigo_ubicacion}"
            )
            return None

        # Extraer tarifa y observación
        tarifa_bd = resultado_tarifa["tarifa"]
        observacion_tarifa = resultado_tarifa["observacion"]

        # Si hay observación de duplicado, agregarla
        if observacion_tarifa:
            actividad_liquidada["observaciones"].append(observacion_tarifa)

        # Obtener nombre de ubicación
        nombre_ubicacion = self._obtener_nombre_ubicacion(
            codigo_ubicacion, ubicaciones_identificadas
        )

        # CÁLCULO FINAL: valor_ica = base_gravable_ubicacion * (tarifa / 100)
        tarifa_decimal = tarifa_bd / 100.0
        valor_ica = base_gravable_ubicacion * tarifa_decimal

        logger.info(
            f"  Cálculo ICA: ${base_gravable_ubicacion:,.2f} x {tarifa_bd}% = ${valor_ica:,.2f}"
        )

        # Actualizar resultado
        actividad_liquidada["nombre_ubicacion"] = nombre_ubicacion
        actividad_liquidada["base_gravable_ubicacion"] = round(base_gravable_ubicacion, 2)
        actividad_liquidada["tarifa"] = tarifa_bd
        actividad_liquidada["porc_ubicacion"] = porcentaje_ubicacion
        actividad_liquidada["valor_ica"] = round(valor_ica, 2)

        return actividad_liquidada

    def _obtener_tarifa_bd(
        self,
        codigo_ubicacion: int,
        codigo_actividad: int,
        estructura_contable: int
    ) -> Dict[str, Any]:
        """
        Obtiene la tarifa de ICA de la base de datos.

        RESPONSABILIDAD (SRP):
        - Solo consulta tarifa de la BD
        - Detecta duplicados y genera observaciones
        - No calcula ni valida lógica de negocio

        Args:
            codigo_ubicacion: Código de ubicación
            codigo_actividad: Código de actividad

        Returns:
            Dict con estructura:
            {
                "tarifa": float | None,  # Tarifa en porcentaje (ej: 9.66)
                "observacion": str | None  # Mensaje si hay duplicados o error
            }
        """
        try:
            # Consultar tabla ACTIVIDADES IK con ambos códigos
            response = self.database_manager.db_connection.supabase.table("ACTIVIDADES IK").select(
                "PORCENTAJE_ICA, DESCRIPCION_DE_LA_ACTIVIDAD"
            ).eq("CODIGO_UBICACION", codigo_ubicacion).eq(
                "CODIGO_DE_LA_ACTIVIDAD", codigo_actividad
            ).eq("ESTRUCTURA_CONTABLE", estructura_contable).execute()

            # VALIDACIÓN 1: Sin registros encontrados
            if not response.data or len(response.data) == 0:
                logger.warning(
                    f"No se encontró tarifa para actividad {codigo_actividad} "
                    f"en ubicación {codigo_ubicacion}"
                )
                return {"tarifa": None, "observacion": None}

            # VALIDACIÓN 2: Más de un registro (duplicado en BD)
            if len(response.data) > 1:
                tarifa_primer_registro = response.data[0]["PORCENTAJE_ICA"]
                descripcion = response.data[0]["DESCRIPCION_DE_LA_ACTIVIDAD"]

                observacion = (
                    f" ADVERTENCIA: La actividad '{descripcion}' (código {codigo_actividad}) "
                    f"en ubicación {codigo_ubicacion} está DUPLICADA en la base de datos "
                    f"({len(response.data)} registros encontrados). "
                    f"Se utilizó el primer registro para el cálculo (tarifa: {tarifa_primer_registro}%)"
                )

                logger.warning(
                    f"Actividad duplicada en BD: {codigo_actividad} en ubicación {codigo_ubicacion} "
                    f"- {len(response.data)} registros encontrados. Usando primer registro."
                )

                # Convertir tarifa manejando formato con coma decimal (5,0 -> 5.0)
                tarifa_convertida = float(str(tarifa_primer_registro).replace(',', '.')) if tarifa_primer_registro is not None else 0.0

                return {
                    "tarifa": tarifa_convertida,
                    "observacion": observacion
                }

            # CASO NORMAL: Un solo registro
            tarifa = response.data[0]["PORCENTAJE_ICA"]
            descripcion = response.data[0]["DESCRIPCION_DE_LA_ACTIVIDAD"]

            logger.info(
                f"Tarifa obtenida: {tarifa}% para actividad '{descripcion}' "
                f"(cod: {codigo_actividad}, ubic: {codigo_ubicacion})"
            )

            # Convertir tarifa manejando formato con coma decimal (5,0 -> 5.0)
            tarifa_convertida = float(str(tarifa).replace(',', '.')) if tarifa is not None else 0.0

            return {
                "tarifa": tarifa_convertida,
                "observacion": None
            }

        except Exception as e:
            logger.error(f"Error consultando tarifa de BD: {e}")
            return {"tarifa": None, "observacion": None}

    def _obtener_porcentaje_ubicacion(
        self,
        codigo_ubicacion: int,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> float:
        """
        Obtiene el porcentaje de ejecución para una ubicación.

        RESPONSABILIDAD (SRP):
        - Solo busca el porcentaje en la lista
        - No valida ni calcula

        Args:
            codigo_ubicacion: Código de ubicación
            ubicaciones_identificadas: Ubicaciones con porcentajes

        Returns:
            float: Porcentaje de ejecución (ej: 60.0 para 60%)
        """
        for ubicacion in ubicaciones_identificadas:
            if ubicacion.get("codigo_ubicacion") == codigo_ubicacion:
                return ubicacion.get("porcentaje_ejecucion", 0.0)

        logger.warning(f"No se encontró porcentaje para ubicación {codigo_ubicacion}")
        return 0.0

    def _obtener_nombre_ubicacion(
        self,
        codigo_ubicacion: int,
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> str:
        """
        Obtiene el nombre de una ubicación.

        RESPONSABILIDAD (SRP):
        - Solo busca el nombre en la lista
        - No valida ni procesa

        Args:
            codigo_ubicacion: Código de ubicación
            ubicaciones_identificadas: Ubicaciones

        Returns:
            str: Nombre de la ubicación
        """
        for ubicacion in ubicaciones_identificadas:
            if ubicacion.get("codigo_ubicacion") == codigo_ubicacion:
                return ubicacion.get("nombre_ubicacion", "")

        logger.warning(f"No se encontró nombre para ubicación {codigo_ubicacion}")
        return ""


# ===============================
# FUNCIÓN DE CONVENIENCIA
# ===============================

def crear_liquidador_ica(database_manager: Any) -> LiquidadorICA:
    """
    Factory function para crear instancia de LiquidadorICA.

    PRINCIPIO: Factory Pattern para creación simplificada

    Args:
        database_manager: Gestor de base de datos

    Returns:
        LiquidadorICA: Instancia configurada
    """
    return LiquidadorICA(database_manager)
