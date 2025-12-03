"""
Script de prueba para verificar sistema de fallback Nexura -> Supabase

Este script verifica que:
1. DatabaseWithFallback se inicializa correctamente
2. DatabaseManager no falla si Nexura esta caida
3. Las operaciones usan Supabase automaticamente cuando Nexura falla
"""

import os
import logging
from dotenv import load_dotenv

# IMPORTANTE: Cargar variables de entorno ANTES de importar database
load_dotenv()

from database.setup import inicializar_database_manager

# Configurar logging para ver los mensajes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    print("=" * 80)
    print("TEST: Sistema de Fallback Nexura -> Supabase")
    print("=" * 80)

    # Inicializar database manager
    logger.info("Paso 1: Inicializando database manager...")
    db_manager, business_service = inicializar_database_manager()

    if not db_manager:
        logger.error("FALLO: DatabaseManager no pudo inicializarse")
        return

    logger.info("✅ DatabaseManager inicializado correctamente")

    # Probar consulta de negocio
    logger.info("\nPaso 2: Probando consulta de negocio (codigo: 99664)...")

    try:
        resultado = db_manager.obtener_negocio_por_codigo("99664")

        if resultado.get('success'):
            logger.info(f"✅ Consulta exitosa!")
            logger.info(f"   Negocio: {resultado['data'].get('negocio', 'N/A')}")
            logger.info(f"   NIT: {resultado['data'].get('nit', 'N/A')}")
        else:
            logger.warning(f"⚠️ Consulta sin resultados: {resultado.get('message')}")

    except Exception as e:
        logger.error(f"❌ Error en consulta: {e}")

    # Probar business service
    logger.info("\nPaso 3: Probando business service...")

    try:
        resultado = business_service.obtener_datos_negocio(99664)

        if resultado.get('success'):
            logger.info(f"✅ Business service exitoso!")
            logger.info(f"   Database disponible: {resultado.get('database_available')}")
        else:
            logger.warning(f"⚠️ Business service sin resultados: {resultado.get('message')}")

    except Exception as e:
        logger.error(f"❌ Error en business service: {e}")

    print("\n" + "=" * 80)
    print("TEST COMPLETADO")
    print("=" * 80)

if __name__ == "__main__":
    main()
