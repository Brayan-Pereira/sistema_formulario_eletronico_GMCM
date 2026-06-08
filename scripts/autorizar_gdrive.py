"""
Script de autorização OAuth 2.0 do Google Drive.
Execute UMA VEZ para gerar o arquivo secrets/gdrive_token.json.

Pré-requisitos:
  1. No Google Cloud Console, vá em APIs e Serviços → Credenciais
  2. Clique em "Criar Credenciais" → "ID do cliente OAuth 2.0"
  3. Tipo de aplicativo: "Aplicativo de computador" (Desktop app)
  4. Baixe o JSON e salve em: secrets/gdrive_oauth_client.json
  5. Execute este script: python scripts/autorizar_gdrive.py

Ao final, será criado: secrets/gdrive_token.json
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

CLIENT_FILE = os.path.join(os.path.dirname(__file__), "..", "secrets", "gdrive_oauth_client.json")
TOKEN_FILE  = os.path.join(os.path.dirname(__file__), "..", "secrets", "gdrive_token.json")
SCOPES      = ["https://www.googleapis.com/auth/drive.file"]

def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        import json
    except ImportError:
        print("[ERRO] Instale: pip install google-auth-oauthlib")
        sys.exit(1)

    client_path = os.path.abspath(CLIENT_FILE)
    token_path  = os.path.abspath(TOKEN_FILE)

    if not os.path.exists(client_path):
        print(f"\n[ERRO] Arquivo não encontrado: {client_path}")
        print("\nPassos:")
        print("  1. Acesse https://console.cloud.google.com")
        print("  2. APIs e Serviços → Credenciais → Criar Credenciais")
        print("  3. Escolha 'ID do cliente OAuth 2.0'")
        print("  4. Tipo: 'Aplicativo de computador' (Desktop app)")
        print("  5. Baixe o JSON e salve em: secrets/gdrive_oauth_client.json")
        sys.exit(1)

    creds = None

    # Reutiliza token existente se ainda válido
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            print("Token renovado automaticamente.")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_path, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
            print("\nAutorização concedida!")

        # Salva o token para uso futuro
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        print(f"Token salvo em: {token_path}")

    # Teste rápido de conexão
    from googleapiclient.discovery import build
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    about = svc.about().get(fields="user,storageQuota").execute()
    print(f"\nConectado como: {about['user']['emailAddress']}")
    quota = about.get("storageQuota", {})
    usado = int(quota.get("usage", 0)) // (1024 * 1024)
    total = int(quota.get("limit", 0)) // (1024 * 1024 * 1024)
    print(f"Armazenamento: {usado} MB usados / {total} GB total")
    print("\n✓ Configuração concluída! O sistema já pode usar o Google Drive.")


if __name__ == "__main__":
    main()
