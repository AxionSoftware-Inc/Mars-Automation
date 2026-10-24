import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "bot_state.json")

def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"State o'qishda xatolik: {e}")
    return {}

def save_state(state: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"State saqlashda xatolik: {e}")

def get_last_file_message_id() -> Optional[int]:
    state = load_state()
    return state.get("last_channel_file_msg_id")

def set_last_file_message_id(msg_id: int):
    state = load_state()
    state["last_channel_file_msg_id"] = msg_id
    save_state(state)

def get_last_excel_channel_msg_id() -> Optional[int]:
    state = load_state()
    return state.get("last_excel_channel_msg_id")

def set_last_excel_channel_msg_id(msg_id: int):
    state = load_state()
    state["last_excel_channel_msg_id"] = msg_id
    save_state(state)

def get_last_forwarded_excel_channel_msg_id() -> Optional[int]:
    state = load_state()
    return state.get("last_forwarded_excel_channel_msg_id") or state.get("last_excel_channel_msg_id")

def set_last_forwarded_excel_channel_msg_id(msg_id: int):
    state = load_state()
    state["last_forwarded_excel_channel_msg_id"] = msg_id
    save_state(state)

