"""
LIQUIDADOR DE CONSORCIOS - ARQUITECTURA SOLID
============================================

Módulo especializado para liquidación de retención en la fuente para consorcios,
siguiendo los principios SOLID y separando la lógica de negocio de la extracción de datos.

PRINCIPIOS APLICADOS:
- SRP: Responsabilidad única - solo liquidación de consorcios
- OCP: Abierto para extensión - fácil agregar nuevos tipos de validaciones
- LSP: Sustituible - implementa interfaces comunes
- ISP: Interfaces segregadas - funciones específicas por responsabilidad
- DIP: Inversión de dependencias - depende de abstracciones

Autor: Sistema Preliquidador v3.1.1
Arquitectura: SOLID + Clean Architecture + Validaciones Manuales
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP

# Configuración de logging
logger = logging.getLogger(__name__)


# ===============================
# DATACLASSES PARA ESTRUCTURAS
# ===============================

@dataclass
class ConceptoLiquidado:
    """
    Estructura para concepto liquidado individualmente por consorciado.

    Detalla el resultado de liquidación de un concepto específico para un consorciado.
    """
    nombre_concepto: str
    tarifa_retencion: float
    base_gravable_individual: Decimal
    base_minima_normativa: Decimal
    aplica_concepto: bool
    valor_retencion_concepto: Decimal
    razon_no_aplicacion: Optional[str] = None

@dataclass
class ConsorciadoLiquidado:
    """
    Estructura para consorciado liquidado.

    Encapsula toda la información de liquidación de un consorciado individual.
    """
    nombre: str
    nit: str
    porcentaje_participacion: float
    aplica_retencion: bool
    valor_retencion: Decimal  # Total de todos los conceptos
    valor_base: Decimal
    conceptos_liquidados: List[ConceptoLiquidado]  # NUEVO: Detalle por concepto
    razon_no_aplicacion: Optional[str] = None
    naturaleza_tributaria: Optional[Dict[str, Any]] = None
    # NUEVOS CAMPOS PARA ARTÍCULO 383
    metodo_calculo: Optional[str] = None  # "convencional" o "articulo_383"
    observaciones_art383: Optional[List[str]] = None  # Observaciones específicas del Art 383


@dataclass
class ResultadoLiquidacionConsorcio:
    """
    Estructura para resultado completo de liquidación de consorcio.

    Encapsula el resultado final con todos los consorciados liquidados.
    """
    es_consorcio: bool
    nombre_consorcio: str
    consorciados: List[ConsorciadoLiquidado]
    retencion_total: Decimal
    valor_total_factura: Decimal
    conceptos_aplicados: List[Dict[str, Any]]
    estado_liquidacion: str
    observaciones: List[str]
    procesamiento_exitoso: bool


# ===============================
# INTERFACES Y ABSTRACCIONES
# ===============================

class IValidadorNaturaleza(ABC):
    """
    Interface para validadores de naturaleza tributaria.

    ISP: Interface específica para validación de naturaleza
    """

    @abstractmethod
    def validar_naturaleza_consorcio(self, consorciado: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valida la naturaleza tributaria de un consorciado.

        Args:
            consorciado: Datos del consorciado

        Returns:
            Tuple[bool, str]: (aplica_retencion, razon_no_aplicacion)
        """
        pass


class IValidadorConceptos(ABC):
    """
    Interface para validadores de conceptos.

    ISP: Interface específica para validación de conceptos
    """

    @abstractmethod
    def validar_concepto(self, concepto: str, diccionario_conceptos: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Valida si un concepto existe en el diccionario.

        Args:
            concepto: Nombre del concepto a validar
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            Tuple[bool, Dict]: (es_valido, datos_concepto)
        """
        pass


class ICalculadorRetencion(ABC):
    """
    Interface para calculadores de retención.

    ISP: Interface específica para cálculos
    """

    @abstractmethod
    def calcular_retencion_general(self, datos_liquidacion: Dict[str, Any]) -> Decimal:
        """
        Calcula la retención general del consorcio procesando TODOS los conceptos.

        Args:
            datos_liquidacion: Datos para el cálculo (debe incluir valor_total y conceptos_identificados)

        Returns:
            Decimal: Valor de retención general total (suma de todas las retenciones por concepto)
        """
        pass

    @abstractmethod
    def calcular_retencion_individual(self,
                                    valor_total_factura: Decimal,
                                    porcentaje_participacion: float,
                                    conceptos_validados: List[Dict[str, Any]],
                                    diccionario_conceptos: Dict[str, Any]) -> Tuple[Decimal, List[ConceptoLiquidado]]:
        """
        Calcula la retención individual de un consorciado validando base gravable por concepto.

        Args:
            valor_total_factura: Valor total de la factura
            porcentaje_participacion: Porcentaje de participación del consorciado (0-100)
            conceptos_validados: Lista de conceptos ya validados con sus datos
            diccionario_conceptos: Diccionario de conceptos de config.py con bases mínimas

        Returns:
            Tuple[Decimal, List[ConceptoLiquidado]]: (valor_retencion_total, lista_conceptos_liquidados)
        """
        pass


# ===============================
# IMPLEMENTACIONES CONCRETAS
# ===============================

class ValidadorNaturalezaTributaria(IValidadorNaturaleza):
    """
    Validador concreto para naturaleza tributaria de consorciados.

    SRP: Solo responsable de validar naturaleza tributaria
    """

    def validar_naturaleza_consorcio(self, consorciado: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valida la naturaleza tributaria según las reglas de negocio.

        Reglas:
        - No responsable de IVA: No aplica retención
        - Autorretenedor: No aplica retención
        - Régimen simple: No aplica retención
        - Datos null: Preliquidación sin finalizar
        """
        try:
            naturaleza = consorciado.get('naturaleza_tributaria', {})

            # Validar datos null - datos incompletos
            if self._tiene_datos_null(naturaleza):
                return False, "No se pudo identificar la naturaleza del tercero. Adjuntar RUT o documento soporte."

            # Validar condiciones de no aplicación
            es_responsable_iva = naturaleza.get('es_responsable_iva')
            es_autorretenedor = naturaleza.get('es_autorretenedor', False)
            regimen_tributario = naturaleza.get('regimen_tributario')
            es_persona_natural = naturaleza.get('es_persona_natural', None)

            # Responsable de IVA ya no se valida


            # Autorretenedor
            if es_autorretenedor is True:
                return False, "Autorretenedor"

            # Régimen simple
            if regimen_tributario == "SIMPLE" and es_persona_natural is not True:
                return False, "Régimen simple, y persona no natural"

            # Si pasa todas las validaciones, aplica retención
            return True, ""

        except Exception as e:
            logger.error(f"Error validando naturaleza de consorciado: {e}")
            return False, f"Error en validación: {str(e)}"

    def _tiene_datos_null(self, naturaleza: Dict[str, Any]) -> bool:
        """
        Verifica si hay datos críticos null o faltantes.

        Args:
            naturaleza: Datos de naturaleza tributaria

        Returns:
            bool: True si hay datos null críticos
        """
        campos_criticos = ['es_responsable_iva', 'regimen_tributario']

        for campo in campos_criticos:
            valor = naturaleza.get(campo)
            if valor is None:
                return True

        return False


class ValidadorConceptos(IValidadorConceptos):
    """
    Validador concreto para conceptos de retención.

    SRP: Solo responsable de validar conceptos contra diccionario
    """

    def validar_concepto(self, concepto: str, diccionario_conceptos: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Valida si un concepto existe en el diccionario de conceptos válidos.

        Args:
            concepto: Nombre del concepto a validar
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            Tuple[bool, Dict]: (es_valido, datos_concepto)
        """
        try:
            # Validar concepto no identificado
            if concepto == "CONCEPTO_NO_IDENTIFICADO" or not concepto:
                return False, {}

            # Buscar concepto exacto
            if concepto in diccionario_conceptos:
                return True, diccionario_conceptos[concepto]

            # Buscar concepto con variaciones (sin acentos, mayúsculas, etc.)
            concepto_normalizado = self._normalizar_concepto(concepto)

            for nombre_concepto, datos_concepto in diccionario_conceptos.items():
                if self._normalizar_concepto(nombre_concepto) == concepto_normalizado:
                    return True, datos_concepto

            # No encontrado
            return False, {}

        except Exception as e:
            logger.error(f"Error validando concepto '{concepto}': {e}")
            return False, {}

    def _normalizar_concepto(self, concepto: str) -> str:
        """
        Normaliza un concepto para comparación.

        Args:
            concepto: Concepto a normalizar

        Returns:
            str: Concepto normalizado
        """
        if not concepto:
            return ""

        return concepto.lower().strip().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')


class CalculadorRetencionConsorcio(ICalculadorRetencion):
    """
    Calculador concreto para retenciones de consorcio.

    SRP: Solo responsable de cálculos de retención
    """

    def calcular_retencion_general(self, datos_liquidacion: Dict[str, Any]) -> Decimal:
        """
        Calcula la retención general teórica (solo informativo - real se calcula por consorciado).

        NOTA v3.1.2: Este método ahora es solo informativo.
        La validación de base gravable real se hace por consorciado individual.

        Args:
            datos_liquidacion: Contiene valor_total, conceptos aplicados, etc.

        Returns:
            Decimal: Valor de retención general teórica (sin validación de base mínima)
        """
        try:
            valor_total = Decimal(str(datos_liquidacion.get('valor_total', 0)))
            conceptos = datos_liquidacion.get('conceptos_identificados', [])

            if not conceptos or valor_total <= 0:
                return Decimal('0')

            logger.info(f"📊 Calculando retención general teórica para {len(conceptos)} concepto(s)")

            retencion_total_general = Decimal('0')

            # Procesar TODOS los conceptos (sin validar base mínima a nivel general)
            for concepto in conceptos:
                nombre_concepto = concepto.get('concepto', 'Concepto desconocido')
                tarifa_retencion = Decimal(str(concepto.get('tarifa_retencion', 0))) / 100

                # Calcular retención teórica para este concepto
                retencion_concepto = valor_total * tarifa_retencion
                retencion_total_general += retencion_concepto

                logger.info(f"📈 {nombre_concepto}: ${valor_total:,.2f} × {tarifa_retencion*100}% = ${retencion_concepto:,.2f}")

            # Redondear resultado final a 2 decimales
            retencion_final = retencion_total_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            logger.info(f"💡 Retención general teórica: ${retencion_final:,.2f} (sujeta a validación por consorciado)")

            return retencion_final

        except Exception as e:
            logger.error(f"Error calculando retención general: {e}")
            return Decimal('0')

    def calcular_retencion_individual(self,
                                    valor_total_factura: Decimal,
                                    porcentaje_participacion: float,
                                    conceptos_validados: List[Dict[str, Any]],
                                    diccionario_conceptos: Dict[str, Any]) -> Tuple[Decimal, List[ConceptoLiquidado]]:
        """
        Calcula la retención individual validando base gravable POR CONCEPTO y POR CONSORCIADO.

        NUEVA LÓGICA v3.1.2:
        1. Calcula valor proporcional del consorciado
        2. Por cada concepto, valida si supera base mínima individual
        3. Solo aplica retención para conceptos que superen la base mínima individual

        Args:
            valor_total_factura: Valor total de la factura
            porcentaje_participacion: Porcentaje de participación (0-100)
            conceptos_validados: Lista de conceptos ya validados
            diccionario_conceptos: Diccionario de conceptos de config.py con bases mínimas

        Returns:
            Tuple[Decimal, List[ConceptoLiquidado]]: (valor_retencion_total, conceptos_liquidados)
        """
        try:
            if valor_total_factura <= 0 or porcentaje_participacion <= 0:
                return Decimal('0'), []

            # Convertir porcentaje a decimal
            porcentaje_decimal = Decimal(str(porcentaje_participacion)) / 100
            valor_individual = valor_total_factura * porcentaje_decimal

            logger.info(f" Valor individual consorciado ({porcentaje_participacion}%): ${valor_individual:,.2f}")

            retencion_total_individual = Decimal('0')
            conceptos_liquidados = []

            # Validar CADA concepto individualmente
            for concepto in conceptos_validados:
                nombre_concepto = concepto.get('concepto', 'Concepto desconocido')
                tarifa_retencion_pct = concepto.get('tarifa_retencion', 0)
                # DETECCIÓN AUTOMÁTICA DE FORMATO: decimal (0.11) vs porcentaje (11)
                if tarifa_retencion_pct <= 1.0:
                    # Ya está en formato decimal (0.11 = 11%)
                    tarifa_retencion = Decimal(str(tarifa_retencion_pct))
                    tarifa_display = tarifa_retencion_pct * 100  # Para mostrar en logs
                else:
                    # Está en formato porcentaje (11 = 11%)
                    tarifa_retencion = Decimal(str(tarifa_retencion_pct)) / 100
                    tarifa_display = tarifa_retencion_pct

                # BASE GRAVABLE DE LA FACTURA (extraída por Gemini por este concepto)
                base_gravable_factura = Decimal(str(concepto.get('base_gravable', 0)))

                # BASE MÍNIMA DEL DICCIONARIO (normativa por este concepto desde config.py)
                nombre_concepto_dict = concepto.get('concepto', '')
                logger.debug(f"🔍 DEBUG: Buscando concepto '{nombre_concepto_dict}' en diccionario")
                logger.debug(f"🔍 DEBUG: Concepto completo de Gemini: {concepto}")

                # Buscar en el diccionario de conceptos la base mínima normativa
                base_minima_diccionario = self._obtener_base_minima_del_diccionario(nombre_concepto_dict, diccionario_conceptos)

                # Calcular base gravable individual del consorciado
                base_gravable_individual = base_gravable_factura * porcentaje_decimal

                # VALIDACIÓN CRÍTICA: Base gravable individual vs base mínima normativa
                if base_gravable_individual < base_minima_diccionario:
                    # No aplica este concepto
                    concepto_liquidado = ConceptoLiquidado(
                        nombre_concepto=nombre_concepto,
                        tarifa_retencion=float(tarifa_retencion),  # Guardar en formato decimal para cálculos
                        base_gravable_individual=base_gravable_individual,
                        base_minima_normativa=base_minima_diccionario,
                        aplica_concepto=False,
                        valor_retencion_concepto=Decimal('0'),
                        razon_no_aplicacion=f"Base individual ${base_gravable_individual:,.2f} < Base mínima ${base_minima_diccionario:,.2f}"
                    )
                    logger.info(f"❌ {nombre_concepto}: {concepto_liquidado.razon_no_aplicacion}")
                else:
                    # Calcular retención para este concepto sobre la base gravable individual
                    retencion_concepto = base_gravable_individual * tarifa_retencion
                    retencion_total_individual += retencion_concepto

                    concepto_liquidado = ConceptoLiquidado(
                        nombre_concepto=nombre_concepto,
                        tarifa_retencion=float(tarifa_retencion),  # Guardar en formato decimal para cálculos
                        base_gravable_individual=base_gravable_individual,
                        base_minima_normativa=base_minima_diccionario,
                        aplica_concepto=True,
                        valor_retencion_concepto=retencion_concepto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    )
                    logger.info(f"✅ {nombre_concepto}: Base ${base_gravable_individual:,.2f} × {tarifa_display}% = ${concepto_liquidado.valor_retencion_concepto:,.2f}")

                conceptos_liquidados.append(concepto_liquidado)

            # Redondear resultado final
            retencion_final = retencion_total_individual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if retencion_final > 0:
                logger.info(f"🎯 Retención individual total: ${retencion_final:,.2f}")
            else:
                logger.info("❌ Sin retención individual - ningún concepto superó base mínima")

            return retencion_final, conceptos_liquidados

        except Exception as e:
            logger.error(f"Error calculando retención individual: {e}")
            return Decimal('0'), []

    def _obtener_base_minima_del_diccionario(self, nombre_concepto: str, diccionario_conceptos: Dict[str, Any]) -> Decimal:
        """
        Obtiene la base mínima normativa del diccionario de conceptos de config.py.

        Args:
            nombre_concepto: Nombre del concepto a buscar
            diccionario_conceptos: Diccionario de conceptos de config.py

        Returns:
            Decimal: Base mínima normativa para el concepto
        """
        try:
            if not nombre_concepto or not diccionario_conceptos:
                return Decimal('0')

            # Buscar concepto en el diccionario
            logger.debug(f"🔍 DEBUG: Buscando '{nombre_concepto}' en {len(diccionario_conceptos)} conceptos")
            logger.debug(f"🔍 DEBUG: Conceptos disponibles: {list(diccionario_conceptos.keys())[:5]}...")

            datos_concepto = diccionario_conceptos.get(nombre_concepto, {})

            if not datos_concepto:
                logger.warning(f"Concepto '{nombre_concepto}' no encontrado en diccionario")
                # Intentar búsqueda similar
                for concepto_disponible in diccionario_conceptos.keys():
                    if nombre_concepto.lower() in concepto_disponible.lower():
                        logger.info(f"💡 Concepto similar encontrado: '{concepto_disponible}'")
                        break
                return Decimal('0')

            # Buscar base mínima (puede estar como 'base_pesos', 'base_minima', 'uvt_minima', etc.)
            base_minima = datos_concepto.get('base_pesos',
                         datos_concepto.get('base_minima',
                         datos_concepto.get('uvt_minima',
                         datos_concepto.get('base_gravable', 0))))

            base_decimal = Decimal(str(base_minima))
            logger.debug(f"✅ Base mínima para '{nombre_concepto}': ${base_decimal:,.2f}")
            logger.debug(f"🔍 DEBUG: Datos completos del concepto: {datos_concepto}")

            return base_decimal

        except Exception as e:
            logger.error(f"Error obteniendo base mínima para '{nombre_concepto}': {e}")
            return Decimal('0')


# ===============================
# LIQUIDADOR PRINCIPAL
# ===============================

class LiquidadorConsorcios:
    """
    Liquidador principal para consorcios siguiendo principios SOLID.

    PRINCIPIOS APLICADOS:
    - SRP: Solo coordina liquidación de consorcios
    - DIP: Depende de abstracciones (interfaces)
    - OCP: Extensible mediante inyección de nuevos validadores/calculadores
    """

    def __init__(self,
                 validador_naturaleza: Optional[IValidadorNaturaleza] = None,
                 validador_conceptos: Optional[IValidadorConceptos] = None,
                 calculador_retencion: Optional[ICalculadorRetencion] = None):
        """
        Inicializa el liquidador con inyección de dependencias.

        Args:
            validador_naturaleza: Validador de naturaleza tributaria
            validador_conceptos: Validador de conceptos
            calculador_retencion: Calculador de retenciones
        """
        # DIP: Inyección de dependencias con valores por defecto
        self.validador_naturaleza = validador_naturaleza or ValidadorNaturalezaTributaria()
        self.validador_conceptos = validador_conceptos or ValidadorConceptos()
        self.calculador_retencion = calculador_retencion or CalculadorRetencionConsorcio()

        logger.info("LiquidadorConsorcios inicializado con arquitectura SOLID")

    async def liquidar_consorcio(self,
                                analisis_gemini: Dict[str, Any],
                                diccionario_conceptos: Dict[str, Any],
                                archivos_directos: List = None,
                                cache_archivos: Dict[str, bytes] = None) -> ResultadoLiquidacionConsorcio:
        """
        Liquida un consorcio completo aplicando validaciones manuales y cálculos.

        FLUJO SOLID:
        1. Validar estructura del análisis
        2. Validar conceptos identificados
        3. Validar naturaleza de cada consorciado
        4. Calcular retención general
        5. Calcular retenciones individuales
        6. Generar resultado estructurado

        Args:
            analisis_gemini: Resultado del análisis de Gemini (solo extracción)
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            ResultadoLiquidacionConsorcio: Resultado completo de liquidación
        """
        logger.info(" Iniciando liquidación de consorcio con validaciones manuales")

        try:
            # PASO 1: Validar estructura básica
            if not self._validar_estructura_consorcio(analisis_gemini):
                return self._crear_resultado_error("Estructura de consorcio inválida")

            # PASO 2: Validar conceptos identificados
            conceptos_validos, mensaje_concepto = self._validar_conceptos_consorcio(
                analisis_gemini.get('conceptos_identificados', []),
                diccionario_conceptos
            )

            if not conceptos_validos:
                return self._crear_resultado_sin_finalizar(mensaje_concepto)

            # PASO 3: Validar y liquidar consorciados individuales
            consorciados_liquidados = []
            observaciones = []

            for consorciado in analisis_gemini.get('consorciados', []):
                consorciado_liquidado = self._liquidar_consorciado_individual(
                    consorciado, conceptos_validos, analisis_gemini, diccionario_conceptos
                )
                consorciados_liquidados.append(consorciado_liquidado)

                if not consorciado_liquidado.aplica_retencion and consorciado_liquidado.razon_no_aplicacion:
                    observaciones.append(f"{consorciado_liquidado.nombre}: {consorciado_liquidado.razon_no_aplicacion}")

            # PASO 3.5: ANÁLISIS ARTÍCULO 383 PARA PERSONAS NATURALES
            consorciados_liquidados = await self._procesar_articulo_383_consorciados(
                consorciados_liquidados, analisis_gemini, observaciones, archivos_directos, cache_archivos
            )

            # PASO 4: Calcular totales
            retencion_total = sum(c.valor_retencion for c in consorciados_liquidados)
            valor_total = Decimal(str(analisis_gemini.get('valor_total', 0)))

            # PASO 5: Generar resultado final
            return ResultadoLiquidacionConsorcio(
                es_consorcio=True,
                nombre_consorcio=analisis_gemini.get('nombre_consorcio', ''),
                consorciados=consorciados_liquidados,
                retencion_total=retencion_total,
                valor_total_factura=valor_total,
                conceptos_aplicados=conceptos_validos,
                estado_liquidacion="Preliquidado",
                observaciones=observaciones,
                procesamiento_exitoso=True
            )

        except Exception as e:
            logger.error(f"Error en liquidación de consorcio: {e}")
            return self._crear_resultado_error(f"Error en liquidación: {str(e)}")

    def _validar_estructura_consorcio(self, analisis: Dict[str, Any]) -> bool:
        """
        Valida que el análisis tenga la estructura mínima requerida.

        Args:
            analisis: Análisis de Gemini

        Returns:
            bool: True si la estructura es válida
        """
        campos_requeridos = ['es_consorcio', 'consorciados', 'conceptos_identificados']

        for campo in campos_requeridos:
            if campo not in analisis:
                logger.error(f"Campo requerido faltante: {campo}")
                return False

        if not analisis.get('es_consorcio', False):
            logger.error("El análisis no corresponde a un consorcio")
            return False

        if not analisis.get('consorciados'):
            logger.error("No hay consorciados en el análisis")
            return False

        return True

    def _validar_conceptos_consorcio(self,
                                   conceptos_identificados: List[Dict[str, Any]],
                                   diccionario_conceptos: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        """
        Valida los conceptos identificados contra el diccionario.

        Args:
            conceptos_identificados: Conceptos identificados por Gemini
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            Tuple[List[Dict], str]: (conceptos_validos, mensaje_error)
        """
        conceptos_validos = []

        for concepto_data in conceptos_identificados:
            concepto_nombre = concepto_data.get('concepto', '')

            es_valido, datos_concepto = self.validador_conceptos.validar_concepto(
                concepto_nombre, diccionario_conceptos
            )

            if not es_valido:
                mensaje_error = "El concepto facturado no se identifica en los soportes adjuntos. Validar soportes."
                logger.warning(f"Concepto no válido: {concepto_nombre}")
                return [], mensaje_error

            # Combinar datos de Gemini con datos del diccionario
            concepto_completo = {
                **concepto_data,
                **datos_concepto
            }
            conceptos_validos.append(concepto_completo)

        return conceptos_validos, ""

    def _liquidar_consorciado_individual(self,
                                       consorciado: Dict[str, Any],
                                       conceptos_validos: List[Dict[str, Any]],
                                       analisis_general: Dict[str, Any],
                                       diccionario_conceptos: Dict[str, Any]) -> ConsorciadoLiquidado:
        """
        Liquida un consorciado individual aplicando todas las validaciones.

        Args:
            consorciado: Datos del consorciado
            conceptos_validos: Conceptos ya validados
            analisis_general: Análisis general del consorcio
            diccionario_conceptos: Diccionario de conceptos de config.py

        Returns:
            ConsorciadoLiquidado: Consorciado liquidado
        """
        nombre = consorciado.get('nombre', '')
        nit = consorciado.get('nit', '')
        porcentaje = float(consorciado.get('porcentaje_participacion', 0))

        # Validar naturaleza tributaria
        aplica_retencion, razon_no_aplicacion = self.validador_naturaleza.validar_naturaleza_consorcio(consorciado)

        if not aplica_retencion:
            # No aplica retención por naturaleza
            return ConsorciadoLiquidado(
                nombre=nombre,
                nit=nit,
                porcentaje_participacion=porcentaje,
                aplica_retencion=False,
                valor_retencion=Decimal('0'),
                valor_base=Decimal('0'),
                conceptos_liquidados=[],
                razon_no_aplicacion=razon_no_aplicacion,
                naturaleza_tributaria=consorciado.get('naturaleza_tributaria')
            )

        # Calcular valor base individual
        valor_total = Decimal(str(analisis_general.get('valor_total', 0)))
        valor_base_individual = valor_total * (Decimal(str(porcentaje)) / 100)

        # NUEVA LÓGICA v3.1.2: Calcular retención individual con validación de base gravable
        retencion_individual, conceptos_liquidados = self.calculador_retencion.calcular_retencion_individual(
            valor_total, porcentaje, conceptos_validos, diccionario_conceptos
        )

        return ConsorciadoLiquidado(
            nombre=nombre,
            nit=nit,
            porcentaje_participacion=porcentaje,
            aplica_retencion=retencion_individual > 0,
            valor_retencion=retencion_individual,
            valor_base=valor_base_individual,
            conceptos_liquidados=conceptos_liquidados,
            naturaleza_tributaria=consorciado.get('naturaleza_tributaria')
        )

    def _crear_resultado_error(self, mensaje: str) -> ResultadoLiquidacionConsorcio:
        """
        Crea un resultado de error.

        Args:
            mensaje: Mensaje de error

        Returns:
            ResultadoLiquidacionConsorcio: Resultado con error
        """
        return ResultadoLiquidacionConsorcio(
            es_consorcio=False,
            nombre_consorcio="",
            consorciados=[],
            retencion_total=Decimal('0'),
            valor_total_factura=Decimal('0'),
            conceptos_aplicados=[],
            estado_liquidacion="Error",
            observaciones=[mensaje],
            procesamiento_exitoso=False
        )

    def _crear_resultado_sin_finalizar(self, mensaje: str) -> ResultadoLiquidacionConsorcio:
        """
        Crea un resultado de preliquidación sin finalizar.

        Args:
            mensaje: Mensaje explicativo

        Returns:
            ResultadoLiquidacionConsorcio: Resultado sin finalizar
        """
        return ResultadoLiquidacionConsorcio(
            es_consorcio=True,
            nombre_consorcio="",
            consorciados=[],
            retencion_total=Decimal('0'),
            valor_total_factura=Decimal('0'),
            conceptos_aplicados=[],
            estado_liquidacion="Preliquidación sin finalizar",
            observaciones=[mensaje],
            procesamiento_exitoso=False
        )

    # ===============================
    # ARTÍCULO 383 PARA CONSORCIADOS
    # ===============================

    def _detectar_consorciados_persona_natural(self, consorciados_liquidados: List[ConsorciadoLiquidado]) -> List[Dict]:
        """
        Detecta consorciados que son personas naturales para análisis Art 383.

        Args:
            consorciados_liquidados: Lista de consorciados ya liquidados

        Returns:
            List[Dict]: Lista de consorciados persona natural con su información
        """
        personas_naturales = []

        for consorciado in consorciados_liquidados:
            if (consorciado.aplica_retencion and
                hasattr(consorciado, 'naturaleza_tributaria') and
                consorciado.naturaleza_tributaria and
                consorciado.naturaleza_tributaria.get('es_persona_natural') == True):

                # Convertir conceptos liquidados a diccionarios
                conceptos_dict = []
                for concepto in consorciado.conceptos_liquidados:
                    conceptos_dict.append({
                        'nombre_concepto': concepto.nombre_concepto,
                        'tarifa_retencion': concepto.tarifa_retencion,
                        'base_gravable_individual': float(concepto.base_gravable_individual),
                        'valor_retencion_concepto': float(concepto.valor_retencion_concepto),
                        'aplica_concepto': concepto.aplica_concepto
                    })

                personas_naturales.append({
                    'nombre': consorciado.nombre,
                    'nit': consorciado.nit,
                    'porcentaje_participacion': float(consorciado.porcentaje_participacion),
                    'conceptos_liquidados': conceptos_dict,
                    'valor_base': float(consorciado.valor_base)
                })

                logger.info(f"🧑‍🎨 Detectada persona natural para Art 383: {consorciado.nombre} ({consorciado.nit})")

        if personas_naturales:
            logger.info(f"✅ Total personas naturales detectadas: {len(personas_naturales)}")
        else:
            logger.info("ℹ️ No se detectaron personas naturales en el consorcio")

        return personas_naturales

    async def _analizar_articulo_383_consorciados(self, personas_naturales: List[Dict],
                                                 documentos_clasificados: Dict,
                                                 archivos_directos: List = None,
                                                 cache_archivos: Dict[str, bytes] = None) -> Dict:
        """
        Análisis separado del Artículo 383 para personas naturales en consorcios.

        Args:
            personas_naturales: Lista de consorciados persona natural
            documentos_clasificados: Documentos clasificados del consorcio
            archivos_directos: Archivos directos para Gemini

        Returns:
            Dict: Resultado del análisis de Gemini para Art 383
        """
        logger.info(f" Iniciando análisis Art 383 para {len(personas_naturales)} personas naturales")

        try:
            # Importar clasificador y prompt
            from Clasificador.clasificador import ProcesadorGemini
            from Clasificador.prompt_clasificador import PROMPT_ANALISIS_ART_383_CONSORCIADOS

            clasificador = ProcesadorGemini()

            # USAR CACHE SI ESTÁ DISPONIBLE (misma lógica que analizar_consorcio)
            archivos_directos = archivos_directos or []
            if cache_archivos:
                logger.info(f"🗂️ Art 383 consorciados usando caché de archivos: {len(cache_archivos)} archivos")
                archivos_directos = clasificador._obtener_archivos_clonados_desde_cache(cache_archivos)
            elif archivos_directos:
                logger.info(f"📁 Art 383 consorciados usando archivos directos originales: {len(archivos_directos)} archivos")

            # Extraer textos de documentos clasificados
            factura_texto = documentos_clasificados.get("FACTURA PRINCIPAL", {}).get("texto", "")
            rut_texto = documentos_clasificados.get("RUT", {}).get("texto", "")
            anexos_texto = documentos_clasificados.get("ANEXOS", {}).get("texto", "")
            cotizaciones_texto = documentos_clasificados.get("COTIZACIONES", {}).get("texto", "")
            anexo_contrato = documentos_clasificados.get("ANEXO CONTRATO", {}).get("texto", "")

            # Crear lista de nombres de archivos directos
            nombres_archivos_directos = []
            if archivos_directos:
                for archivo in archivos_directos:
                    try:
                        nombres_archivos_directos.append(archivo.filename)
                    except:
                        nombres_archivos_directos.append(f"archivo_directo_{len(nombres_archivos_directos) + 1}")

            # Generar prompt específico para consorciados Art 383
            prompt = PROMPT_ANALISIS_ART_383_CONSORCIADOS(
                consorciados_persona_natural=personas_naturales,
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nombres_archivos_directos=nombres_archivos_directos
            )

            logger.info(" Llamando a Gemini para análisis Art 383 de consorciados")

            # Llamar a Gemini (usar híbrido si hay archivos)
            if archivos_directos and len(archivos_directos) > 0:
                respuesta = await clasificador._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            else:
                respuesta = await clasificador._llamar_gemini(prompt)

            logger.info(f" Respuesta Art 383 consorciados recibida: {len(respuesta):,} caracteres")

            # Limpiar y parsear respuesta
            respuesta_limpia = clasificador._limpiar_respuesta_json(respuesta)

            # Parsear JSON con auto-reparación
            try:
                resultado = json.loads(respuesta_limpia)
            except json.JSONDecodeError as first_error:
                logger.warning(f"JSON malformado en Art 383 consorciados, intentando reparar: {first_error}")
                respuesta_reparada = clasificador._reparar_json_malformado(respuesta_limpia)
                resultado = json.loads(respuesta_reparada)

            # Guardar respuesta para debugging
            await clasificador._guardar_respuesta("analisis_art383_consorciados.json", resultado)

            logger.info(f" Análisis Art 383 consorciados completado: {len(resultado.get('consorciados_art383', []))} analizados")

            return resultado

        except Exception as e:
            logger.error(f"💥 Error en análisis Art 383 consorciados: {e}")
            return {
                "consorciados_art383": [],
                "error": str(e),
                "observaciones": ["Error procesando Artículo 383 para consorciados"]
            }

    def _calcular_retencion_articulo_383_consorciado(self, datos_art383_gemini: Dict, consorciado_base: Dict) -> Dict:
        """
        Calcula retención Art 383 para un consorciado específico reutilizando funciones existentes.

        Args:
            datos_art383_gemini: Datos extraídos por Gemini para este consorciado
            consorciado_base: Información base del consorciado

        Returns:
            Dict: Resultado del cálculo Art 383
        """
        logger.info(f"🧮 Calculando Art 383 para {consorciado_base.get('nombre', 'Desconocido')}")

        try:
            # Importar modelos y liquidador existente
            from Liquidador.liquidador import (
                LiquidadorRetencion, AnalisisFactura, InformacionArticulo383,
                CondicionesArticulo383, DeduccionesArticulo383, InteresesVivienda,
                DependientesEconomicos, MedicinaPrepagada, AFCInfo, PlanillaSeguridadSocial,
                ConceptoIdentificadoArt383
            )

            # Extraer datos de Gemini
            condiciones_data = datos_art383_gemini.get('condiciones_cumplidas', {})
            deducciones_data = datos_art383_gemini.get('deducciones_identificadas', {})

            # Crear estructura de conceptos identificados
            conceptos_identificados_art383 = []
            for concepto_data in condiciones_data.get('conceptos_identificados', []):
                conceptos_identificados_art383.append(ConceptoIdentificadoArt383(
                    concepto=concepto_data.get('concepto', ''),
                    base_gravable=concepto_data.get('base_gravable', 0.0)
                ))

            # Crear condiciones cumplidas
            condiciones = CondicionesArticulo383(
                es_persona_natural=condiciones_data.get('es_persona_natural', False),
                conceptos_identificados=conceptos_identificados_art383,
                conceptos_aplicables=condiciones_data.get('conceptos_aplicables', False),
                ingreso=condiciones_data.get('ingreso', 0.0),
                es_primer_pago=condiciones_data.get('es_primer_pago', False),
                documento_soporte=condiciones_data.get('documento_soporte', False)
            )

            # Crear estructuras de deducciones
            intereses_data = deducciones_data.get('intereses_vivienda', {})
            dependientes_data = deducciones_data.get('dependientes_economicos', {})
            medicina_data = deducciones_data.get('medicina_prepagada', {})
            afc_data = deducciones_data.get('AFC', {})
            planilla_data = deducciones_data.get('planilla_seguridad_social', {})

            deducciones = DeduccionesArticulo383(
                intereses_vivienda=InteresesVivienda(
                    intereses_corrientes=intereses_data.get('intereses_corrientes', 0.0),
                    certificado_bancario=intereses_data.get('certificado_bancario', False)
                ),
                dependientes_economicos=DependientesEconomicos(
                    nombre_encargado=dependientes_data.get('nombre_encargado', ''),
                    declaracion_juramentada=dependientes_data.get('declaracion_juramentada', False)
                ),
                medicina_prepagada=MedicinaPrepagada(
                    valor_sin_iva_med_prepagada=medicina_data.get('valor_sin_iva_med_prepagada', 0.0),
                    certificado_med_prepagada=medicina_data.get('certificado_med_prepagada', False)
                ),
                AFC=AFCInfo(
                    valor_a_depositar=afc_data.get('valor_a_depositar', 0.0),
                    planilla_de_cuenta_AFC=afc_data.get('planilla_de_cuenta_AFC', False)
                ),
                planilla_seguridad_social=PlanillaSeguridadSocial(
                    IBC_seguridad_social=planilla_data.get('IBC_seguridad_social', 0.0),
                    planilla_seguridad_social=planilla_data.get('planilla_seguridad_social', False),
                    fecha_de_planilla_seguridad_social=planilla_data.get('fecha_de_planilla_seguridad_social', '0000-00-00')
                )
            )

            # Crear información completa del Art 383
            info_art383 = InformacionArticulo383(
                condiciones_cumplidas=condiciones,
                deducciones_identificadas=deducciones
            )

            # Crear AnalisisFactura mock para reutilizar función existente
            analisis_mock = AnalisisFactura(
                aplica_retencion=True,
                conceptos_identificados=[],  # Los conceptos ya están en info_art383
                naturaleza_tercero=None,
                articulo_383=info_art383,
                es_facturacion_exterior=False,
                valor_total=consorciado_base.get('valor_base', 0.0),
                iva=0.0,
                observaciones=[]
            )

            # ¡¡¡REUTILIZAR FUNCIÓN EXISTENTE CON MISMA LÓGICA!!!
            liquidador = LiquidadorRetencion()
            resultado = liquidador._calcular_retencion_articulo_383_separado(analisis_mock)

            logger.info(f"✅ Art 383 calculado para {consorciado_base.get('nombre', 'Desconocido')}: aplica={resultado.get('puede_liquidar', False)}")

            return resultado

        except Exception as e:
            logger.error(f"💥 Error calculando Art 383 para consorciado: {e}")
            return {
                "puede_liquidar": False,
                "mensajes_error": [f"Error en cálculo Art 383: {str(e)}"]
            }

    def _actualizar_consorciado_con_art383(self, consorciado_original: ConsorciadoLiquidado,
                                          resultado_art383: Any) -> ConsorciadoLiquidado:
        """
        Actualiza un consorciado con los resultados del Art 383.

        Args:
            consorciado_original: Consorciado original
            resultado_art383: Resultado del cálculo Art 383

        Returns:
            ConsorciadoLiquidado: Consorciado actualizado con Art 383
        """
        # Actualizar el valor de retención con el resultado del Art 383
        consorciado_actualizado = ConsorciadoLiquidado(
            nombre=consorciado_original.nombre,
            nit=consorciado_original.nit,
            porcentaje_participacion=consorciado_original.porcentaje_participacion,
            aplica_retencion=True,  # Art 383 aplicado
            valor_retencion=resultado_art383.valor_retencion,  # Nuevo valor Art 383
            valor_base=resultado_art383.valor_base_retencion,  # Nueva base Art 383
            razon_no_aplicacion=None,
            conceptos_liquidados=consorciado_original.conceptos_liquidados,  # Mantener conceptos originales
            naturaleza_tributaria=consorciado_original.naturaleza_tributaria,
            metodo_calculo="articulo_383",  # Identificar que se usó Art 383
            observaciones_art383=resultado_art383.mensajes_error  # Agregar observaciones Art 383
        )

        logger.info(f"🔄 Consorciado actualizado con Art 383: {consorciado_original.nombre} - ${float(resultado_art383.valor_retencion):,.2f}")

        return consorciado_actualizado

    async def _procesar_articulo_383_consorciados(self, consorciados_liquidados: List[ConsorciadoLiquidado],
                                                 analisis_gemini: Dict[str, Any],
                                                 observaciones: List[str],
                                                 archivos_directos: List = None,
                                                 cache_archivos: Dict[str, bytes] = None) -> List[ConsorciadoLiquidado]:
        """
        Procesa Artículo 383 para todos los consorciados que sean personas naturales.

        Args:
            consorciados_liquidados: Lista de consorciados ya liquidados
            analisis_gemini: Análisis original de Gemini
            observaciones: Lista de observaciones para agregar

        Returns:
            List[ConsorciadoLiquidado]: Lista actualizada con Art 383 aplicado donde corresponda
        """
        logger.info(" Iniciando procesamiento Art 383 para consorciados...")

        try:
            # PASO 1: Detectar personas naturales
            personas_naturales = self._detectar_consorciados_persona_natural(consorciados_liquidados)

            if not personas_naturales:
                logger.info("ℹ️ No hay personas naturales para análisis Art 383")
                return consorciados_liquidados

            # PASO 2: Extraer documentos clasificados del análisis original
            # Esto puede necesitar ajuste según la estructura de analisis_gemini
            documentos_clasificados = {
                "FACTURA PRINCIPAL": {"texto": ""},  # Se podría extraer del cache si está disponible
                "RUT": {"texto": ""},
                "ANEXOS": {"texto": ""},
                "COTIZACIONES": {"texto": ""},
                "ANEXO CONTRATO": {"texto": ""}
            }

            # PASO 3: Análizar Art 383 con Gemini
            logger.info(f" Solicitando análisis Art 383 para {len(personas_naturales)} personas naturales")

            resultado_art383 = await self._analizar_articulo_383_consorciados(
                personas_naturales, documentos_clasificados, archivos_directos=archivos_directos, cache_archivos=cache_archivos
            )

            if "error" in resultado_art383:
                logger.warning(f"⚠️ Error en análisis Art 383: {resultado_art383['error']}")
                observaciones.append("Error procesando Art 383 - aplicando tarifas convencionales")
                return consorciados_liquidados

            # PASO 4: Iterar sobre respuesta de Gemini y aplicar cálculos
            consorciados_art383 = resultado_art383.get('consorciados_art383', [])
            logger.info(f" Procesando cálculos Art 383 para {len(consorciados_art383)} consorciados")

            consorciados_actualizados = consorciados_liquidados.copy()

            for consorciado_art383 in consorciados_art383:
                nit_consorciado = consorciado_art383.get('nit', '')
                nombre_consorciado = consorciado_art383.get('nombre', 'Desconocido')

                # Encontrar el consorciado en la lista original
                indice_consorciado = None
                for i, consorciado in enumerate(consorciados_actualizados):
                    if consorciado.nit == nit_consorciado:
                        indice_consorciado = i
                        break

                if indice_consorciado is None:
                    logger.warning(f" No se encontró consorciado con NIT {nit_consorciado}")
                    continue

                # Extraer datos Art 383 de la respuesta de Gemini
                datos_art383_gemini = consorciado_art383.get('articulo_383', {})

                if not datos_art383_gemini:
                    logger.warning(f"⚠️ No hay datos Art 383 para {nombre_consorciado}")
                    continue

                # Preparar datos base del consorciado
                consorciado_original = consorciados_actualizados[indice_consorciado]
                consorciado_base = {
                    'nombre': consorciado_original.nombre,
                    'nit': consorciado_original.nit,
                    'valor_base': float(consorciado_original.valor_base),
                    'porcentaje_participacion': consorciado_original.porcentaje_participacion
                }

                # Calcular Art 383 para este consorciado
                logger.info(f"🧮 Calculando Art 383 para {nombre_consorciado}...")
                resultado_calculo = self._calcular_retencion_articulo_383_consorciado(
                    datos_art383_gemini, consorciado_base
                )

                if resultado_calculo.get('puede_liquidar', False):
                    # Aplicar Art 383 al consorciado
                    consorciado_actualizado = self._actualizar_consorciado_con_art383(
                        consorciado_original, resultado_calculo['resultado']
                    )
                    consorciados_actualizados[indice_consorciado] = consorciado_actualizado

                    logger.info(f"✅ Art 383 aplicado a {nombre_consorciado}: ${float(resultado_calculo['resultado'].valor_retencion):,.2f}")
                    observaciones.append(f"Art 383 aplicado a {nombre_consorciado} (tarifa progresiva)")

                else:
                    # Art 383 no aplica, mantener cálculo convencional
                    logger.info(f"❌ Art 383 no aplica a {nombre_consorciado}: {resultado_calculo.get('mensajes_error', ['Error desconocido'])[0]}")
                    observaciones.append(f"Art 383 no aplica a {nombre_consorciado} - tarifa convencional mantenida")

            logger.info(f"✅ Procesamiento Art 383 completado para {len(personas_naturales)} personas naturales")
            return consorciados_actualizados

        except Exception as e:
            logger.error(f"💥 Error procesando Art 383 para consorciados: {e}")
            observaciones.append(f"Error procesando Art 383: {str(e)} - aplicando tarifas convencionales")
            return consorciados_liquidados


# ===============================
# FUNCIONES DE UTILIDAD
# ===============================

def convertir_resultado_a_dict(resultado: ResultadoLiquidacionConsorcio) -> Dict[str, Any]:
    """
    Convierte el resultado de liquidación a diccionario para serialización.

    Args:
        resultado: Resultado de liquidación

    Returns:
        Dict: Resultado como diccionario
    """
    consorciados_dict = []

    for consorciado in resultado.consorciados:
        consorciado_dict = {
            "nombre": consorciado.nombre,
            "nit": consorciado.nit,
            "porcentaje_participacion": consorciado.porcentaje_participacion,
            "aplica": consorciado.aplica_retencion,
            "valor_retencion": float(consorciado.valor_retencion),
            "valor_base": float(consorciado.valor_base)
        }

        if consorciado.razon_no_aplicacion:
            consorciado_dict["razon_no_aplicacion"] = consorciado.razon_no_aplicacion

        # NUEVO v3.1.2: Incluir detalle completo de conceptos liquidados por consorciado
        conceptos_detalle = []
        for concepto_liq in consorciado.conceptos_liquidados:
            concepto_detalle = {
                "nombre_concepto": concepto_liq.nombre_concepto,
                "tarifa_retencion": concepto_liq.tarifa_retencion,
                "base_gravable_individual": float(concepto_liq.base_gravable_individual),
                "base_minima_normativa": float(concepto_liq.base_minima_normativa),
                "aplica_concepto": concepto_liq.aplica_concepto,
                "valor_retencion_concepto": float(concepto_liq.valor_retencion_concepto)
            }
            if concepto_liq.razon_no_aplicacion:
                concepto_detalle["razon_no_aplicacion"] = concepto_liq.razon_no_aplicacion

            conceptos_detalle.append(concepto_detalle)

        consorciado_dict["conceptos_liquidados"] = conceptos_detalle

        # NUEVO: Incluir información del Artículo 383 si aplica
        if hasattr(consorciado, 'metodo_calculo') and consorciado.metodo_calculo:
            consorciado_dict["metodo_calculo"] = consorciado.metodo_calculo

        if hasattr(consorciado, 'observaciones_art383') and consorciado.observaciones_art383:
            consorciado_dict["observaciones_art383"] = consorciado.observaciones_art383

        consorciados_dict.append(consorciado_dict)

    # Formatear conceptos aplicados con información detallada
    conceptos_dict = []
    for concepto in resultado.conceptos_aplicados:
        concepto_dict = {
            "concepto": concepto.get('concepto', ''),
            "tarifa_retencion": concepto.get('tarifa_retencion', 0),
            "base_gravable": concepto.get('base_gravable', 0)
        }
        conceptos_dict.append(concepto_dict)

    return {
        "retefuente": {
            "es_consorcio": resultado.es_consorcio,
            "nombre_consorcio": resultado.nombre_consorcio,
            "consorciados": consorciados_dict,
            "retencion_total": float(resultado.retencion_total),
            "valor_total_factura": float(resultado.valor_total_factura),
            "conceptos_aplicados": conceptos_dict,
            "resumen_conceptos": ", ".join([f"{c.get('concepto', '')} ({c.get('tarifa_retencion', 0)}%)" for c in resultado.conceptos_aplicados]) if resultado.conceptos_aplicados else "Sin conceptos",
            "estado_liquidacion": resultado.estado_liquidacion,
            "observaciones": resultado.observaciones,
            "procesamiento_exitoso": resultado.procesamiento_exitoso,
            "arquitectura": "SOLID + Validaciones Manuales v3.1.2 - Detalle por Concepto"
        }
    }


# ===============================
# FACTORY PARA CREACIÓN
# ===============================

class LiquidadorConsorciosFactory:
    """
    Factory para crear instancias de LiquidadorConsorcios.

    PRINCIPIOS APLICADOS:
    - Factory Pattern: Centraliza creación de objetos complejos
    - SRP: Solo responsable de crear liquidadores
    - DIP: Permite inyección de diferentes implementaciones
    """

    @staticmethod
    def crear_liquidador(config_personalizada: Optional[Dict[str, Any]] = None) -> LiquidadorConsorcios:
        """
        Crea instancia de LiquidadorConsorcios con configuración opcional.

        Args:
            config_personalizada: Configuración opcional para validadores/calculadores

        Returns:
            LiquidadorConsorcios: Instancia configurada
        """
        if config_personalizada:
            # Permitir inyección de implementaciones personalizadas
            validador_naturaleza = config_personalizada.get('validador_naturaleza')
            validador_conceptos = config_personalizada.get('validador_conceptos')
            calculador_retencion = config_personalizada.get('calculador_retencion')

            return LiquidadorConsorcios(
                validador_naturaleza=validador_naturaleza,
                validador_conceptos=validador_conceptos,
                calculador_retencion=calculador_retencion
            )

        # Configuración por defecto
        return LiquidadorConsorcios()


if __name__ == '__main__':
    # Ejemplo de uso
    liquidador = LiquidadorConsorciosFactory.crear_liquidador()
    logger.info("✅ LiquidadorConsorcios creado con arquitectura SOLID")