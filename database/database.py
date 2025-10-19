# consulta_negocio_robusto.py
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from supabase import create_client, Client
import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

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
    def obtener_cuantia_contrato(self, id_contrato: str, codigo_negocio: str, nit_proveedor: str) -> Dict[str, Any]:
        """Obtiene la tarifa y tipo de cuantía para un contrato"""
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
            ).ilike('"NIT_PROVEEDOR"', f'%{nit_proveedor}%').execute()

            if response.data and len(response.data) > 0:
                cuantia_raw = response.data[0]
                tipo_cuantia = cuantia_raw.get('TIPO_CUANTIA')
                tarifa = cuantia_raw.get('TARIFA', 0.0)

                # Convertir tarifa a float si es necesario
                try:
                    tarifa = float(tarifa) if tarifa is not None else 0.0
                except (ValueError, TypeError):
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
                    'message': f'No existe cuantía para contrato {id_contrato} con código {codigo_negocio} y NIT {nit_proveedor}'
                }

        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'message': f'Error al consultar cuantía del contrato: {e}'
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
