# Multi-stage build para optimizar tamaño
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Etapa final
FROM python:3.11-slim

WORKDIR /app

# Copiar dependencias instaladas
COPY --from=builder /root/.local /root/.local

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash app

# Copiar código fuente
COPY --chown=app:app . .

# Variables de entorno para Python
ENV PYTHONPATH=/root/.local/bin:$PYTHONPATH
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Puerto de la aplicación
EXPOSE 8000

# Cambiar a usuario no-root
USER app

# Comando de inicio
CMD ["python", "main.py"]
