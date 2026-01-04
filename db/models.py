from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from datetime import datetime
import pytz
from config import SETTINGS

TIMEZONE = pytz.timezone('Asia/Makassar') 

Base = declarative_base()

class Service(Base):
    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    last_balance = Column(Float, default=0.0)
    low_balance_alert_sent = Column(Boolean, default=False)
    currency = Column(String, default="USD")
    daily_cost = Column(Float, nullable=True)
    monthly_fee = Column(Float, nullable=True)
    next_alert_date = Column(DateTime, nullable=True) 
    next_monthly_alert = Column(DateTime, nullable=True)
    last_alert_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Service(name='{self.name}', balance={self.last_balance})>"

async def init_db(database_url: str):
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def initialize_services(SessionLocal):
    async with SessionLocal() as session:
        # Schema migration
        result = await session.execute(text("PRAGMA table_info(services)"))
        columns = {row[1] for row in result.fetchall()}
        alter_statements = []
        
        for col in ['currency', 'daily_cost', 'monthly_fee', 'next_monthly_alert', 'last_alert_at']:
            if col not in columns:
                ctype = 'DATETIME' if 'alert' in col else ('FLOAT' if 'cost' in col or 'fee' in col else 'VARCHAR')
                alter_statements.append(f"ALTER TABLE services ADD COLUMN {col} {ctype}")
        
        for stmt in alter_statements:
            try: await session.execute(text(stmt))
            except Exception: pass
        if alter_statements: await session.commit()

        # Seed Data
        services_to_add = [
            {'name': 'Zadarma', 'last_balance': 0.0, 'currency': 'USD'},
            {'name': 'DIDWW', 'last_balance': 0.0, 'currency': 'USD', 'monthly_fee': SETTINGS.DIDWW_MONTHLY_FEE, 'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 20, 10, 0))},
            {'name': 'Make', 'last_balance': 0.0, 'currency': 'Ops'}, # NEW
            {'name': 'Wazzup24 Подписка', 'last_balance': 0.0, 'currency': 'RUB', 'monthly_fee': SETTINGS.WAZZUP_MONTHLY_FEE, 'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0))},
            {'name': 'Wazzup24 Баланс номера', 'last_balance': 0.0, 'currency': 'RUB', 'daily_cost': SETTINGS.WAZZUP_DAILY_COST, 'next_alert_date': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0))},
            {'name': 'Callii', 'next_alert_date': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)), 'currency': 'USD', 'daily_cost': SETTINGS.CALLII_DAILY_COST}, 
            {'name': 'Streamtele', 'currency': 'UAH', 'monthly_fee': SETTINGS.STREAMTELE_MONTHLY_FEE, 'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0))},
        ]

        for data in services_to_add:
            stmt = select(Service).where(Service.name == data['name'])
            exists = (await session.execute(stmt)).scalar_one_or_none()
            if not exists:
                session.add(Service(name=data['name'], **{k: v for k, v in data.items() if k != 'name'}))
        
        await session.commit()