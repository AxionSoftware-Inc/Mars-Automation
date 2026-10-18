import os
import sys
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
API_ID = int(os.getenv("TG_API_ID", "2040"))
API_HASH = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")


def get_paths(session_idx: int = 1):
    suffix = "" if session_idx == 1 else f"_{session_idx}"
    sess_file = os.path.join(DATA_DIR, f"tester_user{suffix}")
    temp_auth = os.path.join(DATA_DIR, f"tester_auth_temp{suffix}.json")
    return sess_file, temp_auth


async def request_code(phone: str, session_idx: int = 1):
    sess_file, temp_auth = get_paths(session_idx)
    os.makedirs(DATA_DIR, exist_ok=True)
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    client = TelegramClient(sess_file, API_ID, API_HASH)
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
    with open(temp_auth, "w", encoding="utf-8") as f:
        json.dump(auth_data, f)

    await client.disconnect()
    print(f"CODE_SENT:{clean_phone}:session_{session_idx}")


async def verify_code(code: str, password: str = "LEGIONGAMING", session_idx: int = 1):
    sess_file, temp_auth = get_paths(session_idx)
    if not os.path.exists(temp_auth):
        print(f"ERROR:Session {session_idx} uchun avval telefon raqam yuboring.")
        return

    with open(temp_auth, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    phone = auth_data["phone"]
    phone_code_hash = auth_data["phone_code_hash"]
    clean_code = str(code).strip().replace(" ", "")

    client = TelegramClient(sess_file, API_ID, API_HASH)
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
        print("ERROR_EXPIRED_CODE:Kod muddati tugagan.")
        await client.disconnect()
        return

    me = await client.get_me()
    if os.path.exists(temp_auth):
        os.remove(temp_auth)

    print(f"SUCCESS:{me.id}:{me.first_name}:{me.username or 'NoUsername'}:session_{session_idx}")
    await client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  tester_client.py request <phone> [session_idx]")
        print("  tester_client.py verify <code> [password] [session_idx]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "request":
        phone_num = sys.argv[2]
        s_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        asyncio.run(request_code(phone_num, s_idx))
    elif cmd == "verify":
        c = sys.argv[2]
        p = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else "LEGIONGAMING"
        s_idx = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        asyncio.run(verify_code(c, p, s_idx))
