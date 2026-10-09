import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_FILE = os.getenv("SESSION_FILE", "/app/data/telethon.session")


async def main():
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)

    if API_ID == 0 or not API_HASH:
        raise RuntimeError("API_ID/API_HASH missing in environment")

    print(f"Session file target: {SESSION_FILE}")
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    await client.connect()
    if await client.is_user_authorized():
        print("Session already authorized.")
        await client.disconnect()
        return

    phone = input("Phone Number: ").strip()
    await client.send_code_request(phone)
    code = input("Code: ").strip()

    try:
        await client.sign_in(phone=phone, code=code)
    except Exception:
        password = input("2FA Password: ").strip()
        await client.sign_in(password=password)

    print(f"Session created: {SESSION_FILE}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())