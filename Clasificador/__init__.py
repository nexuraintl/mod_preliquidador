"""
CLASIFICADOR DE DOCUMENTOS
========================

Módulo para clasificar documentos fiscales usando Google Gemini AI.
Maneja la primera llamada a Gemini para categorizar documentos.
"""

from .clasificador import ProcesadorGemini
from .prompt_clasificador import PROMPT_CLASIFICACION, PROMPT_ANALISIS_FACTURA, PROMPT_ANALISIS_CONSORCIO
from .consorcio_processor import ProcesadorConsorcios

__all__ = [
    'ProcesadorGemini', 
    'PROMPT_CLASIFICACION', 
    'PROMPT_ANALISIS_FACTURA',
    'PROMPT_ANALISIS_CONSORCIO',
    'ProcesadorConsorcios'
]
