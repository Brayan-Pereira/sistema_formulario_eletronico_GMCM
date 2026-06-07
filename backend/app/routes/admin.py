"""
Rotas de administração: aprovação de usuários, upload de templates e auditoria.
Acesso restrito a usuários com is_admin=True.
"""
import json
import os
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import get_admin, get_usuario_ativo
from ..config import settings
from ..database import get_db
from ..models import CampoDinamico, LogAuditoria, TemplatePDF, Usuario, StatusAprovacao
from ..schemas import (
    AprovarUsuarioPayload, CampoDinamicoCreate, LogAuditoriaResponse,
    TemplatePDFResponse, UsuarioPublico,
)
from ..services.audit import registrar_log
from ..services.pdf_processor import processar_template_pdf

router = APIRouter()


# ===========================================================================
# USUÁRIOS PENDENTES
# ===========================================================================

@router.get("/usuarios/pendentes", response_model=List[UsuarioPublico])
def listar_pendentes(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Lista todos os usuários aguardando aprovação."""
    return db.query(Usuario).filter(
        Usuario.status_aprovacao == StatusAprovacao.pendente
    ).order_by(Usuario.data_cadastro).all()


@router.get("/usuarios", response_model=List[UsuarioPublico])
def listar_usuarios(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Lista todos os usuários (exceto o próprio admin logado)."""
    return db.query(Usuario).filter(Usuario.id != admin.id).order_by(Usuario.data_cadastro.desc()).all()


@router.post("/usuarios/aprovar")
def aprovar_usuario(
    payload: AprovarUsuarioPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Aprova ou rejeita o cadastro de um guarda."""
    usuario = db.query(Usuario).filter(Usuario.id == payload.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if payload.acao == "aprovar":
        usuario.status_aprovacao = StatusAprovacao.ativo
        usuario.data_aprovacao = datetime.utcnow()
        usuario.aprovado_por_id = admin.id
        acao_log = "APROVACAO_USUARIO"
        mensagem = f"Usuário {usuario.nome} ({usuario.matricula}) APROVADO."
    elif payload.acao == "rejeitar":
        usuario.status_aprovacao = StatusAprovacao.rejeitado
        acao_log = "REJEICAO_USUARIO"
        mensagem = f"Usuário {usuario.nome} ({usuario.matricula}) REJEITADO."
    elif payload.acao == "inativar":
        usuario.status_aprovacao = StatusAprovacao.inativo
        acao_log = "INATIVACAO_USUARIO"
        mensagem = f"Usuário {usuario.nome} ({usuario.matricula}) INATIVADO."
    else:
        raise HTTPException(status_code=400, detail="Ação inválida. Use: aprovar | rejeitar | inativar.")

    db.commit()
    registrar_log(db=db, acao=acao_log, ip=request.client.host if request.client else None,
                  usuario=admin, detalhes=mensagem)
    return {"ok": True, "mensagem": mensagem}


# ===========================================================================
# TEMPLATES PDF
# ===========================================================================

@router.post("/templates", response_model=TemplatePDFResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(
    request: Request,
    nome_documento: str = Form(...),
    descricao: Optional[str] = Form(None),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """
    Faz upload de um PDF em branco, processa os campos detectados automaticamente
    e salva o modelo no banco.
    """
    if not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    # Verifica tamanho máximo
    conteudo = await arquivo.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(conteudo) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo muito grande. Máximo: {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # Salva o arquivo no disco
    nome_seguro = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{arquivo.filename.replace(' ', '_')}"
    caminho_destino = os.path.join(settings.TEMPLATES_DIR, nome_seguro)
    with open(caminho_destino, "wb") as f:
        f.write(conteudo)

    # Processa o PDF e extrai campos detectados
    resultado = processar_template_pdf(caminho_destino)

    # Cria o registro do template
    template = TemplatePDF(
        nome_documento=nome_documento.strip(),
        descricao=descricao.strip() if descricao else None,
        caminho_arquivo=caminho_destino,
        total_paginas=resultado.get("total_paginas", 1),
        criado_por_id=admin.id,
    )
    db.add(template)
    db.flush()  # Obtém o ID antes do commit

    # Salva campos detectados automaticamente
    for campo_data in resultado.get("campos", []):
        campo = CampoDinamico(
            template_id=template.id,
            nome_campo=campo_data["nome_campo"],
            label=campo_data["label"],
            tipo_campo=campo_data.get("tipo_campo", "text"),
            obrigatorio=campo_data.get("obrigatorio", True),
            ordem=campo_data.get("ordem", 0),
            coordenadas_pdf=json.dumps(campo_data.get("coordenadas")) if campo_data.get("coordenadas") else None,
        )
        db.add(campo)

    db.commit()
    db.refresh(template)

    registrar_log(db=db, acao="UPLOAD_TEMPLATE", ip=request.client.host if request.client else None,
                  usuario=admin, detalhes=f"Template '{nome_documento}' enviado ({len(conteudo)//1024} KB).")
    return template


@router.get("/templates", response_model=List[TemplatePDFResponse])
def listar_templates_admin(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Lista todos os templates (incluindo inativos) para o painel admin."""
    return db.query(TemplatePDF).order_by(TemplatePDF.data_upload.desc()).all()


@router.delete("/templates/{template_id}")
def desativar_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Desativa um template (soft delete)."""
    template = db.query(TemplatePDF).filter(TemplatePDF.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template não encontrado.")
    template.status = "inativo"
    db.commit()
    registrar_log(db=db, acao="DESATIVAR_TEMPLATE", ip=request.client.host if request.client else None,
                  usuario=admin, detalhes=f"Template ID {template_id} desativado.")
    return {"ok": True}


@router.post("/templates/{template_id}/campos", response_model=TemplatePDFResponse)
def salvar_campos_template(
    template_id: int,
    campos: List[CampoDinamicoCreate],
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """
    Substitui todos os campos de um template.
    Usado pelo editor de campos no painel admin.
    """
    template = db.query(TemplatePDF).filter(TemplatePDF.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template não encontrado.")

    # Remove campos existentes
    db.query(CampoDinamico).filter(CampoDinamico.template_id == template_id).delete()

    for i, c in enumerate(campos):
        novo = CampoDinamico(
            template_id=template_id,
            nome_campo=c.nome_campo.strip().lower().replace(" ", "_"),
            label=c.label.strip(),
            tipo_campo=c.tipo_campo,
            obrigatorio=c.obrigatorio,
            opcoes=c.opcoes,
            ordem=c.ordem if c.ordem else i,
            coordenadas_pdf=c.coordenadas_pdf,
        )
        db.add(novo)

    db.commit()
    db.refresh(template)

    registrar_log(db=db, acao="EDITAR_CAMPOS_TEMPLATE", ip=request.client.host if request.client else None,
                  usuario=admin, detalhes=f"Template ID {template_id}: {len(campos)} campos salvos.")
    return template


# ===========================================================================
# AUDITORIA
# ===========================================================================

@router.get("/auditoria", response_model=List[LogAuditoriaResponse])
def listar_logs(
    limite: int = 100,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Retorna os últimos registros de auditoria."""
    return (
        db.query(LogAuditoria)
        .order_by(LogAuditoria.timestamp.desc())
        .limit(min(limite, 500))
        .all()
    )


@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin),
):
    """Estatísticas rápidas para o painel admin."""
    from ..models import RespostaFormulario
    return {
        "pendentes":          db.query(Usuario).filter(Usuario.status_aprovacao == StatusAprovacao.pendente).count(),
        "ativos":             db.query(Usuario).filter(Usuario.status_aprovacao == StatusAprovacao.ativo).count(),
        "templates_ativos":   db.query(TemplatePDF).filter(TemplatePDF.status == "ativo").count(),
        "formularios_hoje":   db.query(RespostaFormulario).filter(
            RespostaFormulario.data_criacao >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).count(),
        "total_formularios":  db.query(RespostaFormulario).count(),
    }
