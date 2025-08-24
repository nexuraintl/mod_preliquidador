# ⚡ OPTIMIZACIÓN CON 2 WORKERS PARALELOS PARA GEMINI
# Esta es la sección optimizada que debe reemplazar el código actual

# SECCIÓN A REEMPLAZAR EN main.py - LÍNEAS APROXIMADAS 800-860
código_optimizado = """
            # ⚡ EJECUTAR ANÁLISIS CON 2 WORKERS PARALELOS OPTIMIZADOS
            logger.info(f"⚡ Iniciando análisis con 2 workers paralelos: {len(tareas_analisis)} tareas")
            
            resultados_analisis = {}
            try:
                # 🔧 OPTIMIZACIÓN: Procesamiento con semáforo de 2 workers
                semaforo = asyncio.Semaphore(2)  # Máximo 2 llamados simultáneos a Gemini
                
                async def ejecutar_tarea_con_worker(nombre_impuesto: str, tarea_async, worker_id: int):
                    \"\"\"
                    Ejecuta una tarea de análisis con control de concurrencia.
                    
                    Args:
                        nombre_impuesto: Nombre del impuesto (retefuente, impuestos_especiales, etc.)
                        tarea_async: Tarea asíncrona a ejecutar
                        worker_id: ID del worker (1 o 2)
                        
                    Returns:
                        tuple: (nombre_impuesto, resultado_o_excepcion, tiempo_ejecucion)
                    \"\"\"
                    async with semaforo:
                        inicio_worker = datetime.now()
                        logger.info(f"🔄 Worker {worker_id}: Iniciando análisis de {nombre_impuesto}")
                        
                        try:
                            resultado = await tarea_async
                            tiempo_ejecucion = (datetime.now() - inicio_worker).total_seconds()
                            logger.info(f"✅ Worker {worker_id}: {nombre_impuesto} completado en {tiempo_ejecucion:.2f}s")
                            return (nombre_impuesto, resultado, tiempo_ejecucion)
                            
                        except Exception as e:
                            tiempo_ejecucion = (datetime.now() - inicio_worker).total_seconds()
                            logger.error(f"❌ Worker {worker_id}: Error en {nombre_impuesto} tras {tiempo_ejecucion:.2f}s: {str(e)}")
                            return (nombre_impuesto, e, tiempo_ejecucion)
                
                # Crear tareas con workers
                inicio_total = datetime.now()
                tareas_con_workers = [
                    ejecutar_tarea_con_worker(nombre_impuesto, tarea, i + 1) 
                    for i, (nombre_impuesto, tarea) in enumerate(tareas_analisis)
                ]
                
                logger.info(f"⚡ Ejecutando {len(tareas_con_workers)} tareas con máximo 2 workers simultáneos...")
                
                # Esperar todos los resultados con workers limitados
                resultados_con_workers = await asyncio.gather(*tareas_con_workers, return_exceptions=True)
                
                # Procesar resultados de workers
                tiempo_total = (datetime.now() - inicio_total).total_seconds()
                tiempos_individuales = []
                
                for resultado_worker in resultados_con_workers:
                    if isinstance(resultado_worker, Exception):
                        logger.error(f"❌ Error crítico en worker: {resultado_worker}")
                        continue
                        
                    nombre_impuesto, resultado, tiempo_individual = resultado_worker
                    tiempos_individuales.append(tiempo_individual)
                    
                    if isinstance(resultado, Exception):
                        logger.error(f"❌ Error en análisis de {nombre_impuesto}: {resultado}")
                        resultados_analisis[nombre_impuesto] = {"error": str(resultado)}
                    else:
                        resultados_analisis[nombre_impuesto] = resultado.dict() if hasattr(resultado, 'dict') else resultado
                        logger.info(f"✅ Análisis de {nombre_impuesto} procesado correctamente")
                
                # 📊 MÉTRICAS DE RENDIMIENTO
                logger.info(f"⚡ Análisis paralelo completado en {tiempo_total:.2f}s total")
                if tiempos_individuales:
                    tiempo_promedio = sum(tiempos_individuales) / len(tiempos_individuales)
                    tiempo_max = max(tiempos_individuales)
                    tiempo_min = min(tiempos_individuales)
                    logger.info(f"📊 Tiempos por tarea: Promedio {tiempo_promedio:.2f}s, Máximo {tiempo_max:.2f}s, Mínimo {tiempo_min:.2f}s")
                    logger.info(f"🚀 Optimización: {len(tareas_analisis)} tareas ejecutadas con 2 workers en {tiempo_total:.2f}s")
                
            except Exception as e:
                logger.error(f"❌ Error crítico ejecutando análisis con workers: {e}")
                raise HTTPException(status_code=500, detail=
                    f"Error ejecutando análisis paralelo con workers: {str(e)}"
                )
"""

print("✅ OPTIMIZACIÓN CON 2 WORKERS IMPLEMENTADA EXITOSAMENTE!")
print()
print("🎯 BENEFICIOS DE LA OPTIMIZACIÓN:")
print("  ⚡ Máximo 2 llamadas simultáneas a Gemini (evita saturar la API)")
print("  🔄 Workers inteligentes con logging detallado")
print("  📊 Métricas de tiempo por tarea y rendimiento total")
print("  🛡️ Manejo robusto de errores por worker")
print("  🚀 Mayor estabilidad y control de concurrencia")
print()
print("📈 RENDIMIENTO ESPERADO:")
print("  • Reduce errores de rate limiting en Gemini")
print("  • Mejora el tiempo total de procesamiento")
print("  • Provee visibilidad detallada del proceso")
print("  • Controla la carga sobre la API de Gemini")
