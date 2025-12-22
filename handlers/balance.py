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

# Жесткий порядок отображения (как ты привык)
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
    
    response_parts = ["💰 **Текущие балансы сервисов:**"]
    
    # 1. Загружаем сервисы
    stmt = select(Service)
    result = await session.execute(stmt)
    services_unsorted = result.scalars().all()
    
    # Превращаем в словарь для удобной сортировки: { 'Zadarma': ServiceObj, ... }
    services_map = {s.name: s for s in services_unsorted}
    
    # 2. Проходимся строго по нашему списку порядка
    for name in DISPLAY_ORDER:
        service = services_map.get(name)
        if not service:
            continue # Если вдруг сервиса нет в базе, пропускаем
            
        # Получаем символ валюты
        sym = CURRENCY_SYMBOLS.get(service.currency, '$')
        
        # Переменные для вывода
        display_amount = 0.0
        status_suffix = ""
        is_subscription = False
        
        # --- ЛОГИКА ОПРЕДЕЛЕНИЯ ТИПА ---
        
        # A. Это API сервис? (Zadarma, DIDWW)
        if name in API_CLIENTS and SETTINGS.API_SERVICE_STATUSES.get(name, True):
            try:
                client = API_CLIENTS[name]
                real_balance = await client.get_balance()
                
                # Обновляем БД
                service.last_balance = real_balance
                await session.commit()
                
                display_amount = real_balance
                status_suffix = "(API)"
            except Exception:
                display_amount = service.last_balance
                status_suffix = "(Ошибка API)"
        
        # B. Это подписка? (Есть monthly_fee и это НЕ API сервис)
        # Пример: Streamtele, Wazzup24 Подписка
        elif service.monthly_fee and service.monthly_fee > 0:
            display_amount = service.monthly_fee
            # Формируем строку как в старом отчете: "Подписка: ₴1500.00"
            # Для этого suffix оставляем пустым, а префикс добавим в line
            is_subscription = True
            
        # C. Это обычный ручной счет? (Callii, Wazzup24 Баланс номера)
        else:
            display_amount = service.last_balance
            status_suffix = "(примерно)"

        # --- ФОРМИРОВАНИЕ СТРОКИ ---
        
        if is_subscription:
            # Особый формат для подписок: "• Streamtele: Подписка: ₴1500.00"
            # Обрати внимание: суффикса нет, слово "Подписка" внутри значения
            line = f"• **{name}:** Подписка: {sym}{display_amount:.2f}"
        else:
            # Стандартный формат: "• Zadarma: $0.00 (API)"
            line = f"• **{name}:** {sym}{display_amount:.2f} {status_suffix}"
            
        response_parts.append(line)

        # Добавляем дату (если есть) с отступом
        alert_date = service.next_alert_date or service.next_monthly_alert
        if alert_date:
            date_str = alert_date.strftime('%Y-%m-%d')
            response_parts.append(f"  _След. оплата:_ {date_str}")

    await message.answer('\n'.join(response_parts))