"""
LIQUIDADOR DE RETENCIÓN EN LA FUENTE
===================================

Módulo para calcular retenciones en la fuente según normativa colombiana.
Aplica tarifas exactas y valida bases mínimas según CONCEPTOS_RETEFUENTE.

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel

# Configuración de logging
logger = logging.getLogger(__name__)

# ===============================
# MODELOS DE DATOS LOCALES
# ===============================

class ConceptoIdentificado(BaseModel):
    concepto: str
    concepto_facturado: Optional[str] = None
    base_gravable: Optional[float] = None
    concepto_index: Optional[int] = None

# 🆕 NUEVO MODELO PARA DETALLES POR CONCEPTO
class DetalleConcepto(BaseModel):
    """Detalle individual de cada concepto liquidado"""
    concepto: str
    concepto_facturado: Optional[str] = None
    tarifa_retencion: float
    base_gravable: float
    valor_retencion: float
    codigo_concepto: Optional[str] = None  # Código del concepto desde BD

class NaturalezaTercero(BaseModel):
    es_persona_natural: Optional[bool] = None
    es_declarante: Optional[bool] = None
    regimen_tributario: Optional[str] = None  # SIMPLE, ORDINARIO, ESPECIAL
    es_autorretenedor: Optional[bool] = None

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
    
    condiciones_cumplidas: CondicionesArticulo383 = CondicionesArticulo383()
    deducciones_identificadas: DeduccionesArticulo383 = DeduccionesArticulo383()
    

class AnalisisFactura(BaseModel):
    conceptos_identificados: List[ConceptoIdentificado]
    naturaleza_tercero: Optional[NaturalezaTercero]
    articulo_383: Optional[InformacionArticulo383] = None  # NUEVA SECCIÓN
    es_facturacion_exterior: bool = False  # Default False, se obtiene de clasificación inicial
    valor_total: Optional[float]
    observaciones: List[str]

class ResultadoLiquidacion(BaseModel):
    valor_base_retencion: float
    valor_retencion: float
    valor_factura_sin_iva: float  # NUEVO: Valor total de la factura sin IVA (de Gemini)
    conceptos_aplicados: List[DetalleConcepto]  #  NUEVO: Detalles por concepto
    resumen_conceptos: str  #  NUEVO: Resumen descriptivo - Puede que no sea necesario
    fecha_calculo: str
    puede_liquidar: bool
    mensajes_error: List[str]
    estado: str  # NUEVO: "No aplica impuesto", "Preliquidacion sin finalizar", "Preliquidado"
    

# ===============================
# LIQUIDADOR DE RETENCIÓN
# ===============================

class LiquidadorRetencion:
    """
    Calcula retenciones en la fuente según normativa colombiana.
    
    Aplica tarifas exactas basadas en el diccionario CONCEPTOS_RETEFUENTE
    y valida todas las condiciones previas para determinar si aplica retención.
    """
    
    def __init__(self, estructura_contable: int = None, db_manager = None):
        """
        Inicializa el liquidador

        Args:
            estructura_contable: Código de estructura contable para consultas
            db_manager: Instancia de DatabaseManager para consultas a BD
        """
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager
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

        # VALIDACIÓN 1: Conceptos facturados en documentos
        conceptos_sin_facturar = [
            c for c in analisis.conceptos_identificados
            if not c.concepto_facturado or c.concepto_facturado.strip() == ""
        ]

        if conceptos_sin_facturar:
            mensajes_error.append("No se identificaron conceptos facturados en los documentos")
            mensajes_error.append(f"Se encontraron {len(conceptos_sin_facturar)} concepto(s) sin concepto facturado")
            logger.error(f"Conceptos sin concepto_facturado: {len(conceptos_sin_facturar)}")
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="Preliquidacion sin finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )

        # VALIDACIÓN 2: Naturaleza del tercero
        resultado_validacion = self._validar_naturaleza_tercero(analisis.naturaleza_tercero)
        if not resultado_validacion["puede_continuar"]:
            return self._crear_resultado_no_liquidable(
                resultado_validacion["mensajes"],
                estado=resultado_validacion.get("estado", "Preliquidacion sin finalizar"),
                valor_factura_sin_iva=analisis.valor_total or 0
            )
        
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
            logger.warning(f"Conceptos no identificados: {len(conceptos_no_identificados)}")
        
        # Verificar si hay al menos un concepto identificado
        if not conceptos_identificados:
            mensajes_error.append("No se identificaron conceptos válidos para calcular retención")
            puede_liquidar = False
            logger.error("No hay conceptos identificados válidos")

        if not puede_liquidar:
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="Preliquidacion sin finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )
        
        #  VALIDACIÓN SEPARADA: ARTÍCULO 383 PARA PERSONAS NATURALES
        # Verificar si se analizó Art 383 y si aplica
        if analisis.articulo_383 :
            logger.info(" Aplicando Artículo 383 - Tarifas progresivas para persona natural")
    
            # Usar función separada para Art 383
            resultado_art383 = self._calcular_retencion_articulo_383_separado(analisis)
            
            if resultado_art383["puede_liquidar"]:
                logger.info(f" Artículo 383 liquidado exitosamente: ${resultado_art383['resultado'].valor_retencion:,.2f}")
                return resultado_art383["resultado"]
            else:
                # Si falla el cálculo del Art. 383, continuar con cálculo tradicional
                mensajes_error.extend(resultado_art383["mensajes_error"])
                mensajes_error.append("Aplicando tarifa convencional porque no aplica Art. 383")
                logger.warning(" Fallback a tarifa convencional porque no aplica Art. 383")

        else:
            # Explicar por qué no aplica Art. 383
            self._agregar_observaciones_art383_no_aplica(analisis.articulo_383, mensajes_error)
        
        # CÁLCULO DE RETENCIÓN CONVENCIONAL
        logger.info(f" Calculando retención para {len(conceptos_identificados)} concepto(s) con bases individuales")
        
        # Obtener conceptos de retefuente
        conceptos_retefuente = self._obtener_conceptos_retefuente()
        
        valor_base_total = analisis.valor_total or 0 # valor de la factura SIN IVA
        valor_retencion_total = 0
        conceptos_aplicados = []
        tarifas_aplicadas = []
        detalles_calculo = []
        
        # CORRECCIÓN CRÍTICA: Validar bases individuales por concepto
        conceptos_con_bases, conceptos_sin_base = self._validar_bases_individuales_conceptos(conceptos_identificados, valor_base_total)

        # Validar si hay conceptos sin base gravable
        if conceptos_sin_base:
            mensajes_error.append("No se extrajo la base gravable de los siguientes conceptos:")
            for concepto in conceptos_sin_base:
                mensajes_error.append(f"  • {concepto}")
            logger.error(f"Liquidación detenida: {len(conceptos_sin_base)} concepto(s) sin base gravable")
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="Preliquidacion sin finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )

        # VALIDACIÓN: Sumatoria de bases gravables debe coincidir con valor total
        suma_bases_gravables = sum(c.base_gravable for c in conceptos_con_bases)
        tolerancia = 1.0  # Tolerancia de $1 peso por redondeos

        if abs(suma_bases_gravables - valor_base_total) > tolerancia:
            diferencia = suma_bases_gravables - valor_base_total
            mensajes_error.append("Error: La sumatoria de las bases gravables no coincide con el valor total de la factura")
            mensajes_error.append(f"  • Suma de bases gravables: ${suma_bases_gravables:,.2f}")
            mensajes_error.append(f"  • Valor total factura (sin IVA): ${valor_base_total:,.2f}")
            mensajes_error.append(f"  • Diferencia: ${diferencia:,.2f}")
            logger.error(f"Liquidación detenida: Suma bases (${suma_bases_gravables:,.2f}) != Valor total (${valor_base_total:,.2f})")
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="Preliquidacion sin finalizar",
                valor_factura_sin_iva=analisis.valor_total or 0
            )

        for concepto_item in conceptos_con_bases:
            logger.info(f" Procesando concepto: {concepto_item.concepto} - Base: ${concepto_item.base_gravable:,.2f}")
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
            return self._crear_resultado_no_liquidable(
                mensajes_error,
                estado="No aplica impuesto",
                valor_factura_sin_iva=analisis.valor_total or 0
            )
        
        #  PREPARAR RESULTADO FINAL CON ESTRUCTURA MEJORADA
        # Crear lista de detalles por concepto
        detalles_conceptos = []
        conceptos_resumen = []
        
        # Agregar detalles del cálculo a los mensajes (mantener funcionalidad existente)
        if detalles_calculo:
            mensajes_error.append("Detalle del cálculo:")
            
            for detalle in detalles_calculo:
                # Agregar al mensaje de error como antes
                mensajes_error.append(
                    f"  • {detalle['concepto']}: ${detalle['base_gravable']:,.0f} x {detalle['tarifa']:.1f}% = ${detalle['valor_retencion']:,.0f}"
                )

                # Crear objeto DetalleConcepto para nueva estructura
                detalle_concepto = DetalleConcepto(
                    concepto=detalle['concepto'],
                    concepto_facturado=detalle.get('concepto_facturado', None),
                    tarifa_retencion=detalle['tarifa'],
                    base_gravable=detalle['base_gravable'],
                    valor_retencion=detalle['valor_retencion'],
                    codigo_concepto=detalle.get('codigo_concepto', None)
                )
                detalles_conceptos.append(detalle_concepto)
                
                # Crear resumen descriptivo para cada concepto
                conceptos_resumen.append(f"{detalle['concepto']} ({detalle['tarifa']:.1f}%)")
        
        # Generar resumen descriptivo completo
        resumen_descriptivo = " + ".join(conceptos_resumen) if conceptos_resumen else "No aplica retención"
        
        # Crear resultado con nueva estructura
        resultado = ResultadoLiquidacion(
            valor_base_retencion=valor_base_total,
            valor_retencion=valor_retencion_total,
            valor_factura_sin_iva=analisis.valor_total or 0,  # NUEVO: Valor total de la factura
            conceptos_aplicados=detalles_conceptos,  #  NUEVO: Lista de conceptos individuales
            resumen_conceptos=resumen_descriptivo,   #  NUEVO: Resumen descriptivo
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=True,
            mensajes_error=mensajes_error,
            estado="Preliquidado"  # NUEVO: Proceso completado exitosamente
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
            
            # PASO 9: Crear resultado con nueva estructura
            concepto_original = analisis.conceptos_identificados[0].concepto if analisis.conceptos_identificados else "Honorarios y servicios"
            concepto_art383 = f"Artículo 383 - {concepto_original}"
            
            # 🆕 NUEVA ESTRUCTURA: Crear detalle del concepto Art. 383
            detalle_concepto_art383 = DetalleConcepto(
                concepto=concepto_art383,
                tarifa_retencion=tarifa_art383,
                base_gravable=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                codigo_concepto=None  # Art 383 no tiene código de concepto específico
            )
            
            # Generar resumen descriptivo
            resumen_art383 = f"{concepto_art383} ({tarifa_art383*100:.1f}%)"
            
            resultado = ResultadoLiquidacion(
                valor_base_retencion=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                conceptos_aplicados=[detalle_concepto_art383],  # 🆕 NUEVO: Lista con concepto individual
                resumen_conceptos=resumen_art383,  # 🆕 NUEVO: Resumen descriptivo
                fecha_calculo=datetime.now().isoformat(),
                puede_liquidar=True,
                mensajes_error=mensajes_detalle,
                estado="Preliquidado"  # NUEVO: Artículo 383 completado exitosamente
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
    
    def _calcular_retencion_articulo_383_separado(self, analisis: AnalisisFactura) -> Dict[str, Any]:
        """
         FUNCIÓN MODIFICADA: Cálculo del Artículo 383 con VALIDACIONES MANUALES.
    
        Gemini solo identifica datos, Python valida y calcula según normativa.
        
        Args:
            analisis: Análisis de factura que incluye el resultado del Art 383 de Gemini
            
        Returns:
            Dict[str, Any]: Resultado del cálculo separado del Art. 383
        """
        logger.info(" Iniciando cálculo Artículo 383 con validaciones manuales")
        
        try:
            # Verificar que existe información del Art 383
            if not analisis.articulo_383:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["No se puede calcular Art 383: no hay análisis disponible"]
                }
            
            art383 = analisis.articulo_383
            mensajes_error = []
            
            # Importar constantes del Artículo 383
            from datetime import datetime, timedelta
            from config import (
                UVT_2025, SMMLV_2025, obtener_tarifa_articulo_383, 
                calcular_limite_deduccion, LIMITES_DEDUCCIONES_ART383
            )
            
            # ===============================
            #  PASO 1: VALIDACIONES BÁSICAS OBLIGATORIAS
            # ===============================
            
            logger.info(" Paso 1: Validaciones básicas...")
            
            # Extraer datos identificados por Gemini
            condiciones = art383.condiciones_cumplidas if hasattr(art383, 'condiciones_cumplidas') else None
            deducciones = art383.deducciones_identificadas if hasattr(art383, 'deducciones_identificadas') else None
            
            if not condiciones:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: No se pudieron extraer las condiciones del análisis de Gemini"]
                }
            
            # VALIDACIÓN 1.1: Persona natural
            es_persona_natural = getattr(condiciones, 'es_persona_natural', False)
            if not es_persona_natural:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: NO APLICA - El tercero no es persona natural"]
                }
            logger.info(" Validación 1.1: Es persona natural")
            
            # VALIDACIÓN 1.2: Conceptos aplicables
            conceptos_aplicables = getattr(condiciones, 'conceptos_aplicables', False)
            if not conceptos_aplicables:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: NO APLICA - Los conceptos identificados no son aplicables para Art. 383"]
                }
            logger.info(" Validación 1.2: Conceptos aplicables para Art. 383")
            
            # ===============================
            #  PASO 2: VALIDACIÓN DE PRIMER PAGO Y PLANILLA
            # ===============================
            
            logger.info(" Paso 2: Validación primer pago y planilla...")
            
            es_primer_pago = getattr(condiciones, 'es_primer_pago', False)
            planilla_seguridad_social = False
            fecha_planilla = "0000-00-00"
            IBC_seguridad_social = 0.0
            
            # Extraer información de planilla de seguridad social
            if deducciones and hasattr(deducciones, 'planilla_seguridad_social'):
                planilla_info = deducciones.planilla_seguridad_social
                planilla_seguridad_social = getattr(planilla_info, 'planilla_seguridad_social', False)
                fecha_planilla = getattr(planilla_info, 'fecha_de_planilla_seguridad_social', "0000-00-00")
                IBC_seguridad_social = getattr(planilla_info, 'IBC_seguridad_social', 0.0)
            
            # VALIDACIÓN 2.1: Si NO es primer pago, planilla es OBLIGATORIA
            if not es_primer_pago and not planilla_seguridad_social:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": [
                        "Art 383: NO APLICA - No es primer pago y no se encontró planilla de seguridad social",
                        "La planilla de seguridad social es OBLIGATORIA cuando no es primer pago"
                    ]
                }
            
            if es_primer_pago:
                logger.info(" Validación 2.1: Es primer pago - planilla no obligatoria")
            else:
                logger.info(" Validación 2.1: No es primer pago pero planilla presente")
            
            # ===============================
            #  PASO 3: VALIDACIÓN DE FECHA DE PLANILLA
            # ===============================
            
            if planilla_seguridad_social and fecha_planilla != "0000-00-00":
                logger.info(" Paso 3: Validación fecha de planilla...")

                try:
                    from dateutil.relativedelta import relativedelta
                    
                    # Parsear fecha de planilla
                    fecha_planilla_obj = datetime.strptime(fecha_planilla, "%Y-%m-%d")
                    fecha_actual = datetime.now()
                    
                    # Calcular diferencia exacta
                    diferencia = relativedelta(fecha_actual, fecha_planilla_obj)
                    diferencia_total_dias = (fecha_actual - fecha_planilla_obj).days
                    
                    # VALIDACIÓN 3.1: Planilla no debe tener más de 60 días de antigüedad
                    if diferencia_total_dias > 60:
                        mensajes_error.append(f" ALERTA: Planilla con {diferencia_total_dias} días de antigüedad")
                        mensajes_error.append(f"Detalle: {diferencia.years} años, {diferencia.months} meses, {diferencia.days} días extras")
                        mensajes_error.append("Art 383: NO APLICA - La planilla tiene más de 60 días de antigüedad")
                        mensajes_error.append("Normativa: La planilla debe ser reciente (máximo 60 días)")
                        return {
                            "puede_liquidar": False,
                            "mensajes_error": mensajes_error
                        }
                    
                    logger.info(f" Validación 3.1: Planilla válida ({diferencia_total_dias} días de antigüedad)")
                    logger.info(f"Detalle preciso: {diferencia.years} años, {diferencia.months} meses, {diferencia.days} días")
                    
                except ImportError:
                    # Fallback si dateutil no está disponible
                    logger.warning("dateutil no disponible, usando cálculo simple")
                    diferencia_dias_simple = (fecha_actual - fecha_planilla_obj).days
                    
                    if diferencia_dias_simple > 60:
                        mensajes_error.append(f" ALERTA: Planilla con {diferencia_dias_simple} días de antigüedad")
                        mensajes_error.append("Art 383: NO APLICA - La planilla tiene más de 60 días de antigüedad")
                        return {
                            "puede_liquidar": False,
                            "mensajes_error": mensajes_error
                        }

                    logger.info(f" Validación: Planilla válida ({diferencia_dias_simple} días de antigüedad)")

                except ValueError:
                    mensajes_error.append(f" ADVERTENCIA: No se pudo validar la fecha de planilla: {fecha_planilla}")
                    logger.warning(f"Fecha de planilla inválida: {fecha_planilla}")
            
            # ===============================
            #  PASO 4: EXTRACCIÓN Y VALIDACIÓN DEL INGRESO
            # ===============================
            
            logger.info(" Paso 4: Extracción del ingreso...")
            
            # Extraer ingreso identificado por Gemini
            ingreso_bruto = getattr(condiciones, 'ingreso', 0.0)
            
            # Si Gemini no identificó ingreso, intentar desde otros campos
            if ingreso_bruto <= 0:
                ingreso_bruto = analisis.valor_total or 0.0
                if ingreso_bruto <= 0:
                    # Intentar sumar desde TODOS los conceptos identificados
                    suma_bases_conceptos = 0.0
                    conceptos_con_base = []
                    
                    for concepto in analisis.conceptos_identificados:
                        if concepto.base_gravable and concepto.base_gravable > 0:
                            suma_bases_conceptos += concepto.base_gravable
                            conceptos_con_base.append(f"{concepto.concepto}: ${concepto.base_gravable:,.2f}")
                    
                    if suma_bases_conceptos > 0:
                        ingreso_bruto = suma_bases_conceptos
                        logger.info(f" Ingreso calculado sumando {len(conceptos_con_base)} conceptos: ${ingreso_bruto:,.2f}")
                        logger.info(f"   Detalle conceptos: {', '.join(conceptos_con_base)}")
                    else:
                        logger.warning("No se encontraron conceptos con base gravable válida")
            
            if ingreso_bruto <= 0:
                return {
                    "puede_liquidar": False,
                    "mensajes_error": ["Art 383: NO se pudo determinar el ingreso bruto"]
                }
            
            logger.info(f" Ingreso bruto identificado: ${ingreso_bruto:,.2f}")
            
            # ===============================
            #  PASO 5: VALIDACIÓN DEL IBC (40% DEL INGRESO)
            # ===============================
            
            if planilla_seguridad_social and IBC_seguridad_social > 0:
                logger.info(" Paso 5: Validación IBC vs 40% del ingreso...")
                
                ibc_esperado = ingreso_bruto * 0.40  # 40% del ingreso
                diferencia_ibc = abs(IBC_seguridad_social - ibc_esperado)
                tolerancia = ibc_esperado * 0.01  # 1% de tolerancia

                # VALIDACIÓN 5.1: IBC debe ser aproximadamente 40% del ingreso
                if diferencia_ibc > tolerancia:
                    mensajes_error.append(f" ALERTA IBC: IBC identificado ${IBC_seguridad_social:,.2f} no coincide con 40% del ingreso ${ibc_esperado:,.2f}")
                    mensajes_error.append(f"Diferencia: ${diferencia_ibc:,.2f} (tolerancia: ${tolerancia:,.2f})")
                    mensajes_error.append("Se continúa con el cálculo usando el ingreso identificado")
                    logger.warning(f"IBC no coincide con 40% del ingreso. IBC: ${IBC_seguridad_social:,.2f}, Esperado: ${ibc_esperado:,.2f}")
                else:
                    logger.info(f" Validación 5.1: IBC válido (${IBC_seguridad_social:,.2f} ≈ 40% del ingreso)")
            
            # ===============================
            #  PASO 6: VALIDACIONES DE DEDUCCIONES MANUALES
            # ===============================

            logger.info(" Paso 6: Validaciones de deducciones...")

            deducciones_aplicables = {
                "intereses_vivienda": 0.0,
                "dependientes_economicos": 0.0,
                "medicina_prepagada": 0.0,
                "AFC": 0.0,
                "pensiones_voluntarias": 0.0
            }
            
            if deducciones:
                # VALIDACIÓN 6.1: Intereses corrientes por vivienda
                if hasattr(deducciones, 'intereses_vivienda'):
                    intereses_info = deducciones.intereses_vivienda
                    intereses_corrientes = getattr(intereses_info, 'intereses_corrientes', 0.0)
                    certificado_bancario = getattr(intereses_info, 'certificado_bancario', False)
                    
                    if intereses_corrientes > 0.0 and certificado_bancario:
                        # Dividir entre 12 (mensual) y limitar a 100 UVT
                        valor_mensual = intereses_corrientes / 12
                        limite_uvt = 100 * UVT_2025
                        deducciones_aplicables["intereses_vivienda"] = min(valor_mensual, limite_uvt)
                        logger.info(f" Intereses vivienda aplicados: ${deducciones_aplicables['intereses_vivienda']:,.2f}")
                    elif intereses_corrientes > 0.0 and not certificado_bancario:
                        mensajes_error.append(" Intereses vivienda identificados pero falta certificado bancario")
                
                # VALIDACIÓN 6.2: Dependientes económicos
                if hasattr(deducciones, 'dependientes_economicos'):
                    dependientes_info = deducciones.dependientes_economicos
                    declaracion_juramentada = getattr(dependientes_info, 'declaracion_juramentada', False)
                    
                    if declaracion_juramentada:
                        # Aplicar 10% del ingreso
                        deducciones_aplicables["dependientes_economicos"] = ingreso_bruto * 0.10
                        logger.info(f" Dependientes económicos aplicados: ${deducciones_aplicables['dependientes_economicos']:,.2f}")

                # VALIDACIÓN 6.3: Medicina prepagada
                if hasattr(deducciones, 'medicina_prepagada'):
                    medicina_info = deducciones.medicina_prepagada
                    valor_sin_iva = getattr(medicina_info, 'valor_sin_iva_med_prepagada', 0.0)
                    certificado_medicina = getattr(medicina_info, 'certificado_med_prepagada', False)
                    
                    if valor_sin_iva > 0.0 and certificado_medicina:
                        # Dividir entre 12 y limitar a 16 UVT
                        valor_mensual = valor_sin_iva / 12
                        limite_uvt = 16 * UVT_2025
                        deducciones_aplicables["medicina_prepagada"] = min(valor_mensual, limite_uvt)
                        logger.info(f" Medicina prepagada aplicada: ${deducciones_aplicables['medicina_prepagada']:,.2f}")
                    elif valor_sin_iva > 0.0 and not certificado_medicina:
                        mensajes_error.append(" Medicina prepagada identificada pero falta certificado")
                
                # VALIDACIÓN 6.4: AFC (Ahorro para Fomento a la Construcción)
                if hasattr(deducciones, 'AFC'):
                    afc_info = deducciones.AFC
                    valor_depositar = getattr(afc_info, 'valor_a_depositar', 0.0)
                    planilla_afc = getattr(afc_info, 'planilla_de_cuenta_AFC', False)
                    
                    if valor_depositar > 0.0 and planilla_afc:
                        # Limitar al 25% del ingreso y 316 UVT
                        limite_porcentaje = ingreso_bruto * 0.25
                        limite_uvt = 316 * UVT_2025
                        deducciones_aplicables["AFC"] = min(valor_depositar, limite_porcentaje, limite_uvt)
                        logger.info(f" AFC aplicado: ${deducciones_aplicables['AFC']:,.2f}")
                    elif valor_depositar > 0.0 and not planilla_afc:
                        mensajes_error.append(" AFC identificado pero falta planilla de cuenta")
                
                # VALIDACIÓN 6.5: Pensiones voluntarias
                if planilla_seguridad_social and IBC_seguridad_social >= (4 * SMMLV_2025):
                    # Solo si IBC >= 4 SMMLV
                    deducciones_aplicables["pensiones_voluntarias"] = IBC_seguridad_social * 0.01  # 1% del IBC
                    logger.info(f" Pensiones voluntarias aplicadas: ${deducciones_aplicables['pensiones_voluntarias']:,.2f}")
            
            # ===============================
            #  PASO 7: CÁLCULO FINAL CON VALIDACIONES
            # ===============================
            
            logger.info(" Paso 7: Cálculo final...")
            
            # Calcular aportes a seguridad social (40% del ingreso)
            aportes_seguridad_social = ingreso_bruto * LIMITES_DEDUCCIONES_ART383["seguridad_social_porcentaje"]
            
            # Sumar todas las deducciones aplicables
            total_deducciones = sum(deducciones_aplicables.values())
            
            # Aplicar límite máximo del 40% del ingreso bruto
            limite_maximo_deducciones = ingreso_bruto * LIMITES_DEDUCCIONES_ART383["deducciones_maximas_porcentaje"]
            deducciones_limitadas = min(total_deducciones, limite_maximo_deducciones)
            
            if total_deducciones > limite_maximo_deducciones:
                mensajes_error.append(f" Deducciones limitadas al 40% del ingreso: ${deducciones_limitadas:,.2f} (original: ${total_deducciones:,.2f})")
                logger.warning(f"Deducciones limitadas al 40%: ${deducciones_limitadas:,.2f}")
            
            # Calcular base gravable final
            base_gravable_final = ingreso_bruto - aportes_seguridad_social - deducciones_limitadas
            
            # Verificar que la base gravable no sea negativa
            if base_gravable_final < 0:
                logger.warning("Base gravable negativa, estableciendo en 0")
                base_gravable_final = 0
            
            # Convertir base gravable a UVT
            base_gravable_uvt = base_gravable_final / UVT_2025
            
            # Aplicar tarifa progresiva del Artículo 383
            tarifa_art383 = obtener_tarifa_articulo_383(base_gravable_final)
            valor_retencion_art383 = base_gravable_final * tarifa_art383
            
            logger.info(f" Cálculo completado:")
            logger.info(f"   - Ingreso bruto: ${ingreso_bruto:,.2f}")
            logger.info(f"   - Aportes seg. social: ${aportes_seguridad_social:,.2f}")
            logger.info(f"   - Deducciones: ${deducciones_limitadas:,.2f}")
            logger.info(f"   - Base gravable: ${base_gravable_final:,.2f}")
            logger.info(f"   - Tarifa: {tarifa_art383*100:.1f}%")
            logger.info(f"   - Retención: ${valor_retencion_art383:,.2f}")
            
            # ===============================
            #  PASO 8: PREPARAR RESULTADO FINAL
            # ===============================
            
            # Preparar mensajes explicativos
            mensajes_detalle = [
                " Cálculo Artículo 383 - VALIDACIONES MANUALES APLICADAS:",
                f" Validaciones básicas: Persona natural + Conceptos aplicables",
                f" Primer pago: {'SÍ' if es_primer_pago else 'NO'} - Planilla: {'Presente' if planilla_seguridad_social else 'No requerida'}",
                f" Ingreso bruto: ${ingreso_bruto:,.2f}",
                f" Aportes seguridad social (40%): ${aportes_seguridad_social:,.2f}",
                f" Deducciones aplicables: ${deducciones_limitadas:,.2f}"
            ]
            
            # Detallar deducciones aplicadas
            for tipo, valor in deducciones_aplicables.items():
                if valor > 0:
                    nombre_deduccion = tipo.replace("_", " ").title()
                    mensajes_detalle.append(f"   - {nombre_deduccion}: ${valor:,.2f}")
            
            mensajes_detalle.extend([
                f" Base gravable final: ${base_gravable_final:,.2f}",
                f" Base gravable en UVT: {base_gravable_uvt:.2f} UVT",
                f" Tarifa aplicada: {tarifa_art383*100:.1f}%",
                f" Retención calculada: ${valor_retencion_art383:,.2f}",
                " Cálculo completado con validaciones manuales"
            ])
            
            # Agregar mensajes de error/alertas al detalle
            if mensajes_error:
                mensajes_detalle.extend(["", " ALERTAS Y OBSERVACIONES:"] + mensajes_error)
            
            # Crear resultado con nueva estructura
            concepto_original = analisis.conceptos_identificados[0].concepto if analisis.conceptos_identificados else "Honorarios y servicios"
            concepto_art383_validado = f"Artículo 383 (Validado) - {concepto_original}"
            
            # Crear detalle del concepto Art. 383 validado manualmente
            detalle_concepto_art383_validado = DetalleConcepto(
                concepto=concepto_art383_validado,
                tarifa_retencion=tarifa_art383,
                base_gravable=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                codigo_concepto=None  # Art 383 no tiene código de concepto específico
            )
            
            # Generar resumen descriptivo
            resumen_art383_validado = f"{concepto_art383_validado} ({tarifa_art383*100:.1f}%)"
            
            resultado = ResultadoLiquidacion(
                valor_base_retencion=base_gravable_final,
                valor_retencion=valor_retencion_art383,
                conceptos_aplicados=[detalle_concepto_art383_validado],
                resumen_conceptos=resumen_art383_validado,
                fecha_calculo=datetime.now().isoformat(),
                puede_liquidar=True,
                mensajes_error=mensajes_detalle,
                estado="Preliquidado"  # NUEVO: Artículo 383 validado completado exitosamente
            )
            
            return {
                "puede_liquidar": True,
                "resultado": resultado,
                "mensajes_error": []
            }
            
        except Exception as e:
            logger.error(f"💥 Error en cálculo Art. 383 con validaciones manuales: {e}")
            return {
                "puede_liquidar": False,
                "mensajes_error": [f"Error en cálculo validado Art. 383: {str(e)}"]
            }
    
    def _procesar_deducciones_art383(self, deducciones_identificadas, ingreso_bruto: float) -> Dict[str, float]:
        """
        Procesa las deducciones identificadas por Gemini y aplica límites según normativa.
        
        Args:
            deducciones_identificadas: Deducciones identificadas por Gemini
            ingreso_bruto: Ingreso bruto para calcular límites
            
        Returns:
            Dict[str, float]: Deducciones aplicables con límites aplicados
        """
        from config import calcular_limite_deduccion
        
        deducciones_aplicables = {
            "intereses_vivienda": 0.0,
            "dependientes_economicos": 0.0,
            "medicina_prepagada": 0.0,
            "rentas_exentas": 0.0
        }
        
        # Intereses por vivienda
        if (deducciones_identificadas.intereses_vivienda.tiene_soporte and 
            deducciones_identificadas.intereses_vivienda.valor > 0):
            deducciones_aplicables["intereses_vivienda"] = calcular_limite_deduccion(
                "intereses_vivienda", ingreso_bruto, deducciones_identificadas.intereses_vivienda.valor
            )
            logger.info(f" Intereses vivienda aplicados: ${deducciones_aplicables['intereses_vivienda']:,.2f}")
        
        # Dependientes económicos
        if (deducciones_identificadas.dependientes_economicos.tiene_soporte and 
            deducciones_identificadas.dependientes_economicos.valor > 0):
            deducciones_aplicables["dependientes_economicos"] = calcular_limite_deduccion(
                "dependientes_economicos", ingreso_bruto, deducciones_identificadas.dependientes_economicos.valor
            )
            logger.info(f" Dependientes económicos aplicados: ${deducciones_aplicables['dependientes_economicos']:,.2f}")
        
        # Medicina prepagada
        if (deducciones_identificadas.medicina_prepagada.tiene_soporte and 
            deducciones_identificadas.medicina_prepagada.valor > 0):
            deducciones_aplicables["medicina_prepagada"] = calcular_limite_deduccion(
                "medicina_prepagada", ingreso_bruto, deducciones_identificadas.medicina_prepagada.valor
            )
            logger.info(f" Medicina prepagada aplicada: ${deducciones_aplicables['medicina_prepagada']:,.2f}")
        
        # Rentas exentas
        if (deducciones_identificadas.rentas_exentas.tiene_soporte and 
            deducciones_identificadas.rentas_exentas.valor > 0):
            deducciones_aplicables["rentas_exentas"] = calcular_limite_deduccion(
                "rentas_exentas", ingreso_bruto, deducciones_identificadas.rentas_exentas.valor
            )
            logger.info(f" Rentas exentas aplicadas: ${deducciones_aplicables['rentas_exentas']:,.2f}")
        
        return deducciones_aplicables
    
    def _generar_mensajes_detalle_art383(self, ingreso_bruto: float, aportes_seguridad_social: float, 
                                        deducciones_limitadas: float, deducciones_aplicables: Dict[str, float],
                                        base_gravable_final: float, base_gravable_uvt: float, 
                                        tarifa_art383: float, valor_retencion_art383: float) -> List[str]:
        """
        Genera mensajes detallados explicando el cálculo del Artículo 383.
        
        Returns:
            List[str]: Lista de mensajes explicativos
        """
        mensajes_detalle = [
            "📜 Cálculo bajo Artículo 383 del Estatuto Tributario (ANÁLISIS SEPARADO):",
            f"  • Ingreso bruto: ${ingreso_bruto:,.2f}",
            f"  • Aportes seguridad social (40%): ${aportes_seguridad_social:,.2f}",
            f"  • Deducciones aplicables: ${deducciones_limitadas:,.2f}"
        ]
        
        # Detallar deducciones aplicadas
        for tipo, valor in deducciones_aplicables.items():
            if valor > 0:
                nombre_deduccion = tipo.replace("_", " ").title()
                mensajes_detalle.append(f"    - {nombre_deduccion}: ${valor:,.2f}")
        
        mensajes_detalle.extend([
            f"  • Base gravable final: ${base_gravable_final:,.2f}",
            f"  • Base gravable en UVT: {base_gravable_uvt:.2f} UVT",
            f"  • Tarifa aplicada: {tarifa_art383*100:.1f}%",
            f"  • Retención calculada: ${valor_retencion_art383:,.2f}",
            "✅ Cálculo completado con análisis separado de Gemini"
        ])
        
        return mensajes_detalle
    
    def _agregar_observaciones_art383_no_aplica(self, articulo_383, mensajes_error: List[str]) -> None:
        """
        🆕 NUEVA FUNCIÓN: Agrega observaciones cuando el Artículo 383 no aplica.
        
        Args:
            articulo_383: Información del Art 383 del análisis
            mensajes_error: Lista de mensajes a la que agregar observaciones
        """
        condiciones = articulo_383.condiciones_cumplidas
        razones_no_aplica = []
        
        if not condiciones.es_persona_natural:
            razones_no_aplica.append("no es persona natural")
        if not condiciones.concepto_aplicable:
            razones_no_aplica.append("concepto no aplicable para Art. 383")
        if not condiciones.cuenta_cobro:
            razones_no_aplica.append("falta cuenta de cobro")
        if not condiciones.planilla_seguridad_social:
            razones_no_aplica.append("falta planilla de seguridad social")
        if not condiciones.es_primer_pago:
            razones_no_aplica.append("no es primer pago y falta planilla")
        
        if razones_no_aplica:
            mensajes_error.append(f" Art. 383 no aplica: {', '.join(razones_no_aplica)}")
            mensajes_error.append(" Aplicando tarifas convencionales de retefuente")
            logger.info(f" Art. 383 no aplica: {', '.join(razones_no_aplica)}")
    
    def _validar_bases_individuales_conceptos(self, conceptos_identificados: List[ConceptoIdentificado], valor_base_total: float) -> Tuple[List[ConceptoIdentificado], List[str]]:
        """
        SRP: SOLO valida que conceptos tengan base gravable.

        La responsabilidad de obtener tarifa y base mínima está en _calcular_retencion_concepto.

        Args:
            conceptos_identificados: Lista de conceptos identificados por Gemini
            valor_base_total: Valor total de la factura para validaciones

        Returns:
            Tuple[List[ConceptoIdentificado], List[str]]:
                - conceptos_validos: Conceptos con base gravable válida
                - conceptos_sin_base: Nombres de conceptos sin base (para mensajes)
        """

        # VALIDACIÓN: Identificar conceptos con y sin base gravable
        conceptos_sin_base = []
        conceptos_validos = []

        for concepto in conceptos_identificados:
            if not concepto.base_gravable or concepto.base_gravable <= 0:
                conceptos_sin_base.append(concepto.concepto)
                logger.error(f"Concepto sin base gravable: {concepto.concepto}")
            else:
                conceptos_validos.append(concepto)
                logger.info(f"Concepto válido: {concepto.concepto} = ${concepto.base_gravable:,.2f}")

        # Retornar ambas listas para que el llamador decida qué hacer
        return conceptos_validos, conceptos_sin_base
    
    
    
    def _validar_naturaleza_tercero(self, naturaleza: Optional[NaturalezaTercero]) -> Dict[str, Any]:
        """
        Valida la naturaleza del tercero y determina si puede continuar el cálculo.

        Args:
            naturaleza: Información del tercero

        Returns:
            Dict con puede_continuar, mensajes, advertencias y estado
        """
        resultado = {
            "puede_continuar": True,
            "mensajes": [],
            "advertencias": [],
            "estado": None  # NUEVO: Se asignará según validaciones
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
                resultado["estado"] = "No aplica impuesto"  # NUEVO
                logger.info("Tercero es autorretenedor - no aplica retención")
                return resultado

            # Ya no se valida responsable de IVA porque aplica retención igual

            # Validar régimen simple
            if hasattr(naturaleza, 'regimen_tributario') and naturaleza.regimen_tributario == "SIMPLE" and hasattr(naturaleza, 'es_persona_natural') and naturaleza.es_persona_natural == False:
                resultado["puede_continuar"] = False
                resultado["mensajes"].append("Régimen Simple de Tributación - Persona Jurídica - NO aplica retención en la fuente")
                resultado["estado"] = "No aplica impuesto"  # NUEVO
                logger.info("Régimen Simple detectado - no aplica retención")
                return resultado
            
            # Validar datos faltantes de forma segura
            datos_faltantes = []
          
            if not hasattr(naturaleza, 'regimen_tributario') or naturaleza.regimen_tributario is None:
                datos_faltantes.append("régimen tributario")
            if not hasattr(naturaleza, 'es_autorretenedor') or naturaleza.es_autorretenedor is None:
                datos_faltantes.append("condición de autorretenedor")

            
            if datos_faltantes:
                resultado["advertencias"].append(
                    f"Faltan datos: {', '.join(datos_faltantes)}. "
                    "Por favor adjunte el RUT para completar la información."
                )
                resultado["puede_continuar"] = False
                resultado["mensajes"].append(f"Datos faltantes de la naturaleza del tercero - NO se puede practicar retención : {datos_faltantes}")
                resultado["estado"] = "Preliquidacion sin finalizar"  # NUEVO
                logger.warning(f"Datos faltantes de la naturaleza del tercero: {datos_faltantes}")
                return resultado
                
            
        except AttributeError as e:
            logger.error(f"Error accediendo a atributos de naturaleza_tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero. Verifique que el RUT esté adjunto.")
        except Exception as e:
            logger.error(f"Error inesperado validando naturaleza del tercero: {e}")
            resultado["advertencias"].append("Error procesando información del tercero.")
        
        return resultado
    
    def _calcular_retencion_concepto(self, concepto_item: ConceptoIdentificado,
                                   conceptos_retefuente: Dict) -> Dict[str, Any]:
        """
        SRP: Responsable de obtener tarifa/base mínima (BD o diccionario) Y calcular retención.

        Args:
            concepto_item: Concepto identificado por Gemini con base_gravable y concepto_index
            conceptos_retefuente: Diccionario de conceptos (fallback legacy)

        Returns:
            Dict con resultado del cálculo para este concepto
        """
        concepto_aplicado = concepto_item.concepto
        base_concepto = concepto_item.base_gravable

        # VALIDACIÓN ESPECIAL: Base cero por falta de valor disponible
        if base_concepto <= 0:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"{concepto_aplicado}: Sin base gravable disponible (${base_concepto:,.2f})",
                "concepto": concepto_aplicado
            }

        # RESPONSABILIDAD: Obtener tarifa, base mínima y código de concepto
        tarifa = None
        base_minima = None
        codigo_concepto = None

        # ESTRATEGIA 1: Si tiene concepto_index, consultar BD
        if concepto_item.concepto_index and self.db_manager and self.estructura_contable is not None:
            try:
                logger.info(f"Consultando BD para concepto_index={concepto_item.concepto_index}")
                resultado_bd = self.db_manager.obtener_concepto_por_index(
                    concepto_item.concepto_index,
                    self.estructura_contable
                )

                if resultado_bd['success']:
                    porcentaje_bd = resultado_bd['data']['porcentaje']
                    base_minima_bd = resultado_bd['data']['base']
                    codigo_concepto = resultado_bd['data'].get('codigo_concepto', None)

                    tarifa = porcentaje_bd  # Ya viene como 11 (porcentaje directo)
                    base_minima = base_minima_bd

                    logger.info(f"Datos obtenidos de BD: tarifa={tarifa}%, base_minima=${base_minima:,.2f}, codigo={codigo_concepto}")
                else:
                    logger.warning(f"No se pudo obtener datos de BD: {resultado_bd['message']}")
            except Exception as e:
                logger.error(f"Error consultando BD: {e}")

        # ESTRATEGIA 2: Fallback a diccionario legacy si no se obtuvo de BD
        if tarifa is None or base_minima is None:
            if concepto_aplicado not in conceptos_retefuente:
                return {
                    "aplica_retencion": False,
                    "mensaje_error": f"Concepto '{concepto_aplicado}' no encontrado en BD ni en diccionario",
                    "concepto": concepto_aplicado
                }

            datos_concepto = conceptos_retefuente[concepto_aplicado]
            tarifa = datos_concepto["tarifa_retencion"] * 100  # Convertir a porcentaje
            base_minima = datos_concepto["base_pesos"]
            logger.info(f"Usando diccionario legacy: tarifa={tarifa}%, base_minima=${base_minima:,.2f}")

        # Verificar base mínima
        if base_concepto < base_minima:
            return {
                "aplica_retencion": False,
                "mensaje_error": f"{concepto_aplicado}: Base ${base_concepto:,.0f} no supera mínimo de ${base_minima:,.0f}",
                "concepto": concepto_aplicado
            }

        # RESPONSABILIDAD: Calcular retención
        valor_retencion_concepto = (base_concepto * tarifa) / 100

        return {
            "aplica_retencion": True,
            "valor_retencion": valor_retencion_concepto,
            "concepto": concepto_aplicado,
            "tarifa": tarifa,
            "codigo_concepto": codigo_concepto,  # Código del concepto desde BD
            "detalle": {
                "concepto": concepto_aplicado,
                "concepto_facturado": concepto_item.concepto_facturado,
                "base_gravable": base_concepto,
                "tarifa": tarifa,
                "valor_retencion": valor_retencion_concepto,
                "base_minima": base_minima,
                "codigo_concepto": codigo_concepto
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
            
            # Importar conceptos desde config
            from config import CONCEPTOS_RETEFUENTE
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
    
    def _crear_resultado_no_liquidable(self, mensajes_error: List[str], estado: str = None, valor_factura_sin_iva: float = 0) -> ResultadoLiquidacion:
        """
        Crea un resultado cuando no se puede liquidar retención.

        Args:
            mensajes_error: Lista de mensajes explicando por qué no se puede liquidar
            estado: Estado específico a asignar (si no se proporciona, se determina automáticamente)
            valor_factura_sin_iva: Valor total de la factura sin IVA (de Gemini)

        Returns:
            ResultadoLiquidacion: Resultado con valores en cero y explicación
        """
        # 🔧 FIX: Generar concepto descriptivo en lugar de "N/A"
        concepto_descriptivo = "No aplica retención"

        # NUEVO: Determinar estado si no se proporciona
        if estado is None:
            estado = "Preliquidacion sin finalizar"  # Default

        # Determinar concepto específico y estado basado en el mensaje de error
        if mensajes_error:
            primer_mensaje = mensajes_error[0].lower()

            if "autorretenedor" in primer_mensaje:
                concepto_descriptivo = "No aplica - tercero es autorretenedor"
                estado = "No aplica impuesto"
            elif "simple" in primer_mensaje:
                concepto_descriptivo = "No aplica - régimen simple de tributación y persona jurídica"
                estado = "No aplica impuesto"
            elif "extranjera" in primer_mensaje or "exterior" in primer_mensaje:
                concepto_descriptivo = "No aplica - facturación extranjera"
            elif "base" in primer_mensaje and "mínimo" in primer_mensaje:
                concepto_descriptivo = "No aplica - base inferior al mínimo"
                estado = "No aplica impuesto"
            elif "concepto" in primer_mensaje and "identificado" in primer_mensaje:
                concepto_descriptivo = "No aplica - conceptos no identificados"
                estado = "Preliquidacion sin finalizar"
            elif "faltantes" in primer_mensaje and "datos" in primer_mensaje:
                concepto_descriptivo = "No aplica - datos del tercero incompletos"
                estado = "Preliquidacion sin finalizar"

        # 🆕 NUEVA ESTRUCTURA: Crear resultado con nueva estructura
        return ResultadoLiquidacion(
            valor_base_retencion=0,
            valor_retencion=0,
            valor_factura_sin_iva=valor_factura_sin_iva,  # NUEVO: Valor total de la factura
            conceptos_aplicados=[],  # 🆕 NUEVO: Lista vacía para casos sin retención
            resumen_conceptos=concepto_descriptivo,  # 🆕 NUEVO: Descripción clara del motivo
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=False,
            mensajes_error=mensajes_error,
            estado=estado  # NUEVO
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

            # Obtener codigo_concepto si está disponible (desde BD)
            codigo_concepto_ext = None
            if concepto_principal.concepto_index and self.db_manager and self.estructura_contable is not None:
                resultado_bd = self.db_manager.obtener_concepto_por_index(
                    concepto_principal.concepto_index, self.estructura_contable
                )
                if resultado_bd['success']:
                    codigo_concepto_ext = resultado_bd['data'].get('codigo_concepto', None)

            # 🆕 NUEVA ESTRUCTURA: Crear detalle del concepto extranjero
            detalle_concepto_extranjero = DetalleConcepto(
                concepto=concepto_principal.concepto,
                tarifa_retencion=concepto_principal.tarifa_aplicada * 100,  # Convertir a porcentaje
                base_gravable=valor_base,
                valor_retencion=valor_retencion,
                codigo_concepto=codigo_concepto_ext
            )
            
            # Generar resumen descriptivo
            resumen_extranjero = f"{concepto_principal.concepto} ({concepto_principal.tarifa_aplicada*100:.1f}%)"
            
            resultado = ResultadoLiquidacion(
                valor_base_retencion=valor_base,
                valor_retencion=valor_retencion,
                conceptos_aplicados=[detalle_concepto_extranjero],  # 🆕 NUEVO: Lista con concepto individual
                resumen_conceptos=resumen_extranjero,  # 🆕 NUEVO: Resumen descriptivo
                fecha_calculo=datetime.now().isoformat(),
                puede_liquidar=True,
                mensajes_error=[],
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

        # Obtener tarifa y código de concepto desde BD o diccionario legacy
        tarifa_concepto = None
        codigo_concepto_extranjero = None

        # ESTRATEGIA 1: Si tiene concepto_index, consultar BD
        if concepto_principal.concepto_index and self.db_manager and self.estructura_contable is not None:
            resultado_bd = self.db_manager.obtener_concepto_por_index(
                concepto_principal.concepto_index, self.estructura_contable
            )
            if resultado_bd['success']:
                porcentaje_bd = resultado_bd['data']['porcentaje']
                codigo_concepto_extranjero = resultado_bd['data'].get('codigo_concepto', None)
                tarifa_concepto = porcentaje_bd / 100  # Convertir de 11 a 0.11
                logger.info(f"Factura extranjera - Tarifa obtenida de BD: {porcentaje_bd}% = {tarifa_concepto}, codigo={codigo_concepto_extranjero}")

        # ESTRATEGIA 2: Fallback a diccionario legacy
        if tarifa_concepto is None:
            if concepto_principal.concepto in conceptos_retefuente:
                datos_concepto = conceptos_retefuente[concepto_principal.concepto]
                tarifa_concepto = datos_concepto["tarifa_retencion"]
                logger.info(f"Factura extranjera - Tarifa obtenida de diccionario legacy: {tarifa_concepto*100}%")
            else:
                logger.error(f"Factura extranjera - Concepto '{concepto_principal.concepto}' no encontrado en BD ni diccionario")
                return ResultadoLiquidacion(
                    valor_base_retencion=0,
                    valor_retencion=0,
                    conceptos_aplicados=[],
                    resumen_conceptos=f"ERROR: Concepto '{concepto_principal.concepto}' no encontrado",
                    aplica_retencion=False,
                    observaciones=f"Concepto no encontrado en base de datos ni diccionario legacy",
                    fecha_calculo=datetime.now().isoformat(),
                    puede_liquidar=False,
                    mensajes_error=[f"Concepto '{concepto_principal.concepto}' no encontrado"],
                )

        valor_retencion = valor_base * tarifa_concepto

        # 🆕 NUEVA ESTRUCTURA: Crear detalle del concepto extranjero (tarifa estándar)
        detalle_concepto_estandar = DetalleConcepto(
            concepto=concepto_principal.concepto,
            tarifa_retencion=tarifa_concepto,
            base_gravable=valor_base,
            valor_retencion=valor_retencion,
            codigo_concepto=codigo_concepto_extranjero
        )
        
        # Generar resumen descriptivo
        resumen_estandar = f"{concepto_principal.concepto} ({tarifa_concepto*100:.1f}%)"
        
        resultado = ResultadoLiquidacion(
            valor_base_retencion=valor_base,
            valor_retencion=valor_retencion,
            conceptos_aplicados=[detalle_concepto_estandar],  # 🆕 NUEVO: Lista con concepto individual
            resumen_conceptos=resumen_estandar,  # 🆕 NUEVO: Resumen descriptivo
            fecha_calculo=datetime.now().isoformat(),
            puede_liquidar=True,
            mensajes_error=analisis_factura.observaciones,

        )
        
        logger.info(f"Retención extranjera calculada: ${valor_retencion:,.0f} ({tarifa_concepto*100:.1f}%)")
        return resultado

    def liquidar_retefuente_seguro(self, analisis_retefuente: Dict[str, Any], nit_administrativo: str) -> Dict[str, Any]:
        """
        Liquida retefuente con manejo seguro de estructura de datos.

        SOLUCIONA EL ERROR: 'dict' object has no attribute 'es_facturacion_exterior'

        FUNCIONALIDAD:
        Maneja estructura JSON de análisis de Gemini
        Extrae correctamente la sección "analisis"
        Convierte dict a objeto AnalisisFactura
        Verifica campos requeridos antes de liquidar
        Manejo robusto de errores con logging detallado
        Fallback seguro en caso de errores

        Args:
            analisis_retefuente: Resultado del análisis de Gemini (estructura JSON)
            nit_administrativo: NIT administrativo

        Returns:
            Dict con resultado de liquidación o información de error
        """
        try:
            logger.info(f"Iniciando liquidación segura de retefuente para NIT: {nit_administrativo}")

            # VERIFICAR ESTRUCTURA Y EXTRAER ANÁLISIS
            es_facturacion_exterior = False  # Default
            if isinstance(analisis_retefuente, dict):
                if "analisis" in analisis_retefuente:
                    # Estructura: {"analisis": {...}, "timestamp": ..., "es_facturacion_exterior": ...}
                    datos_analisis = analisis_retefuente["analisis"]
                    es_facturacion_exterior = analisis_retefuente.get("es_facturacion_exterior", False)
                    logger.info(f"Extrayendo análisis desde estructura JSON con clave 'analisis', es_facturacion_exterior={es_facturacion_exterior}")
                else:
                    # Estructura directa: {"conceptos_identificados": ..., etc}
                    datos_analisis = analisis_retefuente
                    # En estructura directa, es_facturacion_exterior vendría en datos_analisis si existiera
                    es_facturacion_exterior = datos_analisis.get("es_facturacion_exterior", False)
                    logger.info(f"Usando estructura directa de análisis, es_facturacion_exterior={es_facturacion_exterior}")
            else:
                # Ya es un objeto, usar directamente
                datos_analisis = analisis_retefuente
                logger.info("Usando objeto AnalisisFactura directamente")

            # VERIFICAR CAMPOS REQUERIDOS (ya no incluye es_facturacion_exterior)
            campos_requeridos = ["conceptos_identificados", "naturaleza_tercero"]
            campos_faltantes = []

            for campo in campos_requeridos:
                if campo not in datos_analisis:
                    campos_faltantes.append(campo)

            if campos_faltantes:
                error_msg = f"Campos requeridos faltantes: {', '.join(campos_faltantes)}"
                logger.error(f"{error_msg}")
                logger.error(f"Claves disponibles: {list(datos_analisis.keys()) if isinstance(datos_analisis, dict) else 'No es dict'}")

                return {
                    "aplica": False,
                    "error": error_msg,
                    "valor_retencion": 0.0,
                    "observaciones": [
                        "Error en estructura de datos del análisis",
                        f"Faltan campos: {', '.join(campos_faltantes)}",
                        "Revise el análisis de Gemini"
                    ],
                    "estado": "Preliquidacion sin finalizar"  # NUEVO: Error en estructura
                }

            # CREAR OBJETO ANALYSISFACTURA MANUALMENTE
            from Clasificador.clasificador import AnalisisFactura, ConceptoIdentificado, NaturalezaTercero

            # Convertir conceptos identificados
            conceptos = []
            conceptos_data = datos_analisis.get("conceptos_identificados", [])

            if not isinstance(conceptos_data, list):
                logger.warning(f"conceptos_identificados no es lista: {type(conceptos_data)}")
                conceptos_data = []

            for concepto_data in conceptos_data:
                if isinstance(concepto_data, dict):
                    concepto_obj = ConceptoIdentificado(
                        concepto=concepto_data.get("concepto", ""),
                        concepto_facturado=concepto_data.get("concepto_facturado", None),
                        base_gravable=concepto_data.get("base_gravable", None),
                        concepto_index=concepto_data.get("concepto_index", None)
                    )
                    conceptos.append(concepto_obj)
                    logger.info(f"Concepto convertido: {concepto_obj.concepto} (index: {concepto_obj.concepto_index})")

            # Convertir naturaleza del tercero
            naturaleza_data = datos_analisis.get("naturaleza_tercero", {})
            if not isinstance(naturaleza_data, dict):
                logger.warning(f"naturaleza_tercero no es dict: {type(naturaleza_data)}")
                naturaleza_data = {}

            naturaleza_obj = NaturalezaTercero(
                es_persona_natural=naturaleza_data.get("es_persona_natural", None),
                regimen_tributario=naturaleza_data.get("regimen_tributario", None),
                es_autorretenedor=naturaleza_data.get("es_autorretenedor", None),
                es_responsable_iva=naturaleza_data.get("es_responsable_iva", None)
            )

            # Crear objeto completo
            analisis_obj = AnalisisFactura(
                conceptos_identificados=conceptos,
                naturaleza_tercero=naturaleza_obj,
                articulo_383=datos_analisis.get("articulo_383", None),
                es_facturacion_exterior=es_facturacion_exterior,  # Usar valor extraído del nivel superior
                valor_total=datos_analisis.get("valor_total", None),
                observaciones=datos_analisis.get("observaciones", [])
            )

            logger.info(f"Objeto AnalisisFactura creado: {len(conceptos)} conceptos, facturación_exterior={analisis_obj.es_facturacion_exterior}")

            # LIQUIDAR CON OBJETO VÁLIDO
            resultado = self.liquidar_factura(analisis_obj, nit_administrativo)

            # CONVERTIR RESULTADO CON NUEVA ESTRUCTURA
            resultado_dict = {
                "aplica": resultado.puede_liquidar,
                "estado": resultado.estado,
                "valor_factura_sin_iva": resultado.valor_factura_sin_iva,
                "valor_retencion": resultado.valor_retencion,
                "base_gravable": resultado.valor_base_retencion,
                "fecha_calculo": resultado.fecha_calculo,
                "observaciones": resultado.mensajes_error,
                "calculo_exitoso": resultado.puede_liquidar,
                # NUEVOS CAMPOS CON ESTRUCTURA MEJORADA:
                "conceptos_aplicados": [concepto.dict() for concepto in resultado.conceptos_aplicados] if resultado.conceptos_aplicados else [],
                "resumen_conceptos": resultado.resumen_conceptos,
                  # NUEVO: Incluir estado en respuesta
            }

            if resultado.puede_liquidar:
                logger.info(f"Retefuente liquidada exitosamente: ${resultado.valor_retencion:,.2f}")
            else:
                logger.warning(f"Retefuente no se pudo liquidar: {resultado.mensajes_error}")

            return resultado_dict

        except ImportError as e:
            error_msg = f"Error importando clases necesarias: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "aplica": False,
                "error": error_msg,
                "valor_retencion": 0.0,
                "observaciones": ["Error importando módulos de análisis", "Revise la configuración del sistema"],
                "estado": "Preliquidacion sin finalizar"  # NUEVO: Error de importación
            }

        except Exception as e:
            error_msg = f"Error liquidando retefuente: {str(e)}"
            logger.error(f"{error_msg}")
            logger.error(f"Tipo de estructura recibida: {type(analisis_retefuente)}")

            # Log adicional para debugging
            if isinstance(analisis_retefuente, dict):
                logger.error(f"Claves disponibles en análisis: {list(analisis_retefuente.keys())}")
                if "analisis" in analisis_retefuente and isinstance(analisis_retefuente["analisis"], dict):
                    logger.error(f"Claves en 'analisis': {list(analisis_retefuente['analisis'].keys())}")

            # Log del traceback completo para debugging
            import traceback
            logger.error(f"Traceback completo: {traceback.format_exc()}")

            return {
                "aplica": False,
                "error": error_msg,
                "valor_retencion": 0.0,
                "observaciones": [
                    "Error en liquidación de retefuente",
                    "Revise estructura de datos",
                    f"Error técnico: {str(e)}"
                ],
                "estado": "Preliquidacion sin finalizar"  # NUEVO: Error general
            }
