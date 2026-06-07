"""
Serviço de processamento de templates PDF.
Extrai campos preenchíveis usando heurísticas sobre o layout do documento.

Estratégia:
  1. Tenta detectar campos AcroForm nativos (PDFs com campos interativos).
  2. Busca padrões de underscores "____" e linhas após rótulos (PDFs nativos de texto).
  3. Para PDFs escaneados (imagens), aplica OCR com pytesseract como fallback.
"""
import json
import re
from typing import Any, Dict, List

# Importações opcionais — o sistema funciona em modo degradado se não estiverem disponíveis
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

try:
    import pytesseract
    from PIL import Image
    import io
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False


# ---------------------------------------------------------------------------
# Mapeamento de palavras-chave → tipo de campo
# ---------------------------------------------------------------------------
_TIPO_KEYWORDS: List[tuple] = [
    (["data", "dt.", "dt "], "date"),
    (["hora", "horário", "horario", "hr."], "time"),
    (["cpf"], "cpf"),
    (["rg", "identidade", "r.g."], "number"),
    (["placa"], "placa"),
    (["tel", "fone", "celular", "whatsapp"], "number"),
    (["observ", "descric", "descrição", "histórico", "historico", "relato", "ocorrência", "ocorrencia"], "textarea"),
]


def _inferir_tipo(label: str) -> str:
    """Infere o tipo de input baseado no rótulo do campo."""
    label_lower = label.lower()
    for keywords, tipo in _TIPO_KEYWORDS:
        if any(kw in label_lower for kw in keywords):
            return tipo
    return "text"


def _slugify(texto: str) -> str:
    """Converte rótulo para slug válido como nome de campo."""
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto[:50] or "campo"


# ---------------------------------------------------------------------------
# Extração via pdfplumber (PDFs de texto nativo)
# ---------------------------------------------------------------------------

def _extrair_com_pdfplumber(caminho_pdf: str) -> Dict[str, Any]:
    """Detecta campos analisando o layout de texto do PDF."""
    campos = []
    total_paginas = 1
    ordem = 0

    with pdfplumber.open(caminho_pdf) as pdf:
        total_paginas = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words(use_text_flow=True, keep_blank_chars=True)
            texto_pagina = page.extract_text() or ""

            # --- Estratégia 1: Rótulo seguido de underscores ("Nome: _________") ---
            padrao_rotulo_linha = re.compile(
                r"([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú\s/\.\(\)]{2,40}[:;])\s*_{4,}",
                re.UNICODE,
            )
            for match in padrao_rotulo_linha.finditer(texto_pagina):
                rotulo = match.group(1).rstrip(":; ").strip()
                tipo = _inferir_tipo(rotulo)
                campos.append({
                    "nome_campo": _slugify(rotulo),
                    "label": rotulo.title(),
                    "tipo_campo": tipo,
                    "obrigatorio": True,
                    "ordem": ordem,
                    "coordenadas": None,
                })
                ordem += 1

            # --- Estratégia 2: Linha com apenas underscores (campo sem rótulo inline) ---
            linhas = texto_pagina.split("\n")
            for i, linha in enumerate(linhas):
                if re.match(r"^\s*_{6,}\s*$", linha):
                    # Tenta pegar o rótulo da linha anterior
                    rotulo = linhas[i - 1].strip().rstrip(":").strip() if i > 0 else f"Campo {ordem + 1}"
                    rotulo = re.sub(r"_{2,}", "", rotulo).strip()
                    if not rotulo:
                        rotulo = f"Campo {ordem + 1}"
                    tipo = _inferir_tipo(rotulo)
                    # Verifica se já foi adicionado
                    nomes_existentes = {c["nome_campo"] for c in campos}
                    slug = _slugify(rotulo)
                    if slug not in nomes_existentes:
                        campos.append({
                            "nome_campo": slug,
                            "label": rotulo.title(),
                            "tipo_campo": tipo,
                            "obrigatorio": True,
                            "ordem": ordem,
                            "coordenadas": None,
                        })
                        ordem += 1

    # Remove duplicatas por nome_campo
    vistos = set()
    campos_unicos = []
    for c in campos:
        if c["nome_campo"] not in vistos:
            vistos.add(c["nome_campo"])
            campos_unicos.append(c)

    return {"campos": campos_unicos, "total_paginas": total_paginas, "metodo": "pdfplumber"}


# ---------------------------------------------------------------------------
# Extração via PyMuPDF — campos AcroForm nativos
# ---------------------------------------------------------------------------

def _extrair_acroform_pymupdf(caminho_pdf: str) -> Dict[str, Any]:
    """Lê campos interativos do PDF se existirem (AcroForm / Widget annotations)."""
    campos = []
    total_paginas = 1

    doc = fitz.open(caminho_pdf)
    total_paginas = len(doc)
    ordem = 0

    for page_num in range(total_paginas):
        page = doc[page_num]
        for widget in page.widgets():
            nome = widget.field_name or f"campo_{ordem}"
            tipo_fitz = widget.field_type_string.lower()

            tipo_campo = "text"
            if "check" in tipo_fitz:
                tipo_campo = "checkbox"
            elif "combo" in tipo_fitz or "list" in tipo_fitz:
                tipo_campo = "select"

            rect = widget.rect
            campos.append({
                "nome_campo": _slugify(nome),
                "label": nome.replace("_", " ").title(),
                "tipo_campo": tipo_campo,
                "obrigatorio": True,
                "ordem": ordem,
                "coordenadas": {
                    "page": page_num,
                    "x": round(rect.x0, 2),
                    "y": round(rect.y0, 2),
                    "w": round(rect.width, 2),
                    "h": round(rect.height, 2),
                    "font_size": 10,
                },
            })
            ordem += 1
    doc.close()
    return {"campos": campos, "total_paginas": total_paginas, "metodo": "acroform"}


# ---------------------------------------------------------------------------
# Extração via OCR (fallback para PDFs escaneados)
# ---------------------------------------------------------------------------

def _extrair_com_ocr(caminho_pdf: str) -> Dict[str, Any]:
    """Usa pytesseract para detectar campos em PDFs escaneados."""
    if not _HAS_PYMUPDF:
        return {"campos": [], "total_paginas": 1, "metodo": "ocr_sem_pymupdf"}

    doc = fitz.open(caminho_pdf)
    total_paginas = len(doc)
    campos = []
    ordem = 0
    texto_completo = ""

    for page_num in range(total_paginas):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        texto_pagina = pytesseract.image_to_string(img, lang="por")
        texto_completo += texto_pagina + "\n"

    doc.close()

    # Reutiliza a lógica de detecção de padrões do pdfplumber
    padrao = re.compile(
        r"([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú\s/\.\(\)]{2,40}[:;])\s*_{3,}",
        re.UNICODE,
    )
    for match in padrao.finditer(texto_completo):
        rotulo = match.group(1).rstrip(":; ").strip()
        campos.append({
            "nome_campo": _slugify(rotulo),
            "label": rotulo.title(),
            "tipo_campo": _inferir_tipo(rotulo),
            "obrigatorio": True,
            "ordem": ordem,
            "coordenadas": None,
        })
        ordem += 1

    vistos = set()
    campos_unicos = [c for c in campos if c["nome_campo"] not in vistos and not vistos.add(c["nome_campo"])]
    return {"campos": campos_unicos, "total_paginas": total_paginas, "metodo": "ocr"}


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def processar_template_pdf(caminho_pdf: str) -> Dict[str, Any]:
    """
    Tenta extrair campos do PDF usando a melhor estratégia disponível:
    1. AcroForm (PyMuPDF) — mais preciso para PDFs com campos interativos.
    2. pdfplumber — para PDFs de texto nativo com underscores.
    3. OCR (pytesseract) — para PDFs escaneados.
    4. Retorna lista vazia se nenhuma biblioteca estiver disponível
       (admin define campos manualmente no painel).
    """
    # Tenta AcroForm primeiro
    if _HAS_PYMUPDF:
        try:
            resultado = _extrair_acroform_pymupdf(caminho_pdf)
            if resultado["campos"]:
                return resultado
        except Exception:
            pass

    # Tenta pdfplumber
    if _HAS_PDFPLUMBER:
        try:
            resultado = _extrair_com_pdfplumber(caminho_pdf)
            if resultado["campos"]:
                return resultado
        except Exception:
            pass

    # Fallback OCR
    if _HAS_OCR:
        try:
            return _extrair_com_ocr(caminho_pdf)
        except Exception:
            pass

    # Nenhuma biblioteca disponível — admin precisa definir campos manualmente
    total = 1
    if _HAS_PYMUPDF:
        try:
            doc = fitz.open(caminho_pdf)
            total = len(doc)
            doc.close()
        except Exception:
            pass

    return {"campos": [], "total_paginas": total, "metodo": "manual"}
