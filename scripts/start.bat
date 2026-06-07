@echo off
chcp 65001 >nul
title Guarda Municipal — Servidor

echo.
echo ============================================================
echo   SISTEMA DE FORMULARIOS ELETRONICOS — GUARDA MUNICIPAL
echo   Iniciando Servidor Local
echo ============================================================
echo.

cd /d "%~dp0.."

:: Ativa o ambiente virtual
if not exist ".venv\Scripts\activate.bat" (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo        Execute setup.bat primeiro!
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

:: Verifica se o arquivo .env existe
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado.
    echo         Copiando .env.example para .env...
    copy .env.example .env >nul
    echo         Edite o arquivo .env antes de usar em producao!
    echo.
)

:: Lê a porta do .env (padrão 8000)
set PORT=8000
for /f "tokens=2 delims==" %%a in ('findstr /i "^PORT=" .env 2^>nul') do set PORT=%%a

echo [INFO] Servidor iniciando na porta %PORT%...
echo [INFO] Acesso local:    http://localhost:%PORT%
echo [INFO] Documentacao API: http://localhost:%PORT%/api/docs
echo.
echo Para acesso externo via Cloudflare Tunnel:
echo   Execute em outro terminal: cloudflared tunnel --url http://localhost:%PORT%
echo.
echo Pressione CTRL+C para encerrar o servidor.
echo ============================================================
echo.

:: Inicia o servidor FastAPI com uvicorn
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port %PORT% --reload --log-level info

pause
