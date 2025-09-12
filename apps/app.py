# app.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Teknovashop Forge")

# ORÍGENES PERMITIDOS
# Pon tu dominio de Vercel aquí; puedes dejar '*' mientras pruebas.
# Ejemplo: "https://teknovashop-isc3yklgh-teknovashop.vercel.app"
ALLOWED = os.getenv("CORS_ALLOW_ORIGINS", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],   # <- Acepta OPTIONS del preflight
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# ... tus imports/funciones de /generate ...
# @app.post("/generate")
# def generate(...):
#     ...
