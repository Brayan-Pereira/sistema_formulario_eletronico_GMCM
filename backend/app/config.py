import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve raiz do projeto (3 níveis acima de config.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Carrega variáveis do .env automaticamente
load_dotenv(BASE_DIR / ".env")

class Settings:
    # --- Banco de Dados ---
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'storage' / 'guarda_municipal.db'}"

    # --- JWT / Segurança ---
    # OBRIGATÓRIO: altere este valor para uma string aleatória longa em produção
    # Gere com: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "TROQUE_ESTA_CHAVE_ANTES_DE_COLOCAR_EM_PRODUCAO")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))  # 8 horas (turno completo)

    # --- Cloudflare Tunnel ---
    # URL pública gerada pelo Cloudflare Tunnel (ex: https://meu-tunnel.trycloudflare.com)
    CLOUDFLARE_PUBLIC_URL: str = os.getenv("CLOUDFLARE_PUBLIC_URL", "http://localhost:8000")

    # --- Diretórios de Armazenamento Local ---
    STORAGE_DIR: str = str(BASE_DIR / "storage")
    TEMPLATES_DIR: str = str(BASE_DIR / "storage" / "templates")
    GENERATED_DIR: str = str(BASE_DIR / "storage" / "generated")
    QRCODES_DIR: str = str(BASE_DIR / "storage" / "qrcodes")

    # --- Tamanho máximo de upload de PDF (em bytes) ---
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", 20))

    # --- Primeiro Admin (criado no setup) ---
    ADMIN_MATRICULA: str = os.getenv("ADMIN_MATRICULA", "ADMIN001")
    ADMIN_SENHA: str = os.getenv("ADMIN_SENHA", "TroqueEstaSenha@123")

    def __init__(self):
        # Garante que todos os diretórios existam ao inicializar
        for d in [self.STORAGE_DIR, self.TEMPLATES_DIR, self.GENERATED_DIR, self.QRCODES_DIR]:
            os.makedirs(d, exist_ok=True)

settings = Settings()
