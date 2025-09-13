from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
from supabase import create_client, Client

# Inicializar FastAPI
app = FastAPI()

# Configurar CORS dinámicamente
origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(request: Request):
    """
    Genera un STL (dummy ahora) y lo sube a Supabase.
    """
    data = await request.json()

    # Crear contenido de ejemplo STL
    fake_stl = """
solid cube
  facet normal 0 0 0
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid cube
""".encode("utf-8")

    # Nombre único
    filename = f"{uuid.uuid4()}.stl"

    # Subir a Supabase
    res = supabase.storage.from_(SUPABASE_BUCKET).upload(filename, fake_stl)

    if res.get("error"):
        return {"status": "error", "message": res["error"]["message"]}

    # URL pública
    url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)

    return {"status": "ok", "stl_url": url}
