"""Cria atalhos Windows para o voice-macro com ícone do dragão.

Os atalhos apontam para pythonw.exe (sem janela de console) e carregam
o ícone gerado em assets/icons/voice-macro.ico, tornando-os fixáveis
na barra de tarefas via clique direito → "Fixar na barra de tarefas".

Uso direto (normalmente chamado pelo setup.bat):
    python scripts/create_shortcut.py              # Desktop + Menu Iniciar
    python scripts/create_shortcut.py --desktop
    python scripts/create_shortcut.py --startmenu
"""
import sys
import os
import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHONW      = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
MAIN_PY      = PROJECT_ROOT / "main.py"
ICO          = PROJECT_ROOT / "assets" / "icons" / "voice-macro.ico"


def _ensure_ico() -> bool:
    """Gera o voice-macro.ico se ainda não existir."""
    if ICO.exists():
        return True
    print("  Gerando ícone (primeira execução)...")
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from app.tray.tray_icon import _build_icon_cache, _save_icon_cache
        icons = _build_icon_cache(PROJECT_ROOT)
        _save_icon_cache(icons, PROJECT_ROOT)
        return ICO.exists()
    except Exception as e:
        print(f"  AVISO: não foi possível gerar o ícone ({e})")
        return False


def _create_lnk(shortcut_path: Path) -> None:
    """Cria um atalho .lnk via WScript.Shell (sem dependências extras)."""
    ps = (
        f'$s = (New-Object -COM WScript.Shell).CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{PYTHONW}"; '
        f'$s.Arguments = \'"{MAIN_PY}"\'; '
        f'$s.IconLocation = "{ICO}"; '
        f'$s.WorkingDirectory = "{PROJECT_ROOT}"; '
        f'$s.Description = "voice-macro — Push-to-talk voice-to-text"; '
        f'$s.Save()'
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, timeout=15,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "Falha no PowerShell")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria atalhos do voice-macro")
    parser.add_argument("--desktop",   action="store_true")
    parser.add_argument("--startmenu", action="store_true")
    args   = parser.parse_args()

    both         = not args.desktop and not args.startmenu
    do_desktop   = args.desktop   or both
    do_startmenu = args.startmenu or both

    if not PYTHONW.exists():
        print(f"ERRO: venv não encontrado em {PYTHONW}")
        print("Execute: python -m venv .venv  e depois  pip install -r requirements.txt")
        sys.exit(1)

    _ensure_ico()

    if not ICO.exists():
        print("ERRO: ícone não encontrado — execute o app uma vez antes do setup.")
        sys.exit(1)

    created: list[Path] = []

    if do_desktop:
        path = Path(os.path.expandvars("%USERPROFILE%")) / "Desktop" / "voice-macro.lnk"
        _create_lnk(path)
        created.append(path)

    if do_startmenu:
        path = (
            Path(os.path.expandvars("%APPDATA%"))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / "voice-macro.lnk"
        )
        _create_lnk(path)
        created.append(path)

    for p in created:
        print(f"  ✓  {p}")

    if do_startmenu or both:
        print()
        print("  Para fixar na barra de tarefas:")
        print("    1. Win+S → digite 'voice-macro'")
        print("    2. Clique direito → 'Fixar na barra de tarefas'")
        print("    (ou arraste o atalho do Desktop para a barra)")


if __name__ == "__main__":
    main()
