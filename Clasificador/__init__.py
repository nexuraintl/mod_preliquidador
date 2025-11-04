"""
CLASIFICADOR DE DOCUMENTOS
========================

Módulo para clasificar documentos fiscales usando Google Gemini AI.
Maneja la primera llamada a Gemini para categorizar documentos.
"""

from .clasificador import ProcesadorGemini
from prompts.prompt_clasificador import PROMPT_CLASIFICACION
from prompts.prompt_retefuente import PROMPT_ANALISIS_FACTURA


__all__ = [
    'ProcesadorGemini',
    'PROMPT_CLASIFICACION',
    'PROMPT_ANALISIS_FACTURA',
    'ProcesadorConsorcios'
]
