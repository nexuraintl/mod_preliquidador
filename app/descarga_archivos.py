"""Descarga de los documentos de una factura desde el gestor de archivos de Nexura.

El cliente no sube los bytes: en el cuerpo de la peticion envia los metadatos de cada
adjunto (`file_uri`, `name`, `mime_type`, `size`) y el servicio descarga el contenido
en memoria, en el mismo formato {filename, content_type, content} que consume el
pipeline de clasificacion.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

from config import CONFIG

logger = logging.getLogger(__name__)

# Servidores que bloquean el User-Agent por defecto de las librerias HTTP.
# Mismo criterio que database/database.py al consultar la API de Nexura.
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

# Proporcion de adjuntos fallidos a partir de la cual se aborta la factura completa.
UMBRAL_ABORTO = 0.5

TIMEOUT_DESCARGA_SEGUNDOS = 60
MAX_REINTENTOS = 3


class ArchivoInvalido(ValueError):
    """El adjunto no se puede descargar: metadatos incompletos o URI no permitida."""


class DescargaAbortada(RuntimeError):
    """Fallo la descarga de una proporcion de adjuntos igual o superior al umbral."""


@dataclass
class ResultadoDescarga:
    """Resultado de descargar los adjuntos de una factura.

    Attributes:
        archivos_data: Archivos descargados, en el formato {filename, content_type,
            content} que espera BackgroundProcessor.
        fallidos: Adjuntos que no se pudieron descargar, con su motivo.
    """

    archivos_data: List[Dict[str, Any]] = field(default_factory=list)
    fallidos: List[Dict[str, str]] = field(default_factory=list)

    @property
    def resumen_fallos(self) -> str:
        """Devuelve los fallos en una linea legible para logs y mensajes al usuario."""
        return '; '.join(f"{f['archivo']}: {f['motivo']}" for f in self.fallidos)


def hosts_permitidos() -> Set[str]:
    """Devuelve los hosts desde los que se acepta descargar adjuntos.

    Se derivan de NEXURA_API_BASE_URL. Restringir el host no es cosmetico: descargar
    URLs arbitrarias enviadas por el cliente seria una via de SSRF contra la red interna.

    Returns:
        Conjunto de hosts permitidos; vacio si la variable de entorno no esta definida.
    """
    host = urlparse(os.getenv('NEXURA_API_BASE_URL', '')).netloc
    return {host} if host else set()


def nombre_seguro(nombre: Optional[str]) -> Optional[str]:
    """Sanea el nombre declarado por el cliente.

    Es un dato critico: todo el ruteo posterior del sistema depende de la extension
    del nombre, no del mime_type.

    Args:
        nombre: Valor del campo `name` del adjunto.

    Returns:
        El nombre sin componentes de ruta, o None si no queda nada utilizable.
    """
    if not nombre or not nombre.strip():
        return None

    # Path(...).name descarta cualquier intento de traversal en el nombre remoto.
    return Path(nombre.strip()).name or None


def validar_adjunto(adjunto: Dict[str, Any]) -> None:
    """Valida los metadatos de un adjunto sin descargarlo.

    Args:
        adjunto: Diccionario con las claves file_uri, name, mime_type y size.

    Raises:
        ArchivoInvalido: Si falta la URI o el nombre, la URI apunta a un host ajeno a
            la API de Nexura o el tamaño declarado supera el maximo permitido.
    """
    uri = (adjunto.get('file_uri') or '').strip()
    if not uri:
        raise ArchivoInvalido('El adjunto no trae "file_uri"')

    partes = urlparse(uri)
    if partes.scheme not in ('http', 'https'):
        raise ArchivoInvalido('El "file_uri" debe empezar por http:// o https://')

    permitidos = hosts_permitidos()
    if partes.netloc not in permitidos:
        origen = ', '.join(sorted(permitidos)) or 'la API de Nexura'
        raise ArchivoInvalido(
            f'Solo se aceptan archivos de {origen}, no de "{partes.netloc}"'
        )

    nombre = nombre_seguro(adjunto.get('name'))
    if not nombre:
        raise ArchivoInvalido(
            f'El adjunto {uri} no trae un "name" utilizable; la extension del nombre '
            'determina como se procesa el documento'
        )

    _validar_tamaño_declarado(nombre, adjunto.get('size'))


def validar_adjuntos(archivos: List[Dict[str, Any]]) -> None:
    """Valida la lista completa de adjuntos sin descargar nada.

    Pensada para ejecutarse en el endpoint, de modo que un payload mal construido
    falle de inmediato en vez de hacerlo mas tarde por webhook.

    Args:
        archivos: Adjuntos enviados por el cliente.

    Raises:
        ArchivoInvalido: Si la lista esta vacia, supera el maximo de archivos o alguno
            de los adjuntos no es descargable.
    """
    if not archivos:
        raise ArchivoInvalido('Debe enviar al menos un archivo')

    maximo = CONFIG['max_archivos']
    if len(archivos) > maximo:
        raise ArchivoInvalido(f'Maximo {maximo} archivos por factura, recibidos {len(archivos)}')

    for adjunto in archivos:
        validar_adjunto(adjunto)


def _validar_tamaño_declarado(nombre: str, size: Any) -> None:
    """Rechaza por tamaño antes de gastar una descarga.

    El campo `size` llega como texto y es informativo: si no es numerico se ignora,
    porque el limite real se aplica igualmente sobre los bytes recibidos.

    Args:
        nombre: Nombre del archivo, para el mensaje de error.
        size: Tamaño declarado en bytes.

    Raises:
        ArchivoInvalido: Si el tamaño declarado supera CONFIG['max_tamaño_mb'].
    """
    try:
        declarado = int(float(size))
    except (TypeError, ValueError):
        return

    if declarado > CONFIG['max_tamaño_mb'] * 1024 * 1024:
        raise ArchivoInvalido(
            f"El archivo '{nombre}' declara {declarado / 1024 / 1024:.2f} MB y supera "
            f"el maximo de {CONFIG['max_tamaño_mb']} MB"
        )


class DescargadorArchivos:
    """Descarga los adjuntos de una factura desde el gestor de archivos de Nexura.

    Los archivos se mantienen en memoria: el pipeline trabaja con bytes, no con rutas.

    Example:
        >>> descargador = DescargadorArchivos(factura_id, token)
        >>> resultado = await descargador.descargar_todos(archivos)
    """

    def __init__(
        self,
        factura_id: int,
        token: Optional[str] = None,
        timeout: int = TIMEOUT_DESCARGA_SEGUNDOS,
    ):
        """Inicializa el descargador.

        Args:
            factura_id: Identificador de la factura, usado para trazar los logs.
            token: Token JWT de Nexura. Se envia como Bearer si esta disponible; el
                endpoint de descarga actual no lo exige, pero si lo exigiera en
                produccion la descarga seguiria funcionando.
            timeout: Timeout en segundos de cada peticion de descarga.
        """
        self.factura_id = factura_id
        self.token = token
        self.timeout = timeout
        self.max_bytes = CONFIG['max_tamaño_mb'] * 1024 * 1024

    async def descargar_todos(self, archivos: List[Dict[str, Any]]) -> ResultadoDescarga:
        """Descarga en paralelo todos los adjuntos y aplica la regla de aborto.

        Args:
            archivos: Adjuntos enviados por el cliente.

        Returns:
            ResultadoDescarga con los archivos obtenidos y los adjuntos fallidos.

        Raises:
            DescargaAbortada: Si falla una proporcion de adjuntos igual o superior a
                UMBRAL_ABORTO. Se aborta porque la ausencia de un documento puede
                alterar la liquidacion sin que nadie lo advierta.
        """
        total = len(archivos)
        logger.info(f"Factura {self.factura_id}: Descargando {total} archivos de Nexura")

        tareas = [self._descargar_uno(adjunto) for adjunto in archivos]
        descargas = await asyncio.gather(*tareas, return_exceptions=True)

        resultado = ResultadoDescarga()
        for adjunto, descarga in zip(archivos, descargas):
            if isinstance(descarga, BaseException):
                motivo = str(descarga) or type(descarga).__name__
                referencia = adjunto.get('name') or adjunto.get('file_uri') or '(sin nombre)'
                logger.warning(f"Factura {self.factura_id}: Fallo {referencia} - {motivo}")
                resultado.fallidos.append({'archivo': referencia, 'motivo': motivo})
            else:
                resultado.archivos_data.append(descarga)

        fallidos = len(resultado.fallidos)
        if total and (fallidos / total) >= UMBRAL_ABORTO:
            raise DescargaAbortada(
                f'No se pudieron descargar {fallidos} de {total} archivos de la API de '
                f'Nexura. {resultado.resumen_fallos}'
            )

        if fallidos:
            logger.warning(
                f"Factura {self.factura_id}: Continuando con {len(resultado.archivos_data)} "
                f"de {total} archivos ({fallidos} fallidos)"
            )

        return resultado

    async def _descargar_uno(self, adjunto: Dict[str, Any]) -> Dict[str, Any]:
        """Descarga un adjunto con reintentos ante fallos transitorios.

        Solo se reintentan timeouts, errores de conexion y respuestas 429 o 5xx.
        Un 404, un archivo sin permisos o una URI mal formada son permanentes:
        reintentarlos solo retrasa el fallo.

        Args:
            adjunto: Diccionario con file_uri, name, mime_type y size.

        Returns:
            Diccionario {filename, content_type, content} listo para el pipeline.

        Raises:
            ArchivoInvalido: Ante cualquier fallo permanente.
        """
        validar_adjunto(adjunto)
        uri = adjunto['file_uri'].strip()
        nombre = nombre_seguro(adjunto.get('name'))
        mime = adjunto.get('mime_type')

        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                return await self._intentar_descarga(uri, nombre, mime)

            except ArchivoInvalido:
                raise  # Permanente: no tiene sentido reintentar.

            except (httpx.TimeoutException, httpx.TransportError) as e:
                if intento == MAX_REINTENTOS:
                    raise ArchivoInvalido(f'No se pudo conectar con la API de Nexura: {e}') from e
                logger.info(
                    f"Factura {self.factura_id}: Reintento {intento}/{MAX_REINTENTOS} "
                    f"de '{nombre}' tras error de red"
                )
                await asyncio.sleep(2 ** intento)

        raise ArchivoInvalido('No se pudo descargar el archivo')  # pragma: no cover

    async def _intentar_descarga(
        self,
        uri: str,
        nombre: str,
        mime: Optional[str],
    ) -> Dict[str, Any]:
        """Ejecuta un intento de descarga por streaming.

        Args:
            uri: URL de descarga enviada por el cliente.
            nombre: Nombre ya saneado del archivo.
            mime: Tipo MIME declarado por el cliente.

        Returns:
            Diccionario {filename, content_type, content}.

        Raises:
            ArchivoInvalido: Fallo permanente (404, sin permisos, HTML de error o
                tamaño excedido).
            httpx.TransportError: Fallo transitorio, gestionado por el llamador.
        """
        headers = {'User-Agent': USER_AGENT}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as cliente:
            async with cliente.stream('GET', uri, headers=headers) as respuesta:
                self._verificar_respuesta(respuesta, nombre)
                contenido = await self._leer_con_limite(respuesta, nombre)

        logger.info(
            f"Factura {self.factura_id}: Descargado '{nombre}' "
            f"({len(contenido) / 1024 / 1024:.2f} MB)"
        )
        return {
            'filename': nombre,
            'content_type': mime or respuesta.headers.get('content-type'),
            'content': contenido,
        }

    def _verificar_respuesta(self, respuesta: httpx.Response, nombre: str) -> None:
        """Comprueba que la respuesta trae un archivo y no una pagina de error.

        Args:
            respuesta: Respuesta en streaming, aun sin consumir.
            nombre: Nombre del archivo, para el mensaje de error.

        Raises:
            ArchivoInvalido: Si el estado es permanente o el cuerpo es HTML.
            httpx.TransportError: Si el estado es transitorio (429 o 5xx).
        """
        codigo = respuesta.status_code

        if codigo in (401, 403):
            raise ArchivoInvalido(
                f"Sin permiso para descargar '{nombre}'. Verifique las credenciales "
                'del servicio contra la API de Nexura'
            )
        if codigo == 404:
            raise ArchivoInvalido(f"El archivo '{nombre}' no existe o fue eliminado")
        if codigo == 429 or codigo >= 500:
            raise httpx.TransportError(f'La API de Nexura respondio {codigo}')
        if codigo != 200:
            raise ArchivoInvalido(f"La API de Nexura respondio {codigo} al descargar '{nombre}'")

        # Nexura devuelve HTML cuando la sesion caduca o el archivo no esta disponible.
        # Ese HTML NUNCA debe llegar a los extractores.
        tipo = (respuesta.headers.get('content-type') or '').lower()
        if 'text/html' in tipo:
            raise ArchivoInvalido(
                f"La API de Nexura devolvio una pagina web en vez del archivo '{nombre}'. "
                'Suele indicar que el archivo ya no esta disponible'
            )

    async def _leer_con_limite(self, respuesta: httpx.Response, nombre: str) -> bytes:
        """Lee el cuerpo cortando la descarga si se supera el tamaño maximo.

        No se confia en Content-Length ni en el `size` declarado: pueden faltar o no
        coincidir con lo que se envia realmente, asi que el limite se aplica sobre los
        bytes recibidos.

        Args:
            respuesta: Respuesta en streaming.
            nombre: Nombre del archivo, para el mensaje de error.

        Returns:
            El contenido completo del archivo.

        Raises:
            ArchivoInvalido: Si se supera CONFIG['max_tamaño_mb'].
        """
        trozos: List[bytes] = []
        acumulado = 0

        async for trozo in respuesta.aiter_bytes():
            acumulado += len(trozo)
            if acumulado > self.max_bytes:
                raise ArchivoInvalido(
                    f"El archivo '{nombre}' supera el maximo de "
                    f"{CONFIG['max_tamaño_mb']} MB"
                )
            trozos.append(trozo)

        return b''.join(trozos)
