"""
Script de configuração inicial do sistema.
Cria o banco de dados, todas as tabelas e o primeiro usuário administrador.
Execute apenas uma vez: python scripts/setup_admin.py
"""
import sys
import os

# Adiciona o diretório raiz ao path para importar os módulos do app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Usuario, StatusAprovacao
from backend.app.auth import hash_senha
from backend.app.config import settings


def setup():
    print("=" * 55)
    print("  SISTEMA GUARDA MUNICIPAL — SETUP INICIAL")
    print("=" * 55)

    # 1. Cria todas as tabelas
    print("\n[1/3] Criando estrutura do banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("      ✓ Tabelas criadas.")

    # 2. Verifica se já existe um admin
    db = SessionLocal()
    try:
        admin_existente = db.query(Usuario).filter(
            Usuario.matricula == settings.ADMIN_MATRICULA.upper()
        ).first()

        if admin_existente:
            print(f"\n[2/3] Administrador já cadastrado: {admin_existente.matricula}")
            print("      ✓ Nenhuma alteração necessária.")
        else:
            print("\n[2/3] Criando conta de Administrador...")
            admin = Usuario(
                nome="Administrador",
                matricula=settings.ADMIN_MATRICULA.upper(),
                equipe="Administração",
                senha_hash=hash_senha(settings.ADMIN_SENHA),
                status_aprovacao=StatusAprovacao.ativo,
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            print(f"      ✓ Admin criado: {settings.ADMIN_MATRICULA.upper()}")
            print(f"      ✓ Senha inicial: {settings.ADMIN_SENHA}")
            print("      ⚠  TROQUE A SENHA imediatamente após o primeiro login!")

        # 3. Verifica diretórios de armazenamento
        print("\n[3/3] Verificando diretórios de armazenamento...")
        for d in [settings.TEMPLATES_DIR, settings.GENERATED_DIR, settings.QRCODES_DIR]:
            os.makedirs(d, exist_ok=True)
            print(f"      ✓ {d}")

        print("\n" + "=" * 55)
        print("  SETUP CONCLUÍDO COM SUCESSO!")
        print("=" * 55)
        print(f"\n  Matrícula Admin: {settings.ADMIN_MATRICULA.upper()}")
        print(f"  Senha Admin:     {settings.ADMIN_SENHA}")
        print(f"\n  Para iniciar o servidor: scripts\\start.bat")
        print("=" * 55)

    finally:
        db.close()


if __name__ == "__main__":
    setup()
