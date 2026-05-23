import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_PROMPT_FILES = {
    "CLEAN":    "clean.txt",
    "SUMMARY":  "summary.txt",
    "INSTRUCT": "instruct.txt",
    "REFINE":   "refine.txt",
    "ACTION":   "action.txt",
    "PLAN":     "plan.txt",
}

_cache: dict[str, str] = {}


def _load_prompt(mode: str) -> str:
    if mode not in _cache:
        path = _PROMPTS_DIR / _PROMPT_FILES[mode]
        _cache[mode] = path.read_text(encoding="utf-8")
    return _cache[mode]


def process(mode: str, text: str, llm_client) -> str:
    if mode == "DICTATE":
        return text
    if mode not in _PROMPT_FILES:
        logger.warning(f"Unknown mode '{mode}' — falling back to DICTATE")
        return text
    prompt = _load_prompt(mode)
    return llm_client.process(prompt, text)
