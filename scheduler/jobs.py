from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import Service, TIMEZONE
from services.api_clients import API_CLIENTS, MakeClient
from config import SETTINGS
from datetime import datetime, timedelta
import logging
import calendar
import dateutil.parser # Requires: pip install python-dateutil (usually included, or add to requirements)

logger = logging.getLogger(__name__)

async def check_api_balances(bot: Bot, session: AsyncSession):
    """Checks API services, including advanced logic for Make."""
    target_chat_id = SETTINGS.TARGET_CHAT_ID

    for service_name, client in API_CLIENTS.items():
        if not SETTINGS.API_SERVICE_STATUSES.get(service_name, False):
            continue
        try:
            current_balance = await client.get_balance() # Returns REMAINING units
            if current_balance is None:
                continue
            
            stmt = select(Service).where(Service.name == service_name)
            result = await session.execute(stmt)
            service = result.scalar_one_or_none()

            if not service: continue

            # --- Logic for Make (Operations & Subscription) ---
            if service_name == 'Make' and isinstance(client, MakeClient):
                details = client.cached_details
                if details and details.get('reset_at'):
                    # 1. Update Subscription Date
                    # Parse ISO string from API (e.g. 2024-02-01T00:00:00.000Z)
                    reset_dt_utc = dateutil.parser.isoparse(details['reset_at'])
                    reset_dt_local = reset_dt_utc.astimezone(TIMEZONE)
                    
                    # Update DB if date changed
                    if service.next_monthly_alert != reset_dt_local:
                        service.next_monthly_alert = reset_dt_local
                    
                    # 2. Burn Rate Calculation (Will we survive?)
                    now = datetime.now(TIMEZONE)
                    days_until_reset = (reset_dt_local - now).days
                    
                    if days_until_reset > 0:
                        # Assume billing cycle is 30 days roughly
                        usage = details['usage']
                        # Calculate days elapsed since start of cycle (Limit is monthly)
                        # Start date is roughly Reset Date - 1 month
                        # Simpler: just use average usage? No, usage is cumulative for the month.
                        # We need to know when the month STARTED.
                        # Let's approximate: Month Start = Reset Date - 1 Month.
                        prev_month = reset_dt_local - timedelta(days=28) # Safe bet
                        # Find the actual start day? API doesn't give it clearly, but resetAt is reliable.
                        # Let's calculate purely on current usage vs remaining days.
                        
                        # Logic: Usage so far / Days Passed = Burn Rate
                        # Days Passed = Total Cycle Days (30) - Days Until Reset
                        days_passed = 30 - days_until_reset
                        if days_passed < 1: days_passed = 1
                        
                        burn_rate = usage / days_passed # Ops per day
                        
                        if burn_rate > 0:
                            projected_runway_days = current_balance / burn_rate
                            
                            # Alert if runway is significantly shorter than time to reset (buffer 2 days)
                            if projected_runway_days < (days_until_reset - 1):
                                if not service.low_balance_alert_sent:
                                    await bot.send_message(
                                        target_chat_id,
                                        f"🔥 **Make: Критический расход!**\n"
                                        f"Осталось: `{int(current_balance)}` Ops.\n"
                                        f"Расход: ~`{int(burn_rate)}` Ops/день.\n"
                                        f"Хватит на: **{int(projected_runway_days)} дн.**\n"
                                        f"До обновления подписки: **{days_until_reset} дн.**"
                                    )
                                    service.low_balance_alert_sent = True
                            else:
                                service.low_balance_alert_sent = False

            # --- Standard Logic (Top-up & Low Balance) ---
            last_balance = service.last_balance
            
            # Top-up detection (Ignore for Make as it resets automatically)
            if service_name != 'Make':
                if current_balance > last_balance + SETTINGS.MIN_TOP_UP_AMOUNT:
                    top_up = current_balance - last_balance
                    await bot.send_message(
                        target_chat_id,
                        f"✅ **{service_name}: Баланс пополнен!**\n+${top_up:.2f} ➔ `${current_balance:.2f}`"
                    )
                    service.low_balance_alert_sent = False 

            # Low Threshold (For money services)
            if service_name != 'Make': # Make has its own logic above
                if current_balance < SETTINGS.LOW_BALANCE_THRESHOLD:
                    if not service.low_balance_alert_sent:
                        await bot.send_message(
                            target_chat_id,
                            f"⚠️ **{service_name}: Низкий баланс!**\n`${current_balance:.2f}`\nПополните счет."
                        )
                        service.low_balance_alert_sent = True
                else:
                    service.low_balance_alert_sent = False 

            service.last_balance = current_balance
            await session.commit()
            
        except Exception as e:
            logger.error(f"Error checking API {service_name}: {e}")
            await session.rollback()

async def check_planned_alerts(bot: Bot, session: AsyncSession):
    """Checks manual alerts and subscriptions."""
    target_chat_id = SETTINGS.TARGET_CHAT_ID
    now = datetime.now(TIMEZONE)
    today_date = now.date()
    weekday = now.weekday() 

    # 1. Weekend Silence
    if weekday in (5, 6): return

    # 2. Manual Services (Callii, Wazzup Balance)
    stmt = select(Service).where(Service.next_alert_date.isnot(None))
    manual_services = (await session.execute(stmt)).scalars().all()

    for service in manual_services:
        alert_needed = False
        msg_text = ""
        keyboard = None
        due_date = service.next_alert_date.astimezone(TIMEZONE).date()
        
        # Friday Look-ahead
        if weekday == 4:
            days_left = (due_date - today_date).days
            if 0 <= days_left <= 2:
                if not _was_alerted_recently(service.last_alert_at, hours=20):
                    alert_needed = True
                    day_name = "сегодня" if days_left == 0 else ("завтра" if days_left == 1 else "в воскресенье")
                    msg_text = f"🍻 **Пятничный контроль ({service.name}):**\nБаланс обнулится {day_name}. Пополните сейчас!"

        if not alert_needed:
            # 1 Day warning
            if (due_date - today_date).days == 1:
                if 10 <= now.hour < 11 and not _was_alerted_recently(service.last_alert_at, hours=20):
                    alert_needed = True
                    msg_text = f"⏰ **{service.name}:** Завтра заканчиваются средства."
            # Expired
            elif due_date <= today_date:
                if not _was_alerted_recently(service.last_alert_at, hours=2):
                    alert_needed = True
                    msg_text = f"🚨 **{service.name}: СРОК ИСТЕК!**\nСредства закончились."

        if alert_needed and msg_text:
            if service.name == 'Callii':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Оплатил", callback_data="callii_paid")]])
            elif service.name == 'Wazzup24 Баланс номера':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Пополнено", callback_data="wazzup_paid")]])
            
            await bot.send_message(target_chat_id, msg_text, reply_markup=keyboard)
            service.last_alert_at = now
            await session.commit()

    # 3. Monthly Subscriptions (Now includes Make)
    m_stmt = select(Service).where(Service.next_monthly_alert.isnot(None))
    monthly_services = (await session.execute(m_stmt)).scalars().all()

    for service in monthly_services:
        alert_dt = service.next_monthly_alert.astimezone(TIMEZONE)
        
        # Make uses auto-updated API dates, others use manual logic
        if service.name == 'Make':
            # Warn 1 day before reset
            one_day_before = alert_dt - timedelta(days=1)
            if now.date() == one_day_before.date():
                if 10 <= now.hour < 11 and not _was_alerted_recently(service.last_alert_at, hours=20):
                     await bot.send_message(target_chat_id, f"⚡ **Make:** Завтра ({alert_dt.strftime('%d.%m')}) обновление подписки и сброс кредитов.")
                     service.last_alert_at = now
                     await session.commit()
            continue # Skip manual date increment for Make

        # Logic for others (Manual increment)
        if now >= alert_dt:
             currency_sign = SETTINGS.CURRENCY_SIGNS.get(service.currency, '$')
             fee = service.monthly_fee or 0.0
             
             if service.name == 'Streamtele':
                 await bot.send_message(target_chat_id, f"🗓️ **Streamtele:** Ежемесячная оплата {currency_sign}{fee:.2f}.")
                 service.next_monthly_alert = _next_monthly_datetime(alert_dt, target_day=11)
             elif service.name == 'Wazzup24 Подписка':
                 await bot.send_message(target_chat_id, f"🗓️ **Wazzup24 (Подписка):** Оплата {currency_sign}{fee:.2f}.")
                 service.next_monthly_alert = _next_monthly_datetime(alert_dt, target_day=11)
             elif service.name == 'DIDWW':
                 await bot.send_message(target_chat_id, f"📡 **DIDWW:** Завтра списание {currency_sign}{fee:.2f}.")
                 service.next_monthly_alert = _next_monthly_datetime(alert_dt, target_day=20)
             
             await session.commit()

async def deduct_daily_balances(session: AsyncSession):
    stmt = select(Service).where(Service.daily_cost.isnot(None))
    services = (await session.execute(stmt)).scalars().all()
    for service in services:
        if service.daily_cost and service.daily_cost > 0:
            current = service.last_balance or 0.0
            service.last_balance = current - service.daily_cost
    await session.commit()

def _was_alerted_recently(last_alert: datetime, hours: int) -> bool:
    if not last_alert: return False
    now = datetime.now(TIMEZONE)
    if last_alert.tzinfo is None: last_alert = TIMEZONE.localize(last_alert)
    return (now - last_alert) < timedelta(hours=hours)

def _next_monthly_datetime(current_date: datetime, target_day: int) -> datetime:
    base = current_date.astimezone(TIMEZONE)
    month = base.month + 1
    year = base.year
    if month > 12:
        month = 1; year += 1
    _, last_day = calendar.monthrange(year, month)
    day = min(target_day, last_day)
    return TIMEZONE.localize(datetime(year, month, day, 10, 0))