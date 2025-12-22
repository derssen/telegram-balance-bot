from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import Service, TIMEZONE
from config import SETTINGS
from datetime import datetime, timedelta
import math

router = Router()


class WazzupPayment(StatesGroup):
    waiting_for_amount = State()


@router.callback_query(F.data == "wazzup_paid")
async def process_wazzup_paid(callback: CallbackQuery, state: FSMContext):
    """Кнопка 'Пополнено' для ежедневного расхода Wazzup."""
    await callback.message.edit_text(
        "Введите сумму пополнения в рублях для номера +6281239838440:"
    )
    await state.set_state(WazzupPayment.waiting_for_amount)
    await callback.answer()


@router.message(WazzupPayment.waiting_for_amount, F.text.regexp(r'^\d+(\.\d{1,2})?$'))
async def process_wazzup_amount(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка суммы пополнения Wazzup24."""
    try:
        amount = float(message.text)
        daily_cost = SETTINGS.WAZZUP_DAILY_COST
        days = math.floor(amount / daily_cost)

        if days < 1:
            await message.answer("Сумма слишком мала для покрытия дневного расхода (400₽/день).")
            return

        stmt = select(Service).where(Service.name == 'Wazzup24 Баланс номера')
        result = await session.execute(stmt)
        service = result.scalar_one()

        next_alert_datetime = datetime.now(TIMEZONE) + timedelta(days=days)
        next_alert_datetime = next_alert_datetime.replace(hour=10, minute=0, second=0, microsecond=0)

        service.next_alert_date = next_alert_datetime
        await session.commit()

        await message.answer(
            f"Пополнение Wazzup учтено.\n"
            f"Сумма: **₽{amount:.2f}**.\n"
            f"Дней покрытия (расход ₽{daily_cost}/день): **{days}**.\n"
            f"Следующее напоминание: **{next_alert_datetime.strftime('%Y-%m-%d в 10:00')}**."
        )
        await state.clear()
    except ValueError:
        await message.answer("Ошибка: введите число.")
    except Exception as exc:
        await message.answer(f"Ошибка при сохранении: {exc}")
        await state.clear()


@router.message(WazzupPayment.waiting_for_amount)
async def process_wazzup_amount_invalid(message: Message):
    await message.answer("Неверный формат. Введите сумму числом, например 6000 или 7500.50.")

