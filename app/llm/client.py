import time
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_RETRIES = 3


class LLMClient:
    def __init__(self, config: dict):
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config["llm"]["api_key"],
        )
        self._model = config["llm"]["model"]
        self._max_tokens = config["llm"]["max_tokens"]
        self._temperature = config["llm"]["temperature"]
        logger.info(f"LLM client ready: {self._model}")

    def process(self, system_prompt: str, text: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": text},
                    ],
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    timeout=_TIMEOUT,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_exc = e
                if attempt < _RETRIES - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(f"LLM attempt {attempt + 1}/{_RETRIES} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
        raise last_exc
