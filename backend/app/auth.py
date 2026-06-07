"""
Módulo de autenticação: hashing de senhas e geração/validação de JWT.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Usuario, StatusAprovacao

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Hashing de Senha
# ---------------------------------------------------------------------------

def hash_senha(senha: str) -> str:
    """Retorna o hash bcrypt da senha fornecida."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Verifica se a senha em texto plano confere com o hash armazenado."""
    return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def criar_access_token(dados: dict, expira_em: Optional[int] = None) -> str:
    """Gera um JWT assinado com os dados fornecidos."""
    payload = dados.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expira_em or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Decodifica e valida um JWT. Lança HTTPException em caso de falha."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Dependencies FastAPI
# ---------------------------------------------------------------------------

def _extrair_usuario_atual(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: Session,
) -> Usuario:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido.",
        )
    payload = decodificar_token(credentials.credentials)
    usuario_id: int = payload.get("sub")
    if not usuario_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    usuario = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    return usuario


def get_usuario_atual(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependency: retorna o usuário autenticado (qualquer status)."""
    return _extrair_usuario_atual(credentials, db)


def get_usuario_ativo(
    usuario: Usuario = Depends(get_usuario_atual),
) -> Usuario:
    """Dependency: garante que o usuário está ativo (aprovado pelo admin)."""
    if usuario.status_aprovacao != StatusAprovacao.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Cadastro pendente de aprovação ou inativo.",
        )
    return usuario


def get_admin(
    usuario: Usuario = Depends(get_usuario_ativo),
) -> Usuario:
    """Dependency: garante que o usuário ativo tem perfil de administrador."""
    if not usuario.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario
