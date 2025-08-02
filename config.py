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

# ===============================
# CONCEPTOS HARDCODEADOS (FALLBACK)
# ===============================

CONCEPTOS_FALLBACK = [
    "Servicios de consultoría",
    "Honorarios profesionales", 
    "Asesorías técnicas",
    "Servicios de mantenimiento",
    "Arrendamiento de bienes muebles",
    "Arrendamiento de bienes inmuebles",
    "Transporte de carga",
    "Transporte de pasajeros",
    "Compra de combustibles",
    "Compra de productos agrícolas",
    "Servicios de vigilancia",
    "Servicios de aseo",
    "Servicios de temporales",
    "Servicios de restaurante",
    "Servicios hoteleros",
    "Servicios de publicidad",
    "Comisiones",
    "Servicios portuarios",
    "Servicios de telecomunicaciones",
    "Servicios públicos",
    "Intereses",
    "Rendimientos financieros",
    "Arrendamiento de vehículos",
    "Contratos de obra",
    "Contratos de construcción",
    "Servicios de ingeniería",
    "Servicios médicos",
    "Servicios educativos",
    "Servicios de software",
    "Licencias de software",
    "Regalías",
    "Derechos de autor",
    "Servicios de seguridad",
    "Servicios de mensajería",
    "Servicios de alimentación",
    "Arrendamiento de maquinaria",
    "Servicios financieros",
    "Servicios de seguros",
    "Servicios de auditoría",
    "Servicios jurídicos",
    "Servicios contables",
    "Capacitación y entrenamiento",
    "Servicios de traducción",
    "Otros servicios gravados"
]

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
# TARIFAS DE RETENCIÓN NACIONAL (%)
# ===============================

TARIFAS_RETEFUENTE = {
    # Servicios profesionales
    "honorarios": 11.0,
    "servicios_generales": 4.0,
    "consultoria": 11.0,
    "asesoria": 11.0,
    
    # Arrendamientos
    "arrendamiento_inmuebles": 3.5,
    "arrendamiento_muebles": 4.0,
    "arrendamiento_vehiculos": 4.0,
    "arrendamiento_maquinaria": 4.0,
    
    # Transporte
    "transporte_carga": 1.0,
    "transporte_pasajeros": 3.5,
    
    # Compras
    "compras": 2.5,
    "combustibles": 0.1,
    "productos_agricolas": 1.5,
    
    # Servicios específicos
    "servicios_temporales": 1.0,
    "servicios_vigilancia": 6.0,
    "servicios_aseo": 2.0,
    "servicios_restaurante": 3.5,
    "servicios_hoteleros": 3.5,
    
    # Construcción y obra
    "contratos_obra": 2.0,
    "construccion": 2.0,
    "ingenieria": 11.0,
    
    # Financieros
    "intereses": 7.0,
    "comisiones": 10.0,
    "rendimientos_financieros": 7.0,
    
    # Otros
    "servicios_medicos": 11.0,
    "servicios_educativos": 11.0,
    "software": 11.0,
    "regalias": 11.0,
    "derechos_autor": 11.0,
    "publicidad": 4.0,
    "telecomunicaciones": 3.5,
    "servicios_publicos": 1.0,
    
    # Por defecto
    "otros": 6.0,
    "default": 6.0
}

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
# CARGADOR DE CONCEPTOS
# ===============================

class CargadorConceptos:
    """Carga conceptos desde Excel o fallback"""
    
    def __init__(self, ruta_proyecto: str = None):
        self.ruta_proyecto = Path(ruta_proyecto or "C:/Users/USUSARIO/Proyectos/PRELIQUIDADOR")
        self.archivo_excel = self.ruta_proyecto / CONFIG["archivo_excel"]
        self.conceptos = []
        self.cargar_conceptos()
    
    def cargar_conceptos(self) -> List[str]:
        """Carga conceptos desde Excel o usa fallback"""
        
        # Intentar cargar desde Excel
        conceptos_excel = self._cargar_desde_excel()
        if conceptos_excel:
            self.conceptos = conceptos_excel
            logger.info(f"✅ Conceptos cargados desde Excel: {len(self.conceptos)}")
            return self.conceptos
        
        # Usar fallback
        self.conceptos = CONCEPTOS_FALLBACK.copy()
        logger.warning(f"⚠️ Usando conceptos fallback: {len(self.conceptos)}")
        return self.conceptos
    
    def _cargar_desde_excel(self) -> List[str]:
        """Intenta cargar conceptos desde Excel"""
        
        if not self.archivo_excel.exists():
            logger.warning(f"📄 Archivo Excel no encontrado: {self.archivo_excel}")
            return None
        
        try:
            df = pd.read_excel(self.archivo_excel)
            
            # Buscar columna de conceptos (primera columna no vacía)
            for columna in df.columns:
                conceptos = df[columna].dropna().astype(str).tolist()
                if len(conceptos) > 10:  # Mínimo 10 conceptos
                    # Limpiar conceptos
                    conceptos_limpios = []
                    for concepto in conceptos:
                        concepto_limpio = str(concepto).strip()
                        if concepto_limpio and concepto_limpio.lower() not in ['nan', 'none', '']:
                            conceptos_limpios.append(concepto_limpio)
                    
                    if len(conceptos_limpios) > 10:
                        logger.info(f"📊 Excel procesado: {len(conceptos_limpios)} conceptos desde columna '{columna}'")
                        return conceptos_limpios
            
            logger.warning("📊 No se encontraron conceptos válidos en Excel")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error leyendo Excel: {e}")
            return None
    
    def obtener_conceptos(self) -> List[str]:
        """Obtiene la lista de conceptos cargados"""
        return self.conceptos.copy()
    
    def obtener_conceptos_para_prompt(self) -> str:
        """Formatea conceptos para uso en prompts de Gemini"""
        return "\n".join([f"- {concepto}" for concepto in self.conceptos])
    
    def buscar_concepto(self, texto: str) -> str:
        """Busca el concepto más similar en la lista"""
        texto_lower = texto.lower()
        
        # Búsqueda exacta
        for concepto in self.conceptos:
            if texto_lower == concepto.lower():
                return concepto
        
        # Búsqueda parcial
        for concepto in self.conceptos:
            if texto_lower in concepto.lower() or concepto.lower() in texto_lower:
                return concepto
        
        return "CONCEPTO_NO_IDENTIFICADO"
    
    def exportar_conceptos(self, archivo_salida: str = "conceptos_exportados.json"):
        """Exporta conceptos a archivo JSON"""
        try:
            datos = {
                "conceptos": self.conceptos,
                "total": len(self.conceptos),
                "fuente": "Excel" if self.archivo_excel.exists() else "Fallback",
                "archivo_excel": str(self.archivo_excel),
                "fecha_exportacion": pd.Timestamp.now().isoformat()
            }
            
            ruta_salida = self.ruta_proyecto / archivo_salida
            with open(ruta_salida, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Conceptos exportados a: {ruta_salida}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exportando conceptos: {e}")
            return False

# ===============================
# MAPEADOR DE TARIFAS
# ===============================

class MapeadorTarifas:
    """Mapea conceptos a tarifas de retención"""
    
    def __init__(self):
        self.tarifas = TARIFAS_RETEFUENTE.copy()
    
    def obtener_tarifa(self, concepto: str) -> float:
        """Obtiene la tarifa para un concepto específico"""
        
        concepto_lower = concepto.lower()
        
        # Mapeo directo por palabras clave
        mapeo_palabras = {
            "honorario": "honorarios",
            "consultor": "consultoria", 
            "asesor": "asesoria",
            "arrenda": "arrendamiento_muebles",
            "inmueble": "arrendamiento_inmuebles",
            "vehiculo": "arrendamiento_vehiculos",
            "maquinaria": "arrendamiento_maquinaria",
            "transporte": "transporte_carga",
            "pasajero": "transporte_pasajeros",
            "carga": "transporte_carga",
            "vigilancia": "servicios_vigilancia",
            "aseo": "servicios_aseo",
            "temporal": "servicios_temporales",
            "restaurante": "servicios_restaurante",
            "hotel": "servicios_hoteleros",
            "obra": "contratos_obra",
            "construccion": "construccion",
            "ingenier": "ingenieria",
            "interes": "intereses",
            "comision": "comisiones",
            "medico": "servicios_medicos",
            "educativ": "servicios_educativos",
            "software": "software",
            "regalia": "regalias",
            "autor": "derechos_autor",
            "publicidad": "publicidad",
            "telecomunicacion": "telecomunicaciones",
            "combustible": "combustibles",
            "agricola": "productos_agricolas"
        }
        
        # Buscar por palabras clave
        for palabra, tarifa_key in mapeo_palabras.items():
            if palabra in concepto_lower:
                return self.tarifas.get(tarifa_key, self.tarifas["default"])
        
        # Tarifa por defecto
        return self.tarifas["default"]
    
    def obtener_concepto_tarifa(self, concepto: str) -> tuple:
        """Obtiene concepto y tarifa"""
        tarifa = self.obtener_tarifa(concepto)
        return concepto, tarifa
    
    def listar_tarifas(self) -> Dict[str, float]:
        """Lista todas las tarifas disponibles"""
        return self.tarifas.copy()

# ===============================
# CONFIGURACIÓN DE NITS ADMINISTRATIVOS
# ===============================

NITS_CONFIGURACION = {
    "800.178.148-8": {
        "nombre": "Fiduciaria Colombiana de Comercio Exterior S.A.",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA", 
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL"
        ]
    },
    "830.054.060-5": {
        "nombre": "FIDEICOMISOS SOCIEDAD FIDUCIARIA FIDUCOLDEX",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA", 
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL"
        ]
    },
    "900.649.119-9": {
        "nombre": "PATRIMONIO AUTÓNOMO FONTUR",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL"
        ]
    },
    "901.281.733-3": {
        "nombre": "FONDOS DE INVERSIÓN - ABIERTA Y 60 MODERADO",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "900.566.230-1": {
        "nombre": "CONSORCIO",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "901.427.860-1": {
        "nombre": "CONSORCIO", 
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "900.139.498-7": {
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

# ===============================
# INSTANCIAS GLOBALES
# ===============================

# Cargar al importar el módulo
_cargador_conceptos = None
_mapeador_tarifas = None

def inicializar_configuracion(ruta_proyecto: str = None):
    """Inicializa la configuración global"""
    global _cargador_conceptos, _mapeador_tarifas
    
    _cargador_conceptos = CargadorConceptos(ruta_proyecto)
    _mapeador_tarifas = MapeadorTarifas()
    
    logger.info("⚙️ Configuración inicializada")

def obtener_conceptos() -> List[str]:
    """Obtiene la lista de conceptos cargados"""
    if not _cargador_conceptos:
        inicializar_configuracion()
    return _cargador_conceptos.obtener_conceptos()

def obtener_conceptos_para_prompt() -> str:
    """Obtiene conceptos formateados para Gemini"""
    if not _cargador_conceptos:
        inicializar_configuracion()
    return _cargador_conceptos.obtener_conceptos_para_prompt()

def obtener_tarifa_concepto(concepto: str) -> float:
    """Obtiene la tarifa para un concepto"""
    if not _mapeador_tarifas:
        inicializar_configuracion()
    return _mapeador_tarifas.obtener_tarifa(concepto)

def obtener_todas_tarifas() -> Dict[str, float]:
    """Obtiene todas las tarifas disponibles"""
    if not _mapeador_tarifas:
        inicializar_configuracion()
    return _mapeador_tarifas.listar_tarifas()

# ===============================
# FUNCIONES PARA FACTURACIÓN EXTRANJERA
# ===============================

def obtener_conceptos_extranjeros() -> Dict[str, Dict[str, Any]]:
    """Obtiene todos los conceptos de retención para facturación extranjera"""
    return CONCEPTOS_EXTRANJEROS.copy()

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

def obtener_paises_con_convenio() -> List[str]:
    """Obtiene la lista de países con convenio de doble tributación"""
    return PAISES_CON_CONVENIO.copy()

def obtener_preguntas_fuente_nacional() -> List[str]:
    """Obtiene las preguntas para determinar fuente nacional"""
    return PREGUNTAS_FUENTE_NACIONAL.copy()

def es_pais_con_convenio(pais: str) -> bool:
    """Verifica si un país tiene convenio de doble tributación"""
    if not pais:
        return False
    
    pais_normalizado = pais.strip().title()
    return pais_normalizado in PAISES_CON_CONVENIO

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
        # Solo aplica si el ingreso supera SMMLV
        if ingreso_bruto <= SMMLV_2025:
            return 0
        
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
# INICIALIZACIÓN AUTOMÁTICA
# ===============================

# Inicializar al importar
try:
    inicializar_configuracion()
except Exception as e:
    logger.warning(f"⚠️ Error en inicialización automática: {e}")
