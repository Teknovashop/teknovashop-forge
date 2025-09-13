import os
from app import app as fastapi_app
from fastapi.middleware.cors import CORSMiddleware

# Leer orígenes permitidos desde variable (separa por comas)
origins_str = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in origins_str.split(",") if o.strip()]

# Fallback seguro: si no se define nada, intenta el dominio público de Render
render_url = os.getenv("RENDER_EXTERNAL_URL")
if not origins and render_url:
    origins = [render_url]

# Como último recurso (no recomendado en producción), podrías abrir CORS:
# origins = origins or ["*"]

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app = fastapi_app
