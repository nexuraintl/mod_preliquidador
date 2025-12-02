# consulta_negocio_robusto.py
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from .auth_provider import IAuthProvider

logger = logging.getLogger(__name__)

# ================================
# 🏗️ INTERFACES Y ABSTRACCIONES
# ================================

class DatabaseInterface(ABC):
    """Interface abstracta para operaciones de base de datos"""

    @abstractmethod
    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        """Obtiene un negocio por su código"""
        pass

    @abstractmethod
    def listar_codigos_disponibles(self, limite: int = 10) -> Dict[str, Any]:
        """Lista códigos disponibles para pruebas"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verifica la salud de la conexión"""
        pass

    @abstractmethod
    def obtener_tipo_recurso(self, codigo_negocio: str) -> Dict[str, Any]:
        """Obtiene el tipo de recurso (Públicos/Privados) para un código de negocio"""
        pass

    @abstractmethod
    def obtener_cuantia_contrato(self, id_contrato: str, codigo_negocio: str, nit_proveedor: str) -> Dict[str, Any]:
        """Obtiene la tarifa y tipo de cuantía para un contrato"""
        pass

    @abstractmethod
    def obtener_conceptos_retefuente(self, estructura_contable: int) -> Dict[str, Any]:
        """Obtiene los conceptos de retención en la fuente según estructura contable"""
        pass

    @abstractmethod
    def obtener_concepto_por_index(self, index: int, estructura_contable: int) -> Dict[str, Any]:
        """Obtiene los datos completos de un concepto por su index"""
        pass

    @abstractmethod
    def obtener_conceptos_extranjeros(self) -> Dict[str, Any]:
        """Obtiene los conceptos de retención para pagos al exterior"""
        pass

    @abstractmethod
    def obtener_paises_con_convenio(self) -> Dict[str, Any]:
        """Obtiene la lista de países con convenio de doble tributación"""
        pass

    @abstractmethod
    def obtener_ubicaciones_ica(self) -> Dict[str, Any]:
        """Obtiene todas las ubicaciones ICA disponibles"""
        pass

    @abstractmethod
    def obtener_actividades_ica(self, codigo_ubicacion: int, estructura_contable: int) -> Dict[str, Any]:
        """Obtiene las actividades ICA para una ubicación y estructura contable específica"""
        pass

    @abstractmethod
    def obtener_tarifa_ica(self, codigo_ubicacion: int, codigo_actividad: int, estructura_contable: int) -> Dict[str, Any]:
        """Obtiene la tarifa ICA para una actividad específica en una ubicación"""
        pass


# ================================
#  IMPLEMENTACIÓN SUPABASE
# ================================

class SupabaseDatabase(DatabaseInterface):
    """Implementación concreta para Supabase"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.tabla = 'NEGOCIOS FIDUCIARIA'
        
        # Nombres exactos de las columnas con comillas dobles
        self.columnas = {
            'codigo': '"CODIGO DEL NEGOCIO"',
            'negocio': '"DESCRIPCION DEL NEGOCIO"',  # 
            'nit': '"NIT ASOCIADO"',
            'nombre_fiduciario': '"NOMBRE DEL ASOCIADO"'
        }
        
        # Cache de columnas para SELECT
        self._columnas_select = ", ".join(self.columnas.values())
    
    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        """
        Obtiene un negocio por su código (primary key)
        """
        try:
            response = self.supabase.table(self.tabla).select(
                self._columnas_select
            ).eq(self.columnas['codigo'], codigo).execute()
            
            if response.data and len(response.data) > 0:
                negocio_raw = response.data[0]
                
                # Mapear a nombres más amigables
                negocio_limpio = {
                    'codigo': negocio_raw.get('CODIGO DEL NEGOCIO'),
                    'negocio': negocio_raw.get('DESCRIPCION DEL NEGOCIO'),  
                    'nit': negocio_raw.get('NIT ASOCIADO'),
                    'nombre_fiduciario': negocio_raw.get('NOMBRE DEL ASOCIADO')
                }
                
                return {
                    'success': True,
                    'data': negocio_limpio,
                    'message': f'Negocio {codigo} encontrado exitosamente',
                    'raw_data': negocio_raw  # Para debugging
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe negocio con código: {codigo}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar Supabase: {e}'
            }
    
    def listar_codigos_disponibles(self, limite: int = 10) -> Dict[str, Any]:
        """
        Lista los códigos disponibles para pruebas
        """
        try:
            response = self.supabase.table(self.tabla).select(
                self.columnas['codigo']
            ).limit(limite).execute()
            
            if response.data:
                codigos = [item.get('CODIGO DEL NEGOCIO') for item in response.data]
                return {
                    'success': True,
                    'codigos': codigos,
                    'total': len(codigos),
                    'message': f'{len(codigos)} códigos encontrados'
                }
            else:
                return {
                    'success': False,
                    'codigos': [],
                    'message': 'No se encontraron códigos'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Error al listar códigos: {e}'
            }
    
    def obtener_tipo_recurso(self, codigo_negocio: str) -> Dict[str, Any]:
        """
        Obtiene el tipo de recurso (Públicos/Privados) para un código de negocio.

        SRP: Solo consulta la tabla RECURSOS (Data Access Layer)

        Args:
            codigo_negocio: Código del negocio a consultar

        Returns:
            Dict con estructura estándar de respuesta
        """
        try:
            response = self.supabase.table('RECURSOS').select(
                '"PUBLICO/PRIVADO"'
            ).eq('"CODIGO_NEGOCIO"', codigo_negocio).execute()

            if response.data and len(response.data) > 0:
                tipo_recurso_raw = response.data[0]
                tipo_recurso = tipo_recurso_raw.get('PUBLICO/PRIVADO')

                return {
                    'success': True,
                    'data': {
                        'tipo_recurso': tipo_recurso,
                        'codigo_negocio': codigo_negocio
                    },
                    'message': f'Tipo de recurso encontrado para código {codigo_negocio}',
                    'raw_data': tipo_recurso_raw
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe parametrización de recurso para código: {codigo_negocio}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar tipo de recurso: {e}'
            }

    def obtener_cuantia_contrato(self, id_contrato: str, codigo_negocio: str, nit_proveedor: str) -> Dict[str, Any]:
        """
        Obtiene la tarifa y tipo de cuantía para un contrato de la tabla CUANTIAS.

        SRP: Solo consulta la tabla CUANTIAS (Data Access Layer)

        Args:
            id_contrato: ID del contrato identificado por Gemini
            codigo_negocio: Código del negocio del endpoint
            nit_proveedor: NIT del proveedor del endpoint

        Returns:
            Dict con estructura estándar de respuesta incluyendo tarifa y tipo_cuantia
        """
        try:
            response = self.supabase.table('CUANTIAS').select(
                '"TIPO_CUANTIA", "TARIFA"'
            ).ilike('"ID_CONTRATO"', f'%{id_contrato}%').eq(
                '"CODIGO_NEGOCIO"', codigo_negocio
            ).execute()

            if response.data and len(response.data) > 0:
                cuantia_raw = response.data[0]
                tipo_cuantia = cuantia_raw.get('TIPO_CUANTIA')
                tarifa = cuantia_raw.get('TARIFA', 0.0)

                # Convertir tarifa a float manejando formato con coma decimal (5,0 -> 5.0)
                try:
                    if tarifa is not None:
                        tarifa_str = str(tarifa).replace(',', '.')
                        tarifa = float(tarifa_str)
                    else:
                        tarifa = 0.0
                except (ValueError, TypeError) as e:
                    # Si falla, reportar el error pero usar valor por defecto
                    print(f"[WARNING] Error convirtiendo tarifa: {e}. Raw: tarifa={tarifa}")
                    tarifa = 0.0

                return {
                    'success': True,
                    'data': {
                        'tipo_cuantia': tipo_cuantia,
                        'tarifa': tarifa,
                        'id_contrato': id_contrato,
                        'codigo_negocio': codigo_negocio,
                        'nit_proveedor': nit_proveedor
                    },
                    'message': f'Cuantía encontrada para contrato {id_contrato}',
                    'raw_data': cuantia_raw
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe cuantía para contrato {id_contrato} con código de negocio {codigo_negocio}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar cuantía del contrato: {e}'
            }

    def obtener_conceptos_retefuente(self, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene los conceptos de retención en la fuente según estructura contable.

        SRP: Solo consulta la tabla RETENCION EN LA FUENTE (Data Access Layer)

        Args:
            estructura_contable: Código de estructura contable para filtrar conceptos

        Returns:
            Dict con estructura estándar de respuesta incluyendo lista de conceptos
        """
        try:
            response = self.supabase.table('RETENCION EN LA FUENTE').select(
                'descripcion_concepto, index'
            ).eq('estructura_contable', estructura_contable).execute()

            if response.data and len(response.data) > 0:
                conceptos = []
                for item in response.data:
                    conceptos.append({
                        'descripcion_concepto': item.get('descripcion_concepto'),
                        'index': item.get('index')
                    })

                return {
                    'success': True,
                    'data': conceptos,
                    'total': len(conceptos),
                    'message': f'{len(conceptos)} conceptos encontrados para estructura contable {estructura_contable}'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'message': f'No se encontraron conceptos para estructura contable {estructura_contable}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': [],
                'error': str(e),
                'message': f'Error al consultar conceptos de retefuente: {e}'
            }

    def obtener_concepto_por_index(self, index: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene los datos completos de un concepto específico por su index.

        SRP: Solo consulta la tabla RETENCION EN LA FUENTE (Data Access Layer)

        Args:
            index: Índice del concepto
            estructura_contable: Código de estructura contable

        Returns:
            Dict con estructura estándar de respuesta incluyendo base, porcentaje y descripción
        """
        try:
            response = self.supabase.table('RETENCION EN LA FUENTE').select(
                'descripcion_concepto, base, porcentaje, codigo_concepto'
            ).eq('index', index).eq('estructura_contable', estructura_contable).execute()

            if response.data and len(response.data) > 0:
                concepto_raw = response.data[0]
                base = concepto_raw.get('base', 0.0)
                porcentaje = concepto_raw.get('porcentaje', 0.0)
                codigo_concepto = concepto_raw.get('codigo_concepto', '')

                # Convertir a float manejando formato con coma decimal (3,5 -> 3.5)
                try:
                    # Manejar base
                    if base is not None:
                        base_str = str(base).replace(',', '.')
                        base = float(base_str)
                    else:
                        base = 0.0

                    # Manejar porcentaje (puede venir como string con coma: '3,5')
                    if porcentaje is not None:
                        porcentaje_str = str(porcentaje).replace(',', '.')
                        porcentaje = float(porcentaje_str)
                    else:
                        porcentaje = 0.0
                except (ValueError, TypeError) as e:
                    # Si aún falla, reportar el error pero usar valores por defecto
                    print(f"[WARNING] Error convirtiendo base/porcentaje: {e}. Raw: base={base}, porcentaje={porcentaje}")
                    base = 0.0
                    porcentaje = 0.0

                return {
                    'success': True,
                    'data': {
                        'descripcion_concepto': concepto_raw.get('descripcion_concepto'),
                        'base': base,
                        'porcentaje': porcentaje,
                        'index': index,
                        'estructura_contable': estructura_contable,
                        'codigo_concepto': codigo_concepto
                    },
                    'message': f'Concepto encontrado para index {index}',
                    'raw_data': concepto_raw
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe concepto con index {index} para estructura contable {estructura_contable}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar concepto por index: {e}'
            }

    def obtener_conceptos_extranjeros(self) -> Dict[str, Any]:
        """
        Obtiene todos los conceptos de retención para pagos al exterior.

        SRP: Solo consulta la tabla conceptos_extranjeros (Data Access Layer)

        Returns:
            Dict con estructura estándar de respuesta incluyendo:
            - index: Índice del concepto
            - nombre_concepto: Descripción del concepto
            - base_pesos: Base mínima en pesos
            - tarifa_normal: Tarifa para países sin convenio
            - tarifa_convenio: Tarifa para países con convenio
        """
        try:
            response = self.supabase.table('conceptos_extranjeros').select(
                'index, nombre_concepto, base_pesos, tarifa_normal, tarifa_convenio'
            ).execute()

            if response.data and len(response.data) > 0:
                conceptos = []
                for concepto_raw in response.data:
                    try:
                        # Convertir tarifas a float manejando formato con coma
                        tarifa_normal = concepto_raw.get('tarifa_normal', 0.0)
                        tarifa_convenio = concepto_raw.get('tarifa_convenio', 0.0)
                        base_pesos = concepto_raw.get('base_pesos', 0.0)

                        if tarifa_normal is not None:
                            tarifa_normal = float(str(tarifa_normal).replace(',', '.'))
                        else:
                            tarifa_normal = 0.0

                        if tarifa_convenio is not None:
                            tarifa_convenio = float(str(tarifa_convenio).replace(',', '.'))
                        else:
                            tarifa_convenio = 0.0

                        if base_pesos is not None:
                            base_pesos = float(str(base_pesos).replace(',', '.'))
                        else:
                            base_pesos = 0.0

                        conceptos.append({
                            'index': concepto_raw.get('index'),
                            'nombre_concepto': concepto_raw.get('nombre_concepto'),
                            'base_pesos': base_pesos,
                            'tarifa_normal': tarifa_normal,
                            'tarifa_convenio': tarifa_convenio
                        })
                    except (ValueError, TypeError) as e:
                        print(f"[WARNING] Error convirtiendo datos de concepto extranjero: {e}")
                        continue

                return {
                    'success': True,
                    'data': conceptos,
                    'count': len(conceptos),
                    'message': f'{len(conceptos)} conceptos extranjeros encontrados'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron conceptos extranjeros'
                }

        except Exception as e:
            return {
                'success': False,
                'data': [],
                'error': str(e),
                'message': f'Error al consultar conceptos extranjeros: {e}'
            }

    def obtener_paises_con_convenio(self) -> Dict[str, Any]:
        """
        Obtiene la lista de países con convenio de doble tributación.

        SRP: Solo consulta la tabla paises_convenio_tributacion (Data Access Layer)

        Returns:
            Dict con estructura estándar de respuesta incluyendo:
            - paises: Lista de nombres de países con convenio
        """
        try:
            response = self.supabase.table('paises_convenio_tributacion').select(
                'nombre_pais'
            ).execute()

            if response.data and len(response.data) > 0:
                paises = [row.get('nombre_pais') for row in response.data if row.get('nombre_pais')]

                return {
                    'success': True,
                    'data': paises,
                    'count': len(paises),
                    'message': f'{len(paises)} países con convenio encontrados'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron países con convenio'
                }

        except Exception as e:
            return {
                'success': False,
                'data': [],
                'error': str(e),
                'message': f'Error al consultar países con convenio: {e}'
            }

    def obtener_ubicaciones_ica(self) -> Dict[str, Any]:
        """
        Obtiene todas las ubicaciones ICA disponibles de la tabla UBICACIONES ICA.

        SRP: Solo consulta la tabla UBICACIONES ICA (Data Access Layer)

        Returns:
            Dict con estructura estándar de respuesta incluyendo:
            - codigo_ubicacion: Código de la ubicación
            - nombre_ubicacion: Nombre de la ubicación
        """
        try:
            response = self.supabase.table('UBICACIONES ICA').select(
                '"CODIGO_UBICACION", "NOMBRE_UBICACION"'
            ).execute()

            if response.data and len(response.data) > 0:
                ubicaciones = [
                    {
                        'codigo_ubicacion': row.get('CODIGO_UBICACION'),
                        'nombre_ubicacion': row.get('NOMBRE_UBICACION')
                    }
                    for row in response.data
                ]

                return {
                    'success': True,
                    'data': ubicaciones,
                    'count': len(ubicaciones),
                    'message': f'{len(ubicaciones)} ubicaciones ICA encontradas'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron ubicaciones ICA'
                }

        except Exception as e:
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error al consultar ubicaciones ICA: {e}'
            }

    def obtener_actividades_ica(self, codigo_ubicacion: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene las actividades ICA para una ubicación y estructura contable específica.

        SRP: Solo consulta la tabla ACTIVIDADES IK (Data Access Layer)

        Args:
            codigo_ubicacion: Código de la ubicación (ej: 76001 para Cali)
            estructura_contable: Estructura contable (ej: 18, 17)

        Returns:
            Dict con estructura estándar de respuesta incluyendo lista de actividades
        """
        try:
            response = self.supabase.table('ACTIVIDADES IK').select(
                '"CODIGO_UBICACION", "NOMBRE_UBICACION", "CODIGO_DE_LA_ACTIVIDAD", '
                '"DESCRIPCION_DE_LA_ACTIVIDAD", "PORCENTAJE_ICA", "TIPO_DE_ACTIVIDAD"'
            ).eq('"CODIGO_UBICACION"', codigo_ubicacion).eq(
                '"ESTRUCTURA_CONTABLE"', estructura_contable
            ).execute()

            if response.data and len(response.data) > 0:
                actividades = [
                    {
                        'codigo_ubicacion': row.get('CODIGO_UBICACION'),
                        'nombre_ubicacion': row.get('NOMBRE_UBICACION'),
                        'codigo_actividad': row.get('CODIGO_DE_LA_ACTIVIDAD'),
                        'descripcion_actividad': row.get('DESCRIPCION_DE_LA_ACTIVIDAD'),
                        'porcentaje_ica': row.get('PORCENTAJE_ICA'),
                        'tipo_actividad': row.get('TIPO_DE_ACTIVIDAD')
                    }
                    for row in response.data
                ]

                return {
                    'success': True,
                    'data': actividades,
                    'count': len(actividades),
                    'message': f'{len(actividades)} actividades encontradas para ubicación {codigo_ubicacion}'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'No se encontraron actividades para ubicación {codigo_ubicacion} con estructura {estructura_contable}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error al consultar actividades ICA: {e}'
            }

    def obtener_tarifa_ica(self, codigo_ubicacion: int, codigo_actividad: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene la tarifa ICA para una actividad específica en una ubicación.

        SRP: Solo consulta la tabla ACTIVIDADES IK (Data Access Layer)

        Args:
            codigo_ubicacion: Código de la ubicación
            codigo_actividad: Código de la actividad económica
            estructura_contable: Estructura contable

        Returns:
            Dict con estructura estándar de respuesta incluyendo tarifa y descripción
        """
        try:
            response = self.supabase.table('ACTIVIDADES IK').select(
                '"PORCENTAJE_ICA", "DESCRIPCION_DE_LA_ACTIVIDAD"'
            ).eq('"CODIGO_UBICACION"', codigo_ubicacion).eq(
                '"CODIGO_DE_LA_ACTIVIDAD"', codigo_actividad
            ).eq('"ESTRUCTURA_CONTABLE"', estructura_contable).execute()

            if response.data and len(response.data) > 0:
                tarifa_data = response.data[0]

                return {
                    'success': True,
                    'data': {
                        'porcentaje_ica': tarifa_data.get('PORCENTAJE_ICA'),
                        'descripcion_actividad': tarifa_data.get('DESCRIPCION_DE_LA_ACTIVIDAD')
                    },
                    'message': f'Tarifa ICA encontrada para actividad {codigo_actividad} en ubicación {codigo_ubicacion}'
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No se encontró tarifa ICA para ubicación {codigo_ubicacion}, actividad {codigo_actividad}, estructura {estructura_contable}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar tarifa ICA: {e}'
            }

    def health_check(self) -> bool:
        """
        Verifica si la conexión a Supabase funciona
        """
        try:
            # Hacer una consulta simple para verificar conectividad
            response = self.supabase.table(self.tabla).select('count').limit(1).execute()
            return True
        except Exception as e:
            print(f" Health check fallido: {e}")
            return False


# ================================
# IMPLEMENTACION NEXURA API REST
# ================================

class NexuraAPIDatabase(DatabaseInterface):
    """
    Implementacion concreta para Nexura API REST (OCP + LSP)

    Implementa patron Strategy permitiendo sustituir Supabase
    sin modificar codigo existente. Usa inyeccion de dependencias
    para autenticacion (DIP).

    Principios SOLID aplicados:
    - SRP: Solo maneja comunicacion con API REST de Nexura
    - OCP: Extiende DatabaseInterface sin modificar codigo existente
    - LSP: Puede sustituir a cualquier DatabaseInterface
    - DIP: Depende de IAuthProvider (abstraccion)
    """

    def __init__(self, base_url: str, auth_provider: IAuthProvider, timeout: int = 30):
        """
        Inicializa conexion a Nexura API

        Args:
            base_url: URL base de la API (ej: https://preproduccion-fiducoldex.nexura.com/api)
            auth_provider: Proveedor de autenticacion (DIP)
            timeout: Timeout para requests HTTP en segundos (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.auth_provider = auth_provider
        self.timeout = timeout

        # Configuracion robusta de session HTTP (SRP: metodo dedicado)
        self.session = self._configurar_session_robusta()

        logger.info(f"NexuraAPIDatabase inicializado: {self.base_url}")

        # Validar autenticacion
        if not self.auth_provider.is_authenticated():
            logger.warning("Auth provider no esta autenticado")

    def _configurar_session_robusta(self) -> requests.Session:
        """
        Configura session HTTP con resiliencia y connection pooling (SRP)

        Implementa:
        - Reintentos automaticos con backoff exponencial
        - Connection pooling optimizado
        - Manejo de conexiones cerradas por el servidor
        - Keep-alive configurado

        Returns:
            Session HTTP configurada y optimizada
        """
        session = requests.Session()

        # Estrategia de reintentos con backoff exponencial
        retry_strategy = Retry(
            total=3,  # 3 intentos totales
            backoff_factor=1,  # Espera: 0s, 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],  # Codigos HTTP a reintentar
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]  # Todos los metodos
        )

        # HTTPAdapter con connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Maximo 10 conexiones simultaneas
            pool_maxsize=10,  # Tamaño del pool
            pool_block=False  # No bloquear si el pool esta lleno
        )

        # Montar adapter para HTTP y HTTPS
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Configurar keep-alive
        session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=30, max=100'
        })

        logger.info("Session HTTP configurada con reintentos y connection pooling")

        return session

    def _hacer_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza request HTTP a la API (SRP)

        Metodo privado que centraliza la logica de requests,
        manejo de errores y autenticacion.

        Args:
            endpoint: Endpoint de la API (sin base_url)
            method: Metodo HTTP (GET, POST, etc)
            params: Query parameters
            json_data: Body JSON para POST/PUT

        Returns:
            Dict con respuesta parseada de la API

        Raises:
            requests.exceptions.RequestException: Si falla el request
        """
        url = f"{self.base_url}{endpoint}"

        # Obtener headers con autenticacion
        headers = self.auth_provider.get_headers()

        # Solo agregar Content-Type si hay body (POST/PUT/PATCH)
        if method.upper() in ['POST', 'PUT', 'PATCH'] and json_data:
            headers['Content-Type'] = 'application/json'

        # Agregar User-Agent de navegador (fix para servidores que bloquean python-requests)
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        # Refrescar token si es necesario
        self.auth_provider.refresh_if_needed()

        try:
            logger.debug(f"Request {method} {url} | params={params}")

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=self.timeout
            )

            # Verificar status code
            response.raise_for_status()

            # Parsear JSON
            data = response.json()

            logger.debug(f"Response OK: {response.status_code}")
            return data

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout en request a {url}: {e}")
            raise

        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP {response.status_code} en {url}: {e}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"Error en request a {url}: {e}")
            raise

        except ValueError as e:
            logger.error(f"Error parseando JSON de {url}: {e}")
            raise

    def _mapear_respuesta_negocio(self, data_nexura: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Mapea respuesta de Nexura API a formato interno (SRP)

        Convierte:
        - CODIGO_DEL_NEGOCIO -> codigo
        - DESCRIPCION_DEL_NEGOCIO -> negocio
        - NIT_ASOCIADO -> nit
        - NOMBRE_DEL_ASOCIADO -> nombre_fiduciario

        Args:
            data_nexura: Array de resultados de Nexura API

        Returns:
            Dict con datos mapeados o None si array vacio
        """
        if not data_nexura or len(data_nexura) == 0:
            return None

        negocio_raw = data_nexura[0]

        # Mapear columnas de Nexura (con guion bajo) a formato interno
        negocio_limpio = {
            'codigo': negocio_raw.get('CODIGO_DEL_NEGOCIO'),
            'negocio': negocio_raw.get('DESCRIPCION_DEL_NEGOCIO'),
            'nit': negocio_raw.get('NIT_ASOCIADO'),
            'nombre_fiduciario': negocio_raw.get('NOMBRE_DEL_ASOCIADO')
        }

        return negocio_limpio

    def _mapear_conceptos_retefuente(self, data_nexura: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Mapea array de conceptos de Nexura API a formato interno (SRP)

        Convierte campos de Nexura al formato esperado por el sistema:
        - id -> index (identificador unico del concepto)
        - descripcion_concepto -> descripcion_concepto (sin cambios)

        Args:
            data_nexura: Array de conceptos desde Nexura API

        Returns:
            Lista de conceptos con formato:
            [{'descripcion_concepto': str, 'index': int}, ...]
        """
        if not data_nexura:
            return []

        conceptos_mapeados = []

        for concepto_raw in data_nexura:
            concepto_limpio = {
                'descripcion_concepto': concepto_raw.get('descripcion_concepto'),
                'index': concepto_raw.get('id')
            }
            conceptos_mapeados.append(concepto_limpio)

        return conceptos_mapeados

    def _mapear_concepto_individual(self, data_nexura: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Mapea concepto individual de Nexura API a formato interno (SRP)

        Usado por obtener_concepto_por_index() para retornar datos completos
        de un concepto específico.

        Mapeo crítico:
        - id -> index (CRÍTICO: Nexura usa "id", sistema usa "index")
        - descripcion_concepto -> descripcion_concepto (sin cambios)
        - codigo_concepto -> codigo_concepto (sin cambios)
        - base -> base (conversión a float, manejo de formato con coma)
        - porcentaje -> porcentaje (conversión a float, manejo de formato con coma)

        Args:
            data_nexura: Array de resultados de Nexura API (se espera 1 elemento)

        Returns:
            Dict con datos mapeados o None si array vacío:
            {
                'descripcion_concepto': str,
                'base': float,
                'porcentaje': float,
                'index': int,
                'codigo_concepto': str
            }
        """
        if not data_nexura or len(data_nexura) == 0:
            return None

        concepto_raw = data_nexura[0]

        base = concepto_raw.get('base', 0.0)
        porcentaje = concepto_raw.get('porcentaje', 0.0)

        try:
            if base is not None:
                base_str = str(base).replace(',', '.')
                base = float(base_str)
            else:
                base = 0.0

            if porcentaje is not None:
                porcentaje_str = str(porcentaje).replace(',', '.')
                porcentaje = float(porcentaje_str)
            else:
                porcentaje = 0.0
        except (ValueError, TypeError) as e:
            logger.warning(f"Error convirtiendo base/porcentaje: {e}")
            base = 0.0
            porcentaje = 0.0

        concepto_mapeado = {
            'descripcion_concepto': concepto_raw.get('descripcion_concepto', ''),
            'base': base,
            'porcentaje': porcentaje,
            'index': concepto_raw.get('id'),
            'codigo_concepto': concepto_raw.get('codigo_concepto', '')
        }

        return concepto_mapeado

    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        """
        Obtiene un negocio por su codigo desde Nexura API

        Implementa LSP: Retorna misma estructura que SupabaseDatabase

        Args:
            codigo: Codigo del negocio

        Returns:
            Dict con estructura estandar:
            {
                'success': bool,
                'data': {
                    'codigo': str,
                    'negocio': str,
                    'nit': str,
                    'nombre_fiduciario': str
                } | None,
                'message': str
            }
        """
        try:
            # Request a endpoint de NegociosFiduciaria
            response = self._hacer_request(
                endpoint='/preliquidador/negociosFiduciaria/',
                method='GET',
                params={'codigoNegocio': codigo}
            )

            # Verificar estructura de respuesta de Nexura
            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            # Si error_code es 0, es exitoso (segun ejemplo del usuario)
            if error_code == 0:
                data_array = response.get('data', [])
                negocio_mapeado = self._mapear_respuesta_negocio(data_array)

                if negocio_mapeado:
                    return {
                        'success': True,
                        'data': negocio_mapeado,
                        'message': f'Negocio {codigo} encontrado exitosamente',
                        'raw_data': data_array[0]
                    }
                else:
                    return {
                        'success': False,
                        'data': None,
                        'message': f'No existe negocio con codigo: {codigo}'
                    }
            else:
                # Error en la API
                error_message = error_info.get('message', 'Error desconocido')
                return {
                    'success': False,
                    'data': None,
                    'message': f'Error en API: {error_message}',
                    'error': error_info
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'data': None,
                'error': 'Timeout',
                'message': 'Timeout al consultar Nexura API'
            }

        except requests.exceptions.HTTPError as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error HTTP al consultar Nexura API: {e}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_por_codigo: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar Nexura API: {e}'
            }

    def listar_codigos_disponibles(self, limite: int = 10) -> Dict[str, Any]:
        """
        Lista los codigos disponibles para pruebas

        Nota: Este endpoint aun no esta implementado en Nexura API.
        Retorna respuesta indicando no implementado.

        Args:
            limite: Limite de resultados

        Returns:
            Dict con estructura estandar
        """
        logger.warning("listar_codigos_disponibles no implementado en Nexura API")
        return {
            'success': False,
            'codigos': [],
            'message': 'Endpoint no implementado en Nexura API (pendiente migracion)'
        }

    def obtener_tipo_recurso(self, codigo_negocio: str) -> Dict[str, Any]:
        """
        Obtiene el tipo de recurso (Publicos/Privados) para un codigo de negocio

        Migrado a Nexura API (v3.5.0)

        MAPEO CONFIRMADO con API real:
        - Supabase: campo "PUBLICO/PRIVADO" (con barra /)
        - Nexura: campo "PUBLICO_PRIVADO" (con guion bajo _)
        - Valores: "Públicos", "Privados" (idénticos con tilde)

        Args:
            codigo_negocio: Codigo del negocio a consultar

        Returns:
            Dict con estructura estandar:
            {
                'success': bool,
                'data': {
                    'tipo_recurso': str,  # "Públicos" o "Privados"
                    'codigo_negocio': str
                },
                'message': str,
                'raw_data': dict
            }
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/recursos/',
                method='GET',
                params={'codigoNegocio': codigo_negocio}
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    recurso_raw = data_array[0]
                    tipo_recurso = recurso_raw.get('PUBLICO_PRIVADO')

                    return {
                        'success': True,
                        'data': {
                            'tipo_recurso': tipo_recurso,
                            'codigo_negocio': codigo_negocio
                        },
                        'message': f'Tipo de recurso encontrado para código {codigo_negocio}',
                        'raw_data': recurso_raw
                    }
                else:
                    return {
                        'success': False,
                        'data': None,
                        'message': f'No existe parametrización de recurso para código: {codigo_negocio}'
                    }

            elif error_code == 404:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe parametrización de recurso para código: {codigo_negocio}'
                }

            else:
                error_message = error_info.get('message', 'Error desconocido')
                logger.error(f"Error en obtener_tipo_recurso: {error_message}")
                return {
                    'success': False,
                    'data': None,
                    'message': f'Error API: {error_message}',
                    'error_code': error_code
                }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout en obtener_tipo_recurso para codigo {codigo_negocio}")
            return {
                'success': False,
                'data': None,
                'message': f'Timeout al consultar tipo de recurso para código {codigo_negocio}'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning(f"Codigo de negocio {codigo_negocio} no parametrizado en BD")
                return {
                    'success': False,
                    'data': None,
                    'message': f'El código de negocio {codigo_negocio} no está parametrizado en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_tipo_recurso: {e}")
                return {
                    'success': False,
                    'data': None,
                    'message': f'Error HTTP al consultar tipo de recurso: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_tipo_recurso: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'Error de red al consultar tipo de recurso: {str(e)}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_tipo_recurso: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar tipo de recurso: {e}'
            }

    def obtener_cuantia_contrato(self, id_contrato: str, codigo_negocio: str, nit_proveedor: str) -> Dict[str, Any]:
        """
        Obtiene la tarifa y tipo de cuantia para un contrato de Nexura API

        Migrado a Nexura API (v3.8.0 - Optimizado v3.8.1)

        ESTRATEGIA OPTIMIZADA:
        - Endpoint SOPORTA filtros del lado del servidor con camelCase
        - Parametros: idContrato y codigoNegocio (camelCase obligatorio)
        - Busqueda exacta en ID_CONTRATO (no parcial LIKE)
        - Mucho mas eficiente que filtrado del lado del cliente

        IMPORTANTE: Solo camelCase funciona para filtros del servidor:
        - codigoNegocio -> Filtra
        - codigo_negocio -> NO filtra (retorna todos)
        - CODIGO_NEGOCIO -> NO filtra (retorna todos)

        SRP: Solo consulta endpoint de cuantias (Data Access Layer)

        Args:
            id_contrato: ID del contrato identificado por Gemini (busqueda exacta)
            codigo_negocio: Codigo del negocio del endpoint (busqueda exacta)
            nit_proveedor: NIT del proveedor (no usado en filtrado)

        Returns:
            Dict con estructura estandar:
            {
                'success': bool,
                'data': {
                    'tipo_cuantia': str,
                    'tarifa': float,
                    'id_contrato': str,
                    'codigo_negocio': str,
                    'nit_proveedor': str
                },
                'message': str
            }
        """
        logger.info(f"Consultando cuantias para contrato '{id_contrato}' en negocio {codigo_negocio}")

        try:
            # PASO 1: Consultar con filtros del servidor (camelCase)
            response = self._hacer_request(
                endpoint='/preliquidador/cuantias/',
                method='GET',
                params={
                    'idContrato': id_contrato,
                    'codigoNegocio': codigo_negocio
                }
            )

            # PASO 2: Validar estructura de respuesta
            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code != 0 or 'data' not in response:
                logger.error(f"Error en respuesta de cuantias: {error_info.get('message')}")
                return {
                    'success': False,
                    'data': None,
                    'message': f"Error en API: {error_info.get('message', 'Sin datos')}"
                }

            cuantias = response.get('data', [])
            logger.info(f"Registros filtrados por servidor: {len(cuantias)}")

            # PASO 3: Validar que se encontro exactamente 1 registro
            if not cuantias or len(cuantias) == 0:
                logger.warning(
                    f"No se encontro cuantia para contrato '{id_contrato}' "
                    f"en negocio {codigo_negocio}"
                )
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe cuantia para contrato {id_contrato} con codigo de negocio {codigo_negocio}'
                }

            # Tomar el primer registro (debería ser único por la combinación de filtros)
            cuantia_encontrada = cuantias[0]

            if len(cuantias) > 1:
                logger.warning(
                    f"Se encontraron {len(cuantias)} registros para contrato '{id_contrato}' "
                    f"y negocio {codigo_negocio}. Usando el primero."
                )

            # PASO 4: Extraer y procesar datos
            tipo_cuantia = cuantia_encontrada.get('TIPO_CUANTIA')
            tarifa_raw = cuantia_encontrada.get('TARIFA', '0')

            # Convertir tarifa de string "1%" a float 1.0
            tarifa = 0.0
            try:
                if tarifa_raw:
                    # Remover '%' y espacios, convertir coma a punto
                    tarifa_str = str(tarifa_raw).replace('%', '').replace(',', '.').strip()
                    tarifa = float(tarifa_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Error convirtiendo tarifa '{tarifa_raw}': {e}. Usando 0.0")
                tarifa = 0.0

            logger.info(
                f"Cuantia encontrada - Tipo: {tipo_cuantia}, Tarifa: {tarifa}%, "
                f"ID en BD: {cuantia_encontrada.get('ID_CONTRATO')}"
            )

            # PASO 5: Retornar resultado exitoso
            return {
                'success': True,
                'data': {
                    'tipo_cuantia': tipo_cuantia,
                    'tarifa': tarifa,
                    'id_contrato': id_contrato,
                    'codigo_negocio': codigo_negocio,
                    'nit_proveedor': nit_proveedor
                },
                'message': f'Cuantia encontrada para contrato {id_contrato}',
                'raw_data': cuantia_encontrada
            }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout al consultar cuantias (>{self.timeout}s)")
            return {
                'success': False,
                'data': None,
                'message': f'Timeout al consultar cuantias (>{self.timeout}s)'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning(f"Contrato '{id_contrato}' con codigo negocio {codigo_negocio} no encontrado en BD")
                return {
                    'success': False,
                    'data': None,
                    'message': f'El contrato "{id_contrato}" con código de negocio {codigo_negocio} no está parametrizado en la base de datos'
                }
            else:
                logger.error(f"Error HTTP al consultar cuantias: {e}")
                return {
                    'success': False,
                    'data': None,
                    'message': f'Error HTTP al consultar cuantias: {e}'
                }

        except Exception as e:
            logger.error(f"Error inesperado al consultar cuantias: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar cuantia del contrato: {e}'
            }

    def obtener_conceptos_retefuente(self, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene los conceptos de retencion en la fuente segun estructura contable

        Migrado a Nexura API (v3.3.0)

        Args:
            estructura_contable: Codigo de estructura contable

        Returns:
            Dict con estructura estandar:
            {
                'success': bool,
                'data': [{'descripcion_concepto': str, 'index': int}, ...],
                'total': int,
                'message': str
            }
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/retefuente/',
                method='GET',
                params={'estructuraContable': estructura_contable}
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    conceptos_mapeados = self._mapear_conceptos_retefuente(data_array)

                    return {
                        'success': True,
                        'data': conceptos_mapeados,
                        'total': len(conceptos_mapeados),
                        'message': f'{len(conceptos_mapeados)} conceptos encontrados para estructura contable {estructura_contable}'
                    }
                else:
                    return {
                        'success': False,
                        'data': [],
                        'total': 0,
                        'message': f'No se encontraron conceptos para estructura contable {estructura_contable}'
                    }

            elif error_code == 404:
                return {
                    'success': False,
                    'data': [],
                    'total': 0,
                    'message': f'No se encontraron conceptos para la estructura contable {estructura_contable}'
                }

            else:
                error_message = error_info.get('message', 'Error desconocido')
                logger.error(f"Error en obtener_conceptos_retefuente: {error_message}")
                return {
                    'success': False,
                    'data': [],
                    'total': 0,
                    'message': f'Error API: {error_message}',
                    'error_code': error_code
                }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout en obtener_conceptos_retefuente para estructura {estructura_contable}")
            return {
                'success': False,
                'data': [],
                'total': 0,
                'message': f'Timeout al consultar conceptos para estructura contable {estructura_contable}'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning(f"No se encontraron conceptos retefuente para estructura {estructura_contable}")
                return {
                    'success': False,
                    'data': [],
                    'total': 0,
                    'message': f'No se encontraron conceptos de retención en la fuente para la estructura contable {estructura_contable} en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_conceptos_retefuente: {e}")
                return {
                    'success': False,
                    'data': [],
                    'total': 0,
                    'message': f'Error HTTP al consultar conceptos: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_conceptos_retefuente: {e}")
            return {
                'success': False,
                'data': [],
                'total': 0,
                'message': f'Error de red al consultar conceptos: {str(e)}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_conceptos_retefuente: {e}")
            return {
                'success': False,
                'data': [],
                'total': 0,
                'error': str(e),
                'message': f'Error al consultar conceptos de retefuente: {e}'
            }

    def obtener_concepto_por_index(self, index: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene los datos completos de un concepto por su index

        Migrado a Nexura API (v3.4.0)

        IMPORTANTE - Mapeo de nomenclatura:
        - Sistema interno usa "index" como identificador
        - Nexura API usa "id" como identificador
        - Mapeo bidireccional: index -> id (request), id -> index (response)

        Args:
            index: Indice del concepto (se mapea a "id" en Nexura)
            estructura_contable: Codigo de estructura contable

        Returns:
            Dict con estructura estandar:
            {
                'success': bool,
                'data': {
                    'descripcion_concepto': str,
                    'base': float,
                    'porcentaje': float,
                    'index': int,
                    'estructura_contable': int,
                    'codigo_concepto': str
                },
                'message': str,
                'raw_data': dict
            }
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/retefuente/',
                method='GET',
                params={
                    'id': index,
                    'estructuraContable': estructura_contable
                }
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    concepto_mapeado = self._mapear_concepto_individual(data_array)

                    if concepto_mapeado:
                        concepto_mapeado['estructura_contable'] = estructura_contable

                        return {
                            'success': True,
                            'data': concepto_mapeado,
                            'message': f'Concepto encontrado para index {index}',
                            'raw_data': data_array[0]
                        }

                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe concepto con index {index} para estructura contable {estructura_contable}'
                }

            elif error_code == 404:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No existe concepto con index {index} para estructura contable {estructura_contable}'
                }

            else:
                error_message = error_info.get('message', 'Error desconocido')
                logger.error(f"Error en obtener_concepto_por_index: {error_message}")
                return {
                    'success': False,
                    'data': None,
                    'message': f'Error API: {error_message}',
                    'error_code': error_code
                }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout en obtener_concepto_por_index para index {index}")
            return {
                'success': False,
                'data': None,
                'message': f'Timeout al consultar concepto con index {index}'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning(f"Concepto con index {index} no encontrado para estructura {estructura_contable}")
                return {
                    'success': False,
                    'data': None,
                    'message': f'El concepto con index {index} para la estructura contable {estructura_contable} no está parametrizado en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_concepto_por_index: {e}")
                return {
                    'success': False,
                    'data': None,
                    'message': f'Error HTTP al consultar concepto: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_concepto_por_index: {e}")
            return {
                'success': False,
                'data': None,
                'message': f'Error de red al consultar concepto: {str(e)}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_concepto_por_index: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar concepto por index: {e}'
            }

    def obtener_conceptos_extranjeros(self) -> Dict[str, Any]:
        """
        Obtiene todos los conceptos de retencion para pagos al exterior.

        SRP: Solo consulta endpoint de conceptos extranjeros (Data Access Layer)

        Endpoint Nexura API: GET /preliquidador/conceptosExtranjeros/
        Sin parametros requeridos

        Mapeo de campos:
        - id (Nexura) -> index (interno)
        - nombre_concepto (igual)
        - base_pesos (igual, conversion str -> float)
        - tarifa_normal (igual, conversion str -> float)
        - tarifa_convenio (igual, conversion str -> float)

        Returns:
            Dict con estructura estandar de respuesta incluyendo:
            - index: Indice del concepto
            - nombre_concepto: Descripcion del concepto
            - base_pesos: Base minima en pesos
            - tarifa_normal: Tarifa para paises sin convenio
            - tarifa_convenio: Tarifa para paises con convenio
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/conceptosExtranjeros/',
                method='GET'
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    conceptos = []
                    for concepto_raw in data_array:
                        try:
                            # Convertir tarifas y base a float manejando formato con coma
                            tarifa_normal = concepto_raw.get('tarifa_normal', '0')
                            tarifa_convenio = concepto_raw.get('tarifa_convenio', '0')
                            base_pesos = concepto_raw.get('base_pesos', '0')

                            # Conversion de string a float con manejo de coma decimal
                            if tarifa_normal is not None:
                                tarifa_normal = float(str(tarifa_normal).replace(',', '.'))
                            else:
                                tarifa_normal = 0.0

                            if tarifa_convenio is not None:
                                tarifa_convenio = float(str(tarifa_convenio).replace(',', '.'))
                            else:
                                tarifa_convenio = 0.0

                            if base_pesos is not None:
                                base_pesos = float(str(base_pesos).replace(',', '.'))
                            else:
                                base_pesos = 0.0

                            conceptos.append({
                                'index': concepto_raw.get('id'),  # Mapeo: id -> index
                                'nombre_concepto': concepto_raw.get('nombre_concepto'),
                                'base_pesos': base_pesos,
                                'tarifa_normal': tarifa_normal,
                                'tarifa_convenio': tarifa_convenio
                            })
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error convirtiendo datos de concepto extranjero: {e}")
                            continue

                    return {
                        'success': True,
                        'data': conceptos,
                        'count': len(conceptos),
                        'message': f'{len(conceptos)} conceptos extranjeros encontrados'
                    }
                else:
                    return {
                        'success': False,
                        'data': [],
                        'count': 0,
                        'message': 'No se encontraron conceptos extranjeros'
                    }
            elif error_code == 404:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron conceptos extranjeros en la base de datos'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f"Error de API: {error_info.get('message', 'Error desconocido')}"
                }

        except requests.exceptions.Timeout:
            logger.error("Timeout al consultar conceptos extranjeros")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': 'Timeout',
                'message': 'Timeout al consultar conceptos extranjeros en Nexura API'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning("No se encontraron conceptos extranjeros en BD")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron conceptos de retención para pagos al exterior en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_conceptos_extranjeros: {e}")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'Error HTTP al consultar conceptos extranjeros: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_conceptos_extranjeros: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error de red al consultar conceptos extranjeros: {e}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_conceptos_extranjeros: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error al consultar conceptos extranjeros: {e}'
            }

    def obtener_paises_con_convenio(self) -> Dict[str, Any]:
        """
        Obtiene la lista de paises con convenio de doble tributacion.

        SRP: Solo consulta endpoint de paises con convenio (Data Access Layer)

        Endpoint Nexura API: GET /preliquidador/paisesConvenio/
        Sin parametros requeridos (acepta id opcional para filtrar)

        Mapeo de campos:
        - nombre_pais (igual, retorna lista de strings)

        Returns:
            Dict con estructura estandar de respuesta incluyendo:
            - paises: Lista de nombres de paises con convenio
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/paisesConvenio/',
                method='GET'
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    # Extraer solo los nombres de paises
                    paises = [row.get('nombre_pais') for row in data_array if row.get('nombre_pais')]

                    return {
                        'success': True,
                        'data': paises,
                        'count': len(paises),
                        'message': f'{len(paises)} paises con convenio encontrados'
                    }
                else:
                    return {
                        'success': False,
                        'data': [],
                        'count': 0,
                        'message': 'No se encontraron paises con convenio'
                    }
            elif error_code == 404:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron países con convenio de doble tributación en la base de datos'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f"Error de API: {error_info.get('message', 'Error desconocido')}"
                }

        except requests.exceptions.Timeout:
            logger.error("Timeout al consultar paises con convenio")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': 'Timeout',
                'message': 'Timeout al consultar paises con convenio en Nexura API'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning("No se encontraron países con convenio en BD")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron países con convenio de doble tributación en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_paises_con_convenio: {e}")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'Error HTTP al consultar países con convenio: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_paises_con_convenio: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error de red al consultar paises con convenio: {e}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_paises_con_convenio: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error al consultar paises con convenio: {e}'
            }

    def obtener_ubicaciones_ica(self) -> Dict[str, Any]:
        """
        Obtiene todas las ubicaciones ICA disponibles.

        SRP: Solo consulta endpoint de ubicaciones ICA (Data Access Layer)

        Endpoint Nexura API: GET /preliquidador/ubicacionesIca/
        Sin parametros requeridos

        Returns:
            Dict con estructura estandar de respuesta incluyendo:
            - codigo_ubicacion: Codigo de la ubicacion
            - nombre_ubicacion: Nombre de la ubicacion
            - nombre_departamento: Nombre del departamento
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/ubicacionesIca/',
                method='GET'
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    ubicaciones = [
                        {
                            'codigo_ubicacion': row.get('CODIGO_UBICACION') or row.get('codigo_ubicacion'),
                            'nombre_ubicacion': row.get('NOMBRE_UBICACION') or row.get('nombre_ubicacion'),
                            'nombre_departamento': row.get('NOMBRE_DEPARTAMENTO') or row.get('nombre_departamento', '')
                        }
                        for row in data_array
                    ]

                    return {
                        'success': True,
                        'data': ubicaciones,
                        'count': len(ubicaciones),
                        'message': f'{len(ubicaciones)} ubicaciones ICA encontradas'
                    }
                else:
                    return {
                        'success': False,
                        'data': [],
                        'count': 0,
                        'message': 'No se encontraron ubicaciones ICA'
                    }
            elif error_code == 404:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron ubicaciones ICA en la base de datos'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f"Error de API: {error_info.get('message', 'Error desconocido')}"
                }

        except requests.exceptions.Timeout:
            logger.error("Timeout al consultar ubicaciones ICA")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': 'Timeout',
                'message': 'Timeout al consultar ubicaciones ICA en Nexura API'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning("No se encontraron ubicaciones ICA en BD")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': 'No se encontraron ubicaciones ICA en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_ubicaciones_ica: {e}")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'Error HTTP al consultar ubicaciones ICA: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_ubicaciones_ica: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error de red al consultar ubicaciones ICA: {e}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_ubicaciones_ica: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error al consultar ubicaciones ICA: {e}'
            }

    def obtener_actividades_ica(self, codigo_ubicacion: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene las actividades ICA para una ubicacion y estructura contable especifica.

        SRP: Solo consulta endpoint de actividades ICA (Data Access Layer)

        Endpoint Nexura API: GET /preliquidador/actividadesIca/?codigoUbicacion={codigo}&estructuraContable={estructura}

        Args:
            codigo_ubicacion: Codigo de la ubicacion (ej: 76001 para Cali)
            estructura_contable: Estructura contable (ej: 18, 17)

        Returns:
            Dict con estructura estandar de respuesta incluyendo lista de actividades
        """
        try:
            response = self._hacer_request(
                endpoint='/preliquidador/actividadesIca/',
                method='GET',
                params={
                    'codigoUbicacion': codigo_ubicacion,
                    'estructuraContable': estructura_contable
                }
            )

            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            if error_code == 0:
                data_array = response.get('data', [])

                if data_array and len(data_array) > 0:
                    actividades = [
                        {
                            'codigo_ubicacion': row.get('CODIGO_UBICACION') or row.get('codigo_ubicacion'),
                            'nombre_ubicacion': row.get('NOMBRE_UBICACION') or row.get('nombre_ubicacion'),
                            'codigo_actividad': row.get('CODIGO_DE_LA_ACTIVIDAD') or row.get('codigo_actividad'),
                            'descripcion_actividad': row.get('DESCRIPCION_DE_LA_ACTIVIDAD') or row.get('descripcion_actividad'),
                            'porcentaje_ica': row.get('PORCENTAJE_ICA') or row.get('porcentaje_ica'),
                            'tipo_actividad': row.get('TIPO_DE_ACTIVIDAD') or row.get('tipo_actividad')
                        }
                        for row in data_array
                    ]

                    return {
                        'success': True,
                        'data': actividades,
                        'count': len(actividades),
                        'message': f'{len(actividades)} actividades encontradas para ubicacion {codigo_ubicacion}'
                    }
                else:
                    return {
                        'success': False,
                        'data': [],
                        'count': 0,
                        'message': f'No se encontraron actividades para ubicacion {codigo_ubicacion} con estructura {estructura_contable}'
                    }
            elif error_code == 404:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'No se encontraron actividades ICA para la ubicación {codigo_ubicacion} con estructura contable {estructura_contable} en la base de datos'
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f"Error de API: {error_info.get('message', 'Error desconocido')}"
                }

        except requests.exceptions.Timeout:
            logger.error("Timeout al consultar actividades ICA")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': 'Timeout',
                'message': 'Timeout al consultar actividades ICA en Nexura API'
            }

        except requests.exceptions.HTTPError as e:
            # Manejo específico para errores HTTP
            if '404' in str(e):
                logger.warning(f"No se encontraron actividades ICA para ubicación {codigo_ubicacion} con estructura {estructura_contable}")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'No se encontraron actividades ICA para la ubicación {codigo_ubicacion} con estructura contable {estructura_contable} en la base de datos'
                }
            else:
                logger.error(f"Error HTTP en obtener_actividades_ica: {e}")
                return {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'message': f'Error HTTP al consultar actividades ICA: {str(e)}'
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en obtener_actividades_ica: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error de red al consultar actividades ICA: {e}'
            }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_actividades_ica: {e}")
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': str(e),
                'message': f'Error al consultar actividades ICA: {e}'
            }

    def obtener_tarifa_ica(self, codigo_ubicacion: int, codigo_actividad: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene la tarifa ICA para una actividad especifica en una ubicacion.

        SRP: Solo consulta endpoint de actividades ICA (Data Access Layer)

        Este metodo obtiene todas las actividades para la ubicacion y estructura,
        luego filtra por el codigo de actividad especifico.

        Args:
            codigo_ubicacion: Codigo de la ubicacion
            codigo_actividad: Codigo de la actividad economica
            estructura_contable: Estructura contable

        Returns:
            Dict con estructura estandar de respuesta incluyendo tarifa y descripcion
        """
        try:
            # Obtener todas las actividades para esta ubicacion y estructura
            actividades_resultado = self.obtener_actividades_ica(codigo_ubicacion, estructura_contable)

            if not actividades_resultado['success']:
                return {
                    'success': False,
                    'data': None,
                    'message': actividades_resultado['message']
                }

            # Filtrar por codigo de actividad especifico
            actividades = actividades_resultado['data']
            actividad_encontrada = next(
                (act for act in actividades if act['codigo_actividad'] == codigo_actividad),
                None
            )

            if actividad_encontrada:
                return {
                    'success': True,
                    'data': {
                        'porcentaje_ica': actividad_encontrada['porcentaje_ica'],
                        'descripcion_actividad': actividad_encontrada['descripcion_actividad']
                    },
                    'message': f'Tarifa ICA encontrada para actividad {codigo_actividad} en ubicacion {codigo_ubicacion}'
                }
            else:
                return {
                    'success': False,
                    'data': None,
                    'message': f'No se encontro tarifa ICA para ubicacion {codigo_ubicacion}, actividad {codigo_actividad}, estructura {estructura_contable}'
                }

        except Exception as e:
            logger.error(f"Error inesperado en obtener_tarifa_ica: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar tarifa ICA: {e}'
            }

    def health_check(self) -> bool:
        """
        Verifica si la conexion a Nexura API funciona

        Intenta hacer un request simple al endpoint de negocios
        para verificar conectividad y autenticacion.

        Returns:
            True si la API responde correctamente, False en caso contrario
        """
        try:
            # Intentar request con codigo de prueba conocido (codigo 3 existe)
            response = self._hacer_request(
                endpoint='/preliquidador/negociosFiduciaria/',
                method='GET',
                params={'codigoNegocio': '3'}
            )

            # Verificar que responde correctamente
            error_info = response.get('error', {})
            error_code = error_info.get('code', -1)

            # Si retorna estructura correcta con error_code 0, la API esta funcionando
            return error_code == 0 and 'data' in response

        except requests.exceptions.HTTPError as e:
            # 404 significa que el endpoint existe pero el registro no (API funciona)
            if '404' in str(e):
                logger.info("Health check: API responde (404 es esperado para codigo inexistente)")
                return True
            logger.error(f"Health check fallido: {e}")
            return False

        except Exception as e:
            logger.error(f"Health check fallido: {e}")
            return False

    def close(self):
        """
        Cierra la session HTTP

        Buena practica para liberar recursos de conexion.
        Llamar al finalizar uso de la instancia.
        """
        if self.session:
            self.session.close()
            logger.info("Session HTTP cerrada")


# ================================
# MANAGER PRINCIPAL
# ================================

class DatabaseManager:
    """
    Manager principal que usa el patrón Strategy para manejar diferentes tipos de BD
    """
    
    def __init__(self, db_connection: DatabaseInterface) -> None:
        self.db_connection = db_connection
        
        # Verificar conexión al inicializar
        if not self.db_connection.health_check():
            raise ConnectionError("🚨 No se pudo establecer conexión con la base de datos")
        
        print(" DatabaseManager inicializado correctamente")
    
    def obtener_negocio_por_codigo(self, codigo: str) -> Dict[str, Any]:
        """
        Obtiene un negocio por su código usando la implementación configurada
        """
        return self.db_connection.obtener_por_codigo(codigo)
    
    def listar_codigos_disponibles(self, limite: int = 10) -> Dict[str, Any]:
        """
        Lista códigos disponibles usando la implementación configurada
        """
        return self.db_connection.listar_codigos_disponibles(limite)
    
    def verificar_salud_conexion(self) -> bool:
        """
        Verifica el estado de la conexión
        """
        return self.db_connection.health_check()

    def obtener_tipo_recurso_negocio(self, codigo_negocio: str) -> Dict[str, Any]:
        """
        Obtiene el tipo de recurso para un código de negocio.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Args:
            codigo_negocio: Código del negocio

        Returns:
            Dict con resultado de la consulta
        """
        return self.db_connection.obtener_tipo_recurso(codigo_negocio)

    def obtener_cuantia_contrato(self, id_contrato: str, codigo_negocio: str, nit_proveedor: str) -> Dict[str, Any]:
        """
        Obtiene la tarifa y tipo de cuantía para un contrato.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Args:
            id_contrato: ID del contrato identificado por Gemini
            codigo_negocio: Código del negocio del endpoint
            nit_proveedor: NIT del proveedor del endpoint

        Returns:
            Dict con resultado de la consulta incluyendo tarifa y tipo_cuantia
        """
        return self.db_connection.obtener_cuantia_contrato(id_contrato, codigo_negocio, nit_proveedor)

    def obtener_conceptos_retefuente(self, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene los conceptos de retención en la fuente según estructura contable.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Args:
            estructura_contable: Código de estructura contable

        Returns:
            Dict con resultado de la consulta incluyendo lista de conceptos
        """
        return self.db_connection.obtener_conceptos_retefuente(estructura_contable)

    def obtener_concepto_por_index(self, index: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene los datos completos de un concepto por su index.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Args:
            index: Índice del concepto
            estructura_contable: Código de estructura contable

        Returns:
            Dict con resultado de la consulta incluyendo base, porcentaje y descripción
        """
        return self.db_connection.obtener_concepto_por_index(index, estructura_contable)

    def obtener_conceptos_extranjeros(self) -> Dict[str, Any]:
        """
        Obtiene los conceptos de retención para pagos al exterior.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Returns:
            Dict con resultado de la consulta incluyendo:
            - index, nombre_concepto, base_pesos, tarifa_normal, tarifa_convenio
        """
        return self.db_connection.obtener_conceptos_extranjeros()

    def obtener_paises_con_convenio(self) -> Dict[str, Any]:
        """
        Obtiene la lista de países con convenio de doble tributación.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Returns:
            Dict con resultado de la consulta incluyendo lista de nombres de países
        """
        return self.db_connection.obtener_paises_con_convenio()

    def obtener_ubicaciones_ica(self) -> Dict[str, Any]:
        """
        Obtiene todas las ubicaciones ICA disponibles.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Returns:
            Dict con resultado de la consulta incluyendo:
            - success: bool
            - message: str
            - count: int
            - data: List[Dict] con codigo_ubicacion y nombre_ubicacion
        """
        return self.db_connection.obtener_ubicaciones_ica()

    def obtener_actividades_ica(self, codigo_ubicacion: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene las actividades ICA para una ubicación y estructura contable específica.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Args:
            codigo_ubicacion: Código de ubicación (ej: 76001 para Cali)
            estructura_contable: Código de estructura contable

        Returns:
            Dict con resultado de la consulta incluyendo:
            - success: bool
            - message: str
            - count: int
            - data: List[Dict] con todas las actividades ICA
        """
        return self.db_connection.obtener_actividades_ica(codigo_ubicacion, estructura_contable)

    def obtener_tarifa_ica(self, codigo_ubicacion: int, codigo_actividad: int, estructura_contable: int) -> Dict[str, Any]:
        """
        Obtiene la tarifa ICA para una actividad específica en una ubicación.

        SRP: Delega a la implementación configurada (Strategy Pattern)

        Args:
            codigo_ubicacion: Código de ubicación
            codigo_actividad: Código de actividad
            estructura_contable: Código de estructura contable

        Returns:
            Dict con resultado de la consulta incluyendo:
            - success: bool
            - message: str
            - data: Dict con porcentaje_ica y descripcion_actividad
        """
        return self.db_connection.obtener_tarifa_ica(codigo_ubicacion, codigo_actividad, estructura_contable)


def ejecutar_pruebas_completas(db_manager: DatabaseManager):
    """
    Ejecuta un conjunto completo de pruebas
    """
    print(" EJECUTANDO PRUEBAS COMPLETAS")
    print("=" * 60)
    
    # 1. Verificar salud de conexión
    print("1️ Verificando salud de conexión...")
    if db_manager.verificar_salud_conexion():
        print("    Conexión saludable")
    else:
        print("   Problema de conexión")
        return
    
    # 2. Listar códigos disponibles
    print("\n2️ Listando códigos disponibles...")
    codigos_result = db_manager.listar_codigos_disponibles(limite=5)
    
    if codigos_result['success']:
        print(f"    {codigos_result['total']} códigos encontrados:")
        for i, codigo in enumerate(codigos_result['codigos'], 1):
            print(f"      {i}. {codigo}")
        
        # 3. Probar con primer código disponible
        if codigos_result['codigos']:
            codigo_prueba = str(codigos_result['codigos'][0])
            print(f"\n3️ Probando con primer código disponible: '{codigo_prueba}'")
            
            resultado = db_manager.obtener_negocio_por_codigo(codigo_prueba)
            
            if resultado['success']:
                data = resultado['data']
                print("    RESULTADO EXITOSO:")
                print(f"       Código: {data['codigo']}")
                print(f"       Descripción: {data['negocio']}")
                print(f"       NIT: {data['nit']}")
                print(f"       Nombre: {data['nombre_fiduciario']}")
            else:
                print(f"   ❌ Error: {resultado['message']}")
    else:
        print(f"   ❌ No se pudieron listar códigos: {codigos_result['message']}")
    
    # 4. Probar con código específico conocido
    print("\n Probando con código específico:")
    resultado_especifico = db_manager.obtener_negocio_por_codigo("44658")
    
    if resultado_especifico['success']:
        print("   ✅ Código '44658' encontrado!")
        data = resultado_especifico['data']
        print(f"      📊 Datos: {data}")
        
        # Para integración con preliquidador
        print(f"\n🔧 DATOS PARA PRELIQUIDADOR:")
        print(f"   NIT a procesar: {data['nit']}")
        print(f"   Entidad: {data['nombre_fiduciario']}")
        
    else:
        print(f"   ❌ Código '44658': {resultado_especifico['message']}")

def main():
    """
    Función principal de prueba
    """
    print("🚀 INICIANDO SISTEMA DE CONSULTA DE NEGOCIOS")
    print("=" * 60)
    
    try:
        # Configuración (en producción usar variables de entorno)
        SUPABASE_URL = "https://gfcseujjfnaoicdenymt.supabase.co"
        SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmY3NldWpqZm5hb2ljZGVueW10Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEwMzA4MDgsImV4cCI6MjA2NjYwNjgwOH0.ghHQ-wDB7itkoEEKq04iOCmLUyrL1hLSjLXhq1gN62k"
        
        #  Crear la implementación concreta
        supabase_db = SupabaseDatabase(SUPABASE_URL, SUPABASE_KEY)
        
        #  Crear el manager usando el patrón Strategy
        db_manager = DatabaseManager(supabase_db)
        
        # Ejecutar pruebas
        ejecutar_pruebas_completas(db_manager)
        
    except ConnectionError as e:
        print(f" Error de conexión: {e}")
    except Exception as e:
        print(f" Error inesperado: {e}")
    finally:
        print("\n Pruebas completadas")

if __name__ == "__main__":
    main()
