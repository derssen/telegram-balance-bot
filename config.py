import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration and constants."""
    
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    TARGET_CHAT_ID: int = int(os.getenv("TARGET_CHAT_ID", -1))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_db.sqlite3")
    
    # API Credentials
    ZADARMA_KEY: str = os.getenv("ZADARMA_KEY")
    ZADARMA_SECRET: str = os.getenv("ZADARMA_SECRET")
    WAZZUP_TOKEN: str = os.getenv("WAZZUP_TOKEN")
    DIDWW_KEY: str = os.getenv("DIDWW_KEY")
    
    # Make Credentials & Config
    MAKE_API_KEY: str = os.getenv("MAKE_API_KEY")
    MAKE_ORG_ID: str = os.getenv("MAKE_ORG_ID")
    MAKE_ZONE: str = os.getenv("MAKE_ZONE", "eu1") # eu1 or us1
    
    # Financial Constants
    LOW_BALANCE_THRESHOLD: float = 10.0
    MIN_TOP_UP_AMOUNT: float = 5.0
    
    # Service Costs & Fees
    CALLII_DAILY_COST: float = float(os.getenv("CALLII_DAILY_COST", 2.2))
    WAZZUP_DAILY_COST: float = float(os.getenv("WAZZUP_DAILY_COST", 400.0))
    STREAMTELE_MONTHLY_FEE: float = float(os.getenv("STREAMTELE_MONTHLY_FEE", 1500.0))
    WAZZUP_MONTHLY_FEE: float = float(os.getenv("WAZZUP_MONTHLY_FEE", 6000.0))
    DIDWW_MONTHLY_FEE: float = float(os.getenv("DIDWW_MONTHLY_FEE", 45.0))
    
    # Service Info
    WAZZUP_PHONE: str = os.getenv("WAZZUP_PHONE", "+6281239838440")
    
    # Currency Mapping
    SERVICE_CURRENCIES: dict = {
        'Zadarma': 'USD',
        'Wazzup24 Подписка': 'RUB',
        'Wazzup24 Баланс номера': 'RUB',
        'DIDWW': 'USD',
        'Streamtele': 'UAH',
        'Callii': 'USD',
        'Make': 'Ops',
    }
    
    CURRENCY_SIGNS: dict = {
        'USD': '$',
        'UAH': '₴',
        'RUB': '₽',
        'Ops': '⚡',
    }
    
    # API Service Toggle (Auto-detect based on keys)
    API_SERVICE_STATUSES: dict = {
        'Zadarma': bool(os.getenv("ZADARMA_KEY") and os.getenv("ZADARMA_SECRET")),
        'DIDWW': bool(os.getenv("DIDWW_KEY")),
        'Make': bool(os.getenv("MAKE_API_KEY") and os.getenv("MAKE_ORG_ID")),
    }

SETTINGS = Config()

if not SETTINGS.BOT_TOKEN or SETTINGS.TARGET_CHAT_ID == -1:
    raise ValueError("Critical configuration missing: BOT_TOKEN or TARGET_CHAT_ID.")