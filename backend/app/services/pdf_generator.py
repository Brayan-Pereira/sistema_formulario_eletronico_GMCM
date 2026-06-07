"""
Serviço de geração do PDF preenchido.

Estratégia:
  - Usa PyMuPDF (fitz) para sobrepor texto nas coordenadas armazenadas.
  - Se não houver coordenadas (template sem mapeamento), gera um PDF de
    texto formatado via reportlab como fallback.
  - Adiciona rodapé de autoria em todas as páginas (cadeia de custódia).
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import settings

try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


# ---------------------------------------------------------------------------
# Gerar PDF com sobreposição (PyMuPDF)
# ---------------------------------------------------------------------------

def _gerar_com_overlay(
    template_path: str,
    campos: list,
    dados: Dict[str, Any],
    output_path: str,
    nome_guarda: str,
    matricula_guarda: str,
) -> str:
    """Abre o template PDF e insere os dados nas coordenadas mapeadas."""
    doc = fitz.open(template_path)

    campos_por_nome = {c.nome_campo: c for c in campos}

    for nome_campo, valor in dados.items():
        if nome_campo.startswith("__"):
            continue  # Metadados internos
        campo = campos_por_nome.get(nome_campo)
        if not campo or not campo.coordenadas_pdf:
            continue

        try:
            coords = json.loads(campo.coordenadas_pdf)
        except Exception:
            continue

        pagina_num = coords.get("page", 0)
        if pagina_num >= len(doc):
            continue

        page = doc[pagina_num]
        x = coords.get("x", 50)
        y = coords.get("y", 50)
        font_size = coords.get("font_size", 10)

        # Insere o texto na posição correta
        page.insert_text(
            fitz.Point(x, y),
            str(valor).upper(),
            fontsize=font_size,
            color=(0, 0, 0),
            fontname="helv",
        )

    # Rodapé de autoria em todas as páginas
    _inserir_rodape(doc, nome_guarda, matricula_guarda)

    doc.save(output_path)
    doc.close()
    return output_path


def _inserir_rodape(doc, nome_guarda: str, matricula_guarda: str):
    """Insere rodapé de autoria e data em todas as páginas do documento."""
    texto_rodape = (
        f"Documento emitido por: {nome_guarda} | Mat.: {matricula_guarda} | "
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Sistema Guarda Municipal"
    )
    for page in doc:
        rect = page.rect
        # Retângulo no rodapé
        footer_rect = fitz.Rect(10, rect.height - 20, rect.width - 10, rect.height - 5)
        page.draw_rect(footer_rect, color=(0.9, 0.9, 0.9), fill=(0.96, 0.96, 0.96))
        page.insert_textbox(
            footer_rect,
            texto_rodape,
            fontsize=6,
            color=(0.3, 0.3, 0.3),
            fontname="helv",
            align=fitz.TEXT_ALIGN_CENTER,
        )


# ---------------------------------------------------------------------------
# Gerar PDF formatado (reportlab — sem coordenadas)
# ---------------------------------------------------------------------------

def _gerar_com_reportlab(
    nome_documento: str,
    campos: list,
    dados: Dict[str, Any],
    output_path: str,
    nome_guarda: str,
    matricula_guarda: str,
) -> str:
    """
    Gera um PDF formatado quando não há coordenadas mapeadas no template.
    Cria um documento estruturado com os dados preenchidos.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )
    estilos = getSampleStyleSheet()

    # Estilos personalizados
    titulo_style = ParagraphStyle(
        "Titulo",
        parent=estilos["Title"],
        fontSize=14,
        textColor=colors.HexColor("#1a3a6b"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    subtitulo_style = ParagraphStyle(
        "Subtitulo",
        parent=estilos["Normal"],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=estilos["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#555555"),
        spaceBefore=6,
    )
    valor_style = ParagraphStyle(
        "Valor",
        parent=estilos["Normal"],
        fontSize=11,
        textColor=colors.black,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    rodape_style = ParagraphStyle(
        "Rodape",
        parent=estilos["Normal"],
        fontSize=7,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )

    elementos = []

    # Cabeçalho institucional
    elementos.append(Paragraph("GUARDA MUNICIPAL", titulo_style))
    elementos.append(Paragraph(nome_documento.upper(), titulo_style))
    elementos.append(Paragraph(
        f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        subtitulo_style,
    ))
    elementos.append(Spacer(1, 6 * mm))

    # Linha separadora
    elementos.append(Table(
        [[""]],
        colWidths=[170 * mm],
        style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#1a3a6b"))]),
    ))
    elementos.append(Spacer(1, 4 * mm))

    # Campos preenchidos
    campos_por_nome = {c.nome_campo: c for c in campos}
    for campo in sorted(campos, key=lambda c: c.ordem):
        valor = dados.get(campo.nome_campo, "")
        if not valor or str(valor).startswith("__"):
            continue
        elementos.append(Paragraph(campo.label.upper(), label_style))
        elementos.append(Paragraph(str(valor).upper(), valor_style))

    elementos.append(Spacer(1, 8 * mm))

    # Tabela de autoria
    data_autoria = [
        ["Guarda Responsável", "Matrícula", "Data/Hora"],
        [nome_guarda.upper(), matricula_guarda.upper(), datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]
    tabela_autoria = Table(
        data_autoria,
        colWidths=[80 * mm, 45 * mm, 45 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke]),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    elementos.append(tabela_autoria)
    elementos.append(Spacer(1, 6 * mm))
    elementos.append(Paragraph(
        "Documento gerado eletronicamente pelo Sistema de Formulários da Guarda Municipal. "
        "Verifique a autenticidade pelo QR Code.",
        rodape_style,
    ))

    doc.build(elementos)
    return output_path


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def gerar_pdf_preenchido(
    template_path: str,
    campos: list,
    dados: Dict[str, Any],
    token_hash: str,
    nome_guarda: str,
    matricula_guarda: str,
) -> str:
    """
    Gera o PDF final preenchido e retorna o caminho do arquivo salvo.
    Usa overlay se houver coordenadas; caso contrário, usa reportlab.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"{timestamp}_{token_hash[:8]}.pdf"
    output_path = os.path.join(settings.GENERATED_DIR, nome_arquivo)

    # Verifica se algum campo tem coordenadas mapeadas
    tem_coordenadas = any(
        c.coordenadas_pdf for c in campos if not c.nome_campo.startswith("__")
    )

    if tem_coordenadas and _HAS_PYMUPDF:
        try:
            return _gerar_com_overlay(
                template_path=template_path,
                campos=campos,
                dados=dados,
                output_path=output_path,
                nome_guarda=nome_guarda,
                matricula_guarda=matricula_guarda,
            )
        except Exception as e:
            # Fallback para reportlab se overlay falhar
            pass

    if _HAS_REPORTLAB:
        # Descobre o nome do documento pelo template
        nome_documento = os.path.basename(template_path).replace("_", " ").replace(".pdf", "")
        return _gerar_com_reportlab(
            nome_documento=nome_documento,
            campos=campos,
            dados=dados,
            output_path=output_path,
            nome_guarda=nome_guarda,
            matricula_guarda=matricula_guarda,
        )

    raise RuntimeError(
        "Nenhuma biblioteca de PDF disponível. "
        "Instale PyMuPDF (pymupdf) ou reportlab: pip install pymupdf reportlab"
    )
