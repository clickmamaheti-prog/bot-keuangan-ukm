"""
Parser sederhana untuk mendeteksi transaksi dari chat user
"""
import re


# Keyword untuk deteksi jenis transaksi
INCOME_KEYWORDS = [
    "jual", "dapat", "terima", "bayar", "income", "masuk", "pendapatan",
    "gaji", "bonus", "komisi", "hasil", "cuan", "laba", "untung",
    "transfer masuk", "diterima", "pemasukan", "fee", "honor", "upah"
]

EXPENSE_KEYWORDS = [
    "beli", "bayar", "keluar", "modal", "biaya", "pengeluaran", "expense",
    "cost", "harga", "belanja", "bayarin", "transfer keluar", "dibayar",
    "ongkos", "ongkir", "sewa", "listrik", "air", "pulsa", "kuota",
    "bensin", "makan", "minum", "gaji karyawan", "bon", "hutang"
]

# Pattern untuk mendeteksi nominal uang
MONEY_PATTERN = r'(\d[\d.,]*)\s*(rb|k|ribu|jt|juta|j)?'
MONEY_CLEAN = r'[\d.,]+'


def parse_message(text: str) -> dict:
    """
    Parse pesan user untuk mendeteksi transaksi.
    
    Contoh input:
    - "jual nasi goreng 15rb"
    - "beli telur 25000"
    - "bayar listrik 200rb"
    - "pendapatan jualan hari ini 500k"
    
    Returns:
        dict dengan keys: type, amount, description, raw_text
        atau None jika bukan transaksi
    """
    if not text:
        return None
    
    text = text.strip().lower()
    
    # Deteksi jenis transaksi dari keyword
    trans_type = detect_type(text)
    if not trans_type:
        return None
    
    # Ekstrak nominal uang
    amount = extract_amount(text)
    if amount is None or amount <= 0:
        return None
    
    # Bersihkan deskripsi (hapus keyword + nominal)
    description = clean_description(text, trans_type, amount)
    
    return {
        "type": trans_type,
        "amount": amount,
        "description": description,
        "raw_text": text
    }


def detect_type(text: str) -> str:
    """Deteksi apakah ini pemasukan atau pengeluaran"""
    # Cek keyword INCOME lebih dulu
    for kw in INCOME_KEYWORDS:
        if kw in text:
            return "INCOME"
    
    # Cek keyword EXPENSE
    for kw in EXPENSE_KEYWORDS:
        if kw in text:
            return "EXPENSE"
    
    return None


def extract_amount(text: str) -> float:
    """Ekstrak nominal uang dari teks"""
    # Cari pola seperti: 15rb, 25.000, 500k, 1jt, 2.5jt
    matches = re.findall(r'(\d+[\d,.]*)\s*(rb|k|ribu|jt|juta|j)?', text)
    
    if not matches:
        # Coba cari angka biasa
        nums = re.findall(r'\d+', text)
        if nums:
            return float(nums[-1])
        return None
    
    amount_str, suffix = matches[-1]
    
    # Bersihkan dari koma/titik
    amount_str = amount_str.replace(',', '.').replace(' ', '')
    
    try:
        amount = float(amount_str)
    except ValueError:
        return None
    
    # Konversi suffix
    suffix = suffix.strip().lower() if suffix else ""
    if suffix in ("rb", "k", "ribu"):
        amount *= 1000
    elif suffix in ("jt", "juta", "j"):
        amount *= 1_000_000
    
    return amount


def clean_description(text: str, trans_type: str, amount: float) -> str:
    """Bersihkan deskripsi dari keyword transaksi dan nominal"""
    # Hapus nominal dari teks
    cleaned = re.sub(MONEY_PATTERN, '', text, flags=re.IGNORECASE)
    
    # Hapus keyword yang terdeteksi (case insensitive)
    keywords = INCOME_KEYWORDS if trans_type == "INCOME" else EXPENSE_KEYWORDS
    for kw in keywords:
        cleaned = cleaned.replace(kw, '')
    
    # Bersihkan spasi berlebih
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if not cleaned:
        # Fallback: tipe transaksi saja
        return "Transaksi"
    
    return cleaned.capitalize()


def format_rupiah(amount: float) -> str:
    """Format angka ke Rupiah: 15000 -> Rp15.000"""
    return f"Rp{amount:,.0f}".replace(",", ".")
