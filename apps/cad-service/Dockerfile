FROM python:3.11-slim

# dependencias para cadquery/occt
RUN apt-get update && apt-get install -y git curl build-essential libgl1 libxrender1 libxext6 libsm6 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=10000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
