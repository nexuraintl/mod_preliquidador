"""
DATABASE SERVICE - BUSINESS DATA MANAGEMENT
==========================================

Servicio dedicado para gestión de datos de negocio siguiendo principios SOLID.

PRINCIPIOS APLICADOS:
- SRP: Responsabilidad única - solo manejo de datos de negocio
- DIP: Depende de abstracción (DatabaseManager) no de implementación concreta
- OCP: Abierto para extensión (nuevas consultas) cerrado para modificación
- LSP: Puede sustituirse por otras implementaciones del servicio
- ISP: Interface específica para datos de negocio

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

# Configuración de logging
logger = logging.getLogger(__name__)


# ===============================
# INTERFACES Y ABSTRACCIONES
# ===============================

class IBusinessDataService(ABC):
    """
    Interface para servicios de datos de negocio.

    ISP: Interface específica para una responsabilidad concreta
    """

    @abstractmethod
    def obtener_datos_negocio(self, codigo_negocio: int) -> Dict[str, Any]:
        """
        Obtiene datos de negocio por código.

        Args:
            codigo_negocio: Código único del negocio

        Returns:
            Dict con estructura estándar de respuesta
        """
        pass


# ===============================
# IMPLEMENTACIÓN CONCRETA
# ===============================

class BusinessDataService(IBusinessDataService):
    """
    Servicio para gestión de datos de negocio.

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Solo maneja obtención y procesamiento de datos de negocio
    - DIP: Depende de DatabaseManager (abstracción) no de implementación específica
    - OCP: Extensible para nuevos tipos de consultas sin modificar código existente
    """

    def __init__(self, database_manager: Optional[Any] = None):
        """
        Inicializa el servicio con inyección de dependencias.

        Args:
            database_manager: Gestor de base de datos (DIP: abstracción inyectada)
        """
        self.database_manager = database_manager
        logger.info("BusinessDataService inicializado siguiendo principios SOLID")

    def obtener_datos_negocio(self, codigo_negocio: int) -> Dict[str, Any]:
        """
        Obtiene datos completos de negocio por código con manejo robusto de errores.

        RESPONSABILIDADES (SRP):
        - Validar disponibilidad de database manager
        - Ejecutar consulta de negocio
        - Procesar respuesta y manejar errores
        - Generar logs consistentes
        - Retornar estructura estándar

        Args:
            codigo_negocio: Código único del negocio a consultar

        Returns:
            Dict con estructura estándar:
            {
                "success": bool,
                "data": Dict[str, Any] | None,
                "message": str,
                "codigo_consultado": int,
                "database_available": bool
            }
        """
        logger.info(f"🔍 Consultando datos de negocio para código: {codigo_negocio}")

        # PASO 1: Validar disponibilidad del database manager
        if not self.database_manager:
            warning_msg = "DatabaseManager no está disponible - continuando sin datos de negocio"
            logger.warning(f"⚠️ {warning_msg}")
            return self._crear_respuesta_sin_database(codigo_negocio, warning_msg)

        # PASO 2: Ejecutar consulta con manejo de errores
        try:
            resultado_consulta = self.database_manager.obtener_negocio_por_codigo(str(codigo_negocio))

            # PASO 3: Procesar respuesta exitosa
            if resultado_consulta.get('success', False):
                datos_negocio = resultado_consulta.get('data')
                if datos_negocio:
                    success_msg = f"Negocio encontrado: {datos_negocio.get('negocio', 'N/A')} - NIT: {datos_negocio.get('nit', 'N/A')} - Fiduciario: {datos_negocio.get('nombre_fiduciario', 'N/A')}"
                    logger.info(f"✅ {success_msg}")

                    return {
                        "success": True,
                        "data": datos_negocio,
                        "message": success_msg,
                        "codigo_consultado": codigo_negocio,
                        "database_available": True
                    }

            # PASO 4: Procesar respuesta sin resultados
            error_msg = resultado_consulta.get('message', f'No se encontró negocio con código: {codigo_negocio}')
            logger.warning(f"⚠️ {error_msg}")

            return {
                "success": False,
                "data": None,
                "message": error_msg,
                "codigo_consultado": codigo_negocio,
                "database_available": True
            }

        except Exception as e:
            # PASO 5: Manejo de errores de base de datos
            error_msg = f"Error consultando base de datos: {str(e)}"
            logger.error(f"❌ {error_msg}")

            return {
                "success": False,
                "data": None,
                "message": error_msg,
                "codigo_consultado": codigo_negocio,
                "database_available": True,
                "error_details": str(e)
            }

    def _crear_respuesta_sin_database(self, codigo_negocio: int, mensaje: str) -> Dict[str, Any]:
        """
        Crea respuesta estándar cuando database no está disponible.

        PRINCIPIO SRP: Método privado con responsabilidad específica

        Args:
            codigo_negocio: Código que se intentó consultar
            mensaje: Mensaje descriptivo del problema

        Returns:
            Dict con estructura estándar para casos sin database
        """
        return {
            "success": False,
            "data": None,
            "message": mensaje,
            "codigo_consultado": codigo_negocio,
            "database_available": False
        }

    def validar_disponibilidad_database(self) -> bool:
        """
        Valida si el database manager está disponible y operativo.

        PRINCIPIO SRP: Responsabilidad específica de validación

        Returns:
            bool: True si database está disponible y operativo
        """
        if not self.database_manager:
            return False

        try:
            # Intentar verificar salud de conexión si está disponible
            if hasattr(self.database_manager, 'verificar_salud_conexion'):
                return self.database_manager.verificar_salud_conexion()
            else:
                # Si no tiene método de health check, asumir disponible
                return True
        except Exception as e:
            logger.error(f"❌ Error verificando disponibilidad de database: {e}")
            return False


# ===============================
# FACTORY PARA CREACIÓN DE SERVICIOS
# ===============================

class BusinessDataServiceFactory:
    """
    Factory para crear instancias de BusinessDataService.

    PRINCIPIOS APLICADOS:
    - Factory Pattern: Centraliza creación de objetos complejos
    - SRP: Solo responsable de crear servicios de datos de negocio
    - DIP: Permite inyección de diferentes database managers
    """

    @staticmethod
    def crear_servicio(database_manager: Optional[Any] = None) -> IBusinessDataService:
        """
        Crea instancia de BusinessDataService con database manager inyectado.

        Args:
            database_manager: Manager de base de datos (opcional)

        Returns:
            IBusinessDataService: Instancia del servicio configurada
        """
        servicio = BusinessDataService(database_manager)
        logger.info("✅ BusinessDataService creado via Factory Pattern")
        return servicio


# ===============================
# FUNCIONES DE CONVENIENCIA
# ===============================

def crear_business_service(database_manager: Optional[Any] = None) -> IBusinessDataService:
    """
    Función de conveniencia para crear BusinessDataService.

    Args:
        database_manager: Manager de base de datos (opcional)

    Returns:
        IBusinessDataService: Servicio listo para usar
    """
    return BusinessDataServiceFactory.crear_servicio(database_manager)


# ===============================
# TESTING Y MOCKING SUPPORT
# ===============================

class MockBusinessDataService(IBusinessDataService):
    """
    Mock implementation para testing.

    PRINCIPIO LSP: Puede sustituir a BusinessDataService en tests
    """

    def __init__(self, mock_data: Dict[int, Dict[str, Any]] = None):
        self.mock_data = mock_data or {}
        logger.info("MockBusinessDataService inicializado para testing")

    def obtener_datos_negocio(self, codigo_negocio: int) -> Dict[str, Any]:
        """Mock implementation que retorna datos predefinidos"""
        if codigo_negocio in self.mock_data:
            return {
                "success": True,
                "data": self.mock_data[codigo_negocio],
                "message": f"Mock data para código {codigo_negocio}",
                "codigo_consultado": codigo_negocio,
                "database_available": True
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": f"Mock: No se encontró código {codigo_negocio}",
                "codigo_consultado": codigo_negocio,
                "database_available": True
            }