import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bot_keuangan")

# Payment
PREMIUM_PRICE = int(os.getenv("PREMIUM_PRICE", "50000"))
BANK_NAME = os.getenv("BANK_NAME", "BCA")
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "")
BANK_HOLDER = os.getenv("BANK_HOLDER", "DevCultur XII")
QRIS_IMAGE_URL = os.getenv("QRIS_IMAGE_URL", "")

# Webhook URL (Railway akan provide URL)
WEBHOOK_URL = os.getenv("RAILWAY_URL", "")
PORT = int(os.getenv("PORT", "8000"))
