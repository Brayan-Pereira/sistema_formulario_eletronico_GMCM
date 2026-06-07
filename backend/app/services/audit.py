"""
Serviço de log de auditoria.
Registra todas as ações relevantes com usuário, IP e timestamp.
Os registros são imutáveis (apenas INSERT, nunca UPDATE/DELETE na tabela de logs).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import LogAuditoria, Usuario


def registrar_log(
    db: Session,
    acao: str,
    ip: Optional[str] = None,
    usuario: Optional[Usuario] = None,
    detalhes: Optional[str] = None,
) -> LogAuditoria:
    """
    Insere um registro imutável no log de auditoria.

    Parâmetros:
      acao     — Código da ação (ex: LOGIN, EMISSAO_FORMULARIO, APROVACAO_USUARIO)
      ip       — IP de origem da requisição
      usuario  — Objeto Usuario autenticado (pode ser None para ações anônimas)
      detalhes — Informações adicionais em texto livre
    """
    log = LogAuditoria(
        usuario_id=usuario.id if usuario else None,
        acao=acao,
        timestamp=datetime.utcnow(),
        ip_origem=ip,
        detalhes=detalhes,
        nome_usuario=usuario.nome if usuario else None,
        matricula_usuario=usuario.matricula if usuario else None,
    )
    db.add(log)
    db.commit()
    return log
