"""
Ponto de entrada da aplicação FastAPI.
Inicializa o banco de dados, configura middlewares e monta as rotas.
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .routes import admin, auth, documents, forms

# Cria todas as tabelas ao iniciar (se não existirem)
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Instância principal
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sistema de Formulários Eletrônicos — Guarda Municipal",
    description=(
        "Plataforma de desmaterialização de documentos operacionais. "
        "Backend local com túnel seguro via Cloudflare Tunnels."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS — permite acesso do Cloudflare Tunnel e localhost
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Em produção, substitua pelo domínio do Cloudflare Tunnel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rotas da API
# ---------------------------------------------------------------------------
app.include_router(auth.router,      prefix="/api/auth",      tags=["Autenticação"])
app.include_router(admin.router,     prefix="/api/admin",     tags=["Administração"])
app.include_router(forms.router,     prefix="/api/forms",     tags=["Formulários"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documentos"])

# ---------------------------------------------------------------------------
# Rotas públicas de URL limpa para o QR Code (redireciona para /api/documents/*)
# URL no QR Code: /download/{hash}  →  /api/documents/download/{hash}
# ---------------------------------------------------------------------------
@app.get("/download/{token_hash}", include_in_schema=False)
async def public_download(token_hash: str):
    return RedirectResponse(url=f"/api/documents/download/{token_hash}", status_code=302)

@app.get("/visualizar/{token_hash}", include_in_schema=False)
async def public_visualizar(token_hash: str):
    return RedirectResponse(url=f"/api/documents/visualizar/{token_hash}", status_code=302)

# ---------------------------------------------------------------------------
# Servir Frontend (SPA)
# ---------------------------------------------------------------------------
_FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)
_STATIC_DIR = os.path.join(_FRONTEND_DIR, "static")

if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = os.path.join(_FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"status": "API ativa", "docs": "/api/docs"})


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Redireciona todas as rotas não-API para o index.html (SPA client-side routing)."""
    if full_path.startswith(("api/", "static/")):
        return JSONResponse({"error": "Not found"}, status_code=404)
    index_path = os.path.join(_FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"error": "Frontend não encontrado"}, status_code=404)


# ---------------------------------------------------------------------------
# Handler de erros global
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Em produção nunca exponha detalhes internos para o cliente
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor. Consulte os logs."},
    )
