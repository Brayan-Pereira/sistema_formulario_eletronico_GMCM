# Sistema de Formulários Eletrônicos — Guarda Municipal

Plataforma web para **desmaterialização e emissão digital de documentos operacionais** da Guarda Municipal (Termos de Apreensão, BOs internos, Cautelas de Equipamento, Termos de Liberação, etc.).

- **Mobile (rua):** Interface otimizada para smartphone, modo escuro, botões grandes para uso com polegar
- **Desktop (base):** Painel administrativo para aprovação de cadastros, upload de modelos e auditoria
- **Cidadão:** Recebe o documento instantaneamente via QR Code, sem precisar de login

---

## Status do Projeto

| Item | Status |
|------|--------|
| Backend FastAPI | Operacional |
| Banco de dados SQLite | Criado e populado |
| Autenticação JWT + bcrypt | Operacional |
| Painel Admin | Operacional |
| QR Code + Download público | Operacional |
| Extração automática de campos PDF | Operacional (pdfplumber + PyMuPDF) |
| Geração de PDF preenchido | Operacional (reportlab + overlay PyMuPDF) |
| Frontend SPA mobile-first | Operacional |
| Dark Mode | Operacional |

---

## Arquitetura

```
 ┌─────────────────────────────────────────────────────────┐
 │                    REDE LOCAL (Wi-Fi)                   │
 │                                                         │
 │  [Guarda - Smartphone] ──────────────────────────────►  │
 │                                    http://IP:8000        │
 │  [Cidadão - Smartphone] ─────────────────────────────►  │
 │    (escaneia QR Code)              http://IP:8000        │
 │                                         │               │
 │                                         ▼               │
 │                          [PC da Base — Servidor]        │
 │                          ├── FastAPI (Python 3.13)      │
 │                          ├── SQLite (guarda_municipal.db)│
 │                          ├── storage/templates/         │
 │                          ├── storage/generated/         │
 │                          └── storage/qrcodes/           │
 └─────────────────────────────────────────────────────────┘

             OU (para acesso via internet móvel):

 [Guarda/Cidadão - 4G/5G]
         │  HTTPS criptografado
         ▼
 [Cloudflare Tunnel] → [PC da Base — Servidor local]
```

**Soberania dos dados:** PDFs, banco de dados e QR Codes ficam **exclusivamente no HD local** da base. O Cloudflare Tunnel atua apenas como proxy criptografado, sem armazenar nada.

---

## Pré-requisitos

| Requisito | Versão | Instalado? |
|-----------|--------|------------|
| Python | 3.13.7 | ✓ (`py` no PATH) |
| Cloudflare Tunnel | Qualquer | Opcional (para acesso externo) |

> No Windows, o comando Python é **`py`** (não `python`). O `setup.bat` já trata isso automaticamente.

---

## Instalação

### Passo 1 — Executar o setup (apenas uma vez)

Clique duas vezes em **`scripts\setup.bat`** ou execute no terminal:

```bat
cd "Guarda Municipal projeto"
scripts\setup.bat
```

O script faz automaticamente:
1. Detecta o Python (`py`)
2. Cria o ambiente virtual `.venv`
3. Instala todas as dependências
4. Cria o banco de dados SQLite e todas as tabelas
5. Cria o usuário administrador padrão

### Passo 2 — Configurar o `.env`

O arquivo `.env` já foi criado em `scripts\setup.bat`. Edite conforme necessário:

```bat
notepad .env
```

Variáveis principais:

```env
# URL usada nos QR Codes — use o IP da máquina para acesso na rede Wi-Fi local
CLOUDFLARE_PUBLIC_URL=http://192.168.100.102:8000

# Chave secreta para JWT — OBRIGATÓRIO alterar em produção
SECRET_KEY=sua_chave_aleatoria_longa_aqui

# Credenciais do admin padrão (usadas apenas no setup inicial)
ADMIN_MATRICULA=ADMIN001
ADMIN_SENHA=TroqueEstaSenha@123
```

> Para gerar uma `SECRET_KEY` segura: `.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"`

### Passo 3 — Iniciar o servidor

Clique duas vezes em **`scripts\start.bat`** ou execute:

```bat
scripts\start.bat
```

Ou manualmente (com o venv ativado):

```powershell
.\.venv\Scripts\activate.ps1
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesso local: **http://localhost:8000**
Acesso na rede: **http://192.168.100.102:8000**
Documentação API: **http://localhost:8000/api/docs**

---

## QR Code — Como funciona

O QR Code gerado pelo sistema aponta para a variável `CLOUDFLARE_PUBLIC_URL` do `.env`.

### Cenário 1 — Rede Wi-Fi local (base + viaturas próximas)

```env
CLOUDFLARE_PUBLIC_URL=http://192.168.100.102:8000
```

O celular do cidadão e o servidor precisam estar na mesma rede Wi-Fi. O guarda emite o documento → apresenta o QR Code → cidadão escaneia → baixa o PDF.

### Cenário 2 — Internet móvel (patrulhamento externo)

1. Instale o [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. Execute em um terminal separado:
   ```bat
   cloudflared tunnel --url http://localhost:8000
   ```
3. Copie a URL gerada (ex: `https://xyz.trycloudflare.com`) e edite o `.env`:
   ```env
   CLOUDFLARE_PUBLIC_URL=https://xyz.trycloudflare.com
   ```
4. Reinicie o servidor

> Documentos já emitidos mantêm a URL antiga no QR Code. Somente novos documentos usarão a nova URL.

### Rota de download pública

```
/download/{hash}     →  302 redirect  →  /api/documents/download/{hash}  →  PDF
/visualizar/{hash}   →  302 redirect  →  /api/documents/visualizar/{hash} →  Página HTML
```

O hash tem 64 caracteres hexadecimais (256 bits de entropia), tornando a adivinhagem computacionalmente inviável.

---

## Primeiro Uso

### Credenciais do Administrador padrão

| Campo | Valor |
|-------|-------|
| Matrícula | `ADMIN001` |
| Senha | `TroqueEstaSenha@123` |
| Acesso | http://localhost:8000 |

> ⚠️ **Troque a senha imediatamente após o primeiro login!**

### Fluxo operacional completo

```
1. ADMIN (base)
   └── Login → Painel Admin → Templates → Enviar Novo Modelo (PDF em branco)
       └── Sistema detecta campos automaticamente
       └── Admin ajusta campos manualmente se necessário (botão ✏️ Campos)

2. GUARDA (smartphone)
   └── Acessa http://IP:8000 no navegador
   └── "Solicitar Cadastro" → preenche Nome, Matrícula, Viatura, Senha
   └── Tela de espera: "Aguardando Aprovação..."

3. ADMIN aprova
   └── Painel Admin → Aprovações → ✓ Aprovar
   └── Guarda recebe acesso automaticamente (polling a cada 15s)

4. GUARDA emite documento
   └── Dashboard → seleciona o formulário
   └── Preenche os campos na tela
   └── "Emitir Documento" → PDF gerado → QR Code exibido

5. CIDADÃO recebe cópia digital
   └── Aponta câmera para o QR Code
   └── Abre página de visualização no próprio celular
   └── Baixa o PDF (sem login, sem app)
```

---

## Estrutura de Pastas

```
Guarda Municipal projeto/
├── .env                         # Configuração ativa (criado pelo setup)
├── .env.example                 # Modelo de configuração
├── README.md
│
├── backend/
│   ├── requirements.txt         # Dependências Python
│   └── app/
│       ├── main.py              # Ponto de entrada FastAPI + montagem de rotas
│       ├── config.py            # Leitura do .env via python-dotenv
│       ├── database.py          # Conexão SQLAlchemy / SQLite
│       ├── models.py            # Tabelas ORM (5 tabelas)
│       ├── schemas.py           # Schemas Pydantic + contrato JSON mobile
│       ├── auth.py              # JWT HS256 + bcrypt + dependencies de guarda/admin
│       ├── routes/
│       │   ├── auth.py          # POST /api/auth/registrar|login  GET /api/auth/status|me
│       │   ├── admin.py         # /api/admin/* — aprovações, templates, auditoria
│       │   ├── forms.py         # /api/forms/* — listagem e submissão de formulários
│       │   └── documents.py     # /api/documents/* — download, QR Code, visualização
│       └── services/
│           ├── pdf_processor.py # Extração de campos: AcroForm → pdfplumber → OCR
│           ├── pdf_generator.py # Geração do PDF: overlay PyMuPDF ou reportlab
│           ├── qr_generator.py  # QR Code PNG (qrcode[pil])
│           └── audit.py         # Log imutável de auditoria (só INSERT)
│
├── frontend/
│   ├── index.html               # SPA — 7 views em um único arquivo HTML
│   └── static/
│       ├── css/style.css        # Mobile-first, dark mode, paleta azul-marinho
│       └── js/
│           ├── app.js           # Roteador SPA, dark mode, polling de aprovação
│           ├── auth.js          # JWT em localStorage, login/registro/logout
│           ├── forms.js         # Renderização dinâmica + máscaras (CPF, placa)
│           ├── admin.js         # Painel admin: aprovações, upload, editor de campos
│           └── network.js       # Banner offline + retry automático
│
├── storage/                     # Criado automaticamente — dados locais
│   ├── templates/               # PDFs originais enviados pelo admin
│   ├── generated/               # PDFs preenchidos e emitidos pelos guardas
│   ├── qrcodes/                 # Imagens PNG dos QR Codes gerados
│   └── guarda_municipal.db      # Banco de dados SQLite
│
└── scripts/
    ├── setup.bat                # Setup completo (venv + deps + banco + admin)
    ├── start.bat                # Inicia o servidor uvicorn
    └── setup_admin.py           # Script Python chamado pelo setup.bat
```

---

## Schema do Banco de Dados

### `usuarios`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER PK | — |
| nome | VARCHAR(200) | Nome completo |
| matricula | VARCHAR(50) UNIQUE | RE/Matrícula (sempre maiúsculo) |
| equipe | VARCHAR(100) | Viatura ou equipe |
| senha_hash | VARCHAR(255) | Hash bcrypt |
| status_aprovacao | ENUM | `pendente` / `ativo` / `inativo` / `rejeitado` |
| is_admin | BOOLEAN | Acesso ao painel admin |
| data_cadastro | DATETIME | — |
| data_aprovacao | DATETIME | Preenchida ao aprovar |
| aprovado_por_id | FK → usuarios | Admin que aprovou |

### `templates_pdf`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER PK | — |
| nome_documento | VARCHAR(200) | Ex: "Termo de Apreensão" |
| caminho_arquivo | VARCHAR(500) | Caminho no HD local |
| data_upload | DATETIME | — |
| status | VARCHAR(20) | `ativo` / `inativo` |
| total_paginas | INTEGER | — |

### `campos_dinamicos`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER PK | — |
| template_id | FK | — |
| nome_campo | VARCHAR(200) | Slug interno (`nome_abordado`) |
| label | VARCHAR(200) | Rótulo exibido na tela |
| tipo_campo | ENUM | `text`, `number`, `date`, `time`, `textarea`, `select`, `checkbox`, `cpf`, `placa` |
| obrigatorio | BOOLEAN | — |
| opcoes | TEXT | JSON array (apenas para `select`) |
| ordem | INTEGER | Ordem de exibição |
| coordenadas_pdf | TEXT | JSON `{page, x, y, w, h, font_size}` para overlay |

### `respostas_formularios`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER PK | — |
| template_id | FK | — |
| usuario_id | FK | — |
| dados_json | TEXT | JSON com todos os valores preenchidos |
| token_hash_unico | VARCHAR(64) UNIQUE | 64 chars hex (256 bits) — chave do QR Code |
| caminho_pdf_final | VARCHAR(500) | PDF gerado no HD local |
| caminho_qrcode | VARCHAR(500) | PNG do QR Code no HD local |
| data_criacao | DATETIME | — |
| nome_guarda_autoria | VARCHAR(200) | **Desnormalizado** — imutável (cadeia de custódia) |
| matricula_guarda_autoria | VARCHAR(50) | **Desnormalizado** — imutável |

### `logs_auditoria`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | INTEGER PK | — |
| usuario_id | FK | Pode ser NULL (ações anônimas) |
| acao | VARCHAR(500) | Código: `LOGIN`, `EMISSAO_FORMULARIO`, `APROVACAO_USUARIO`, etc. |
| timestamp | DATETIME | UTC |
| ip_origem | VARCHAR(45) | Suporta IPv4 e IPv6 |
| detalhes | TEXT | Texto livre com contexto adicional |
| nome_usuario | VARCHAR(200) | **Desnormalizado** — preservado mesmo se usuário deletado |
| matricula_usuario | VARCHAR(50) | **Desnormalizado** |

---

## Contrato JSON — Backend → Frontend Mobile

Payload que o backend envia para o celular renderizar o formulário dinamicamente:

```json
{
  "template_id": 1,
  "nome_documento": "Termo de Apreensão",
  "descricao": "Registro de apreensão de objetos em abordagem.",
  "campos": [
    { "id": 1, "nome_campo": "nome_abordado",     "label": "Nome do Abordado",    "tipo_campo": "text",     "obrigatorio": true,  "opcoes": null, "ordem": 1 },
    { "id": 2, "nome_campo": "cpf_abordado",      "label": "CPF do Abordado",     "tipo_campo": "cpf",      "obrigatorio": false, "opcoes": null, "ordem": 2 },
    { "id": 3, "nome_campo": "rg_abordado",       "label": "RG",                  "tipo_campo": "number",   "obrigatorio": true,  "opcoes": null, "ordem": 3 },
    { "id": 4, "nome_campo": "data_abordagem",    "label": "Data da Abordagem",   "tipo_campo": "date",     "obrigatorio": true,  "opcoes": null, "ordem": 4 },
    { "id": 5, "nome_campo": "hora_abordagem",    "label": "Hora da Abordagem",   "tipo_campo": "time",     "obrigatorio": true,  "opcoes": null, "ordem": 5 },
    { "id": 6, "nome_campo": "local_abordagem",   "label": "Local / Endereço",    "tipo_campo": "text",     "obrigatorio": true,  "opcoes": null, "ordem": 6 },
    { "id": 7, "nome_campo": "objetos_apreendidos","label": "Objetos Apreendidos", "tipo_campo": "textarea", "obrigatorio": true,  "opcoes": null, "ordem": 7 },
    { "id": 8, "nome_campo": "situacao_item",     "label": "Situação do Item",    "tipo_campo": "select",   "obrigatorio": true,
      "opcoes": ["Ilícito", "Produto de Furto", "Objeto Suspeito", "Outro"], "ordem": 8 }
  ]
}
```

**Tipos de campo e comportamento no celular:**

| Tipo | Input HTML | Comportamento |
|------|-----------|---------------|
| `text` | `type="text"` | Caps lock automático |
| `number` | `type="tel" inputmode="numeric"` | Teclado numérico |
| `date` | `type="date"` | Seletor de data nativo |
| `time` | `type="time"` | Seletor de hora nativo |
| `textarea` | `<textarea>` | Texto livre multilinha |
| `select` | `<select>` | Lista de opções pré-definidas |
| `checkbox` | `type="checkbox"` | Marcar / não marcar |
| `cpf` | `type="tel"` + máscara | Formata `000.000.000-00` automaticamente |
| `placa` | `type="text"` | Caps lock, máx. 8 chars |

---

## Análise de Segurança

| Vetor de Ataque | Mitigação Implementada |
|-----------------|------------------------|
| Senhas fracas / expostas | Hash **bcrypt** com salt automático e custo adaptativo |
| Sequestro de sessão | **JWT HS256** com expiração de 8h (1 turno), sem refresh token |
| Acesso não autorizado a documentos | Hash único de 64 chars hex (256 bits de entropia) — inviável de adivinhar |
| Injeção SQL | **SQLAlchemy ORM** com parametrização — nenhuma query SQL dinâmica |
| Dados em trânsito | **HTTPS via Cloudflare Tunnel** quando em uso externo |
| Enumeração de usuários | Login retorna mensagem genérica para matrícula e senha incorretos |
| Falsificação de autoria | Nome + matrícula **desnormalizados** na tabela `respostas_formularios` — imutáveis |
| Trilha de auditoria adulterada | Tabela `logs_auditoria` com apenas INSERT — nunca UPDATE ou DELETE |
| Upload malicioso | Validação de extensão `.pdf`, limite de 20 MB, nome de arquivo sanitizado |
| Acesso admin sem autorização | Dependency `get_admin` valida `is_admin=True` em cada endpoint protegido |

### Hardening adicional recomendado para produção

- Gerar `SECRET_KEY` com `python -c "import secrets; print(secrets.token_hex(32))"`
- Substituir SQLite por **PostgreSQL** com `pg_crypto` para criptografia em repouso
- Configurar Cloudflare Tunnel com **Access Policies** (2FA adicional antes de chegar na API)
- Agendar **backup automático** do diretório `storage/` para HD externo ou NAS local

---

## API — Referência de Endpoints

| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| `POST` | `/api/auth/registrar` | Cria cadastro com status `pendente` | Público |
| `POST` | `/api/auth/login` | Autentica e retorna JWT | Público |
| `GET`  | `/api/auth/me` | Dados do usuário autenticado | JWT |
| `GET`  | `/api/auth/status` | Verifica status de aprovação (polling) | JWT |
| `GET`  | `/api/forms/templates` | Lista formulários disponíveis (contrato JSON mobile) | JWT+Ativo |
| `GET`  | `/api/forms/templates/{id}` | Retorna um template específico | JWT+Ativo |
| `POST` | `/api/forms/submeter` | Envia dados → gera PDF + QR Code | JWT+Ativo |
| `GET`  | `/api/forms/meus-formularios` | Histórico do guarda logado (últimos 50) | JWT+Ativo |
| `GET`  | `/download/{hash}` | Redirect 302 → download do PDF | Público |
| `GET`  | `/visualizar/{hash}` | Redirect 302 → página HTML para o cidadão | Público |
| `GET`  | `/api/documents/download/{hash}` | Download direto do PDF | Público |
| `GET`  | `/api/documents/visualizar/{hash}` | Página HTML de visualização | Público |
| `GET`  | `/api/documents/qrcode/{hash}` | Imagem PNG do QR Code | Público |
| `GET`  | `/api/admin/dashboard/stats` | Estatísticas do painel | JWT+Admin |
| `GET`  | `/api/admin/usuarios/pendentes` | Lista aprovações pendentes | JWT+Admin |
| `GET`  | `/api/admin/usuarios` | Lista todos os guardas | JWT+Admin |
| `POST` | `/api/admin/usuarios/aprovar` | Aprova / rejeita / inativa guarda | JWT+Admin |
| `GET`  | `/api/admin/templates` | Lista todos os templates (incl. inativos) | JWT+Admin |
| `POST` | `/api/admin/templates` | Upload de PDF modelo | JWT+Admin |
| `POST` | `/api/admin/templates/{id}/campos` | Salva campos do template | JWT+Admin |
| `DELETE` | `/api/admin/templates/{id}` | Desativa template (soft delete) | JWT+Admin |
| `GET`  | `/api/admin/auditoria` | Log de auditoria (últimos 100) | JWT+Admin |

Documentação Swagger interativa: **http://localhost:8000/api/docs**
