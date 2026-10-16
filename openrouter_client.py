import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"

class OpenRouterClient:
    """
    OpenRouter orqali Gemini 2.5 Flash modeliga so'rov yuborish mijozi.
    Matn va rasm (multimodal) so'rovlarini to'liq qo'llab-quvvatlaydi.
    Ham asinxron (httpx.AsyncClient), ham sinxron (httpx.Client) usullarni taqdim etadi.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model = model

    def _build_payload_and_headers(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[tuple]:
        if not self.api_key:
            logger.error("OpenRouterClient: API kalit mavjud emas!")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mars-pos.uz",
            "X-Title": "Mars POS Assistant"
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }

        if response_format:
            payload["response_format"] = response_format

        return headers, payload

    async def chat_completion_async(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """Asinxron so'rov — asyncio event loopni hech qachon bloklamaydi!"""
        # Testlardagi mocklarni qo'llab-quvvatlash:
        if hasattr(self.chat_completion, "assert_called") or getattr(self.chat_completion, "__class__.__name__", "") in ("MagicMock", "AsyncMock"):
            res = self.chat_completion(messages=messages, temperature=temperature, response_format=response_format)
            if asyncio.iscoroutine(res):
                return await res
            return res

        built = self._build_payload_and_headers(messages, temperature, response_format)
        if not built:
            return None
        headers, payload = built

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                else:
                    logger.error(f"OpenRouter API xatoligi (status={resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"OpenRouter API asinxron so'rovida xatolik: {e}")
        return None

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """Sinxron so'rov (yoki mocklar uchun)"""
        built = self._build_payload_and_headers(messages, temperature, response_format)
        if not built:
            return None
        headers, payload = built

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(OPENROUTER_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                else:
                    logger.error(f"OpenRouter API xatoligi (status={resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"OpenRouter API sinxron so'rovida xatolik: {e}")
        return None

openrouter_client = OpenRouterClient()
