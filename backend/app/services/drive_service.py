"""
Serviço de integração com Google Drive.

Fluxo:
  1. Autentica via OAuth 2.0 com token pessoal (conta Gmail).
     Execute scripts/autorizar_gdrive.py UMA VEZ para gerar secrets/gdrive_token.json.
  2. Faz upload do PDF para uma pasta dedicada no Drive.
  3. Cria link público de compartilhamento (role=reader, type=anyone).
  4. Agenda deleção automática do arquivo após GDRIVE_DELETE_AFTER_SECONDS.

Configuração necessária no .env:
  GDRIVE_ENABLED=true
  GDRIVE_TOKEN_FILE=./secrets/gdrive_token.json
  GDRIVE_OAUTH_CLIENT_FILE=./secrets/gdrive_oauth_client.json
  GDRIVE_FOLDER_ID=<ID da pasta no Drive>
  GDRIVE_DELETE_AFTER_SECONDS=120
"""
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Importações opcionais (graceful degradation se não instalado)
# ---------------------------------------------------------------------------
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False
    logger.warning("google-api-python-client não instalado. Drive desativado.")


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


# ---------------------------------------------------------------------------
# Leitura lazy das configurações (sempre lê do os.environ, após load_dotenv)
# ---------------------------------------------------------------------------
def _cfg():
    return {
        "enabled":      os.getenv("GDRIVE_ENABLED", "false").lower() == "true",
        "token_file":   os.getenv("GDRIVE_TOKEN_FILE",  "./secrets/gdrive_token.json"),
        "folder_id":    os.getenv("GDRIVE_FOLDER_ID",   ""),
        "delete_after": int(os.getenv("GDRIVE_DELETE_AFTER_SECONDS", "120")),
    }


# ---------------------------------------------------------------------------
# Autenticação OAuth 2.0 (token pessoal)
# ---------------------------------------------------------------------------

def _build_service():
    """
    Constrói o cliente autenticado da Drive API v3 usando OAuth 2.0.
    Renova o token automaticamente se expirado.
    """
    if not _HAS_GOOGLE:
        raise RuntimeError("Instale: pip install google-api-python-client google-auth google-auth-oauthlib")

    token_path = os.path.abspath(_cfg()["token_file"])
    if not os.path.exists(token_path):
        raise FileNotFoundError(
            f"Token OAuth não encontrado: {token_path}\n"
            "Execute primeiro: python scripts/autorizar_gdrive.py"
        )

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Renova automaticamente se expirado
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Salva o token renovado
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            logger.info("Token OAuth renovado automaticamente.")
        else:
            raise RuntimeError(
                "Token OAuth inválido ou sem refresh_token.\n"
                "Execute novamente: python scripts/autorizar_gdrive.py"
            )

    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# Operações principais
# ---------------------------------------------------------------------------

def upload_pdf(caminho_local: str, nome_arquivo: str) -> dict:
    """
    Envia o PDF para o Google Drive na pasta GDRIVE_FOLDER_ID.
    Retorna { 'file_id': str, 'web_view_link': str }
    """
    service = _build_service()

    folder_id = _cfg()["folder_id"]
    metadata = {
        "name": nome_arquivo,
        "parents": [folder_id] if folder_id else [],
    }

    media = MediaFileUpload(caminho_local, mimetype="application/pdf", resumable=False)

    arquivo = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )

    logger.info("PDF enviado ao Drive: %s (id=%s)", nome_arquivo, arquivo.get("id"))
    return {"file_id": arquivo["id"], "web_view_link": arquivo.get("webViewLink", "")}


def create_share_link(file_id: str) -> str:
    """
    Torna o arquivo acessível a qualquer pessoa com o link (role=reader).
    Retorna a URL de compartilhamento direta para download.
    """
    service = _build_service()

    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()

    # URL de download direto (não exige conta Google)
    share_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.info("Link público criado para file_id=%s", file_id)
    return share_url


def delete_file(file_id: str) -> bool:
    """
    Deleta o arquivo do Drive por file_id.
    Retorna True se deletado, False se já não existia (404).
    Não propaga outros erros — registra no log.
    """
    try:
        service = _build_service()
        service.files().delete(fileId=file_id).execute()
        logger.info("Arquivo deletado do Drive: file_id=%s", file_id)
        return True
    except Exception as e:
        # 404 = já foi deletado manualmente
        if "404" in str(e) or "notFound" in str(e).lower():
            logger.warning("Arquivo já não existe no Drive: file_id=%s", file_id)
            return False
        logger.error("Erro ao deletar arquivo do Drive file_id=%s: %s", file_id, e)
        return False


# ---------------------------------------------------------------------------
# Deleção automática com timer (thread simples, sem APScheduler)
# ---------------------------------------------------------------------------

def _deletar_apos_delay(file_id: str, delay_segundos: int):
    """Thread que espera `delay_segundos` e então deleta o arquivo."""
    timer = threading.Timer(delay_segundos, delete_file, args=[file_id])
    timer.daemon = True   # Não bloqueia o shutdown do servidor
    timer.start()
    logger.info(
        "Deleção agendada: file_id=%s em %ds (%s)",
        file_id,
        delay_segundos,
        (datetime.now(timezone.utc) + timedelta(seconds=delay_segundos)).isoformat(),
    )


# ---------------------------------------------------------------------------
# Função principal — chamada pelo endpoint de submissão
# ---------------------------------------------------------------------------

def upload_e_agendar_delecao(caminho_pdf: str, nome_arquivo: str) -> Optional[str]:
    """
    Orquestra o fluxo completo:
      1. Upload do PDF
      2. Criação do link público
      3. Agendamento de deleção automática

    Retorna a share_url para uso no QR Code.
    Retorna None se GDRIVE_ENABLED=false ou em caso de erro.
    """
    cfg = _cfg()
    if not cfg["enabled"]:
        logger.info("Google Drive desativado (GDRIVE_ENABLED=false). Usando URL local.")
        return None

    if not cfg["folder_id"]:
        logger.warning("GDRIVE_FOLDER_ID não configurado. Drive ignorado.")
        return None

    try:
        # 1. Upload
        resultado = upload_pdf(caminho_pdf, nome_arquivo)
        file_id = resultado["file_id"]

        # 2. Link público
        share_url = create_share_link(file_id)

        # 3. Agendar deleção
        _deletar_apos_delay(file_id, cfg["delete_after"])

        return share_url

    except FileNotFoundError as e:
        logger.error("Credenciais não encontradas: %s", e)
        return None
    except Exception as e:
        logger.error("Falha no upload para o Drive: %s", e)
        return None
