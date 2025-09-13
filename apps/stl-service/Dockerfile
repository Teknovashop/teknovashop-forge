FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
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
ENV PORT=8000
EXPOSE 8000
CMD sh -c "uvicorn asgi:app --host 0.0.0.0 --port ${PORT}"
