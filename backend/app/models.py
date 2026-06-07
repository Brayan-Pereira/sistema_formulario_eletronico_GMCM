import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    Text, Enum as SAEnum, Boolean
)
from sqlalchemy.orm import relationship

from .database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StatusAprovacao(str, enum.Enum):
    pendente  = "pendente"
    ativo     = "ativo"
    inativo   = "inativo"
    rejeitado = "rejeitado"


class TipoCampo(str, enum.Enum):
    text      = "text"
    number    = "number"
    date      = "date"
    time      = "time"
    textarea  = "textarea"
    select    = "select"
    checkbox  = "checkbox"
    cpf       = "cpf"
    placa     = "placa"


# ---------------------------------------------------------------------------
# Tabela: usuarios
# ---------------------------------------------------------------------------

class Usuario(Base):
    __tablename__ = "usuarios"

    id                = Column(Integer, primary_key=True, index=True)
    nome              = Column(String(200), nullable=False)
    matricula         = Column(String(50), unique=True, nullable=False, index=True)
    equipe            = Column(String(100), nullable=True)
    senha_hash        = Column(String(255), nullable=False)
    status_aprovacao  = Column(
        SAEnum(StatusAprovacao, name="status_aprovacao"),
        default=StatusAprovacao.pendente,
        nullable=False,
    )
    is_admin          = Column(Boolean, default=False, nullable=False)
    data_cadastro     = Column(DateTime, default=datetime.utcnow)
    data_aprovacao    = Column(DateTime, nullable=True)
    aprovado_por_id   = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    formularios = relationship("RespostaFormulario", back_populates="usuario",
                               foreign_keys="RespostaFormulario.usuario_id")
    logs        = relationship("LogAuditoria", back_populates="usuario",
                               foreign_keys="LogAuditoria.usuario_id")


# ---------------------------------------------------------------------------
# Tabela: templates_pdf
# ---------------------------------------------------------------------------

class TemplatePDF(Base):
    __tablename__ = "templates_pdf"

    id              = Column(Integer, primary_key=True, index=True)
    nome_documento  = Column(String(200), nullable=False)
    descricao       = Column(Text, nullable=True)
    caminho_arquivo = Column(String(500), nullable=False)
    data_upload     = Column(DateTime, default=datetime.utcnow)
    status          = Column(String(20), default="ativo")   # ativo | inativo
    total_paginas   = Column(Integer, default=1)
    criado_por_id   = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    campos   = relationship("CampoDinamico", back_populates="template",
                            cascade="all, delete-orphan")
    respostas = relationship("RespostaFormulario", back_populates="template")


# ---------------------------------------------------------------------------
# Tabela: campos_dinamicos
# ---------------------------------------------------------------------------

class CampoDinamico(Base):
    __tablename__ = "campos_dinamicos"

    id              = Column(Integer, primary_key=True, index=True)
    template_id     = Column(Integer, ForeignKey("templates_pdf.id"), nullable=False)
    nome_campo      = Column(String(200), nullable=False)   # slug, ex: "nome_abordado"
    label           = Column(String(200), nullable=False)   # rótulo legível
    tipo_campo      = Column(SAEnum(TipoCampo, name="tipo_campo"), default=TipoCampo.text)
    obrigatorio     = Column(Boolean, default=True)
    opcoes          = Column(Text, nullable=True)   # JSON p/ select (["opt1","opt2"])
    ordem           = Column(Integer, default=0)

    # Coordenadas no PDF onde o valor será inserido (JSON: {page,x,y,w,h,font_size})
    coordenadas_pdf = Column(Text, nullable=True)

    template = relationship("TemplatePDF", back_populates="campos")


# ---------------------------------------------------------------------------
# Tabela: respostas_formularios
# ---------------------------------------------------------------------------

class RespostaFormulario(Base):
    __tablename__ = "respostas_formularios"

    id               = Column(Integer, primary_key=True, index=True)
    template_id      = Column(Integer, ForeignKey("templates_pdf.id"), nullable=False)
    usuario_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    dados_json       = Column(Text, nullable=False)   # JSON dos campos preenchidos
    token_hash_unico = Column(String(64), unique=True, nullable=False, index=True)
    caminho_pdf_final = Column(String(500), nullable=True)
    caminho_qrcode   = Column(String(500), nullable=True)
    data_criacao     = Column(DateTime, default=datetime.utcnow)
    status           = Column(String(30), default="gerado")  # gerado | erro

    # Desnormalização para cadeia de custódia imutável
    nome_guarda_autoria      = Column(String(200), nullable=False)
    matricula_guarda_autoria = Column(String(50),  nullable=False)

    template = relationship("TemplatePDF", back_populates="respostas")
    usuario  = relationship("Usuario", back_populates="formularios",
                            foreign_keys=[usuario_id])


# ---------------------------------------------------------------------------
# Tabela: logs_auditoria
# ---------------------------------------------------------------------------

class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id         = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    acao       = Column(String(500), nullable=False)
    timestamp  = Column(DateTime, default=datetime.utcnow)
    ip_origem  = Column(String(45), nullable=True)   # Suporta IPv6
    detalhes   = Column(Text, nullable=True)

    # Desnormalização: guarda nome+matrícula mesmo se usuário for deletado
    nome_usuario      = Column(String(200), nullable=True)
    matricula_usuario = Column(String(50),  nullable=True)

    usuario = relationship("Usuario", back_populates="logs",
                           foreign_keys=[usuario_id])
