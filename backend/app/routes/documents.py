"""
Rotas públicas de documentos: download de PDF e imagem do QR Code.
NÃO requerem autenticação — acesso via hash único (token opaco de 64 chars).
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RespostaFormulario, TemplatePDF

router = APIRouter()


@router.get("/qrcode/{token_hash}")
def obter_qrcode(token_hash: str, db: Session = Depends(get_db)):
    """
    Retorna a imagem PNG do QR Code de um documento.
    Acessível publicamente para que o guarda mostre ao cidadão.
    """
    _validar_hash(token_hash)
    resposta = _buscar_resposta(db, token_hash)

    if not resposta.caminho_qrcode or not os.path.exists(resposta.caminho_qrcode):
        raise HTTPException(status_code=404, detail="QR Code não encontrado.")

    return FileResponse(
        resposta.caminho_qrcode,
        media_type="image/png",
        filename=f"qrcode_{token_hash[:8]}.png",
    )


@router.get("/download/{token_hash}")
def download_pdf(token_hash: str, db: Session = Depends(get_db)):
    """
    Permite ao cidadão baixar diretamente o PDF do termo.
    Acesso público via link/QR Code — sem necessidade de login.
    """
    _validar_hash(token_hash)
    resposta = _buscar_resposta(db, token_hash)

    if not resposta.caminho_pdf_final or not os.path.exists(resposta.caminho_pdf_final):
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    nome_arquivo = f"Termo_{resposta.matricula_guarda_autoria}_{resposta.data_criacao.strftime('%Y%m%d_%H%M%S')}.pdf"
    return FileResponse(
        resposta.caminho_pdf_final,
        media_type="application/pdf",
        filename=nome_arquivo,
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/visualizar/{token_hash}", response_class=HTMLResponse)
def visualizar_documento(token_hash: str, db: Session = Depends(get_db)):
    """
    Página HTML pública de visualização do documento.
    Exibida quando o cidadão escaneia o QR Code.
    """
    _validar_hash(token_hash)
    resposta = _buscar_resposta(db, token_hash)

    template = db.query(TemplatePDF).filter(TemplatePDF.id == resposta.template_id).first()
    nome_doc = template.nome_documento if template else "Documento Oficial"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{nome_doc} — Guarda Municipal</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f0f4f8; min-height: 100vh; display: flex;
          flex-direction: column; align-items: center; padding: 24px 16px; }}
  .card {{ background: #fff; border-radius: 16px; padding: 32px 24px;
           max-width: 480px; width: 100%; box-shadow: 0 4px 24px rgba(0,0,0,0.10); }}
  .badge {{ background: #1a3a6b; color: #fff; border-radius: 8px; padding: 6px 16px;
            font-size: 13px; font-weight: 600; display: inline-block; margin-bottom: 16px; }}
  h1 {{ font-size: 20px; color: #1a3a6b; margin-bottom: 8px; }}
  .meta {{ font-size: 14px; color: #555; margin-bottom: 24px; }}
  .info-row {{ display: flex; justify-content: space-between; padding: 10px 0;
               border-bottom: 1px solid #eee; font-size: 15px; }}
  .info-row:last-child {{ border-bottom: none; }}
  .label {{ color: #888; font-size: 13px; }}
  .value {{ color: #1a1a1a; font-weight: 500; }}
  .btn {{ display: block; width: 100%; background: #1a3a6b; color: #fff;
           border: none; border-radius: 12px; padding: 16px; font-size: 16px;
           font-weight: 600; cursor: pointer; text-align: center; text-decoration: none;
           margin-top: 24px; }}
  .btn:hover {{ background: #153060; }}
  .shield {{ font-size: 48px; text-align: center; margin-bottom: 12px; }}
  .hash {{ font-size: 11px; color: #aaa; margin-top: 16px; word-break: break-all; }}
</style>
</head>
<body>
  <div class="card">
    <div class="shield">🛡️</div>
    <div class="badge">DOCUMENTO OFICIAL</div>
    <h1>{nome_doc}</h1>
    <p class="meta">Guarda Municipal — Documento Autenticado Digitalmente</p>
    <div class="info-row">
      <span class="label">Emitido por</span>
      <span class="value">{resposta.nome_guarda_autoria}</span>
    </div>
    <div class="info-row">
      <span class="label">Matrícula</span>
      <span class="value">{resposta.matricula_guarda_autoria}</span>
    </div>
    <div class="info-row">
      <span class="label">Data de Emissão</span>
      <span class="value">{resposta.data_criacao.strftime('%d/%m/%Y %H:%M')}</span>
    </div>
    <div class="info-row">
      <span class="label">Status</span>
      <span class="value" style="color:#16a34a">✓ Documento Válido</span>
    </div>
    <a class="btn" href="/api/documents/download/{token_hash}">
      ⬇ Baixar PDF do Documento
    </a>
    <p class="hash">ID: {token_hash}</p>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _validar_hash(token_hash: str):
    """Valida que o hash tem exatamente 64 caracteres hexadecimais."""
    if len(token_hash) != 64 or not all(c in "0123456789abcdefABCDEF" for c in token_hash):
        raise HTTPException(status_code=400, detail="Identificador de documento inválido.")


def _buscar_resposta(db: Session, token_hash: str) -> RespostaFormulario:
    resposta = db.query(RespostaFormulario).filter(
        RespostaFormulario.token_hash_unico == token_hash.lower()
    ).first()
    if not resposta:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return resposta
