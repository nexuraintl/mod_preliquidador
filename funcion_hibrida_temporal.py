async def _llamar_gemini_hibrido_factura(self, prompt: str, archivos_directos: List[UploadFile]) -> str:
    """
    FUNCIÓN HÍBRIDA PARA ANÁLISIS DE FACTURA: Prompt + Archivos directos para análisis de retefuente.
    
    FUNCIONALIDAD:
    ✅ Análisis especializado de facturas con multimodalidad
    ✅ Combina prompt de análisis + archivos PDFs/imágenes
    ✅ Optimizado para análisis de retefuente, consorcios y extranjera
    ✅ Reutilizable para todos los tipos de análisis de facturas
    ✅ Timeout extendido para análisis complejo
    
    Args:
        prompt: Prompt especializado para análisis (PROMPT_ANALISIS_FACTURA, etc.)
        archivos_directos: Lista de archivos para envío directo a Gemini
        
    Returns:
        str: Respuesta de Gemini con análisis completo
        
    Raises:
        ValueError: Si hay error en la llamada a Gemini
    """
    try:
        # Timeout extendido para análisis de facturas (más complejo que clasificación)
        timeout_segundos = 120.0  # 2 minutos para análisis detallado
        
        logger.info(f"🧠 Análisis híbrido de factura con timeout de {timeout_segundos}s")
        logger.info(f"📋 Contenido: 1 prompt de análisis + {len(archivos_directos)} archivos directos")
        
        # ✅ CREAR CONTENIDO MULTIMODAL CORRECTO PARA ANÁLISIS
        contenido_multimodal = []
        
        # Agregar prompt de análisis (primer elemento)
        contenido_multimodal.append(prompt)
        logger.info(f"✅ Prompt de análisis agregado: {len(prompt):,} caracteres")
        
        # ✅ PROCESAR ARCHIVOS DIRECTOS PARA ANÁLISIS
        for i, archivo in enumerate(archivos_directos):
            try:
                # Resetear puntero y leer archivo
                if hasattr(archivo, 'seek'):
                    await archivo.seek(0)
                
                archivo_bytes = await archivo.read()
                
                # Determinar MIME type por magic bytes o extensión
                nombre_archivo = getattr(archivo, 'filename', f'archivo_analisis_{i+1}')
                
                if archivo_bytes.startswith(b'%PDF'):
                    # PDF
                    archivo_objeto = {
                        "mime_type": "application/pdf",
                        "data": archivo_bytes
                    }
                    logger.info(f"✅ PDF para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes)")
                elif archivo_bytes.startswith((b'\xff\xd8\xff', b'\x89PNG')):
                    # Imagen JPEG o PNG
                    if archivo_bytes.startswith(b'\xff\xd8\xff'):
                        mime_type = "image/jpeg"
                    else:
                        mime_type = "image/png"
                    archivo_objeto = {
                        "mime_type": mime_type,
                        "data": archivo_bytes
                    }
                    logger.info(f"✅ Imagen para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes, {mime_type})")
                else:
                    # Detectar por extensión como fallback
                    extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''
                    
                    mime_type_map = {
                        'pdf': 'application/pdf',
                        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                        'png': 'image/png', 'gif': 'image/gif',
                        'bmp': 'image/bmp', 'tiff': 'image/tiff', 'tif': 'image/tiff',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_type_map.get(extension, 'application/octet-stream')
                    
                    archivo_objeto = {
                        "mime_type": mime_type,
                        "data": archivo_bytes
                    }
                    logger.info(f"✅ Archivo para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes, {mime_type})")
                
                contenido_multimodal.append(archivo_objeto)
                
            except Exception as e:
                logger.error(f"❌ Error procesando archivo {i+1} para análisis: {e}")
                continue
        
        # ✅ LLAMAR A GEMINI CON CONTENIDO MULTIMODAL PARA ANÁLISIS
        logger.info(f"🚀 Enviando análisis a Gemini: {len(contenido_multimodal)} elementos")
        
        loop = asyncio.get_event_loop()
        
        respuesta = await asyncio.wait_for(
            loop.run_in_executor(
                None, 
                lambda: self.modelo.generate_content(contenido_multimodal)
            ),
            timeout=timeout_segundos
        )
        
        if not respuesta:
            raise ValueError("Gemini devolvió respuesta None en análisis híbrido")
            
        if not hasattr(respuesta, 'text') or not respuesta.text:
            raise ValueError("Gemini devolvió respuesta sin texto en análisis híbrido")
            
        texto_respuesta = respuesta.text.strip()
        
        if not texto_respuesta:
            raise ValueError("Gemini devolvió texto vacío en análisis híbrido")
            
        logger.info(f"✅ Análisis híbrido de factura completado: {len(texto_respuesta):,} caracteres")
        return texto_respuesta
        
    except asyncio.TimeoutError:
        error_msg = f"Análisis híbrido tardó más de {timeout_segundos}s en completarse"
        logger.error(f"❌ Timeout en análisis híbrido: {error_msg}")
        raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"❌ Error en análisis híbrido de factura: {e}")
        logger.error(f"🔍 Archivos enviados: {[getattr(archivo, 'filename', 'sin_nombre') for archivo in archivos_directos]}")
        raise ValueError(f"Error híbrido en análisis de factura: {str(e)}")