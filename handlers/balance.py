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
    'UAH': '₴'
}

# Display order configuration
DISPLAY_ORDER = [
    'Zadarma',
    'DIDWW',
    'Streamtele',
    'Callii',
    'Wazzup24 Подписка',
    'Wazzup24 Баланс номера'
]

@router.message(Command("balance"))
async def handle_balance_command(message: Message, session: AsyncSession):
    """
    Handles /balance command. Fetches data from APIs and DB to show a summary.
    """
    response_parts = ["💰 **Текущие балансы сервисов:**"]
    
    # 1. Fetch all services
    stmt = select(Service)
    result = await session.execute(stmt)
    services_unsorted = result.scalars().all()
    
    services_map = {s.name: s for s in services_unsorted}
    
    # 2. Iterate based on predefined order
    for name in DISPLAY_ORDER:
        service = services_map.get(name)
        if not service:
            continue
            
        sym = CURRENCY_SYMBOLS.get(service.currency, '$')
        
        display_amount = 0.0
        status_suffix = ""
        is_subscription = False
        
        # A. API Services (Zadarma, DIDWW)
        if name in API_CLIENTS and SETTINGS.API_SERVICE_STATUSES.get(name, True):
            try:
                client = API_CLIENTS[name]
                real_balance = await client.get_balance()
                
                # Update DB with fresh data
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
        
        # B. Subscription Services
        elif service.monthly_fee and service.monthly_fee > 0:
            display_amount = service.monthly_fee
            is_subscription = True
            
        # C. Manual Balance Services
        else:
            display_amount = service.last_balance
            status_suffix = "(примерно)"

        # Formatting Output
        if is_subscription:
            line = f"• **{name}:** Подписка: {sym}{display_amount:.2f}"
        else:
            line = f"• **{name}:** {sym}{display_amount:.2f} {status_suffix}"
            
        response_parts.append(line)

        # Append Next Alert Date if available
        alert_date = service.next_alert_date or service.next_monthly_alert
        if alert_date:
            date_str = alert_date.strftime('%Y-%m-%d')
            response_parts.append(f"  _След. оплата:_ {date_str}")

    await message.answer('\n'.join(response_parts))