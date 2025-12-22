import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router, BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from config import SETTINGS
from db.models import init_db, initialize_services
from scheduler.jobs import check_api_balances, check_planned_alerts
from handlers import callii as callii_handlers
from handlers import balance as balance_handlers # Новый импорт
from handlers import wazzup as wazzup_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 1. Фильтр доступа ---
class TargetChatFilter(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем, есть ли у события атрибут chat, и получаем его ID
        chat_id = getattr(event, 'chat', None).id if hasattr(event, 'chat') and getattr(event, 'chat') else None
        
        # Для CallbackQuery ID чата нужно брать из message
        if isinstance(event, types.CallbackQuery) and event.message:
            chat_id = event.message.chat.id
        
        target_chat_id = SETTINGS.TARGET_CHAT_ID

        if chat_id is None or chat_id != target_chat_id:
            # Если это Message, отправляем ответ-предупреждение
            if isinstance(event, types.Message):
                await event.answer("Не дёргай меня по пустякам, ничтожество (у тебя нету прав).")
            # Для других событий (CallbackQuery и т.д.) просто тихо игнорируем
            return

        # Если ID чата совпадает, продолжаем обработку
        return await handler(event, data)

# 1.1: Middleware для инъекции сессии БД
class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Всегда открываем сессию и прокидываем ее в data, чтобы DI aiogram смог
        # подставить session: AsyncSession в сигнатуру хендлера.
        async with self.session_pool() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            finally:
                # Сессия закрывается автоматически контекстным менеджером
                ...

# --- 2. Планировщик и старт ---
async def scheduler_loop(bot: Bot, session_local):
    """Основной асинхронный цикл для планировщика."""
    
    # Задержки в секундах
    #API_CHECK_INTERVAL = 3600  # 1 час
    #PLANNED_ALERT_CHECK_INTERVAL = 600 # 10 минут (чтобы не пропустить 10:00)
    # TEST
    API_CHECK_INTERVAL = 60  # 1 минута
    PLANNED_ALERT_CHECK_INTERVAL = 600 # 10 минут (чтобы не пропустить 10:00)

    # Запускаем задачи
    while True:
        try:
            # Ежечасная проверка API балансов
            async with session_local() as session:
                await check_api_balances(bot, session)
            
            await asyncio.sleep(API_CHECK_INTERVAL)
            
            # Проверка плановых оповещений (Callii, Streamtele)
            async with session_local() as session:
                await check_planned_alerts(bot, session)

            await asyncio.sleep(PLANNED_ALERT_CHECK_INTERVAL) # Повторяем проверку плановых оповещений
            
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            await asyncio.sleep(60) # Короткая пауза в случае ошибки


async def main():
    # Инициализация БД
    SessionLocal = await init_db(SETTINGS.DATABASE_URL)
    await initialize_services(SessionLocal)
    
    bot = Bot(token=SETTINGS.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher(storage=MemoryStorage())
    
    # 1. Создание экземпляров Middleware
    db_middleware = DBSessionMiddleware(SessionLocal)

    # 2. Регистрируем роутеры СНАЧАЛА
    # Получаем импортированные роутеры, чтобы применить к ним Middleware
    router_balance = balance_handlers.router
    router_callii = callii_handlers.router
    router_wazzup = wazzup_handlers.router
    
    # 3. Применяем Middleware к роутерам и диспетчеру
    
    # Применяем Middleware к каждому роутеру и диспетчеру (dp)
    for target in [router_balance, router_callii, router_wazzup, dp]:
        # Фильтр доступа: Срабатывает первым
        target.message.middleware(TargetChatFilter())
        target.callback_query.middleware(TargetChatFilter())
        
        # Инъекция сессии: Срабатывает вторым (идет после фильтра)
        target.message.middleware(db_middleware)
        target.callback_query.middleware(db_middleware)
        
    # 4. Включаем роутеры в диспетчер
    dp.include_router(router_callii)
    dp.include_router(router_wazzup)
    dp.include_router(router_balance)

    # Простой хендлер для начала работы (регистрируем на dp)
    @dp.message(Command("start"))
    async def command_start_handler(message: types.Message) -> None:
        await message.answer(f"Привет Максим! Я бот для мониторинга балансов. Я работаю в фоновом режиме, ты можешь ввести команду /balance чтобы получить текущий баланс.")

    # Запуск планировщика в фоновом режиме
    scheduler_task = asyncio.create_task(scheduler_loop(bot, SessionLocal))
    
    # Запуск бота
    try:
        # Note: session_local=SessionLocal здесь не используется для инъекции в хендлеры,
        # а только для внутреннего использования aiogram, но его можно оставить.
        await dp.start_polling(bot, session_local=SessionLocal)
    finally:
        # Остановка планировщика при завершении работы бота
        scheduler_task.cancel()
        await scheduler_task
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")