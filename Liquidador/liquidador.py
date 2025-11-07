"""
LIQUIDADOR DE RETENCIÓN EN LA FUENTE
===================================

Módulo para calcular retenciones en la fuente según normativa colombiana.
Aplica tarifas exactas y valida bases mínimas según CONCEPTOS_RETEFUENTE.

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Configuración de logging
logger = logging.getLogger(__name__)

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

class ResultadoLiquidacion(BaseModel):
    valor_base_retencion: float
    valor_retencion: float
    tarifa_aplicada: float
    concepto_aplicado: str
    fecha_calculo: str
    puede_liquidar: bool
    mensajes_error: List[str]

# ===============================
# LIQUIDADOR DE RETENCIÓN
# ===============================

class LiquidadorRetencion:
    """
    Calcula retenciones en la fuente según normativa colombiana.
    
    Aplica tarifas exactas basadas en el diccionario CONCEPTOS_RETEFUENTE
    y valida todas las condiciones previas para determinar si aplica retención.
    """
    
    def __init__(self):
        """Inicializa el liquidador"""
        logger.info("LiquidadorRetencion inicializado")
    
    def calcular_retencion(self, analisis: AnalisisFactura) -> ResultadoLiquidacion:
        """
        Calcula la retención en la fuente basada en el análisis de Gemini.
        
        Args:
            analisis: Resultado del análisis de factura de Gemini
            
        Returns:
            ResultadoLiquidacion: Resultado completo del cálculo de retención
        """
        logger.info("Iniciando cálculo de retención en la fuente")
        
        mensajes_error = []
        puede_liquidar = True
        
        # VALIDACIÓN 1: Facturación exterior
        if analisis.es_facturacion_exterior:
            logger.info("Facturación exterior detectada - NO aplica retención")
            return self._crear_resultado_no_liquidable(
                ["Esta facturación es fuera de Colombia - NO aplica retención en la fuente"]
            )
        
        # VALIDACIÓN 2: Naturaleza del tercero
        resultado_validacion = self._validar_naturaleza_tercero(analisis.naturaleza_tercero)
        if not resultado_validacion["puede_continuar"]:
            return self._crear_resultado_no_liquidable(resultado_validacion["mensajes"])
        
        # Agregar advertencias de naturaleza del tercero (si las hay)
        mensajes_error.extend(resultado_validacion["advertencias"])
        
        # VALIDACIÓN 3: Conceptos identificados
        conceptos_identificados = [
            c for c in analisis.conceptos_identificados 
            if c.concepto != "CONCEPTO_NO_IDENTIFICADO"
        ]
        
        conceptos_no_identificados = [
            c for c in analisis.conceptos_identificados 
            if c.concepto == "CONCEPTO_NO_IDENTIFICADO"
        ]
        
        # Agregar advertencias por conceptos no identificados
        if conceptos_no_identificados:
            mensajes_error.append(f"Se encontraron {len(conceptos_no_identificados)} concepto(s) no identificado(s) que no serán liquidados")
            mensajes_error.append("Revise la factura manualmente para los conceptos no identificados")
            logger.warning(f"Conceptos no identificados: {len(conceptos_no_identificados)}")
        
        # Verificar si hay al menos un concepto identificado
        if not conceptos_identificados:
            mensajes_error.append("No se identificaron conceptos válidos para calcular retención")
            puede_liquidar = False
            logger.error("No hay conceptos identificados válidos")
        
        if not puede_liquidar:
            return self._crear_resultado_no_liquidable(mensajes_error)
        
        # VALIDACIÓN ESPECIAL: ARTÍCULO 383 PARA PERSONAS NATURALES
        # Si aplica Art. 383, usar tarifas progresivas en lugar de tarifas convencionales
        if (analisis.articulo_383 and 
            analisis.articulo_383.aplica and 
            analisis.articulo_383.condiciones_cumplidas.es_persona_natural and
            analisis.articulo_383.condiciones_cumplidas.concepto_aplicable and
            analisis.articulo_383.condiciones_cumplidas.planilla_seguridad_social and
            analisis.articulo_383.condiciones_cumplidas.cuenta_cobro):
            
            logger.info("Aplicando Artículo 383 - Tarifas progresivas para persona natural")
            resultado_art383 = self._calcular_retencion_articulo_383(analisis)
            
            if resultado_art383["puede_liquidar"]:
                return resultado_art383["resultado"]
            else:
                # Si falla el cálculo del Art. 383, continuar con cálculo tradicional
                mensajes_error.extend(resultado_art383["mensajes_error"])
                mensajes_error.append("Aplicando tarifa convencional por fallos en Art. 383")
                logger.warning("Fallback a tarifa convencional por errores en Art. 383")
        
        elif analisis.articulo_383 and not analisis.articulo_383.aplica:
            # Explicar por qué no aplica Art. 383
            condiciones = analisis.articulo_383.condiciones_cumplidas
            razones_no_aplica = []
            
            if not condiciones.es_persona_natural:
                razones_no_aplica.append("no es persona natural")
            if not condiciones.concepto_aplicable:
                razones_no_aplica.append("concepto no aplica para Art. 383")
            if not condiciones.planilla_seguridad_social:
                razones_no_aplica.append("falta planilla de seguridad social")
            if not condiciones.cuenta_cobro:
                razones_no_aplica.append("falta cuenta de cobro")
            
            if razones_no_aplica:
                mensajes_error.append(f"Art. 383 no aplica: {', '.join(razones_no_aplica)}")
                mensajes_error.append("Aplicando tarifas convencionales")
                logger.info(f"Art. 383 no aplica: {', '.join(razones_no_aplica)}")
        
        # CÁLCULO DE RETENCIÓN CONVENCIONAL
        logger.info(f"Calculando retención para {len(conceptos_identificados)} concepto(s)")
        
        # Obtener conceptos de retefuente
        conceptos_retefuente = self._obtener_conceptos_retefuente()
        
        valor_base_total = analisis.valor_total or 0
        valor_retencion_total = 0
        conceptos_aplicados = []
        tarifas_aplicadas = []
        detalles_calculo = []
        
        for concepto_item in conceptos_identificados:
            resultado_concepto = self._calcular_retencion_concepto(
                concepto_item, valor_base_total, conceptos_retefuente
            )
            
            if resultado_concepto["aplica_retencion"]:
                valor_retencion_total += resultado_concepto["valor_retencion"]
                conceptos_aplicados.append(resultado_concepto["concepto"])
                tarifas_aplicadas.append(resultado_concepto["tarifa"])
                detalles_calculo.append(resultado_concepto["detalle"])
                logger.info(f"Retención aplicada: {resultado_concepto['concepto']} - ${resultado_concepto['valor_retencion']:,.0f}")
            else:
                mensajes_error.append(resultado_concepto["mensaje_error"])
                logger.warning(f"No aplica retención: {resultado_concepto['mensaje_error']}")
        
        # Verificar si se pudo calcular alguna retención
        if valor_retencion_total == 0 and not detalles_calculo:
            puede_liquidar = False
            if not mensajes_error:
                mensajes_error.append("No se pudo calcular retención para ningún concepto")
            logger.error("No se calculó retención para ningún concepto")
        
        # Si no se puede liquidar, devolver resultado vacío
        if not puede_liquidar:
            return self._crear_resultado_no_liquidable(mensajes_error)
        
        # PREPARAR RESULTADO FINAL
        concepto_aplicado = ", ".join(conceptos_aplicados) if conceptos_aplicados else "N/A"
        tarifa_promedio = sum(tarifas_aplicadas) / len(tarifas_aplicadas) if tarifas_aplicadas else 0
        
        # Agregar detalles del cálculo a los mensajes
        if detalles_calculo:
            mensajes_error.append("Detalle del cálculo:")
            for detalle in detalles_calculo:
                mensajes_error.append(
                    f"  • {detalle['concepto']}: ${detalle['base_gravable']:,.0f} x {detalle['tarifa']:.1f}% = ${detalle['valor_retencion']:,.0f}"
                )
        
        resultado = ResultadoLiquidacion(
            valor_base_retencion=valor_base_total,
            valor_retencion=valor_retencion_total,
            tarifa_aplicada=tarifa_promedio,
            concepto_aplicado=concepto_aplicado,
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=True,
            mensajes_error=mensajes_error
        )
        
        logger.info(f"Retención calculada exitosamente: ${valor_retencion_total:,.0f}")
        return resultado
    
    def _calcular_retencion_articulo_383(self, analisis: AnalisisFactura) -> Dict[str, Any]:
        """
        Calcula retención bajo el Artículo 383 con tarifas progresivas para personas naturales.
        
        Args:
            analisis: Análisis de factura con información del Art. 383
            
        Returns:
            Dict con resultado del cálculo del Art. 383
        """
        logger.info("Iniciando cálculo bajo Artículo 383 del Estatuto Tributario")
        
        # Importar constantes del Artículo 383
        from config import (
            UVT_2025, SMMLV_2025, obtener_tarifa_articulo_383, 
            calcular_limite_deduccion, LIMITES_DEDUCCIONES_ART383
        )
        
        art383 = analisis.articulo_383
        calculo = art383.calculo
        deducciones = art383.deducciones_identificadas
        
        try:
            # PASO 1: Verificar que tengamos la información necesaria
            if calculo.ingreso_bruto <= 0:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["No se pudo determinar el ingreso bruto para Art. 383"]
                }
            
            ingreso_bruto = calculo.ingreso_bruto
            logger.info(f"Ingreso bruto: ${ingreso_bruto:,.0f}")
            
            # PASO 2: Calcular aportes a seguridad social (40% del ingreso)
            aportes_seguridad_social = ingreso_bruto * LIMITES_DEDUCCIONES_ART383["seguridad_social_porcentaje"]
            logger.info(f"Aportes seguridad social (40%): ${aportes_seguridad_social:,.0f}")
            
            # PASO 3: Validar y calcular deducciones con límites
            deducciones_aplicables = {
                "intereses_vivienda": 0,
                "dependientes_economicos": 0,
                "medicina_prepagada": 0,
                "rentas_exentas": 0
            }
            
            # Intereses por vivienda
            if deducciones.intereses_vivienda.tiene_soporte and deducciones.intereses_vivienda.valor > 0:
                deducciones_aplicables["intereses_vivienda"] = calcular_limite_deduccion(
                    "intereses_vivienda", ingreso_bruto, deducciones.intereses_vivienda.valor
                )
            
            # Dependientes económicos
            if deducciones.dependientes_economicos.tiene_soporte and deducciones.dependientes_economicos.valor > 0:
                deducciones_aplicables["dependientes_economicos"] = calcular_limite_deduccion(
                    "dependientes_economicos", ingreso_bruto, deducciones.dependientes_economicos.valor
                )
            
            # Medicina prepagada
            if deducciones.medicina_prepagada.tiene_soporte and deducciones.medicina_prepagada.valor > 0:
                deducciones_aplicables["medicina_prepagada"] = calcular_limite_deduccion(
                    "medicina_prepagada", ingreso_bruto, deducciones.medicina_prepagada.valor
                )
            
            # Rentas exentas (solo si supera SMMLV)
            if deducciones.rentas_exentas.tiene_soporte and deducciones.rentas_exentas.valor > 0:
                deducciones_aplicables["rentas_exentas"] = calcular_limite_deduccion(
                    "rentas_exentas", ingreso_bruto, deducciones.rentas_exentas.valor
                )
            
            total_deducciones = sum(deducciones_aplicables.values())
            logger.info(f"Total deducciones aplicables: ${total_deducciones:,.0f}")
            
            # PASO 4: Aplicar límite máximo del 40% del ingreso bruto
            limite_maximo_deducciones = ingreso_bruto * LIMITES_DEDUCCIONES_ART383["deducciones_maximas_porcentaje"]
            deducciones_limitadas = min(total_deducciones, limite_maximo_deducciones)
            
            if total_deducciones > limite_maximo_deducciones:
                logger.warning(f"Deducciones limitadas al 40%: ${deducciones_limitadas:,.0f} (original: ${total_deducciones:,.0f})")
            
            # PASO 5: Calcular base gravable final
            base_gravable_final = ingreso_bruto - aportes_seguridad_social - deducciones_limitadas
            
            # Verificar que la base gravable no sea negativa
            if base_gravable_final < 0:
                logger.warning("Base gravable negativa, estableciendo en 0")
                base_gravable_final = 0
            
            logger.info(f"Base gravable final: ${base_gravable_final:,.0f}")
            
            # PASO 6: Convertir base gravable a UVT
            base_gravable_uvt = base_gravable_final / UVT_2025
            logger.info(f"Base gravable en UVT: {base_gravable_uvt:.2f} UVT")
            
            # PASO 7: Aplicar tarifa progresiva del Artículo 383
            tarifa_art383 = obtener_tarifa_articulo_383(base_gravable_final)
            valor_retencion_art383 = base_gravable_final * tarifa_art383
            
            logger.info(f"Tarifa Art. 383: {tarifa_art383*100:.0f}%")
            logger.info(f"Retención Art. 383: ${valor_retencion_art383:,.0f}")
            
            # PASO 8: Preparar mensajes explicativos
            mensajes_detalle = [
                f"Cálculo bajo Artículo 383 del Estatuto Tributario:",
                f"  • Ingreso bruto: ${ingreso_bruto:,.0f}",
                f"  • Aportes seguridad social (40%): ${aportes_seguridad_social:,.0f}",
                f"  • Deducciones aplicables: ${deducciones_limitadas:,.0f}"
            ]
            
            # Detallar deducciones aplicadas
            for tipo, valor in deducciones_aplicables.items():
                if valor > 0:
                    nombre_deduccion = tipo.replace("_", " ").title()
                    mensajes_detalle.append(f"    - {nombre_deduccion}: ${valor:,.0f}")
            
            mensajes_detalle.extend([
                f"  • Base gravable final: ${base_gravable_final:,.0f}",
                f"  • Base gravable en UVT: {base_gravable_uvt:.2f} UVT",
                f"  • Tarifa aplicada: {tarifa_art383*100:.0f}%",
                f"  • Retención calculada: ${valor_retencion_art383:,.0f}"
            ])
            
            # PASO 9: Crear resultado
            resultado = ResultadoLiquidacion(
                valor_base_retencion=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                tarifa_aplicada=tarifa_art383 * 100,  # Convertir a porcentaje
                concepto_aplicado=f"Artículo 383 - {analisis.conceptos_identificados[0].concepto if analisis.conceptos_identificados else 'Honorarios y servicios'}",
                fecha_calculo=datetime.now().isoformat(),
                puede_liquidar=True,
                mensajes_error=mensajes_detalle
            )
            
            return {
                "puede_liquidar": True,
                "resultado": resultado,
                "mensajes_error": []
            }
            
        except Exception as e:
            logger.error(f"Error calculando Artículo 383: {e}")
            return {
                "puede_liquidar": False,
                "mensajes_error": [f"Error en cálculo Art. 383: {str(e)}"]
            }
    
    def _validar_naturaleza_tercero(self, naturaleza: Optional[NaturalezaTercero]) -> Dict[str, Any]:
        """
        Valida la naturaleza del tercero y determina si puede continuar el cálculo.
        
        Args:
            naturaleza: Información del tercero
            
        Returns:
            Dict con puede_continuar, mensajes y advertencias
        """
        resultado = {
            "puede_continuar": True,
            "mensajes": [],
            "advertencias": []
        }
        
        # 🔧 VALIDACIÓN MEJORADA: Manejar None correctamente
        if not naturaleza or naturaleza is None:
            resultado["advertencias"].append("No se pudo identificar la naturaleza del tercero. Por favor adjunte el RUT.")
            logger.warning("Naturaleza del tercero no identificada o es None")
            return resultado
        
        # 🔧 VALIDACIÓN SEGURA: Verificar que el objeto tiene atributos antes de acceder
        try:
            # Validar autorretenedor
            if hasattr(naturaleza, 'es_autorretenedor') and naturaleza.es_autorretenedor is True:
                resultado["puede_continuar"] = False
                resultado["mensajes"].append("El tercero es autorretenedor - NO se debe practicar retención")
                logger.info("Tercero es autorretenedor - no aplica retención")
                return resultado
            
            # VALIDACIÓN CRÍTICA: Responsable de IVA
            if hasattr(naturaleza, 'es_responsable_iva') and naturaleza.es_responsable_iva is False:
                resultado["puede_continuar"] = False
                resultado["mensajes"].append("El tercero NO es responsable de IVA - NO se le aplica retención en la fuente")
                logger.info("Tercero NO es responsable de IVA - no aplica retención")
                return resultado
            
            # Validar régimen simple
            if hasattr(naturaleza, 'regimen_tributario') and naturaleza.regimen_tributario == "SIMPLE":
                resultado["puede_continuar"] = False
                resultado["mensajes"].append("Régimen Simple de Tributación - NO aplica retención en la fuente")
                logger.info("Régimen Simple detectado - no aplica retención")
                return resultado
            
            # Validar datos faltantes de forma segura
            datos_faltantes = []
            if not hasattr(naturaleza, 'es_declarante') or naturaleza.es_declarante is None:
                datos_faltantes.append("condición de declarante")
            if not hasattr(naturaleza, 'regimen_tributario') or naturaleza.regimen_tributario is None:
                datos_faltantes.append("régimen tributario")
            if not hasattr(naturaleza, 'es_autorretenedor') or naturaleza.es_autorretenedor is None:
                datos_faltantes.append("condición de autorretenedor")
            if not hasattr(naturaleza, 'es_responsable_iva') or naturaleza.es_responsable_iva is None:
                datos_faltantes.append("condición de responsable de IVA")
            
            if datos_faltantes:
                resultado["advertencias"].append(
                    f"Faltan datos: {', '.join(datos_faltantes)}. "
                    "Por favor adjunte el RUT para completar la información."
                )
                logger.warning(f"Datos faltantes del tercero: {datos_faltantes}")
            
        except AttributeError as e:
            logger.error(f"Error accediendo a atributos de naturaleza_tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero. Verifique que el RUT esté adjunto.")
        except Exception as e:
            logger.error(f"Error inesperado validando naturaleza del tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero.")
        
        return resultado
    
    def _calcular_retencion_concepto(self, concepto_item: ConceptoIdentificado, 
                                   valor_base_total: float, conceptos_retefuente: Dict) -> Dict[str, Any]:
        """
        Calcula retención para un concepto específico.
        
        Args:
            concepto_item: Concepto identificado por Gemini
            valor_base_total: Valor total de la factura
            conceptos_retefuente: Diccionario de conceptos con tarifas y bases
            
        Returns:
            Dict con resultado del cálculo para este concepto
        """
        concepto_aplicado = concepto_item.concepto
        base_concepto = concepto_item.base_gravable or valor_base_total
        
        # Buscar concepto exacto en el diccionario
        if concepto_aplicado not in conceptos_retefuente:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"Concepto '{concepto_aplicado}' no encontrado en la tabla de retefuente",
                "concepto": concepto_aplicado
            }
        
        datos_concepto = conceptos_retefuente[concepto_aplicado]
        tarifa = datos_concepto["tarifa_retencion"] * 100  # Convertir a porcentaje
        base_minima = datos_concepto["base_pesos"]
        
        # Verificar base mínima
        if base_concepto < base_minima:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"{concepto_aplicado}: Base ${base_concepto:,.0f} no supera mínimo de ${base_minima:,.0f}",
                "concepto": concepto_aplicado
            }
        
        # Calcular retención
        valor_retencion_concepto = (base_concepto * tarifa) / 100
        
        return {
            "aplica_retencion": True,
            "valor_retencion": valor_retencion_concepto,
            "concepto": concepto_aplicado,
            "tarifa": tarifa,
            "detalle": {
                "concepto": concepto_aplicado,
                "base_gravable": base_concepto,
                "tarifa": tarifa,
                "valor_retencion": valor_retencion_concepto,
                "base_minima": base_minima
            }
        }
    
    def _obtener_conceptos_retefuente(self) -> Dict:
        """
        Obtiene el diccionario de conceptos de retefuente desde config global.
        
        Returns:
            Dict: CONCEPTOS_RETEFUENTE con tarifas y bases mínimas
        """
        try:
            # Intentar importar desde main o config
            import sys
            import os
            
            # Agregar directorio padre al path
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, parent_dir)
            
            # Importar conceptos desde main
            from main import CONCEPTOS_RETEFUENTE
            logger.info(f"Conceptos cargados desde main: {len(CONCEPTOS_RETEFUENTE)}")
            return CONCEPTOS_RETEFUENTE
            
        except ImportError as e:
            logger.error(f"No se pudo importar CONCEPTOS_RETEFUENTE desde main: {e}")
            # Usar conceptos hardcodeados como fallback
            return self._conceptos_fallback()
        except Exception as e:
            logger.error(f"Error obteniendo conceptos: {e}")
            return self._conceptos_fallback()
    
    def _conceptos_fallback(self) -> Dict:
        """
        Conceptos de emergencia si no se puede acceder al diccionario global.
        
        Returns:
            Dict: Conceptos básicos hardcodeados
        """
        logger.warning("Usando conceptos de fallback - limitados")
        
        return {
            "Servicios generales (declarantes)": {
                "base_pesos": 100000,
                "tarifa_retencion": 0.04
            },
            "Servicios generales (no declarantes)": {
                "base_pesos": 100000,
                "tarifa_retencion": 0.06
            },
            "Honorarios y comisiones por servicios (declarantes)": {
                "base_pesos": 0,
                "tarifa_retencion": 0.11
            },
            "Honorarios y comisiones por servicios (no declarantes)": {
                "base_pesos": 0,
                "tarifa_retencion": 0.10
            },
            "Arrendamiento de bienes inmuebles": {
                "base_pesos": 498000,
                "tarifa_retencion": 0.035
            }
        }
    
    def _crear_resultado_no_liquidable(self, mensajes_error: List[str]) -> ResultadoLiquidacion:
        """
        Crea un resultado cuando no se puede liquidar retención.
        
        Args:
            mensajes_error: Lista de mensajes explicando por qué no se puede liquidar
            
        Returns:
            ResultadoLiquidacion: Resultado con valores en cero y explicación
        """
        return ResultadoLiquidacion(
            valor_base_retencion=0,
            valor_retencion=0,
            tarifa_aplicada=0,
            concepto_aplicado="N/A",
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=False,
            mensajes_error=mensajes_error
        )
    
    # ===============================
    # FUNCIONES PÚBLICAS PARA MAIN.PY
    # ===============================
    
    def liquidar_factura(self, analisis_factura: AnalisisFactura, nit_administrativo: str) -> ResultadoLiquidacion:
        """
        Función pública para liquidar facturas nacionales.
        
        Args:
            analisis_factura: Análisis de la factura de Gemini
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            ResultadoLiquidacion: Resultado del cálculo de retención
        """
        logger.info(f"Liquidando factura nacional para NIT: {nit_administrativo}")
        return self.calcular_retencion(analisis_factura)
    
    def liquidar_factura_extranjera(self, analisis_factura: AnalisisFactura, nit_administrativo: str) -> ResultadoLiquidacion:
        """
        Función especializada para liquidar facturas extranjeras.
        
        Args:
            analisis_factura: Análisis de la factura extranjera de Gemini
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            ResultadoLiquidacion: Resultado del cálculo de retención extranjera
        """
        logger.info(f"Liquidando factura extranjera para NIT: {nit_administrativo}")
        
        # Para facturas extranjeras, el análisis de Gemini ya determinó si aplica retención
        # y calculó el valor basado en las tarifas de pagos al exterior
        
        # Verificar si es facturación exterior
        if not analisis_factura.es_facturacion_exterior:
            logger.warning("Factura marcada como extranjera pero el análisis dice que no es exterior")
            # Procesar como factura nacional
            return self.calcular_retencion(analisis_factura)
        
        # Para facturas extranjeras, extraer el resultado del análisis de Gemini
        if not analisis_factura.conceptos_identificados:
            return self._crear_resultado_no_liquidable([
                "No se identificaron conceptos para facturación extranjera"
            ])
        
        # Tomar el primer concepto identificado (para extranjeras normalmente es uno)
        concepto_principal = analisis_factura.conceptos_identificados[0]
        
        # Verificar si el concepto tiene tarifa aplicada (viene del prompt extranjero)
        if hasattr(concepto_principal, 'tarifa_aplicada') and concepto_principal.tarifa_aplicada > 0:
            valor_base = concepto_principal.base_gravable or analisis_factura.valor_total or 0
            valor_retencion = valor_base * concepto_principal.tarifa_aplicada
            
            resultado = ResultadoLiquidacion(
                valor_base_retencion=valor_base,
                valor_retencion=valor_retencion,
                tarifa_aplicada=concepto_principal.tarifa_aplicada * 100,  # Convertir a porcentaje
                concepto_aplicado=concepto_principal.concepto,
                fecha_calculo=datetime.now().isoformat(),
                puede_liquidar=True,
                mensajes_error=[]
            )
            
            logger.info(f"Retención extranjera calculada: ${valor_retencion:,.0f} ({concepto_principal.tarifa_aplicada*100:.1f}%)")
            return resultado
        
        # Si no tiene tarifa aplicada, usar tarifa estándar del concepto
        valor_base = concepto_principal.base_gravable or analisis_factura.valor_total or 0
        tarifa_concepto = concepto_principal.tarifa_retencion  # Ya viene en decimal del prompt
        valor_retencion = valor_base * tarifa_concepto
        
        resultado = ResultadoLiquidacion(
            valor_base_retencion=valor_base,
            valor_retencion=valor_retencion,
            tarifa_aplicada=tarifa_concepto * 100,  # Convertir a porcentaje para respuesta
            concepto_aplicado=concepto_principal.concepto,
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=True,
            mensajes_error=analisis_factura.observaciones
        )
        
        logger.info(f"Retención extranjera calculada: ${valor_retencion:,.0f} ({tarifa_concepto*100:.1f}%)")
        return resultado
