"""
Rotas de autenticação: registro, login, status do cadastro.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import criar_access_token, hash_senha, verificar_senha, get_usuario_atual
from ..database import get_db
from ..models import Usuario, StatusAprovacao
from ..schemas import TokenResponse, UsuarioLogin, UsuarioPublico, UsuarioRegistro
from ..services.audit import registrar_log

router = APIRouter()


@router.post("/registrar", response_model=UsuarioPublico, status_code=status.HTTP_201_CREATED)
def registrar(payload: UsuarioRegistro, request: Request, db: Session = Depends(get_db)):
    """
    Cria um novo usuário com status PENDENTE.
    O acesso só é liberado após aprovação manual do Administrador na base.
    """
    existente = db.query(Usuario).filter(
        Usuario.matricula == payload.matricula.upper()
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Matrícula já cadastrada no sistema.",
        )

    novo_usuario = Usuario(
        nome=payload.nome.strip(),
        matricula=payload.matricula.strip().upper(),
        equipe=payload.equipe.strip() if payload.equipe else None,
        senha_hash=hash_senha(payload.senha),
        status_aprovacao=StatusAprovacao.pendente,
        is_admin=False,
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    registrar_log(
        db=db,
        acao="REGISTRO_PENDENTE",
        ip=request.client.host if request.client else None,
        usuario=novo_usuario,
        detalhes=f"Novo cadastro solicitado: {novo_usuario.nome} | Equipe: {novo_usuario.equipe}",
    )

    return novo_usuario


@router.post("/login", response_model=TokenResponse)
def login(payload: UsuarioLogin, request: Request, db: Session = Depends(get_db)):
    """
    Autentica o usuário e retorna um JWT.
    Usuários com status PENDENTE ou REJEITADO recebem mensagem específica.
    """
    usuario = db.query(Usuario).filter(
        Usuario.matricula == payload.matricula.strip().upper()
    ).first()

    if not usuario or not verificar_senha(payload.senha, usuario.senha_hash):
        # Mesmo erro para não revelar qual campo está errado (prevenção de enumeração)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Matrícula ou senha incorretos.",
        )

    if usuario.status_aprovacao == StatusAprovacao.pendente:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PENDENTE: Seu cadastro ainda não foi aprovado pelo Administrador.",
        )

    if usuario.status_aprovacao == StatusAprovacao.rejeitado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="REJEITADO: Seu cadastro foi rejeitado. Entre em contato com a chefia.",
        )

    if usuario.status_aprovacao == StatusAprovacao.inativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="INATIVO: Sua conta foi desativada. Entre em contato com a chefia.",
        )

    token = criar_access_token({"sub": str(usuario.id)})

    registrar_log(
        db=db,
        acao="LOGIN",
        ip=request.client.host if request.client else None,
        usuario=usuario,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        usuario=UsuarioPublico.model_validate(usuario),
    )


@router.get("/me", response_model=UsuarioPublico)
def me(usuario: Usuario = Depends(get_usuario_atual)):
    """Retorna os dados do usuário autenticado (inclusive status de aprovação)."""
    return usuario


@router.get("/status", response_model=dict)
def status_cadastro(usuario: Usuario = Depends(get_usuario_atual)):
    """
    Endpoint consultado periodicamente pelo mobile para verificar
    se o cadastro pendente foi aprovado.
    """
    return {
        "status_aprovacao": usuario.status_aprovacao.value,
        "nome": usuario.nome,
        "matricula": usuario.matricula,
    }
