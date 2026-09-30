from typing import List, Optional, Tuple
import random

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from loguru import logger
from openai import AsyncOpenAI

from src.services.llm.const.list_models import GEMINI_MODELS
from src.settings.config import APPLICATION


OPENAI_COMPATIBLE_DEFAULTS = {
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "grok": ("https://api.x.ai/v1", "grok-3-mini"),
}
OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "openai-compatible",
    "openai_compatible",
    "compatible",
    "groq",
    "grok",
}


class LLModel:
    """Provider-agnostic LLM client for Gemini and OpenAI-compatible APIs."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        top_p: float = 1.0,
        top_k: int = 30,
        max_output_tokens: int = 1024 * 20,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = (
            provider or APPLICATION.get("llm_provider") or "gemini"
        ).strip().lower()
        default_base_url, default_model = OPENAI_COMPATIBLE_DEFAULTS.get(
            self.provider, (None, None)
        )
        self.base_url = base_url or APPLICATION.get("llm_base_url") or default_base_url
        self.model_name = (
            model_name
            or APPLICATION.get("llm_model")
            or default_model
            or GEMINI_MODELS["GEMINI_2_5_FLASH"]
        )
        configured_key = api_key or APPLICATION.get("llm_api_key") or ""
        self.api_keys = [key.strip() for key in configured_key.split(",") if key.strip()]
        configured_gemini_keys = (
            api_key
            if self.provider == "gemini" and api_key
            else APPLICATION.get("gemini_api_keys")
        ) or ""
        self.gemini_api_keys = [
            key.strip()
            for key in configured_gemini_keys.split(",")
            if key.strip()
        ]
        self.generation_config = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_output_tokens,
        }
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        self._openai_clients = []

    def start(self) -> None:
        if self.provider == "gemini":
            if not self.gemini_api_keys:
                logger.warning("LLM provider Gemini is configured but GEMINI_API_KEYS is empty")
            return

        if self.provider not in OPENAI_COMPATIBLE_PROVIDERS:
            raise ValueError(
                f"Unsupported BACKEND_LLM_PROVIDER={self.provider!r}. "
                "Use gemini, openai, openai-compatible, groq, or grok."
            )
        if not self.base_url:
            raise ValueError(
                "BACKEND_LLM_BASE_URL is required for an OpenAI-compatible provider"
            )
        if not self.api_keys:
            logger.warning(
                "BACKEND_LLM_API_KEY is empty; using a placeholder key for a local "
                "OpenAI-compatible endpoint"
            )
            self.api_keys = ["not-needed"]
        self._openai_clients = [
            AsyncOpenAI(api_key=key, base_url=self.base_url) for key in self.api_keys
        ]
        logger.info(
            "LLM ready: provider={} model={} base_url={}",
            self.provider,
            self.model_name,
            self.base_url,
        )

    async def stop(self) -> None:
        for client in self._openai_clients:
            await client.close()
        self._openai_clients = []

    def has_credentials(self) -> bool:
        """Whether an API key is configured for the active provider.

        Used to skip a doomed LLM round-trip (and its retries) when no key is set,
        so callers fall back cleanly instead of paying the timeout.
        """
        if self.provider == "gemini":
            return bool(self.gemini_api_keys)
        return bool(self.api_keys)

    async def ask_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        retries: int = 3,
        timeout_seconds: int = 60 * 10,
        history: Optional[List[dict]] = None,
        *,
        json_mode: bool = False,
        temperature: Optional[float] = None,
    ) -> Tuple[bool, Optional[str], Optional[Exception]]:
        """Ask the LLM a single turn, optionally with prior conversation ``history``.

        ``history`` is an ordered list of ``{"role": "user"|"assistant", "content": str}``
        turns that precede ``user_prompt``. Passing ``None`` reproduces the original
        single-shot behavior exactly.

        ``json_mode`` requests native JSON output (OpenAI ``response_format`` /
        Gemini ``response_mime_type``). ``temperature`` overrides the default for
        this call only (e.g. a low value for grounded/extractive answers).
        """
        selected_model = model or self.model_name
        if self.provider == "gemini":
            return await self._ask_gemini(
                system_prompt, user_prompt, selected_model, retries, timeout_seconds,
                history, json_mode=json_mode, temperature=temperature,
            )
        return await self._ask_openai_compatible(
            system_prompt, user_prompt, selected_model, retries, timeout_seconds,
            history, json_mode=json_mode, temperature=temperature,
        )

    async def _ask_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        retries: int,
        timeout_seconds: int,
        history: Optional[List[dict]] = None,
        *,
        json_mode: bool = False,
        temperature: Optional[float] = None,
    ) -> Tuple[bool, Optional[str], Optional[Exception]]:
        last_error: Optional[Exception] = None
        generation_config = dict(self.generation_config)
        if temperature is not None:
            generation_config["temperature"] = temperature
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        contents = []
        for turn in history or []:
            role = "model" if turn.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [str(turn.get("content") or "")]})
        contents.append({"role": "user", "parts": [user_prompt]})
        for attempt in range(1, retries + 1):
            try:
                api_key = random.choice(self.gemini_api_keys)
                genai.configure(api_key=api_key)
                gemini_model = genai.GenerativeModel(
                    model_name=model,
                    generation_config=generation_config,
                    system_instruction=system_prompt,
                    safety_settings=self.safety_settings,
                )
                response = await gemini_model.generate_content_async(
                    contents,
                    request_options={"timeout": timeout_seconds},
                )
                return True, response.parts[0].text, None
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini request failed ({}/{}): {}", attempt, retries, exc
                )
        logger.error("Gemini request failed after {} attempts: {}", retries, last_error)
        return False, None, last_error

    async def _ask_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        retries: int,
        timeout_seconds: int,
        history: Optional[List[dict]] = None,
        *,
        json_mode: bool = False,
        temperature: Optional[float] = None,
    ) -> Tuple[bool, Optional[str], Optional[Exception]]:
        if not self._openai_clients:
            self.start()

        messages = [{"role": "system", "content": system_prompt}]
        for turn in history or []:
            role = "assistant" if turn.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": str(turn.get("content") or "")})
        messages.append({"role": "user", "content": user_prompt})

        create_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.generation_config["temperature"],
            "top_p": self.generation_config["top_p"],
            "max_tokens": self.generation_config["max_output_tokens"],
            "timeout": timeout_seconds,
        }
        if json_mode:
            create_kwargs["response_format"] = {"type": "json_object"}

        last_error: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                client = random.choice(self._openai_clients)
                response = await client.chat.completions.create(**create_kwargs)
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("OpenAI-compatible endpoint returned empty content")
                return True, content, None
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "OpenAI-compatible request failed ({}/{}): {}", attempt, retries, exc
                )
        logger.error(
            "OpenAI-compatible request failed after {} attempts: {}", retries, last_error
        )
        return False, None, last_error
