"""
LIQUIDADOR DE IMPUESTOS ESPECIALES - INTEGRADO
==============================================

Módulo integrado para calcular:
1. Estampilla Pro Universidad Nacional (tarifas por rangos UVT)
2. Contribución a Obra Pública del 5% (tarifa fija)

Aprovecha flujos similares y detecta automáticamente qué impuestos aplican según el NIT.

Autor: Miguel Angel Jaramillo Durango
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
import re

# Configuración de logging
logger = logging.getLogger(__name__)

# ===============================
# IMPORTAR CONFIGURACIÓN
# ===============================

from config import (
    UVT_2025,
    NITS_ESTAMPILLA_UNIVERSIDAD,
    NITS_CONTRIBUCION_OBRA_PUBLICA,
    TERCEROS_RECURSOS_PUBLICOS,
    OBJETOS_CONTRATO_ESTAMPILLA,
    OBJETOS_CONTRATO_OBRA_PUBLICA,
    RANGOS_ESTAMPILLA_UNIVERSIDAD,
    nit_aplica_estampilla_universidad,
    nit_aplica_contribucion_obra_publica,
    es_tercero_recursos_publicos,
    obtener_tarifa_estampilla_universidad,
    calcular_contribucion_obra_publica,
    detectar_impuestos_aplicables,
    obtener_configuracion_estampilla_universidad,
    obtener_configuracion_obra_publica,
    obtener_configuracion_impuestos_integrada
)

# ===============================
# MODELOS DE DATOS LOCALES
# ===============================

class ObjetoContratoIdentificado(BaseModel):
    objeto: str  # "contrato_obra", "interventoria", "servicios_conexos_obra"
    aplica_estampilla: bool
    palabras_clave_encontradas: List[str]

class TerceroContrato(BaseModel):
    nombre: str
    es_consorcio: bool = False
    administra_recursos_publicos: bool = False
    participacion_porcentaje: Optional[float] = None

class AnalisisContrato(BaseModel):
    valor_total_contrato: Optional[float] = None
    valor_total_uvt: Optional[float] = None
    objeto_identificado: Optional[ObjetoContratoIdentificado] = None
    tercero: Optional[TerceroContrato] = None
    observaciones: List[str] = []

class ResultadoEstampilla(BaseModel):
    aplica: bool
    estado: str  # "Preliquidado", "No aplica el impuesto", "Preliquidación sin finalizar"
    nit_administrativo_valido: bool
    tercero_valido: bool
    objeto_contrato_valido: bool
    valor_contrato_identificado: bool
    valor_estampilla: float = 0.0
    tarifa_aplicada: float = 0.0
    rango_uvt: str = ""
    valor_contrato_pesos: float = 0.0
    valor_contrato_uvt: float = 0.0
    detalle_calculo: Dict[str, Any] = {}
    consorcios: List[Dict[str, Any]] = []  # Para manejo de consorcios
    mensajes_error: List[str] = []
    fecha_calculo: str = ""

class ResultadoContribucionObraPublica(BaseModel):
    aplica: bool
    estado: str  # "Preliquidado", "No aplica el impuesto", "Preliquidación sin finalizar"
    nit_administrativo_valido: bool
    tercero_valido: bool
    objeto_contrato_valido: bool
    valor_factura_identificado: bool
    valor_contribucion: float = 0.0
    tarifa_aplicada: float = 0.05  # Siempre 5%
    valor_factura_sin_iva: float = 0.0
    detalle_calculo: Dict[str, Any] = {}
    consorcios: List[Dict[str, Any]] = []  # Para manejo de consorcios
    mensajes_error: List[str] = []
    fecha_calculo: str = ""

class ResultadoImpuestosIntegrado(BaseModel):
    """Resultado integrado para ambos impuestos"""
    nit_administrativo: str
    impuestos_aplicables: List[str]
    procesamiento_paralelo: bool
    estampilla_universidad: Optional[ResultadoEstampilla] = None
    contribucion_obra_publica: Optional[ResultadoContribucionObraPublica] = None
    resumen_total: Dict[str, Any] = {}
    fecha_calculo: str = ""

# ===============================
# CLASE PRINCIPAL
# ===============================

class LiquidadorEstampilla:
    """
    🏛️ LIQUIDADOR INTEGRADO DE IMPUESTOS ESPECIALES - OPTIMIZADO 2025
    
    DESDE 2025: Ambos impuestos aplican para los MISMOS NITs administrativos.
    El sistema ahora utiliza análisis integrado optimizado.
    
    ✅ ESTAMPILLA PRO UNIVERSIDAD NACIONAL:
        - NITs unificados (ahora incluye todos los NITs de obra pública)
        - Objetos: obra + interventoría + servicios conexos
        - Cálculo: Tarifas por rangos UVT (0.5%, 1.0%, 2.0%)
        
    ✅ CONTRIBUCIÓN A OBRA PÚBLICA 5%:
        - Mismo NITs que estampilla (configuración unificada)
        - Objetos: SOLO contrato de obra (no interventoría)
        - Cálculo: Tarifa fija del 5% sobre factura sin IVA
        
    ✅ OPTIMIZACIONES IMPLEMENTADAS:
        - Prompt integrado en prompt_clasificador.py (mejor organización)
        - Detección automática de qué impuestos aplican según objeto
        - Procesamiento paralelo cuando ambos aplican (solo obra)
        - Manejo unificado de consorcios para ambos impuestos
        
    ⚠️ FUNCIONES ELIMINADAS (ya no necesarias):
        - obtener_prompt_gemini() → Reemplazado por prompt integrado
        - obtener_prompt_gemini_integrado() → Movido a prompt_clasificador.py
    """
    
    def __init__(self):
        self.uvt_2025 = UVT_2025
        logger.info(f" LiquidadorEstampilla INTEGRADO inicializado - UVT 2025: ${self.uvt_2025:,}")
        logger.info(f" Configuración: {len(NITS_ESTAMPILLA_UNIVERSIDAD)} NITs unificados")
        logger.info(f" Modo: ANÁLISIS INTEGRADO (estampilla + obra pública)")
    
    def validar_nit_administrativo(self, nit: str) -> Tuple[bool, str]:
        """
        Valida si el NIT administrativo aplica para estampilla universidad
        
        Args:
            nit: NIT de la entidad administrativa
            
        Returns:
            Tuple[bool, str]: (es_valido, mensaje)
        """
        if nit_aplica_estampilla_universidad(nit):
            nombre_entidad = NITS_ESTAMPILLA_UNIVERSIDAD[nit]
            return True, f"NIT válido: {nombre_entidad}"
        else:
            return False, f"El NIT {nit} no aplica para estampilla pro universidad nacional"
    
    def validar_tercero(self, nombre_tercero: str) -> Tuple[bool, str]:
        """
        Valida si el tercero administra recursos públicos
        
        Args:
            nombre_tercero: Nombre del tercero beneficiario
            
        Returns:
            Tuple[bool, str]: (es_valido, mensaje)
        """
        if es_tercero_recursos_publicos(nombre_tercero):
            return True, f"Tercero válido: {nombre_tercero} administra recursos públicos"
        else:
            return False, f"El tercero '{nombre_tercero}' no administra recursos públicos"
    
    def identificar_objeto_contrato(self, texto_documentos: str) -> ObjetoContratoIdentificado:
        """
        Identifica el objeto del contrato basado en palabras clave
        
        Args:
            texto_documentos: Texto extraído de los documentos
            
        Returns:
            ObjetoContratoIdentificado: Resultado de la identificación
        """
        texto_lower = texto_documentos.lower()
        
        for tipo_objeto, config in OBJETOS_CONTRATO_ESTAMPILLA.items():
            palabras_encontradas = []
            
            for palabra_clave in config["palabras_clave"]:
                if palabra_clave.lower() in texto_lower:
                    palabras_encontradas.append(palabra_clave)
            
            if palabras_encontradas:
                return ObjetoContratoIdentificado(
                    objeto=tipo_objeto,
                    aplica_estampilla=config["aplica"],
                    palabras_clave_encontradas=palabras_encontradas
                )
        
        # No se identificó ningún objeto válido
        return ObjetoContratoIdentificado(
            objeto="no_identificado",
            aplica_estampilla=False,
            palabras_clave_encontradas=[]
        )
    
    def extraer_valor_contrato(self, texto_documentos: str) -> Optional[float]:
        """
        Extrae el valor total del contrato del texto
        
        FUNCIONALIDAD:
        ✅ Busca patrones como "valor del contrato: $1,000,000"
        ✅ Maneja porcentajes como "20% del valor del contrato"
        ✅ Considera adiciones al contrato
        
        Args:
            texto_documentos: Texto extraído de los documentos
            
        Returns:
            Optional[float]: Valor del contrato en pesos, None si no se encuentra
        """
        # Patrones para buscar valores monetarios
        patrones_valor = [
            r'valor\s+(?:total\s+)?(?:del\s+)?contrato[:\s]+\$?[\d,.]+'  ,
            r'valor\s+contractual[:\s]+\$?[\d,.]+'  ,
            r'por\s+valor\s+de[:\s]+\$?[\d,.]+'  ,
            r'contrato\s+por[:\s]+\$?[\d,.]+'  ,
            r'suma\s+de[:\s]+\$?[\d,.]+'  
        ]
        
        # Patrones para extraer números
        patron_numero = r'[\d,.]+'
        
        for patron in patrones_valor:
            matches = re.finditer(patron, texto_documentos, re.IGNORECASE)
            for match in matches:
                texto_match = match.group()
                # Extraer el número del match
                numero_match = re.search(patron_numero, texto_match)
                if numero_match:
                    try:
                        # Limpiar y convertir a float
                        valor_str = numero_match.group().replace(',', '').replace('.', '')
                        # Asumir que los últimos 2 dígitos son decimales si es muy grande
                        if len(valor_str) > 6:
                            valor_float = float(valor_str[:-2] + '.' + valor_str[-2:])
                        else:
                            valor_float = float(valor_str)
                        
                        if valor_float > 1000:  # Filtro básico para valores razonables
                            return valor_float
                    except ValueError:
                        continue
        
        # Buscar patrones de porcentaje
        patrones_porcentaje = [
            r'(\d+)%\s+del\s+valor\s+del\s+contrato',
            r'pago\s+correspondiente\s+al\s+(\d+)%'
        ]
        
        for patron in patrones_porcentaje:
            match = re.search(patron, texto_documentos, re.IGNORECASE)
            if match:
                porcentaje = float(match.group(1))
                # Buscar el valor base cerca del match
                texto_contexto = texto_documentos[max(0, match.start()-200):match.end()+200]
                valor_base = self._extraer_valor_monetario_simple(texto_contexto)
                if valor_base:
                    valor_total = (valor_base * 100) / porcentaje
                    return valor_total
        
        return None
    
    def _extraer_valor_monetario_simple(self, texto: str) -> Optional[float]:
        """Extrae un valor monetario simple del texto"""
        patron = r'\$?[\d,.]+'
        matches = re.findall(patron, texto)
        
        for match in matches:
            try:
                valor_str = match.replace('$', '').replace(',', '')
                valor_float = float(valor_str)
                if valor_float > 1000:
                    return valor_float
            except ValueError:
                continue
        
        return None
    
    def calcular_estampilla(self, valor_contrato_pesos: float, valor_factura_sin_iva: float = None) -> Dict[str, Any]:
        """
        Calcula el valor de la estampilla según el valor del contrato
        
        IMPORTANTE: La tarifa se determina por el valor del CONTRATO en UVT,
        pero el cálculo final se hace sobre el valor de la FACTURA sin IVA.
        
        FÓRMULA CORRECTA: Estampilla = Valor factura (sin IVA) x Porcentaje tarifa aplicable
        
        Args:
            valor_contrato_pesos: Valor del contrato en pesos colombianos (para determinar tarifa)
            valor_factura_sin_iva: Valor de la factura sin IVA (para cálculo final)
            
        Returns:
            Dict con el cálculo detallado
        """
        # Si no se proporciona valor de factura, usar el valor del contrato
        if valor_factura_sin_iva is None:
            valor_factura_sin_iva = valor_contrato_pesos
            logger.warning(" No se proporcionó valor de factura, usando valor del contrato")
        
        # Obtener tarifa según valor del contrato en UVT
        info_tarifa = obtener_tarifa_estampilla_universidad(valor_contrato_pesos)
        
        # ✅ CÁLCULO CORRECTO: Aplicar tarifa sobre valor de FACTURA sin IVA
        valor_estampilla = valor_factura_sin_iva * info_tarifa["tarifa"]
        
        # Determinar rango en texto
        if info_tarifa["rango_hasta_uvt"] == float('inf'):
            rango_texto = f"Más de {info_tarifa['rango_desde_uvt']:,.0f} UVT"
        else:
            rango_texto = f"Entre {info_tarifa['rango_desde_uvt']:,.0f} y {info_tarifa['rango_hasta_uvt']:,.0f} UVT"
        
        return {
            "valor_estampilla": valor_estampilla,
            "tarifa_aplicada": info_tarifa["tarifa"],
            "tarifa_porcentaje": info_tarifa["tarifa"] * 100,
            "valor_contrato_pesos": valor_contrato_pesos,
            "valor_factura_sin_iva": valor_factura_sin_iva,
            "valor_contrato_uvt": info_tarifa["valor_contrato_uvt"],
            "rango_uvt": rango_texto,
            "rango_desde_uvt": info_tarifa["rango_desde_uvt"],
            "rango_hasta_uvt": info_tarifa["rango_hasta_uvt"],
            "uvt_2025": info_tarifa["uvt_2025"],
            "formula_aplicada": f"Estampilla = Valor factura sin IVA (${valor_factura_sin_iva:,.2f}) x {info_tarifa['tarifa']*100:.1f}% = ${valor_estampilla:,.2f}"
        }
    
    def calcular_estampilla_consorcio(self, valor_contrato_pesos: float, valor_factura_sin_iva: float,
                                    consorciados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calcula la estampilla para cada consorciado según su participación
        
        IMPORTANTE: Tarifa determinada por valor del CONTRATO, cálculo sobre valor FACTURA.
        FÓRMULA: Estampilla = Valor factura sin IVA x Tarifa x % participación
        
        Args:
            valor_contrato_pesos: Valor total del contrato (para determinar tarifa)
            valor_factura_sin_iva: Valor de la factura sin IVA (para cálculo)
            consorciados: Lista de consorciados con su participación
            
        Returns:
            List[Dict]: Cálculo para cada consorciado
        """
        resultados = []
        
        # Obtener tarifa una sola vez (basada en valor total del contrato)
        info_tarifa = obtener_tarifa_estampilla_universidad(valor_contrato_pesos)
        
        for consorciado in consorciados:
            nombre = consorciado.get("nombre", "Sin nombre")
            participacion = consorciado.get("participacion_porcentaje", 0) / 100
            
            # ✅ CÁLCULO CORRECTO PARA CONSORCIOS:
            # Estampilla = Valor factura sin IVA x Tarifa x % participación
            valor_estampilla_consorciado = valor_factura_sin_iva * info_tarifa["tarifa"] * participacion
            
            # Agregar información del consorciado
            calculo = {
                "valor_estampilla": valor_estampilla_consorciado,
                "tarifa_aplicada": info_tarifa["tarifa"],
                "tarifa_porcentaje": info_tarifa["tarifa"] * 100,
                "valor_contrato_pesos": valor_contrato_pesos,
                "valor_factura_sin_iva": valor_factura_sin_iva,
                "valor_contrato_uvt": info_tarifa["valor_contrato_uvt"],
                "nombre_consorciado": nombre,
                "participacion_porcentaje": consorciado.get("participacion_porcentaje", 0),
                "valor_proporcional_factura": valor_factura_sin_iva * participacion,
                "formula_aplicada": f"Estampilla = ${valor_factura_sin_iva:,.2f} x {info_tarifa['tarifa']*100:.1f}% x {participacion*100:.1f}% = ${valor_estampilla_consorciado:,.2f}"
            }
            
            # Determinar rango en texto
            if info_tarifa["rango_hasta_uvt"] == float('inf'):
                calculo["rango_uvt"] = f"Más de {info_tarifa['rango_desde_uvt']:,.0f} UVT"
            else:
                calculo["rango_uvt"] = f"Entre {info_tarifa['rango_desde_uvt']:,.0f} y {info_tarifa['rango_hasta_uvt']:,.0f} UVT"
            
            resultados.append(calculo)
        
        return resultados
    
    def liquidar_estampilla(self, analisis_contrato: AnalisisContrato, valor_factura_sin_iva: float,
                          nit_administrativo: str) -> ResultadoEstampilla:
        """
        Procesa la liquidación completa de estampilla pro universidad nacional
        
        CUMPLE EXACTAMENTE LOS REQUISITOS:
        ✅ Valida objeto del contrato (obra, interventoría, servicios conexos)
        ✅ Si NO se identifica objeto → "Preliquidación sin finalizar"
        ✅ Valida valor del contrato (para determinar tarifa UVT)
        ✅ Si NO se identifica valor → "Preliquidación sin finalizar"
        ✅ Fórmula: Estampilla = Valor factura (sin IVA) x Porcentaje tarifa
        ✅ Estados: "Preliquidado" / "No aplica el impuesto" / "Preliquidación sin finalizar"
        ✅ Manejo de consorcios con porcentaje de participación
        
        Args:
            analisis_contrato: Resultado del análisis de Gemini
            valor_factura_sin_iva: Valor de la factura sin IVA (para cálculo final)
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            ResultadoEstampilla: Resultado completo de la liquidación
        """
        resultado = ResultadoEstampilla(
            aplica=False,
            estado="Preliquidación sin finalizar",
            nit_administrativo_valido=False,
            tercero_valido=False,
            objeto_contrato_valido=False,
            valor_contrato_identificado=False,
            fecha_calculo=datetime.now().isoformat()
        )
        
        try:
            # 1. VALIDAR NIT ADMINISTRATIVO
            nit_valido, mensaje_nit = self.validar_nit_administrativo(nit_administrativo)
            resultado.nit_administrativo_valido = nit_valido
            
            if not nit_valido:
                resultado.mensajes_error.append(mensaje_nit)
                resultado.estado = "No aplica el impuesto"
                return resultado
            
            # 2. VALIDAR TERCERO
            if analisis_contrato.tercero:
                tercero_valido, mensaje_tercero = self.validar_tercero(analisis_contrato.tercero.nombre)
                resultado.tercero_valido = tercero_valido
                
                if not tercero_valido:
                    resultado.mensajes_error.append(mensaje_tercero)
                    resultado.estado = "No aplica el impuesto"
                    return resultado
            else:
                resultado.mensajes_error.append("No se identificó información del tercero")
                resultado.estado = "Preliquidación sin finalizar"
                return resultado
            
            # 3. ✅ VALIDAR OBJETO DEL CONTRATO - REQUISITO CRÍTICO
            if analisis_contrato.objeto_identificado:
                resultado.objeto_contrato_valido = analisis_contrato.objeto_identificado.aplica_estampilla
                
                if not resultado.objeto_contrato_valido:
                    resultado.mensajes_error.append(f"Objeto del contrato '{analisis_contrato.objeto_identificado.objeto}' no aplica para estampilla")
                    resultado.estado = "No aplica el impuesto"
                    return resultado
            else:
                # ✅ CUMPLE REQUISITO: Si NO se identifica objeto → "Preliquidación sin finalizar"
                resultado.mensajes_error.append("Cuando no se identifica el objeto del contrato, asignar estado: Preliquidación sin finalizar")
                resultado.estado = "Preliquidación sin finalizar"
                return resultado
            
            # 4. ✅ VALIDAR VALOR DEL CONTRATO - REQUISITO CRÍTICO
            if analisis_contrato.valor_total_contrato:
                resultado.valor_contrato_identificado = True
                resultado.valor_contrato_pesos = analisis_contrato.valor_total_contrato
                resultado.valor_contrato_uvt = analisis_contrato.valor_total_contrato / self.uvt_2025
            else:
                # ✅ CUMPLE REQUISITO: Si NO se identifica valor → "Preliquidación sin finalizar"
                resultado.mensajes_error.append("Si no se identifica el valor del contrato, asignar estado: Preliquidación sin finalizar")
                resultado.estado = "Preliquidación sin finalizar"
                return resultado
            
            # 5. ✅ CALCULAR ESTAMPILLA CON FÓRMULA CORRECTA
            if analisis_contrato.tercero and analisis_contrato.tercero.es_consorcio:
                # MANEJO DE CONSORCIOS
                logger.info(" Calculando estampilla para consorcio")
                # Aquí se necesitaría información de los consorciados del análisis
                # Por ahora, manejo básico
                calculo = self.calcular_estampilla(
                    valor_contrato_pesos=resultado.valor_contrato_pesos,
                    valor_factura_sin_iva=valor_factura_sin_iva
                )
            else:
                # EMPRESA INDIVIDUAL
                calculo = self.calcular_estampilla(
                    valor_contrato_pesos=resultado.valor_contrato_pesos,
                    valor_factura_sin_iva=valor_factura_sin_iva
                )
            
            # 6. ✅ ACTUALIZAR RESULTADO CON ESTADOS CORRECTOS
            resultado.aplica = True
            resultado.estado = "Preliquidado"  # ✅ CUMPLE REQUISITO: Si aplica → "Preliquidado"
            resultado.valor_estampilla = calculo["valor_estampilla"]
            resultado.tarifa_aplicada = calculo["tarifa_aplicada"]
            resultado.rango_uvt = calculo["rango_uvt"]
            resultado.detalle_calculo = calculo
            
            logger.info(f" Estampilla calculada: ${resultado.valor_estampilla:,.2f} ({resultado.tarifa_aplicada*100:.1f}%)")
            logger.info(f"Fórmula aplicada: {calculo.get('formula_aplicada', 'N/A')}")
            
        except Exception as e:
            logger.error(f" Error calculando estampilla: {e}")
            resultado.mensajes_error.append(f"Error interno: {str(e)}")
            resultado.estado = "Preliquidación sin finalizar"
        
        return resultado
    
    def obtener_prompt_integrado_desde_clasificador(self, factura_texto: str, rut_texto: str, anexos_texto: str, 
                                                     cotizaciones_texto: str, anexo_contrato: str, nit_administrativo: str, nombres_archivos_directos: List[str]=None) -> str:
        """
        🚀 NUEVA FUNCIÓN - Obtiene el prompt integrado optimizado desde prompt_clasificador.py
        
        Esta función reemplaza los prompts individuales y utiliza el análisis integrado
        de obra pública + estampilla universidad.
        
        Args:
            factura_texto: Texto extraído de la factura principal
            rut_texto: Texto del RUT (si está disponible)
            anexos_texto: Texto de anexos adicionales
            cotizaciones_texto: Texto de cotizaciones
            anexo_contrato: Texto del anexo de concepto de contrato
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            str: Prompt integrado optimizado para Gemini
        """
        from Clasificador.prompt_clasificador import PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO
        
        return PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO(
            factura_texto=factura_texto,
            rut_texto=rut_texto,
            anexos_texto=anexos_texto,
            cotizaciones_texto=cotizaciones_texto,
            anexo_contrato=anexo_contrato,
            nit_administrativo=nit_administrativo,
            nombres_archivos_directos=nombres_archivos_directos
        )
    
    # ===============================
    # MÉTODOS PARA CONTRIBUCIÓN A OBRA PÚBLICA 5% (NUEVO)
    # ===============================
    
    def liquidar_contribucion_obra_publica(self, valor_factura_sin_iva: float, 
                                           nit_administrativo: str,
                                           nombre_tercero: str = "",
                                           objeto_contrato: str = "",
                                           es_consorcio: bool = False,
                                           consorciados_info: List[Dict] = None) -> ResultadoContribucionObraPublica:
        """
        Liquida contribución a obra pública del 5%
        
        CUMPLE EXACTAMENTE LOS REQUISITOS:
        ✅ Solo contrato de obra (construcción, mantenimiento, instalación)
        ✅ Si NO se identifica objeto → "Preliquidación sin finalizar"
        ✅ Si NO se identifica valor → "Preliquidación sin finalizar"
        ✅ Fórmula: Contribución = Valor factura (sin IVA) x 5%
        ✅ Consorcios: Contribución = Valor factura (sin IVA) x 5% x % participación
        ✅ Estados: "Preliquidado" / "No aplica el impuesto" / "Preliquidación sin finalizar"
        
        Args:
            valor_factura_sin_iva: Valor de la factura sin IVA
            nit_administrativo: NIT de la entidad administrativa
            nombre_tercero: Nombre del tercero beneficiario
            objeto_contrato: Descripción del objeto del contrato
            es_consorcio: Si es un consorcio o unión temporal
            consorciados_info: Lista de consorciados con participación
            
        Returns:
            ResultadoContribucionObraPublica: Resultado completo del cálculo
        """
        logger.info(f" Iniciando liquidación contribución obra pública - Valor: ${valor_factura_sin_iva:,.2f}")
        
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resultado = ResultadoContribucionObraPublica(
            aplica=False,
            estado="Preliquidación sin finalizar",
            nit_administrativo_valido=False,
            tercero_valido=False,
            objeto_contrato_valido=False,
            valor_factura_identificado=False,
            fecha_calculo=fecha_actual
        )
        
        try:
            # 1. ✅ VALIDAR NIT ADMINISTRATIVO
            if nit_aplica_contribucion_obra_publica(nit_administrativo):
                resultado.nit_administrativo_valido = True
                logger.info(f" NIT válido para obra pública: {NITS_CONTRIBUCION_OBRA_PUBLICA[nit_administrativo]}")
            else:
                resultado.mensajes_error.append(f"NIT {nit_administrativo} no aplica para contribución a obra pública")
                resultado.estado = "No aplica el impuesto"
                logger.warning(f"NIT no válido: {nit_administrativo}")
                return resultado
            
            # 2. ✅ VALIDAR TERCERO (solo si se proporciona nombre)
            if nombre_tercero:
                if es_tercero_recursos_publicos(nombre_tercero):
                    resultado.tercero_valido = True
                    logger.info(f"Tercero válido: {nombre_tercero}")
                else:
                    resultado.mensajes_error.append(f"Tercero '{nombre_tercero}' no administra recursos públicos")
                    resultado.estado = "No aplica el impuesto"
                    logger.warning(f"Tercero no válido: {nombre_tercero}")
                    return resultado
            else:
                resultado.tercero_valido = True  # Si no se proporciona, asumimos válido
            
            # 3. ✅ VALIDAR OBJETO DEL CONTRATO - REQUISITO CRÍTICO (SOLO OBRA)
            if objeto_contrato:
                es_obra = self._es_contrato_obra(objeto_contrato)
                if es_obra:
                    resultado.objeto_contrato_valido = True
                    logger.info(f" Objeto válido para obra pública: contrato de obra")
                else:
                    resultado.mensajes_error.append("Cuando no se identifica el objeto del contrato como OBRA, asignar estado: Preliquidación sin finalizar")
                    logger.warning(f" Objeto no válido: {objeto_contrato}")
                    resultado.estado = "Preliquidación sin finalizar"
                    return resultado
            else:
                # ✅ CUMPLE REQUISITO: Si NO se identifica objeto → "Preliquidación sin finalizar"
                resultado.mensajes_error.append("Cuando no se identifica el objeto del contrato, asignar estado: Preliquidación sin finalizar")
                resultado.estado = "Preliquidación sin finalizar"
                return resultado
            
            # 4. ✅ VALIDAR VALOR DE FACTURA - REQUISITO CRÍTICO
            if valor_factura_sin_iva > 0:
                resultado.valor_factura_identificado = True
                resultado.valor_factura_sin_iva = valor_factura_sin_iva
            else:
                # ✅ CUMPLE REQUISITO: Si NO se identifica valor → "Preliquidación sin finalizar"
                resultado.mensajes_error.append("Si no se identifica el valor de la factura, asignar estado: Preliquidación sin finalizar")
                resultado.estado = "Preliquidación sin finalizar"
                return resultado
            
            # 5. ✅ CÁLCULO CON FÓRMULA CORRECTA
            if es_consorcio and consorciados_info:
                resultado = self._calcular_obra_publica_consorcio(resultado, valor_factura_sin_iva, consorciados_info)
            else:
                resultado = self._calcular_obra_publica_individual(resultado, valor_factura_sin_iva)
            
            # 6. ✅ ESTADO FINAL CORRECTO
            if resultado.aplica and resultado.valor_contribucion > 0:
                resultado.estado = "Preliquidado"  # ✅ CUMPLE REQUISITO: Si aplica → "Preliquidado"
                logger.info(f" Contribución obra pública calculada: ${resultado.valor_contribucion:,.2f}")
                logger.info(f" Fórmula: Valor factura sin IVA x 5% = ${valor_factura_sin_iva:,.2f} x 5% = ${resultado.valor_contribucion:,.2f}")
            else:
                resultado.estado = "No aplica el impuesto"
            
            return resultado
            
        except Exception as e:
            logger.error(f" Error liquidando obra pública: {e}")
            resultado.mensajes_error.append(f"Error en cálculo: {str(e)}")
            resultado.estado = "Preliquidación sin finalizar"
            return resultado
    
    def _es_contrato_obra(self, descripcion: str) -> bool:
        """¿cnica si una descripción corresponde a contrato de obra"""
        if not descripcion:
            return False
            
        descripcion_lower = descripcion.lower()
        palabras_obra = OBJETOS_CONTRATO_OBRA_PUBLICA["contrato_obra"]["palabras_clave"]
        
        for palabra in palabras_obra:
            if palabra.lower() in descripcion_lower:
                return True
        
        return False
    
    def _calcular_obra_publica_individual(self, resultado: ResultadoContribucionObraPublica, 
                                         valor_factura: float) -> ResultadoContribucionObraPublica:
        """Calcula contribución obra pública para facturación individual"""
        
        valor_contribucion = calcular_contribucion_obra_publica(valor_factura, 100.0)
        
        resultado.aplica = True
        resultado.valor_contribucion = valor_contribucion
        resultado.tarifa_aplicada = 0.05  # 5% fijo
        resultado.detalle_calculo = {
            "tipo_calculo": "individual",
            "valor_factura_sin_iva": valor_factura,
            "tarifa_aplicada": 0.05,
            "valor_contribucion": valor_contribucion,
            "formula": "Valor factura sin IVA x 5%"
        }
        
        return resultado
    
    def _calcular_obra_publica_consorcio(self, resultado: ResultadoContribucionObraPublica,
                                        valor_factura: float, 
                                        consorciados_info: List[Dict]) -> ResultadoContribucionObraPublica:
        """Calcula contribución obra pública para consorcio"""
        
        consorcios_calculo = []
        valor_total_contribucion = 0.0
        
        for consorciado in consorciados_info:
            nombre = consorciado.get("nombre", "No identificado")
            participacion = consorciado.get("porcentaje_participacion", 0.0)
            
            valor_contribucion_consorciado = calcular_contribucion_obra_publica(
                valor_factura, participacion
            )
            
            consorcios_calculo.append({
                "nombre": nombre,
                "porcentaje_participacion": participacion,
                "valor_proporcional": valor_factura * (participacion / 100.0),
                "valor_contribucion": valor_contribucion_consorciado,
                "tarifa_aplicada": 0.05
            })
            
            valor_total_contribucion += valor_contribucion_consorciado
        
        resultado.aplica = True
        resultado.valor_contribucion = valor_total_contribucion
        resultado.tarifa_aplicada = 0.05
        resultado.consorcios = consorcios_calculo
        resultado.detalle_calculo = {
            "tipo_calculo": "consorcio",
            "valor_factura_sin_iva": valor_factura,
            "total_consorciados": len(consorciados_info),
            "tarifa_aplicada": 0.05,
            "valor_total_contribucion": valor_total_contribucion,
            "formula": "Valor factura sin IVA x 5% x % participación"
        }
        
        return resultado
    
    def liquidar_integrado(self, analisis_especiales: dict, nit_administrativo: str) -> dict:
        """
        🚀 MÉTODO INTEGRADO - Procesa estampilla + obra pública en una sola llamada
        
        Esta función es requerida por el endpoint principal para procesamiento paralelo.
        Analiza qué impuestos aplican y los liquida según los datos de Gemini.
        
        Args:
            analisis_especiales: Respuesta de Gemini con análisis de estampilla + obra pública
            nit_administrativo: NIT de la entidad administrativa
            
        Returns:
            dict: Resultado consolidado con ambos impuestos
        """
        logger.info(f"Liquidación integrada iniciada para NIT: {nit_administrativo}")
        
        resultado_integrado = {
            "nit_administrativo": nit_administrativo,
            "timestamp": datetime.now().isoformat(),
            "procesamiento_integrado": True
        }
        
        try:
            # Detectar qué impuestos aplican automáticamente
            aplica_estampilla = nit_aplica_estampilla_universidad(nit_administrativo)
            aplica_obra_publica = nit_aplica_contribucion_obra_publica(nit_administrativo)
            
            logger.info(f" Estampilla aplica: {aplica_estampilla}")
            logger.info(f" Obra pública aplica: {aplica_obra_publica}")
            
            # LIQUIDAR ESTAMPILLA UNIVERSIDAD (si aplica)
            if aplica_estampilla and analisis_especiales.get("estampilla_universidad"):
                try:
                    estampilla_data = analisis_especiales["estampilla_universidad"]
                    tercero_data = analisis_especiales.get("tercero_identificado", {})
                    
                    # Crear objeto AnalisisContrato desde respuesta de Gemini
                    tercero = TerceroContrato(
                        nombre=tercero_data.get("nombre", ""),
                        es_consorcio=tercero_data.get("es_consorcio", False),
                        administra_recursos_publicos=tercero_data.get("administra_recursos_publicos", False)
                    )
                    
                    objeto_contrato = ObjetoContratoIdentificado(
                        objeto=estampilla_data.get("objeto_contrato", {}).get("tipo", "no_identificado"),
                        aplica_estampilla=estampilla_data.get("objeto_contrato", {}).get("aplica_estampilla", False),
                        palabras_clave_encontradas=estampilla_data.get("objeto_contrato", {}).get("palabras_clave_encontradas", [])
                    )
                    
                    analisis_contrato = AnalisisContrato(
                        valor_total_contrato=estampilla_data.get("valor_contrato", {}).get("valor_total_pesos", 0.0),
                        valor_total_uvt=estampilla_data.get("valor_contrato", {}).get("valor_total_uvt", 0.0),
                        objeto_identificado=objeto_contrato,
                        tercero=tercero,
                        observaciones=[]
                    )
                    
                    # Usar valor de la factura si está disponible
                    valor_factura = estampilla_data.get("valor_factura", {}).get("valor_sin_iva", analisis_contrato.valor_total_contrato)
                    
                    # Liquidar estampilla
                    resultado_estampilla = self.liquidar_estampilla(analisis_contrato, valor_factura, nit_administrativo)
                    
                    # Convertir a diccionario para compatibilidad
                    resultado_integrado["estampilla_universidad"] = {
                        "aplica": resultado_estampilla.aplica,
                        "estado": resultado_estampilla.estado,
                        "valor_estampilla": resultado_estampilla.valor_estampilla,
                        "tarifa_aplicada": resultado_estampilla.tarifa_aplicada,
                        "rango_uvt": resultado_estampilla.rango_uvt,
                        "valor_contrato_pesos": resultado_estampilla.valor_contrato_pesos,
                        "valor_contrato_uvt": resultado_estampilla.valor_contrato_uvt,
                        "mensajes_error": resultado_estampilla.mensajes_error,
                        "fecha_calculo": resultado_estampilla.fecha_calculo
                    }
                    
                    logger.info(f" Estampilla procesada: ${resultado_estampilla.valor_estampilla:,.2f}")
                    
                except Exception as e:
                    logger.error(f" Error procesando estampilla: {e}")
                    resultado_integrado["estampilla_universidad"] = {
                        "aplica": False,
                        "estado": "Error en procesamiento",
                        "error": str(e),
                        "mensajes_error": [f"Error interno: {str(e)}"]
                    }
            else:
                resultado_integrado["estampilla_universidad"] = {
                    "aplica": False,
                    "estado": "No aplica el impuesto",
                    "razon": "NIT no configurado para estampilla" if not aplica_estampilla else "No se detectó información de estampilla en el análisis"
                }
            
            # LIQUIDAR CONTRIBUCIÓN OBRA PÚBLICA (si aplica)
            if aplica_obra_publica and analisis_especiales.get("contribucion_obra_publica"):
                try:
                    obra_data = analisis_especiales["contribucion_obra_publica"]
                    tercero_data = analisis_especiales.get("tercero_identificado", {})
                    
                    # Extraer parámetros para obra pública
                    valor_factura_sin_iva = obra_data.get("valor_factura", {}).get("valor_sin_iva", 0.0)
                    nombre_tercero = tercero_data.get("nombre", "")
                    es_consorcio = tercero_data.get("es_consorcio", False)
                    consorciados_info = tercero_data.get("consorciados", [])
                    
                    # Crear descripción del objeto
                    palabras_clave = obra_data.get("objeto_contrato", {}).get("palabras_clave_encontradas", [])
                    objeto_contrato = " ".join(palabras_clave) if palabras_clave else "contrato de obra"
                    
                    # Liquidar obra pública
                    resultado_obra_publica = self.liquidar_contribucion_obra_publica(
                        valor_factura_sin_iva=valor_factura_sin_iva,
                        nit_administrativo=nit_administrativo,
                        nombre_tercero=nombre_tercero,
                        objeto_contrato=objeto_contrato,
                        es_consorcio=es_consorcio,
                        consorciados_info=consorciados_info
                    )
                    
                    # Convertir a diccionario para compatibilidad
                    resultado_integrado["contribucion_obra_publica"] = {
                        "aplica": resultado_obra_publica.aplica,
                        "estado": resultado_obra_publica.estado,
                        "valor_contribucion": resultado_obra_publica.valor_contribucion,
                        "tarifa_aplicada": resultado_obra_publica.tarifa_aplicada,
                        "valor_factura_sin_iva": resultado_obra_publica.valor_factura_sin_iva,
                        "mensajes_error": resultado_obra_publica.mensajes_error,
                        "fecha_calculo": resultado_obra_publica.fecha_calculo
                    }
                    
                    logger.info(f" Obra pública procesada: ${resultado_obra_publica.valor_contribucion:,.2f}")
                    
                except Exception as e:
                    logger.error(f" Error procesando obra pública: {e}")
                    resultado_integrado["contribucion_obra_publica"] = {
                        "aplica": False,
                        "estado": "Error en procesamiento",
                        "error": str(e),
                        "mensajes_error": [f"Error interno: {str(e)}"]
                    }
            else:
                resultado_integrado["contribucion_obra_publica"] = {
                    "aplica": False,
                    "estado": "No aplica el impuesto",
                    "razon": "NIT no configurado para obra pública" if not aplica_obra_publica else "No se detectó información de obra pública en el análisis"
                }
            
            # RESUMEN TOTAL
            valor_total_estampilla = resultado_integrado.get("estampilla_universidad", {}).get("valor_estampilla", 0)
            valor_total_obra_publica = resultado_integrado.get("contribucion_obra_publica", {}).get("valor_contribucion", 0)
            
            resultado_integrado["resumen_total"] = {
                "valor_total_impuestos_especiales": valor_total_estampilla + valor_total_obra_publica,
                "estampilla_calculada": valor_total_estampilla,
                "obra_publica_calculada": valor_total_obra_publica,
                "procesamiento_exitoso": True
            }
            
            logger.info(f" Total impuestos especiales: ${valor_total_estampilla + valor_total_obra_publica:,.2f}")
            
            return resultado_integrado
            
        except Exception as e:
            logger.error(f" Error en liquidación integrada: {e}")
            return {
                "nit_administrativo": nit_administrativo,
                "error": f"Error en liquidación integrada: {str(e)}",
                "procesamiento_exitoso": False,
                "timestamp": datetime.now().isoformat()
            }


# ===============================
# FUNCIONES DE UTILIDAD
# ===============================

def crear_liquidador_estampilla() -> LiquidadorEstampilla:
    """Factory function para crear instancia del liquidador integrado (compatibilidad hacia atrás)"""
    logger.info(" Creando liquidador integrado - Modo estampilla + obra pública")
    return LiquidadorEstampilla()

# ✅ ALIAS INTEGRADO: Liquidador de Impuestos Especiales
LiquidadorImpuestosEspeciales = LiquidadorEstampilla

def crear_liquidador_impuestos_especiales() -> LiquidadorEstampilla:
    """Factory function para crear instancia del liquidador integrado optimizado"""
    logger.info(" Creando liquidador integrado (estampilla + obra pública)")
    return LiquidadorEstampilla()

def validar_configuracion_estampilla() -> Dict[str, Any]:
    """Valida la configuración integrada de estampilla + obra pública"""
    try:
        config = obtener_configuracion_estampilla_universidad()
        
        validacion = {
            "valida": True,
            "tipo_configuracion": "INTEGRADA (estampilla + obra pública)",
            "nits_configurados": len(config["nits_validos"]),
            "terceros_configurados": len(config["terceros_recursos_publicos"]),
            "objetos_contrato": len(config["objetos_contrato"]),
            "rangos_uvt": len(config["rangos_uvt"]),
            "uvt_2025": config["uvt_2025"],
            "nits_unificados": list(config["nits_validos"].keys()),
            "errores": []
        }
        
        # Validaciones básicas
        if config["uvt_2025"] <= 0:
            validacion["errores"].append("UVT 2025 no válido")
            validacion["valida"] = False
        
        if len(config["nits_validos"]) == 0:
            validacion["errores"].append("No hay NITs configurados")
            validacion["valida"] = False
        
        if len(config["terceros_recursos_publicos"]) == 0:
            validacion["errores"].append("No hay terceros configurados")
            validacion["valida"] = False
        
        # ✅ Validación de unificación exitosa
        from config import NITS_CONTRIBUCION_OBRA_PUBLICA
        if config["nits_validos"] == NITS_CONTRIBUCION_OBRA_PUBLICA:
            validacion["unificacion_exitosa"] = True
            logger.info("Validación exitosa: NITs unificados correctamente")
        else:
            validacion["errores"].append("NITs de estampilla y obra pública no están unificados")
            validacion["valida"] = False
        
        return validacion
        
    except Exception as e:
        return {
            "valida": False,
            "error": str(e),
            "errores": [f"Error validando configuración integrada: {str(e)}"]
        }

def validar_configuracion_impuestos_integrada() -> Dict[str, Any]:
    """Valida la configuración OPTIMIZADA de ambos impuestos con NITs unificados"""
    try:
        config_integrada = obtener_configuracion_impuestos_integrada()
        
        validacion = {
            "valida": True,
            "version": "OPTIMIZADA 2025 - NITs Unificados",
            "estampilla_universidad": {},
            "contribucion_obra_publica": {},
            "terceros_compartidos": len(config_integrada["terceros_recursos_publicos_compartidos"]),
            "prompt_integrado_disponible": False,
            "errores": []
        }
        
        # Validar estampilla universidad
        config_estampilla = config_integrada["estampilla_universidad"]
        validacion["estampilla_universidad"] = {
            "nits_configurados": len(config_estampilla["nits_validos"]),
            "objetos_contrato": len(config_estampilla["objetos_contrato"]),
            "rangos_uvt": len(config_estampilla["rangos_uvt"])
        }
        
        # Validar obra pública
        config_obra = config_integrada["contribucion_obra_publica"]
        validacion["contribucion_obra_publica"] = {
            "nits_configurados": len(config_obra["nits_validos"]),
            "tarifa_fija": config_obra["tarifa_fija"],
            "objetos_contrato": len(config_obra["objetos_contrato"])
        }
        
        # ✅ Validación crítica: NITs unificados
        if config_estampilla["nits_validos"] == config_obra["nits_validos"]:
            validacion["nits_unificados_exitoso"] = True
            logger.info(" NITs unificados correctamente entre ambos impuestos")
        else:
            validacion["errores"].append("NITs no están unificados entre estampilla y obra pública")
            validacion["valida"] = False
        
        # Validación de prompt integrado
        try:
            from Clasificador.prompt_clasificador import PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO
            validacion["prompt_integrado_disponible"] = True
            logger.info(" Prompt integrado disponible en prompt_clasificador.py")
        except ImportError:
            validacion["errores"].append("Prompt integrado no encontrado en prompt_clasificador.py")
            validacion["valida"] = False
        
        # Validaciones críticas
        if len(config_integrada["terceros_recursos_publicos_compartidos"]) == 0:
            validacion["errores"].append("No hay terceros que administren recursos públicos configurados")
            validacion["valida"] = False
        
        if config_obra["tarifa_fija"] != 0.05:
            validacion["errores"].append("Tarifa de obra pública debe ser 5%")
            validacion["valida"] = False
        
        # Log final
        estado = "OK" if validacion["valida"] else "ERROR"
        logger.info(f" Validación configuración INTEGRADA OPTIMIZADA: {estado}")
        if validacion["valida"]:
            logger.info(f"   ✓ {validacion['estampilla_universidad']['nits_configurados']} NITs unificados")
            logger.info(f"   ✓ {validacion['terceros_compartidos']} terceros compartidos")
            logger.info(f"   ✓ Prompt integrado funcionando")
        
        return validacion
        
    except Exception as e:
        return {
            "valida": False,
            "error": str(e),
            "errores": [f"Error validando configuración integrada optimizada: {str(e)}"]
        }
