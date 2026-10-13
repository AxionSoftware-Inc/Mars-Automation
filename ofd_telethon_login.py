import os
import sys
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SESSION_FILE = os.path.join(DATA_DIR, "ofd_user.session")
TEMP_AUTH_FILE = os.path.join(DATA_DIR, "ofd_auth_temp.json")

# Telegram rasmiy Android API ma'lumotlari
API_ID = int(os.getenv("TG_API_ID", "2040"))
API_HASH = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")


async def request_code(phone: str):
    """1-qadam: Telegramdan telefon raqamga tasdiqlash kodini so'rash"""
    os.makedirs(DATA_DIR, exist_ok=True)
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    client = TelegramClient(os.path.join(DATA_DIR, "ofd_user"), API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"ALREADY_AUTHORIZED:{me.id}:{me.first_name}:{me.username}")
        await client.disconnect()
        return

    res = await client.send_code_request(clean_phone)
    auth_data = {
        "phone": clean_phone,
        "phone_code_hash": res.phone_code_hash
    }
    with open(TEMP_AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(auth_data, f)

    await client.disconnect()
    print(f"CODE_SENT:{clean_phone}")


async def verify_code(code: str, password: str = ""):
    """2-qadam: Telegramdan kelgan 5 xonali kodni tekshirib, sessiyani faollashtirish"""
    if not os.path.exists(TEMP_AUTH_FILE):
        print("ERROR:No pending auth found. Avval 'request <phone>' buyrug'ini bering.")
        return

    with open(TEMP_AUTH_FILE, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    phone = auth_data["phone"]
    phone_code_hash = auth_data["phone_code_hash"]
    clean_code = str(code).strip().replace(" ", "")

    client = TelegramClient(os.path.join(DATA_DIR, "ofd_user"), API_ID, API_HASH)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=clean_code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        if password:
            await client.sign_in(password=password)
        else:
            print("NEED_PASSWORD:2FA parol talab qilinadi")
            await client.disconnect()
            return
    except PhoneCodeInvalidError:
        print("ERROR_INVALID_CODE:Kiritilgan kod noto'g'ri!")
        await client.disconnect()
        return
    except PhoneCodeExpiredError:
        print("ERROR_EXPIRED_CODE:Kod muddati tugagan, qaytadan so'rang.")
        await client.disconnect()
        return

    me = await client.get_me()
    if os.path.exists(TEMP_AUTH_FILE):
        os.remove(TEMP_AUTH_FILE)

    print(f"SUCCESS:{me.id}:{me.first_name}:{me.username or 'NoUsername'}")
    await client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ofd_telethon_login.py request <phone> OR ofd_telethon_login.py verify <code> [2fa_pass]")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "request":
        if len(sys.argv) < 3:
            print("ERROR:Telefon raqam ko'rsatilmadi!")
            sys.exit(1)
        asyncio.run(request_code(sys.argv[2]))
    elif action == "verify":
        if len(sys.argv) < 3:
            print("ERROR:Tasdiqlash kodi ko'rsatilmadi!")
            sys.exit(1)
        code_arg = sys.argv[2]
        pass_arg = sys.argv[3] if len(sys.argv) > 3 else ""
        asyncio.run(verify_code(code_arg, pass_arg))
