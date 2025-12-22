from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import pytz
from config import SETTINGS

# Используем вашу таймзону
TIMEZONE = pytz.timezone('Asia/Makassar') 

Base = declarative_base()

class Service(Base):
    __tablename__ = 'services'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    
    # Мониторинг баланса
    last_balance = Column(Float, default=0.0)
    low_balance_alert_sent = Column(Boolean, default=False)
    
    # Новые поля (согласно твоему скриншоту)
    currency = Column(String, default="USD")     # USD, RUB, UAH
    daily_cost = Column(Float, nullable=True)    # Расход в день
    monthly_fee = Column(Float, nullable=True)   # Ежемесячный платеж
    
    # Даты оповещений
    next_alert_date = Column(DateTime, nullable=True) 
    next_monthly_alert = Column(DateTime, nullable=True) # Для ежемесячных подписок

    def __repr__(self):
        return f"<Service(name='{self.name}', balance={self.last_balance})>"

# Инициализация
async def init_db(database_url: str):
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return AsyncSessionLocal

# Вспомогательная функция для добавления начальных данных
async def initialize_services(SessionLocal):
    async with SessionLocal() as session:
        # --- simple sqlite migration to add new columns if missing ---
        pragma_stmt = text("PRAGMA table_info(services)")
        result = await session.execute(pragma_stmt)
        columns = {row[1] for row in result.fetchall()}

        alter_statements = []
        if 'currency' not in columns:
            alter_statements.append("ALTER TABLE services ADD COLUMN currency VARCHAR")
        if 'daily_cost' not in columns:
            alter_statements.append("ALTER TABLE services ADD COLUMN daily_cost FLOAT")
        if 'monthly_fee' not in columns:
            alter_statements.append("ALTER TABLE services ADD COLUMN monthly_fee FLOAT")
        if 'next_monthly_alert' not in columns:
            alter_statements.append("ALTER TABLE services ADD COLUMN next_monthly_alert DATETIME")

        for stmt in alter_statements:
            try:
                await session.execute(text(stmt))
            except Exception:
                # ignore if already exists or other minor issues
                pass
        if alter_statements:
            await session.commit()

        services_to_add = [
            # API сервисы
            {
                'name': 'Zadarma',
                'last_balance': 0.0,
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Zadarma', 'USD'),
            },
            # Wazzup разделён: подписка (ежемесячно) и баланс номера (ежедневный расход)
            {
                'name': 'Wazzup24 Подписка',
                'last_balance': 0.0,
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Wazzup24 Подписка', 'RUB'),
                'monthly_fee': SETTINGS.WAZZUP_MONTHLY_FEE,
                'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)),
            },
            {
                'name': 'Wazzup24 Баланс номера',
                'last_balance': 0.0,
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Wazzup24 Баланс номера', 'RUB'),
                'daily_cost': SETTINGS.WAZZUP_DAILY_COST,
                'next_alert_date': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)),
            },
            {
                'name': 'DIDWW',
                'last_balance': 0.0,
                'currency': SETTINGS.SERVICE_CURRENCIES.get('DIDWW', 'USD'),
                'monthly_fee': SETTINGS.DIDWW_MONTHLY_FEE,
                'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 20, 10, 0)),
            },
            # Callii (Управляемый FSM)
            {
                'name': 'Callii',
                'next_alert_date': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)),
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Callii', 'USD'),
                'daily_cost': SETTINGS.CALLII_DAILY_COST,
            }, 
            # Streamtele (Ежемесячное напоминание)
            {
                'name': 'Streamtele',
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Streamtele', 'UAH'),
                'monthly_fee': SETTINGS.STREAMTELE_MONTHLY_FEE,
                'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)),
            },
        ]

        from sqlalchemy.future import select # Дополнительный импорт нужен для 'select'
        
        for data in services_to_add:
            # ИСПРАВЛЕНО: Используем select и where для поиска по уникальному полю 'name'
            stmt = select(Service).filter(Service.name == data['name'])
            result = await session.execute(stmt)
            exists = result.scalar_one_or_none()
            
            if not exists:
                session.add(Service(name=data['name'], **{k: v for k, v in data.items() if k != 'name'}))
        
        await session.commit()