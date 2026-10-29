"""
core/ai_agent.py - Mars POS Yuqori Qatlam (AI Agent & Tool Orchestrator)
========================================================================
Ushbu modul 2 qatlamli arxitekturadagi "Yuqori Qatlam" (AI Agent) vazifasini
bajaradi:
1. Gemini 3.5 Flash Lite modeli orqali mijoz xabarini (sheva, xato yozuv, niyat)
   to'liq tushunadi.
2. Niyatga qarab Pastki Qatlamdagi (`core/tools.py`) aniq asboblarni (Tools) chaqiradi:
   - `check_monthly_debt`
   - `check_fiscal_license`
   - `get_payment_requisites`
   - `pos_troubleshoot_step`
   - `verify_receipt_data`
   - `escalate_to_admin`
   - `get_instruction`
3. Asbob natijasini qayta ishlab, mijozga lo'nda, xatosiz va anti-gallyutsinatsiyalangan
   javob qaytaradi.
4. Agar AI API tomonida uzilish bo'lsa, zaxira (deterministic fallback) rejimiga o'tadi.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from aiogram import Bot

from openrouter_client import openrouter_client
from user_memory import user_memory
from core.models import extract_clean_inn, extract_fiscal_module
from core import tools as mars_tools

logger = logging.getLogger(__name__)


# =============================================================================
# GEMINI VA OPENROUTER ASBOBLARI (TOOL SCHEMAS)
# =============================================================================
MARS_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_monthly_debt",
            "description": "Korxonaning oylik abonent to'lovidan qarzdorligini INN (STIR) orqali Excel bazasidan tekshirish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inn": {
                        "type": "string",
                        "description": "9 yoki 14 xonali korxona INN (STIR) raqami"
                    }
                },
                "required": ["inn"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_fiscal_license",
            "description": "Apparatning yillik fiskal modul litsenziyasi va Soliq qarzdorligini seriya raqami orqali tekshirish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fiscal_module": {
                        "type": "string",
                        "description": "Apparatning fiskal modul seriya raqami (masalan LG..., YG...)"
                    }
                },
                "required": ["fiscal_module"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_requisites",
            "description": "To'lov qilish uchun rasmiy bank hisob raqamlari (shot) va video yo'riqnomalarni olish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_type": {
                        "type": "string",
                        "enum": ["monthly", "annual", "both"],
                        "description": "To'lov turi: monthly (oylik abonent), annual (yillik soliq/fiskal modul), both (ikkalasi)"
                    }
                },
                "required": ["payment_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pos_troubleshoot_step",
            "description": "Smart POS apparatidagi nosozlik (ishlamayapti, xatolik, chek chiqmayapti) bo'yicha 4 bosqichli diagnostikani bajarish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inn": {
                        "type": "string",
                        "description": "Korxona INN raqami (agar ma'lum bo'lsa)"
                    },
                    "fiscal_module": {
                        "type": "string",
                        "description": "Fiskal modul seriya raqami (agar ma'lum bo'lsa)"
                    },
                    "reboot_tried": {
                        "type": "boolean",
                        "description": "Mijoz apparatni o'chirib yoqib ko'rganmi yoki yo'qmi"
                    },
                    "error_code": {
                        "type": "string",
                        "description": "Ekrandagi xatolik kodi yoki yozuvi"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_admin",
            "description": "Mijozni mas'ul viloyat adminiga yoki jonli mutaxassis/usta/operatorga yo'naltirish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Eskalatsiya sababi (masalan: usta kerak, apparat sinishi, dasturiy xato)"
                    },
                    "inn": {
                        "type": "string",
                        "description": "Korxona INN raqami (agar ma'lum bo'lsa)"
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_instruction",
            "description": "Standart kassa amallari bo'yicha yo'riqnoma yoki videoni olish (MXIK, Tasnif, Qaytuv/Vozvrat, Soat, Wifi).",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["mxik", "vozvrat", "soat", "wifi"],
                        "description": "Yo'riqnoma mavzusi"
                    }
                },
                "required": ["topic"]
            }
        }
    }
]


MARS_AGENT_SYSTEM_PROMPT = """Siz «Mars Elektron Texnika» MCHJning rasmiy Smart POS xizmat ko'rsatish AI yordamchisisiz.

QAT'IY QOIDALAR:
1. SIZGA PASTKI QATLAM ASBOBLARI (TOOLS) BIRIKTIRILGAN. HAR QANDAY REAL MA'LUMOT UCHUN ASBOBNI CHAQIRING!
   - Agar mijoz qarz so'rasa yoki INN yuborsa -> `check_monthly_debt` chaqiring.
   - Agar yillik to'lov, soliq litsenziyasi yoki Fiskal modul (LG/YG) so'ralsa -> `check_fiscal_license` chaqiring.
   - Agar hisob raqam, shot, rekvizit yoki to'lov qayerga qilinishi so'ralsa -> `get_payment_requisites` chaqiring.
   - Agar apparat ishlamasa, xatolik bersa yoki o'chib qolsa -> `pos_troubleshoot_step` chaqiring.
   - Agar mijoz usta, operator, admin talab qilsa yoki asabiy bo'lsa -> `escalate_to_admin` chaqiring.
   - Agar MXIK/Tasnif, vozvrat, soat, wifi paroli so'ralsa -> `get_instruction` chaqiring.

2. ANTI-GALLYUTSINATSIYA:
   - Hech qachon o'zingizdan qarz summasi yoki apparat modelini to'qimang! Faqat asbob bergan natijaga tayaning.
   - Kompaniya faqat 2 xil apparatga xizmat ko'rsatadi: «P3 Humo» va «Smart One».

3. JAVOB USLUBI:
   - O'ta qisqa, aniq va lo'nda (1-2 ta jumla).
   - O'zbek tilida (mijoz qaysi alifboda yozsa, o'sha alifboda) javob bering.
"""


@dataclass
class AgentResult:
    reply_text: str
    action: str = "DIRECT_REPLY"
    tool_called: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None
    media_video_id: Optional[int] = None


class MarsAIAgent:
    """
    Mars POS Yuqori Qatlam AI Agenti.
    Mijoz xabarlarini tahlil qilib, kerakli asbobga yo'naltiradi va natijani qaytaradi.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name

    async def process_user_turn(
        self,
        text: str,
        user_id: int,
        chat_id: int,
        bot: Optional[Bot] = None,
        script: str = "latin",
        photo_bytes: Optional[bytes] = None
    ) -> AgentResult:
        """
        Foydalanuvchi xabarini 2 qatlamli model asosida qayta ishlash.
        """
        clean_text = (text or "").strip()
        inn_in_text = extract_clean_inn(clean_text)
        fm_in_text = extract_fiscal_module(clean_text)

        # Xotiradagi avvalgi ma'lumotlar bilan boyitish
        remembered_inn = user_memory.get_last_id(chat_id, user_id) or inn_in_text
        remembered_fm = user_memory.get_last_fm(chat_id, user_id) or fm_in_text

        # 1. Agar to'g'ridan-to'g'ri faqat INN yuborilgan bo'lsa -> ortiqcha AI chaqiruvsiz tezkor asbob!
        if inn_in_text and len(clean_text) in (9, 14) and clean_text.isdigit():
            user_memory.set_last_id(chat_id, user_id, inn_in_text)
            tool_res = mars_tools.check_monthly_debt(inn_in_text, script=script)
            return AgentResult(
                reply_text=tool_res["formatted_text"],
                action="CHECK_DEBT",
                tool_called="check_monthly_debt",
                tool_result=tool_res
            )

        # 2. Agar to'g'ridan-to'g'ri faqat Fiskal modul (LG..., YG...) yuborilgan bo'lsa -> tezkor asbob!
        if fm_in_text and len(clean_text) in range(8, 18) and clean_text.upper().startswith(("LG", "YG", "UZ")):
            user_memory.set_last_fm(chat_id, user_id, fm_in_text)
            tool_res = await mars_tools.check_fiscal_license(fm_in_text, bot=bot, script=script)
            return AgentResult(
                reply_text=tool_res["formatted_text"],
                action="CHECK_OFD",
                tool_called="check_fiscal_license",
                tool_result=tool_res
            )

        # 3. Yuqori qatlam (Gemini Tool Calling) ga so'rov tuzish
        context_hint = f"\n[Kontekst: Oxirgi ma'lum INN={remembered_inn or 'yoq'}, FM={remembered_fm or 'yoq'}]"
        messages = [
            {"role": "system", "content": MARS_AGENT_SYSTEM_PROMPT + context_hint},
            {"role": "user", "content": clean_text}
        ]

        try:
            ai_resp = await openrouter_client.chat_completion_with_tools_async(
                messages=messages,
                tools=MARS_AGENT_TOOLS,
                temperature=0.1
            )
        except Exception as e:
            logger.error(f"MarsAIAgent: AI so'rovida xatolik: {e}")
            ai_resp = None

        # Agar AI tool call chaqirgan bo'lsa:
        if ai_resp and ai_resp.get("tool_calls"):
            tool_call = ai_resp["tool_calls"][0]
            fn_name = tool_call.get("function", {}).get("name", "")
            raw_args = tool_call.get("function", {}).get("arguments", "{}")

            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except Exception:
                args = {}

            return await self._execute_tool(
                fn_name=fn_name,
                args=args,
                user_id=user_id,
                chat_id=chat_id,
                remembered_inn=remembered_inn,
                remembered_fm=remembered_fm,
                bot=bot,
                script=script
            )

        # Agar AI oddiy matnli javob bergan bo'lsa:
        if ai_resp and ai_resp.get("content"):
            content = ai_resp["content"].strip()
            return AgentResult(reply_text=content, action="DIRECT_REPLY")

        # 4. Zaxira rejim (Fallback): Agar AI javob bermasa yoki tarmoq uzilsa
        return await self._fallback_deterministic(
            clean_text=clean_text,
            remembered_inn=remembered_inn,
            remembered_fm=remembered_fm,
            user_id=user_id,
            chat_id=chat_id,
            bot=bot,
            script=script
        )

    async def _execute_tool(
        self,
        fn_name: str,
        args: Dict[str, Any],
        user_id: int,
        chat_id: int,
        remembered_inn: Optional[str],
        remembered_fm: Optional[str],
        bot: Optional[Bot],
        script: str
    ) -> AgentResult:
        """Pastki qatlam asbobini chaqirish va natijani shakllantirish"""
        logger.info(f"🛠 MarsAIAgent Tool chaqirmoqda: {fn_name}({args})")

        if fn_name == "check_monthly_debt":
            inn = args.get("inn") or remembered_inn
            if inn:
                user_memory.set_last_id(chat_id, user_id, inn)
                res = mars_tools.check_monthly_debt(inn, script=script)
                return AgentResult(
                    reply_text=res["formatted_text"],
                    action="CHECK_DEBT",
                    tool_called=fn_name,
                    tool_result=res
                )

        elif fn_name == "check_fiscal_license":
            fm = args.get("fiscal_module") or remembered_fm
            if fm:
                user_memory.set_last_fm(chat_id, user_id, fm)
                res = await mars_tools.check_fiscal_license(fm, bot=bot, script=script)
                return AgentResult(
                    reply_text=res["formatted_text"],
                    action="CHECK_OFD",
                    tool_called=fn_name,
                    tool_result=res
                )

        elif fn_name == "get_payment_requisites":
            ptype = args.get("payment_type", "monthly")
            res = mars_tools.get_payment_requisites(ptype, script=script)
            return AgentResult(
                reply_text=res["formatted_text"],
                action="REQUISITES",
                tool_called=fn_name,
                tool_result=res,
                media_video_id=res.get("video_id")
            )

        elif fn_name == "pos_troubleshoot_step":
            inn = args.get("inn") or remembered_inn
            fm = args.get("fiscal_module") or remembered_fm
            reboot_tried = bool(args.get("reboot_tried", False))
            err_code = args.get("error_code")
            res = await mars_tools.pos_troubleshoot_step(
                inn=inn,
                fiscal_module=fm,
                reboot_tried=reboot_tried,
                error_code=err_code,
                bot=bot,
                script=script
            )
            return AgentResult(
                reply_text=res["formatted_text"],
                action=res.get("action", "TROUBLESHOOT"),
                tool_called=fn_name,
                tool_result=res
            )

        elif fn_name == "escalate_to_admin":
            reason = args.get("reason", "Mijoz mutaxassis so'ramoqda")
            inn = args.get("inn") or remembered_inn
            res = mars_tools.escalate_to_admin(
                inn=inn,
                reason=reason,
                user_id=user_id,
                script=script
            )
            return AgentResult(
                reply_text=res["formatted_text"],
                action="ESCALATE_ADMIN",
                tool_called=fn_name,
                tool_result=res
            )

        elif fn_name == "get_instruction":
            topic = args.get("topic", "mxik")
            res = mars_tools.get_instruction(topic, script=script)
            return AgentResult(
                reply_text=res["formatted_text"],
                action="INSTRUCTION",
                tool_called=fn_name,
                tool_result=res,
                media_video_id=res.get("video_id")
            )

        # Standart fallback
        return AgentResult(
            reply_text="Savolingiz mutaxassisimizga yo'naltirildi. Tez orada javob beramiz.",
            action="DEFAULT"
        )

    async def _fallback_deterministic(
        self,
        clean_text: str,
        remembered_inn: Optional[str],
        remembered_fm: Optional[str],
        user_id: int,
        chat_id: int,
        bot: Optional[Bot],
        script: str
    ) -> AgentResult:
        """
        Zaxira qatlam: AI tarmoq uzilishi yoki xatolik yuz berganda
        mijozni xatosiz qabul qilish.
        """
        t = clean_text.lower()

        # Usta / Admin talabi
        if any(w in t for w in ["usta", "admin", "operator", "odam", "mutaxassis"]):
            res = mars_tools.escalate_to_admin(inn=remembered_inn, reason="Mijoz usta so'ramoqda", script=script)
            return AgentResult(reply_text=res["formatted_text"], action="ESCALATE_ADMIN")

        # Hisob raqam
        if any(w in t for w in ["hisob", "shot", "kartaga", "rekvizit", "to'lov qayerga"]):
            res = mars_tools.get_payment_requisites("monthly", script=script)
            return AgentResult(reply_text=res["formatted_text"], action="REQUISITES", media_video_id=res.get("video_id"))

        # Qarz tekshirish
        if any(w in t for w in ["qarz", "qarzdorlik", "tolanganmi", "to'langanmi"]):
            if remembered_inn:
                res = mars_tools.check_monthly_debt(remembered_inn, script=script)
                return AgentResult(reply_text=res["formatted_text"], action="CHECK_DEBT", tool_result=res)
            return AgentResult(
                reply_text="Qarzdorlikni tekshirish uchun korxonangizning 9 xonali INN (STIR) raqamini yuboring.",
                action="ASK_INN"
            )

        return AgentResult(
            reply_text="Savolingiz qabul qilindi. Aniq ma'lumot olish uchun INN raqamingizni yuboring yoki mutaxassisimiz javobini kuting.",
            action="SAFE_FALLBACK"
        )


mars_ai_agent = MarsAIAgent()
