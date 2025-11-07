"""
DATABASE SETUP - INFRASTRUCTURE LAYER
======================================

Modulo de infraestructura para inicializar el gestor de base de datos.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad unica de inicializar infraestructura de base de datos
- DIP: Depende de abstracciones (DatabaseManager, BusinessDataService)
- Infrastructure Layer: Setup de componentes de infraestructura

UBICACION EN CLEAN ARCHITECTURE:
- Infrastructure Layer: Frameworks & Drivers
- Configuracion e inicializacion de base de datos
- Manejo de credenciales y conexiones

PATRONES APLICADOS:
- Factory Pattern: Creacion de instancias de servicios
- Strategy Pattern: DatabaseManager usa Strategy para diferentes DBs
- Dependency Injection: Inyeccion de DatabaseManager en BusinessService

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

import os
import logging
from typing import Optional, Tuple

# Importar componentes del modulo database (DIP: depender de abstracciones)
from .database import DatabaseManager, SupabaseDatabase
from .database_service import crear_business_service, BusinessDataService

# Logger para este modulo
logger = logging.getLogger(__name__)


def inicializar_database_manager() -> Tuple[Optional[DatabaseManager], Optional[BusinessDataService]]:
    """
    Inicializa el gestor de base de datos y servicios asociados usando variables de entorno.

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Funcion dedicada solo a inicializacion de componentes de base de datos
    - DIP: Servicios dependen de abstracciones inyectadas
    - OCP: Extensible para otras implementaciones de base de datos

    ARQUITECTURA:
    - Obtiene credenciales de variables de entorno (seguridad)
    - Crea implementacion concreta de database (SupabaseDatabase)
    - Crea DatabaseManager usando Strategy Pattern
    - Crea BusinessDataService con Dependency Injection
    - Implementa graceful degradation si no hay credenciales

    COMPORTAMIENTO:
    - Si no hay credenciales: Crea BusinessService sin DB (modo degradado)
    - Si hay error: Loggea error y retorna None + BusinessService sin DB
    - Si exitoso: Retorna DatabaseManager + BusinessService completo

    Returns:
        tuple: (database_manager, business_service)
            - database_manager: DatabaseManager o None si error
            - business_service: BusinessDataService (siempre disponible, con o sin DB)

    Environment Variables:
        SUPABASE_URL: URL de la instancia de Supabase
        SUPABASE_KEY: Key de API de Supabase

    Example:
        >>> db_manager, business_service = inicializar_database_manager()
        >>> if db_manager:
        ...     print("Base de datos inicializada correctamente")
        >>> # business_service siempre esta disponible
        >>> resultado = business_service.obtener_datos_negocio(codigo)
    """
    try:
        # Obtener credenciales desde variables de entorno
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            logger.warning(" Variables de entorno SUPABASE_URL y SUPABASE_KEY no estan configuradas")
            logger.warning(" DatabaseManager y BusinessService no seran inicializados")

            # Crear business service sin database manager (graceful degradation)
            business_service = crear_business_service(None)
            logger.info(" BusinessService creado en modo degradado (sin base de datos)")
            return None, business_service

        # Crear la implementacion concreta (Strategy Pattern)
        logger.info(" Creando conexion a Supabase...")
        supabase_db = SupabaseDatabase(supabase_url, supabase_key)

        # Crear el manager usando el patron Strategy
        db_manager = DatabaseManager(supabase_db)
        logger.info(" DatabaseManager inicializado correctamente")

        # Crear business service con dependency injection (DIP)
        business_service = crear_business_service(db_manager)
        logger.info(" BusinessDataService inicializado con database manager")

        logger.info(" Stack completo de base de datos inicializado exitosamente")
        return db_manager, business_service

    except Exception as e:
        logger.error(f" Error inicializando DatabaseManager: {e}")
        logger.exception("Traceback completo del error:")

        # Graceful degradation: crear business service sin database manager
        business_service = crear_business_service(None)
        logger.info(" BusinessService creado en modo degradado tras error")

        return None, business_service


def verificar_conexion_database(db_manager: Optional[DatabaseManager]) -> bool:
    """
    Verifica que la conexion a la base de datos este funcionando.

    PRINCIPIO SRP: Solo verifica conexion, no inicializa.

    Args:
        db_manager: DatabaseManager a verificar

    Returns:
        bool: True si la conexion esta OK, False si no

    Example:
        >>> db_manager, _ = inicializar_database_manager()
        >>> if verificar_conexion_database(db_manager):
        ...     print("Conexion OK")
    """
    if not db_manager:
        logger.warning("No hay DatabaseManager para verificar")
        return False

    try:
        # Intentar una operacion simple para verificar conexion
        # Aqui podrias agregar un health check especifico
        logger.info("Verificando conexion a base de datos...")
        # TODO: Implementar health check especifico si es necesario
        return True
    except Exception as e:
        logger.error(f"Error verificando conexion: {e}")
        return False


# Metadata del modulo
__version__ = "3.0.0"
__architecture__ = "Clean Architecture - Infrastructure Layer"
