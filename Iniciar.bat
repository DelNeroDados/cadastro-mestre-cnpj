@echo off
rem ==================================================================
rem  Cadastro mestre de empresas (CNPJ) - inicializador para Windows
rem
rem  Dois cliques: roda a demonstracao (base sintetica, sem internet)
rem  e abre o relatorio de qualidade no navegador.
rem
rem  Iniciar.bat real    -> roda com os cartoes reais das pastas
rem                         extracted_cnpjs e no_extracted_cnpjs
rem  Iniciar.bat testes  -> roda os testes automatizados
rem ==================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Cadastro mestre de empresas (CNPJ)

rem ---------- Python ----------
set "PY="
if exist "%~dp0..\.python_embed\python.exe" set "PY="%~dp0..\.python_embed\python.exe""
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY goto :sem_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto :sem_python

rem ---------- Bibliotecas ----------
%PY% -c "import pandas, yaml, rapidfuzz, jinja2, pdfplumber, requests, pytest" >nul 2>nul
if errorlevel 1 (
    echo Instalando as bibliotecas, so acontece na primeira vez...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 goto :erro
)

if /i "%~1"=="testes" (
    %PY% -m pytest tests -q -p no:cacheprovider
    pause
    exit /b
)
if /i "%~1"=="real" (
    %PY% executar.py real --pdfs extracted_cnpjs no_extracted_cnpjs
    if errorlevel 1 goto :erro
    start "" "saida_real\relatorio_qualidade.html"
    pause
    exit /b 0
)

%PY% executar.py demo
if errorlevel 1 goto :erro
start "" "saida_demo\relatorio_qualidade.html"
pause
exit /b 0

:erro
echo.
echo [erro] Algo deu errado. Veja a mensagem acima.
pause
exit /b 1

:sem_python
echo.
echo [erro] Nao encontrei o Python 3.10 ou mais novo.
echo Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
pause
exit /b 1
