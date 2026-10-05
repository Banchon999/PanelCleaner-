import os
import time

import requests
from loguru import logger

API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY_ENV_VAR = "OPENROUTER_API_KEY"

# HTTP status codes that are worth retrying.
RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class OpenRouterError(Exception):
    pass


def resolve_api_key(configured_key: str | None) -> str | None:
    """
    Get the OpenRouter API key, preferring the environment variable over the config file.

    :param configured_key: The key stored in the config file, if any.
    :return: The API key, or None if none is set.
    """
    env_key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if configured_key and configured_key.strip():
        return configured_key.strip()
    return None


class OpenRouterClient:
    """
    A minimal client for the OpenRouter chat completions API.
    See: https://openrouter.ai/docs/api-reference/chat-completion
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        timeout: float = 120,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise OpenRouterError(
                f"No OpenRouter API key set. Set the {API_KEY_ENV_VAR} environment variable "
                "or add openrouter_api_key to the config file."
            )
        if not model:
            raise OpenRouterError("No OpenRouter model set in the profile.")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        """
        Send a chat completion request and return the content of the reply.

        :param messages: The chat messages, as dicts with "role" and "content".
        :param json_mode: Ask the model to respond with a JSON object.
        :return: The reply text.
        :raises OpenRouterError: If the request fails after all retries.
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Optional attribution headers, see https://openrouter.ai/docs/api-reference/overview
            "HTTP-Referer": "https://github.com/VoxelCubes/PanelCleaner",
            "X-Title": "Panel Cleaner",
        }

        last_error = ""
        for attempt in range(self.max_retries + 1):
            if attempt:
                delay = 2**attempt
                logger.warning(f"Retrying OpenRouter request in {delay}s ({last_error})")
                time.sleep(delay)
            try:
                response = self.session.post(
                    API_URL, json=payload, headers=headers, timeout=self.timeout
                )
            except requests.RequestException as e:
                last_error = f"network error: {e}"
                continue

            if response.status_code in RETRY_STATUS_CODES:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                continue
            if response.status_code == 400 and "response_format" in payload:
                # Not every model supports JSON mode, fall back to asking for it in the prompt only.
                logger.warning(
                    f"Model {self.model} rejected JSON mode, retrying without it: "
                    f"{response.text[:300]}"
                )
                payload.pop("response_format")
                last_error = f"HTTP 400: {response.text[:300]}"
                continue
            if response.status_code != 200:
                raise OpenRouterError(
                    f"OpenRouter request failed with HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )

            try:
                data = response.json()
            except ValueError:
                last_error = f"invalid JSON response: {response.text[:300]}"
                continue

            # OpenRouter can report upstream provider errors inside a 200 response.
            if "error" in data:
                last_error = f"provider error: {data['error']}"
                continue

            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                last_error = f"unexpected response format: {str(data)[:300]}"
                continue
            if not content:
                last_error = "empty response"
                continue
            return content

        raise OpenRouterError(
            f"OpenRouter request failed after {self.max_retries + 1} attempts: {last_error}"
        )
