"""
LIQUIDADOR SOBRETASA BOMBERIL
==============================

Módulo para calcular la Sobretasa Bomberil basándose en el resultado
de la liquidación de ICA. Este impuesto solo aplica cuando ICA es mayor a cero.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo cálculos de Sobretasa Bomberil
- DIP: Depende de abstracciones (database_manager)
- OCP: Abierto para extensión (nuevas tarifas/reglas)
- LSP: Puede sustituirse por otras implementaciones

ARQUITECTURA:
- ICA: Liquidación previa requerida
- Sobretasa Bomberil: Impuesto independiente calculado sobre ICA por ubicación

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

# Configuración de logging
logger = logging.getLogger(__name__)


class LiquidadorSobretasaBomberil:
    """
    Liquidador especializado para Sobretasa Bomberil.

    RESPONSABILIDADES (SRP):
    - Validar que ICA aplica y tiene valor > 0
    - Iterar todas las ubicaciones identificadas en ICA
    - Consultar tarifa de la base de datos por cada ubicación
    - Calcular sobretasa por ubicación: valor_ica_ubicacion * tarifa
    - Generar resultado estructurado con lista de ubicaciones

    DEPENDENCIAS (DIP):
    - database_manager: Para consultas de tarifas
    """

    def __init__(self, database_manager: Any):
        """
        Inicializa el liquidador Sobretasa Bomberil con inyección de dependencias.

        Args:
            database_manager: Gestor de base de datos (abstracción)
        """
        self.database_manager = database_manager
        logger.info("LiquidadorSobretasaBomberil inicializado siguiendo principios SOLID")

    def liquidar_sobretasa_bomberil(
        self,
        resultado_ica: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Liquida Sobretasa Bomberil basándose en el resultado de ICA.

        FLUJO:
        1. Validar que valor_ica > 0
        2. Extraer todas las ubicaciones de las actividades relacionadas
        3. Para cada ubicación:
           - Consultar tarifa en tabla TASA_BOMBERIL
           - Calcular: valor_sobretasa_ubicacion = valor_ica_ubicacion * tarifa
        4. Sumar todos los valores por ubicación
        5. Generar resultado estructurado con lista de ubicaciones

        VALIDACIONES:
        - Si valor_ica <= 0: No aplica (preliquidación sin finalizar)
        - Si error en BD: Preliquidación sin finalizar
        - Si ninguna ubicación tiene tarifa: No aplica impuesto
        - Si al menos una ubicación tiene tarifa: Preliquidado

        Args:
            resultado_ica: Resultado de la liquidación de ICA

        Returns:
            Dict con resultado final de liquidación Sobretasa Bomberil:
            {
                "aplica": bool,
                "estado": str,
                "valor_total_sobretasa": float,
                "ubicaciones": [
                    {
                        "nombre_ubicacion": str,
                        "codigo_ubicacion": int,
                        "tarifa": float,
                        "base_gravable_ica": float,
                        "valor": float
                    }
                ],
                "observaciones": str,
                "fecha_liquidacion": str
            }
        """
        logger.info("Iniciando liquidación Sobretasa Bomberil...")

        # Resultado base
        resultado = {
            "aplica": False,
            "estado": "No aplica impuesto",
            "valor_total_sobretasa": 0.0,
            "ubicaciones": [],
            "observaciones": "",
            "fecha_liquidacion": datetime.now().isoformat()
        }

        try:
            # VALIDACIÓN 1: Verificar que ICA tiene valor > 0
            valor_total_ica = resultado_ica.get("valor_total_ica", 0.0)

            if valor_total_ica <= 0:
                resultado["estado"] = "Preliquidacion sin finalizar"
                resultado["observaciones"] = (
                    "No aplica ICA, por tanto no aplica Sobretasa Bomberil"
                )
                logger.info("Sobretasa Bomberil no aplica - ICA no tiene valor")
                return resultado

            # PASO 2: Extraer todas las ubicaciones de ICA
            ubicaciones_ica = self._extraer_ubicaciones_ica(resultado_ica)

            if not ubicaciones_ica:
                resultado["estado"] = "Preliquidacion sin finalizar"
                resultado["observaciones"] = (
                    "No se pudieron identificar ubicaciones en el análisis de ICA"
                )
                logger.error("No se encontraron ubicaciones en resultado ICA")
                return resultado

            logger.info(f"Procesando {len(ubicaciones_ica)} ubicaciones de ICA")

            # PASO 3: Procesar cada ubicación
            ubicaciones_liquidadas = []
            valor_total_sobretasa = 0.0
            error_bd = False

            for ubicacion_ica in ubicaciones_ica:
                codigo_ubicacion = ubicacion_ica["codigo_ubicacion"]
                nombre_ubicacion = ubicacion_ica["nombre_ubicacion"]
                valor_ica_ubicacion = ubicacion_ica["valor_ica"]

                # Consultar tarifa en la base de datos
                resultado_tarifa = self._obtener_tarifa_bd(codigo_ubicacion)

                # VALIDACIÓN: Error en consulta de BD
                if resultado_tarifa["error"]:
                    error_bd = True
                    logger.error(
                        f"Error consultando TASA_BOMBERIL para ubicación {codigo_ubicacion}"
                    )
                    continue

                # Si la ubicación no tiene tarifa, no la agregamos
                if resultado_tarifa["tarifa"] is None:
                    logger.info(
                        f"Ubicación {nombre_ubicacion} no tiene Sobretasa Bomberil"
                    )
                    continue

                # CÁLCULO: valor_sobretasa = valor_ica_ubicacion * tarifa
                tarifa_bd = resultado_tarifa["tarifa"]
                valor_sobretasa_ubicacion = valor_ica_ubicacion * tarifa_bd

                logger.info(
                    f"  Ubicación {nombre_ubicacion}: ${valor_ica_ubicacion:,.2f} x "
                    f"{tarifa_bd} = ${valor_sobretasa_ubicacion:,.2f}"
                )

                # Agregar ubicación liquidada
                ubicaciones_liquidadas.append({
                    "nombre_ubicacion": nombre_ubicacion,
                    "codigo_ubicacion": codigo_ubicacion,
                    "tarifa": tarifa_bd,
                    "base_gravable_ica": round(valor_ica_ubicacion, 2),
                    "valor": round(valor_sobretasa_ubicacion, 2)
                })

                valor_total_sobretasa += valor_sobretasa_ubicacion

            # VALIDACIÓN 2: Si hubo error de BD
            if error_bd and not ubicaciones_liquidadas:
                resultado["estado"] = "Preliquidacion sin finalizar"
                resultado["observaciones"] = "Error al consultar la base de datos"
                logger.error("Error en todas las consultas a Base de datos")
                return resultado

            # VALIDACIÓN 3: Ninguna ubicación tiene tarifa (no aplica)
            if not ubicaciones_liquidadas:
                resultado["estado"] = "No aplica impuesto"
                resultado["observaciones"] = (
                    f"Ninguna de las {len(ubicaciones_ica)} ubicaciones aplica Sobretasa Bomberil"
                )
                logger.info("Sobretasa Bomberil no aplica - Ninguna ubicación tiene tarifa")
                return resultado

            # PASO 4: Generar resultado exitoso
            resultado["aplica"] = True
            resultado["estado"] = "Preliquidado"
            resultado["valor_total_sobretasa"] = round(valor_total_sobretasa, 2)
            resultado["ubicaciones"] = ubicaciones_liquidadas
            resultado["observaciones"] = (
                f"Sobretasa Bomberil aplicada en {len(ubicaciones_liquidadas)} ubicación(es)"
            )

            logger.info(
                f"Liquidación Sobretasa Bomberil exitosa - Total: ${valor_total_sobretasa:,.2f}"
            )
            return resultado

        except Exception as e:
            logger.error(f"Error en liquidación Sobretasa Bomberil: {e}")
            resultado["estado"] = "Preliquidacion sin finalizar"
            resultado["observaciones"] = f"Error en liquidación: {str(e)}"
            return resultado

    def _extraer_ubicaciones_ica(
        self,
        resultado_ica: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extrae todas las ubicaciones y sus valores de ICA.

        RESPONSABILIDAD (SRP):
        - Solo extrae ubicaciones de actividades relacionadas
        - Itera todas las actividades relacionadas de la primera actividad facturada

        Args:
            resultado_ica: Resultado de liquidación ICA

        Returns:
            List[Dict]: Lista de ubicaciones con estructura:
            [
                {
                    "codigo_ubicacion": int,
                    "nombre_ubicacion": str,
                    "valor_ica": float
                }
            ]
        """
        ubicaciones = []

        try:
            # Obtener actividades facturadas
            actividades_facturadas = resultado_ica.get("actividades_facturadas", [])

            if not actividades_facturadas:
                logger.warning("No hay actividades facturadas en resultado ICA")
                return ubicaciones

            # Tomar la primera actividad facturada - OJO En este punto solo se usa la primera puede que cambie
            
            primera_actividad = actividades_facturadas[0]
            actividades_relacionadas = primera_actividad.get("actividades_relacionada", [])

            if not actividades_relacionadas:
                logger.warning("No hay actividades relacionadas en primera actividad")
                return ubicaciones

            # ITERAR TODAS las actividades relacionadas
            for act_rel in actividades_relacionadas:
                codigo_ubicacion = act_rel.get("codigo_ubicacion")
                nombre_ubicacion = act_rel.get("nombre_ubicacion", "")
                valor_ica = act_rel.get("valor", 0.0)

                if codigo_ubicacion:
                    ubicaciones.append({
                        "codigo_ubicacion": codigo_ubicacion,
                        "nombre_ubicacion": nombre_ubicacion,
                        "valor_ica": valor_ica
                    })
                    logger.info(
                        f"Ubicación extraída: {nombre_ubicacion} (código: {codigo_ubicacion}) "
                        f"- Valor ICA: ${valor_ica:,.2f}"
                    )

            logger.info(f"Total ubicaciones extraídas: {len(ubicaciones)}")
            return ubicaciones

        except Exception as e:
            logger.error(f"Error extrayendo ubicaciones de ICA: {e}")
            return ubicaciones

    def _obtener_tarifa_bd(self, codigo_ubicacion: int) -> Dict[str, Any]:
        """
        Obtiene la tarifa de Sobretasa Bomberil de la base de datos.

        RESPONSABILIDAD (SRP):
        - Solo consulta tarifa de la BD para una ubicación específica
        - No calcula ni valida lógica de negocio

        Args:
            codigo_ubicacion: Código de ubicación

        Returns:
            Dict con estructura:
            {
                "tarifa": float | None,
                "nombre_ubicacion": str,
                "error": bool,
                "mensaje": str
            }
        """
        try:
            logger.info(f"Consultando tarifa Sobretasa Bomberil para ubicación {codigo_ubicacion}")

            # Consultar tabla TASA_BOMBERIL
            response = self.database_manager.db_connection.supabase.table("TASA_BOMBERIL").select(
                "CODIGO_UBICACION, NOMBRE_UBICACION, TARIFA"
            ).eq("CODIGO_UBICACION", codigo_ubicacion).execute()

            # Sin registros encontrados
            if not response.data or len(response.data) == 0:
                logger.info(
                    f"No se encontró tarifa Sobretasa Bomberil para ubicación {codigo_ubicacion}"
                )
                return {
                    "tarifa": None,
                    "nombre_ubicacion": str(codigo_ubicacion),
                    "error": False,
                    "mensaje": "No aplica para esta ubicación"
                }

            # Registro encontrado
            primer_registro = response.data[0]
            tarifa = primer_registro.get("TARIFA")
            nombre_ubicacion = primer_registro.get("NOMBRE_UBICACION", "")

            logger.info(
                f"Tarifa Sobretasa Bomberil obtenida: {tarifa} para ubicación "
                f"'{nombre_ubicacion}' (código: {codigo_ubicacion})"
            )

            return {
                "tarifa": float(tarifa) if tarifa is not None else None,
                "nombre_ubicacion": nombre_ubicacion,
                "error": False,
                "mensaje": "Tarifa obtenida exitosamente"
            }

        except Exception as e:
            logger.error(f"Error consultando TASA_BOMBERIL: {e}")
            return {
                "tarifa": None,
                "nombre_ubicacion": "",
                "error": True,
                "mensaje": str(e)
            }


# ===============================
# FUNCIÓN DE CONVENIENCIA
# ===============================

def crear_liquidador_sobretasa_bomberil(database_manager: Any) -> LiquidadorSobretasaBomberil:
    """
    Factory function para crear instancia de LiquidadorSobretasaBomberil.

    PRINCIPIO: Factory Pattern para creación simplificada

    Args:
        database_manager: Gestor de base de datos

    Returns:
        LiquidadorSobretasaBomberil: Instancia configurada
    """
    return LiquidadorSobretasaBomberil(database_manager)
