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
    """Callback for 'Paid' button on Callii alert."""
    await callback.message.edit_text(
        "Спасибо за оплату. **Введите сумму пополнения (числом в USD):**"
    )
    await state.set_state(CalliiPayment.waiting_for_amount)
    await callback.answer()

@router.message(CalliiPayment.waiting_for_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def process_callii_amount(message: Message, state: FSMContext, session: AsyncSession):
    """Process the entered amount and recalculate next alert date."""
    try:
        amount = float(message.text)
        daily_cost = SETTINGS.CALLII_DAILY_COST
        
        # Calculate coverage days
        days = math.floor(amount / daily_cost)
        
        if days < 1:
            await message.answer(
                "Сумма слишком мала для покрытия дневного расхода. Введите большую сумму."
            )
            return

        # Calculate next alert date (10:00 AM)
        next_alert_datetime = datetime.now(TIMEZONE) + timedelta(days=days)
        next_alert_datetime = next_alert_datetime.replace(hour=10, minute=0, second=0, microsecond=0)

        # Update DB
        stmt = select(Service).where(Service.name == 'Callii')
        result = await session.execute(stmt)
        service = result.scalar_one()
        
        service.next_alert_date = next_alert_datetime
        await session.commit()
        
        await message.answer(
            f"💰 **Платеж Callii обработан!**\n"
            f"Сумма: **${amount:.2f}**\n"
            f"Дней покрытия (расход ${daily_cost}/день): **{days}**.\n"
            f"Следующий контроль баланса запланирован на **{next_alert_datetime.strftime('%Y-%m-%d в 10:00')}**."
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(f"Ошибка системы: {e}")
        await state.clear()

@router.message(CalliiPayment.waiting_for_amount)
async def process_callii_amount_invalid(message: Message):
    await message.answer("Неверный формат. Пожалуйста, введите число (например, 50 или 50.50).")