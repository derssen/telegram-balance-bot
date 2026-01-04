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

class CalliiPayment(StatesGroup):
    waiting_for_amount = State()

@router.callback_query(F.data == "callii_paid")
async def process_callii_paid(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Спасибо за оплату. **Введите сумму пополнения (числом в USD):**"
    )
    await state.set_state(CalliiPayment.waiting_for_amount)
    await callback.answer()

@router.message(CalliiPayment.waiting_for_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def process_callii_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        top_up_amount = float(message.text)
        daily_cost = SETTINGS.CALLII_DAILY_COST
        
        stmt = select(Service).where(Service.name == 'Callii')
        result = await session.execute(stmt)
        service = result.scalar_one()
        
        current_balance = service.last_balance or 0.0
        new_total_balance = current_balance + top_up_amount
        
        days_covered = math.floor(new_total_balance / daily_cost)
        
        next_alert_datetime = datetime.now(TIMEZONE) + timedelta(days=days_covered)
        next_alert_datetime = next_alert_datetime.replace(hour=10, minute=0, second=0, microsecond=0)

        service.last_balance = new_total_balance
        service.next_alert_date = next_alert_datetime
        await session.commit()
        
        await message.answer(
            f"💰 **Платеж Callii обработан!**\n"
            f"Было: `${current_balance:.2f}`\n"
            f"Внесено: `${top_up_amount:.2f}`\n"
            f"Стало: `${new_total_balance:.2f}`\n"
            f"Хватит на дней: **{days_covered}** (до {next_alert_datetime.strftime('%Y-%m-%d')})."
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(f"Ошибка системы: {e}")
        await state.clear()

@router.message(CalliiPayment.waiting_for_amount)
async def process_callii_amount_invalid(message: Message):
    await message.answer("Неверный формат. Пожалуйста, введите число.")