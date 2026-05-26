@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  ============================================================
echo   voice-macro — Setup
echo  ============================================================
echo.

:: ── 1. Verifica o venv ───────────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo  ERRO: ambiente virtual nao encontrado.
    echo.
    echo  Execute primeiro:
    echo    python -m venv .venv
    echo    .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

set PYTHON=.venv\Scripts\python.exe
set PYTHONW=.venv\Scripts\pythonw.exe

:: ── 2. Gera o icone (.ico) se ainda nao existir ──────────────────────────────
if not exist "assets\icons\voice-macro.ico" (
    echo  Gerando icone do dragao...
    "%PYTHON%" -c "import sys; sys.path.insert(0,'.');from app.tray.tray_icon import _build_icon_cache,_save_icon_cache;from pathlib import Path;icons=_build_icon_cache(Path('.'));_save_icon_cache(icons,Path('.'))"
    if errorlevel 1 (
        echo  AVISO: nao foi possivel gerar o icone automaticamente.
        echo         Execute o app uma vez antes de rodar o setup novamente.
    ) else (
        echo  Icone gerado com sucesso.
    )
) else (
    echo  Icone ja existe — pulando geracao.
)

echo.

:: ── 3. Cria atalhos no Desktop e no Menu Iniciar ────────────────────────────
echo  Criando atalhos...
"%PYTHON%" scripts\create_shortcut.py
if errorlevel 1 (
    echo  ERRO ao criar atalhos. Verifique se o ambiente virtual esta correto.
    echo.
    pause
    exit /b 1
)

echo.

:: ── 4. Configura inicializacao automatica com o Windows ─────────────────────
echo  Configurando inicio automatico com o Windows...
"%PYTHON%" scripts\setup_windows_startup.py
if errorlevel 1 (
    echo  AVISO: nao foi possivel configurar o inicio automatico.
)

echo.
echo  ============================================================
echo   Setup concluido!
echo.
echo   Para usar:
echo     - Clique duas vezes em "voice-macro" no Desktop, ou
echo     - Win+S, digite "voice-macro" e pressione Enter.
echo.
echo   Para fixar na barra de tarefas:
echo     - Win+S, digite "voice-macro"
echo     - Clique direito -> "Fixar na barra de tarefas"
echo.
echo   O app iniciara automaticamente no proximo login do Windows.
echo  ============================================================
echo.
pause
