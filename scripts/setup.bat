@echo off
chcp 65001 >nul
title Guarda Municipal — Setup

echo.
echo ============================================================
echo   SISTEMA DE FORMULARIOS ELETRONICOS — GUARDA MUNICIPAL
echo   Setup Inicial
echo ============================================================
echo.

:: Verifica se Python está instalado
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo        Instale o Python 3.11+ em https://python.org
    echo        Marque "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [1/4] Python encontrado.

:: Navega para a raiz do projeto
cd /d "%~dp0.."
echo [2/4] Diretorio do projeto: %CD%

:: Cria e ativa ambiente virtual
if not exist ".venv" (
    echo [3/4] Criando ambiente virtual Python...
    py -m venv .venv
) else (
    echo [3/4] Ambiente virtual ja existe.
)

:: Ativa o venv
call .venv\Scripts\activate.bat

:: Instala dependências
echo [4/4] Instalando dependencias (pode demorar alguns minutos)...
pip install --upgrade pip --quiet
pip install -r backend\requirements.txt

echo.
echo [5/5] Criando banco de dados e usuario administrador...
py scripts\setup_admin.py

echo.
echo ============================================================
echo   SETUP CONCLUIDO! Execute start.bat para iniciar.
echo ============================================================
echo.
pause
