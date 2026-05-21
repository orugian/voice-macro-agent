"""Setup guiado para novos usuários do voice-macro.

Executa com Python do sistema (não do venv):
    python scripts/setup.py

O que faz:
    1. Verifica Python 3.11+
    2. Cria o ambiente virtual .venv (se não existir)
    3. Instala requirements.txt
    4. Cria .env (solicita a chave OpenRouter se necessário)
    5. Valida CUDA e faster-whisper
"""
import sys
import getpass
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


def step(n: int, msg: str) -> None:
    print(f"\n[{n}/5] {msg}")
    print("-" * 50)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"\nERRO: comando falhou com código {result.returncode}")
        sys.exit(result.returncode)
    return result


def main() -> None:
    print("=" * 50)
    print(" voice-macro — Setup")
    print("=" * 50)

    # 1. Verificar Python 3.11+
    step(1, "Verificando versão do Python")
    major, minor = sys.version_info[:2]
    print(f"  Python {major}.{minor} detectado")
    if (major, minor) < (3, 11):
        print(f"ERRO: Python 3.11+ necessário. Versão atual: {major}.{minor}")
        sys.exit(1)
    print("  OK")

    # 2. Criar .venv
    step(2, "Criando ambiente virtual (.venv)")
    venv_dir = ROOT / ".venv"
    if venv_dir.exists():
        print("  .venv já existe — pulando criação")
    else:
        run([sys.executable, "-m", "venv", str(venv_dir)])
        print("  .venv criado")

    # 3. Instalar dependências
    step(3, "Instalando dependências (requirements.txt)")
    pip = venv_dir / "Scripts" / "pip.exe"
    run([str(pip), "install", "-r", str(ROOT / "requirements.txt")])
    print("  Dependências instaladas")

    # 4. Criar .env
    step(4, "Configurando chave de API (.env)")
    env_path = ROOT / ".env"
    if env_path.exists():
        print("  .env já existe — pulando")
    else:
        print("  Para usar modos com LLM (CLEAN, SUMMARY, etc.),")
        print("  você precisa de uma chave OpenRouter.")
        print("  Obtenha em: https://openrouter.ai/keys")
        key = getpass.getpass("\n  Cole sua OPENROUTER_API_KEY (Enter para pular, Ctrl+C para cancelar): ").strip()
        if key:
            env_path.write_text(f"OPENROUTER_API_KEY={key}\n", encoding="utf-8")
            print("  .env criado com a chave")
        else:
            print("  Pulado — somente o modo DICTATE estará disponível")

    # 5. Validar CUDA
    step(5, "Validando CUDA e faster-whisper")
    validate_script = ROOT / "scripts" / "validate_cuda.py"
    if validate_script.exists():
        python_venv = venv_dir / "Scripts" / "python.exe"
        result = subprocess.run(
            [str(python_venv), str(validate_script)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout)
            print("  CUDA OK")
        else:
            print("  AVISO: validação CUDA falhou. Saída:")
            print(result.stdout)
            print(result.stderr)
            print("  Consulte docs/PLAN.md → seção Troubleshooting CUDA")
    else:
        print("  scripts/validate_cuda.py não encontrado — pulando")

    print()
    print("=" * 50)
    print(" Setup concluído!")
    print("=" * 50)
    print()
    print("Para iniciar o voice-macro:")
    print(f"  .venv\\Scripts\\python.exe main.py")
    print()
    print("Ou dê duplo-clique em: launch.bat")
    print()
    print("Auto-start no Windows:")
    print("  .venv\\Scripts\\python.exe scripts/setup_windows_startup.py")


if __name__ == "__main__":
    main()
