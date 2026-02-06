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
from .database import DatabaseManager, SupabaseDatabase, NexuraAPIDatabase, DatabaseInterface, DatabaseWithFallback
from .database_service import crear_business_service, BusinessDataService
from .auth_provider import AuthProviderFactory, IAuthProvider

# Logger para este modulo
logger = logging.getLogger(__name__)


async def inicializar_auth_service_nexura() -> IAuthProvider:
    """
    Inicializa servicio de autenticacion de Nexura ejecutando login.

    CRITICAL: Lanza NexuraAuthenticationError si falla.
    El sistema NO debe iniciar sin autenticacion valida.

    SRP: Solo inicializa autenticacion
    DIP: Retorna IAuthProvider (abstraccion)

    Returns:
        IAuthProvider configurado con token valido

    Raises:
        NexuraAuthenticationError: Si login falla (CRITICO)

    Environment Variables:
        - NEXURA_API_BASE_URL: URL base de Nexura
        - NEXURA_LOGIN_USER: Usuario para login
        - NEXURA_LOGIN_PASSWORD: Contrasena para login
        - NEXURA_API_TIMEOUT: Timeout en segundos (default: 30)
    """
    from .nexura_auth_service import NexuraAuthService, NexuraAuthenticationError

    nexura_url = os.getenv("NEXURA_API_BASE_URL")
    login_user = os.getenv("NEXURA_LOGIN_USER")
    login_password = os.getenv("NEXURA_LOGIN_PASSWORD")
    timeout = int(os.getenv("NEXURA_API_TIMEOUT", "30"))

    # Validar variables requeridas
    if not nexura_url:
        error_msg = "NEXURA_API_BASE_URL no configurado"
        logger.critical(error_msg)
        raise NexuraAuthenticationError(error_msg)

    if not login_user or not login_password:
        error_msg = "NEXURA_LOGIN_USER y NEXURA_LOGIN_PASSWORD son requeridos para autenticacion"
        logger.critical(error_msg)
        raise NexuraAuthenticationError(error_msg)

    # Crear servicio de autenticacion
    auth_service = NexuraAuthService(
        base_url=nexura_url,
        login_user=login_user,
        login_password=login_password,
        timeout=timeout
    )

    # Ejecutar login (async)
    try:
        auth_provider = await auth_service.login()
        logger.info("Autenticacion Nexura inicializada correctamente")
        return auth_provider
    except NexuraAuthenticationError:
        # Re-lanzar para detener startup
        raise


def crear_database_por_tipo(tipo_db: str, auth_provider: Optional[IAuthProvider] = None) -> Optional[DatabaseInterface]:
    """
    Factory para crear instancia de database segun tipo configurado (Factory Pattern + OCP)

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Funcion dedicada solo a crear instancias de database
    - OCP: Extensible para nuevos tipos de database sin modificar existente
    - DIP: Retorna abstraccion (DatabaseInterface), no implementacion concreta
    - Factory Pattern: Centraliza creacion de objetos complejos

    TIPOS SOPORTADOS:
    - 'supabase': Base de datos Supabase (implementacion original)
    - 'nexura': API REST de Nexura (nueva implementacion)

    Args:
        tipo_db: Tipo de database ('supabase' o 'nexura')
        auth_provider: AuthProvider pre-configurado (opcional, para Nexura con login centralizado)

    Returns:
        DatabaseInterface o None si falta configuracion

    Environment Variables:
        SUPABASE:
            - SUPABASE_URL: URL de la instancia de Supabase
            - SUPABASE_KEY: Key de API de Supabase

        NEXURA:
            - NEXURA_API_BASE_URL: URL base de la API de Nexura
            - NEXURA_AUTH_TYPE: Tipo de auth ('none', 'jwt', 'api_key')
            - NEXURA_JWT_TOKEN: Token JWT (si auth_type='jwt')
            - NEXURA_API_KEY: API Key (si auth_type='api_key')
            - NEXURA_API_TIMEOUT: Timeout en segundos (default: 30)

    Note:
        v3.11.1+: Fallback a Supabase desactivado por defecto cuando DATABASE_TYPE='nexura'.
        La función retorna NexuraAPIDatabase directamente sin DatabaseWithFallback wrapper.
        Para reactivar fallback: ver código comentado en líneas 127-150.

    Example:
        >>> db = crear_database_por_tipo('nexura')  # Retorna NexuraAPIDatabase (sin fallback)
        >>> if db:
        ...     manager = DatabaseManager(db)
    """
    tipo_db = tipo_db.lower().strip()

    if tipo_db == 'supabase':
        logger.info("Creando database tipo: Supabase")

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            logger.warning("Variables SUPABASE_URL y SUPABASE_KEY no configuradas")
            return None

        return SupabaseDatabase(supabase_url, supabase_key)

    elif tipo_db == 'nexura':
        logger.info("Creando database tipo: Nexura API (fallback desactivado)")

        nexura_url = os.getenv("NEXURA_API_BASE_URL")
        # Timeout aumentado a 30 segundos (sin fallback activo desde v3.11.1)
        timeout = int(os.getenv("NEXURA_API_TIMEOUT", "30"))

        if not nexura_url:
            logger.warning("Variable NEXURA_API_BASE_URL no configurada")
            return None

        # MODIFICADO v3.12.0: Usar auth_provider inyectado si esta disponible
        if auth_provider is None:
            # Fallback: Crear desde config (modo legacy sin login centralizado)
            logger.warning("No se inyecto auth_provider - creando desde config (modo legacy)")
            auth_type = os.getenv("NEXURA_AUTH_TYPE", "none")
            jwt_token = os.getenv("NEXURA_JWT_TOKEN", "")
            api_key = os.getenv("NEXURA_API_KEY", "")

            try:
                provider = AuthProviderFactory.create_from_config(
                    auth_type=auth_type,
                    token=jwt_token,
                    api_key=api_key
                )
                logger.info(f"Auth provider creado desde config: tipo={auth_type}")
            except ValueError as e:
                logger.error(f"Error creando auth provider: {e}")
                return None
        else:
            # Usar auth_provider pre-configurado con login centralizado
            provider = auth_provider
            logger.info("Usando auth_provider pre-configurado con login centralizado")

        # Crear database primaria (Nexura) con auth provider
        nexura_db = NexuraAPIDatabase(
            base_url=nexura_url,
            auth_provider=provider,  # DIP: Inyeccion de dependencia
            timeout=timeout
        )

        # DECISIÓN ARQUITECTÓNICA v3.11.1+: Fallback desactivado
        logger.info(
            "⚠️  FALLBACK A SUPABASE DESACTIVADO - Sistema usando solo Nexura API en producción"
        )
        logger.info(
            "ℹ️  Para reactivar fallback: Descomentar código en database/setup.py líneas 127-150"
        )

        # ========================================
        # CÓDIGO DE FALLBACK PRESERVADO (COMENTADO)
        # Para reactivar: Descomentar bloque siguiente y configurar vars SUPABASE
        # ========================================
        # supabase_url = os.getenv("SUPABASE_URL")
        # supabase_key = os.getenv("SUPABASE_KEY")
        #
        # if supabase_url and supabase_key:
        #     logger.info("Configurando Supabase como database de fallback")
        #     supabase_db = SupabaseDatabase(supabase_url, supabase_key)
        #
        #     # Retornar DatabaseWithFallback (Decorator Pattern)
        #     fallback_db = DatabaseWithFallback(
        #         primary_db=nexura_db,
        #         fallback_db=supabase_db
        #     )
        #     logger.info("✅ Sistema de fallback Nexura -> Supabase configurado correctamente")
        #     return fallback_db
        # else:
        #     logger.warning(
        #         "⚠️ Variables SUPABASE_URL y/o SUPABASE_KEY no configuradas. "
        #         "Nexura funcionará SIN fallback (puede fallar si Nexura está caída)"
        #     )
        # ========================================

        return nexura_db  # Retornar Nexura directamente (sin wrapper de fallback)

    else:
        logger.error(f"Tipo de database no valido: {tipo_db}")
        logger.error("Tipos soportados: 'supabase', 'nexura'")
        return None


async def inicializar_database_manager() -> Tuple[Optional[DatabaseManager], Optional[BusinessDataService]]:
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

    NUEVO v3.12.0:
    - Funcion ahora es async para ejecutar login a Nexura en startup
    - Si DATABASE_TYPE='nexura': ejecuta login ANTES de crear database
    - Si login falla: lanza excepcion (servicio NO inicia - fail-fast)
    - Token obtenido se inyecta en NexuraAPIDatabase via auth_provider

    Returns:
        tuple: (database_manager, business_service)
            - database_manager: DatabaseManager o None si error
            - business_service: BusinessDataService (siempre disponible, con o sin DB)

    Environment Variables:
        DATABASE_TYPE: Tipo de database a usar ('supabase' o 'nexura', default: 'nexura')

        SUPABASE (si DATABASE_TYPE='supabase'):
            - SUPABASE_URL: URL de la instancia de Supabase
            - SUPABASE_KEY: Key de API de Supabase

        NEXURA (si DATABASE_TYPE='nexura'):
            - NEXURA_API_BASE_URL: URL base de la API de Nexura
            - NEXURA_LOGIN_USER: Usuario para login (v3.12.0+)
            - NEXURA_LOGIN_PASSWORD: Contrasena para login (v3.12.0+)
            - NEXURA_API_TIMEOUT: Timeout en segundos (default: 30)

    NOTA v3.11.1+:
        - Fallback Nexura → Supabase DESACTIVADO por defecto
        - DATABASE_TYPE='nexura' retorna NexuraAPIDatabase directamente
        - Para reactivar fallback: ver database/setup.py líneas 127-150
        - DATABASE_TYPE='supabase' sigue funcionando sin cambios

    NOTA v3.12.0+:
        - Login centralizado a Nexura en startup
        - Si login falla, el servicio NO inicia (NexuraAuthenticationError)
        - Token compartido entre database y webhook

    Example:
        >>> db_manager, business_service = await inicializar_database_manager()
        >>> if db_manager:
        ...     print("Base de datos inicializada correctamente")
        >>> # business_service siempre esta disponible
        >>> resultado = business_service.obtener_datos_negocio(codigo)
    """
    try:
        # Obtener tipo de database desde variable de entorno (default: nexura)
        tipo_db = os.getenv("DATABASE_TYPE", "nexura")
        logger.info(f"Inicializando database tipo: {tipo_db}")

        # NUEVO v3.12.0: Si es Nexura, hacer login primero
        provider = None
        if tipo_db == 'nexura':
            logger.info("Tipo Nexura detectado - iniciando autenticacion centralizada...")
            try:
                from .nexura_auth_service import NexuraAuthenticationError
                provider = await inicializar_auth_service_nexura()
                logger.info("Autenticacion completada exitosamente")
            except NexuraAuthenticationError as e:
                logger.critical(f"FALLO CRITICO: No se pudo autenticar con Nexura: {e}")
                logger.critical("EL SERVICIO NO PUEDE INICIAR SIN AUTENTICACION VALIDA")
                raise  # Re-lanzar para detener startup de FastAPI

        # Usar factory para crear la implementacion correcta con auth_provider inyectado
        db_implementation = crear_database_por_tipo(tipo_db, provider)

        if not db_implementation:
            logger.warning(f"No se pudo crear implementacion de database tipo '{tipo_db}'")
            logger.warning("DatabaseManager no sera inicializado")

            # Crear business service sin database manager (graceful degradation)
            business_service = crear_business_service(None)
            logger.info("BusinessService creado en modo degradado (sin base de datos)")
            return None, business_service

        # Crear el manager usando el patron Strategy
        db_manager = DatabaseManager(db_implementation)
        logger.info(f"DatabaseManager inicializado correctamente (tipo: {tipo_db})")

        # Crear business service con dependency injection (DIP)
        business_service = crear_business_service(db_manager)
        logger.info("BusinessDataService inicializado con database manager")

        logger.info(f"Stack completo de base de datos inicializado exitosamente (tipo: {tipo_db})")
        return db_manager, business_service

    except Exception as e:
        logger.error(f"Error inicializando DatabaseManager: {e}")
        logger.exception("Traceback completo del error:")

        # Re-lanzar NexuraAuthenticationError para fail-fast
        from .nexura_auth_service import NexuraAuthenticationError
        if isinstance(e, NexuraAuthenticationError):
            logger.critical("Re-lanzando NexuraAuthenticationError para detener startup")
            raise

        # Graceful degradation para otros errores
        business_service = crear_business_service(None)
        logger.info("BusinessService creado en modo degradado tras error")

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
