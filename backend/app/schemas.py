from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ===========================================================================
# AUTH / USUÁRIOS
# ===========================================================================

class UsuarioRegistro(BaseModel):
    nome:      str = Field(..., min_length=3, max_length=200)
    matricula: str = Field(..., min_length=2, max_length=50)
    equipe:    Optional[str] = Field(None, max_length=100)
    senha:     str = Field(..., min_length=6, max_length=128)

    @field_validator("matricula")
    @classmethod
    def matricula_upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("nome")
    @classmethod
    def nome_strip(cls, v: str) -> str:
        return v.strip()


class UsuarioLogin(BaseModel):
    matricula: str
    senha:     str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    usuario:      "UsuarioPublico"


class UsuarioPublico(BaseModel):
    id:               int
    nome:             str
    matricula:        str
    equipe:           Optional[str]
    status_aprovacao: str
    is_admin:         bool
    data_cadastro:    datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# TEMPLATES PDF
# ===========================================================================

class CampoDinamicoCreate(BaseModel):
    nome_campo:      str = Field(..., max_length=200)
    label:           str = Field(..., max_length=200)
    tipo_campo:      str = Field("text")
    obrigatorio:     bool = True
    opcoes:          Optional[str] = None   # JSON string
    ordem:           int = 0
    coordenadas_pdf: Optional[str] = None  # JSON string


class CampoDinamicoResponse(BaseModel):
    id:              int
    nome_campo:      str
    label:           str
    tipo_campo:      str
    obrigatorio:     bool
    opcoes:          Optional[str]
    ordem:           int
    coordenadas_pdf: Optional[str]

    model_config = {"from_attributes": True}


class TemplatePDFResponse(BaseModel):
    id:             int
    nome_documento: str
    descricao:      Optional[str]
    data_upload:    datetime
    status:         str
    total_paginas:  int
    campos:         List[CampoDinamicoResponse] = []

    model_config = {"from_attributes": True}


# ===========================================================================
# FORMULÁRIOS / RESPOSTAS
# ===========================================================================

class FormularioSubmit(BaseModel):
    template_id: int
    dados:       Dict[str, Any]   # {nome_campo: valor}


class FormularioResponse(BaseModel):
    id:               int
    template_id:      int
    token_hash_unico: str
    data_criacao:     datetime
    status:           str
    url_qrcode:       Optional[str] = None
    url_download:     Optional[str] = None

    # Autoria imutável
    nome_guarda_autoria:      str
    matricula_guarda_autoria: str

    model_config = {"from_attributes": True}


# ===========================================================================
# PAYLOAD JSON DE CONTRATO  (Backend → Frontend Mobile)
# Exemplo completo para documentação / OpenAPI
# ===========================================================================

class ContratoCampoMobile(BaseModel):
    """Representa um campo que o frontend mobile deve renderizar dinamicamente."""
    id:          int
    nome_campo:  str            # slug interno, ex: "nome_abordado"
    label:       str            # rótulo na tela, ex: "Nome do Abordado"
    tipo_campo:  str            # text | number | date | time | textarea | select | checkbox | cpf | placa
    obrigatorio: bool
    opcoes:      Optional[List[str]] = None   # Apenas para tipo "select"
    ordem:       int


class ContratoTemplateMobile(BaseModel):
    """Payload completo que o frontend recebe para montar o formulário na tela."""
    template_id:    int
    nome_documento: str
    descricao:      Optional[str]
    campos:         List[ContratoCampoMobile]

    model_config = {
        "json_schema_extra": {
            "example": {
                "template_id": 1,
                "nome_documento": "Termo de Apreensão",
                "descricao": "Registro de apreensão de objetos em abordagem.",
                "campos": [
                    {"id": 1, "nome_campo": "nome_abordado",     "label": "Nome do Abordado",       "tipo_campo": "text",     "obrigatorio": True,  "opcoes": None, "ordem": 1},
                    {"id": 2, "nome_campo": "cpf_abordado",      "label": "CPF do Abordado",        "tipo_campo": "cpf",      "obrigatorio": False, "opcoes": None, "ordem": 2},
                    {"id": 3, "nome_campo": "rg_abordado",       "label": "RG",                     "tipo_campo": "number",   "obrigatorio": True,  "opcoes": None, "ordem": 3},
                    {"id": 4, "nome_campo": "data_abordagem",    "label": "Data da Abordagem",      "tipo_campo": "date",     "obrigatorio": True,  "opcoes": None, "ordem": 4},
                    {"id": 5, "nome_campo": "hora_abordagem",    "label": "Hora da Abordagem",      "tipo_campo": "time",     "obrigatorio": True,  "opcoes": None, "ordem": 5},
                    {"id": 6, "nome_campo": "local_abordagem",   "label": "Local / Endereço",       "tipo_campo": "text",     "obrigatorio": True,  "opcoes": None, "ordem": 6},
                    {"id": 7, "nome_campo": "objetos_apreendidos","label": "Objetos Apreendidos",   "tipo_campo": "textarea", "obrigatorio": True,  "opcoes": None, "ordem": 7},
                    {"id": 8, "nome_campo": "situacao_item",     "label": "Situação do Item",       "tipo_campo": "select",   "obrigatorio": True,
                     "opcoes": ["Ilícito", "Produto de Furto", "Objeto Suspeito", "Outro"], "ordem": 8},
                ],
            }
        }
    }


# ===========================================================================
# ADMIN
# ===========================================================================

class AprovarUsuarioPayload(BaseModel):
    usuario_id: int
    acao:       str   # "aprovar" | "rejeitar"


class LogAuditoriaResponse(BaseModel):
    id:               int
    acao:             str
    timestamp:        datetime
    ip_origem:        Optional[str]
    nome_usuario:     Optional[str]
    matricula_usuario: Optional[str]
    detalhes:         Optional[str]

    model_config = {"from_attributes": True}
