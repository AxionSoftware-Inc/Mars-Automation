import os
import json
import logging
import urllib.request
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3.5-flash-lite"

class OpenRouterClient:
    """
    OpenRouter orqali Gemini 3.5 Flash Lite modeliga so'rov yuborish mijozi.
    Matn va rasm (multimodal) so'rovlarini to'liq qo'llab-quvvatlaydi.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
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

        try:
            req = urllib.request.Request(
                OPENROUTER_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"OpenRouter API xatoligi: {e}")
            return None

        return None

openrouter_client = OpenRouterClient()
