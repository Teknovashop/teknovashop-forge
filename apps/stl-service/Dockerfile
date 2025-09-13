FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libx11-6 \
    libxi6 \
    libsm6 \
    libxrandr2 \
    libxcursor1 \
    libxfixes3 \
    libxinerama1 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render te inyecta la variable PORT automáticamente
ENV PORT=10000
EXPOSE 10000

# 👇 Arrancamos con el wrapper ASGI (con soporte CORS)
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "10000"]
