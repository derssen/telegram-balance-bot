import math
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import Service, TIMEZONE
from config import SETTINGS

router = Router()

class WazzupPayment(StatesGroup):
    waiting_for_amount = State()

@router.callback_query(F.data == "wazzup_paid")
async def process_wazzup_paid(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите сумму пополнения в рублях для номера +6281239838440:"
    )
    await state.set_state(WazzupPayment.waiting_for_amount)
    await callback.answer()

@router.message(WazzupPayment.waiting_for_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def process_wazzup_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        top_up_amount = float(message.text)
        daily_cost = SETTINGS.WAZZUP_DAILY_COST
        
        # 1. Get the service from DB
        stmt = select(Service).where(Service.name == 'Wazzup24 Баланс номера')
        result = await session.execute(stmt)
        service = result.scalar_one()

        # 2. Logic: Current Balance + New Amount
        current_balance = service.last_balance or 0.0
        new_total_balance = current_balance + top_up_amount
        
        # 3. Calculate how many days this total amount covers
        days_covered = math.floor(new_total_balance / daily_cost)

        # 4. Calculate new date
        # We start counting from TODAY (now), because the balance covers future days
        next_alert_datetime = datetime.now(TIMEZONE) + timedelta(days=days_covered)
        next_alert_datetime = next_alert_datetime.replace(hour=10, minute=0, second=0, microsecond=0)

        # 5. Save to DB
        service.last_balance = new_total_balance # Update balance!
        service.next_alert_date = next_alert_datetime
        await session.commit()

        await message.answer(
            f"✅ Пополнение Wazzup учтено.\n"
            f"Было: `₽{current_balance:.2f}`\n"
            f"Внесено: `₽{top_up_amount:.2f}`\n"
            f"Стало: `₽{new_total_balance:.2f}`\n"
            f"Хватит на дней: **{days_covered}** (до {next_alert_datetime.strftime('%Y-%m-%d')})."
        )
        await state.clear()
    except Exception as exc:
        await message.answer(f"Ошибка сохранения: {exc}")
        await state.clear()

@router.message(WazzupPayment.waiting_for_amount)
async def process_wazzup_amount_invalid(message: Message):
    await message.answer("Неверный формат. Введите сумму числом.")