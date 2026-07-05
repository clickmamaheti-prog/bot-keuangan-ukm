"""
Bot handlers untuk Bot Laporan Keuangan UKM
"""
import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

from config import (
    ADMIN_TELEGRAM_ID, BANK_NAME, BANK_ACCOUNT, BANK_HOLDER,
    PREMIUM_PRICE, QRIS_IMAGE_URL
)
from database import User, Transaction, PremiumRequest, get_session
from parser import parse_message, format_rupiah
from report_generator import generate_daily_report, generate_weekly_report, generate_monthly_report

logger = logging.getLogger(__name__)
DATABASE_URL = None


def set_database_url(url: str):
    global DATABASE_URL
    DATABASE_URL = url


# ======================== REGISTER / START ========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start"""
    user = update.effective_user
    telegram_id = user.id
    
    # Simpan user ke database
    session = get_session(DATABASE_URL)
    try:
        existing = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not existing:
            new_user = User(
                telegram_id=telegram_id,
                username=user.username,
                full_name=user.full_name,
                trial_end=datetime.datetime.now() + datetime.timedelta(days=7)
            )
            session.add(new_user)
            session.commit()
            is_new = True
        else:
            is_new = False
            # Update info
            existing.username = user.username
            session.commit()
        
        # Cek status premium
        is_premium = existing.is_premium if existing else False
        if existing and existing.premium_until and existing.premium_until < datetime.datetime.now():
            existing.is_premium = False
            session.commit()
            is_premium = False
    finally:
        session.close()
    
    welcome_msg = (
        f"👋 *Halo {user.full_name or user.username}!*\n\n"
        f"📊 *Bot Laporan Keuangan UKM*\n\n"
        f"Catat pemasukan & pengeluaran kamu dengan mudah!\n\n"
        f"📝 *Cara pakai:*\n"
        f"Ketik transaksi seperti chat biasa:\n"
        f"• \"jual nasi goreng 15rb\" → 🟢 Pemasukan\n"
        f"• \"beli telur 25rb\" → 🔴 Pengeluaran\n"
        f"• \"laporan\" atau /harian → Lihat laporan hari ini\n\n"
        f"💰 *Premium:* Rp{PREMIUM_PRICE:,}/bulan\n"
        f"(Gratis trial 7 hari)\n\n"
        f"📋 Ketik /menu untuk bantuan"
    )
    
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /menu"""
    user_id = update.effective_user.id
    
    session = get_session(DATABASE_URL)
    try:
        db_user = session.query(User).filter_by(telegram_id=user_id).first()
        is_premium = db_user and db_user.is_premium
        trial_end = db_user.trial_end if db_user else None
    finally:
        session.close()
    
    keyboard = [
        [InlineKeyboardButton("📊 Laporan Harian", callback_data="report_daily")],
        [InlineKeyboardButton("📈 Laporan Mingguan", callback_data="report_weekly")],
        [InlineKeyboardButton("📑 Laporan Bulanan", callback_data="report_monthly")],
        [InlineKeyboardButton("💰 Premium", callback_data="premium_info")],
        [InlineKeyboardButton("📋 Riwayat Transaksi", callback_data="history")],
        [InlineKeyboardButton("❓ Bantuan", callback_data="help")]
    ]
    
    status = "⭐ *PREMIUM*" if is_premium else f"🆓 *GRATIS* (trial: {trial_end.strftime('%d/%m') if trial_end else 'habis'})"
    
    msg = f"📋 *MENU UTAMA*\n\nStatus: {status}\n\nPilih menu di bawah:"
    
    await update.message.reply_text(
        msg, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ======================== PARSING TRANSAKSI ========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pesan teks dari user - auto detect transaksi"""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Handle commands
    if text.lower() in ["laporan", "harian", "/harian"]:
        await daily_report(update, context)
        return
    elif text.lower() in ["menu", "/menu"]:
        await menu_command(update, context)
        return
    elif text.lower().startswith("cari "):
        await search_transactions(update, context)
        return
    elif text.lower().startswith("kategori "):
        await set_category(update, context)
        return
    
    # Parse transaksi
    parsed = parse_message(text)
    if not parsed:
        # Bukan format transaksi, kasih petunjuk
        await update.message.reply_text(
            "❓ *Tidak dikenali*\n\n"
            "Coba format:\n"
            "• `jual nasi goreng 15rb`\n"
            "• `beli telur 25rb`\n"
            "• `laporan` untuk lihat report\n\n"
            "Atau ketik /menu",
            parse_mode="Markdown"
        )
        return
    
    # Cek limit transaksi untuk free user
    session = get_session(DATABASE_URL)
    try:
        db_user = session.query(User).filter_by(telegram_id=user_id).first()
        is_premium = db_user and db_user.is_premium
        
        if not is_premium:
            # Free user: cek limit transaksi (max 10 transaksi/hari)
            today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            daily_count = session.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= today_start
            ).count()
            
            if daily_count >= 10:
                await update.message.reply_text(
                    "⚠️ *Limit transaksi gratis hari ini sudah habis!*\n"
                    f"Kamu sudah mencatat {daily_count} transaksi hari ini.\n\n"
                    f"💎 Upgrade *Premium Rp{PREMIUM_PRICE:,}/bulan* untuk transaksi unlimited!\n"
                    "Ketik /premium untuk info lebih lanjut.",
                    parse_mode="Markdown"
                )
                return
        
        # Simpan transaksi
        transaction = Transaction(
            user_id=user_id,
            type=parsed["type"],
            amount=parsed["amount"],
            description=parsed["description"],
            category="Umum"
        )
        session.add(transaction)
        session.commit()
        
        # Emoji sesuai tipe
        emoji = "🟢" if parsed["type"] == "INCOME" else "🔴"
        label = "PEMASUKAN" if parsed["type"] == "INCOME" else "PENGELUARAN"
        
        # Hitung saldo hari ini
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trans = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= today_start
        ).all()
        today_income = sum(t.amount for t in today_trans if t.type == "INCOME")
        today_expense = sum(t.amount for t in today_trans if t.type == "EXPENSE")
        today_balance = today_income - today_expense
        
        msg = (
            f"{emoji} *{label}*\n"
            f"📝 {parsed['description']}\n"
            f"💰 {format_rupiah(parsed['amount'])}\n\n"
            f"📊 *Hari ini:*\n"
            f"  🟢 Pemasukan: {format_rupiah(today_income)}\n"
            f"  🔴 Pengeluaran: {format_rupiah(today_expense)}\n"
            f"  💰 Saldo: {format_rupiah(today_balance)}"
        )
        
        # Kasih tahu sisa limit untuk free user
        if not is_premium:
            remaining = 10 - (daily_count + 1)
            msg += f"\n\n📌 _Sisa {remaining}/10 transaksi gratis hari ini_"
            if remaining <= 3:
                msg += f"\n💎 _Upgrade Premium untuk unlimited!_"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    finally:
        session.close()


# ======================== LAPORAN ========================

async def daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan laporan harian"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    session = get_session(DATABASE_URL)
    try:
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= today_start
        ).order_by(Transaction.created_at.desc()).all()
        
        msg, income, expense, profit = generate_daily_report(transactions)
        
        # Keyboard untuk aksi cepat
        keyboard = [
            [InlineKeyboardButton("📈 Mingguan", callback_data="report_weekly"),
             InlineKeyboardButton("📑 Bulanan", callback_data="report_monthly")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
        ]
        
        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        session.close()


async def weekly_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan laporan mingguan"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    week_start = datetime.datetime.now() - datetime.timedelta(days=datetime.datetime.now().weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    session = get_session(DATABASE_URL)
    try:
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= week_start
        ).order_by(Transaction.created_at.desc()).all()
        
        if not transactions:
            await query.edit_message_text(
                "📭 *Belum ada transaksi minggu ini*\n\n"
                "Mulai catat transaksi, contoh:\n"
                "• `jual nasi goreng 15rb`\n"
                "• `beli telur 25rb`",
                parse_mode="Markdown"
            )
            return
        
        msg = generate_weekly_report(transactions, week_start)
        
        keyboard = [
            [InlineKeyboardButton("📊 Harian", callback_data="report_daily"),
             InlineKeyboardButton("📑 Bulanan", callback_data="report_monthly")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
        ]
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        session.close()


async def monthly_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan laporan bulanan (PREMIUM)"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    session = get_session(DATABASE_URL)
    try:
        db_user = session.query(User).filter_by(telegram_id=user_id).first()
        is_premium = db_user and db_user.is_premium
        
        if not is_premium:
            keyboard = [[InlineKeyboardButton("💰 Lihat Harga Premium", callback_data="premium_info")]]
            await query.edit_message_text(
                "🔒 *Laporan Bulanan adalah fitur PREMIUM*\n\n"
                f"💎 Upgrade Premium Rp{PREMIUM_PRICE:,}/bulan\n"
                "untuk mengakses:\n"
                "✅ Laporan bulanan lengkap\n"
                "✅ Transaksi unlimited\n"
                "✅ Export Excel/PDF\n"
                "✅ Prioritas",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        now = datetime.datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= month_start
        ).order_by(Transaction.created_at.desc()).all()
        
        if not transactions:
            await query.edit_message_text(
                "📭 *Belum ada transaksi bulan ini*",
                parse_mode="Markdown"
            )
            return
        
        msg = generate_monthly_report(transactions, now.month, now.year)
        
        keyboard = [
            [InlineKeyboardButton("📊 Harian", callback_data="report_daily"),
             InlineKeyboardButton("📈 Mingguan", callback_data="report_weekly")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
        ]
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        session.close()


async def daily_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback untuk laporan harian dari button"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    session = get_session(DATABASE_URL)
    try:
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= today_start
        ).order_by(Transaction.created_at.desc()).all()
        
        msg, income, expense, profit = generate_daily_report(transactions)
        
        keyboard = [
            [InlineKeyboardButton("📈 Mingguan", callback_data="report_weekly"),
             InlineKeyboardButton("📑 Bulanan", callback_data="report_monthly")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")]
        ]
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    finally:
        session.close()


# ======================== PREMIUM ========================

async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan info premium"""
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id
    
    session = get_session(DATABASE_URL)
    try:
        db_user = session.query(User).filter_by(telegram_id=user_id).first()
        is_premium = db_user and db_user.is_premium
    finally:
        session.close()
    
    msg = (
        "💰 *PREMIUM*\n\n"
        f"Hanya *Rp{PREMIUM_PRICE:,}/bulan*\n\n"
        "✅ *Transaksi unlimited*\n"
        "✅ *Laporan bulanan*\n"
        "✅ *Export Excel/PDF*\n"
        "✅ *Kategori kustom*\n"
        "✅ *Multiple bisnis*\n"
        "✅ *Prioritas support*\n\n"
        "📱 *Cara bayar:*\n"
        f"🏦 {BANK_NAME}\n"
        f"🔢 {BANK_ACCOUNT}\n"
        f"👤 a.n {BANK_HOLDER}\n"
        f"💰 Rp{PREMIUM_PRICE:,}\n\n"
        "📲 Kirim bukti transfer dengan reply:\n"
        "`/bukti <foto bukti>`\n\n"
        "⏳ Aktivasi maksimal 1x24 jam"
    )
    
    if QRIS_IMAGE_URL:
        msg += f"\n\nAtau scan QRIS:\n{QRIS_IMAGE_URL}"
    
    keyboard = [[InlineKeyboardButton("✅ Saya sudah bayar", callback_data="payment_done")]]
    
    if query:
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


async def premium_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback tombol premium"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "premium_info":
        await premium_info(update, context)
    elif query.data == "payment_done":
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.full_name
        
        session = get_session(DATABASE_URL)
        try:
            req = PremiumRequest(
                user_id=user_id,
                username=username,
                status="PENDING"
            )
            session.add(req)
            session.commit()
            request_id = req.id
        finally:
            session.close()
        
        await query.edit_message_text(
            "✅ *Pembayaran sedang diproses!*\n\n"
            "Admin akan memverifikasi pembayaran kamu.\n"
            "Maksimal 1x24 jam.\n\n"
            "Ada pertanyaan? Hubungi admin.",
            parse_mode="Markdown"
        )
        
        # Kirim notifikasi ke admin
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=(
                f"🆕 *Permintaan Premium Baru!*\n\n"
                f"👤 User: @{username or 'no username'} (ID: {user_id})\n"
                f"📋 Request ID: #{request_id}\n"
                f"💰 Nominal: {format_rupiah(PREMIUM_PRICE)}\n\n"
                f"Ketik:\n"
                f"✅ `/confirm {user_id}` untuk aktivasi\n"
                f"❌ `/reject {user_id}` untuk tolak"
            ),
            parse_mode="Markdown"
        )


# ======================== ADMIN COMMANDS ========================

async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: konfirmasi pembayaran premium"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("❌ Kamu bukan admin!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Cara pakai:*\n`/confirm <telegram_id>`\n`/confirm 123456789`",
            parse_mode="Markdown"
        )
        return
    
    target_id = int(context.args[0])
    
    session = get_session(DATABASE_URL)
    try:
        db_user = session.query(User).filter_by(telegram_id=target_id).first()
        if not db_user:
            await update.message.reply_text("❌ User tidak ditemukan di database!")
            return
        
        db_user.is_premium = True
        db_user.premium_until = datetime.datetime.now() + datetime.timedelta(days=30)
        
        # Update request status
        req = session.query(PremiumRequest).filter_by(
            user_id=target_id, status="PENDING"
        ).first()
        if req:
            req.status = "CONFIRMED"
            req.confirmed_at = datetime.datetime.now()
        
        session.commit()
        
        await update.message.reply_text(
            f"✅ *Premium diaktifkan!*\n\n"
            f"User: {db_user.full_name or db_user.username}\n"
            f"ID: {target_id}\n"
            f"Aktif sampai: {db_user.premium_until.strftime('%d/%m/%Y')}",
            parse_mode="Markdown"
        )
        
        # Notifikasi user
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🎉 *SELAMAT! Akun kamu sudah Premium!*\n\n"
                     "✅ Transaksi unlimited\n"
                     "✅ Laporan bulanan\n"
                     "✅ Export Excel/PDF\n\n"
                     "Terima kasih sudah upgrade! 💪",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Gagal notifikasi user: {e}")
    finally:
        session.close()


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: tolak permintaan premium"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("❌ Kamu bukan admin!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Cara pakai:*\n`/reject <telegram_id>`",
            parse_mode="Markdown"
        )
        return
    
    target_id = int(context.args[0])
    
    session = get_session(DATABASE_URL)
    try:
        req = session.query(PremiumRequest).filter_by(
            user_id=target_id, status="PENDING"
        ).first()
        if req:
            req.status = "REJECTED"
            session.commit()
        
        await update.message.reply_text(f"❌ Permintaan premium user {target_id} ditolak.")
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ *Maaf, pembayaran kamu belum terverifikasi.*\n\n"
                     "Silakan cek kembali bukti transfer dan coba lagi.",
                parse_mode="Markdown"
            )
        except:
            pass
    finally:
        session.close()


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: lihat statistik bot"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("❌ Kamu bukan admin!")
        return
    
    session = get_session(DATABASE_URL)
    try:
        total_users = session.query(User).count()
        premium_users = session.query(User).filter_by(is_premium=True).count()
        total_transactions = session.query(Transaction).count()
        pending_requests = session.query(PremiumRequest).filter_by(status="PENDING").count()
        
        # Transaksi hari ini
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trans = session.query(Transaction).filter(
            Transaction.created_at >= today_start
        ).count()
        
        msg = (
            "📊 *STATISTIK BOT*\n\n"
            f"👥 Total user: {total_users}\n"
            f"⭐ Premium: {premium_users}\n"
            f"📦 Total transaksi: {total_transactions}\n"
            f"📊 Transaksi hari ini: {today_trans}\n"
            f"⏳ Pending premium: {pending_requests}\n\n"
            f"💵 Potensi pendapatan: {format_rupiah(premium_users * PREMIUM_PRICE)}/bln"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        session.close()


# ======================== CALLBACK HANDLER ========================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua callback dari inline keyboard"""
    query = update.callback_query
    data = query.data
    
    if data == "report_daily":
        await daily_report_callback(update, context)
    elif data == "report_weekly":
        await weekly_report_callback(update, context)
    elif data == "report_monthly":
        await monthly_report_callback(update, context)
    elif data == "premium_info" or data == "payment_done":
        await premium_button(update, context)
    elif data == "menu":
        await query.answer()
        user_id = update.effective_user.id
        
        session = get_session(DATABASE_URL)
        try:
            db_user = session.query(User).filter_by(telegram_id=user_id).first()
            is_premium = db_user and db_user.is_premium
        finally:
            session.close()
        
        keyboard = [
            [InlineKeyboardButton("📊 Laporan Harian", callback_data="report_daily")],
            [InlineKeyboardButton("📈 Laporan Mingguan", callback_data="report_weekly")],
            [InlineKeyboardButton("📑 Laporan Bulanan", callback_data="report_monthly")],
            [InlineKeyboardButton("💰 Premium", callback_data="premium_info")],
            [InlineKeyboardButton("❓ Bantuan", callback_data="help")]
        ]
        
        status = "⭐ *PREMIUM*" if is_premium else "🆓 *GRATIS*"
        
        await query.edit_message_text(
            f"📋 *MENU UTAMA*\n\nStatus: {status}\n\nPilih menu di bawah:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data == "help":
        await query.answer()
        await query.edit_message_text(
            "❓ *BANTUAN*\n\n"
            "📝 *Cara catat transaksi:*\n"
            "Ketik langsung seperti chat:\n"
            "• `jual nasi 15rb`\n"
            "• `beli telur 25rb`\n"
            "• `bayar listrik 200rb`\n\n"
            "📊 *Perintah:*\n"
            "• `laporan` - Laporan harian\n"
            "• `cari <kata>` - Cari transaksi\n"
            "• `kategori <nama>` - Set kategori\n\n"
            "💎 *Premium:*\n"
            "Klik \"💰 Premium\" untuk info upgrade\n\n"
            "Ada masalah? Hubungi admin",
            parse_mode="Markdown"
        )


# ======================== HEALTH CHECK ========================

async def search_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cari transaksi berdasarkan keyword"""
    text = update.message.text
    user_id = update.effective_user.id
    keyword = text[5:].strip()  # Ambil setelah "cari "
    
    if not keyword:
        await update.message.reply_text(
            "⚠️ *Cara pakai:*\n`cari <kata kunci>`\nContoh: `cari nasi`",
            parse_mode="Markdown"
        )
        return
    
    session = get_session(DATABASE_URL)
    try:
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.description.ilike(f"%{keyword}%")
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        if not transactions:
            await update.message.reply_text(f"📭 Tidak ada transaksi dengan kata \"{keyword}\"")
            return
        
        msg = f"🔍 *Hasil pencarian:* \"{keyword}\"\n\n"
        for t in transactions:
            emoji = "🟢" if t.type == "INCOME" else "🔴"
            date = t.created_at.strftime("%d/%m %H:%M")
            msg += f"{emoji} {date} | {t.description}: {format_rupiah(t.amount)}\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    finally:
        session.close()


async def set_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set kategori untuk transaksi"""
    text = update.message.text
    keyword = text[9:].strip()
    
    await update.message.reply_text(
        "📌 *Fitur Kategori*\n\n"
        "Fitur ini akan tersedia segera di update premium.\n"
        "Untuk sekarang, kategori otomatis di-set \"Umum\".",
        parse_mode="Markdown"
    )


# ======================== SCHEDULED REPORTS ========================

async def send_daily_reports(app: Application):
    """Kirim laporan harian otomatis ke semua user (setiap jam 20:00)"""
    session = get_session(DATABASE_URL)
    try:
        users = session.query(User).all()
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for user in users:
            transactions = session.query(Transaction).filter(
                Transaction.user_id == user.telegram_id,
                Transaction.created_at >= today_start
            ).all()
            
            if not transactions:
                continue
            
            msg, _, _, _ = generate_daily_report(transactions)
            
            try:
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=msg,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Gagal kirim laporan ke {user.telegram_id}: {e}")
    finally:
        session.close()
