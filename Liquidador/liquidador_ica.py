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

    def liquidar_ica(self, analisis_clasificador: Dict[str, Any]) -> Dict[str, Any]:
        """
        Liquida ICA basándose en el análisis del clasificador.

        FLUJO:
        1. Validar estado del análisis
        2. Para cada actividad facturada y ubicación:
           - Obtener tarifa de la BD
           - Calcular: valor = base_gravable * tarifa * porcentaje_ubicacion
        3. Sumar todos los valores
        4. Generar resultado estructurado

        Args:
            analisis_clasificador: Resultado del ClasificadorICA

        Returns:
            Dict con resultado final de liquidación ICA
        """
        logger.info("Iniciando liquidación ICA...")

        # Resultado base
        resultado = {
            "aplica": False,
            "estado": "No aplica impuesto",
            "valor_total_ica": 0.0,
            "actividades_facturadas": [],
            "observaciones": analisis_clasificador.get("observaciones", []),
            "fecha_liquidacion": datetime.now().isoformat()
        }

        try:
            # PASO 1: Validar que el análisis del clasificador es válido
            if not analisis_clasificador.get("aplica", False):
                resultado["estado"] = analisis_clasificador.get("estado", "No aplica impuesto")
                logger.info(f"ICA no aplica - Estado: {resultado['estado']}")
                return resultado

            if analisis_clasificador.get("estado") != "Validado - Listo para liquidación":
                resultado["aplica"] = True  # Aplica pero no se puede liquidar
                resultado["estado"] = analisis_clasificador.get("estado", "Preliquidacion sin finalizar")
                logger.warning(f"No se puede liquidar - Estado: {resultado['estado']}")
                return resultado

            # PASO 2: Extraer datos validados
            actividades_facturadas = analisis_clasificador.get("actividades_facturadas", [])
            ubicaciones_identificadas = analisis_clasificador.get("ubicaciones_identificadas", [])

            if not actividades_facturadas:
                resultado["estado"] = "Preliquidacion sin finalizar"
                resultado["observaciones"].append("No hay actividades facturadas para liquidar")
                logger.error("No hay actividades facturadas")
                return resultado

            logger.info(f"Liquidando {len(actividades_facturadas)} actividades")

            # PASO 3: Procesar cada actividad facturada
            actividades_liquidadas = []
            valor_total_ica = 0.0

            for act_fact in actividades_facturadas:
                actividad_liquidada = self._liquidar_actividad_facturada(
                    act_fact, ubicaciones_identificadas
                )

                if actividad_liquidada:
                    # Extraer observaciones de esta actividad y agregarlas al resultado
                    if actividad_liquidada.get("observaciones"):
                        resultado["observaciones"].extend(actividad_liquidada["observaciones"])

                    # Agregar actividad a la lista (sin el campo observaciones interno)
                    actividad_para_resultado = {
                        "nombre_actividad_fact": actividad_liquidada["nombre_actividad_fact"],
                        "base_gravable": actividad_liquidada["base_gravable"],
                        "actividades_relacionada": actividad_liquidada["actividades_relacionada"]
                    }
                    actividades_liquidadas.append(actividad_para_resultado)

                    # Sumar valores de todas las ubicaciones de esta actividad
                    for act_rel in actividad_liquidada["actividades_relacionada"]:
                        valor_total_ica += act_rel["valor"]

            # PASO 4: Validar que se liquidó al menos una actividad
            if not actividades_liquidadas:
                resultado["estado"] = "Preliquidacion sin finalizar"
                resultado["observaciones"].append(
                    "No se pudo liquidar ninguna actividad (problemas obteniendo tarifas de BD)"
                )
                logger.error("No se liquidó ninguna actividad")
                return resultado

            # PASO 5: Generar resultado final exitoso
            resultado["aplica"] = True
            resultado["estado"] = "Preliquidado"
            resultado["valor_total_ica"] = round(valor_total_ica, 2)
            resultado["actividades_facturadas"] = actividades_liquidadas

            logger.info(f"Liquidación ICA exitosa - Total: ${valor_total_ica:,.2f}")
            return resultado

        except Exception as e:
            logger.error(f"Error en liquidación ICA: {e}")
            resultado["estado"] = "Preliquidacion sin finalizar"
            resultado["observaciones"].append(f"Error en liquidación: {str(e)}")
            return resultado

    def _liquidar_actividad_facturada(
        self,
        actividad_facturada: Dict[str, Any],
        ubicaciones_identificadas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Liquida una actividad facturada para todas sus ubicaciones.

        RESPONSABILIDAD (SRP):
        - Solo calcula valores para una actividad
        - Delega consulta de tarifas a método específico
        - Acumula observaciones de tarifas duplicadas

        Args:
            actividad_facturada: Actividad con sus relaciones
            ubicaciones_identificadas: Ubicaciones validadas con porcentajes

        Returns:
            Dict con actividad liquidada y observaciones:
            {
                "nombre_actividad_fact": str,
                "base_gravable": float,
                "actividades_relacionada": List[Dict],
                "observaciones": List[str]  # NUEVO: Observaciones de esta actividad
            }
        """
        nombre_actividad = actividad_facturada.get("nombre_actividad", "")
        base_gravable = actividad_facturada.get("base_gravable", 0.0)
        actividades_relacionadas = actividad_facturada.get("actividades_relacionadas", [])

        logger.info(f"Liquidando actividad: {nombre_actividad} - Base: ${base_gravable:,.2f}")

        actividad_liquidada = {
            "nombre_actividad_fact": nombre_actividad,
            "base_gravable": base_gravable,
            "actividades_relacionada": [],  # Nota: nombre en singular según especificación
            "observaciones": []  # NUEVO: Acumular observaciones de esta actividad
        }

        # Procesar cada actividad relacionada (una por ubicación)
        for act_rel in actividades_relacionadas:
            nombre_act_rel = act_rel.get("nombre_act_rel", "").strip()

            # Saltar si no hay relación
            if not nombre_act_rel:
                continue

            codigo_actividad = act_rel.get("codigo_actividad", 0)
            codigo_ubicacion = act_rel.get("codigo_ubicacion", 0)

            # Obtener porcentaje de ubicación
            porcentaje_ubicacion = self._obtener_porcentaje_ubicacion(
                codigo_ubicacion, ubicaciones_identificadas
            )

            if porcentaje_ubicacion <= 0:
                logger.warning(
                    f"No se encontró porcentaje para ubicación {codigo_ubicacion}"
                )
                continue

            # Obtener tarifa de la BD (ahora retorna dict con tarifa y observacion)
            resultado_tarifa = self._obtener_tarifa_bd(codigo_ubicacion, codigo_actividad)

            if resultado_tarifa["tarifa"] is None:
                logger.error(
                    f"No se pudo obtener tarifa para actividad {codigo_actividad} "
                    f"en ubicación {codigo_ubicacion}"
                )
                continue

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

            # CÁLCULO FINAL: valor = base_gravable * tarifa * porcentaje_ubicacion
            porcentaje_decimal = porcentaje_ubicacion / 100.0
            tarifa_decimal = tarifa_bd / 100.0  # Convertir porcentaje a decimal
            valor_calculado = base_gravable * tarifa_decimal * porcentaje_decimal

            logger.info(
                f"  Ubicación {codigo_ubicacion}: ${base_gravable:,.2f} x "
                f"{tarifa_bd}% x {porcentaje_ubicacion}% = ${valor_calculado:,.2f}"
            )

            # Agregar actividad relacionada liquidada
            actividad_liquidada["actividades_relacionada"].append({
                "nombre_act_rel": nombre_act_rel,
                "tarifa": tarifa_bd,
                "valor": round(valor_calculado, 2),
                "nombre_ubicacion": nombre_ubicacion,
                "codigo_ubicacion": codigo_ubicacion,
                "porcentaje_ubi": porcentaje_ubicacion
            })

        return actividad_liquidada if actividad_liquidada["actividades_relacionada"] else None

    def _obtener_tarifa_bd(
        self,
        codigo_ubicacion: int,
        codigo_actividad: int
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
            ).execute()

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

                return {
                    "tarifa": float(tarifa_primer_registro),
                    "observacion": observacion
                }

            # CASO NORMAL: Un solo registro
            tarifa = response.data[0]["PORCENTAJE_ICA"]
            descripcion = response.data[0]["DESCRIPCION_DE_LA_ACTIVIDAD"]

            logger.info(
                f"Tarifa obtenida: {tarifa}% para actividad '{descripcion}' "
                f"(cod: {codigo_actividad}, ubic: {codigo_ubicacion})"
            )

            return {
                "tarifa": float(tarifa),
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
