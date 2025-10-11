"""
PROMPTS PARA CLASIFICACIÓN DE DOCUMENTOS
========================================

Plantillas de prompts utilizadas por el clasificador de documentos.
"""

import json
from typing import Dict, List



def PROMPT_CLASIFICACION(textos_preprocesados: Dict[str, str], nombres_archivos_directos: List[str], proveedor: str = None) -> str:
    """
    Genera el prompt optimizado para clasificar documentos fiscales colombianos.
    Versión mejorada con prevención de alucinaciones y criterios más claros.

    Args:
        textos_preprocesados: Diccionario con textos preprocesados
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del proveedor que emite la factura (v3.0)
    """

    todos_los_archivos = nombres_archivos_directos + list(textos_preprocesados.keys())
    total_archivos = len(todos_los_archivos)

    # Contexto de proveedor para mejor identificación
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════════
INFORMACIÓN DEL PROVEEDOR (CONTEXTO DE VALIDACIÓN)
═══════════════════════════════════════════════════════════════════════

**PROVEEDOR ESPERADO:** {proveedor}

INSTRUCCIONES DE VALIDACIÓN CONTRA RUT:
• Verifica que el nombre/razón social del proveedor en la FACTURA coincida con el RUT
• Verifica que el NIT en la FACTURA coincida con el NIT del RUT
• Si encuentras discrepancias entre FACTURA y RUT, repórtalas explícitamente
• Si el proveedor es un CONSORCIO o UNIÓN TEMPORAL:
  - Verifica que el nombre del consorcio en FACTURA coincida con RUT
  - Identifica los miembros/integrantes del consorcio
  - Verifica los porcentajes de participación si están disponibles
  - Reporta si falta información de algún consorciado

VALIDACIÓN DE COHERENCIA:
1. Nombre en FACTURA vs Nombre en RUT → deben coincidir
2. NIT en FACTURA vs NIT en RUT → deben coincidir
3. Si es consorcio: nombre del consorcio debe aparecer en ambos documentos
4. Si hay inconsistencias, márcalas en "indicadores_consorcio" o crea campo de observaciones

"""

    return f"""
ROL: Eres un CLASIFICADOR LITERAL de documentos fiscales colombianos.
Tu función es ÚNICAMENTE identificar y clasificar basándote en lo que está ESCRITO TEXTUALMENTE.
{contexto_proveedor}

 REGLA FUNDAMENTAL ANTI-ALUCINACIÓN:
• PROHIBIDO deducir, interpretar o suponer información
• SOLO usa texto que puedas CITAR LITERALMENTE del documento
• Si no encuentras evidencia textual explícita → marca como false
• NO uses contexto implícito, SOLO texto explícito
• NO clasifiques pagina por página, clasifica el documento completo

═══════════════════════════════════════════════════════════════════════
PASO 1: CLASIFICACIÓN DE DOCUMENTOS
═══════════════════════════════════════════════════════════════════════

Debes clasificar EXACTAMENTE {total_archivos} documento(s) en UNA de estas categorías:

1. **FACTURA** - Identificar si contiene:
   ✓ Número de factura o documento equivalente
   ✓ Fecha de emisión/venta
   ✓ Valores monetarios (subtotal, total, impuestos)
   ✓ Datos del vendedor/proveedor y comprador
   ✓ Descripción de bienes o servicios vendidos
   
   SE PUEDE CLASIFICAR COMO FACTURA TAMBIÉN:
   • "SOPORTE EN ADQUISICIONES EFECTUADAS A NO OBLIGADOS A FACTURAR"
   • "CUENTA DE COBRO"
   • "DOCUMENTO EQUIVALENTE"
   • Cualquier documento con estructura de venta/cobro

2. **RUT** - Registro Único Tributario que contiene:
   ✓ Número de identificación tributaria (NIT)
   ✓ Razón social
   ✓ Responsabilidades tributarias
   ✓ Actividades económicas CIIU

4. **ANEXO_CONTRATO** - Documento que contiene ESPECÍFICAMENTE:
   ✓ Objeto del contrato
   ✓ Obligaciones contractuales
   ✓ Términos y condiciones del contrato

5. **ANEXO** - Cualquier otro documento de soporte

REGLA ESPECIAL: Si un documento combina múltiple información → clasifícalo por su función PRINCIPAL
Si hay solo UN DOCUMENTO con múltiples funciones → clasifícalo como FACTURA

═══════════════════════════════════════════════════════════════════════
PASO 2: IDENTIFICACIÓN DE CONTENIDO (FACTURA Y RUT)
═══════════════════════════════════════════════════════════════════════

**factura_identificada = true** si en CUALQUIER documento encuentras:
• Estructura de facturación (valores + conceptos + totales)
• Información de venta/cobro formal
• NO importa si está en un archivo separado o integrado

**rut_identificado = true** si en CUALQUIER documento encuentras:
• El Registro Único Tributario completo
• Información de responsabilidades tributarias
• NO importa si está en un archivo separado o integrado

═══════════════════════════════════════════════════════════════════════
PASO 3: DETECCIÓN DE CONSORCIO
═══════════════════════════════════════════════════════════════════════

 BUSCAR ÚNICAMENTE EN: **FACTURA** o **RUT**
 NO buscar en: ANEXO_CONTRATO, anexos

**es_consorcio = true** SOLO SI encuentras TEXTUALMENTE:
• La palabra "CONSORCIO" en el nombre/razón social del proveedor
• La palabra "UNIÓN TEMPORAL" en el nombre/razón social
• Texto explícito: "consorciados", "miembros del consorcio"
• Porcentajes de participación: "Empresa A: 60%, Empresa B: 40%"

Si no encuentras estas palabras EXACTAS → es_consorcio = false

═══════════════════════════════════════════════════════════════════════
PASO 4: DETERMINACIÓN DE FUENTE DE INGRESO (NACIONAL vs EXTRANJERA)
═══════════════════════════════════════════════════════════════════════

 DOCUMENTOS A REVISAR: TODOS los documentos listados

Para determinar si es **FUENTE EXTRANJERA**, responde estas preguntas basándote SOLO en texto explícito:

1. **¿El servicio tiene uso o beneficio económico en Colombia?**
   Buscar texto similar a:
   • "servicio prestado en Colombia"
   • "para uso en territorio colombiano"
   • "beneficiario en Colombia"

2. **¿La actividad se ejecutó total o parcialmente en Colombia?**
   Buscar texto similar a:
   • "ejecutado en Colombia"
   • "realizado en [ciudad colombiana]"
   • "prestación del servicio en Colombia"

3. **¿Es asistencia técnica/consultoría usada en Colombia?**
   Buscar texto similar a:
   • "asistencia técnica para operaciones en Colombia"
   • "consultoría implementada en Colombia"
   • "know-how aplicado en territorio nacional"

4. **¿El bien vendido está ubicado en Colombia?**
   Buscar texto similar a:
   • "entrega en Colombia"
   • "bien ubicado en [dirección colombiana]"
   • "instalación en Colombia"

IMPORTANTE : Si no encuentras evidencia textual clara para alguna de las preguntas anteriores → responde null


═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

**ARCHIVOS DIRECTOS:**
{_formatear_archivos_directos(nombres_archivos_directos)}

**TEXTOS PREPROCESADOS:**
{_formatear_textos_preprocesados(textos_preprocesados)}

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA OBLIGATORIO (JSON ESTRICTO)
═══════════════════════════════════════════════════════════════════════

{{
    "clasificacion": {{
        "nombre_archivo_1": "FACTURA|RUT|COTIZACION|ANEXO_CONTRATO|ANEXO",
        "nombre_archivo_2": "FACTURA|RUT|COTIZACION|ANEXO_CONTRATO|ANEXO"
    }},
    "factura_identificada": true/false,
    "rut_identificado": true/false,
    "es_consorcio": true/false,
    "indicadores_consorcio": ["cita textual exacta del RUT o FACTURA"],
    "analisis_fuente_ingreso": {{
        "servicio_uso_colombia": true/false/null,
        "evidencias_uso_encontradas": ["cita textual"],
        "ejecutado_en_colombia": true/false/null,
        "evidencias_ejecucion_encontradas": ["cita textual"],
        "asistencia_tecnica_colombia": true/false/null,
        "evidencias_asistencia_encontradas": ["cita textual"],
        "bien_ubicado_colombia": true/false/null,
        "evidencias_bien_encontradas": ["cita textual"]
    }},
}}

 RECORDATORIOS FINALES:
• NO interpretes - SOLO extrae lo que está escrito
• Las evidencias deben ser CITAS TEXTUALES copiadas del documento
• Si no hay información clara, usa false o ( null para los items de analisis fuente ingreso)
• Clasifica TODOS los documentos listados
"""
def _formatear_archivos_directos(nombres_archivos_directos: List[str]) -> str:
    """
    Formatea la lista de archivos directos para el prompt.
    
    Args:
        nombres_archivos_directos: Lista de nombres de archivos directos
        
    Returns:
        str: Texto formateado para incluir en el prompt
    """
    if not nombres_archivos_directos:
        return "- No hay archivos directos en esta solicitud"
    
    texto = ""
    for i, nombre in enumerate(nombres_archivos_directos, 1):
        extension = nombre.split('.')[-1].upper() if '.' in nombre else "DESCONOCIDO"
        tipo_archivo = "PDF" if extension == "PDF" else "IMAGEN" if extension in ["JPG", "JPEG", "PNG", "GIF", "BMP", "TIFF"] else extension
        texto += f"- {nombre} (ARCHIVO {tipo_archivo} ADJUNTO - lo verás directamente)\n"
    
    return texto.strip()

def _formatear_textos_preprocesados(textos_preprocesados: Dict[str, str]) -> str:
    """
    Formatea los textos preprocesados para incluir en el prompt.
    
    Args:
        textos_preprocesados: Diccionario con textos preprocesados
        
    Returns:
        str: Texto formateado para incluir en el prompt
    """
    if not textos_preprocesados:
        return "- No hay textos preprocesados en esta solicitud"
    
    import json
    return json.dumps(textos_preprocesados, indent=2, ensure_ascii=False)

def _generar_seccion_archivos_directos(nombres_archivos_directos: List[str]) -> str:
    """
    Genera sección informativa sobre archivos directos para análisis de factura.
    
    Args:
        nombres_archivos_directos: Lista de nombres de archivos directos o None
        
    Returns:
        str: Texto formateado para incluir en el prompt de análisis
    """
    if not nombres_archivos_directos:
        return " **ARCHIVOS DIRECTOS**: No hay archivos directos adjuntos."
    
    texto = " **ARCHIVOS DIRECTOS ADJUNTOS** (verás estos archivos nativamente):\n"
    for nombre in nombres_archivos_directos:
        extension = nombre.split('.')[-1].upper() if '.' in nombre else "DESCONOCIDO"
        if extension == "PDF":
            tipo = "PDF"
        elif extension in ["JPG", "JPEG", "PNG", "GIF", "BMP", "TIFF", "WEBP"]:
            tipo = "IMAGEN"
        else:
            tipo = extension
        texto += f"   - {nombre} (ARCHIVO {tipo} - procésalo directamente)\n"
    
    return texto.strip()

def PROMPT_ANALISIS_FACTURA(factura_texto: str, rut_texto: str, anexos_texto: str,
                            cotizaciones_texto: str, anexo_contrato: str, conceptos_dict: dict,
                            nombres_archivos_directos: List[str] = None, proveedor: str = None) -> str:
    """
    Genera el prompt para analizar factura y extraer información de retención.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_dict: Diccionario de conceptos con tarifas y bases mínimas
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del proveedor que emite la factura (v3.0)

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    # Contexto de proveedor para validación
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════
 INFORMACIÓN DEL PROVEEDOR (VALIDACIÓN OBLIGATORIA)
═══════════════════════════════════════════════════════════════════

**PROVEEDOR ESPERADO:** {proveedor}

 VALIDACIONES OBLIGATORIAS CONTRA RUT:

1. VALIDACIÓN DE IDENTIDAD:
   - Verifica que el nombre/razón social del proveedor en FACTURA coincida con el nombre en RUT
   - Verifica que el NIT en FACTURA coincida con el NIT en RUT
   - Si hay discrepancias, repórtalas en "observaciones"


"""

    return f"""
Eres un sistema de análisis tributario colombiano para FIDUCIARIA FIDUCOLDEX.
Tu función es IDENTIFICAR con PRECISIÓN conceptos de retención en la fuente y naturaleza del tercero.

 REGLA FUNDAMENTAL: SOLO usa información EXPLÍCITAMENTE presente en los documentos.
 NUNCA inventes, asumas o deduzcas información no visible.
 Si no encuentras un dato, usa NULL o el valor por defecto especificado.
{contexto_proveedor}

═══════════════════════════════════════════════════════════════════
 CONCEPTOS VÁLIDOS DE RETENCIÓN (USA SOLO ESTOS):
═══════════════════════════════════════════════════════════════════
{json.dumps(conceptos_dict, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
 DOCUMENTOS PROPORCIONADOS:
═══════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS Y DETALLES:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
 PROTOCOLO DE ANÁLISIS ESTRICTO:
═══════════════════════════════════════════════════════════════════

 PASO 1: VERIFICACIÓN DEL RUT
├─ Si RUT existe → Continuar al PASO 2
└─ Si RUT NO existe → DETENER análisis con:
   
     "aplica_retencion": false,
     "estado": "Preliquidacion sin finalizar",
     "observaciones": ["RUT no disponible en documentos adjuntos"]
     (Los demás campos pueden ser null o 0.0 según corresponda)

 PASO 2: EXTRACCIÓN DE DATOS DEL RUT (SOLO del documento RUT)
Buscar TEXTUALMENTE en el RUT:

 TIPO DE CONTRIBUYENTE (Sección 24 o equivalente):
├─ Si encuentras "Persona natural" → es_persona_natural: true
├─ Si encuentras "Persona jurídica" → es_persona_natural: false
└─ Si NO encuentras → es_persona_natural: null

 RÉGIMEN TRIBUTARIO (Buscar texto exacto):
├─ Si encuentras "RÉGIMEN SIMPLE" o "SIMPLE" → regimen_tributario: "SIMPLE"
├─ Si encuentras "RÉGIMEN ORDINARIO" u "ORDINARIO" → regimen_tributario: "ORDINARIO"
├─ Si encuentras "RÉGIMEN ESPECIAL", "ESPECIAL" o "SIN ÁNIMO DE LUCRO" → regimen_tributario: "ESPECIAL"
└─ Si NO encuentras → regimen_tributario: null

 AUTORRETENEDOR:
├─ Si encuentras texto "ES AUTORRETENEDOR" → es_autorretenedor: true
└─ Si NO encuentras esa frase → es_autorretenedor: false


 RESPONSABLE DE IVA (Sección Responsabilidades):
├─ Si encuentras "NO RESPONSABLE DE IVA" o "49 - No responsable de IVA" → es_responsable_iva: false
├─ Si encuentras "RESPONSABLE DE IVA" (sin el NO) → es_responsable_iva: true
└─ Si NO encuentras ninguna mención → es_responsable_iva: null

 PASO 3: VALIDACIÓN DE CONDICIONES DE NO APLICACIÓN
Verificar si aplica alguna condición de exclusión:

 NO APLICA RETENCIÓN SI:
├─ regimen_tributario == "SIMPLE" → estado: "no aplica impuesto"
├─ es_autorretenedor == true → estado: "no aplica impuesto"
├─ es_responsable_iva == false → estado: "no aplica impuesto"
└─ Cualquier campo crítico == null → estado: "Preliquidacion sin finalizar"

 PASO 4: IDENTIFICACIÓN DE CONCEPTOS 

 REGLAS DE IDENTIFICACIÓN:
1. Buscar PRIMERO en la factura principal
2. Si la factura no tiene detalle, buscar en ANEXOS
3. Comparar texto encontrado con nombres en CONCEPTOS VÁLIDOS

 MATCHING DE CONCEPTOS - ESTRICTO:
├─ Si encuentras coincidencia EXACTA → usar ese concepto
├─ Si encuentras coincidencia PARCIAL clara → usar el concepto más específico
├─ Si NO hay coincidencia clara → "CONCEPTO_NO_IDENTIFICADO"
└─ NUNCA inventes un concepto que no esté en la lista

 EXTRACCIÓN DE VALORES:
├─ Usar SOLO valores numéricos presentes en documentos
├─ Si hay múltiples conceptos → extraer cada valor por separado
├─ Si solo hay total → usar ese valor para el concepto principal
├─ NUNCA calcules o inventes valores
└─ "valor_total" es el valor total de la factura

 PASO 5: VALIDACIÓN DE COHERENCIA
├─ Verificar que IVA en factura coincida con es_responsable_iva del RUT
├─ Si hay incongruencia → estado: "Preliquidacion sin finalizar" + observación
└─ Documentar TODA anomalía en observaciones

═══════════════════════════════════════════════════════════════════
 PROHIBICIONES ABSOLUTAS:
═══════════════════════════════════════════════════════════════════
 NO inventes información no presente en documentos
 NO asumas valores por defecto excepto los especificados
 NO modifiques nombres de conceptos del diccionario
 NO calcules valores no mostrados
 NO deduzcas el régimen tributario por el tipo de empresa
 NO asumas que alguien es autorretenedor sin confirmación explícita
 NO uses información de la factura para determinar responsabilidad IVA 

═══════════════════════════════════════════════════════════════════
 FORMATO DE RESPUESTA OBLIGATORIO (JSON ESTRICTO):
═══════════════════════════════════════════════════════════════════
{{
    "aplica_retencion": boolean,
    "estado": "Preliquidado" | "no aplica impuesto" | "Preliquidacion sin finalizar",
    "conceptos_identificados": [
        {{
            "concepto": "Nombre exacto del diccionario o CONCEPTO_NO_IDENTIFICADO",
            "tarifa_retencion": número o 0.0,
            "base_gravable": número encontrado o 0.0
        }}
    ],
    "naturaleza_tercero": {{
        "es_persona_natural": true | false | null,
        "regimen_tributario": "SIMPLE" | "ORDINARIO" | "ESPECIAL" | null,
        "es_autorretenedor": true | false,
        "es_responsable_iva": true | false | null
    }},
    "es_facturacion_exterior": boolean,
    "valor_total": número encontrado o 0.0,
    "iva": número encontrado o 0.0,
    "observaciones": ["Lista de observaciones relevantes"]
}}

 RESPONDE ÚNICAMENTE CON EL JSON. SIN EXPLICACIONES ADICIONALES.

    """
def PROMPT_ANALISIS_ART_383(factura_texto: str, rut_texto: str, anexos_texto: str, 
                            cotizaciones_texto: str, anexo_contrato: str,
                            nombres_archivos_directos: List[str] = None, 
                            conceptos_identificados: List = None) -> str:

    # Importar constantes del Artículo 383
    from config import obtener_constantes_articulo_383
    
    constantes_art383 = obtener_constantes_articulo_383()
    
    return f"""
Eres un sistema de validación del Artículo 383 del Estatuto Tributario Colombiano para FIDUCIARIA FIDUCOLDEX.
Tu función es VERIFICAR si aplican deducciones especiales para personas naturales.

 REGLA FUNDAMENTAL: SOLO reporta información TEXTUALMENTE presente en documentos.
 NUNCA asumas, deduzcas o inventes información no visible.
 Si no encuentras un dato específico, usa el valor por defecto indicado.

═══════════════════════════════════════════════════════════════════
 DATOS DE REFERENCIA ART. 383:
═══════════════════════════════════════════════════════════════════
CONCEPTOS QUE APLICAN PARA ART. 383:
{json.dumps(constantes_art383['conceptos_aplicables'], indent=2, ensure_ascii=False)}

CONCEPTOS YA IDENTIFICADOS EN ANÁLISIS PREVIO:
{json.dumps(conceptos_identificados, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
 DOCUMENTOS DISPONIBLES PARA ANÁLISIS:
═══════════════════════════════════════════════════════════════════
{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto if factura_texto else "[NO PROPORCIONADA]"}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
 PROTOCOLO DE VERIFICACIÓN ESTRICTO - ARTÍCULO 383:
═══════════════════════════════════════════════════════════════════

 PASO 1: VERIFICAR TIPO DE CONTRIBUYENTE
├─ Buscar EN EL RUT → Sección 24 o "Tipo de contribuyente"
├─ Si encuentra "Persona natural" o "natural" → es_persona_natural: true
├─ Si encuentra "Persona jurídica" → es_persona_natural: false
└─ Si NO encuentra información → es_persona_natural: false (DEFAULT)

 PASO 2: VALIDAR CONCEPTOS APLICABLES AL ART. 383

 REGLA DE MATCHING ESTRICTA:
Para CADA concepto en conceptos_identificados:
  1. Comparar TEXTUALMENTE con lista de conceptos_aplicables Art. 383
  2. CRITERIOS DE COINCIDENCIA:
     ├─ Coincidencia EXACTA del texto → INCLUIR
     ├─ Palabras clave coinciden (honorarios, servicios, comisiones) → INCLUIR
     └─ NO hay coincidencia clara → EXCLUIR

 RESULTADO:
├─ Si HAY conceptos que coinciden → Agregar a conceptos_identificados con sus valores
├─ Si hay conceptos que coinciden → conceptos_aplicables: true
├─ Si NO hay coincidencias → conceptos_identificados: [] (lista vacía)
└─ Si NO hay coincidencias → conceptos_aplicables: false

 PASO 3: DETECTAR PRIMER PAGO

 BUSCAR TEXTUALMENTE en FACTURA y ANEXOS estas frases EXACTAS:
├─ "primer pago"
├─ "pago inicial"
├─ "anticipo"
├─ "pago adelantado"
├─ "primera cuota"
├─ "entrega inicial"
├─ "adelanto"
├─ "pago #1" o "pago 1" o "pago 001"
├─ "inicio de contrato"
└─ "pago de arranque"

 RESULTADO:
├─ Si encuentras ALGUNA frase → es_primer_pago: true
└─ Si NO encuentras ALGUNA → es_primer_pago: false (DEFAULT)

 PASO 4: BUSCAR PLANILLA DE SEGURIDAD SOCIAL Y EXTRAER IBC

 BUSCAR en ANEXOS palabras clave:
├─ "planilla" Y ("salud" O "pensión" O "seguridad social" O "PILA")
├─ "aportes" Y ("EPS" O "AFP" O "parafiscales")
└─ "pago seguridad social"

 SI ENCUENTRA PLANILLA:
├─ planilla_seguridad_social: true
├─ Buscar fecha en formato: DD/MM/AAAA o AAAA-MM-DD o "mes de XXXX"
│  ├─ Si encuentra fecha → fecha_de_planilla_seguridad_social: "AAAA-MM-DD"
│  └─ Si NO encuentra fecha → fecha_de_planilla_seguridad_social: "0000-00-00"
├─ BUSCAR Y EXTRAER IBC (Ingreso Base de Cotización):
│  ├─ Buscar "IBC" o "Ingreso Base de Cotización" o "Base de cotización"
│  ├─ Si encuentra valor → IBC_seguridad_social: [valor extraído]
│  └─ Si NO encuentra → IBC_seguridad_social: 0.0
│
└─ IMPORTANTE: El IBC SOLO se extrae de la PLANILLA DE SEGURIDAD SOCIAL

 SI NO ENCUENTRA PLANILLA:
├─ planilla_seguridad_social: false (DEFAULT)
├─ fecha_de_planilla_seguridad_social: "0000-00-00" (DEFAULT)
└─ IBC_seguridad_social: 0.0 (DEFAULT)

 PASO 5: VERIFICAR DOCUMENTO SOPORTE Y EXTRAER VALOR DE INGRESO

 BUSCAR en documentos estas palabras EXACTAS:
├─ "cuenta de cobro"
├─ "factura de venta"
├─ "documento soporte"
└─ "no obligado a facturar"

 SI ENCUENTRA "DOCUMENTO SOPORTE":
├─ Documento_soporte: true
├─ BUSCAR Y EXTRAER VALOR DE INGRESO DEL DOCUMENTO SOPORTE:
│  ├─ Buscar palabras clave EN EL DOCUMENTO SOPORTE: "valor", "total", "honorarios", "servicios prestados"
│  ├─ Identificar el monto principal facturado (sin IVA ni retenciones)
│  ├─ Si encuentra valor → ingreso: [valor extraído]
│  └─ Si NO encuentra valor → ingreso: 0.0
│
└─ IMPORTANTE:  
   └─ Si hay múltiples documentos soporte, priorizar el valor del ingreso de la cuenta de cobro

 SI NO ENCUENTRA "DOCUMENTO SOPORTE":
├─ Documento_soporte: false (DEFAULT)
└─ ingreso: 0.0 (DEFAULT) - No extraer de otros documentos

 RESULTADO:
├─ Si encuentra documento soporte → documento_soporte: true + extraer ingreso
└─ Si NO encuentra → documento_soporte: false + ingreso: 0.0

 PASO 6: IDENTIFICAR DEDUCCIONES (BÚSQUEDA TEXTUAL ESTRICTA)

 INTERESES POR VIVIENDA:
BUSCAR: "intereses" Y ("vivienda" O "hipoteca" O "crédito hipotecario")
├─ Si encuentra certificación bancaria:
│  ├─ Extraer valor numérico de "intereses corrientes" → intereses_corrientes: [valor]
│  └─ certificado_bancario: true
└─ Si NO encuentra:
   ├─ intereses_corrientes: 0.0 (DEFAULT)
   └─ certificado_bancario: false (DEFAULT)

 DEPENDIENTES ECONÓMICOS:
BUSCAR: "dependiente" O "declaración juramentada" Y "económico"
├─ Si encuentra declaración:
│  ├─ Extraer nombre del titular encargado si está presente → nombre_encargado: "[nombre]"
│  └─ declaracion_juramentada: true
└─ Si NO encuentra:
   ├─ nombre_encargado: "" (DEFAULT)
   └─ declaracion_juramentada: false (DEFAULT)

 MEDICINA PREPAGADA:
BUSCAR: "medicina prepagada" O "plan complementario" O "póliza de salud"
├─ Si encuentra certificación:
│  ├─ Extraer valor "sin IVA" o "valor neto" → valor_sin_iva_med_prepagada: [valor]
│  └─ certificado_med_prepagada: true
└─ Si NO encuentra:
   ├─ valor_sin_iva_med_prepagada: 0.0 (DEFAULT)
   └─ certificado_med_prepagada: false (DEFAULT)

 AFC (AHORRO PARA FOMENTO A LA CONSTRUCCIÓN):
BUSCAR: "AFC" O "ahorro para fomento" O "cuenta AFC"
├─ Si encuentra soporte:
│  ├─ Extraer "valor a depositar" → valor_a_depositar: [valor]
│  └─ planilla_de_cuenta_AFC: true
└─ Si NO encuentra:
   ├─ valor_a_depositar: 0.0 (DEFAULT)
   └─ planilla_de_cuenta_AFC: false (DEFAULT)

═══════════════════════════════════════════════════════════════════
 REGLAS ABSOLUTAS - NO NEGOCIABLES:
═══════════════════════════════════════════════════════════════════
 NO inventes valores numéricos - usa 0.0 si no los encuentras
 NO asumas fechas - usa "0000-00-00" si no las encuentras
 NO deduzcas información por contexto
 NO completes campos vacíos con suposiciones
 NO interpretes - solo busca texto LITERAL
 NO calcules valores derivados
 IBC solo se extrae de PLANILLA DE SEGURIDAD SOCIAL

═══════════════════════════════════════════════════════════════════
 FORMATO JSON DE RESPUESTA OBLIGATORIO:
═══════════════════════════════════════════════════════════════════
{{
    "articulo_383": {{
        "condiciones_cumplidas": {{
            "es_persona_natural": boolean (default: false),
            "conceptos_identificados": [
                {{
                    "concepto": "texto exacto del concepto",
                    "base_gravable": número encontrado o 0.0
                }}
            ] o [],
            "conceptos_aplicables": boolean (true si hay conceptos que aplican, false si no aplican),
            "ingreso": número o 0.0 ,
            "es_primer_pago": boolean (default: false),
            "documento_soporte": boolean (default: false)
        }},
        "deducciones_identificadas": {{
            "intereses_vivienda": {{
                "intereses_corrientes": número o 0.0,
                "certificado_bancario": boolean (default: false)
            }},
            "dependientes_economicos": {{
                "nombre_encargado": "texto encontrado" o "",
                "declaracion_juramentada": boolean (default: false)
            }},
            "medicina_prepagada": {{
                "valor_sin_iva_med_prepagada": número o 0.0,
                "certificado_med_prepagada": boolean (default: false)
            }},
            "AFC": {{
                "valor_a_depositar": número o 0.0,
                "planilla_de_cuenta_AFC": boolean (default: false)
            }},
            "planilla_seguridad_social": {{
                "IBC_seguridad_social": número o 0.0 (SOLO de planilla)
                "planilla_seguridad_social": boolean (default: false),
                "fecha_de_planilla_seguridad_social": "AAAA-MM-DD" (default: "0000-00-00")
            }}
        }}
    }}
}}

 RESPONDE ÚNICAMENTE CON EL JSON. SIN EXPLICACIONES ADICIONALES.
"""
def PROMPT_ANALISIS_CONSORCIO(factura_texto: str, rut_texto: str, anexos_texto: str,
                              cotizaciones_texto: str, anexo_contrato: str, conceptos_dict: dict,
                              nombres_archivos_directos: List[str] = None, proveedor: str = None) -> str:
    """
    Genera el prompt optimizado para analizar consorcios.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_dict: Diccionario de conceptos con tarifas y bases mínimas
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del consorcio/unión temporal (v3.0)

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    # Contexto de proveedor para validación de consorcio
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════
 INFORMACIÓN DEL CONSORCIO/UNIÓN TEMPORAL (VALIDACIÓN OBLIGATORIA)
═══════════════════════════════════════════════════════════════════

**CONSORCIO/UNIÓN TEMPORAL ESPERADO:** {proveedor}

 VALIDACIONES OBLIGATORIAS PARA CONSORCIOS:

1. VALIDACIÓN DE IDENTIDAD DEL CONSORCIO:
   - Verifica que el nombre del consorcio en FACTURA coincida con el esperado: "{proveedor}"
   - Verifica que el nombre del consorcio en RUT coincida con FACTURA
   - Si hay discrepancias, repórtalas en "observaciones"

2. VALIDACIÓN DE CONSORCIADOS/INTEGRANTES:
   - Busca RUT individual de cada consorciado en los anexos

3. VALIDACIÓN CONTRA RUT DEL CONSORCIO:
   - Verifica que el NIT del consorcio en FACTURA coincida con RUT

4. VALIDACIÓN DE COHERENCIA:
   - El nombre del consorcio esperado debe aparecer en FACTURA y RUT
   - Los consorciados deben estar claramente identificados

5. REPORTE DE INCONSISTENCIAS:
   - Si nombre consorcio en FACTURA ≠ nombre esperado → agregar a observaciones
   - Si nombre consorcio en FACTURA ≠ nombre en RUT → agregar a observaciones
   - Si NIT del consorcio no coincide entre documentos → agregar a observaciones

"""

    return f"""
Eres un sistema de análisis tributario colombiano para FIDUCIARIA FIDUCOLDEX.
Tu función es IDENTIFICAR con PRECISIÓN conceptos de retención en la fuente, naturaleza del tercero para CONSORCIOS y UNIONES TEMPORALES individualmente.

 REGLA FUNDAMENTAL: SOLO usa información EXPLÍCITAMENTE presente en los documentos.
 NUNCA inventes, asumas o deduzcas información no visible.
 Si no encuentras un dato, usa NULL o el valor por defecto especificado.
{contexto_proveedor}

═══════════════════════════════════════════════════════════════════
 CONCEPTOS VÁLIDOS DE RETENCIÓN (USA SOLO ESTOS):
═══════════════════════════════════════════════════════════════════
{json.dumps(conceptos_dict, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
 DOCUMENTOS PROPORCIONADOS:
═══════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS Y DETALLES:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
 REGLA CRÍTICA DE FORMATO DE SALIDA:
═══════════════════════════════════════════════════════════════════

 IMPORTANTE: Debes retornar SIEMPRE UN SOLO JSON de salida.
   - Incluso si hay múltiples documentos de diferentes proveedores
   - Analiza el documento principal (factura/orden de pago)
   - Si hay información contradictoria entre documentos, repórtala en "observaciones"
   - NO generes un array de JSONs con múltiples objetos
   - SOLO retorna UN objeto JSON único

═══════════════════════════════════════════════════════════════════
 PROTOCOLO DE ANÁLISIS ESTRICTO:
═══════════════════════════════════════════════════════════════════

 PASO 1: IDENTIFICACIÓN DEL TIPO DE ENTIDAD
Buscar en RUT y documentos:
├─ Si encuentras "CONSORCIO" → es_consorcio: true
├─ Si encuentras "UNIÓN TEMPORAL" o "UNION TEMPORAL" → es_consorcio: true
├─ Si encuentras "CONSORCIO" o "UNIÓN TEMPORAL" extrae el nombre general del Consorcio/Unión
└─ Si NO encuentras ninguno → es_consorcio: false y asignar análisis con los valores en 0.0 o null o ""

═══════════════════════════════════════════════════════════════════
 PROTOCOLO ESPECIAL PARA CONSORCIOS/UNIONES TEMPORALES:
═══════════════════════════════════════════════════════════════════

Si es_consorcio == true:

 PASO A: IDENTIFICAR TODOS LOS CONSORCIADOS
Buscar en ESTE ORDEN:
1. Sección "CONSORCIADOS" o "INTEGRANTES" en el RUT principal
2. Tabla de participación en facturas o anexos
3. Documento de constitución del consorcio
4. Cualquier documento que liste los integrantes

Para CADA consorciado extraer:
├─ NIT/Cédula: Número exacto sin puntos ni guiones
├─ Nombre/Razón Social: Nombre completo tal como aparece
├─ Porcentaje participación: Extraer SOLO el número del porcentaje (ej: si encuentras "30%" → 30, si encuentras "0.4%" → 0.4, si encuentras "25.5%" → 25.5)
└─ Si no hay porcentaje → porcentaje_participacion: null

 PASO B: ANALIZAR CADA CONSORCIADO INDIVIDUALMENTE
Para CADA consorciado identificado:
1. Buscar su RUT individual en los anexos (archivo con su NIT)
2. Si encuentra RUT individual → Extraer naturaleza tributaria
3. Si NO encuentra RUT → Todos los campos de naturaleza en null

Extraer del RUT INDIVIDUAL de cada consorciado:
TIPO DE CONTRIBUYENTE (Sección 24 o equivalente):
├─ Si encuentras "Persona natural" → es_persona_natural: true
├─ Si encuentras "Persona jurídica" → es_persona_natural: false
└─ Si NO encuentras → es_persona_natural: null

 RÉGIMEN TRIBUTARIO (Buscar texto exacto):
├─ Si encuentras "RÉGIMEN SIMPLE" o "SIMPLE" → regimen_tributario: "SIMPLE"
├─ Si encuentras "RÉGIMEN ORDINARIO" u "ORDINARIO" → regimen_tributario: "ORDINARIO"
├─ Si encuentras "RÉGIMEN ESPECIAL", "ESPECIAL" o "SIN ÁNIMO DE LUCRO" → regimen_tributario: "ESPECIAL"
└─ Si NO encuentras → regimen_tributario: null

 AUTORRETENEDOR:
├─ Si encuentras texto "ES AUTORRETENEDOR" → es_autorretenedor: true
└─ Si NO encuentras esa frase → es_autorretenedor: false


 RESPONSABLE DE IVA (Sección Responsabilidades):
├─ Si encuentras "NO RESPONSABLE DE IVA" o "49 - No responsable de IVA" → es_responsable_iva: false
├─ Si encuentras "RESPONSABLE DE IVA" (sin el NO) → es_responsable_iva: true
└─ Si NO encuentras ninguna mención → es_responsable_iva: null

 PASO C: VALIDACIÓN DE CONDICIONES DE NO APLICACIÓN
Verificar si aplica alguna condición de exclusión:

 NO APLICA RETENCIÓN INDIVIDUAL SI:
├─ regimen_tributario == "SIMPLE" → "aplica_retencion_individual": false, "razon_no_aplicacion": "regimen_simple"
├─ es_autorretenedor == true → "aplica_retencion_individual": false, "razon_no_aplicacion": "autorretenedor"
└─ es_responsable_iva == false → "aplica_retencion_individual": false, "razon_no_aplicacion": "no_responsable_iva"


 PASO D: IDENTIFICAR CONCEPTOS (UNA VEZ, APLICA A TODOS)
Los conceptos de retención son los MISMOS para todos los consorciados:
├─ Identificar los servicios/bienes facturados y extraer el nombre exacto 
├─ Buscar coincidencias en CONCEPTOS VÁLIDOS
└─ Estos conceptos se aplican a TODOS por igual

 MATCHING DE CONCEPTOS - ESTRICTO:
├─ Si encuentras coincidencia EXACTA → usar ese concepto
├─ Si encuentras coincidencia PARCIAL clara → usar el concepto más específico
├─ Si NO hay coincidencia clara → "CONCEPTO_NO_IDENTIFICADO"
└─ NUNCA inventes un concepto que no esté en la lista


 PASO E: VALIDAR PORCENTAJES
├─ Sumar todos los porcentajes de participación
├─ Si suma != 100% → agregar observación pero CONTINUAR
└─ Si faltan porcentajes → agregar observación pero CONTINUAR

═══════════════════════════════════════════════════════════════════
 PROHIBICIONES ABSOLUTAS:
═══════════════════════════════════════════════════════════════════
 NO inventes consorciados no listados
 NO asumas porcentajes de participación
 NO deduzcas naturaleza sin RUT específico
 NO modifiques nombres de conceptos
 NO calcules valores no mostrados
 NO asumas que consorciados tienen misma naturaleza

═══════════════════════════════════════════════════════════════════
 FORMATO DE RESPUESTA (JSON ESTRICTO):
═══════════════════════════════════════════════════════════════════

FORMATO SI ES CONSORCIO/UNIÓN TEMPORAL:
{{
    "es_consorcio": true,
    "nombre_consorcio": "Nombre del Consorcio/Unión Temporal",
    "tipo_entidad": "CONSORCIO" | "UNION_TEMPORAL",
    "conceptos_identificados": [
        {{
            "nombre_concepto": "Texto LITERAL del concepto extraido",
            "concepto": "Nombre MAPEADO del diccionario o CONCEPTO_NO_IDENTIFICADO",
            "tarifa_retencion": número o 0.0,
            "base_gravable": número extraido de la factura o 0.0
        }}
    ],
    "consorciados": [
        {{
            "nit": "número identificación",
            "nombre": "razón social completa",
            "porcentaje_participacion": número o null,  // Solo el número: 30% → 30, 0.4% → 0.4
            "tiene_rut_individual": boolean,
            "naturaleza_tributaria": {{
                "es_persona_natural": true | false | null,
                "regimen_tributario": "SIMPLE" | "ORDINARIO" | "ESPECIAL" | null,
                "es_autorretenedor": true | false | null,
                "es_responsable_iva": true | false | null
            }},
            "aplica_retencion_individual": boolean,
            "razon_no_aplicacion": "autorretenedor" | "regimen_simple" | "no_responsable_iva" | null
        }}
    ],
    "validacion_porcentajes": {{
        "suma_total": número o 0.0,
        "es_valido": boolean
    }},
    "valor_total": número encontrado o 0.0,
    "iva": número encontrado o 0.0,
    "observaciones": ["Lista de observaciones"]
}}

    """
def PROMPT_ANALISIS_ART_383_CONSORCIADOS(
    consorciados_persona_natural: List[Dict],
    factura_texto: str = "",
    rut_texto: str = "",
    anexos_texto: str = "",
    cotizaciones_texto: str = "",
    anexo_contrato: str = "",
    nombres_archivos_directos: List[str] = None,
    
) -> str:
    """
    Genera prompt para análisis de Artículo 383 de MÚLTIPLES consorciados.
    
    Args:
        consorciados: Lista de consorciados con su información de liquidación
        documentos_por_consorciado: Dict con documentos específicos por NIT
            Ejemplo: {
                "8301078411": {
                    "rut": "texto_rut",
                    "anexos": "texto_anexos",
                    "cotizaciones": "texto_cotizaciones",
                    "planilla": "texto_planilla"
                }
            }
        factura_principal: Texto de factura principal del consorcio (opcional)
        anexo_contrato: Texto del anexo del contrato (opcional)
        nombres_archivos_directos: Lista de nombres de archivos (opcional)
    """
    
    from config import obtener_constantes_articulo_383
    
    constantes_art383 = obtener_constantes_articulo_383()

    
    return f"""
Eres un sistema de validación del Artículo 383 del Estatuto Tributario Colombiano para FIDUCIARIA FIDUCOLDEX.
Tu función es VERIFICAR si aplican deducciones especiales para personas naturales en un CONSORCIO.

⚠️ REGLA FUNDAMENTAL: SOLO reporta información TEXTUALMENTE presente en documentos.
⚠️ NUNCA asumas, deduzcas o inventes información no visible.
⚠️ Si no encuentras un dato específico, usa el valor por defecto indicado.

═══════════════════════════════════════════════════════════════════
📊 DATOS DE REFERENCIA ART. 383:
═══════════════════════════════════════════════════════════════════
CONCEPTOS QUE APLICAN PARA ART. 383:
{json.dumps(constantes_art383['conceptos_aplicables'], indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
📄 DOCUMENTOS GENERALES DEL CONSORCIO:
═══════════════════════════════════════════════════════════════════
{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto if factura_texto else "[NO PROPORCIONADA]"}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
👥 INFORMACIÓN DE CONSORCIADOS A ANALIZAR:
═══════════════════════════════════════════════════════════════════
TOTAL DE CONSORCIADOS: {len(consorciados_persona_natural)}

LISTA DE CONSORCIADOS:
{json.dumps([{'nombre': c.get('nombre'), 'nit': c.get('nit'), 'participacion': c.get('porcentaje_participacion'), 'conceptos_liquidados': c.get('conceptos_liquidados')} for c in consorciados_persona_natural], indent=2, ensure_ascii=False)}


═══════════════════════════════════════════════════════════════════
🔍 PROTOCOLO DE VERIFICACIÓN ESTRICTO - ARTÍCULO 383 PARA CONSORCIADOS:
═══════════════════════════════════════════════════════════════════

⚠️ IMPORTANTE: Debes analizar CADA CONSORCIADO de forma INDEPENDIENTE.
⚠️ Cada consorciado tiene sus propios documentos (RUT, anexos, planilla).
⚠️ NO mezcles información entre consorciados.

PARA CADA CONSORCIADO, REALIZAR LOS SIGUIENTES PASOS:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 PASO 1: VERIFICAR TIPO DE CONTRIBUYENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
├─ Buscar EN EL RUT DEL CONSORCIADO → Sección 24 o "Tipo de contribuyente"
├─ Si encuentra "Persona natural" o "natural" → es_persona_natural: true
├─ Si encuentra "Persona jurídica" → es_persona_natural: false
└─ Si NO encuentra información → es_persona_natural: false (DEFAULT)

⚠️ SOLO CONTINUAR si es_persona_natural: true
⚠️ Si es persona jurídica, pasar al siguiente consorciado

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 PASO 2: VALIDAR CONCEPTOS APLICABLES AL ART. 383
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 REGLA DE MATCHING ESTRICTA:
Para CADA concepto en conceptos_liquidados del consorciado:
  1. Comparar TEXTUALMENTE con lista de conceptos_aplicables Art. 383
  2. CRITERIOS DE COINCIDENCIA:
     ├─ Coincidencia EXACTA del texto → INCLUIR
     ├─ Palabras clave coinciden (honorarios, servicios, comisiones) → INCLUIR
     └─ NO hay coincidencia clara → EXCLUIR

🔹 RESULTADO:
├─ Si HAY conceptos que coinciden → Agregar a conceptos_identificados con sus valores
├─ Si hay conceptos que coinciden → conceptos_aplicables: true
├─ Si NO hay coincidencias → conceptos_identificados: [] (lista vacía)
└─ Si NO hay coincidencias → conceptos_aplicables: false

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 PASO 3: DETECTAR PRIMER PAGO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 BUSCAR TEXTUALMENTE en ANEXOS DEL CONSORCIADO estas frases EXACTAS:
├─ "primer pago"
├─ "pago inicial"
├─ "anticipo"
├─ "pago adelantado"
├─ "primera cuota"
├─ "entrega inicial"
├─ "adelanto"
├─ "pago #1" o "pago 1" o "pago 001"
├─ "inicio de contrato"
└─ "pago de arranque"

🔹 RESULTADO:
├─ Si encuentras ALGUNA frase → es_primer_pago: true
└─ Si NO encuentras ALGUNA → es_primer_pago: false (DEFAULT)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 PASO 4: BUSCAR PLANILLA DE SEGURIDAD SOCIAL Y EXTRAER IBC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 BUSCAR en PLANILLA DEL CONSORCIADO palabras clave:
├─ "planilla" Y ("salud" O "pensión" O "seguridad social" O "PILA")
├─ "aportes" Y ("EPS" O "AFP" O "parafiscales")
└─ "pago seguridad social"

🔹 SI ENCUENTRA PLANILLA:
├─ planilla_seguridad_social: true
├─ Buscar fecha en formato: DD/MM/AAAA o AAAA-MM-DD o "mes de XXXX"
│  ├─ Si encuentra fecha → fecha_de_planilla_seguridad_social: "AAAA-MM-DD"
│  └─ Si NO encuentra fecha → fecha_de_planilla_seguridad_social: "0000-00-00"
├─ BUSCAR Y EXTRAER IBC (Ingreso Base de Cotización):
│  ├─ Buscar "IBC" o "Ingreso Base de Cotización" o "Base de cotización"
│  ├─ Si encuentra valor → IBC_seguridad_social: [valor extraído]
│  └─ Si NO encuentra → IBC_seguridad_social: 0.0
│
└─ ⚠️ IMPORTANTE: El IBC SOLO se extrae de la PLANILLA DE SEGURIDAD SOCIAL

🔹 SI NO ENCUENTRA PLANILLA:
├─ planilla_seguridad_social: false (DEFAULT)
├─ fecha_de_planilla_seguridad_social: "0000-00-00" (DEFAULT)
└─ IBC_seguridad_social: 0.0 (DEFAULT)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 PASO 5: VERIFICAR DOCUMENTO SOPORTE Y EXTRAER VALOR DE INGRESO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 BUSCAR en ANEXOS DEL CONSORCIADO estas palabras EXACTAS:
├─ "cuenta de cobro"
├─ "factura de venta"
├─ "documento soporte"
└─ "no obligado a facturar"

🔹 SI ENCUENTRA "DOCUMENTO SOPORTE":
├─ Documento_soporte: true
├─ BUSCAR Y EXTRAER VALOR DE INGRESO DEL DOCUMENTO SOPORTE:
│  ├─ Buscar palabras clave EN EL DOCUMENTO SOPORTE: "valor", "total", "honorarios", "servicios prestados"
│  ├─ Identificar el monto principal facturado (sin IVA ni retenciones)
│  ├─ Si encuentra valor → ingreso: [valor extraído]
│  └─ Si NO encuentra valor → usar valor_base del consorciado como referencia
│
└─ ⚠️ IMPORTANTE:  
   └─ Si hay múltiples documentos soporte, priorizar el valor del ingreso de la cuenta de cobro

🔹 SI NO ENCUENTRA "DOCUMENTO SOPORTE":
├─ Documento_soporte: false (DEFAULT)
└─ ingreso: 0.0 (DEFAULT) - No extraer de otros documentos

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 PASO 6: IDENTIFICAR DEDUCCIONES (BÚSQUEDA TEXTUAL ESTRICTA)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ BUSCAR EN ANEXOS Y DOCUMENTOS DEL CONSORCIADO ESPECÍFICO

🔹 INTERESES POR VIVIENDA:
BUSCAR: "intereses" Y ("vivienda" O "hipoteca" O "crédito hipotecario")
├─ Si encuentra certificación bancaria:
│  ├─ Extraer valor numérico de "intereses corrientes" → intereses_corrientes: [valor]
│  └─ certificado_bancario: true
└─ Si NO encuentra:
   ├─ intereses_corrientes: 0.0 (DEFAULT)
   └─ certificado_bancario: false (DEFAULT)

🔹 DEPENDIENTES ECONÓMICOS:
BUSCAR: "dependiente" O "declaración juramentada" Y "económico"
├─ Si encuentra declaración:
│  ├─ Extraer nombre del titular encargado si está presente → nombre_encargado: "[nombre]"
│  └─ declaracion_juramentada: true
└─ Si NO encuentra:
   ├─ nombre_encargado: "" (DEFAULT)
   └─ declaracion_juramentada: false (DEFAULT)

🔹 MEDICINA PREPAGADA:
BUSCAR: "medicina prepagada" O "plan complementario" O "póliza de salud"
├─ Si encuentra certificación:
│  ├─ Extraer valor "sin IVA" o "valor neto" → valor_sin_iva_med_prepagada: [valor]
│  └─ certificado_med_prepagada: true
└─ Si NO encuentra:
   ├─ valor_sin_iva_med_prepagada: 0.0 (DEFAULT)
   └─ certificado_med_prepagada: false (DEFAULT)

🔹 AFC (AHORRO PARA FOMENTO A LA CONSTRUCCIÓN):
BUSCAR: "AFC" O "ahorro para fomento" O "cuenta AFC"
├─ Si encuentra soporte:
│  ├─ Extraer "valor a depositar" → valor_a_depositar: [valor]
│  └─ planilla_de_cuenta_AFC: true
└─ Si NO encuentra:
   ├─ valor_a_depositar: 0.0 (DEFAULT)
   └─ planilla_de_cuenta_AFC: false (DEFAULT)

═══════════════════════════════════════════════════════════════════
⚠️ REGLAS ABSOLUTAS - NO NEGOCIABLES:
═══════════════════════════════════════════════════════════════════
❌ NO inventes valores numéricos - usa 0.0 si no los encuentras
❌ NO asumas fechas - usa "0000-00-00" si no las encuentras
❌ NO deduzcas información por contexto
❌ NO completes campos vacíos con suposiciones
❌ NO interpretes - solo busca texto LITERAL
❌ NO calcules valores derivados
❌ NO mezcles información entre consorciados
❌ IBC solo se extrae de PLANILLA DE SEGURIDAD SOCIAL del consorciado específico
✅ Analiza CADA consorciado de forma INDEPENDIENTE con sus propios documentos

═══════════════════════════════════════════════════════════════════
📤 FORMATO JSON DE RESPUESTA OBLIGATORIO:
═══════════════════════════════════════════════════════════════════
{{
    "consorciados_art383": [
        {{
            "nit": "NIT del consorciado",
            "nombre": "Nombre del consorciado",
            "porcentaje_participacion": número,
            "articulo_383": {{
                "condiciones_cumplidas": {{
                    "es_persona_natural": boolean (default: false),
                    "conceptos_identificados": [
                        {{
                            "concepto": "texto exacto del concepto",
                            "base_gravable": número encontrado o 0.0
                        }}
                    ] o [],
                    "conceptos_aplicables": boolean (true si hay conceptos que aplican, false si no aplican),
                    "ingreso": número o 0.0,
                    "es_primer_pago": boolean (default: false),
                    "documento_soporte": boolean (default: false)
                }},
                "deducciones_identificadas": {{
                    "intereses_vivienda": {{
                        "intereses_corrientes": número o 0.0,
                        "certificado_bancario": boolean (default: false)
                    }},
                    "dependientes_economicos": {{
                        "nombre_encargado": "texto encontrado" o "",
                        "declaracion_juramentada": boolean (default: false)
                    }},
                    "medicina_prepagada": {{
                        "valor_sin_iva_med_prepagada": número o 0.0,
                        "certificado_med_prepagada": boolean (default: false)
                    }},
                    "AFC": {{
                        "valor_a_depositar": número o 0.0,
                        "planilla_de_cuenta_AFC": boolean (default: false)
                    }},
                    "planilla_seguridad_social": {{
                        "IBC_seguridad_social": número o 0.0 (SOLO de planilla),
                        "planilla_seguridad_social": boolean (default: false),
                        "fecha_de_planilla_seguridad_social": "AAAA-MM-DD" (default: "0000-00-00")
                    }}
                }}
            }}
        }}
    ]
}}

⚠️ RESPONDE ÚNICAMENTE CON EL JSON. SIN EXPLICACIONES ADICIONALES.
⚠️ Incluye un objeto por cada consorciado analizado.
⚠️ Mantén el orden de los consorciados según fueron proporcionados.
"""
def PROMPT_ANALISIS_FACTURA_EXTRANJERA(factura_texto: str, rut_texto: str, anexos_texto: str,
                                       cotizaciones_texto: str, anexo_contrato: str,
                                       conceptos_extranjeros_dict: dict, paises_convenio: list,
                                       preguntas_fuente: list, nombres_archivos_directos: List[str] = None,
                                       proveedor: str = None) -> str:
    """
    Genera el prompt para analizar factura extranjera y determinar retenciones.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_extranjeros_dict: Diccionario de conceptos extranjeros con tarifas
        paises_convenio: Lista de países con convenio de doble tributación
        preguntas_fuente: Lista de preguntas para determinar fuente nacional
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del proveedor extranjero (v3.0)

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    # Contexto de proveedor para validación
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════
 INFORMACIÓN DEL PROVEEDOR EXTRANJERO (VALIDACIÓN OBLIGATORIA)
═══════════════════════════════════════════════════════════════════

**PROVEEDOR ESPERADO:** {proveedor}

 VALIDACIONES OBLIGATORIAS PARA PROVEEDOR EXTRANJERO:

1. VALIDACIÓN DE IDENTIDAD:
   - Verifica que el nombre del proveedor en FACTURA coincida con el esperado
   - Si hay RUT extranjero disponible, verifica coherencia de datos
   - Si hay discrepancias, repórtalas en "observaciones"

2. VALIDACIÓN DE PAÍS DE ORIGEN:
   - Verifica el país de domicilio del proveedor en la FACTURA
   - Cruza con información del RUT si está disponible
   - Confirma si el país tiene convenio de doble tributación

3. VALIDACIÓN DE COHERENCIA:
   - El proveedor esperado debe corresponder con los datos de FACTURA
   - Verifica que todos los documentos se refieran al mismo tercero extranjero
   - Reporta si hay inconsistencias en nombres, país o datos tributarios

4. REPORTE DE INCONSISTENCIAS:
   - Si nombre en FACTURA ≠ proveedor esperado → agregar a observaciones
   - Si país en FACTURA ≠ país en RUT → agregar a observaciones
   - Si faltan datos críticos del proveedor → agregar a observaciones

"""

    return f"""
    Eres un experto contador colombiano especializado en retención en la fuente para PAGOS AL EXTERIOR.
{contexto_proveedor}
    
    CONCEPTOS DE RETEFUENTE PARA PAGOS AL EXTERIOR (con tarifas normal y convenio):
    {json.dumps(conceptos_extranjeros_dict, indent=2, ensure_ascii=False)}
    
    PAÍSES CON CONVENIO DE DOBLE TRIBUTACIÓN:
    {json.dumps(paises_convenio, indent=2, ensure_ascii=False)}
    
    DOCUMENTOS DISPONIBLES:
    
    FACTURA (DOCUMENTO PRINCIPAL):
    {factura_texto}
    
    RUT (si está disponible):
    {rut_texto if rut_texto else "NO DISPONIBLE"}
    
    ANEXOS (DETALLES ADICIONALES):
    {anexos_texto if anexos_texto else "NO DISPONIBLES"}
    
    COTIZACIONES (PROPUESTAS COMERCIALES):
    {cotizaciones_texto if cotizaciones_texto else "NO DISPONIBLES"}
    
    ANEXO CONCEPTO CONTRATO (OBJETO DEL CONTRATO):
    {anexo_contrato if anexo_contrato else "NO DISPONIBLES"}
    
    INSTRUCCIONES CRÍTICAS PARA FACTURACIÓN EXTRANJERA:
    
    1. **VALIDACIÓN DE FUENTE NACIONAL** (RESPONDE SÍ/NO A CADA PREGUNTA):
    {chr(10).join([f'   - {pregunta}' for pregunta in preguntas_fuente])}
    
       **IMPORTANTE**: Si CUALQUIERA de estas respuestas es SÍ, se considera FUENTE NACIONAL
       y debe aplicarse la tarifa correspondiente. Si TODAS son NO, es fuente extranjera.
    
    2. **IDENTIFICACIÓN DEL PAÍS DE ORIGEN**:
       - Identifica el país donde está domiciliado el proveedor
       - Verifica si está en la lista de países con convenio
       - Incluye Comunidad Andina: Perú, Ecuador, Bolivia
    
    3. **IDENTIFICACIÓN DE CONCEPTOS**:
       - Usa el NOMBRE EXACTO del concepto como aparece en el diccionario de conceptos extranjeros
       - Si encuentras servicios específicos, mapea al concepto más cercano
       - NO inventes o modifiques nombres de conceptos
       - Si no encuentras coincidencia exacta: "CONCEPTO_NO_IDENTIFICADO"
    
    4. **APLICACIÓN DE TARIFAS**:
       - Si el país TIENE convenio: usa "tarifa_convenio"
       - Si el país NO TIENE convenio: usa "tarifa_normal"
       - Las bases mínimas para conceptos extranjeros son 0 (sin base mínima)
    
    5. **VALORES MONETARIOS**:
       - Extrae valores en la moneda original
       - Si hay conversión a pesos, especifica la tasa de cambio
       - Identifica si hay IVA aplicado
    
    EJEMPLOS DE ANÁLISIS:
    
    Ejemplo 1 - Fuente Nacional:
    - Servicio: "Consultoría técnica para proyecto en Bogotá"
    - Pregunta "uso en Colombia": SÍ → ES FUENTE NACIONAL
    - Resultado: Aplicar retención según normativa colombiana
    
    Ejemplo 2 - Fuente Extranjera con Convenio:
    - Servicio: "Licencia de software usado en España"
    - Todas las preguntas: NO → ES FUENTE EXTRANJERA
    - País: España (TIENE convenio)
    - Resultado: Aplicar tarifa_convenio del concepto correspondiente
    
    Ejemplo 3 - Fuente Extranjera sin Convenio:
    - Servicio: "Honorarios por servicios en Estados Unidos"
    - Todas las preguntas: NO → ES FUENTE EXTRANJERA
    - País: Estados Unidos (NO TIENE convenio)
    - Resultado: Aplicar tarifa_normal del concepto correspondiente
    
    IMPORTANTE:
    - Si NO puedes identificar un concepto específico, indica "CONCEPTO_NO_IDENTIFICADO"
    - Si no puedes determinar el país, marca como null
    - Especifica claramente si aplica retención y por qué
    - Para conceptos extranjeros NO hay base mínima (base_pesos = 0)
    
    RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
    {{
        "es_facturacion_extranjera": true,
        "pais_proveedor": "string o null",
        "tiene_convenio_doble_tributacion": false,
        "validacion_fuente_nacional": {{
            "pregunta_1_uso_beneficio_colombia": false,
            "pregunta_2_actividad_en_colombia": false,
            "pregunta_3_asistencia_tecnica_colombia": false,
            "pregunta_4_bien_ubicado_colombia": false,
            "es_fuente_nacional": false,
            "justificacion": "string"
        }},
        "conceptos_identificados": [
            {{
                "concepto": "nombre exacto del concepto o CONCEPTO_NO_IDENTIFICADO",
                "tarifa_normal": 0.0,
                "tarifa_convenio": 0.0,
                "tarifa_aplicada": 0.0,
                "base_gravable": 0.0
            }}
        ],
        "calculo_retencion": {{
            "aplica_retencion": false,
            "valor_retencion": 0.0,
            "tarifa_aplicada_porcentaje": 0.0,
            "razon_aplicacion": "string"
        }},
        "valor_total": 0.0,
        "moneda_original": "string",
        "tasa_cambio": null,
        "iva": 0.0,
        "observaciones": ["observación 1", "observación 2"]
    }}
    """

def PROMPT_ANALISIS_CONSORCIO_EXTRANJERO(factura_texto: str, rut_texto: str, anexos_texto: str,
                                         cotizaciones_texto: str, anexo_contrato: str,
                                         conceptos_extranjeros_dict: dict, paises_convenio: list,
                                         preguntas_fuente: list, nombres_archivos_directos: List[str] = None,
                                         proveedor: str = None) -> str:
    """
    Genera el prompt optimizado para analizar consorcios con facturación extranjera.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_extranjeros_dict: Diccionario de conceptos extranjeros con tarifas
        paises_convenio: Lista de países con convenio de doble tributación
        preguntas_fuente: Lista de preguntas para determinar fuente nacional
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del consorcio extranjero (v3.0)

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    # Limitar conceptos para reducir tokens
    conceptos_limitados = dict(list(conceptos_extranjeros_dict.items())[:5])

    # Contexto de proveedor para validación de consorcio extranjero
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
    ═══════════════════════════════════════════════════════════════════
     INFORMACIÓN DEL CONSORCIO EXTRANJERO (VALIDACIÓN OBLIGATORIA)
    ═══════════════════════════════════════════════════════════════════

    **CONSORCIO EXTRANJERO ESPERADO:** {proveedor}

     VALIDACIONES OBLIGATORIAS PARA CONSORCIOS EXTRANJEROS:

    1. VALIDACIÓN DE IDENTIDAD DEL CONSORCIO:
       - Verifica que el nombre del consorcio en FACTURA coincida con: "{proveedor}"
       - Verifica el país de domicilio del consorcio
       - Si hay RUT disponible, verifica coherencia de datos
       - Reporta discrepancias en "observaciones"

    2. VALIDACIÓN DE CONSORCIADOS/INTEGRANTES:
       - Identifica TODOS los consorciados del consorcio extranjero
       - Verifica que cada consorciado tenga: identificación, nombre, porcentaje
       - Busca documentación individual de cada consorciado en anexos
       - Si faltan documentos individuales, repórtalo en "observaciones"

    3. VALIDACIÓN DE PAÍS Y CONVENIO:
       - Identifica el país de cada consorciado (pueden ser diferentes)
       - Verifica si cada país tiene convenio de doble tributación
       - Reporta si hay consorciados de diferentes países
       - Valida coherencia entre país en FACTURA y documentos

    4. VALIDACIÓN DE COHERENCIA:
       - El nombre del consorcio esperado debe aparecer en FACTURA
       - Los consorciados deben estar claramente identificados
       - La suma de porcentajes debe ser 100% (o reportar si no lo es)
       - Verifica que todos los documentos se refieran al mismo consorcio

    5. REPORTE DE INCONSISTENCIAS:
       - Si nombre consorcio ≠ nombre esperado → agregar a observaciones
       - Si faltan documentos de consorciados → agregar a observaciones
       - Si suma de porcentajes ≠ 100% → agregar a observaciones
       - Si hay consorciados de diferentes países → reportar cada país
       - Si país no coincide entre documentos → agregar a observaciones

    """

    return f"""
    ANALIZA ESTE CONSORCIO CON FACTURACIÓN EXTRANJERA Y CALCULA RETENCIONES POR CONSORCIADO.
{contexto_proveedor}
    ═══════════════════════════════════════════════════════════════════
     REGLA CRÍTICA DE FORMATO DE SALIDA:
    ═══════════════════════════════════════════════════════════════════

    ⚠️ IMPORTANTE: Debes retornar SIEMPRE UN SOLO JSON de salida.
       - Incluso si hay múltiples documentos de diferentes proveedores
       - Analiza el documento principal (factura/orden de pago)
       - Si hay información contradictoria entre documentos, repórtala en "observaciones"
       - NO generes un array de JSONs con múltiples objetos
       - SOLO retorna UN objeto JSON único

    CONCEPTOS RETEFUENTE EXTRANJEROS (usa NOMBRE EXACTO):
    {json.dumps(conceptos_limitados, indent=1, ensure_ascii=False)}

    PAÍSES CON CONVENIO: {paises_convenio}

    DOCUMENTOS DISPONIBLES:

    {_generar_seccion_archivos_directos(nombres_archivos_directos)} 
    
    FACTURA:
    {factura_texto}
    
    RUT:
    {rut_texto if rut_texto else "NO DISPONIBLE"}
    
    ANEXOS:
    {anexos_texto if anexos_texto else "NO DISPONIBLES"}
    
    INSTRUCCIONES PARA CONSORCIO EXTRANJERO:
    
    1. **VALIDACIÓN DE FUENTE NACIONAL** (SÍ/NO):
    {chr(10).join([f'   - {pregunta}' for pregunta in preguntas_fuente])}
    
    2. **EXTRACCIÓN**: nombre, NIT y % de cada consorciado
    3. **IDENTIFICACIÓN**: concepto extranjero + país proveedor
    4. **APLICACIÓN DE TARIFA**: convenio o normal según país
    5. **CÁLCULO**: valor_proporcional = valor_total * (porcentaje/100)
    6. **RETENCIÓN**: valor_retencion = valor_proporcional * tarifa_aplicada
    
    REGLAS ESPECIALES EXTRANJERAS:
    - Si es fuente nacional: aplicar normativa colombiana estándar
    - Si es fuente extranjera: aplicar tarifas de pagos al exterior
    - No hay base mínima para conceptos extranjeros
    - Verificar convenio por país del proveedor
    
    RESPONDE SOLO JSON COMPLETO:
    {{
        "es_consorcio": true,
        "es_facturacion_extranjera": true,
        "pais_proveedor": "string",
        "tiene_convenio_doble_tributacion": false,
        "validacion_fuente_nacional": {{
            "pregunta_1_uso_beneficio_colombia": false,
            "pregunta_2_actividad_en_colombia": false,
            "pregunta_3_asistencia_tecnica_colombia": false,
            "pregunta_4_bien_ubicado_colombia": false,
            "es_fuente_nacional": false,
            "justificacion": "string"
        }},
        "consorcio_info": {{
            "nombre_consorcio": "string",
            "nit_consorcio": "string",
            "total_consorciados": 0
        }},
        "consorciados": [{{
            "nombre": "string",
            "nit": "string",
            "porcentaje_participacion": 0.0,
            "valor_proporcional": 0.0,
            "aplica_retencion": true,
            "valor_retencion": 0.0,
            "tarifa_aplicada": 0.0,
            "razon_tarifa": "convenio/normal"
        }}],
        "conceptos_identificados": [{{
            "concepto": "string",
            "tarifa_normal": 0.0,
            "tarifa_convenio": 0.0,
            "tarifa_aplicada": 0.0,
            "base_gravable": 0.0
        }}],
        "resumen_retencion": {{
            "valor_total_factura": 0.0,
            "iva_total": 0.0,
            "total_retenciones": 0.0,
            "consorciados_con_retencion": 0,
            "consorciados_sin_retencion": 0
        }},
        "observaciones": []
    }}
    """


def PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO(factura_texto: str, rut_texto: str, anexos_texto: str, 
                                                       cotizaciones_texto: str, anexo_contrato: str, 
                                                       nit_administrativo: str, nombres_archivos_directos: List[str] = None) -> str:
    """
    PROMPT INTEGRADO OPTIMIZADO - EXTRACCIÓN Y CLASIFICACIÓN
    
    Analiza documentos para extraer información y clasificar el tipo de contrato
    para posterior cálculo de impuestos (Estampilla y Obra Pública).
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        nit_administrativo: NIT de la entidad administrativa
        nombres_archivos_directos: Lista de nombres de archivos analizados
        
    Returns:
        str: Prompt optimizado para extracción y clasificación
    """
    
    # Importar configuración desde config.py
    from config import (
        UVT_2025,
        CODIGOS_NEGOCIO_ESTAMPILLA,
        TERCEROS_RECURSOS_PUBLICOS,
        OBJETOS_CONTRATO_ESTAMPILLA,
        OBJETOS_CONTRATO_OBRA_PUBLICA,
        RANGOS_ESTAMPILLA_UNIVERSIDAD,
        obtener_configuracion_impuestos_integrada
    )
    
    config_integrada = obtener_configuracion_impuestos_integrada()
    
    return f"""
### TAREA: EXTRACCIÓN DE DATOS Y CLASIFICACIÓN DE CONTRATO ###
═════════════════════════════════════════════════════════════

INSTRUCCIÓN PRINCIPAL:
Eres un sistema de extracción de datos especializado en documentos contractuales colombianos.
Tu ÚNICA tarea es:
1. Extraer información específica de los documentos proporcionados
2. Clasificar el tipo de contrato basándote en el objeto extraído

NO debes:
- Calcular impuestos
- Determinar si aplican o no los impuestos
- Inventar información que no esté en los documentos
- Hacer interpretaciones más allá de la clasificación

### DOCUMENTOS PROPORCIONADOS ###
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_generar_seccion_archivos_directos(nombres_archivos_directos)}

<<INICIO_FACTURA>>
{factura_texto if factura_texto else "[NO PROPORCIONADO]"}
<<FIN_FACTURA>>

<<INICIO_RUT>>
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}
<<FIN_RUT>>

<<INICIO_ANEXOS>>
{anexos_texto if anexos_texto else "[NO PROPORCIONADO]"}
<<FIN_ANEXOS>>

<<INICIO_COTIZACIONES>>
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADO]"}
<<FIN_COTIZACIONES>>

<<INICIO_ANEXO_CONTRATO>>
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}
<<FIN_ANEXO_CONTRATO>>

### PROCESO DE EXTRACCIÓN ###
════════════════════════════

PASO 1 - EXTRAER OBJETO DEL CONTRATO:
--------------------------------------
• ORDEN DE BÚSQUEDA: Anexo Contrato → Factura → Anexos → Cotizaciones
• IDENTIFICACION : Buscar TEXTUALMENTE una seccion que mencione OBJETO DEL CONTRATO, No confundas CONCEPTO de la factura con OBJETO del contrato
• ACCIÓN: Copiar la descripción TEXTUAL EXACTA del objeto del contrato
• SI NO EXISTE LA SECCION TEXTUAL OBJETO DEL CONTRATO EN LOS DOCUMENTOS : Asignar valor "no_identificado"
• IMPORTANTE: No parafrasear, copiar literalmente

PASO 2 - EXTRAER VALORES MONETARIOS:
------------------------------------
2.1 VALOR FACTURA SIN IVA:
    • Buscar en la factura principal
    • Identificar: "subtotal", "valor antes de IVA", "base gravable"
    • SI NO EXISTE: Asignar valor 0

2.2 VALOR TOTAL DEL CONTRATO SIN ADICIONES:
    • Buscar en CUALQUIER documento disponible
    • Identificar: "valor del contrato", "valor total contrato"
    • SI NO EXISTE: Asignar valor 0

2.3 VALOR DE ADICIONES/MODIFICACIONES:
    • Buscar términos: "adición", "otrosí", "modificación", "prórroga con adición"
    • Sumar TODOS los valores de adiciones encontradas
    • SI NO EXISTE: Asignar valor 0

PASO 3 - CLASIFICAR TIPO DE CONTRATO:
-------------------------------------
Comparar el objeto extraído con estas palabras clave ESPECÍFICAS:

• Obra: {OBJETOS_CONTRATO_ESTAMPILLA['contrato_obra']['palabras_clave']}
   • Interventoría: {OBJETOS_CONTRATO_ESTAMPILLA['interventoria']['palabras_clave']}
   • Servicios conexos: {OBJETOS_CONTRATO_ESTAMPILLA['servicios_conexos_obra']['palabras_clave']}

═══ TIPO A: CONTRATO_OBRA ═══
PALABRAS CLAVE EXACTAS {OBJETOS_CONTRATO_ESTAMPILLA['contrato_obra']['palabras_clave']}


═══ TIPO B: INTERVENTORIA ═══
PALABRAS CLAVE EXACTAS: {OBJETOS_CONTRATO_ESTAMPILLA['interventoria']['palabras_clave']}


═══ TIPO C: SERVICIOS_CONEXOS ═══
PALABRAS CLAVE EXACTAS: {OBJETOS_CONTRATO_ESTAMPILLA['servicios_conexos_obra']['palabras_clave']}


═══ TIPO D: NO_APLICA ═══
Asignar cuando el objeto del contrato extraído:
• No contiene NINGUNA relación con las palabras clave de los tipos anteriores
• Es un servicio/producto completamente diferente

═══ TIPO E: NO_IDENTIFICADO ═══
Asignar cuando el objeto del contrato no se haya podido extraer de los documentos proporcionados   


### REGLAS ESTRICTAS ###
═══════════════════════

 PROHIBIDO:
1. Inventar valores o descripciones no presentes en documentos
2. Redondear o modificar valores numéricos
3. Hacer cálculos de ningún tipo
4. Interpretar más allá de la clasificación por palabras clave
5. Decidir sobre aplicación de impuestos
6. Asignar el concepto de la factura como OBJETO del contrato
7. Extraer el objeto del contrato de secciones que no mencionen TEXTUALMENTE "OBJETO DEL CONTRATO"


✓ OBLIGATORIO:
1. Copiar textualmente las descripciones encontradas
2. Usar 0 cuando no encuentres un valor
3. Usar "no_identificado" cuando no encuentres una descripción
4. Clasificar ÚNICAMENTE basándote en palabras clave exactas
5. Incluir la evidencia textual que justifica la clasificación
6. Extraer el objeto del contrato SOLAMENTE de la seccion que mencione TEXTUALMENTE OBJETO DEL CONTRATO

### FORMATO DE RESPUESTA - JSON ESTRICTO ###
════════════════════════════════════════════

Responde ÚNICAMENTE con el siguiente JSON.
NO incluyas texto antes o después del JSON:

{{
  "extraccion": {{
    "objeto_contrato": {{
      "descripcion_literal": "Copiar texto exacto del documento o 'no_identificado'",
      "documento_origen": "Nombre del documento donde se encontró o 'ninguno'",
    }},
    "valores": {{
      "factura_sin_iva": valor encontrado o 0,
      "contrato_total": valor encontrado o 0,
      "adiciones": valor encontrado o 0,
      "observaciones_valores": "Notas sobre valores encontrados o faltantes"
    }}
  }},
  
  "clasificacion": {{
    "tipo_contrato": "CONTRATO_OBRA|INTERVENTORIA|SERVICIOS_CONEXOS|NO_APLICA|NO_IDENTIFICADO",
    "palabras_clave_encontradas": ["lista", "de", "palabras", "encontradas"],
    "fragmento_evidencia": "Copiar la frase exacta del documento que contiene las palabras clave",
    "confianza_clasificacion": "ALTA|MEDIA|BAJA",
    "razon_confianza": "Explicación breve del nivel de confianza"
    
  }}
}}
"""
# ===============================
#  NUEVO PROMPT: ANÁLISIS DE IVA Y RETEIVA
# ===============================



def PROMPT_ANALISIS_IVA(factura_texto: str, rut_texto: str, anexos_texto: str, 
                                    cotizaciones_texto: str, anexo_contrato: str, 
                                    nombres_archivos_directos: list[str] = None) -> str:
    """
    Prompt optimizado para Gemini - Enfocado en extracción y clasificación de IVA.
    
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
    # Importar configuraciones de IVA
    from config import obtener_configuracion_iva
    # Obtener configuración de IVA
    config_iva = obtener_configuracion_iva()
    
    return f"""
ROL: Eres un EXTRACTOR y CLASIFICADOR de información tributaria especializado en IVA colombiano.
Tu función es ÚNICAMENTE extraer datos específicos de los documentos como el RUT el cual es el FORMULARIO DE REGISTRO UNICO TRIBUTARIO y clasificar conceptos según las categorías predefinidas.

═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA (DOCUMENTO PRINCIPAL):
{factura_texto}

RUT (si está disponible):
{rut_texto if rut_texto else "NO DISPONIBLE"}

ANEXOS (DETALLES ADICIONALES):
{anexos_texto if anexos_texto else "NO DISPONIBLES"}

COTIZACIONES (PROPUESTAS COMERCIALES):
{cotizaciones_texto if cotizaciones_texto else "NO DISPONIBLES"}

ANEXO CONCEPTO CONTRATO (OBJETO DEL CONTRATO):
{anexo_contrato if anexo_contrato else "NO DISPONIBLES"}

═══════════════════════════════════════════════════════════════════════
CATEGORÍAS DE CLASIFICACIÓN (SOLO SI NO HAY IVA EN FACTURA)
═══════════════════════════════════════════════════════════════════════

BIENES QUE NO CAUSAN IVA:
{json.dumps(config_iva['bienes_no_causan_iva'], indent=2, ensure_ascii=False)}

BIENES EXENTOS DE IVA:
{json.dumps(config_iva['bienes_exentos_iva'], indent=2, ensure_ascii=False)}

SERVICIOS EXCLUIDOS DE IVA:
{json.dumps(config_iva['servicios_excluidos_iva'], indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════════
TAREAS ESPECÍFICAS DE EXTRACCIÓN
═══════════════════════════════════════════════════════════════════════

1.  CRÍTICO - SOLO DEL RUT (FORMULARIO DE REGISTRO ÚNICO TRIBUTARIO) - EXTRAER:

    INSTRUCCIÓN OBLIGATORIA PARA DOCUMENTOS LARGOS:

   • DEBES escanear COMPLETAMENTE TODO el documento de INICIO a FIN
   • El RUT puede estar en CUALQUIER página del documento (inicio, medio o final)
   • NO asumas ubicaciones - REVISA TODAS LAS PÁGINAS sin excepción
   • Busca indicadores del RUT: "REGISTRO ÚNICO TRIBUTARIO", "RUT", "DIAN", "NIT"
   • Es OBLIGATORIO revisar el documento COMPLETO

    EXTRACCIÓN ESPECÍFICA una vez encuentres el RUT:

   • Buscar SOLO en la sección "RESPONSABILIDADES, CALIDADES Y ATRIBUTOS"
   • NO te fijes en pequeñas casillas marcadas, Solo en el texto principal
   • Identificar texto de responsabilidad:
     - "48 - Impuesto sobre las ventas - IVA" → es_responsable_iva: true
     - "49 - No responsable de IVA" → es_responsable_iva: false
     - "53 - Régimen simple de tributación" → es_responsable_iva: false

    VALIDACIONES DE CASOS ESPECIALES:

   • Si encuentras el RUT pero NO tiene código de responsabilidad IVA:
     → "es_responsable_iva": null
     → "codigo_encontrado": 0.0
     → "texto_evidencia": "RUT encontrado pero sin código de responsabilidad IVA"

   • Si NO encuentras el RUT en ninguna parte del documento:
     → "rut_disponible": false
     → "es_responsable_iva": null
     → "codigo_encontrado": 0.0
     → "texto_evidencia": "RUT no encontrado después de escanear todo el documento"

2. SOLO DE LA FACTURA - EXTRAER:
   • Valor del IVA (buscar: "IVA", "I.V.A", "Impuesto")
   • Porcentaje del IVA (usualmente 19 si 19%, 5 si 5% o 0 si 0%) (extraelo como un numero entero >= 0)
   • Valor subtotal (factura SIN IVA)
   • Valor total (factura CON IVA incluido)
   • Concepto facturado (copiar textualmente la descripción del servicio/bien)

3. CLASIFICACIÓN DEL CONCEPTO:
   
   SI LA FACTURA TIENE IVA (valor > 0):
   → Asignar categoría: "gravado"
   
   SI LA FACTURA NO TIENE IVA (valor = 0 o no menciona IVA):
   → Comparar el concepto extraído con las listas de categorías proporcionadas
   → Asignar categoría: "no_causa_iva" | "exento" | "excluido" | "no_clasificado"
   
   IMPORTANTE: Si no puedes clasificar con certeza, usa "no_clasificado"

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA (JSON ESTRICTO)
═══════════════════════════════════════════════════════════════════════

Responde ÚNICAMENTE con el siguiente JSON, sin texto adicional:

{{
    "extraccion_rut": {{
        "es_responsable_iva": true | false | null,
        "codigo_encontrado": 48 | 49 | 53 | 0.0,
        "texto_evidencia": "Texto exacto donde encontraste la información"
    }},
    "extraccion_factura": {{
        "valor_iva": valor encontrado o 0.0,
        "porcentaje_iva": valor encontrado o 0,
        "valor_subtotal_sin_iva": valor encontrado o 0.0,
        "valor_total_con_iva": valor encontrado o 0.0,
        "concepto_facturado": "Transcripción textual del concepto/descripción",
    }},
    "clasificacion_concepto": {{
        "categoria": "gravado|no_causa_iva|exento|excluido|no_clasificado",
        "justificacion": "Breve explicación de por qué se asignó esta categoría",
        "coincidencia_encontrada": "Item específico de las listas que coincide (si aplica)"
    }},
    "validaciones": {{
        "rut_disponible": true/false
    }}
}}

═══════════════════════════════════════════════════════════════════════
REGLAS CRÍTICAS
═══════════════════════════════════════════════════════════════════════

• NO interpretes ni deduzcas información que no esté explícita
• Si un dato no está disponible, usa 0.0 para números o "no_identificado" para textos
• La clasificación SOLO se hace si NO hay IVA en la factura
• Si hay IVA en la factura, SIEMPRE es categoría "gravado"
• Extrae EXACTAMENTE lo que aparece en los documentos
• No calcules valores que no estén explícitos en la factura

"""
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
     - "Pro Cultura" / "Procultura" / "Estampilla ProCultura"/ PROCULTURA
     - "Pro Bienestar" /  "Estampilla Bienestar"
     - "Adulto Mayor" / "Pro Adulto Mayor" / "Estampilla Adulto Mayor / Estampilla Bienestar Adulto Mayor"
     - "Universidad Pedagógica" / "Estampilla Pro Universidad Pedagógica" 
     - "Francisco José de Caldas" / "FJDC" / Estampilla Francisco José de Caldas
     - "Pro Deporte" / "Prodeporte" / "Estampilla ProDeporte"

2.  **EXTRACCIÓN DE INFORMACIÓN**:
   Para cada estampilla identificada, extrae:
   • **Nombre exacto** como aparece en el documento
   • **Porcentaje** (ej: 1.5 , 2.0 , 0.5 , 1.1)
   • **Valor a deducir** en pesos colombianos
   • **Texto de referencia** donde se encontró la información

3.  **VALIDACIÓN DE INFORMACIÓN COMPLETA**:
   • **INFORMACIÓN COMPLETA**: Nombre + Porcentaje + Valor → Estado: "preliquidado"
   • **INFORMACIÓN INCOMPLETA**: Solo nombre o porcentaje sin valor → Estado: "preliquidacion_sin_finalizar"
   • **NO IDENTIFICADA**: No se encuentra información → Estado: "no_aplica_impuesto"

4.  **CONSOLIDACIÓN ACUMULATIVA**:
   • Si FACTURA tiene info de 3 estampillas Y ANEXOS tienen info de 2 adicionales
   • RESULTADO: Mostrar las 5 estampillas consolidadas
   • Si hay duplicados, priorizar información más detallada

5.  **OBSERVACIONES ESPECÍFICAS**:
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
  "valor": 150000,
  "estado": "preliquidado"
}}

 **EJEMPLO 2 - INFORMACIÓN INCOMPLETA**:
Anexo: "Aplica estampilla Pro Bienestar"
Resultado: {{
  "nombre_estampilla": "Bienestar",
  "porcentaje": null,
  "valor": null,
  "estado": "preliquidacion_sin_finalizar",
  "observaciones": "Se menciona la estampilla pero no se encontró porcentaje ni valor"
}}

 **EJEMPLO 3 - NO IDENTIFICADA**:
Resultado: {{
  "nombre_estampilla": "Prodeporte",
  "porcentaje": null,
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
            "valor": 150000,
            "estado": "preliquidado",
            "texto_referencia": "Factura línea 15: Estampilla Pro Cultura 1.5% = $150,000",
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Bienestar",
            "porcentaje": null,
            "valor": null,
            "estado": "preliquidacion_sin_finalizar",
            "texto_referencia": "Anexo página 2: Aplica estampilla Pro Bienestar",
            "observaciones": "Se menciona la estampilla pero no se encontró porcentaje ni valor específico"
        }},
        {{
            "nombre_estampilla": "Adulto Mayor",
            "porcentaje": null,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }},
        {{
            "nombre_estampilla": "Prouniversidad Pedagógica",
            "porcentaje": null,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }},
        {{
            "nombre_estampilla": "Francisco José de Caldas",
            "porcentaje": null,
            "valor": null,
            "estado": "no_aplica_impuesto",
            "texto_referencia": null,
            "observaciones": "No se identificó información referente a esta estampilla en los adjuntos"
        }},
        {{
            "nombre_estampilla": "Prodeporte",
            "porcentaje": null,
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


def PROMPT_ANALISIS_TASA_PRODEPORTE(factura_texto: str, anexos_texto: str, observaciones_texto: str = "", nombres_archivos_directos: list[str] = None) -> str:
    """
    Prompt para extracción de datos de Tasa Prodeporte.

    Gemini SOLO extrae datos, NO calcula ni valida.
    Python realiza todas las validaciones y cálculos.

    Args:
        factura_texto: Texto extraído de la factura
        anexos_texto: Texto de anexos adicionales
        observaciones_texto: Observaciones del usuario
        nombres_archivos_directos: Lista de nombres de archivos directos

    Returns:
        str: Prompt formateado para Gemini
    """
    return f"""
ANALISIS DE TASA PRODEPORTE - SOLO EXTRACCION DE DATOS

Tu responsabilidad es UNICAMENTE extraer informacion de los documentos.
NO debes calcular ningun impuesto, solo identificar datos.

═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA:
{factura_texto}

OBSERVACIONES DEL USUARIO:
{observaciones_texto if observaciones_texto else "NO DISPONIBLES"}

ANEXOS:
{anexos_texto if anexos_texto else "NO DISPONIBLES"}

═══════════════════════════════════════════════════════════════════════
TAREAS DE EXTRACCION
═══════════════════════════════════════════════════════════════════════

1. VALORES DE FACTURA (extraer de la factura):
   - factura_con_iva: Valor total con IVA incluido
   - factura_sin_iva: Valor total sin IVA (subtotal)
   - iva: Valor del IVA



2. MENCION DE TASA PRODEPORTE (analizar SOLO las observaciones):
   - aplica_tasa_prodeporte: true si encuentras mencion de " validar tasa prodeporte",
     "aplicar tasa prodeporte", "revisar tasa pro deporte" o similares que indiquen la aplicacion de la tasa prodeporte. 
   - aplica_tasa_prodeporte: False si no  encuentras mencion de tasa prodeporte o si encuentras " no aplicar tasa prodeporte" o similares que indiquen que NO se debe aplicar.
   - texto_mencion_tasa: Copia textualmente el fragmento donde identificaste la   mencion de si aplica o no aplica .
     Debe ser el texto LITERAL de las observaciones. Si no encuentras mencion, string vacio "".

3. MUNICIPIO/DEPARTAMENTO (analizar SOLO las observaciones):
   - municipio_identificado: Nombre del municipio o departamento mencionado
   - texto_municipio: Copia textualmente el fragmento donde identificaste el municipio.
     Debe ser el texto LITERAL de las observaciones. Si no encuentras, string vacio "".

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA JSON
═══════════════════════════════════════════════════════════════════════

{{
    "factura_con_iva": 0.0,
    "factura_sin_iva": 0.0,
    "iva": 0.0,
    "aplica_tasa_prodeporte": false,
    "texto_mencion_tasa": "",
    "municipio_identificado": "",
    "texto_municipio": ""
}}

═══════════════════════════════════════════════════════════════════════
REGLAS IMPORTANTES
═══════════════════════════════════════════════════════════════════════

• Si NO encuentras un valor, usa 0.0 para numeros y "" para textos
• Los textos copiados deben ser LITERALES, sin interpretacion
• NO inventes informacion que no este en los documentos
• Si un campo no aplica o no lo encuentras, dejalo vacio o en 0
• Para valores monetarios, extrae solo numeros (sin simbolos $ ni comas)
    """


if __name__ == '__main__':
    
   
    import sys
    import os
    # Asegurar que el directorio raíz esté en sys.path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # Llamada correcta: la función acepta 5 argumentos
    prompt = PROMPT_ANALISIS_IVA("hola", "rut", "anexo", "cotizacion", "anexo")
    print(prompt)
