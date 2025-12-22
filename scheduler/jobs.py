from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import Service, TIMEZONE
from services.api_clients import API_CLIENTS
from config import SETTINGS
from datetime import datetime
import logging
import calendar

logger = logging.getLogger(__name__)

async def check_api_balances(bot: Bot, session: AsyncSession):
    """Ежечасная проверка балансов API-сервисов."""
    target_chat_id = SETTINGS.TARGET_CHAT_ID

    for service_name, client in API_CLIENTS.items():
        # НОВОЕ: Проверяем, активен ли сервис
        if not SETTINGS.API_SERVICE_STATUSES.get(service_name, False):
            logger.info(f"Skipping balance check for {service_name} (disabled in config).")
            continue
        try:
            current_balance = await client.get_balance()
            if current_balance is None:
                logger.info(f"Skipping balance logic for {service_name}: API balance not available.")
                continue
            
            # 1. Получаем данные из БД
            stmt = select(Service).where(Service.name == service_name)
            result = await session.execute(stmt)
            service = result.scalar_one_or_none()

            if not service:
                logger.warning(f"Service {service_name} not found in DB.")
                continue

            last_balance = service.last_balance
            
            # --- 2. Логика пополнения (Изменение баланса в плюс > $5) ---
            if current_balance > last_balance + SETTINGS.MIN_TOP_UP_AMOUNT:
                top_up_amount = current_balance - last_balance
                await bot.send_message(
                    target_chat_id,
                    f"✅ **Счет в {service_name} пополнен!**\n"
                    f"Сумма пополнения: **${top_up_amount:.2f}**.\n"
                    f"Текущий баланс: **${current_balance:.2f}**."
                )
                # Сбрасываем флаг низкого баланса, если был
                service.low_balance_alert_sent = False 

            # --- 3. Логика низкого баланса (< $10) ---
            if current_balance < SETTINGS.LOW_BALANCE_THRESHOLD:
                if not service.low_balance_alert_sent:
                    await bot.send_message(
                        target_chat_id,
                        f"⚠️ **ВНИМАНИЕ! Низкий баланс в {service_name}!**\n"
                        f"Текущий баланс: **${current_balance:.2f}**.\n"
                        f"Пожалуйста, пополните счет."
                    )
                    service.low_balance_alert_sent = True
            elif current_balance >= SETTINGS.LOW_BALANCE_THRESHOLD:
                # Баланс вернулся в норму
                service.low_balance_alert_sent = False 

            # Обновляем последний известный баланс
            service.last_balance = current_balance
            await session.commit()
            
        except Exception as e:
            logger.error(f"Error checking balance for {service_name}: {e}")
            await session.rollback()

async def check_planned_alerts(bot: Bot, session: AsyncSession):
    """Плановые оповещения для ручных сервисов."""
    target_chat_id = SETTINGS.TARGET_CHAT_ID
    
    # Текущее время (с учетом таймзоны)
    now_in_tz = datetime.now(TIMEZONE)
    today_date = now_in_tz.date()

    # --- Ежедневные расходы (Callii, Wazzup Баланс) ---
    daily_stmt = select(Service).where(Service.next_alert_date.isnot(None))
    daily_result = await session.execute(daily_stmt)
    daily_services = daily_result.scalars().all()

    for service in daily_services:
        if not service.next_alert_date:
            continue

        if service.next_alert_date.astimezone(TIMEZONE).date() <= today_date:
            if service.name == 'Callii':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Оплатил", callback_data="callii_paid")]
                ])
                await bot.send_message(
                    target_chat_id,
                    "⏰ **Callii:** срок пополнения истек. Оплатите и нажмите кнопку, чтобы указать сумму.",
                    reply_markup=keyboard
                )
            elif service.name == 'Wazzup24 Баланс номера':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Пополнено", callback_data="wazzup_paid")]
                ])
                await bot.send_message(
                    target_chat_id,
                    "📞 **Wazzup24 (баланс):** ежедневное потребление 400₽.\n"
                    f"Номер {SETTINGS.WAZZUP_PHONE}. Пополните баланс и нажмите кнопку, чтобы указать сумму.",
                    reply_markup=keyboard
                )

    # --- Ежемесячные оплаты ---
    monthly_stmt = select(Service).where(Service.next_monthly_alert.isnot(None))
    monthly_result = await session.execute(monthly_stmt)
    monthly_services = monthly_result.scalars().all()

    for service in monthly_services:
        if not service.next_monthly_alert:
            continue

        alert_dt = service.next_monthly_alert.astimezone(TIMEZONE)
        if now_in_tz >= alert_dt:
            currency_sign = SETTINGS.CURRENCY_SIGNS.get(service.currency or 'USD', service.currency or 'USD')
            fee = service.monthly_fee or 0.0

            if service.name == 'Streamtele':
                await bot.send_message(
                    target_chat_id,
                    "🗓️ **Streamtele:** ежемесячная проверка.\n"
                    f"Абонплата: {currency_sign}{fee:.2f}. Проверьте биллинг и оплатите при необходимости."
                )
                service.next_monthly_alert = _next_monthly_datetime(alert_dt, target_day=11)

            elif service.name == 'Wazzup24 Подписка':
                await bot.send_message(
                    target_chat_id,
                    "🗓️ **Wazzup24 (подписка):**\n"
                    f"Номер {SETTINGS.WAZZUP_PHONE} необходимо оплатить до 11 числа.\n"
                    f"Сумма подписки: {currency_sign}{fee:.2f}."
                )
                service.next_monthly_alert = _next_monthly_datetime(alert_dt, target_day=11)

            elif service.name == 'DIDWW':
                current_balance = service.last_balance or 0.0
                projected = current_balance - fee
                await bot.send_message(
                    target_chat_id,
                    "📡 **DIDWW:** завтра (21 числа) спишется абонплата.\n"
                    f"Текущий баланс: {currency_sign}{current_balance:.2f}.\n"
                    f"После списания ({currency_sign}{fee:.2f}) останется примерно {currency_sign}{projected:.2f}."
                )
                service.next_monthly_alert = _next_monthly_datetime(alert_dt, target_day=20)

            await session.commit()
            logger.info(f"{service.name} next monthly alert set to {service.next_monthly_alert}")


def _next_monthly_datetime(current_date: datetime, target_day: int, hour: int = 10, minute: int = 0) -> datetime:
    """Возвращает дату следующего месяца для заданного дня."""
    base = current_date.astimezone(TIMEZONE) if current_date else datetime.now(TIMEZONE)
    month = base.month + 1
    year = base.year
    if month > 12:
        month = 1
        year += 1
    _, last_day = calendar.monthrange(year, month)
    day = min(target_day, last_day)
    return TIMEZONE.localize(datetime(year, month, day, hour, minute))