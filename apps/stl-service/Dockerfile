# Dockerfile (backend)
FROM python:3.11-slim

# Ajustes y banderas útiles en producción
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRIMESH_NO_NETWORK=1

# Paquetes de sistema que evitan errores con numpy/trimesh
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libgl1 libglib2.0-0 libglu1-mesa libgles2-mesa \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r /app/requirements.txt

# Código
COPY . /app

# Puerto por defecto en local; en Render se inyecta $PORT
EXPOSE 10000

# Usa el $PORT de Render si existe; si no, 10000 (útil en local)
CMD ["sh", "-c", "uvicorn asgi:fastapi_app --host 0.0.0.0 --port ${PORT:-10000}"]
