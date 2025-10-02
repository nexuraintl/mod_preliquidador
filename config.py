"""
CONFIGURACIÓN DEL PRELIQUIDADOR DE RETEFUENTE
==========================================

Maneja la configuración de conceptos, tarifas y parámetros del sistema.
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)



# Conceptos exactos con base mínima y tarifa específica
# Estructura: {concepto: {base_pesos: int, tarifa_retencion: float}}
CONCEPTOS_RETEFUENTE = {
    "Compras generales (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Compras generales (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Compras con tarjeta débito o crédito": {
        "base_pesos": 0,
        "tarifa_retencion": 0.015
    },
    "Compras de bienes o productos agrícolas o pecuarios sin procesamiento industrial": {
        "base_pesos": 3486000,
        "tarifa_retencion": 0.015
    },
    "Compras de bienes o productos agrícolas o pecuarios con procesamiento industrial (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes o productos agrícolas o pecuarios con procesamiento industrial declarantes (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Compras de café pergamino o cereza": {
        "base_pesos": 3486000,
        "tarifa_retencion": 0.005
    },
    "Compras de combustibles derivados del petróleo": {
        "base_pesos": 0,
        "tarifa_retencion": 0.001
    },
    "Enajenación de activos fijos de personas naturales (notarías y tránsito son agentes retenedores)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Compras de vehículos": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Servicios generales (declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.04
    },
    "Servicios generales (no declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.06
    },
    "Servicios de transporte de carga": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios de transporte nacional de pasajeros por vía terrestre": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Servicios de transporte nacional de pasajeros por vía aérea o marítima": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios prestados por empresas de servicios temporales (sobre AIU)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios prestados por empresas de vigilancia y aseo (sobre AIU)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.02
    },
    "Servicios integrales de salud prestados por IPS": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.02
    },
    "Arrendamiento de bienes muebles": {
        "base_pesos": 0,
        "tarifa_retencion": 0.04
    },
    "Arrendamiento de bienes inmuebles": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Otros ingresos tributarios (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Otros ingresos tributarios (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Honorarios y comisiones por servicios (persona juridica)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
     "Honorarios y comisiones por servicios (declarantes)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
    "Honorarios y comisiones por servicios (no declarantes)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.10
    },
    "Servicios de hoteles y restaurantes (declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.035
    },
    "Servicios de hoteles y restaurantes (no declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.035
    },
     "Servicios de licenciamiento o derecho de uso de software": {
        "base_pesos": 0,
        "tarifa_retencion": 0.035
    },
       "Intereses o rendimientos financieros": {
        "base_pesos": 0,
        "tarifa_retencion": 0.07
    },
    "Loterías, rifas, apuestas y similares": {
        "base_pesos": 2390000,
        "tarifa_retencion": 0.2
    },
    "Emolumentos eclesiásticos (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.04
    },
    "Emolumentos eclesiásticos ( no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Retención en colocación independiente de juegos de suerte y azar": {
        "base_pesos": 249000,
        "tarifa_retencion": 0.03
    },
     "Contratos de construcción y urbanización.": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.02
    },
    "compra de oro por las sociedades de comercialización internacional.": {
        "base_pesos": 0,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes raíces cuya destinación y uso sea vivienda de habitación (por las primeras $497990000 pesos colombianos)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Compras de bienes raíces cuya destinación y uso sea vivienda de habitación (exceso de $497990000 pesos colombianos)": {
        "base_pesos": 497990000,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes raíces cuya destinación y uso sea distinto a vivienda de habitación": {
        "base_pesos": 0,
        "tarifa_retencion": 0.025
    },
    "Servicios de consultoría en informática":{
        "base_pesos":0,
        "tarifa_retencion":0.035
    },
    "Alquiler":{
        "base_pesos": 0,
        "tarifa_retencion": 0.03
    },
    "transporte de pasajeros":{
        "base_pesos": 100000000,
        "tarifa_retencion": 0.035
    },
    "comision a terceros":{
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
    "personal de servicio":{
        "base_pesos": 0,
        "tarifa_retencion": 0.035
    },
    "pago a terceros":{
        "base_pesos": 0,
        "tarifa_retencion": 0.035
    }
}


# ===============================
# CONCEPTOS Y TARIFAS EXTRANJEROS
# ===============================

# Conceptos de retención para pagos al exterior
CONCEPTOS_EXTRANJEROS = {
    "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software": {
        "base_pesos": 0,  # Sin base mínima
        "tarifa_normal": 0.20,  # 20%
        "tarifa_convenio": 0.10  # 10%
    },
    "Consultorías, servicios técnicos y de asistencia técnica prestados por personas no residentes o no domiciliadas en Colombia": {
        "base_pesos": 0,
        "tarifa_normal": 0.20,  # 20%
        "tarifa_convenio": 0.10  # 10%
    },
    "Rendimientos financieros realizados a personas no residentes, originados en créditos obtenidos en el exterior por término igual o superior a un (1) año o por intereses o costos financieros del canon de arrendamiento en contratos de leasing con empresas extranjeras sin domicilio en colombia": {
        "base_pesos": 0,
        "tarifa_normal": 0.15,  # 15%
        "tarifa_convenio": 0.10  # 10%
    },
    "Contratos de leasing sobre naves, helicópteros y/o aerodinos, así como sus partes con empresas extranjeras sin domicilio en Colombia": {
        "base_pesos": 0,
        "tarifa_normal": 0.01,  # 1%
        "tarifa_convenio": 0.01  # 1%
    },
    "Rendimientos financieros o intereses realizados a personas no residentes, originados en créditos o valores de contenido crediticio, por término igual o superior a ocho (8) años, destinados a financiación de proyectos de infraestructura bajo esquema de Asociaciones Público-Privadas": {
        "base_pesos": 0,
        "tarifa_normal": 0.05,  # 5%
        "tarifa_convenio": 0.05  # 5%
    },
    "Prima cedida por reaseguros realizados a personas no residentes o no domiciliadas en el país": {
        "base_pesos": 0,
        "tarifa_normal": 0.01,  # 1%
        "tarifa_convenio": 0.01  # 1%
    },
    "Administración, servicios de gestión o dirección empresarial (como planificación, supervisión o coordinación) realizados a personas no residentes o no domiciliadas en el país, tales como casas matrices o entidades vinculadas en el exterior.": {
        "base_pesos": 0,
        "tarifa_normal": 0.33,  # 33%
        "tarifa_convenio": 0.33  # 33%
    }
}

# Países con convenio de doble tributación vigente
PAISES_CONVENIO_DOBLE_TRIBUTACION = [
    "Francia",
    "Italia", 
    "Reino Unido",
    "República Checa",
    "Portugal",
    "India",
    "Corea del Sur",
    "México",
    "Canadá",
    "Suiza",
    "Chile",
    "España"
]

# Países de la Comunidad Andina de Naciones (Decisión 578)
PAISES_COMUNIDAD_ANDINA = [
    "Perú",
    "Ecuador", 
    "Bolivia"
]

# Todos los países con convenio (incluye CAN)
PAISES_CON_CONVENIO = PAISES_CONVENIO_DOBLE_TRIBUTACION + PAISES_COMUNIDAD_ANDINA

# Preguntas para determinar fuente nacional
PREGUNTAS_FUENTE_NACIONAL = [
    "¿El servicio tiene uso o beneficio económico en Colombia?",
    "¿La actividad (servicio) se ejecutó total o parcialmente en Colombia?", 
    "¿El servicio corresponde a asistencia técnica, consultoría o know-how usado en Colombia?",
    "¿El bien vendido o utilizado está ubicado en Colombia?"
]


# ===============================
# CONFIGURACIÓN GENERAL
# ===============================

CONFIG = {
    "archivo_excel": "RETEFUENTE_CONCEPTOS.xlsx",
    "max_archivos": 6,
    "max_tamaño_mb": 50,
    "extensiones_soportadas": [".pdf", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".docx", ".doc"],
    "min_caracteres_ocr": 1000,
    "timeout_gemini_segundos": 30,
    "encoding_default": "utf-8"
}

# ===============================
# CONFIGURACIÓN DE NITS ADMINISTRATIVOS
# ===============================

NITS_CONFIGURACION = {
    "800178148": {
        "nombre": "Fiduciaria Colombiana de Comercio Exterior S.A.",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA", 
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL"
        ]
    },
    "830054060": {
        "nombre": "FIDEICOMISOS SOCIEDAD FIDUCIARIA FIDUCOLDEX",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA", 
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL"
        ]
    },
    "900649119": {
        "nombre": "PATRIMONIO AUTÓNOMO FONTUR",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL"
        ]
    },
    "901281733": {
        "nombre": "FONDOS DE INVERSIÓN - ABIERTA Y 60 MODERADO",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "900566230": {
        "nombre": "CONSORCIO",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "901427860": {
        "nombre": "CONSORCIO", 
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "900139498": {
        "nombre": "FIC FIDUCOLDEX",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    }
}

# ===============================
# FUNCIONES PARA GESTIÓN DE NITS
# ===============================

def obtener_nits_disponibles() -> Dict[str, Dict[str, Any]]:
    """Obtiene todos los NITs configurados"""
    return NITS_CONFIGURACION.copy()

def validar_nit_administrativo(nit: str) -> tuple[bool, str, List[str]]:
    """
    Valida si un NIT administrativo existe y retorna su información
    
    Args:
        nit: NIT a validar
        
    Returns:
        tuple: (es_valido, nombre_entidad, impuestos_aplicables)
    """
    nit_limpio = nit.strip()
    
    if nit_limpio in NITS_CONFIGURACION:
        datos = NITS_CONFIGURACION[nit_limpio]
        return True, datos["nombre"], datos["impuestos_aplicables"]
    else:
        return False, "", []

def nit_aplica_retencion_fuente(nit: str) -> bool:
    """
    Verifica si un NIT aplica retención en la fuente
    
    Args:
        nit: NIT a verificar
        
    Returns:
        bool: True si aplica retención en la fuente
    """
    es_valido, _, impuestos = validar_nit_administrativo(nit)
    return es_valido and "RETENCION_FUENTE" in impuestos


# =====================================
# FUNCIONES PARA FACTURACIÓN EXTRANJERA
# =====================================

def obtener_conceptos_extranjeros() -> Dict[str, Dict[str, Any]]:
    """Obtiene todos los conceptos de retención para facturación extranjera"""
    return CONCEPTOS_EXTRANJEROS.copy()
#no se usa
def obtener_conceptos_extranjeros_para_prompt() -> str:
    """Formatea conceptos extranjeros para uso en prompts de Gemini"""
    conceptos_formateados = []
    for concepto, datos in CONCEPTOS_EXTRANJEROS.items():
        tarifa_normal = datos["tarifa_normal"] * 100
        tarifa_convenio = datos["tarifa_convenio"] * 100
        conceptos_formateados.append(
            f"- {concepto}\n  * Tarifa normal: {tarifa_normal}%\n  * Tarifa con convenio: {tarifa_convenio}%"
        )
    return "\n\n".join(conceptos_formateados)
#si se usa
def obtener_paises_con_convenio() -> List[str]:
    """Obtiene la lista de países con convenio de doble tributación"""
    return PAISES_CON_CONVENIO.copy()

def obtener_preguntas_fuente_nacional() -> List[str]:
    """Obtiene las preguntas para determinar fuente nacional"""
    return PREGUNTAS_FUENTE_NACIONAL.copy()
#no se usa 
def es_pais_con_convenio(pais: str) -> bool:
    """Verifica si un país tiene convenio de doble tributación"""
    if not pais:
        return False
    
    pais_normalizado = pais.strip().title()
    return pais_normalizado in PAISES_CON_CONVENIO
#no se usa 
def obtener_tarifa_extranjera(concepto: str, tiene_convenio: bool = False) -> float:
    """Obtiene la tarifa para un concepto de facturación extranjera"""
    
    # Buscar concepto exacto
    if concepto in CONCEPTOS_EXTRANJEROS:
        datos = CONCEPTOS_EXTRANJEROS[concepto]
        return datos["tarifa_convenio"] if tiene_convenio else datos["tarifa_normal"]
    
    # Buscar por similitud (keywords)
    concepto_lower = concepto.lower()
    
    # Mapeo por palabras clave para conceptos extranjeros
    mapeo_keywords = {
        "interes": "Rendimientos financieros realizados a personas no residentes, originados en créditos obtenidos en el exterior por término igual o superior a un (1) año o por intereses o costos financieros del canon de arrendamiento en contratos de leasing con empresas extranjeras",
        "honorario": "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software",
        "consultoria": "Consultorías, servicios técnicos y de asistencia técnica prestados por personas no residentes o no domiciliadas en Colombia",
        "asistencia": "Consultorías, servicios técnicos y de asistencia técnica prestados por personas no residentes o no domiciliadas en Colombia",
        "regalias": "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software",
        "software": "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software",
        "leasing": "Contratos de leasing sobre naves, helicópteros y/o aerodinos, así como sus partes con empresas extranjeras sin domicilio en Colombia",
        "reaseguro": "Prima cedida por reaseguros realizados a personas no residentes o no domiciliadas en el país",
        "administracion": "Administración o dirección realizados a personas no residentes o no domiciliadas en el país",
        "direccion": "Administración o dirección realizados a personas no residentes o no domiciliadas en el país"
    }
    
    for keyword, concepto_mapped in mapeo_keywords.items():
        if keyword in concepto_lower:
            datos = CONCEPTOS_EXTRANJEROS[concepto_mapped]
            return datos["tarifa_convenio"] if tiene_convenio else datos["tarifa_normal"]
    
    # Por defecto, usar el primer concepto (más general)
    primer_concepto = list(CONCEPTOS_EXTRANJEROS.keys())[0]
    datos = CONCEPTOS_EXTRANJEROS[primer_concepto]
    return datos["tarifa_convenio"] if tiene_convenio else datos["tarifa_normal"]

# ===============================
# ARTÍCULO 383 - PERSONAS NATURALES
# ===============================

# Valores para la vigencia 2025
UVT_2025 = 49799  # Valor UVT 2025 en pesos
SMMLV_2025 = 1423500  # Salario Mínimo Mensual Legal Vigente 2025

# Conceptos que aplican para Artículo 383 ET
CONCEPTOS_ARTICULO_383 = [
    "Honorarios y comisiones por servicios (declarantes)",
    "Honorarios y comisiones por servicios (no declarantes)", 
    "Prestacion de servicios",
    "Comisiones",
    "Viaticos"
    # Nota: Incluye honorarios, prestación de servicios, diseños, comisiones, viáticos
]

# Tarifas progresivas Artículo 383 por rangos UVT
TARIFAS_ARTICULO_383 = [
    {"desde_uvt": 0, "hasta_uvt": 95, "tarifa": 0.00},      # 0%
    {"desde_uvt": 95, "hasta_uvt": 150, "tarifa": 0.19},    # 19%
    {"desde_uvt": 150, "hasta_uvt": 360, "tarifa": 0.28},   # 28%
    {"desde_uvt": 360, "hasta_uvt": 640, "tarifa": 0.33},   # 33%
    {"desde_uvt": 640, "hasta_uvt": 945, "tarifa": 0.35},   # 35%
    {"desde_uvt": 945, "hasta_uvt": 2300, "tarifa": 0.37},  # 37%
    {"desde_uvt": 2300, "hasta_uvt": float('inf'), "tarifa": 0.39}  # 39%
]

# Límites de deducciones Artículo 383 (en UVT mensuales)
LIMITES_DEDUCCIONES_ART383 = {
    "intereses_vivienda": 100,  # Hasta 100 UVT/mes
    "dependientes_economicos": 32,  # Hasta 32 UVT/mes o 10% del ingreso
    "medicina_prepagada": 16,  # Hasta 16 UVT/mes
    "rentas_exentas_uvt_anual": 3800,  # Hasta 3800 UVT/año
    "rentas_exentas_porcentaje": 0.25,  # Hasta 25% del ingreso mensual
    "deducciones_maximas_porcentaje": 0.40,  # Máximo 40% del ingreso bruto
    "seguridad_social_porcentaje": 0.40  # 40% del ingreso para seguridad social
}

# ===============================
# FUNCIONES ARTÍCULO 383
# ===============================

def es_concepto_articulo_383(concepto: str) -> bool:
    """Verifica si un concepto aplica para Artículo 383"""
    return concepto in CONCEPTOS_ARTICULO_383

def obtener_tarifa_articulo_383(base_gravable_pesos: float) -> float:
    """Obtiene la tarifa del Artículo 383 según la base gravable en pesos"""
    base_gravable_uvt = base_gravable_pesos / UVT_2025
    
    for rango in TARIFAS_ARTICULO_383:
        if rango["desde_uvt"] <= base_gravable_uvt < rango["hasta_uvt"]:
            return rango["tarifa"]
    
    # Si no encuentra rango, usar la última tarifa (39%)
    return TARIFAS_ARTICULO_383[-1]["tarifa"]

def calcular_limite_deduccion(tipo_deduccion: str, ingreso_bruto: float, valor_deducido: float) -> float:
    """Calcula el límite permitido para una deducción específica"""
    limites = LIMITES_DEDUCCIONES_ART383
    
    if tipo_deduccion == "intereses_vivienda":
        return min(valor_deducido, limites["intereses_vivienda"] * UVT_2025)
    
    elif tipo_deduccion == "dependientes_economicos":
        limite_porcentaje = ingreso_bruto * 0.10
        limite_uvt = limites["dependientes_economicos"] * UVT_2025
        return min(valor_deducido, limite_porcentaje, limite_uvt)
    
    elif tipo_deduccion == "medicina_prepagada":
        return min(valor_deducido, limites["medicina_prepagada"] * UVT_2025)
    
    elif tipo_deduccion == "rentas_exentas":
        #AGREGAR CONDICION DE DIVIDIR EL MONTO IDENTIFICADO POR LA IA POR 12 
        limite_porcentaje = ingreso_bruto * limites["rentas_exentas_porcentaje"]
        limite_uvt_mensual = (limites["rentas_exentas_uvt_anual"] * UVT_2025) / 12
        return min(valor_deducido, limite_porcentaje, limite_uvt_mensual)
    
    return 0

def obtener_constantes_articulo_383() -> Dict[str, Any]:
    """Obtiene todas las constantes del Artículo 383 para uso en prompts"""
    return {
        "uvt_2025": UVT_2025,
        "smmlv_2025": SMMLV_2025,
        "conceptos_aplicables": CONCEPTOS_ARTICULO_383,
        "tarifas": TARIFAS_ARTICULO_383,
        "limites_deducciones": LIMITES_DEDUCCIONES_ART383
    }

# ===============================
# CONFIGURACIÓN IMPUESTOS ESPECIALES INTEGRADOS
# ===============================

# IMPORTANTE: Desde 2025, estampilla pro universidad nacional y contribución 
# a obra pública aplican para los MISMOS NITs administrativos

# NITs válidos para AMBOS impuestos (estampilla + obra pública)
NITS_ESTAMPILLA_UNIVERSIDAD = {
    "8001781488": "Fiduciaria Colombiana de Comercio Exterior S.A",
    "830.054.060-5": "Fideicomisos Sociedad Fiduciaria Fiducoldex",
    "900.649.119-9": "Fondo Nacional del Turismo Fontur de la fiduciaria"
}

# Alias para compatibilidad hacia atrás - MISMO contenido
NITS_CONTRIBUCION_OBRA_PUBLICA = NITS_ESTAMPILLA_UNIVERSIDAD.copy()

# Terceros que administran recursos públicos (COMPARTIDO para ambos impuestos)
TERCEROS_RECURSOS_PUBLICOS = {
    "PATRIMONIO AUTONOMO INNPULSA COLOMBIA": True,
    "PATRIMONIO AUTONOMO COLOMBIA PRODUCTIVA": True,
    "PATRIMONIO AUTÓNOMO FONDO MUJER EMPRENDE": True
    # 💡 Expandible: Agregar más terceros aquí en el futuro
}

# Objetos de contrato que aplican para estampilla universidad
OBJETOS_CONTRATO_ESTAMPILLA = {
    "contrato_obra": {
        "palabras_clave": ["construcción", "mantenimiento", "instalación","TRABAJO MATERIAL"],
        "aplica": True
    },
    "interventoria": {
        "palabras_clave": ["interventoría", "interventoria"],
        "aplica": True
    },
    "servicios_conexos_obra": {
        "palabras_clave": [
            "estudios necesarios para la ejecución de proyectos de inversión",
            "estudios de diagnóstico",
            "estudios de prefactibilidad",
            "factibilidad para programas o proyectos",
            "asesorías tecnicas de coordinación",
            "asesorías de control",
            "asesorías de supervision",
            "asesoria",
            "gerencia de obra",
            "gerencia de proyectos dirección",
            "programación ejecución de diseño, planos, anteproyectos y proyectos",
            "diseño",
            "operación",
            "interventoria mantenimiento"
        ],
        "aplica": True
    }
}

# Objetos de contrato que aplican para contribución a obra pública (SOLO OBRA)
OBJETOS_CONTRATO_OBRA_PUBLICA = {
    "contrato_obra": {
        "palabras_clave": ["construcción", "mantenimiento", "instalación", "TRABAJO MATERIAL"],
        "aplica": True
    }
    # ⚠️ IMPORTANTE: Solo aplica para contrato de obra, NO interventoría ni servicios conexos
}

# Rangos UVT y tarifas para estampilla pro universidad nacional
RANGOS_ESTAMPILLA_UNIVERSIDAD = [
    {"desde_uvt": 26, "hasta_uvt": 52652, "tarifa": 0.005},      # 0.5%
    {"desde_uvt": 52652, "hasta_uvt": 157904, "tarifa": 0.01},   # 1.0%
    {"desde_uvt": 157904, "hasta_uvt": float('inf'), "tarifa": 0.02}  # 2.0%
]

# ===============================
# FUNCIONES ESTAMPILLA UNIVERSIDAD
# ===============================

def nit_aplica_estampilla_universidad(nit: str) -> bool:
    """Verifica si un NIT aplica para estampilla pro universidad nacional"""
    return nit in NITS_ESTAMPILLA_UNIVERSIDAD

def es_tercero_recursos_publicos(nombre_tercero: str) -> bool:
    """Verifica si un tercero administra recursos públicos"""
    nombre_upper = nombre_tercero.upper().strip()
    return nombre_upper in TERCEROS_RECURSOS_PUBLICOS

def obtener_tarifa_estampilla_universidad(valor_contrato_pesos: float) -> Dict[str, Any]:
    """Obtiene la tarifa de estampilla según el valor del contrato en pesos"""
    valor_uvt = valor_contrato_pesos / UVT_2025
    
    for rango in RANGOS_ESTAMPILLA_UNIVERSIDAD:
        if rango["desde_uvt"] <= valor_uvt < rango["hasta_uvt"]:
            return {
                "tarifa": rango["tarifa"],
                "rango_desde_uvt": rango["desde_uvt"],
                "rango_hasta_uvt": rango["hasta_uvt"],
                "valor_contrato_uvt": valor_uvt,
                "uvt_2025": UVT_2025
            }
    
    # Por defecto, rango más bajo si no encuentra
    return {
        "tarifa": RANGOS_ESTAMPILLA_UNIVERSIDAD[0]["tarifa"],
        "rango_desde_uvt": RANGOS_ESTAMPILLA_UNIVERSIDAD[0]["desde_uvt"],
        "rango_hasta_uvt": RANGOS_ESTAMPILLA_UNIVERSIDAD[0]["hasta_uvt"],
        "valor_contrato_uvt": valor_uvt,
        "uvt_2025": UVT_2025
    }

def obtener_configuracion_estampilla_universidad() -> Dict[str, Any]:
    """Obtiene toda la configuración de estampilla para uso en prompts"""
    return {
        "nits_validos": NITS_ESTAMPILLA_UNIVERSIDAD,
        "terceros_recursos_publicos": list(TERCEROS_RECURSOS_PUBLICOS.keys()),
        "objetos_contrato": OBJETOS_CONTRATO_ESTAMPILLA,
        "rangos_uvt": RANGOS_ESTAMPILLA_UNIVERSIDAD,
        "uvt_2025": UVT_2025
    }

# ===============================
# FUNCIONES CONTRIBUCIÓN A OBRA PÚBLICA
# ===============================

def nit_aplica_contribucion_obra_publica(nit: str) -> bool:
    """Verifica si un NIT aplica para contribución a obra pública del 5%"""
    return nit in NITS_CONTRIBUCION_OBRA_PUBLICA

def calcular_contribucion_obra_publica(valor_factura_sin_iva: float, porcentaje_participacion: float = 100.0) -> float:
    """Calcula la contribución a obra pública del 5%
    
    Args:
        valor_factura_sin_iva: Valor de la factura sin IVA
        porcentaje_participacion: % de participación (para consorcios)
    
    Returns:
        float: Valor de la contribución a obra pública
    """
    tarifa_fija = 0.05  # 5% fijo
    participacion_decimal = porcentaje_participacion / 100.0
    return valor_factura_sin_iva * tarifa_fija * participacion_decimal

def obtener_configuracion_obra_publica() -> Dict[str, Any]:
    """Obtiene toda la configuración de obra pública para uso en prompts"""
    return {
        "nits_validos": NITS_CONTRIBUCION_OBRA_PUBLICA,
        "terceros_recursos_publicos": list(TERCEROS_RECURSOS_PUBLICOS.keys()),
        "objetos_contrato": OBJETOS_CONTRATO_OBRA_PUBLICA,
        "tarifa_fija": 0.05,  # 5%
        "uvt_2025": UVT_2025
    }

# ===============================
# FUNCIÓN INTEGRADA DE DETECCIÓN AUTOMÁTICA
# ===============================

def detectar_impuestos_aplicables(nit: str) -> Dict[str, Any]:
    """Detecta automáticamente qué impuestos aplican según el NIT
    
    Args:
        nit: NIT administrativo
        
    Returns:
        Dict con información de qué impuestos aplican
    """
    aplica_estampilla = nit_aplica_estampilla_universidad(nit)
    aplica_obra_publica = nit_aplica_contribucion_obra_publica(nit)
    
    return {
        "nit": nit,
        "aplica_estampilla_universidad": aplica_estampilla,
        "aplica_contribucion_obra_publica": aplica_obra_publica,
        "impuestos_aplicables": [
            impuesto for impuesto, aplica in [
                ("ESTAMPILLA_UNIVERSIDAD", aplica_estampilla),
                ("CONTRIBUCION_OBRA_PUBLICA", aplica_obra_publica)
            ] if aplica
        ],
        "procesamiento_paralelo": aplica_estampilla and aplica_obra_publica,
        "nombre_entidad_estampilla": NITS_ESTAMPILLA_UNIVERSIDAD.get(nit),
        "nombre_entidad_obra_publica": NITS_CONTRIBUCION_OBRA_PUBLICA.get(nit)
    }

def obtener_configuracion_impuestos_integrada() -> Dict[str, Any]:
    """Obtiene configuración integrada para ambos impuestos"""
    return {
        "estampilla_universidad": obtener_configuracion_estampilla_universidad(),
        "contribucion_obra_publica": obtener_configuracion_obra_publica(),
        "terceros_recursos_publicos_compartidos": list(TERCEROS_RECURSOS_PUBLICOS.keys())
    }

# ===============================
# CONFIGURACIÓN IVA Y RETEIVA
# ===============================

# NITs de la fiduciaria que aplican IVA y ReteIVA
NITS_IVA_RETEIVA = {
    "8001781488": {
        "nombre": "Fiduciaria Colombiana de Comercio Exterior S.A.",
        "aplica_iva": True,
        "aplica_reteiva": True
    },
    "830054060": {
        "nombre": "FIDEICOMISOS SOCIEDAD FIDUCIARIA FIDUCOLDEX",
        "aplica_iva": True,
        "aplica_reteiva": True
    },
    "900649119": {
        "nombre": "PATRIMONIO AUTÓNOMO FONTUR",
        "aplica_iva": True,
        "aplica_reteiva": True
    }
}

# Diccionarios de bienes y servicios relacionados con IVA (inicialmente vacíos)
BIENES_NO_CAUSAN_IVA = {
    "1": "Animales vivos de la especie porcina",
    "2": "Animales vivos de las especies ovina o caprina",
    "3": "Gallos, gallinas, patos, gansos, pavos (gallipavos) y pintadas, de las especies domésticas, vivos",
    "4": "Los demás animales vivos, excepto los animales domésticos de compañía",
    "5": "Peces vivos, excepto los peces ornamentales",
    "6": "Albacoras o atunes blancos",
    "7": "Atunes de aleta amarilla (rabiles)",
    "8": "Atunes comunes o de aleta azul, del Atlántico y del Pacífico",
    "9": "Pescado seco, salado o en salmuera, pescado ahumado, incluso cocido antes o durante el ahumado, harina, polvo y «pellets» de pescado, aptos para la alimentación humana",
    "10": "Productos constituidos por los componentes naturales de la leche",
    "11": "Miel natural",
    "12": "Semen de Bovino",
    "13": "Bulbos, cebollas, tubérculos, raíces y bulbos tuberosos, turiones y rizomas, en reposo vegetativo, en vegetación o en flor, plantas y raíces de achicoria, excepto las raíces",
    "14": "Las demás plantas vivas (incluidas sus raíces), esquejes e injertos; micelios",
    "15": "Plántulas para la siembra, incluso de especies forestales maderables",
    "16": "Papas (patatas) frescas o refrigeradas",
    "17": "Tomates frescos o refrigerados",
    "18": "Cebollas, chalotes, ajos, puerros y demás hortalizas aliáceas, frescos o refrigerados",
    "19": "Coles, incluidos los repollos, coliflores, coles rizadas, colinabos y productos comestibles similares del género Brassica, frescos o refrigerados",
    "20": "Lechugas (Lactuca sativa) y achicorias, comprendidas la escarola y la endibia (Cichoriumspp), frescas o refrigeradas",
    "21": "Zanahorias, nabos, remolachas para ensalada, salsifies, apionabos, rábanos y raíces comestibles similares, frescos o refrigerados",
    "22": "Pepinos y pepinillos, frescos o refrigerados",
    "23": "Hortalizas de vaina, aunque estén desvainadas, frescas o refrigeradas",
    "24": "Las demás hortalizas, frescas o refrigeradas",
    "25": "Hortalizas secas, incluidas las cortadas en trozos o en rodajas o las trituradas o pulverizadas, pero sin otra preparación",
    "26": "Hortalizas de vaina secas desvainadas, aunque estén mondadas o partidas",
    "27": "Raíces de yuca (mandioca), arrurruz o salep, aguaturmas (patacas), camotes (batatas, boniatos) y raíces y tubérculos similares ricos en fécula o inulina, frescos, refrigerados, congelados o secos, incluso troceados o en «pellets», médula de sagú",
    "28": "Cocos con la cáscara interna (endocarpio)",
    "29": "Los demás cocos frescos",
    "30": "Bananas, incluidos los plátanos «plantains», frescos o secos",
    "31": "Dátiles, higos, piñas (ananás), aguacates (paltas), guayabas, mangos y mangostanes, frescos o secos",
    "32": "Agrios (cítricos) frescos o secos",
    "33": "Uvas, frescas o secas, incluidas las pasas",
    "34": "Melones, sandías y papayas, frescos",
    "35": "Manzanas, peras y membrillos, frescos",
    "36": "Damascos (albaricoques, chabacanos), cerezas, duraznos (melocotones) (incluidos los griñones nectarines), ciruelas y endrinas, frescos",
    "37": "Las demás frutas u otros frutos, frescos",
    "38": "Café en grano sin tostar, cáscara y cascarilla de café",
    "39": "Semillas de cilantro para la siembra",
    "40": "Trigo duro para la siembra",
    "41": "Las demás semillas de trigo para la siembra",
    "42": "Centeno para la siembra",
    "43": "Cebada",
    "44": "Avena para la siembra",
    "45": "Maíz para la siembra",
    "46": "Maíz para consumo humano",
    "47": "Arroz para consumo humano",
    "48": "Arroz para la siembra",
    "49": "Arroz con cáscara (Arroz Paddy)",
    "50": "Sorgo de grano para la siembra",
    "51": "Maíz trillado para consumo humano",
    "52": "Habas de soya para la siembra",
    "53": "Maníes (cacahuetes, cacahuates) para la siembra",
    "54": "Copra para la siembra",
    "55": "Semillas de lino para la siembra",
    "56": "Semillas de nabo (nabina) o de colza para siembra",
    "57": "Semillas de girasol para la siembra",
    "58": "Semillas de nueces y almendras de palma para la siembra",
    "59": "Semillas de algodón para la siembra",
    "60": "Semillas de ricino para la siembra",
    "61": "Semillas de sésamo (ajonjolí) para la siembra",
    "62": "Semillas de mostaza para la siembra",
    "63": "Semillas de cártamo para la siembra",
    "64": "Semillas de melón para la siembra",
    "65": "Las demás semillas y frutos oleaginosos para la siembra",
    "66": "Semillas, frutos y esporas, para siembra",
    "67": "Caña de azúcar",
    "68": "Chancaca (panela, raspadura) obtenida de la extracción y evaporación en forma artesanal de los jugos de caña de azúcar en trapiches paneleros",
    "69": "Cacao en grano para la siembra",
    "70": "Cacao en grano crudo",
    "71": "Únicamente la Bienestarina",
    "72": "Productos alimenticios elaborados de manera artesanal a base de leche",
    "73": "Pan horneado o cocido y producido a base principalmente de harinas de cereales, con o sin levadura, sal o dulce, sea integral o no",
    "74": "Productos alimenticios elaborados de manera artesanal a base de guayaba",
    "75": "Agua, incluidas el agua mineral natural o artificial y la gaseada, sin adición de azúcar u otro edulcorante ni aromatizada, hielo y nieve",
    "76": "Sal (incluidas la de mesa y la desnaturalizada) y cloruro de sodio puro, incluso en disolución acuosa o con adición de antiaglomerantes",
    "77": "Azufre de cualquier clase, excepto el sublimado, el precipitado y el coloidal",
    "78": "Fosfatos de calcio naturales, fosfatos aluminocálcicos naturales y cretas fosfatadas",
    "79": "Dolomita sin calcinar ni sinterizar, llamada «cruda»",
    "80": "Hullas, briquetas, ovoides y combustibles sólidos similares, obtenidos de la hulla",
    "81": "Coques y semicoques de hulla",
    "82": "Coques y semicoques de lignito o turba",
    "83": "Gas natural licuado",
    "84": "Gas propano únicamente para uso domiciliario",
    "85": "Butanos licuados",
    "86": "Gas natural en estado gaseoso, incluido el biogás",
    "87": "Gas propano en estado gaseoso únicamente para uso domiciliario y gas butano en estado gaseoso",
    "88": "Energía eléctrica",
    "89": "Material radiactivo para uso médico",
    "90": "Guatas, gasas, vendas y artículos análogos impregnados o recubiertos de sustancias farmacéuticas",
    "91": "Abonos de origen animal o vegetal, incluso mezclados entre sí o tratados químicamente",
    "92": "Abonos minerales o químicos nitrogenados",
    "93": "Abonos minerales o químicos fosfatados",
    "94": "Abonos minerales o químicos potásicos",
    "95": "Abonos minerales o químicos con dos o tres de los elementos fertilizantes: nitrógeno, fósforo y potasio",
    "96": "Insecticidas, raticidas y demás antirroedores, fungicidas, herbicidas, inhibidores de germinación",
    "97": "Reactivos de diagnóstico sobre cualquier soporte y reactivos de diagnóstico preparados",
    "98": "Caucho natural",
    "99": "Neumáticos de los tipos utilizados en vehículos y máquinas agrícolas o forestales",
    "100": "Preservativos",
        "101": "Papel prensa en bobinas (rollos) o en hojas",
    "102": "Los demás papeles prensa en bobinas (rollos)",
    "103": "Pita (Cabuya, fique)",
    "104": "Tejidos de las demás fibras textiles vegetales",
    "105": "Redes confeccionadas para la pesca",
    "106": "Empaques de yute, cáñamo y fique",
    "107": "Sacos (bolsas)y talegas, para envasar de yute",
    "108": "Sacos (bolsas) y talegas, para envasar de pita (cabuya, fique)",
    "109": "Sacos (bolsas) y talegas, para envasar de cáñamo",
    "110": "Ladrillos de construcción y bloques de calicanto, de arcilla, y con base en cemento, bloques de arcilla silvocalcarea",
    "111": "Monedas de curso legal",
    "112": "Motores fuera de borda, hasta 115HP",
    "113": "Motores Diesel hasta 150HP",
    "114": "Sistemas de riego por goteo o aspersión",
    "115": "Los demás sistemas de riego",
    "116": "Aspersores y goteros, para sistemas de riego",
    "117": "Guadañadoras, incluidas las barras de corte para montar sobre un tractor",
    "118": "Las demás máquinas y aparatos de henificar",
    "119": "Prensas para paja o forraje, incluidas las prensas recogedoras",
    "120": "Cosechadoras-trilladoras",
    "121": "Las demás máquinas y aparatos de trillar",
    "122": "Máquinas de cosechar raíces o tubérculos",
    "123": "Las demás máquinas y aparatos de cosechar, máquinas y aparatos de trillar",
    "124": "Máquinas para limpieza o clasificación de huevos, frutos o demás productos agrícolas",
    "125": "Partes de máquinas, aparatos y artefactos de cosechar o trillar, incluidas las prensas para paja o forraje, cortadoras de césped y guadañadoras, máquinas para limpieza o clasificación de huevos, frutos o demás productos agrícolas, excepto las de la partida 8437",
    "126": "Máquinas y aparatos para preparar alimentos o piensos para animales",
    "127": "Las demás máquinas y aparatos para uso agropecuario",
    "128": "Partes de las demás máquinas y aparatos para uso agropecuario",
    "129": "Máquinas para limpieza, clasificación o cribado de semillas, granos u hortalizas de vaina secas",
    "130": "Tractores para uso agropecuario",
    "131": "Tractores para uso agropecuario",
    "132": "Sillones de ruedas y demás vehículos para inválidos, incluso con motor u otro mecanismo de propulsión",
    "133": "Partes y accesorios de sillones de ruedas y demás vehículos para inválidos",
    "134": "Remolques y semirremolques, autocargadores o autodescargadores, para uso agrícola",
    "135": "Lentes de contacto",
    "136": "Lentes de vidrio para gafas",
    "137": "Lentes de otras materias para gafas",
    "138": "Catéteres y catéteres peritoneales y equipos para la infusión de líquidos y filtros para diálisis renal de esta subpartida",
    "139": "Equipos para la infusión de sangre",
    "140": "Artículos y aparatos de ortopedia, incluidas las fajas y vendajes médicoquirúrgicos y las muletas tablillas, férulas u otros artículos y aparatos para fracturas, artículos y aparatos de prótesis, audífonos y demás aparatos que lleve la propia persona o se le implanten para compensar un defecto o incapacidad; las impresoras braille, máquinas inteligentes de lectura para ciegos, software lector de pantalla para ciegos, estereotipadoras braille, líneas braille, regletas braille, cajas aritméticas y de dibujo braille, elementos manuales o mecánicos de escritura del sistema braille, así como los bastones para ciegos aunque estén dotados de tecnología, contenidos en esta partida arancelaria",
    "141": "Lápices de escribir y colorear",
    "142": "Las materias primas químicas con destino a la producción de plaguicidas e insecticidas y de los fertilizantes y con destino a la producción de medicamentos",
    "143": "Las materias primas destinadas a la producción de vacunas para lo cual deberá acreditarse tal condición en la forma como lo señale el reglamento",
    "144": "Todos los productos de soporte nutricional (incluidos los suplementos dietarios y los complementos nutricionales en presentaciones líquidas, sólidas, granuladas, gaseosas, en polvo) del régimen especial destinados a ser administrados por vía enteral, para pacientes con patologías específicas o con condiciones especiales; y los alimentos para propósitos médicos especiales para pacientes que requieren nutrición enteral por sonda a corto o largo plazo",
    "145": "Los dispositivos anticonceptivos para uso femenino",
    "146": "Los computadores personales de escritorio o portátiles, cuyo valor no exceda de cincuenta (50) UVT",
    "147": "Los dispositivos móviles inteligentes (tabletas y celulares) cuyo valor no exceda de veintidós (22) UVT",
    "148": "Los equipos y elementos nacionales o importados que se destinen a la construcción, instalación, montaje y operación de sistemas de control y monitoreo, necesarios para el cumplimiento de las disposiciones, regulaciones y estándares ambientales vigentes, para lo cual deberá acreditarse tal condición ante el Ministerio de Ambiente y Desarrollo Sostenible",
    "149": "Los alimentos de consumo humano y animal que se importen de los países colindantes a los departamentos de Vichada, Guajira, Guainía y Vaupés, siempre y cuando se destinen exclusivamente al consumo local en esos departamentos",
    "150": "Los alimentos aptos para el consumo humano así como bienes de higiene y aseo, donados a favor de los bancos de alimentos que se encuentren constituidos como entidades sin ánimo de lucro del Régimen Tributario Especial, los bancos de alimentos que bajo la misma personería jurídica posea la iglesia o confesión religiosa reconocida por el Ministerio del Interior o por la ley y las asociaciones de bancos de alimentos (Modificado Ley 2380 de 2024)",
    "151": "Los vehículos, automotores, destinados al transporte público de pasajeros, destinados solo a reposición. Tendrán derecho a este beneficio los pequeños transportadores propietarios de menos de 3 vehículos y solo para efectos de la reposición de uno solo, y por una única vez. Este beneficio tendrá una vigencia hasta el año 2019",
    "152": "Los objetos con interés artístico, cultural e histórico comprados por parte de los museos que integren la Red Nacional de Museos y las entidades públicas que posean o administren estos bienes, estarán exentos del cobro del IVA",
    "153": "La venta de bienes inmuebles",
    "154": "El consumo humano y animal, vestuario, elementos de aseo y medicamentos para uso humano o veterinario, materiales de construcción que se introduzcan y comercialicen a los departamentos de Guainía, Guaviare, Vaupés y Vichada, siempre y cuando se destinen exclusivamente al consumo dentro del mismo departamento. El Gobierno nacional reglamentará la materia para garantizar que la exclusión del IVA se aplique en las ventas al consumidor final",
    "155": "El combustible para aviación que se suministre para el servicio de transporte aéreo nacional de pasajeros y de carga con origen y destino a los departamentos de Guainía, Amazonas, Vaupés, San Andrés Islas y Providencia, Arauca y Vichada",
    "156": "Los productos que se compren o introduzcan al departamento del Amazonas en el marco del convenio Colombo-Peruano y el convenio con la República Federativa del Brasil",
    "157": "La compraventa de maquinaria y equipos destinados al desarrollo de proyectos o actividades que se encuentren registrados en el Registro Nacional de Reducción de Emisiones de Gases Efecto Invernadero definido en el artículo 155 de la Ley 1753 de 2015, que generen y certifiquen reducciones de Gases Efecto Invernadero - GEl, según reglamentación que expida el Ministerio de Ambiente y Desarrollo Sostenible. (GEMINI: SE DEBE VALIDAR MANUALMENTE SI EL PROYECTO SE ENCUENTRA REGISTRADO en el Registro Nacional de Reducción de Emisiones de Gases Efecto Invernadero definido en el artículo 155 de la Ley 1753 de 2015)",
    "158": "Las bicicletas, bicicletas eléctricas, motos eléctricas, patines, monopatines, monopatines eléctricos, patinetas, y patinetas eléctricas, de hasta 50 UVT",
    "159": "La venta de los bienes facturados por los comerciantes (librero): se entiende por librero la persona natural o jurídica que se dedica exclusivamente a la venta de libros, revistas, folletos o coleccionables seriados de carácter científico o cultural, en establecimientos mercantiles legalmente habilitados y de libre acceso al público consumidor",
    "160": "Incentivos de premio inmediato de Juegos de suerte y azar territoriales",
    "161": "El petróleo crudo recibido por parte de la Agencia Nacional de Hidrocarburos por concepto de pago de regalías para su respectiva monetización",
    "162": "Para los efectos del presente artículo y de conformidad con la reglamentación vigente expedida por el Ministerio de Salud y el Instituto Colombiano Agropecuario, se entienden como animales domésticos de compañía los gatos, perros, hurones, conejos, chinchillas, hámster, cobayos, jerbos y Mini-Pigs"
}
BIENES_EXENTOS_IVA = {
    
    "1": "Animales vivos de la especie bovina, excepto los de lidia.",
    "2": "Pollitos de un día de nacidos.",
    "3": "Carne de animales de la especie bovina, fresca o refrigerada.",
    "4": "Carne de animales de la especie bovina, congelada.",
    "5": "Carne de animales de la especie porcina, fresca, refrigerada o congelada.",
    "6": "Carne de animales de las especies ovina o caprina, fresca, refrigerada o congelada.",
    "7": "Despojos comestibles de animales de las especies bovina, porcina, ovina, caprina, caballar, asnal o mular, frescos, refrigerados o congelados.",
    "8": "Carne y despojos comestibles, de aves, refrigerados o congelados.",
    "9": "Carnes y despojos comestibles de conejo o liebre, frescos, refrigerados o congelados.",
    "10": "Pescado fresco o refrigerado, excepto los filetes y demás carne de pescado.",
    "11": "Pescado congelado, excepto los filetes y demás carne de pescado (con excepciones).",
    "12": "Filetes y demás carne de pescado (incluso picada), frescos, refrigerados o congelados.",
    "13": "Únicamente camarones de cultivo.",
    "14": "Leche y nata (crema), sin concentrar, sin adición de azúcar ni otro edulcorante.",
    "15": "Leche y nata (crema), concentradas o con adición de azúcar u otro edulcorante.",
    "16": "Queso fresco (sin madurar), incluido el lactosuero, y requesón.",
    "17": "Huevos de gallina de la especie Gallus domesticus, fecundados para incubación.",
    "18": "Huevos fecundados para incubación de las demás aves.",
    "19": "Huevos frescos de gallina.",
    "20": "Huevos frescos de las demás aves.",
    "21": "Arroz para consumo humano (excepto el arroz con cáscara o 'Arroz Paddy' y el arroz para la siembra, los cuales conservan la calidad de bienes excluidos del IVA).",
    "22": "Fórmulas lácteas para niños de hasta 12 meses de edad, únicamente la leche maternizada o humanizada.",
    "23": "Únicamente preparaciones infantiles a base de leche.",
    "24": "Provitaminas y vitaminas, naturales o reproducidas por síntesis (incluidos los concentrados naturales) y sus derivados utilizados principalmente como vitaminas, mezclados o no entre sí o en disoluciones de cualquier clase.",
    "25": "Antibióticos.",
    "26": "Glándulas y demás órganos para usos opoterápicos, desecados, incluso pulverizados; extractos de glándulas o de otros órganos o de sus secreciones para usos opoterápicos; heparina y sus sales; las demás sustancias humanas o animales preparadas para usos terapéuticos o profilácticos no expresadas ni comprendidas en otra parte.",
    "27": "Sangre humana, sangre animal preparada para usos terapéuticos, profilácticos o de diagnóstico; antisueros (sueros con anticuerpos); demás fracciones de la sangre y productos inmunológicos modificados, incluso obtenidos por proceso biotecnológico; vacunas, toxinas, cultivos de microrganismos (excepto las levaduras) y productos similares.",
    "28": "Medicamentos (revisar excepciones) constituidos por productos mezclados entre sí, preparados para usos terapéuticos o profilácticos, sin dosificar ni acondicionar para la venta al por menor.",
    "29": "Medicamentos (revisar excepciones) constituidos por productos mezclados o sin mezclar, preparados para usos terapéuticos o profilácticos, dosificados o acondicionados para la venta al por menor.",
    "30": "Preparaciones y artículos farmacéuticos a que se refiere la nota 4 de este capítulo.",
    "31": "Inversor de energía para sistema de energía solar con paneles.",
    "32": "Paneles solares.",
    "33": "Controlador de carga para sistema de energía solar con paneles.",
    "34": "Armas de guerra, excepto los revólveres, pistolas y armas blancas, de uso privativo de las Fuerzas Militares y la Policía Nacional.",
    "35": "Compresas y toallas higiénicas.",
    "36": "Las municiones y material de guerra o reservado y, por consiguiente, de uso privativo, y los siguientes elementos pertenecientes a las Fuerzas Militares y la Policía Nacional: a) Sistemas de armas y armamento mayor y menor con sus accesorios, repuestos y elementos necesarios para instrucción, operación y mantenimiento; b) Naves, artefactos navales y aeronaves destinados al servicio del Ramo de Defensa Nacional con sus accesorios y repuestos; c) Municiones, torpedos y minas; d) Material blindado; e) Semovientes destinados al mantenimiento del orden público; f) Materiales explosivos y pirotécnicos, materias primas para su fabricación y accesorios; g) Paracaídas y equipos de salto; h) Elementos, equipos y accesorios contra motines; i) Equipos de ingenieros de combate; j) Equipos de buceo y de voladuras submarinas; k) Equipos de detección aérea, de superficie y submarina; l) Elementos para control de incendios y averías; m) Herramientas y equipos para pruebas y mantenimiento; n) Equipos, software y demás implementos de sistemas y comunicaciones para uso de las Fuerzas Militares y la Policía Nacional; o) Otros elementos aplicables al servicio y fabricación del material de guerra o reservado; p) Servicios de diseño, construcción y mantenimiento de armas, municiones y material de guerra con destino a la fuerza pública, así como capacitación de tripulaciones, prestados por entidades descentralizadas del sector defensa.",
    "37": "Los vehículos automotores de transporte público de pasajeros completos y el chasis con motor y la carrocería adquiridos individualmente para conformar un vehículo automotor completo nuevo, de transporte público de pasajeros. Beneficio aplicable a ventas a pequeños transportadores propietarios de hasta dos (2) vehículos, para reposición de uno o dos vehículos propios, por única vez; vigencia de cinco (5) años.",
    "38": "Los vehículos automotores de servicio público o particular de transporte de carga completos y el chasis con motor y la carrocería adquiridos individualmente para conformar un vehículo automotor completo nuevo de transporte de carga de más de 10.5 toneladas de peso bruto vehicular. Beneficio aplicable a ventas a pequeños transportadores propietarios de hasta dos (2) vehículos, para reposición de uno o dos vehículos propios, por única vez; vigencia de cinco (5) años.",
    "39": "Las bicicletas y sus partes; motocicletas y sus partes y motocarros y sus partes, que se introduzcan y comercialicen en los departamentos de Amazonas, Guainía, Guaviare, Vaupés y Vichada, siempre que se destinen exclusivamente al consumo dentro del mismo departamento y las motocicletas y motocarros sean registrados en el departamento. También estarán exentos los bienes indicados anteriormente que se importen al territorio aduanero nacional y se destinen posteriormente exclusivamente a estos departamentos.",
    "40": "El Gobierno nacional reglamentará la materia para que la exención del IVA se aplique en las ventas al consumidor final y para que los importadores ubicados fuera de los territorios indicados puedan descontar a su favor, en la cuenta corriente del IVA, el valor total pagado en la nacionalización y las compras nacionales cuando las mercancías se comercialicen con destino exclusivo a los departamentos señalados.",
    "41": "El consumo humano y animal, vestuario, elementos de aseo y medicamentos para uso humano o veterinario, materiales de construcción que se introduzcan y comercialicen al departamento de Amazonas, siempre que se destinen exclusivamente al consumo dentro del mismo departamento. Requisitos: a) El adquiriente sea sociedad constituida y domiciliada en el Departamento del Amazonas y cuya actividad económica se realice únicamente en dicho departamento; b) El adquiriente esté inscrito en factura electrónica; c) El documento de transporte aéreo y/o fluvial debe garantizar que las mercancías ingresan efectivamente al Departamento del Amazonas y se enajenan únicamente a consumidores finales allí ubicados.",
    "42": "Las ventas de libros y revistas de carácter científico y cultural, según la calificación que hará el Gobierno Nacional.",
    "43": "Exenciones para: bienes corporales muebles que se exporten; servicio de reencauche; servicios de reparación a embarcaciones marítimas y aerodinos de bandera o matrícula extranjera; y la venta en el país de bienes de exportación a sociedades de comercialización internacional siempre que hayan de ser efectivamente exportados.",
    "44": "Exenciones para ventas e importaciones de bienes y equipos destinados al deporte, a la salud, a la investigación científica y tecnológica, y a la educación, donados a favor de entidades oficiales o sin ánimo de lucro, por personas o entidades nacionales o por entidades, personas o gobiernos extranjeros, siempre que obtengan calificación favorable en el comité previsto en el artículo 362. También las importaciones de bienes y equipos para la seguridad nacional con destino a la Fuerza Pública.",
    "45": "Ventas e importaciones de bienes y equipos efectuadas en desarrollo de convenios, tratados, acuerdos internacionales e interinstitucionales o proyectos de cooperación, donados a favor del Gobierno Nacional o entidades de derecho público del orden nacional por personas naturales o jurídicas, organismos multilaterales o gobiernos extranjeros, según reglamento que expida el Gobierno Nacional."

    
}

SERVICIOS_EXCLUIDOS_IVA = {
  "1": "Los servicios médicos, odontológicos, hospitalarios, clínicos y de laboratorio, para la salud humana.",
    "2": "Los servicios de administración de fondos del Estado y los servicios vinculados con la seguridad social de acuerdo con lo previsto en la Ley 100 de 1993.",
    "3": "Los planes obligatorios de salud del sistema de seguridad social en salud expedidos por entidades autorizadas por la Superintendencia Nacional de Salud, los servicios prestados por las administradoras dentro del régimen de ahorro individual con solidaridad y de prima media con prestación definida, los servicios prestados por administradoras de riesgos laborales y los servicios de seguros y reaseguros para invalidez y sobrevivientes, contemplados dentro del régimen de ahorro individual con solidaridad a que se refiere el artículo 135 de la Ley 100 de 1993 o las disposiciones que la modifiquen o sustituyan.",
    "4": "Las comisiones por intermediación por la colocación de los planes de salud del sistema general de seguridad social en salud expedidos por las entidades autorizadas legalmente por la Superintendencia Nacional de Salud, que no estén sometidos al impuesto sobre las ventas - IVA.",
    "5": "Los servicios de educación prestados por establecimientos de educación preescolar, primaria, media e intermedia, superior y especial o no formal, reconocidos como tales por el Gobierno nacional, y los servicios de educación prestados por personas naturales a dichos establecimientos. Están excluidos igualmente los servicios prestados por los establecimientos de educación relativos a restaurantes, cafeterías y transporte, así como los que se presten en desarrollo de las Leyes 30 de 1992 y 115 de 1994, o las disposiciones que las modifiquen o sustituyan. Igualmente están excluidos los servicios de evaluación de la educación y de elaboración y aplicación de exámenes para la selección y promoción de personal, prestados por organismos o entidades de la administración pública.",
    "6": "Los servicios de educación virtual para el desarrollo de contenidos digitales, de acuerdo con la reglamentación expedida por el Ministerio de Tecnologías de la Información y las Comunicaciones, prestados en Colombia o en el exterior.",
    "7": "Los servicios de conexión y acceso a internet de los usuarios residenciales del estrato 3.",
    "8": "En el caso del servicio telefónico local, se excluyen del impuesto los primeros trescientos veinticinco (325) minutos mensuales del servicio telefónico local facturado a los usuarios de los estratos 1, 2 y 3 y el servicio telefónico prestado desde teléfonos públicos.",
    "9": "El servicio de transporte público, terrestre, fluvial y marítimo de personas en el territorio nacional, y el de transporte público o privado nacional e internacional de carga marítimo, fluvial, terrestre y aéreo. Igualmente, se excluye el transporte de gas e hidrocarburos.",
    "10": "El transporte aéreo nacional de pasajeros con destino o procedencia de rutas nacionales donde no exista transporte terrestre organizado. Esta exclusión también aplica para el transporte aéreo turístico con destino o procedencia al departamento de La Guajira y los municipios de Nuquí (Chocó), Mompóx (Bolívar), Tolú (Sucre), Miraflores (Guaviare) y Puerto Carreño (Vichada).",
    "11": "Los servicios públicos de energía. La energía y los servicios públicos de energía a base de gas u otros insumos.",
    "12": "El agua para la prestación del servicio público de acueducto y alcantarillado, los servicios públicos de acueducto y alcantarillado, los servicios de aseo público y los servicios públicos de recolección de basuras.",
    "13": "El gas para la prestación del servicio público de gas domiciliario y el servicio de gas domiciliario, ya sea conducido por tubería o distribuido en cilindros.",
    "14": "Los servicios de alimentación, contratados con recursos públicos, destinados al sistema penitenciario, de asistencia social, de escuelas de educación pública, a las Fuerzas Militares, Policía Nacional, Centro de Desarrollo Infantil, centros geriátricos públicos, hospitales públicos y comedores comunitarios.",
    "15": "El servicio de arrendamiento de inmuebles para vivienda y el arrendamiento de espacios para exposiciones y muestras artesanales nacionales, incluidos los eventos artísticos y culturales.",
    "16": "Los intereses y rendimientos financieros por operaciones de crédito, siempre que no formen parte de la base gravable señalada en el artículo 447, y el arrendamiento financiero (leasing).",
    "17": "Los servicios de intermediación para el pago de incentivos o transferencias monetarias condicionadas en el marco de los programas sociales del Gobierno Nacional.",
    "18": "Las boletas de entrada a cine, a los eventos deportivos, culturales (incluidos los musicales) y de recreación familiar. También se encuentran excluidos los servicios de que trata el artículo 6° de la Ley 1493 de 2011.",
    "19": "Los servicios funerarios, los de cremación, inhumación y exhumación de cadáveres, alquiler y mantenimiento de tumbas y mausoleos.",
    "20": "Adquisición de licencias de software para el desarrollo comercial de contenidos digitales, de acuerdo con la reglamentación expedida por el Ministerio de Tecnologías de la Información y Comunicaciones.",
    "21": "Suministro de páginas web, servidores (hosting), computación en la nube (cloud computing).",
    "22": "Las comisiones pagadas por los servicios que se presten para el desarrollo de procesos de titularización de activos a través de universalidades y patrimonios autónomos cuyo pago se realice exclusivamente con cargo a los recursos de tales universalidades o patrimonios autónomos.",
    "23": "Las comisiones percibidas por las sociedades fiduciarias, sociedades administradoras de inversión y comisionistas de bolsa por la administración de fondos de inversión colectiva.",
    "24": "Los siguientes servicios, siempre que se destinen a la adecuación de tierras, a la producción agropecuaria y pesquera y a la comercialización de los respectivos productos:\n"
          "a) El riego de terrenos dedicados a la explotación agropecuaria;\n"
          "b) El diseño de sistemas de riego, su instalación, construcción, operación, administración y conservación;\n"
          "c) La construcción de reservorios para la actividad agropecuaria;\n"
          "d) La preparación y limpieza de terrenos de siembra;\n"
          "e) El control de plagas, enfermedades y malezas, incluida la fumigación aérea y terrestre de sembradíos;\n"
          "f) El corte y recolección manual y mecanizada de productos agropecuarios;\n"
          "g) Aplicación de fertilizantes y elementos de nutrición edáfica y foliar de los cultivos;\n"
          "h) Aplicación de sales mineralizadas;\n"
          "i) Aplicación de enmiendas agrícolas;\n"
          "j) Aplicación de insumos como vacunas y productos veterinarios;\n"
          "k) El pesaje y el alquiler de corrales en ferias de ganado mayor y menor;\n"
          "l) La siembra;\n"
          "m) La construcción de drenajes para la agricultura;\n"
          "n) La construcción de estanques para la piscicultura;\n"
          "o) Los programas de sanidad animal;\n"
          "p) La perforación de pozos profundos para la extracción de agua;\n"
          "q) El desmonte de algodón, la trilla y el secamiento de productos agrícolas;\n"
          "r) La selección, clasificación y el empaque de productos agropecuarios sin procesamiento industrial;\n"
          "s) La asistencia técnica en el sector agropecuario;\n"
          "t) La captura, procesamiento y comercialización de productos pesqueros;\n"
          "u) El servicio de recaudo de derechos de acceso vehicular a las centrales mayoristas de abasto.",
    "25": "La comercialización de animales vivos, excepto los animales domésticos de compañía.",
    "26": "El servicio de faenamiento.",
    "27": "Están excluidos de IVA los servicios de hotelería y turismo que sean prestados en los municipios que integran las siguientes zonas de régimen aduanero especial: a) Zona de régimen aduanero especial de Urabá, Tumaco y Guapi; b) Zona de régimen aduanero especial de Inírida, Puerto Carreño, La Primavera y Cumaribo; c) Zona de régimen aduanero especial de Maicao, Uribía y Manaure.",
    "28": "Las operaciones cambiarias de compra y venta de divisas, así como las operaciones cambiarias sobre instrumentos derivados financieros.",
    "29": "Las comisiones percibidas por la utilización de tarjetas crédito y débito.",
    "30": "Los servicios de promoción y fomento deportivo prestados por los clubes deportivos definidos en el artículo 2 del Decreto Ley 1228 de 1995.",
    "31": "Los servicios de reparación y mantenimiento de naves y artefactos navales tanto marítimos como fluviales de bandera colombiana, excepto los servicios que se encuentran en el literal P) del numeral 3 del artículo 477 de este Estatuto.",
    "32": "Los servicios de publicidad en periódicos que registren ventas en publicidad a 31 de diciembre del año inmediatamente anterior inferiores a 180.000 UVT.",
    "33": "La publicidad en las emisoras de radio cuyas ventas sean inferiores a 30.000 UVT al 31 de diciembre del año inmediatamente anterior y programadoras de canales regionales de televisión cuyas ventas sean inferiores a 60.000 UVT al 31 de diciembre del año inmediatamente anterior. Aquellas que superen este monto se regirán por la regla general.",
    "34": "Las exclusiones previstas en este numeral no se aplicarán a las empresas que surjan como consecuencia de la escisión de sociedades que antes de la expedición de la presente Ley conformen una sola empresa ni a las nuevas empresas que se creen cuya matriz o empresa dominante se encuentre gravada con el IVA por este concepto.",
    "35": "Los servicios de corretaje de contratos de reaseguros."

}

# Configuración de tarifas ReteIVA
CONFIG_RETEIVA = {
    "tarifa_fuente_nacional": 0.15,    # 15% para fuente nacional
    "tarifa_fuente_extranjera": 1.0,   # 100% para fuente extranjera
    "porcentaje_iva_extranjero_esperado": 0.19  # 19% IVA esperado para extranjeros
}

# ===============================
# FUNCIONES IVA Y RETEIVA
# ===============================

def nit_aplica_iva_reteiva(nit: str) -> bool:
    """Verifica si un NIT aplica para análisis de IVA y ReteIVA"""
    return nit in NITS_IVA_RETEIVA

def obtener_configuracion_iva() -> Dict[str, Any]:
    """Obtiene toda la configuración de IVA para uso en prompts"""
    return {
        "nits_validos": NITS_IVA_RETEIVA,
        "bienes_no_causan_iva": BIENES_NO_CAUSAN_IVA,
        "bienes_exentos_iva": BIENES_EXENTOS_IVA,
        "servicios_excluidos_iva": SERVICIOS_EXCLUIDOS_IVA,
        "config_reteiva": CONFIG_RETEIVA
    }

def es_fuente_ingreso_nacional(respuestas_fuente: Dict[str, bool]) -> bool:
    """Determina si un servicio/bien es de fuente nacional según validaciones
    
    Args:
        respuestas_fuente: Diccionario con respuestas a preguntas de fuente
        
    Returns:
        bool: True si es fuente nacional, False si es extranjera
    """
    # Si CUALQUIERA de las respuestas es SÍ, es fuente nacional
    # Si TODAS son NO, es fuente extranjera
    return any(respuestas_fuente.values())

def calcular_reteiva(valor_iva: float, es_fuente_nacional: bool) -> float:
    """Calcula el valor de ReteIVA según la fuente
    
    Args:
        valor_iva: Valor del IVA calculado
        es_fuente_nacional: True si es fuente nacional, False si extranjera
        
    Returns:
        float: Valor de ReteIVA calculado
    """
    config = CONFIG_RETEIVA
    
    if es_fuente_nacional:
        return valor_iva * config["tarifa_fuente_nacional"]
    else:
        return valor_iva * config["tarifa_fuente_extranjera"]

def obtener_tarifa_reteiva(es_fuente_nacional: bool) -> float:
    """Obtiene la tarifa de ReteIVA según la fuente
    
    Args:
        es_fuente_nacional: True si es fuente nacional, False si extranjera
        
    Returns:
        float: Tarifa de ReteIVA (0.15 para nacional, 1.0 para extranjera)
    """
    config = CONFIG_RETEIVA
    
    if es_fuente_nacional:
        return config["tarifa_fuente_nacional"]
    else:
        return config["tarifa_fuente_extranjera"]

# ===============================
# FUNCIONES INTEGRADAS ACTUALIZADAS
# ===============================

def detectar_impuestos_aplicables(nit: str) -> Dict[str, Any]:
    """Detecta automáticamente qué impuestos aplican según el NIT - ACTUALIZADO CON IVA
    
    Args:
        nit: NIT administrativo
        
    Returns:
        Dict con información de qué impuestos aplican
    """
    aplica_estampilla = nit_aplica_estampilla_universidad(nit)
    aplica_obra_publica = nit_aplica_contribucion_obra_publica(nit)
    aplica_iva = nit_aplica_iva_reteiva(nit)  # ✅ NUEVA VALIDACIÓN
    
    impuestos_aplicables = []
    if aplica_estampilla:
        impuestos_aplicables.append("ESTAMPILLA_UNIVERSIDAD")
    if aplica_obra_publica:
        impuestos_aplicables.append("CONTRIBUCION_OBRA_PUBLICA")
    if aplica_iva:
        impuestos_aplicables.append("IVA_RETEIVA")  # ✅ NUEVO IMPUESTO
    
    return {
        "nit": nit,
        "aplica_estampilla_universidad": aplica_estampilla,
        "aplica_contribucion_obra_publica": aplica_obra_publica,
        "aplica_iva_reteiva": aplica_iva,  # ✅ NUEVO CAMPO
        "impuestos_aplicables": impuestos_aplicables,
        "procesamiento_paralelo": len(impuestos_aplicables) > 1,  # ✅ LÓGICA ACTUALIZADA
        "nombre_entidad_estampilla": NITS_ESTAMPILLA_UNIVERSIDAD.get(nit),
        "nombre_entidad_obra_publica": NITS_CONTRIBUCION_OBRA_PUBLICA.get(nit),
        "nombre_entidad_iva": NITS_IVA_RETEIVA.get(nit, {}).get("nombre")  # ✅ NUEVO CAMPO
    }

def obtener_configuracion_impuestos_integrada() -> Dict[str, Any]:
    """Obtiene configuración integrada para todos los impuestos - ACTUALIZADO CON IVA"""
    return {
        "estampilla_universidad": obtener_configuracion_estampilla_universidad(),
        "contribucion_obra_publica": obtener_configuracion_obra_publica(),
        "iva_reteiva": obtener_configuracion_iva(),  # ✅ NUEVA CONFIGURACIÓN
        "terceros_recursos_publicos_compartidos": list(TERCEROS_RECURSOS_PUBLICOS.keys())
    }

# ===============================
# INICIALIZACIÓN AUTOMÁTICA
# ===============================

def inicializar_configuracion():
    """Inicializa y valida la configuración del sistema"""
    try:
        # Validar que las constantes estén definidas
        assert UVT_2025 > 0, "UVT_2025 debe ser mayor a 0"
        assert SMMLV_2025 > 0, "SMMLV_2025 debe ser mayor a 0"
        assert len(NITS_ESTAMPILLA_UNIVERSIDAD) > 0, "Debe haber NITs configurados para estampilla"
        assert len(NITS_CONTRIBUCION_OBRA_PUBLICA) > 0, "Debe haber NITs configurados para obra pública"
        assert len(TERCEROS_RECURSOS_PUBLICOS) > 0, "Debe haber terceros configurados"
        assert len(CONCEPTOS_RETEFUENTE) > 0, "Debe haber conceptos de retefuente configurados"
        assert len(NITS_IVA_RETEIVA) > 0, "Debe haber NITs configurados para IVA y ReteIVA"
        
        logger.info(" Configuración inicializada correctamente")
        logger.info(f"   - UVT 2025: ${UVT_2025:,}")
        logger.info(f"   - NITs Estampilla: {len(NITS_ESTAMPILLA_UNIVERSIDAD)}")
        logger.info(f"   - NITs Obra Pública: {len(NITS_CONTRIBUCION_OBRA_PUBLICA)}")
        logger.info(f"   - Terceros: {len(TERCEROS_RECURSOS_PUBLICOS)}")
        logger.info(f"   - Conceptos ReteFuente: {len(CONCEPTOS_RETEFUENTE)}")
        logger.info(f"   - NITs IVA y ReteIVA: {len(NITS_IVA_RETEIVA)}")
        
        return True
        
    except Exception as e:
        logger.error(f" Error en inicialización: {e}")
        return False

# Inicializar al importar
#try:
    #inicializar_configuracion()
#except Exception as e:
   # logger.warning(f" Error en inicialización automática: {e}")
