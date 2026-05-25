#!/usr/bin/env python3
"""Cria atalhos Windows para o voice-macro, permitindo fixar na barra de tarefas.

O atalho aponta para pythonw.exe + main.py e usa o ícone voice-macro.ico,
tornando-o "pinável" na taskbar do Windows via clique direito → Fixar.

Pré-requisito: execute o app uma vez para gerar assets/icons/voice-macro.ico
    .venv\\Scripts\\pythonw.exe main.py   (e feche pelo menu da tray)

Uso:
    python scripts/create_shortcut.py               # Desktop + Start Menu
    python scripts/create_shortcut.py --desktop
    python scripts/create_shortcut.py --startmenu
"""
import sys
import os
import argparse
import subprocess
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def create_lnk(
    target: Path,
    icon_path: Path,
    shortcut_path: Path,
    arguments: str = "",
    start_in: Path | None = None,
) -> None:
    """Cria um atalho .lnk via WScript.Shell (PowerShell, sem dependências extras)."""
    work_dir = str(start_in or target.parent)
    ps = (
        f'$s = (New-Object -COM WScript.Shell).CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{target}"; '
        f'$s.Arguments = \'{arguments}\'; '
        f'$s.IconLocation = "{icon_path}"; '
        f'$s.WorkingDirectory = "{work_dir}"; '
        f'$s.Description = "voice-macro — Push-to-talk voice-to-text"; '
        f'$s.Save()'
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Falha ao criar atalho via PowerShell")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria atalhos do voice-macro para fixar na barra de tarefas"
    )
    parser.add_argument("--desktop",   action="store_true", help="Apenas Desktop")
    parser.add_argument("--startmenu", action="store_true", help="Apenas Menu Iniciar")
    args = parser.parse_args()

    both         = not args.desktop and not args.startmenu
    do_desktop   = args.desktop   or both
    do_startmenu = args.startmenu or both

    root    = get_project_root()
    python  = root / ".venv" / "Scripts" / "pythonw.exe"
    main_py = root / "main.py"
    ico     = root / "assets" / "icons" / "voice-macro.ico"

    # ── Validações ────────────────────────────────────────────────────────────
    if not python.exists():
        print(f"ERRO: venv não encontrado em {python}")
        print("Execute: python -m venv .venv  e depois  pip install -r requirements.txt")
        sys.exit(1)

    if not ico.exists():
        print("ERRO: voice-macro.ico não encontrado.")
        print("Inicie o app uma vez para gerar os assets de ícone:")
        print(f"  {python} {main_py}")
        print("(pode fechar pela tray logo em seguida)")
        sys.exit(1)

    # ── Criação dos atalhos ───────────────────────────────────────────────────
    arguments = f'"{main_py}"'
    created: list[Path] = []

    if do_desktop:
        desktop  = Path(os.path.expandvars("%USERPROFILE%")) / "Desktop"
        shortcut = desktop / "voice-macro.lnk"
        create_lnk(python, ico, shortcut, arguments=arguments, start_in=root)
        created.append(shortcut)

    if do_startmenu:
        programs = (
            Path(os.path.expandvars("%APPDATA%"))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )
        shortcut = programs / "voice-macro.lnk"
        create_lnk(python, ico, shortcut, arguments=arguments, start_in=root)
        created.append(shortcut)

    for s in created:
        print(f"✓  Atalho criado: {s}")

    if do_startmenu or both:
        print()
        print("Para fixar na barra de tarefas:")
        print("  1. Pressione Win+S e digite 'voice-macro'")
        print("  2. Clique direito no resultado → 'Fixar na barra de tarefas'")
        print()
        print("Ou arraste o atalho do Desktop diretamente para a barra de tarefas.")


if __name__ == "__main__":
    main()
