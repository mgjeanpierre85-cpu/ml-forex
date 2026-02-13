import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("8112184461:AAEDjFKsSgrKtv6oBIA3hJ51AhX8eRU7eno")
TELEGRAM_CHAT_ID = os.getenv("-1003230221533")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN no está definido en las variables de entorno.")

if not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_CHAT_ID no está definido en las variables de entorno.")
