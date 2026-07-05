"""
Database models untuk Bot Laporan Keuangan UKM
"""
import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, DateTime, Boolean, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    language = Column(String(10), default="id")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)  # telegram_id
    type = Column(String(20), nullable=False)  # INCOME / EXPENSE
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    date = Column(DateTime, default=datetime.datetime.utcnow)  # tanggal transaksi


class PremiumRequest(Base):
    __tablename__ = "premium_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    status = Column(String(20), default="PENDING")  # PENDING / CONFIRMED / REJECTED
    payment_method = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)


def init_db(database_url):
    """Inisialisasi koneksi database"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def get_session(database_url):
    """Buat session database baru"""
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()
