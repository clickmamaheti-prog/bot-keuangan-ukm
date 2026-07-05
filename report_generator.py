"""
Report generator untuk laporan keuangan
"""
import datetime
from typing import List, Tuple
from database import Transaction
from parser import format_rupiah


def generate_daily_report(transactions: List[Transaction]) -> Tuple[str, float, float, float]:
    """
    Generate laporan harian
    
    Returns:
        (pesan_laporan, total_pemasukan, total_pengeluaran, laba)
    """
    total_income = sum(t.amount for t in transactions if t.type == "INCOME")
    total_expense = sum(t.amount for t in transactions if t.type == "EXPENSE")
    profit = total_income - total_expense
    
    # Detail per kategori
    income_details = [t for t in transactions if t.type == "INCOME"]
    expense_details = [t for t in transactions if t.type == "EXPENSE"]
    
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    
    msg = f"📊 *LAPORAN HARIAN*\n📅 {today}\n\n"
    msg += "━━━━━━━━━━━━━━━━━\n"
    
    msg += f"💚 *PEMASUKAN:*\n"
    if income_details:
        for t in income_details[:10]:
            msg += f"  • {t.description}: {format_rupiah(t.amount)}\n"
    else:
        msg += "  _(Belum ada pemasukan)_\n"
    
    msg += f"\n❤️ *PENGELUARAN:*\n"
    if expense_details:
        for t in expense_details[:10]:
            msg += f"  • {t.description}: {format_rupiah(t.amount)}\n"
    else:
        msg += "  _(Belum ada pengeluaran)_\n"
    
    msg += "\n━━━━━━━━━━━━━━━━━\n"
    msg += f"💚 Pemasukan: {format_rupiah(total_income)}\n"
    msg += f"❤️ Pengeluaran: {format_rupiah(total_expense)}\n"
    
    if profit >= 0:
        msg += f"✅ *Laba: {format_rupiah(profit)}*\n"
    else:
        msg += f"❌ *Rugi: {format_rupiah(abs(profit))}*\n"
    
    msg += "\n💡 _Ketik /menu untuk opsi lainnya_"
    
    return msg, total_income, total_expense, profit


def generate_weekly_report(transactions: List[Transaction], week_start: datetime.datetime) -> str:
    """
    Generate laporan mingguan
    """
    total_income = sum(t.amount for t in transactions if t.type == "INCOME")
    total_expense = sum(t.amount for t in transactions if t.type == "EXPENSE")
    profit = total_income - total_expense
    transaction_count = len(transactions)
    
    week_end = week_start + datetime.timedelta(days=6)
    date_range = f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m/%Y')}"
    
    # Daily breakdown
    daily_data = {}
    for t in transactions:
        day_key = t.created_at.strftime("%A")
        if day_key not in daily_data:
            daily_data[day_key] = {"income": 0, "expense": 0}
        if t.type == "INCOME":
            daily_data[day_key]["income"] += t.amount
        else:
            daily_data[day_key]["expense"] += t.amount
    
    msg = f"📈 *LAPORAN MINGGUAN*\n📅 {date_range}\n\n"
    msg += "━━━━━━━━━━━━━━━━━\n"
    
    msg += f"📋 *Ringkasan:*\n"
    msg += f"  📦 Total transaksi: {transaction_count}x\n"
    msg += f"  💚 Pemasukan: {format_rupiah(total_income)}\n"
    msg += f"  ❤️ Pengeluaran: {format_rupiah(total_expense)}\n"
    
    if profit >= 0:
        msg += f"  ✅ *Laba: {format_rupiah(profit)}*\n"
    else:
        msg += f"  ❌ *Rugi: {format_rupiah(abs(profit))}*\n"
    
    msg += "\n📆 *Per Hari:*\n"
    day_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    # Map English day names to Indonesian
    en_to_id = {
        "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
        "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
    }
    for day_en, day_id in en_to_id.items():
        if day_en in daily_data:
            d = daily_data[day_en]
            msg += f"  {day_id}: 💚{format_rupiah(d['income'])} / ❤️{format_rupiah(d['expense'])}\n"
    
    msg += "\n💡 _Ketik /menu untuk opsi lainnya_"
    return msg


def generate_monthly_report(transactions: List[Transaction], month: int, year: int) -> str:
    """
    Generate laporan bulanan (PREMIUM FEATURE)
    """
    total_income = sum(t.amount for t in transactions if t.type == "INCOME")
    total_expense = sum(t.amount for t in transactions if t.type == "EXPENSE")
    profit = total_income - total_expense
    transaction_count = len(transactions)
    
    # Top spending categories
    expense_by_desc = {}
    for t in transactions:
        if t.type == "EXPENSE":
            key = t.description or "Lainnya"
            if key not in expense_by_desc:
                expense_by_desc[key] = 0
            expense_by_desc[key] += t.amount
    
    top_expenses = sorted(expense_by_desc.items(), key=lambda x: x[1], reverse=True)[:5]
    
    month_names = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                   "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    
    msg = f"📊 *LAPORAN BULANAN*\n📅 {month_names[month]} {year}\n\n"
    msg += "━━━━━━━━━━━━━━━━━\n"
    
    msg += f"📋 *Ringkasan:*\n"
    msg += f"  📦 Total transaksi: {transaction_count}x\n"
    msg += f"  💚 Pemasukan: {format_rupiah(total_income)}\n"
    msg += f"  ❤️ Pengeluaran: {format_rupiah(total_expense)}\n"
    
    if profit >= 0:
        msg += f"  ✅ *Laba: {format_rupiah(profit)}*\n"
    else:
        msg += f"  ❌ *Rugi: {format_rupiah(abs(profit))}*\n"
    
    msg += f"\n📈 *Rata-rata harian:*\n"
    days_in_month = 30
    msg += f"  💚 Rata pemasukan: {format_rupiah(total_income/days_in_month)}/hari\n"
    msg += f"  ❤️ Rata pengeluaran: {format_rupiah(total_expense/days_in_month)}/hari\n"
    
    if top_expenses:
        msg += "\n🔥 *Top Pengeluaran:*\n"
        for desc, amount in top_expenses:
            pct = (amount / total_expense * 100) if total_expense > 0 else 0
            msg += f"  • {desc}: {format_rupiah(amount)} ({pct:.0f}%)\n"
    
    msg += f"\n📊 *Neraca: *\n"
    msg += f"  💰 Saldo akhir: {format_rupiah(profit)}\n"
    
    msg += "\n💡 _Ketik /menu untuk opsi lainnya_"
    return msg
