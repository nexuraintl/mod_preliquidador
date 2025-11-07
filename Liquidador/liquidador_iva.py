"""
LIQUIDADOR IVA Y RETEIVA
========================

Módulo para el cálculo preciso de IVA y ReteIVA según normativa colombiana.
Funciona en paralelo con otros liquidadores del sistema integrado.

Funcionalidades:
- Cálculo de ReteIVA para fuente nacional (15%)
- Cálculo de ReteIVA para fuente extranjera (100%)
- Validación de responsabilidad de IVA
- Manejo de casos especiales (exentos, excluidos, no responsables)
- Integración con sistema de procesamiento paralelo

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# Configuración de IVA
from config import (
    obtener_configuracion_iva,
    calcular_reteiva,
    obtener_tarifa_reteiva,
    es_fuente_ingreso_nacional,
    nit_aplica_iva_reteiva
)

logger = logging.getLogger(__name__)

@dataclass
class ResultadoLiquidacionIVA:
    """Resultado estructurado de la liquidación de IVA y ReteIVA"""
    # Datos de entrada
    nit_administrativo: str
    
    # IVA
    valor_iva_identificado: float
    porcentaje_iva: float
    aplica_iva: bool
    
    # ReteIVA
    valor_reteiva: float
    tarifa_reteiva: float
    porcentaje_reteiva_texto: str
    aplica_reteiva: bool
    
    # Fuente de ingreso
    es_fuente_nacional: bool
    metodo_calculo: str
    
    # Estado y validaciones
    estado_liquidacion: str
    es_responsable_iva: Optional[bool]
    observaciones: list
    calculo_exitoso: bool
    
    # Metadatos de cálculo
    timestamp: str
    version_liquidador: str

class LiquidadorIVA:
    """
    Liquidador especializado para cálculo de IVA y ReteIVA.
    
    Calcula retención de IVA según:
    - Fuente nacional: 15% sobre el valor del IVA
    - Fuente extranjera: 100% sobre el valor del IVA
    - Validaciones de responsabilidad y aplicabilidad
    - Casos especiales y excepciones normativas
    """
    
    VERSION = "1.0.0"
    
    def __init__(self):
        """Inicializa el liquidador de IVA con configuración actual"""
        self.config_iva = obtener_configuracion_iva()
        logger.info("✅ LiquidadorIVA inicializado correctamente")
    
    def liquidar_iva_completo(self, analisis_iva: Dict[str, Any], 
                             nit_administrativo: str) -> ResultadoLiquidacionIVA:
        """
        Realiza la liquidación completa de IVA y ReteIVA.
        
        Args:
            analisis_iva: Resultado del análisis de IVA de Gemini
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            ResultadoLiquidacionIVA: Resultado completo de la liquidación
            
        Raises:
            ValueError: Si el NIT no aplica para IVA o datos inválidos
            Exception: Errores de cálculo
        """
        logger.info(f"💰 Iniciando liquidación de IVA para NIT: {nit_administrativo}")
        
        try:
            # 1. Validar NIT administrativo
            if not nit_aplica_iva_reteiva(nit_administrativo):
                raise ValueError(f"NIT {nit_administrativo} no está configurado para IVA/ReteIVA")
            
            # 2. Extraer datos del análisis
            datos_iva = self._extraer_datos_analisis(analisis_iva)
            
            # 3. Validar estado de liquidación
            estado_valido, mensaje_estado = self._validar_estado_liquidacion(datos_iva)
            
            if not estado_valido:
                return self._crear_resultado_no_aplica(
                    nit_administrativo=nit_administrativo,
                    razon=mensaje_estado,
                    datos_iva=datos_iva
                )
            
            # 4. Calcular ReteIVA
            resultado_calculo = self._calcular_reteiva_preciso(
                valor_iva=datos_iva["valor_iva_total"],
                es_fuente_nacional=datos_iva["es_fuente_nacional"]
            )
            
            # 5. Construir resultado final
            resultado = self._construir_resultado_exitoso(
                nit_administrativo=nit_administrativo,
                datos_iva=datos_iva,
                resultado_calculo=resultado_calculo
            )
            
            logger.info(f"✅ Liquidación completada: ReteIVA=${resultado.valor_reteiva:,.2f}")
            return resultado
            
        except Exception as e:
            error_msg = f"❌ Error en liquidación de IVA: {str(e)}"
            logger.error(error_msg)
            
            return self._crear_resultado_error(
                nit_administrativo=nit_administrativo,
                mensaje_error=error_msg
            )
    
    def _extraer_datos_analisis(self, analisis_iva: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae y valida los datos necesarios del análisis de IVA.
        
        Args:
            analisis_iva: Resultado del análisis de Gemini
            
        Returns:
            Dict con datos extraídos y validados
            
        Raises:
            ValueError: Si faltan datos críticos
        """
        try:
            # Extraer estructura principal
            iva_data = analisis_iva.get("analisis_iva", {})
            fuente_data = analisis_iva.get("analisis_fuente_ingreso", {})
            reteiva_data = analisis_iva.get("calculo_reteiva", {})
            estado_data = analisis_iva.get("estado_liquidacion", {})
            
            # Datos de IVA
            iva_identificado = iva_data.get("iva_identificado", {})
            responsabilidad_iva = iva_data.get("responsabilidad_iva_rut", {})
            concepto_facturado = iva_data.get("concepto_facturado", {})
            
            # Construir datos extraídos
            datos = {
                # IVA identificado
                "tiene_iva": iva_identificado.get("tiene_iva", False),
                "valor_iva_total": float(iva_identificado.get("valor_iva_total", 0.0)),
                "porcentaje_iva": float(iva_identificado.get("porcentaje_iva", 0.0)),
                "detalle_conceptos_iva": iva_identificado.get("detalle_conceptos_iva", []),
                
                # Responsabilidad IVA
                "rut_disponible": responsabilidad_iva.get("rut_disponible", False),
                "es_responsable_iva": responsabilidad_iva.get("es_responsable_iva"),
                "codigo_encontrado": responsabilidad_iva.get("codigo_encontrado", "no_encontrado"),
                
                # Concepto facturado
                "concepto_descripcion": concepto_facturado.get("descripcion", "No identificado"),
                "concepto_aplica_iva": concepto_facturado.get("aplica_iva", True),
                "categoria_concepto": concepto_facturado.get("categoria", "no_identificado"),
                
                # Fuente de ingreso
                "es_fuente_nacional": fuente_data.get("es_fuente_nacional", True),
                "validaciones_fuente": fuente_data.get("validaciones_fuente", {}),
                
                # ReteIVA
                "aplica_reteiva": reteiva_data.get("aplica_reteiva", False),
                "porcentaje_reteiva": reteiva_data.get("porcentaje_reteiva", "0%"),
                "metodo_calculo": reteiva_data.get("metodo_calculo", "no_definido"),
                
                # Estado
                "estado_liquidacion": estado_data.get("estado", "Error en procesamiento"),
                "observaciones": estado_data.get("observaciones", [])
            }
            
            logger.info(f"📊 Datos extraídos: IVA=${datos['valor_iva_total']:,.2f}, Estado={datos['estado_liquidacion']}")
            return datos
            
        except Exception as e:
            error_msg = f"Error extrayendo datos del análisis: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
    
    def _validar_estado_liquidacion(self, datos_iva: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valida si el estado permite proceder con la liquidación.
        
        Args:
            datos_iva: Datos extraídos del análisis
            
        Returns:
            Tuple[bool, str]: (es_valido, mensaje_explicativo)
        """
        estado = datos_iva["estado_liquidacion"]
        
        # Estados que NO permiten liquidación
        estados_no_validos = [
            "NO APLICA IVA, EL VALOR DEL IVA = 0",
            "Preliquidación Sin Finalizar",
            "Error en procesamiento"
        ]
        
        if estado in estados_no_validos:
            return False, f"Estado no permite liquidación: {estado}"
        
        # Validaciones adicionales
        if not datos_iva["tiene_iva"]:
            return False, "No se identificó IVA en la factura"
        
        if datos_iva["valor_iva_total"] <= 0:
            return False, "Valor de IVA debe ser mayor a cero"
        
        if datos_iva["es_responsable_iva"] is False:
            return False, "Tercero no es responsable de IVA según RUT"
        
        if not datos_iva["concepto_aplica_iva"]:
            return False, "Concepto facturado no aplica IVA (exento/excluido)"
        
        # Estado válido para liquidación
        return True, "Estado válido para liquidación"
    
    def _calcular_reteiva_preciso(self, valor_iva: float, 
                                 es_fuente_nacional: bool) -> Dict[str, Any]:
        """
        Calcula ReteIVA con precisión usando Decimal para evitar errores de redondeo.
        
        Args:
            valor_iva: Valor del IVA identificado
            es_fuente_nacional: True si es fuente nacional, False si extranjera
            
        Returns:
            Dict con resultado del cálculo preciso
        """
        try:
            # Usar Decimal para cálculos precisos
            valor_iva_decimal = Decimal(str(valor_iva))
            
            # Obtener tarifa según fuente
            tarifa_reteiva = obtener_tarifa_reteiva(es_fuente_nacional)
            tarifa_decimal = Decimal(str(tarifa_reteiva))
            
            # Calcular ReteIVA
            valor_reteiva_decimal = valor_iva_decimal * tarifa_decimal
            
            # Redondear a 2 decimales
            valor_reteiva_redondeado = valor_reteiva_decimal.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            # Determinar método y porcentaje texto
            if es_fuente_nacional:
                metodo = "fuente_nacional"
                porcentaje_texto = "15%"
            else:
                metodo = "fuente_extranjera"
                porcentaje_texto = "100%"
            
            resultado = {
                "valor_reteiva": float(valor_reteiva_redondeado),
                "tarifa_reteiva": tarifa_reteiva,
                "porcentaje_reteiva_texto": porcentaje_texto,
                "metodo_calculo": metodo,
                "valor_iva_base": valor_iva,
                "calculo_formula": f"${valor_iva:,.2f} x {porcentaje_texto} = ${float(valor_reteiva_redondeado):,.2f}"
            }
            
            logger.info(f"🧮 Cálculo ReteIVA: {resultado['calculo_formula']}")
            return resultado
            
        except Exception as e:
            error_msg = f"Error en cálculo preciso de ReteIVA: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
    
    def _construir_resultado_exitoso(self, nit_administrativo: str,
                                   datos_iva: Dict[str, Any],
                                   resultado_calculo: Dict[str, Any]) -> ResultadoLiquidacionIVA:
        """
        Construye el resultado exitoso de la liquidación.
        
        Args:
            nit_administrativo: NIT administrativo
            datos_iva: Datos del análisis
            resultado_calculo: Resultado del cálculo
            
        Returns:
            ResultadoLiquidacionIVA: Resultado estructurado
        """
        from datetime import datetime
        
        return ResultadoLiquidacionIVA(
            # Datos de entrada
            nit_administrativo=nit_administrativo,
            
            # IVA
            valor_iva_identificado=datos_iva["valor_iva_total"],
            porcentaje_iva=datos_iva["porcentaje_iva"],
            aplica_iva=True,
            
            # ReteIVA
            valor_reteiva=resultado_calculo["valor_reteiva"],
            tarifa_reteiva=resultado_calculo["tarifa_reteiva"],
            porcentaje_reteiva_texto=resultado_calculo["porcentaje_reteiva_texto"],
            aplica_reteiva=True,
            
            # Fuente de ingreso
            es_fuente_nacional=datos_iva["es_fuente_nacional"],
            metodo_calculo=resultado_calculo["metodo_calculo"],
            
            # Estado y validaciones
            estado_liquidacion="Preliquidado",
            es_responsable_iva=datos_iva["es_responsable_iva"],
            observaciones=[
                f"IVA identificado: ${datos_iva['valor_iva_total']:,.2f}",
                f"Fuente: {'Nacional' if datos_iva['es_fuente_nacional'] else 'Extranjera'}",
                f"Cálculo: {resultado_calculo['calculo_formula']}"
            ],
            calculo_exitoso=True,
            
            # Metadatos
            timestamp=datetime.now().isoformat(),
            version_liquidador=self.VERSION
        )
    
    def _crear_resultado_no_aplica(self, nit_administrativo: str,
                                  razon: str, datos_iva: Dict[str, Any]) -> ResultadoLiquidacionIVA:
        """
        Crea resultado cuando no aplica IVA/ReteIVA.
        
        Args:
            nit_administrativo: NIT administrativo
            razon: Razón por la cual no aplica
            datos_iva: Datos del análisis
            
        Returns:
            ResultadoLiquidacionIVA: Resultado de no aplicación
        """
        from datetime import datetime
        
        return ResultadoLiquidacionIVA(
            # Datos de entrada
            nit_administrativo=nit_administrativo,
            
            # IVA
            valor_iva_identificado=datos_iva.get("valor_iva_total", 0.0),
            porcentaje_iva=datos_iva.get("porcentaje_iva", 0.0),
            aplica_iva=False,
            
            # ReteIVA
            valor_reteiva=0.0,
            tarifa_reteiva=0.0,
            porcentaje_reteiva_texto="0%",
            aplica_reteiva=False,
            
            # Fuente de ingreso
            es_fuente_nacional=datos_iva.get("es_fuente_nacional", True),
            metodo_calculo="no_aplica",
            
            # Estado y validaciones
            estado_liquidacion="No aplica",
            es_responsable_iva=datos_iva.get("es_responsable_iva"),
            observaciones=[
                f"Razón: {razon}",
                f"Estado original: {datos_iva.get('estado_liquidacion', 'No disponible')}"
            ] + datos_iva.get("observaciones", []),
            calculo_exitoso=True,  # Exitoso aunque no aplique
            
            # Metadatos
            timestamp=datetime.now().isoformat(),
            version_liquidador=self.VERSION
        )
    
    def _crear_resultado_error(self, nit_administrativo: str,
                              mensaje_error: str) -> ResultadoLiquidacionIVA:
        """
        Crea resultado de error.
        
        Args:
            nit_administrativo: NIT administrativo
            mensaje_error: Descripción del error
            
        Returns:
            ResultadoLiquidacionIVA: Resultado de error
        """
        from datetime import datetime
        
        return ResultadoLiquidacionIVA(
            # Datos de entrada
            nit_administrativo=nit_administrativo,
            
            # IVA
            valor_iva_identificado=0.0,
            porcentaje_iva=0.0,
            aplica_iva=False,
            
            # ReteIVA
            valor_reteiva=0.0,
            tarifa_reteiva=0.0,
            porcentaje_reteiva_texto="0%",
            aplica_reteiva=False,
            
            # Fuente de ingreso
            es_fuente_nacional=True,
            metodo_calculo="error",
            
            # Estado y validaciones
            estado_liquidacion="Error en liquidación",
            es_responsable_iva=None,
            observaciones=[mensaje_error],
            calculo_exitoso=False,
            
            # Metadatos
            timestamp=datetime.now().isoformat(),
            version_liquidador=self.VERSION
        )
    
    def validar_configuracion(self) -> Dict[str, Any]:
        """
        Valida la configuración actual del liquidador.
        
        Returns:
            Dict con estado de la configuración
        """
        try:
            config = self.config_iva
            
            validacion = {
                "configuracion_valida": True,
                "nits_configurados": len(config["nits_validos"]),
                "bienes_no_causan_iva": len(config["bienes_no_causan_iva"]),
                "bienes_exentos_iva": len(config["bienes_exentos_iva"]),
                "servicios_excluidos_iva": len(config["servicios_excluidos_iva"]),
                "tarifas_reteiva": config["config_reteiva"]
            }
            
            # Validar tarifas críticas
            tarifas = config["config_reteiva"]
            if tarifas["tarifa_fuente_nacional"] != 0.15:
                validacion["advertencias"] = ["Tarifa fuente nacional no es 15%"]
            
            if tarifas["tarifa_fuente_extranjera"] != 1.0:
                validacion.setdefault("advertencias", []).append("Tarifa fuente extranjera no es 100%")
            
            logger.info("✅ Configuración de liquidador IVA validada")
            return validacion
            
        except Exception as e:
            logger.error(f"❌ Error validando configuración: {str(e)}")
            return {
                "configuracion_valida": False,
                "error": str(e)
            }

# ===============================
# FUNCIONES DE UTILIDAD
# ===============================

def convertir_resultado_a_dict(resultado: ResultadoLiquidacionIVA) -> Dict[str, Any]:
    """
    Convierte el resultado a diccionario para integración con sistema paralelo.
    
    Args:
        resultado: Resultado de liquidación
        
    Returns:
        Dict serializable para JSON
    """
    return {
        "aplica": resultado.aplica_reteiva,
        "valor_iva_identificado": resultado.valor_iva_identificado,
        "valor_reteiva": resultado.valor_reteiva,
        "porcentaje_iva": resultado.porcentaje_iva,
        "tarifa_reteiva": resultado.tarifa_reteiva,
        "porcentaje_reteiva_texto": resultado.porcentaje_reteiva_texto,
        "es_fuente_nacional": resultado.es_fuente_nacional,
        "metodo_calculo": resultado.metodo_calculo,
        "estado_liquidacion": resultado.estado_liquidacion,
        "es_responsable_iva": resultado.es_responsable_iva,
        "observaciones": resultado.observaciones,
        "calculo_exitoso": resultado.calculo_exitoso
    }

def crear_resumen_iva_paralelo(resultado: ResultadoLiquidacionIVA) -> Dict[str, Any]:
    """
    Crea resumen para integración con procesamiento paralelo.
    
    Args:
        resultado: Resultado de liquidación
        
    Returns:
        Dict con resumen para sistema paralelo
    """
    return {
        "iva_reteiva": {
            "aplica": resultado.aplica_reteiva,
            "valor_iva": resultado.valor_iva_identificado,
            "valor_reteiva": resultado.valor_reteiva,
            "porcentaje_reteiva": resultado.porcentaje_reteiva_texto,
            "fuente_ingreso": "nacional" if resultado.es_fuente_nacional else "extranjera",
            "estado": resultado.estado_liquidacion
        }
    }

# ===============================
# EJEMPLO DE USO
# ===============================

if __name__ == "__main__":
    """
    Ejemplo de uso del LiquidadorIVA.
    """
    # Simular análisis de IVA de Gemini
    analisis_ejemplo = {
        "analisis_iva": {
            "iva_identificado": {
                "tiene_iva": True,
                "valor_iva_total": 1900000.0,
                "porcentaje_iva": 19.0,
                "detalle_conceptos_iva": [
                    {"concepto": "Servicios", "valor_iva": 1900000.0, "porcentaje": 19.0}
                ]
            },
            "responsabilidad_iva_rut": {
                "rut_disponible": True,
                "es_responsable_iva": True,
                "codigo_encontrado": "48"
            },
            "concepto_facturado": {
                "descripcion": "Servicios de consultoría",
                "aplica_iva": True,
                "categoria": "gravado"
            }
        },
        "analisis_fuente_ingreso": {
            "es_fuente_nacional": True,
            "validaciones_fuente": {
                "uso_beneficio_colombia": True,
                "ejecutado_en_colombia": True,
                "asistencia_tecnica_colombia": False,
                "bien_ubicado_colombia": True
            }
        },
        "calculo_reteiva": {
            "aplica_reteiva": True,
            "porcentaje_reteiva": "15%",
            "metodo_calculo": "fuente_nacional"
        },
        "estado_liquidacion": {
            "estado": "Preliquidado",
            "observaciones": ["IVA identificado correctamente"]
        }
    }
    
    # Crear liquidador
    liquidador = LiquidadorIVA()
    
    # Realizar liquidación
    resultado = liquidador.liquidar_iva_completo(
        analisis_iva=analisis_ejemplo,
        nit_administrativo="800.178.148-8"
    )
    
    # Mostrar resultado
    print(f"✅ Liquidación completada:")
    print(f"   - Estado: {resultado.estado_liquidacion}")
    print(f"   - IVA identificado: ${resultado.valor_iva_identificado:,.2f}")
    print(f"   - ReteIVA ({resultado.porcentaje_reteiva_texto}): ${resultado.valor_reteiva:,.2f}")
    print(f"   - Fuente: {'Nacional' if resultado.es_fuente_nacional else 'Extranjera'}")
