import asyncio
from telethon import TelegramClient

async def view_recent():
    c = TelegramClient("data/ofd_user", 2040, "b18441a1ff607e10a989891a5462e627")
    await c.connect()
    msgs = await c.get_messages(-1003742874507, limit=6)
    for m in msgs:
        sender = await m.get_sender()
        name = getattr(sender, "first_name", "")
        reply_id = getattr(m.reply_to, "reply_to_msg_id", None) if m.reply_to else None
        text_preview = (m.text[:120].replace('\n', ' ') if m.text else '[Photo/Media]')
        print(f"[{m.id}] {name} (reply_to={reply_id}): {text_preview}")
    await c.disconnect()

if __name__ == "__main__":
    asyncio.run(view_recent())
