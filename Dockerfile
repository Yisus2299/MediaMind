# ============================================
# STAGE 1: Builder - Instala dependencias
# ============================================
FROM python:3.12-slim AS builder

# Instalar dependencias de compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    gfortran \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario appuser en el builder también
RUN useradd -m -u 1000 appuser

# Cambiar a appuser para instalar dependencias como él
USER appuser
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias como appuser en su home
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# ============================================
# STAGE 2: Final - Imagen ligera
# ============================================
FROM python:3.12-slim

# Instalar solo dependencias de runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root (mismo UID que en builder)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copiar las dependencias desde el home de appuser
COPY --from=builder --chown=appuser:appuser /home/appuser/.local /home/appuser/.local

# Establecer variables de entorno
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH

# Copiar el código
COPY --chown=appuser:appuser . .

# Cambiar a usuario no-root
USER appuser

# Exponer puerto
EXPOSE 8000

# Comando por defecto
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]