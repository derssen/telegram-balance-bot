from datetime import datetime
import pytz
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select

from config import SETTINGS

# Define Timezone
TIMEZONE = pytz.timezone('Asia/Makassar')

Base = declarative_base()

class Service(Base):
    """Database model representing a tracked service."""
    __tablename__ = 'services'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    
    # Balance Monitoring
    last_balance = Column(Float, default=0.0)
    low_balance_alert_sent = Column(Boolean, default=False)
    
    # Financial Configuration
    currency = Column(String, default="USD")     # USD, RUB, UAH
    daily_cost = Column(Float, nullable=True)    # Estimated daily cost
    monthly_fee = Column(Float, nullable=True)   # Fixed monthly fee
    
    # Alert Schedule
    next_alert_date = Column(DateTime, nullable=True) 
    next_monthly_alert = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Service(name='{self.name}', balance={self.last_balance})>"

async def init_db(database_url: str) -> sessionmaker:
    """Initialize the database engine and session factory."""
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return async_session

async def initialize_services(session_factory) -> None:
    """
    Populate the database with default services and perform schema migrations if necessary.
    """
    async with session_factory() as session:
        # 1. Simple schema migration (add columns if missing)
        pragma_stmt = text("PRAGMA table_info(services)")
        result = await session.execute(pragma_stmt)
        existing_columns = {row[1] for row in result.fetchall()}

        alter_statements = []
        required_columns = ['currency', 'daily_cost', 'monthly_fee', 'next_monthly_alert']
        
        for col in required_columns:
            if col not in existing_columns:
                col_type = 'DATETIME' if 'next' in col else ('FLOAT' if 'cost' in col or 'fee' in col else 'VARCHAR')
                alter_statements.append(f"ALTER TABLE services ADD COLUMN {col} {col_type}")

        for stmt in alter_statements:
            try:
                await session.execute(text(stmt))
            except Exception:
                pass # Ignore errors if column exists
        
        if alter_statements:
            await session.commit()

        # 2. Seed default data
        services_to_seed = [
            {
                'name': 'Zadarma',
                'last_balance': 0.0,
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Zadarma', 'USD'),
            },
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
            {
                'name': 'Callii',
                'next_alert_date': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)),
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Callii', 'USD'),
                'daily_cost': SETTINGS.CALLII_DAILY_COST,
            }, 
            {
                'name': 'Streamtele',
                'currency': SETTINGS.SERVICE_CURRENCIES.get('Streamtele', 'UAH'),
                'monthly_fee': SETTINGS.STREAMTELE_MONTHLY_FEE,
                'next_monthly_alert': TIMEZONE.localize(datetime(2025, 12, 11, 10, 0)),
            },
        ]

        for data in services_to_seed:
            stmt = select(Service).filter(Service.name == data['name'])
            result = await session.execute(stmt)
            exists = result.scalar_one_or_none()
            
            if not exists:
                session.add(Service(name=data['name'], **{k: v for k, v in data.items() if k != 'name'}))
        
        await session.commit()