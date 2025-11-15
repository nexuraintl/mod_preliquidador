"""
PROMPT PARA ANALISIS DE ESTAMPILLAS GENERALES
==============================================

Prompt especializado para identificación de 6 estampillas generales:
- Procultura
- Bienestar
- Adulto Mayor
- Prouniversidad Pedagógica
- Francisco José de Caldas
- Prodeporte

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo prompts de estampillas generales
- OCP: Abierto para extensión
- DIP: Funciones puras

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

from typing import List

# Import de función auxiliar compartida
from .prompt_clasificador import _generar_seccion_archivos_directos


def PROMPT_ANALISIS_ESTAMPILLAS_GENERALES(factura_texto: str, rut_texto: str, anexos_texto: str,
                                             cotizaciones_texto: str, anexo_contrato: str, nombres_archivos_directos: list[str] = None) -> str:
    """
     NUEVO PROMPT: Análisis de 6 Estampillas Generales

    Analiza documentos para identificar información de estampillas:
    - Procultura
    - Bienestar
    - Adulto Mayor
    - Prouniversidad Pedagógica
    - Francisco José de Caldas
    - Prodeporte

    Estas estampillas aplican para TODOS los NITs administrativos.
    Solo identifica información sin realizar cálculos.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        nombres_archivos_directos: Lista de nombres de archivos directos

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    return f"""
Eres un experto contador colombiano especializado en ESTAMPILLAS GENERALES que trabaja para la FIDUCIARIA FIDUCOLDEX.
Tu tarea es identificar información sobre 6 estampillas específicas en los documentos adjuntos.

 ESTAMPILLAS A IDENTIFICAR:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
1.  **PROCULTURA** - Estampilla Pro Cultura
2.  **BIENESTAR** - Estampilla Pro Bienestar
3.  **ADULTO MAYOR** - Estampilla Pro Adulto Mayor
4.  **PROUNIVERSIDAD PEDAGÓGICA** - Estampilla Pro Universidad Pedagógica
5.  **FRANCISCO JOSÉ DE CALDAS** - Estampilla Francisco José de Caldas
6.  **PRODEPORTE** - Estampilla Pro Deporte

 ESTRATEGIA DE ANÁLISIS SECUENCIAL:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

 **ANÁLISIS ACUMULATIVO** - Revisar TODOS los documentos en este orden:
1.  **FACTURA PRINCIPAL** - Buscar desglose de estampillas
2.  **ANEXOS** - Información adicional sobre estampillas
3.  **ANEXO CONTRATO** - Referencias a estampillas aplicables
4.  **RUT** - Validación del tercero

 **IMPORTANTE**: Revisar TODOS los documentos y consolidar información encontrada

DOCUMENTOS DISPONIBLES:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}


FACTURA PRINCIPAL:
{factura_texto}

RUT DEL TERCERO:
{rut_texto if rut_texto else "NO DISPONIBLE"}

ANEXOS ADICIONALES:
{anexos_texto if anexos_texto else "NO DISPONIBLES"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "NO DISPONIBLES"}

ANEXO CONCEPTO CONTRATO:
{anexo_contrato if anexo_contrato else "NO DISPONIBLES"}

INSTRUCCIONES CRÍTICAS:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

1.  **IDENTIFICACIÓN DE ESTAMPILLAS**:
   • Busca menciones EXACTAS de los nombres de las estampillas
   • Identifica variaciones comunes:
     - "Estampilla Pro Cultura" / "Estampilla ProCultura"/ ESTAMPILLA PROCULTURA
     - "Estampilla Pro Bienestar" /  "Estampilla Bienestar"
     - "Estampilla Adulto Mayor" / "Pro Adulto Mayor" / "Estampilla Adulto Mayor / Estampilla Bienestar Adulto Mayor"
     - "Estampilla Pro Universidad Pedagógica"
     -  "Estampilla FJDC" / Estampilla Francisco José de Caldas
     - "Estampilla Pro Deporte" /  "Estampilla ProDeporte"

2.  **EXTRACCIÓN DE INFORMACIÓN**:
   Para cada estampilla identificada, extrae:
   • **Nombre exacto** como aparece en el documento
   • **Porcentaje** (ej: 1.5 , 2.0 , 0.5 , 1.1)
   • **Valor a deducir** en pesos colombianos
   • **Texto de referencia** donde se encontró la información
   • **valor base** base gravable de la estampilla en pesos colombianos

3.  **VALIDACIÓN DE INFORMACIÓN COMPLETA**:
   • **INFORMACIÓN COMPLETA**: Nombre + Porcentaje + Valor + valor base → Estado: "preliquidado"
   • **INFORMACIÓN INCOMPLETA**: Solo nombre o porcentaje sin valor o sin valor base → Estado: "preliquidacion_sin_finalizar"
   • **NO IDENTIFICADA**: No se encuentra información → Estado: "no_aplica_impuesto"

4.  **CONSOLIDACIÓN ACUMULATIVA**:
   • Si FACTURA tiene info de 3 estampillas Y ANEXOS tienen info de 2 adicionales
   • RESULTADO: Mostrar las 5 estampillas consolidadas
   • Si hay duplicados, priorizar información más detallada

5.  **OBSERVACIONES ESPECÍFICAS**:
menciona en las observaciones si:
   • Si encuentra estampillas mencionadas pero sin información completa
   • Si hay inconsistencias entre documentos
   • Si faltan detalles específicos de porcentaje o valor

EJEMPLOS DE IDENTIFICACIÓN:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

 **EJEMPLO 1 - INFORMACIÓN COMPLETA**:
Factura: "Estampilla Pro Cultura 1.5% = $150,000"
Resultado: {{
  "nombre_estampilla": "Procultura",
  "porcentaje": 1.5,
  "valor_base": 1000000,
  "valor": 150000,
  "estado": "preliquidado"
}}

 **EJEMPLO 2 - INFORMACIÓN INCOMPLETA**:
Anexo: "Aplica estampilla Pro Bienestar"
Resultado: {{
  "nombre_estampilla": "Bienestar",
  "porcentaje": null,
  "valor_base": 0.0,
  "valor": null,
  "estado": "preliquidacion_sin_finalizar",
  "observaciones": "Se menciona la estampilla pero no se encontró porcentaje ni valor"
}}

 **EJEMPLO 3 - NO IDENTIFICADA**:
Resultado: {{
  "nombre_estampilla": "Prodeporte",
  "porcentaje": null,
  "valor_base": 0.0,
  "valor": null,
  "estado": "no_aplica_impuesto",
  "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
}}

IMPORTANTE:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
• NO realizar cálculos, solo identificar información
• Si una estampilla se menciona múltiples veces, consolidar la información más completa
• Priorizar información de FACTURA, luego ANEXOS, luego ANEXO CONTRATO
• Si no encuentra información de alguna estampilla, marcar como "no_aplica_impuesto"
• Ser específico en observaciones cuando falta información

RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
    "estampillas_generales": [
        {{
            "nombre_estampilla": "Procultura",
            "porcentaje": 1.5,
            "valor_base": 1000000,
            "valor": 150000,
            "estado": "preliquidado",
            "texto_referencia": "Factura línea 15: Estampilla Pro Cultura 1.5% = $150,000",
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Bienestar",
            "porcentaje": null,
            "valor_base": 0.0,
            "valor": null,
            "estado": "preliquidacion_sin_finalizar",
            "texto_referencia": "Anexo página 2: Aplica estampilla Pro Bienestar",
            "observaciones": "Se menciona la estampilla pero no se encontró porcentaje ni valor específico"
        }},
        {{
            "nombre_estampilla": "Adulto Mayor",
            "porcentaje": null,
            "valor_base": 0.0,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }},
        {{
            "nombre_estampilla": "Prouniversidad Pedagógica",
            "porcentaje": null,
            "valor_base": 0.0,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }},
        {{
            "nombre_estampilla": "Francisco José de Caldas",
            "porcentaje": null,
            "valor_base": 0.0,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }},
        {{
            "nombre_estampilla": "Prodeporte",
            "porcentaje": null,
            "valor_base": 0.0,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }}
    ]
}}

 **CRÍTICO - CONDICIONES EXACTAS**:
• SIEMPRE incluir las 6 estampillas en el resultado (aunque sea como "no_aplica_impuesto")
• Estados válidos: "preliquidado", "preliquidacion_sin_finalizar", "no_aplica_impuesto"
• Si encuentra información parcial, marcar como "preliquidacion_sin_finalizar" con observaciones específicas
• Consolidar información de TODOS los documentos de forma acumulativa
• Especificar claramente dónde se encontró cada información
• NO INVENTAR VALORES, SOLO UTILIZAR LA INFORMACIÓN PRESENTE EN LOS DOCUMENTOS
    """
