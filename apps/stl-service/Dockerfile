FROM python:3.11-slim

# Dependencias de sistema (ajusta según tu generador STL real)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglu1 \
    libgl1 \
    libxrender1 \
    libxext6 \
    libxi6 \
    libxrandr2 \
    libxcursor1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render proporciona la variable de entorno PORT
ENV PORT=10000
EXPOSE 10000

# IMPORTANTE: ejecutar el wrapper ASGI (no app:app)
CMD ["sh", "-c", "uvicorn asgi:app --host 0.0.0.0 --port ${PORT}"]
