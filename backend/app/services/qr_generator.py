"""
Serviço de geração de QR Codes.
O QR Code aponta para a URL pública de visualização/download do documento.
"""
import os

from ..config import settings

try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
    _HAS_QRCODE = True
except ImportError:
    _HAS_QRCODE = False


def gerar_qrcode(url: str, token_hash: str) -> str:
    """
    Gera um QR Code PNG para a URL fornecida.
    Retorna o caminho absoluto do arquivo PNG salvo.
    """
    if not _HAS_QRCODE:
        raise RuntimeError(
            "Biblioteca 'qrcode' não instalada. Execute: pip install qrcode[pil]"
        )

    nome_arquivo = f"qr_{token_hash[:16]}.png"
    caminho_saida = os.path.join(settings.QRCODES_DIR, nome_arquivo)

    qr = qrcode.QRCode(
        version=None,             # Auto-detecta tamanho mínimo
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Alta correção de erro
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a3a6b", back_color="white")
    img.save(caminho_saida)

    return caminho_saida
