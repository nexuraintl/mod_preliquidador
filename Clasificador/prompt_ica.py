"""
PROMPTS PARA ANALISIS ICA (INDUSTRIA Y COMERCIO)
================================================

Prompts especializados para identificar ubicaciones y actividades
sujetas a retención de ICA según normativa colombiana.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo generación de prompts ICA
- OCP: Abierto para extensión - nuevos prompts sin modificar existentes
- DIP: Funciones puras sin dependencias externas

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import json
from typing import List, Dict, Any

# Importar función para generar sección de archivos directos
from .prompt_clasificador import _generar_seccion_archivos_directos


def crear_prompt_identificacion_ubicaciones(
    ubicaciones_bd: List[Dict[str, Any]],
    textos_documentos: Dict[str, str],
    nombres_archivos_directos: List[str] = None
) -> str:
    """
    Crea prompt para que Gemini identifique ubicaciones donde se ejecuta la actividad.

    RESPONSABILIDAD (SRP):
    - Solo genera el prompt de identificación de ubicaciones
    - No procesa respuestas ni valida datos

    Args:
        ubicaciones_bd: Lista de ubicaciones de la base de datos
                       [{"codigo_ubicacion": 1, "nombre_ubicacion": "BOGOTA D.C."}, ...]
        textos_documentos: Diccionario con textos de documentos adjuntos
        nombres_archivos_directos: Lista de nombres de archivos directos (para multimodalidad)

    Returns:
        str: Prompt estructurado para Gemini
    """

    # Formatear ubicaciones de la base de datos
    ubicaciones_formateadas = "\n".join([
        f"- Código {ub['codigo_ubicacion']}: {ub['nombre_ubicacion']}"
        for ub in ubicaciones_bd
    ])

    # Formatear documentos
    docs_formateados = ""
    for nombre, contenido in textos_documentos.items():
        docs_formateados += f"\n{'='*80}\n"
        docs_formateados += f"ARCHIVO: {nombre}\n"
        docs_formateados += f"{'='*80}\n"
        docs_formateados += f"{contenido}\n"

    return f"""
ROL: Eres un ANALISTA EXPERTO en retención de ICA (Industria y Comercio) en Colombia.
Tu función es IDENTIFICAR las ubicaciones donde se ejecuta la actividad facturada.

REGLA FUNDAMENTAL:
- SOLO usa información que puedas CITAR TEXTUALMENTE de los documentos
- PROHIBIDO deducir o suponer ubicaciones
- Si no encuentras evidencia clara, marca codigo_ubicacion = 0

═══════════════════════════════════════════════════════════════════════
PASO 1: UBICACIONES PARAMETRIZADAS EN BASE DE DATOS
═══════════════════════════════════════════════════════════════════════

{ubicaciones_formateadas}

IMPORTANTE: Solo estas ubicaciones están parametrizadas en el sistema.

═══════════════════════════════════════════════════════════════════════
PASO 2: DOCUMENTOS ADJUNTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

{docs_formateados}

═══════════════════════════════════════════════════════════════════════
PASO 3: INSTRUCCIONES DE IDENTIFICACIÓN
═══════════════════════════════════════════════════════════════════════

BUSCAR EN LA FACTURA:
1. Ubicación explícita de ejecución del contrato
2. Ciudad/municipio donde se realiza la actividad
3. Dirección del lugar de ejecución
4. Lugar de prestación del servicio

IMPORTANTE:
- Para identificar las ubicaciones busca  palabras clave similares a las siguientes: 
" Servicios prestados en ", " Lugar de ejecución: ", " Prestación del servicio en ",
" Ejecución en ", " Realizado en ", "ejecutado en ", "Municipio de Prestación del Servicio: "

Si encuentras UBICACIONES SOLAS sin que se especifique que ahí se ejecuta la actividad, NO LAS CONSIDERES y menciona en observaciones que no se encontraron ubicaciones de ejecución explícitas.

VALIDACIONES OBLIGATORIAS:

Si encuentras UNA sola ubicación:
- porcentaje_ejecucion = 100 (siempre, aunque no aparezca en documentos)
- Buscar la ubicación en la lista de la base de datos
- Si la encuentras: copiar EXACTAMENTE codigo_ubicacion y nombre_ubicacion
- Si NO la encuentras: codigo_ubicacion = 0, nombre_ubicacion = "NOMBRE EN MAYUSCULAS SIN ACENTOS"
- texto_identificador = "CITA TEXTUAL del documento donde identificaste la ubicación"

Si encuentras MULTIPLES ubicaciones:
- Para CADA ubicación extraer el porcentaje de ejecución (formato 70 si aparece 70%)
- Si NO aparece el porcentaje explícitamente: porcentaje_ejecucion = 0.0
- Para cada una validar si está en la base de datos
- texto_identificador = "CITA TEXTUAL del documento donde identificaste CADA ubicación"

VALIDACION CRITICA:
- La suma de porcentajes_ejecucion debe ser 100% (si hay múltiples ubicaciones)

Si NO encuentras ubicación:
- nombre_ubicacion = ""
- codigo_ubicacion = 0
- texto_identificador = ""
- porcentaje_ejecucion = 0.0

Agrega las observaciones que consideres relevantes en el campo "observaciones" del JSON.

═══════════════════════════════════════════════════════════════════════
PASO 4: FORMATO DE RESPUESTA JSON (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════

Debes responder UNICAMENTE con un JSON válido siguiendo esta estructura EXACTA:

{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "NOMBRE EXACTO como aparece en BD (o MAYUSCULAS SIN ACENTOS si no está en BD)",
      "codigo_ubicacion": 1,
      "texto_identificador": "CITA TEXTUAL del documento",
      "porcentaje_ejecucion": 100.0
    }},
    {{
      "nombre_ubicacion": "SEGUNDA UBICACION (solo si aplica)",
      "codigo_ubicacion": 2,
      "texto_identificador": "CITA TEXTUAL del documento",
      "porcentaje_ejecucion": 0.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 1 - Una ubicación encontrada en BD:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "BOGOTA D.C.",
      "codigo_ubicacion": 1,
      "texto_identificador": "Lugar de ejecución: Bogotá D.C., Carrera 7 # 12-34",
      "porcentaje_ejecucion": 100.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 2 - Múltiples ubicaciones con porcentajes:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "BOGOTA D.C.",
      "codigo_ubicacion": 1,
      "texto_identificador": "Ejecución en Bogotá: 60% del contrato",
      "porcentaje_ejecucion": 60.0
    }},
    {{
      "nombre_ubicacion": "MEDELLIN",
      "codigo_ubicacion": 5,
      "texto_identificador": "Ejecución en Medellín: 40% del contrato",
      "porcentaje_ejecucion": 40.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 3 - Ubicación NO encontrada en BD:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "ZIPAQUIRA",
      "codigo_ubicacion": 0,
      "texto_identificador": "Servicio prestado en el municipio de Zipaquirá",
      "porcentaje_ejecucion": 100.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 4 - NO se encontró ubicación:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "",
      "codigo_ubicacion": 0,
      "texto_identificador": "",
      "porcentaje_ejecucion": 0.0
    }}
  ],
  "observaciones": "No se encontró ubicación en los documentos proporcionados o no se encontrar documentos"
}}

IMPORTANTE:
- Responde SOLO con el JSON, sin texto adicional
- NO agregues comentarios fuera del JSON
- Valida que sea JSON válido antes de responder
"""


def crear_prompt_relacionar_actividades(
    ubicaciones_identificadas: List[Dict[str, Any]],
    actividades_bd_por_ubicacion: Dict[str, List[Dict[str, Any]]],
    textos_documentos: Dict[str, str],
    nombres_archivos_directos: List[str] = None
) -> str:
    """
    Crea prompt para que Gemini relacione actividades facturadas con actividades de BD.

    RESPONSABILIDAD (SRP):
    - Solo genera el prompt de relación de actividades
    - No procesa respuestas ni calcula tarifas

    Args:
        ubicaciones_identificadas: Ubicaciones identificadas en llamada anterior
                                  [{"nombre_ubicacion": "BOGOTA", "codigo_ubicacion": 1}, ...]
        actividades_bd_por_ubicacion: Actividades de BD agrupadas por ubicación
                                      {"1": [{"codigo_actividad": 10, "descripcion": "..."}, ...]}
        textos_documentos: Diccionario con textos de documentos (especialmente FACTURA)
        nombres_archivos_directos: Lista de nombres de archivos directos (para multimodalidad)

    Returns:
        str: Prompt estructurado para Gemini
    """

    # Formatear ubicaciones identificadas
    ubicaciones_str = "\n".join([
        f"- {ub['nombre_ubicacion']} (Código: {ub['codigo_ubicacion']})"
        for ub in ubicaciones_identificadas
    ])

    # Formatear actividades por ubicación
    actividades_str = ""
    for cod_ubicacion, actividades in actividades_bd_por_ubicacion.items():
        ubicacion_nombre = next(
            (u['nombre_ubicacion'] for u in ubicaciones_identificadas
             if str(u['codigo_ubicacion']) == str(cod_ubicacion)),
            f"Código {cod_ubicacion}"
        )
        actividades_str += f"\n{'='*80}\n"
        actividades_str += f"ACTIVIDADES PARA: {ubicacion_nombre} (Código: {cod_ubicacion})\n"
        actividades_str += f"{'='*80}\n"

        for act in actividades:
            actividades_str += f"\nCódigo Actividad: {act['codigo_actividad']}\n"
            actividades_str += f"Descripción: {act['descripcion_actividad']}\n"
            actividades_str += f"Tipo: {act['tipo_actividad']}\n"
            actividades_str += f"Tarifa ICA: {act['porcentaje_ica']}%\n"
            actividades_str += f"-" * 40 + "\n"

    # Formatear documentos (enfocado en FACTURA)
    docs_formateados = ""
    for nombre, contenido in textos_documentos.items():
        docs_formateados += f"\n{'='*80}\n"
        docs_formateados += f"ARCHIVO: {nombre}\n"
        docs_formateados += f"{'='*80}\n"
        docs_formateados += f"{contenido}\n"

    return f"""
ROL: Eres un ANALISTA EXPERTO en clasificación de actividades económicas para ICA en Colombia.
Tu función es RELACIONAR actividades facturadas con actividades parametrizadas en base de datos.

REGLA FUNDAMENTAL:
- Tu UNICO trabajo es IDENTIFICAR y RELACIONAR conceptos
- NO calculas tarifas, NO validas normativa, NO haces cálculos
- SOLO relacionas actividades de la FACTURA con actividades de la BASE DE DATOS

═══════════════════════════════════════════════════════════════════════
PASO 1: UBICACIONES IDENTIFICADAS (PASO ANTERIOR)
═══════════════════════════════════════════════════════════════════════

{ubicaciones_str}

═══════════════════════════════════════════════════════════════════════
PASO 2: ACTIVIDADES PARAMETRIZADAS EN BASE DE DATOS POR UBICACION
═══════════════════════════════════════════════════════════════════════

{actividades_str}

═══════════════════════════════════════════════════════════════════════
PASO 3: DOCUMENTOS A ANALIZAR (ENFOQUE EN FACTURA)
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

{docs_formateados}

═══════════════════════════════════════════════════════════════════════
PASO 4: INSTRUCCIONES DE RELACION
═══════════════════════════════════════════════════════════════════════

PROCESO OBLIGATORIO:

1. EXTRAER de la FACTURA:
   - Actividad facturada (TEXTUAL, tal como aparece)
   - Base gravable de cada actividad

2. RELACIONAR actividad facturada con actividades de la BD:
   - Para CADA ubicación identificada
   - Buscar en las actividades de BD de ESA ubicación
   - SOLO PUEDE HABER UNA actividad relacionada POR UBICACION
   - Si NO encuentras relación para una ubicación, dejar actividades_relacionadas vacío para esa ubicación

3. IMPORTANTE:
   - Una actividad facturada puede tener múltiples actividades relacionadas SOLO si son de DIFERENTES ubicaciones
   - Para la MISMA ubicación, SOLO PUEDE HABER UNA actividad relacionada
   - Si no encuentras ninguna relación, nombre_act_rel = "", codigo_actividad = 0, codigo_ubicacion = 0

═══════════════════════════════════════════════════════════════════════
PASO 5: FORMATO DE RESPUESTA JSON (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════

Debes responder UNICAMENTE con un JSON válido siguiendo esta estructura EXACTA:

{{
  "actividades_facturadas": [
    {{
      "nombre_actividad": "ACTIVIDAD TEXTUAL de la FACTURA",
      "base_gravable": 1000000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "DESCRIPCION TEXTUAL de BD para ubicación 1",
          "codigo_actividad": 10,
          "codigo_ubicacion": 1
        }},
        {{
          "nombre_act_rel": "DESCRIPCION TEXTUAL de BD para ubicación 2",
          "codigo_actividad": 15,
          "codigo_ubicacion": 2
        }}
      ]
    }},
    {{
      "nombre_actividad": "SEGUNDA ACTIVIDAD FACTURADA (solo si existe)",
      "base_gravable": 500000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "DESCRIPCION de BD",
          "codigo_actividad": 20,
          "codigo_ubicacion": 1
        }}
      ]
    }}
  ]
}}

EJEMPLO 1 - Una actividad, una ubicación:
{{
  "actividades_facturadas": [
    {{
      "nombre_actividad": "Servicios de consultoría en sistemas",
      "base_gravable": 5000000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "Servicios de consultoría en informática",
          "codigo_actividad": 620100,
          "codigo_ubicacion": 1
        }}
      ]
    }}
  ]
}}

EJEMPLO 2 - Una actividad, múltiples ubicaciones:
{{
  "actividades_facturadas": [
    {{
      "nombre_actividad": "Servicios de ingeniería civil",
      "base_gravable": 10000000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "Servicios de ingeniería y arquitectura",
          "codigo_actividad": 711000,
          "codigo_ubicacion": 1
        }},
        {{
          "nombre_act_rel": "Servicios de ingeniería y arquitectura",
          "codigo_actividad": 711000,
          "codigo_ubicacion": 5
        }}
      ]
    }}
  ]
}}

EJEMPLO 3 - Múltiples actividades facturadas:
{{
  "actividades_facturadas": [
    {{
      "nombre_actividad": "Servicios de consultoría",
      "base_gravable": 3000000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "Servicios de consultoría empresarial",
          "codigo_actividad": 702000,
          "codigo_ubicacion": 1
        }}
      ]
    }},
    {{
      "nombre_actividad": "Servicios de capacitación",
      "base_gravable": 2000000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "Servicios de educación y capacitación",
          "codigo_actividad": 855900,
          "codigo_ubicacion": 1
        }}
      ]
    }}
  ]
}}

EJEMPLO 4 - NO se pudo relacionar:
{{
  "actividades_facturadas": [
    {{
      "nombre_actividad": "Servicios varios no especificados",
      "base_gravable": 1000000.0,
      "actividades_relacionadas": [
        {{
          "nombre_act_rel": "",
          "codigo_actividad": 0,
          "codigo_ubicacion": 0
        }}
      ]
    }}
  ]
}}

IMPORTANTE:
- Responde SOLO con el JSON, sin texto adicional
- NO agregues comentarios fuera del JSON
- Valida que sea JSON válido antes de responder
- POR CADA ubicación identificada, SOLO UNA actividad relacionada
"""


def limpiar_json_gemini(respuesta_gemini: str) -> str:
    """
    Limpia la respuesta de Gemini para extraer solo el JSON válido.

    RESPONSABILIDAD (SRP):
    - Solo limpia y extrae JSON de respuestas de Gemini
    - No procesa ni valida el contenido del JSON

    Args:
        respuesta_gemini: Respuesta cruda de Gemini

    Returns:
        str: JSON limpio y válido
    """
    # Eliminar bloques de código markdown
    respuesta_limpia = respuesta_gemini.strip()

    if respuesta_limpia.startswith("```json"):
        respuesta_limpia = respuesta_limpia[7:]
    elif respuesta_limpia.startswith("```"):
        respuesta_limpia = respuesta_limpia[3:]

    if respuesta_limpia.endswith("```"):
        respuesta_limpia = respuesta_limpia[:-3]

    return respuesta_limpia.strip()


def validar_estructura_ubicaciones(data: Dict[str, Any]) -> bool:
    """
    Valida que el JSON de ubicaciones tenga la estructura correcta.

    RESPONSABILIDAD (SRP):
    - Solo valida estructura de JSON de ubicaciones
    - No valida lógica de negocio

    Args:
        data: Diccionario parseado de JSON

    Returns:
        bool: True si la estructura es válida
    """
    if "ubicaciones" not in data:
        return False

    if not isinstance(data["ubicaciones"], list):
        return False

    if len(data["ubicaciones"]) == 0:
        return False

    campos_requeridos = ["nombre_ubicacion", "codigo_ubicacion", "texto_identificador", "porcentaje_ejecucion"]

    for ubicacion in data["ubicaciones"]:
        for campo in campos_requeridos:
            if campo not in ubicacion:
                return False

    return True


def validar_estructura_actividades(data: Dict[str, Any]) -> bool:
    """
    Valida que el JSON de actividades tenga la estructura correcta.

    RESPONSABILIDAD (SRP):
    - Solo valida estructura de JSON de actividades
    - No valida lógica de negocio

    Args:
        data: Diccionario parseado de JSON

    Returns:
        bool: True si la estructura es válida
    """
    if "actividades_facturadas" not in data:
        return False

    if not isinstance(data["actividades_facturadas"], list):
        return False

    if len(data["actividades_facturadas"]) == 0:
        return False

    for actividad in data["actividades_facturadas"]:
        if "nombre_actividad" not in actividad:
            return False
        if "base_gravable" not in actividad:
            return False
        if "actividades_relacionadas" not in actividad:
            return False

        if not isinstance(actividad["actividades_relacionadas"], list):
            return False

        for rel in actividad["actividades_relacionadas"]:
            if "nombre_act_rel" not in rel:
                return False
            if "codigo_actividad" not in rel:
                return False
            if "codigo_ubicacion" not in rel:
                return False

    return True
