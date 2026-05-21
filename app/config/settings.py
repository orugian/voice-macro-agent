import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent.parent


def load_config() -> dict:
    config_path = ROOT / "config.toml"
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    cfg["llm"]["api_key"] = os.getenv("OPENROUTER_API_KEY", "")
    return cfg


CONFIG = load_config()
