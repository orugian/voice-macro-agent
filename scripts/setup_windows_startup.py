"""Configura voice-macro para iniciar automaticamente com o Windows.

Cria um .bat na pasta Startup do usuário que executa o app sem janela de console.

Uso:
    python scripts/setup_windows_startup.py           # instalar
    python scripts/setup_windows_startup.py --remove  # remover
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PYTHONW = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
MAIN_PY = PROJECT_ROOT / "main.py"
STARTUP_FOLDER = (
    Path(os.environ["APPDATA"])
    / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
)
BAT_PATH = STARTUP_FOLDER / "voice-macro.bat"


def _check_env() -> bool:
    if not PYTHONW.exists():
        print(f"ERRO: pythonw.exe não encontrado em {PYTHONW}")
        print("Execute scripts/setup.py primeiro para criar o ambiente virtual.")
        return False
    return True


def install() -> None:
    if not _check_env():
        sys.exit(1)

    # pythonw.exe = Python sem janela de console (ideal para auto-start)
    content = (
        f'@echo off\n'
        f'cd /d "{PROJECT_ROOT}"\n'
        f'"{PYTHONW}" "{MAIN_PY}"\n'
    )
    BAT_PATH.write_text(content, encoding="utf-8")
    print(f"Startup configurado: {BAT_PATH}")
    print("voice-macro iniciará automaticamente no próximo login do Windows.")
    print()
    print("Para remover: python scripts/setup_windows_startup.py --remove")


def uninstall() -> None:
    if BAT_PATH.exists():
        BAT_PATH.unlink()
        print(f"Startup removido: {BAT_PATH}")
    else:
        print("Nenhum startup configurado (arquivo não encontrado).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        uninstall()
    else:
        install()
