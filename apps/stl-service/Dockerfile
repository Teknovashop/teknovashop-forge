# teknovashop-forge/Dockerfile
FROM python:3.11-slim

# Paquetes de sistema (OpenGL “headless” válido para trimesh)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libgl1 libglib2.0-0 libglu1-mesa libopengl0 \
 && rm -rf /var/lib/apt/lists/*

# Ajustes de Python para contenedor
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias primero para aprovechar cache cuando sea posible
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

ENV PORT=10000
EXPOSE 10000

# uvicorn entra por asgi:app (alias a fastapi_app)
CMD ["sh", "-c", "uvicorn asgi:app --host 0.0.0.0 --port ${PORT}"]
