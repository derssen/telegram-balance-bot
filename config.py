import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Settings:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    TARGET_CHAT_ID: int = int(os.getenv("TARGET_CHAT_ID", -1)) # Важный ID чата
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///balances.sqlite3")
    
    # API Credentials
    ZADARMA_KEY: str = os.getenv("ZADARMA_KEY")
    ZADARMA_SECRET: str = os.getenv("ZADARMA_SECRET")
    WAZZUP_TOKEN: str = os.getenv("WAZZUP_TOKEN")
    DIDWW_KEY: str = os.getenv("DIDWW_KEY")
    
    # Constants
    LOW_BALANCE_THRESHOLD: float = 10.0
    MIN_TOP_UP_AMOUNT: float = 5.0
    CALLII_DAILY_COST: float = float(os.getenv("CALLII_DAILY_COST", 2.2))
    WAZZUP_DAILY_COST: float = float(os.getenv("WAZZUP_DAILY_COST", 400.0))
    STREAMTELE_MONTHLY_FEE: float = float(os.getenv("STREAMTELE_MONTHLY_FEE", 1500.0))
    WAZZUP_MONTHLY_FEE: float = float(os.getenv("WAZZUP_MONTHLY_FEE", 6000.0))
    DIDWW_MONTHLY_FEE: float = float(os.getenv("DIDWW_MONTHLY_FEE", 45.0))
    WAZZUP_PHONE: str = os.getenv("WAZZUP_PHONE", "+6281239838440")
    SERVICE_CURRENCIES: dict = {
        'Zadarma': 'USD',
        'Wazzup24 Подписка': 'RUB',
        'Wazzup24 Баланс номера': 'RUB',
        'DIDWW': 'USD',
        'Streamtele': 'UAH',
        'Callii': 'USD',
    }
    CURRENCY_SIGNS: dict = {
        'USD': '$',
        'UAH': '₴',
        'RUB': '₽',
    }
    # Статус активности API-сервисов
    API_SERVICE_STATUSES: dict = {
        'Zadarma': os.getenv("ZADARMA_ENABLED", "True").lower() in ('true', '1', 't'),
        'DIDWW': os.getenv("DIDWW_ENABLED", "True").lower() in ('true', '1', 't'),
    }

SETTINGS = Settings()

# Проверка, что критические переменные загружены
if not SETTINGS.BOT_TOKEN or SETTINGS.TARGET_CHAT_ID == -1:
    raise ValueError("BOT_TOKEN or TARGET_CHAT_ID is not configured correctly.")