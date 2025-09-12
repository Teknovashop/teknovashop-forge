# apps/app.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Si tu router de generación está en apps/stl-service/routes.py con un APIRouter llamado router:
# from stl-service.routes import router as stl_router
# NOTA: En Python, los guiones no son válidos en import. Si tu carpeta se llama "stl-service",
# asegúrate de que realmente sea "stl_service" en el repo. Si es "stl-service" tendrás que
# renombrarla a "stl_service" para poder importarla:
from stl_service.routes import router as stl_router  # <— ajusta el import a tu estructura real

app = FastAPI(title="Teknovashop Forge API")

# --- CORS ---
# Define la URL de tu frontend en Vercel (o usa la variable en Render)
# Si pones varias, sepáralas por comas: https://foo.vercel.app,https://bar.com
origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],  # limpia espacios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rutas mínimas ---
@app.get("/health")
async def health():
    return {"status": "ok"}

# Monta tus rutas de generación (la de POST /generate, etc.)
app.include_router(stl_router, prefix="")
