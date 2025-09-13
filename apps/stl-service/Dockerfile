# apps/stl-service/Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libxrender1 \
    libxext6 \
    libxi6 \
    libxfixes3 \
    libxrandr2 \
    libxcursor1 \
    libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del servicio
COPY . .

# Render inyecta el puerto en $PORT
ENV PORT=8000
EXPOSE 8000

# >>> IMPORTANTE: servir el wrapper ASGI con CORS ya aplicado
CMD sh -c "uvicorn asgi:app --host 0.0.0.0 --port ${PORT}"
