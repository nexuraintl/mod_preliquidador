# ---------------------
# Stage 1: Builder
# ---------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias globalmente
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------
# Stage 2: Final image
# ---------------------
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para tiempo de ejecución
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash app

# Copiar dependencias instaladas y código fuente
COPY --from=builder /usr/local /usr/local
COPY --chown=app:app . .

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Cambiar a usuario no-root
USER app

# Cloud Run necesita este puerto
EXPOSE 8080

# Comando de inicio
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]