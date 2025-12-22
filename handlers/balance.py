from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import Service, TIMEZONE
from services.api_clients import API_CLIENTS
from config import SETTINGS # Новый импорт

router = Router()

CURRENCY_SIGNS = SETTINGS.CURRENCY_SIGNS
MANUAL_APPROX_VALUES = {
    'Streamtele': SETTINGS.STREAMTELE_MONTHLY_FEE,
    'Callii': 10.0,
    'Wazzup24 Подписка': SETTINGS.WAZZUP_MONTHLY_FEE,
    'Wazzup24 Баланс номера': SETTINGS.WAZZUP_DAILY_COST,
}
MANUAL_SERVICES = ('Streamtele', 'Callii', 'Wazzup24 Подписка', 'Wazzup24 Баланс номера')

@router.message(Command("balance"))
async def handle_balance_command(message: Message, session: AsyncSession):
    
    response_parts = ["💰 **Текущие балансы сервисов:**"]
    
    # --- 1. Проверка API-сервисов ---
    for service_name, client in API_CLIENTS.items():
        
        if not SETTINGS.API_SERVICE_STATUSES.get(service_name, False):
            # Сервис отключен
            response_parts.append(f"• **{service_name}:** _Отключен в конфигурации_ 🚫")
            continue
            
        try:
            current_balance = await client.get_balance()
            if current_balance is None:
                response_parts.append(f"• **{service_name}:** _Баланс через API недоступен_ ⚙️")
            else:
                currency = SETTINGS.SERVICE_CURRENCIES.get(service_name, 'USD')
                symbol = CURRENCY_SIGNS.get(currency, currency)
                response_parts.append(f"• **{service_name}:** `{symbol}{current_balance:.2f}` (API)")
        except Exception as e:
            response_parts.append(f"• **{service_name}:** Ошибка API (см. логи)")

    # --- 2. Проверка ручных сервисов ---
    stmt = select(Service).where(Service.name.in_(MANUAL_SERVICES))
    manual_result = await session.execute(stmt)
    manual_services = {service.name: service for service in manual_result.scalars()}

    for name in MANUAL_SERVICES:
        approx = MANUAL_APPROX_VALUES.get(name, 0.0)
        service = manual_services.get(name)
        currency = SETTINGS.SERVICE_CURRENCIES.get(name, 'USD')
        symbol = CURRENCY_SIGNS.get(currency, currency)

        if name == 'Callii':
            next_date = service.next_alert_date.astimezone(TIMEZONE).strftime('%Y-%m-%d') if service and service.next_alert_date else "N/A"
            response_parts.append(
                f"• **{name}:** `{symbol}{approx:.2f}` (примерно)\n"
                f"  _След. оплата:_ **{next_date}**"
            )
        elif name == 'Streamtele':
            next_monthly = service.next_monthly_alert.astimezone(TIMEZONE).strftime('%Y-%m-%d') if service and service.next_monthly_alert else "N/A"
            response_parts.append(
                f"• **{name}:** Подписка: `{symbol}{approx:.2f}`)\n"
                f"  _След. оплата:_ **{next_monthly}**"
            )
        elif name == 'Wazzup24 Подписка':
            next_monthly = service.next_monthly_alert.astimezone(TIMEZONE).strftime('%Y-%m-%d') if service and service.next_monthly_alert else "N/A"
            response_parts.append(
                f"• **{name}:** `{symbol}{approx:.2f}`\n"
                f"  _След. оплата:_ **{next_monthly}**"
            )
        elif name == 'Wazzup24 Баланс номера':
            next_daily = service.next_alert_date.astimezone(TIMEZONE).strftime('%Y-%m-%d') if service and service.next_alert_date else "N/A"
            current_balance = service.last_balance if service and service.last_balance is not None else approx
            response_parts.append(
                f"• **{name}:** `{symbol}{current_balance:.1f}`\n"
                f"  _След. оплата:_ **{next_daily}**"
            )


    await message.answer('\n'.join(response_parts))