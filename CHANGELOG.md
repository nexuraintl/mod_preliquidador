# CHANGELOG - Preliquidador de Retención en la Fuente

## [2.2.0] - 2025-08-18

### 🆕 Añadido
- **Nueva funcionalidad: 6 Estampillas Generales**: Implementación completa del análisis e identificación de estampillas generales
  - 🎨 **Procultura** - Estampilla Pro Cultura
  - 🏥 **Bienestar** - Estampilla Pro Bienestar 
  - 👴 **Adulto Mayor** - Estampilla Pro Adulto Mayor
  - 🎓 **Prouniversidad Pedagógica** - Estampilla Pro Universidad Pedagógica
  - 🔬 **Francisco José de Caldas** - Estampilla Francisco José de Caldas
  - ⚽ **Prodeporte** - Estampilla Pro Deporte
- **Nuevo prompt especializado**: `PROMPT_ANALISIS_ESTAMPILLAS_GENERALES` en `prompt_clasificador.py`
- **Nueva función Gemini**: `analizar_estampillas_generales()` en clase `ProcesadorGemini`
- **Nuevo módulo de validación**: `liquidador_estampillas_generales.py` con funciones pydantic
- **Procesamiento universal**: Las estampillas generales aplican para TODOS los NITs administrativos
- **Integración completa**: Funcionalidad agregada tanto en procesamiento paralelo como individual

### 🔄 Cambiado
- **Procesamiento paralelo expandido**: Ahora incluye 4 tareas simultáneas con Gemini:
  1. Análisis de Retefuente
  2. Análisis de Impuestos Especiales (estampilla universidad + obra pública)
  3. Análisis de IVA y ReteIVA 
  4. **Análisis de Estampillas Generales** (🆕 NUEVO)
- **Estrategia de análisis acumulativo**: Revisa TODOS los documentos (factura, anexos, contrato, RUT) y consolida información
- **Estados específicos**: Implementación de 3 estados para cada estampilla:
  - `"preliquidacion_completa"` - Información completa (nombre + porcentaje + valor)
  - `"preliquidacion_sin_finalizar"` - Información parcial (solo nombre o porcentaje sin valor)
  - `"no_aplica_impuesto"` - No se encuentra información

### 🔍 Validado
- **Validación formato Pydantic**: Modelos `EstampillaGeneral`, `ResumenAnalisisEstampillas`, `ResultadoEstampillasGenerales`
- **Función `validar_formato_estampillas_generales()`**: Valida que respuesta de Gemini coincida con modelo pydantic
- **Función `presentar_resultado_estampillas_generales()`**: Presenta información en formato correcto para JSON final
- **Corrección automática**: Sistema corrige respuestas incompletas de Gemini y genera campos faltantes

### 📊 Mejorado
- **JSON resultado final expandido**: Nueva sección `"estampillas_generales"` con estructura detallada:
  ```json
  {
    "estampillas_generales": {
      "procesamiento_exitoso": true,
      "total_estampillas_analizadas": 6,
      "estampillas": { /* acceso por nombre */ },
      "resumen": { /* estadísticas */ },
      "detalles_por_estampilla": [ /* lista completa */ ]
    }
  }
  ```
- **Archivos JSON adicionales**: Nuevo archivo `analisis_estampillas_generales.json` en Results/
- **Logs informativos mejorados**: Logs específicos para estampillas con emojis y contadores
- **Manejo de errores robusto**: Fallbacks y mensajes descriptivos para errores en estampillas

### 🔍 Técnico
- **Identificación única por nombre**: Sistema identifica variaciones comunes de nombres de estampillas
- **Extracción inteligente**: Busca porcentajes (1.5%, 2.0%) y valores monetarios en documentos
- **Texto de referencia**: Incluye ubicación exacta donde se encontró cada información
- **Solo identificación**: Módulo NO realiza cálculos, solo presenta información identificada por Gemini
- **Observaciones detalladas**: Sistema explica por qué falta información o qué se encontró parcialmente

### 🐛 Sin cambios de configuración
- **Compatible con NITs existentes**: No requiere modificar configuración de NITs en `config.py`
- **Funcionalidad aditiva**: No afecta funcionamiento de retefuente, estampilla universidad, obra pública o IVA
- **Endpoint único preservado**: Sigue siendo `/api/procesar-facturas` sin cambios en parámetros

## [2.1.1] - 2025-08-17

### 🐛 Corregido
- **Error en liquidación de facturas extranjeras**: Corrección del flujo de procesamiento para facturas internacionales
- **Validación restrictiva**: Cambiada validación que rechazaba automáticamente facturas extranjeras por redirección inteligente
- **Función especializada**: Ahora `calcular_retencion()` redirige correctamente a `liquidar_factura_extranjera()` cuando detecta facturación exterior
- **Parámetro NIT opcional**: Función `liquidar_factura_extranjera()` ya no requiere NIT obligatorio para mayor flexibilidad

### 🔧 Mejorado
- **Compatibilidad de resultados**: Verificada compatibilidad completa entre `calcular_retencion()` y `liquidar_factura_extranjera()`
- **Logs informativos**: Mejores mensajes de log para identificar cuando se usa la función especializada de extranjeras
- **Documentación de funciones**: Aclarada la funcionalidad de procesamiento de facturas internacionales

### 📝 Técnico
- **Problema identificado**: La validación en línea ~95-99 de `liquidador.py` rechazaba facturas extranjeras sin usar función especializada
- **Solución implementada**: Redirección interna desde `calcular_retencion()` a `liquidar_factura_extranjera()`
- **Función existente**: Se aprovechó la lógica ya implementada y funcional para facturas extranjeras
- **Sin cambios en main.py**: Corrección interna que no requiere modificaciones en el flujo principal

## [2.1.0] - 2025-08-16

### 🗑️ Eliminado
- **Archivo obsoleto**: Eliminado `Clasificador/clasificacion_IVA.py` (clase `ClasificadorIVA` no utilizada)
- **Código redundante**: Removida clase que duplicaba funcionalidad existente en `clasificador.py`
- **Dependencias innecesarias**: Eliminadas importaciones de configuraciones IVA no implementadas
- **Confusión arquitectural**: Removida implementación alternativa que no se integraba al flujo principal

### 🔧 Mejorado
- **Arquitectura simplificada**: Solo función `analizar_iva()` en `ProcesadorGemini` para análisis IVA
- **Código más limpio**: Eliminada duplicación de lógica entre clase especializada y función integrada
- **Mantenimiento simplificado**: Una sola implementación de análisis IVA en lugar de dos
- **Funcionalidad preservada**: Análisis completo de IVA/ReteIVA se mantiene intacto desde `clasificador.py`

### 📋 Técnico
- **Análisis realizado**: Verificación de utilidad reveló que `ClasificadorIVA` no se importaba en `main.py`
- **Función activa**: Solo `def analizar_iva()` en `clasificador.py` se utiliza en producción
- **Sin impacto**: Eliminación confirmada sin afectar funcionalidad del sistema
- **Generación JSONs**: Confirmado que resultados IVA se generan desde flujo principal, no desde clase eliminada

## [2.0.6] - 2025-08-16

### 🐛 Corregido
- **Logging duplicado**: Eliminación completa de handlers duplicados en configuración profesional
- **"Error desconocido" falso**: Corrección del manejo de casos válidos sin retención que se marcaban incorrectamente como errores
- **Conceptos descriptivos**: Reemplazo de "N/A" por mensajes descriptivos apropiados (ej: "No aplica - tercero no responsable de IVA")
- **Manejo mejorado de casos sin retención**: Distinción clara entre casos válidos sin retención vs errores técnicos
- **Logs profesionales únicos**: Configuración mejorada que previene completamente la duplicación de mensajes
- **Mensajes de error precisos**: Eliminación de mensajes genéricos "Error desconocido" por descripciones específicas

### 🔧 Mejorado
- **Liquidador de retención**: Método `_crear_resultado_no_liquidable()` genera conceptos específicos según el caso
- **Procesamiento paralelo**: Manejo robusto de casos válidos donde no aplica retención sin marcarlos como errores
- **Procesamiento individual**: Mismas mejoras aplicadas al flujo de procesamiento individual
- **Configuración de logging**: Limpieza completa de handlers existentes antes de crear nuevos
- **Validación de terceros**: Manejo seguro de casos donde el tercero no es responsable de IVA

### 📋 Técnico
- **Causa del bug**: Casos válidos de "no aplica retención" se trataban como errores en main.py
- **Solución**: Lógica mejorada que distingue entre `calculo_exitoso=False` (válido) y errores técnicos
- **Logging**: Configuración profesional con `removeHandler()` y `close()` para evitar duplicación
- **Conceptos**: Generación dinámica de mensajes descriptivos basados en el tipo de validación fallida

## [2.0.5] - 2025-08-16

### 🆕 Añadido
- **Soporte para archivos de email**: Nuevas extensiones .msg y .eml
- **Función extraer_texto_emails()**: Procesa archivos de Outlook (.msg) y email estándar (.eml)
- **Metadatos completos de email**: Extracción de ASUNTO, REMITENTE, DESTINATARIOS, FECHA, CUERPO
- **Detección de adjuntos**: Lista archivos adjuntos sin procesarlos (solo metadata)
- **Dependencia extract-msg**: Soporte robusto para archivos .msg de Outlook
- **Formato estructurado**: Texto extraído con formato legible para análisis IA
- **Decodificación inteligente**: Manejo automático de diferentes codificaciones de caracteres
- **Conversión HTML a texto**: Extracción de texto plano de emails HTML
- **Guardado automático**: Integración completa con sistema de guardado en Results/

### 🔧 Cambiado
- **validar_archivo()**: Actualizada para incluir extensiones .msg y .eml
- **procesar_archivo()**: Añadida llamada a extraer_texto_emails() para nuevas extensiones
- **Dependencias verificadas**: Sistema reporta estado de extract-msg en logs
- **Estadisticas de guardado**: Incluye información de dependencias de email

### ⚙️ Características Técnicas
- **Archivos .msg**: Procesados con extract-msg (requiere instalación)
- **Archivos .eml**: Procesados con librería email estándar (incluida en Python)
- **Fallback robusto**: Decodificación inteligente con múltiples codificaciones
- **Manejo de errores**: Guardado de errores con información detallada para debugging
- **Performance**: Sin procesamiento de adjuntos (solo listado) para eficiencia

### 📚 Documentación
- **requirements.txt**: Añadida dependencia extract-msg==0.48.4
- **CHANGELOG.md**: Documentada nueva funcionalidad de procesamiento de emails
- **README.md**: Próxima actualización con formatos soportados y ejemplos de uso

## [2.0.4] - 2025-08-14

### 🗑️ Eliminado
- **Frontend web completo**: Eliminada carpeta `Static/` con interfaz web
- **Endpoint de frontend**: Removido `GET /` que servía `index.html`
- **Archivos estáticos**: Eliminado `app.mount("/static", StaticFiles(...))` 
- **Dependencias innecesarias**: Removidas importaciones `HTMLResponse` y `StaticFiles`
- **Archivos web**: Eliminados HTML, CSS, JS del frontend
- **Clase CargadorConceptos**: Eliminada clase completa (~100 líneas) - no se utilizaba en el proyecto
- **Clase MapeadorTarifas**: Eliminada clase completa (~50 líneas) - funcionalidad redundante
- **TARIFAS_RETEFUENTE**: Eliminado diccionario de tarifas genéricas (~60 líneas) - redundante con CONCEPTOS_RETEFUENTE
- **CONCEPTOS_FALLBACK**: Eliminada lista fallback (~45 líneas) - no se utilizaba en el sistema

### 🔧 Cambiado
- **API REST pura**: Sistema enfocado 100% en endpoints de backend
- **Uso exclusivo con Postman/cURL**: Sin interfaz gráfica, solo programático
- **Performance mejorada**: Startup más rápido sin montar archivos estáticos
- **Arquitectura simplificada**: Backend puro sin responsabilidades de frontend
- **Testing optimizado**: Diseño específico para herramientas de API testing
- **Conceptos de retefuente**: Movidos `CONCEPTOS_RETEFUENTE` de `main.py` a `config.py`
- **Importaciones actualizadas**: Todos los módulos importan conceptos desde `config.py`

### ⚡ Beneficios
- **Menos complejidad**: ~270 líneas de código eliminadas + carpeta frontend completa
- **Startup más rápido**: Sin procesamiento de archivos estáticos ni clases innecesarias
- **Mantenimiento simplificado**: Solo lógica de backend y código que realmente se utiliza
- **Menor superficie de bugs**: Sin frontend ni clases redundantes que mantener
- **API más profesional**: Enfocada exclusivamente en funcionalidad de negocio
- **Configuración centralizada**: Conceptos de retefuente en su ubicación lógica
- **Código más limpio**: Eliminadas todas las redundancias y código muerto

### 📚 Documentación
- **README.md**: Actualizada guía de uso eliminando referencias al frontend web
- **README.md**: Enfoque exclusivo en uso via API REST con Postman/cURL
- **README.md**: Eliminada sección de interfaz web y navegador

## [2.0.3] - 2025-08-14

### 🗑️ Eliminado
- **Endpoint redundante**: Eliminado `/health` (funcionalidad integrada en `/api/diagnostico`)
- **Código duplicado**: Removidas ~40 líneas de código redundante del health check básico
- **Optimización**: Mantenido solo `/api/diagnostico` que proporciona información más completa y detallada

### 🔧 Cambiado
- **Diagnóstico unificado**: `/api/diagnostico` es ahora el único endpoint de verificación del sistema
- **Performance**: Eliminada redundancia entre health check básico y diagnóstico completo
- **Mantenimiento**: Menor superficie de código para mantener y debuggear
- **Funcionalidad**: Sin pérdida de capacidades, `/api/diagnostico` incluye toda la información del health check eliminado

### 📚 Documentación
- **README.md**: Actualizada sección de endpoints disponibles
- **README.md**: Removida documentación del endpoint `/health` eliminado
- **README.md**: Clarificada funcionalidad del endpoint `/api/diagnostico` como único punto de verificación

## [2.0.2] - 2025-08-14

### 🗑️ Eliminado
- **Endpoints obsoletos**: Eliminados `/procesar-documentos` y `/api/procesar-facturas-test`
- **Endpoint innecesario**: Eliminado `/api/estructura` (funcionalidad duplicada en `/api/diagnostico`)
- **Archivo obsoleto**: Eliminado `Extraccion/extraer_conceptos.py` (conceptos ya hardcodeados en main.py)
- **Código muerto**: Removidos endpoints duplicados que no estaban siendo utilizados
- **Optimización**: Simplificada arquitectura de endpoints manteniendo solo los esenciales

### 🔧 Cambiado
- **Endpoints optimizados**: Sistema usa endpoints únicos sin duplicaciones de funcionalidad
- **Módulo Extraccion**: Simplificado removiendo scripts no utilizados en producción
- **Diagnóstico centralizado**: `/api/diagnostico` mantiene toda la información de estructura del sistema
- **Mantenimiento**: Código más limpio con menos endpoints y archivos que mantener

## [2.0.1] - 2025-08-13

### 🐛 Corregido
- **CRÍTICO**: Error timeout de Gemini aumentado de 30s a 90s para análisis de impuestos especiales
- **CRÍTICO**: Error `'dict' object has no attribute 'es_facturacion_exterior'` en liquidación de retefuente
- **CRÍTICO**: Implementada función `liquidar_retefuente_seguro()` para manejo robusto de estructuras de datos
- Timeout escalonado para Gemini: 60s estándar, 90s impuestos especiales, 120s consorcios
- Manejo seguro de conversión de dict a objeto AnalisisFactura
- Logging mejorado con información detallada de timeouts y errores de estructura
- Validación robusta de campos requeridos antes de liquidación

### 🔧 Cambiado
- Timeout de Gemini: 30s → 60s (estándar), 90s (impuestos especiales), 120s (consorcios)
- Liquidación de retefuente usa función segura con verificación de estructura
- Manejo de errores mejorado con fallbacks seguros
- Logging profesional sin duplicaciones con información específica de timeouts

### 🆕 Añadido
- Función `liquidar_retefuente_seguro()` para manejo seguro de análisis de Gemini
- Validación automática de campos requeridos en análisis de retefuente
- Creación manual de objetos AnalisisFactura desde estructuras JSON
- Mensajes de error específicos con información de debugging
- Guardado automático de análisis de retefuente individual en Results/
- Timeout variable según complejidad del análisis (estándar/especiales/consorcios)

## [2.0.0] - 2025-08-08

### 🆕 Añadido
- Sistema integrado de múltiples impuestos con procesamiento paralelo
- Estampilla Pro Universidad Nacional según Decreto 1082/2015
- Contribución a obra pública 5% para contratos de construcción
- IVA y ReteIVA con análisis especializado
- Detección automática de impuestos aplicables por NIT
- Procesamiento paralelo cuando múltiples impuestos aplican
- Guardado automático de JSONs organizados por fecha en Results/

### 🔧 Cambiado
- Arquitectura modular completamente renovada
- Endpoint principal único `/api/procesar-facturas`
- Liquidadores especializados por tipo de impuesto
- Análisis de Gemini optimizado para múltiples impuestos
- Configuración unificada para todos los impuestos

### 🗑️ Eliminado
- Endpoints duplicados de versiones anteriores
- Código redundante de procesamiento individual

## [1.5.0] - 2025-07-30

### 🆕 Añadido
- Procesamiento de consorcios con matriz de participaciones
- Análisis de facturas extranjeras con tarifas especiales
- Artículo 383 para personas naturales con deducciones
- Preprocesamiento Excel optimizado

### 🔧 Cambiado
- Mejoras en extracción de texto de PDFs
- Optimización de prompts de Gemini
- Validación mejorada de conceptos de retefuente

## [1.0.0] - 2025-07-15

### 🆕 Añadido
- Sistema base de retención en la fuente
- Integración con Google Gemini AI
- Extracción de texto de PDF, Excel, Word
- Clasificación automática de documentos
- Liquidación según normativa colombiana
- Frontend web responsive
- API REST con FastAPI
- Guardado de resultados en JSON

### ⚙️ Configuración Inicial
- Configuración de NITs administrativos
- Conceptos de retefuente desde RETEFUENTE_CONCEPTOS.xlsx
- Variables de entorno para APIs
- Estructura modular del proyecto
