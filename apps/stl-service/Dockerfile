FROM python:3.11-slim

# Paquetes de sistema mínimos para numpy/trimesh (sin libgles2-mesa que falla)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libgl1 libglib2.0-0 libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./ 
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
EXPOSE 10000

# Arranque
CMD ["sh","-c","uvicorn asgi:app --host 0.0.0.0 --port ${PORT}"]
