# CHANGELOG - Preliquidador de Retención en la Fuente

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
