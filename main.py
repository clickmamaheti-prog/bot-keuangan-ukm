"""
Bot Laporan Keuangan UKM - Main Entry Point
FastAPI app + Telegram Bot Webhook

Siap deploy ke Railway!
"""
import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TELEGRAM_BOT_TOKEN, DATABASE_URL, PORT, WEBHOOK_URL
from database import init_db
from bot_handlers import (
    start_command, menu_command, handle_message,
    admin_confirm, admin_reject, admin_stats,
    callback_handler, send_daily_reports, set_database_url
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Scheduler untuk laporan otomatis
scheduler = AsyncIOScheduler()

# Aplikasi Telegram Bot
telegram_app: Application = None

# ======================== LIFECYCLE ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle FastAPI: startup & shutdown"""
    global telegram_app, scheduler
    
    # Startup
    logger.info("🚀 Memulai Bot Laporan Keuangan UKM...")
    
    # Init database
    try:
        init_db(DATABASE_URL)
        set_database_url(DATABASE_URL)  # Set URL untuk bot_handlers
        logger.info("✅ Database siap!")
    except Exception as e:
        logger.error(f"❌ Gagal konek database: {e}")
        raise
    
    # Init Telegram Bot
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("menu", menu_command))
    telegram_app.add_handler(CommandHandler("confirm", admin_confirm))
    telegram_app.add_handler(CommandHandler("reject", admin_reject))
    telegram_app.add_handler(CommandHandler("stats", admin_stats))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    telegram_app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Setup webhook atau polling
    bot_url = WEBHOOK_URL or os.getenv("RAILWAY_URL", "")
    
    # Inisialisasi aplikasi untuk semua mode
    await telegram_app.initialize()
    
    if bot_url:
        # Webhook mode (Render / Railway)
        await telegram_app.start()
        webhook_url = f"{bot_url}/webhook"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook set: {webhook_url}")
    else:
        # Polling mode (development)
        await telegram_app.start()
        asyncio.create_task(telegram_app.updater.start_polling())
        logger.info("✅ Polling mode started")
    
    # Schedule laporan harian (setiap jam 20:00 WIB / 13:00 UTC)
    scheduler.add_job(
        lambda: asyncio.create_task(send_daily_reports(telegram_app)),
        CronTrigger(hour=13, minute=0),  # 20:00 WIB = 13:00 UTC
        id="daily_report",
        replace_existing=True
    )
    scheduler.start()
    logger.info("✅ Laporan harian terjadiwal: 20:00 WIB")
    
    logger.info("✅ Bot siap! 🎉")
    
    yield
    
    # Shutdown
    logger.info("🛑 Mematikan bot...")
    scheduler.shutdown()
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()


# ======================== FASTAPI APP ========================

app = FastAPI(
    title="Bot Laporan Keuangan UKM",
    description="Bot Telegram untuk catat keuangan UKM",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "bot": "Bot Laporan Keuangan UKM",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check detail"""
    return {
        "status": "healthy",
        "telegram_bot": telegram_app is not None,
        "webhook": WEBHOOK_URL or "polling"
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Endpoint untuk webhook Telegram"""
    if telegram_app is None:
        return {"ok": False, "error": "Bot belum siap"}
    
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}
