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
    aplica_retencion: bool  #  CAMPO SINCRONIZADO AGREGADO
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
        
        # VALIDACIÓN 1: Facturación exterior - Usar función especializada
        if analisis.es_facturacion_exterior:
            logger.info("Facturación exterior detectada - Redirigiendo a función especializada")
            return self.liquidar_factura_extranjera(analisis)
        
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
        
        #  VALIDACIÓN SEPARADA: ARTÍCULO 383 PARA PERSONAS NATURALES
        # Verificar si se analizó Art 383 y si aplica
        if analisis.articulo_383 and analisis.articulo_383.aplica:
            logger.info(" Aplicando Artículo 383 - Tarifas progresivas para persona natural")
            
            # Usar función separada para Art 383
            resultado_art383 = self._calcular_retencion_articulo_383_separado(analisis)
            
            if resultado_art383["puede_liquidar"]:
                logger.info(f" Artículo 383 liquidado exitosamente: ${resultado_art383['resultado'].valor_retencion:,.2f}")
                return resultado_art383["resultado"]
            else:
                # Si falla el cálculo del Art. 383, continuar con cálculo tradicional
                mensajes_error.extend(resultado_art383["mensajes_error"])
                mensajes_error.append("Aplicando tarifa convencional por fallos en Art. 383")
                logger.warning(" Fallback a tarifa convencional por errores en Art. 383")
        
        elif analisis.articulo_383 and not analisis.articulo_383.aplica:
            # Explicar por qué no aplica Art. 383
            self._agregar_observaciones_art383_no_aplica(analisis.articulo_383, mensajes_error)
        
        # CÁLCULO DE RETENCIÓN CONVENCIONAL
        logger.info(f"💰 Calculando retención para {len(conceptos_identificados)} concepto(s) con bases individuales")
        
        # Obtener conceptos de retefuente
        conceptos_retefuente = self._obtener_conceptos_retefuente()
        
        valor_base_total = analisis.valor_total or 0
        valor_retencion_total = 0
        conceptos_aplicados = []
        tarifas_aplicadas = []
        detalles_calculo = []
        
        # 🔧 CORRECCIÓN CRÍTICA: Calcular bases individuales por concepto
        conceptos_con_bases = self._calcular_bases_individuales_conceptos(conceptos_identificados, valor_base_total)
        
        for concepto_item in conceptos_con_bases:
            logger.info(f"📊 Procesando concepto: {concepto_item.concepto} - Base: ${concepto_item.base_gravable:,.2f}")
            resultado_concepto = self._calcular_retencion_concepto(
                concepto_item, conceptos_retefuente
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
    
    def _calcular_bases_individuales_conceptos(self, conceptos_identificados: List[ConceptoIdentificado], 
                                             valor_base_total: float) -> List[ConceptoIdentificado]:
        """
        🆕 NUEVA FUNCIÓN: Calcula bases gravables individuales para cada concepto.
        
        Si un concepto no tiene base específica, calcula proporción del valor total.
        
        Args:
            conceptos_identificados: Lista de conceptos identificados por Gemini
            valor_base_total: Valor total de la factura para calcular proporciones
            
        Returns:
            List[ConceptoIdentificado]: Conceptos con bases gravables calculadas
        """
        conceptos_con_bases = []
        conceptos_sin_base = []
        suma_bases_especificas = 0
        
        # PASO 1: Separar conceptos con y sin base específica
        for concepto in conceptos_identificados:
            if concepto.base_gravable and concepto.base_gravable > 0:
                conceptos_con_bases.append(concepto)
                suma_bases_especificas += concepto.base_gravable
                logger.info(f"💰 Concepto con base específica: {concepto.concepto} = ${concepto.base_gravable:,.2f}")
            else:
                conceptos_sin_base.append(concepto)
                logger.warning(f"⚠️ Concepto sin base específica: {concepto.concepto}")
        
        # PASO 2: Calcular valor disponible para conceptos sin base
        valor_disponible = max(0, valor_base_total - suma_bases_especificas)
        
        # PASO 3: Asignar proporciones a conceptos sin base específica
        if conceptos_sin_base and valor_disponible > 0:
            proporcion_por_concepto = valor_disponible / len(conceptos_sin_base)
            logger.info(f"📈 Asignando proporción: ${proporcion_por_concepto:,.2f} por concepto ({len(conceptos_sin_base)} conceptos)")
            
            for concepto in conceptos_sin_base:
                # Crear nueva instancia con base calculada
                concepto_con_base = ConceptoIdentificado(
                    concepto=concepto.concepto,
                    tarifa_retencion=concepto.tarifa_retencion,
                    base_gravable=proporcion_por_concepto
                )
                conceptos_con_bases.append(concepto_con_base)
                logger.info(f"📊 Base asignada por proporción: {concepto.concepto} = ${proporcion_por_concepto:,.2f}")
        
        elif conceptos_sin_base and valor_disponible <= 0:
            # 🔧 CORRECCIÓN CRÍTICA: No hay valor disponible - usar base cero
            logger.warning(f"⚠️ No hay valor disponible. Suma bases específicas: ${suma_bases_especificas:,.2f} >= Total: ${valor_base_total:,.2f}")
            for concepto in conceptos_sin_base:
                # 🔧 CORREGIDO: Usar $0.00 en lugar de $1.00 para evitar retenciones erróneas
                concepto_con_base = ConceptoIdentificado(
                    concepto=concepto.concepto,
                    tarifa_retencion=concepto.tarifa_retencion,
                    base_gravable=0.0  # 🔧 CORREGIDO: Cero real, no simbólico
                )
                conceptos_con_bases.append(concepto_con_base)
                logger.warning(f"📊 Base cero asignada: {concepto.concepto} = $0.00 (sin valor disponible)")
        
        # PASO 4: Validar total
        total_bases_calculadas = sum(c.base_gravable for c in conceptos_con_bases)
        logger.info(f"📊 RESUMEN: {len(conceptos_con_bases)} conceptos - Total bases: ${total_bases_calculadas:,.2f} / Factura: ${valor_base_total:,.2f}")
        
        return conceptos_con_bases
    
    def _calcular_retencion_concepto(self, concepto_item: ConceptoIdentificado, 
                                   conceptos_retefuente: Dict) -> Dict[str, Any]:
        """
        🔧 CORREGIDO: Calcula retención para un concepto específico usando SOLO su base gravable.
        
        Args:
            concepto_item: Concepto identificado por Gemini con base_gravable específica
            conceptos_retefuente: Diccionario de conceptos con tarifas y bases
            
        Returns:
            Dict con resultado del cálculo para este concepto
        """
        concepto_aplicado = concepto_item.concepto
        base_concepto = concepto_item.base_gravable  # 🔧 CORRECCIÓN: Solo base específica
        
        # 🆕 VALIDACIÓN ESPECIAL: Base cero por falta de valor disponible
        if base_concepto <= 0:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"{concepto_aplicado}: Sin base gravable disponible (${base_concepto:,.2f})",
                "concepto": concepto_aplicado
            }
        
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
                resultado["puede_continuar"] = False
                resultado["mensajes"].append(f"Datos faltantes de la naturaleza del tercero - NO se puede practicar retención : {datos_faltantes}")
                logger.warning(f"Datos faltantes de la naturaleza del tercero: {datos_faltantes}")
                return resultado
                
            
        except AttributeError as e:
            logger.error(f"Error accediendo a atributos de naturaleza_tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero. Verifique que el RUT esté adjunto.")
        except Exception as e:
            logger.error(f"Error inesperado validando naturaleza del tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero.")
        
        return resultado
    
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
    
    def liquidar_factura_extranjera(self, analisis_factura: AnalisisFactura, nit_administrativo: str = "") -> ResultadoLiquidacion:
        """
        Función especializada para liquidar facturas extranjeras.
        
        Args:
            analisis_factura: Análisis de la factura extranjera de Gemini
            nit_administrativo: NIT de la entidad administrativa (opcional)
            
        Returns:
            ResultadoLiquidacion: Resultado del cálculo de retención extranjera
        """
        nit_log = nit_administrativo if nit_administrativo else "[No especificado]"
        logger.info(f"Liquidando factura extranjera para NIT: {nit_log}")
        
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

        # 🔧 CORRECCIÓN CRÍTICA: Usar base específica del concepto
        # Verificar si el concepto tiene tarifa aplicada (viene del prompt extranjero)
        if hasattr(concepto_principal, 'tarifa_aplicada') and concepto_principal.tarifa_aplicada > 0:
            # 🔧 CORREGIDO: Usar SOLO base_gravable del concepto
            if not concepto_principal.base_gravable or concepto_principal.base_gravable <= 0:
                # Si no tiene base específica, usar valor total como fallback
                valor_base = analisis_factura.valor_total or 0
                logger.warning(f"⚠️ Factura extranjera: Concepto sin base específica, usando valor total: ${valor_base:,.2f}")
            else:
                valor_base = concepto_principal.base_gravable
                logger.info(f"💰 Factura extranjera: Usando base específica del concepto: ${valor_base:,.2f}")
            
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
        
        # 🔧 CORRECCIÓN CRÍTICA: Si no tiene tarifa aplicada, usar tarifa estándar del concepto
        if not concepto_principal.base_gravable or concepto_principal.base_gravable <= 0:
            # Si no tiene base específica, usar valor total como fallback
            valor_base = analisis_factura.valor_total or 0
            logger.warning(f"⚠️ Factura extranjera: Concepto sin base específica (tarifa estándar), usando valor total: ${valor_base:,.2f}")
        else:
            valor_base = concepto_principal.base_gravable
            logger.info(f"💰 Factura extranjera: Usando base específica del concepto (tarifa estándar): ${valor_base:,.2f}")
        
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
