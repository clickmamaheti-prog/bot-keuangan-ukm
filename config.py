import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_keuangan.db")

# Payment
PREMIUM_PRICE = int(os.getenv("PREMIUM_PRICE", "50000"))
BANK_NAME = os.getenv("BANK_NAME", "BCA")
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "")
BANK_HOLDER = os.getenv("BANK_HOLDER", "DevCultur XII")
QRIS_IMAGE_URL = os.getenv("QRIS_IMAGE_URL", "")

# Webhook URL (Render / Railway)
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "") or os.getenv("RAILWAY_URL", "") or RENDER_URL
PORT = int(os.getenv("PORT", "8000"))
