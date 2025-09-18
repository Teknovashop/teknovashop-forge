# Dockerfile (backend Render)
FROM python:3.11-slim

# Producción: no caches, logs sin buffer y sin red desde trimesh
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRIMESH_NO_NETWORK=1

# Paquetes de sistema (válidos en Debian Trixie)
# NOTA: quitamos 'libgles2-mesa' (no existe). Si alguna lib GL faltara,
# se puede añadir 'libgles2' en su lugar, pero para este backend no es necesaria.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libgl1 libglib2.0-0 libglu1-mesa \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r /app/requirements.txt

# Código
COPY . /app

# Puerto (Render inyecta $PORT en runtime)
EXPOSE 10000

# Arranque: usa $PORT si está, si no 10000 (útil en local)
CMD ["sh", "-c", "uvicorn asgi:fastapi_app --host 0.0.0.0 --port ${PORT:-10000}"]
