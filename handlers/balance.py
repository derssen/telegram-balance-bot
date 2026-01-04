from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import Service
from services.api_clients import API_CLIENTS
from config import SETTINGS

router = Router()

CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'RUB': '₽',
    'UAH': '₴',
    'Ops': '⚡',
}

# Added 'Make' to the list
DISPLAY_ORDER = [
    'Zadarma',
    'DIDWW',
    'Make',
    'Streamtele',
    'Callii',
    'Wazzup24 Подписка',
    'Wazzup24 Баланс номера'
]

@router.message(Command("balance"))
async def handle_balance_command(message: Message, session: AsyncSession):
    """Handles /balance command."""
    response_parts = ["💰 **Текущие балансы сервисов:**"]
    
    stmt = select(Service)
    result = await session.execute(stmt)
    services_unsorted = result.scalars().all()
    services_map = {s.name: s for s in services_unsorted}
    
    for name in DISPLAY_ORDER:
        service = services_map.get(name)
        if not service: continue
            
        sym = CURRENCY_SYMBOLS.get(service.currency, '$')
        display_amount = 0.0
        status_suffix = ""
        is_subscription = False
        
        # A. API Services
        if name in API_CLIENTS and SETTINGS.API_SERVICE_STATUSES.get(name, True):
            try:
                client = API_CLIENTS[name]
                real_balance = await client.get_balance()
                
                if real_balance is not None:
                    service.last_balance = real_balance
                    await session.commit()
                    display_amount = real_balance
                    status_suffix = "(API)"
                else:
                    display_amount = service.last_balance
                    status_suffix = "(Ошибка API)"
            except Exception:
                display_amount = service.last_balance
                status_suffix = "(Сбой API)"
        
        # B. Subscriptions
        elif service.monthly_fee and service.monthly_fee > 0:
            display_amount = service.monthly_fee
            is_subscription = True
        
        # C. Manual
        else:
            display_amount = service.last_balance
            status_suffix = "(примерно)"

        # Formatting
        amount_fmt = f"{int(display_amount)}" if service.currency == 'Ops' else f"{display_amount:.2f}"
        
        if is_subscription:
            line = f"• **{name}:** Подписка: `{sym}{amount_fmt}`"
        else:
            line = f"• **{name}:** `{sym}{amount_fmt}` {status_suffix}"
            
        response_parts.append(line)

        # Alerts
        alert_date = service.next_alert_date or service.next_monthly_alert
        if alert_date:
            date_str = alert_date.strftime('%Y-%m-%d')
            label = "Сброс:" if name == 'Make' else "След. оплата:"
            response_parts.append(f"  _{label}_ {date_str}")

    await message.answer('\n'.join(response_parts))