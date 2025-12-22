from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import Service
from services.api_clients import API_CLIENTS
from config import SETTINGS

router = Router()

# Карта символов валют
CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'RUB': '₽',
    'UAH': '₴'
}

@router.message(Command("balance"))
async def handle_balance_command(message: Message, session: AsyncSession):
    
    response_parts = ["💰 **Текущие балансы сервисов:**"]
    
    # 1. Загружаем ВСЕ сервисы из БД
    stmt = select(Service).order_by(Service.id)
    result = await session.execute(stmt)
    services = result.scalars().all()

    if not services:
        await message.answer("Сервисы не найдены в базе данных.")
        return

    for service in services:
        # Получаем красивый символ валюты
        currency_symbol = CURRENCY_SYMBOLS.get(service.currency, service.currency or '$')
        
        # --- Логика для API сервисов ---
        # Если имя сервиса есть в списке API клиентов, пробуем обновить баланс
        # НО! Wazzup у тебя разбит на две части в БД. API клиент возвращает только один баланс.
        # Поэтому API опрашиваем только если точное совпадение имени или особая логика.
        
        real_balance = None
        is_api = False
        
        if service.name in API_CLIENTS and SETTINGS.API_SERVICE_STATUSES.get(service.name, True):
            try:
                client = API_CLIENTS[service.name]
                real_balance = await client.get_balance()
                
                # Обновляем в БД, чтобы данные были свежими
                service.last_balance = real_balance
                is_api = True
            except Exception:
                # Если ошибка API, используем то, что было в базе
                real_balance = service.last_balance
        else:
            # Для ручных сервисов (Callii, Streamtele, Wazzup Подписки) берем из БД
            real_balance = service.last_balance

        # Сохраняем обновление в БД
        await session.commit()

        # --- Формирование строки вывода ---
        
        status_text = "(API)" if is_api else "(примерно)"
        # Если это подписка (есть monthly_fee), меняем формат вывода
        if service.monthly_fee and service.monthly_fee > 0:
             status_text = f"Подписка: {currency_symbol}{service.monthly_fee:.2f}"
        
        line = f"• **{service.name}:** {currency_symbol}{real_balance:.2f} {status_text}"
        response_parts.append(line)

        # Добавляем дату следующей оплаты, если есть
        # Приоритет: next_alert_date (для Callii) или next_monthly_alert (для подписок)
        alert_date = service.next_alert_date or service.next_monthly_alert
        
        if alert_date:
            date_str = alert_date.strftime('%Y-%m-%d')
            response_parts.append(f"  _След. оплата:_ {date_str}")

    await message.answer('\n'.join(response_parts))