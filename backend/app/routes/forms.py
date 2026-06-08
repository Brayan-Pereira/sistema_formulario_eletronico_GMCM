"""
Rotas de formulários: listagem de templates, preenchimento e emissão de documentos.
"""
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_usuario_ativo
from ..database import get_db
from ..models import CampoDinamico, RespostaFormulario, TemplatePDF, Usuario
from ..schemas import (
    ContratoTemplateMobile, ContratoCampoMobile,
    FormularioResponse, FormularioSubmit,
)
from ..services.audit import registrar_log
from ..services.pdf_generator import gerar_pdf_preenchido
from ..services.qr_generator import gerar_qrcode
from ..services.drive_service import upload_e_agendar_delecao
from ..config import settings
import os
import secrets

router = APIRouter()


# ===========================================================================
# TEMPLATES DISPONÍVEIS (para o guarda na rua)
# ===========================================================================

@router.get("/templates", response_model=List[ContratoTemplateMobile])
def listar_templates(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_ativo),
):
    """
    Lista os templates ativos e retorna o contrato JSON completo para
    que o frontend mobile renderize o formulário dinamicamente.
    """
    templates = (
        db.query(TemplatePDF)
        .filter(TemplatePDF.status == "ativo")
        .order_by(TemplatePDF.nome_documento)
        .all()
    )

    resultado = []
    for t in templates:
        campos_ordenados = sorted(t.campos, key=lambda c: c.ordem)
        campos_mobile = []
        for c in campos_ordenados:
            opcoes = None
            if c.opcoes:
                try:
                    opcoes = json.loads(c.opcoes)
                except Exception:
                    opcoes = [c.opcoes]
            campos_mobile.append(
                ContratoCampoMobile(
                    id=c.id,
                    nome_campo=c.nome_campo,
                    label=c.label,
                    tipo_campo=c.tipo_campo.value if hasattr(c.tipo_campo, "value") else c.tipo_campo,
                    obrigatorio=c.obrigatorio,
                    opcoes=opcoes,
                    ordem=c.ordem,
                )
            )
        resultado.append(
            ContratoTemplateMobile(
                template_id=t.id,
                nome_documento=t.nome_documento,
                descricao=t.descricao,
                campos=campos_mobile,
            )
        )
    return resultado


@router.get("/templates/{template_id}", response_model=ContratoTemplateMobile)
def obter_template(
    template_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_ativo),
):
    """Retorna um único template formatado para renderização mobile."""
    template = db.query(TemplatePDF).filter(
        TemplatePDF.id == template_id,
        TemplatePDF.status == "ativo",
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")

    campos_ordenados = sorted(template.campos, key=lambda c: c.ordem)
    campos_mobile = []
    for c in campos_ordenados:
        opcoes = None
        if c.opcoes:
            try:
                opcoes = json.loads(c.opcoes)
            except Exception:
                opcoes = [c.opcoes]
        campos_mobile.append(
            ContratoCampoMobile(
                id=c.id,
                nome_campo=c.nome_campo,
                label=c.label,
                tipo_campo=c.tipo_campo.value if hasattr(c.tipo_campo, "value") else c.tipo_campo,
                obrigatorio=c.obrigatorio,
                opcoes=opcoes,
                ordem=c.ordem,
            )
        )
    return ContratoTemplateMobile(
        template_id=template.id,
        nome_documento=template.nome_documento,
        descricao=template.descricao,
        campos=campos_mobile,
    )


# ===========================================================================
# SUBMISSÃO DE FORMULÁRIO
# ===========================================================================

@router.post("/submeter", response_model=FormularioResponse)
def submeter_formulario(
    payload: FormularioSubmit,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_ativo),
):
    """
    Recebe os dados preenchidos pelo guarda, gera o PDF oficial,
    cria o QR Code e retorna a URL de download para apresentar ao cidadão.
    """
    template = db.query(TemplatePDF).filter(
        TemplatePDF.id == payload.template_id,
        TemplatePDF.status == "ativo",
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template não encontrado.")

    # Valida campos obrigatórios
    campos_db = {c.nome_campo: c for c in template.campos}
    for nome, campo in campos_db.items():
        if campo.obrigatorio and not payload.dados.get(nome):
            raise HTTPException(
                status_code=400,
                detail=f"Campo obrigatório não preenchido: '{campo.label}'.",
            )

    # Adiciona autoria automática ao dado (cadeia de custódia)
    dados_com_autoria = dict(payload.dados)
    dados_com_autoria["__guarda_nome"]      = usuario.nome
    dados_com_autoria["__guarda_matricula"] = usuario.matricula
    dados_com_autoria["__guarda_equipe"]    = usuario.equipe or ""

    # Gera token único de 32 bytes (64 hex chars) — seguro criptograficamente
    token_hash = secrets.token_hex(32)

    # Gera o PDF preenchido
    caminho_pdf = gerar_pdf_preenchido(
        template_path=template.caminho_arquivo,
        campos=template.campos,
        dados=dados_com_autoria,
        token_hash=token_hash,
        nome_guarda=usuario.nome,
        matricula_guarda=usuario.matricula,
    )

    # URL pública para download (via Cloudflare Tunnel ou localhost)
    url_download = f"{settings.CLOUDFLARE_PUBLIC_URL}/download/{token_hash}"

    # Tenta enviar ao Google Drive e obter link temporário para o QR Code
    nome_arquivo_drive = f"{template.nome_documento.replace(' ', '_')}_{token_hash[:8]}.pdf"
    url_qr = upload_e_agendar_delecao(caminho_pdf, nome_arquivo_drive) or url_download

    # Gera QR Code apontando para Drive (se disponível) ou URL local
    caminho_qr = gerar_qrcode(url=url_qr, token_hash=token_hash)

    # Persiste a resposta com autoria imutável
    resposta = RespostaFormulario(
        template_id=template.id,
        usuario_id=usuario.id,
        dados_json=json.dumps(dados_com_autoria, ensure_ascii=False),
        token_hash_unico=token_hash,
        caminho_pdf_final=caminho_pdf,
        caminho_qrcode=caminho_qr,
        nome_guarda_autoria=usuario.nome,
        matricula_guarda_autoria=usuario.matricula,
        status="gerado",
    )
    db.add(resposta)
    db.commit()
    db.refresh(resposta)

    registrar_log(
        db=db,
        acao="EMISSAO_FORMULARIO",
        ip=request.client.host if request.client else None,
        usuario=usuario,
        detalhes=f"Formulário '{template.nome_documento}' emitido. Hash: {token_hash[:16]}...",
    )

    return FormularioResponse(
        id=resposta.id,
        template_id=resposta.template_id,
        token_hash_unico=resposta.token_hash_unico,
        data_criacao=resposta.data_criacao,
        status=resposta.status,
        url_qrcode=f"{settings.CLOUDFLARE_PUBLIC_URL}/api/documents/qrcode/{token_hash}",
        url_download=url_download,
        url_drive=url_qr if url_qr != url_download else None,
        nome_guarda_autoria=resposta.nome_guarda_autoria,
        matricula_guarda_autoria=resposta.matricula_guarda_autoria,
    )


@router.get("/meus-formularios", response_model=List[FormularioResponse])
def meus_formularios(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_ativo),
):
    """Histórico de formulários emitidos pelo guarda autenticado."""
    respostas = (
        db.query(RespostaFormulario)
        .filter(RespostaFormulario.usuario_id == usuario.id)
        .order_by(RespostaFormulario.data_criacao.desc())
        .limit(50)
        .all()
    )
    return [
        FormularioResponse(
            id=r.id,
            template_id=r.template_id,
            token_hash_unico=r.token_hash_unico,
            data_criacao=r.data_criacao,
            status=r.status,
            url_qrcode=f"{settings.CLOUDFLARE_PUBLIC_URL}/api/documents/qrcode/{r.token_hash_unico}",
            url_download=f"{settings.CLOUDFLARE_PUBLIC_URL}/download/{r.token_hash_unico}",
            nome_guarda_autoria=r.nome_guarda_autoria,
            matricula_guarda_autoria=r.matricula_guarda_autoria,
        )
        for r in respostas
    ]
