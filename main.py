import asyncio
import logging
from typing import Callable, Awaitable, Dict, Any

from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject

from config import SETTINGS
from db.models import init_db, initialize_services
from scheduler.jobs import check_api_balances, check_planned_alerts
from handlers import callii as callii_handlers
from handlers import balance as balance_handlers
from handlers import wazzup as wazzup_handlers

# Logging configuration
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Middlewares ---

class TargetChatFilter(BaseMiddleware):
    """
    Security middleware: Only allows interactions from the specific TARGET_CHAT_ID.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        chat_id = None
        
        # Determine chat ID based on event type
        if hasattr(event, 'chat') and event.chat:
            chat_id = event.chat.id
        elif isinstance(event, types.CallbackQuery) and event.message:
            chat_id = event.message.chat.id
        
        if chat_id != SETTINGS.TARGET_CHAT_ID:
            # Silent ignore for security
            return

        return await handler(event, data)

class DBSessionMiddleware(BaseMiddleware):
    """
    Dependency Injection middleware: Provides a database session to handlers.
    """
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)

# --- Scheduler ---

async def scheduler_loop(bot: Bot, session_factory):
    """
    Background loop for scheduled tasks (API checks and Alerts).
    """
    # Intervals in seconds
    API_CHECK_INTERVAL = 3600  # 1 hour
    PLANNED_ALERT_CHECK_INTERVAL = 600 # 10 minutes

    while True:
        try:
            # Task 1: Check API Balances
            async with session_factory() as session:
                await check_api_balances(bot, session)
            
            # Wait before next API check (Using short sleep loop logic if strictly required, 
            # but simpler here to just wait for the planned alert check to keep loop alive)
            
            # Note: To avoid blocking the loop for a full hour, we check planned alerts more frequently.
            # In a production environment with this specific loop structure, we need to manage timing carefully.
            # For simplicity based on previous code, we run them sequentially but we should ideally separate them.
            
            # Re-implementation for non-blocking concurrency would be better, 
            # but strictly following the provided pattern:
            
            await asyncio.sleep(60) # Small buffer
            
            # Task 2: Check Planned Alerts
            async with session_factory() as session:
                await check_planned_alerts(bot, session)
                
            # Wait remainder of cycle (This is a simplified logic from the original file)
            # A more robust approach uses apscheduler, but per instructions, we keep this structure.
            await asyncio.sleep(PLANNED_ALERT_CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
            await asyncio.sleep(60)

async def main():
    """Application entry point."""
    
    # 1. Database Initialization
    session_factory = await init_db(SETTINGS.DATABASE_URL)
    await initialize_services(session_factory)
    
    # 2. Bot Setup
    bot = Bot(token=SETTINGS.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher(storage=MemoryStorage())
    
    # 3. Middleware Registration
    db_middleware = DBSessionMiddleware(session_factory)
    chat_filter = TargetChatFilter()
    
    routers = [
        balance_handlers.router,
        callii_handlers.router,
        wazzup_handlers.router
    ]
    
    # Apply middlewares to all routers and the dispatcher
    for r in routers + [dp]:
        # Filter first, then DB injection
        r.message.middleware(chat_filter)
        r.callback_query.middleware(chat_filter)
        
        r.message.middleware(db_middleware)
        r.callback_query.middleware(db_middleware)
        
    # 4. Include Routers
    dp.include_routers(*routers)

    @dp.message(Command("start"))
    async def command_start_handler(message: types.Message) -> None:
        await message.answer(
            "👋 **Система мониторинга активна.**\n\n"
            "Я работаю в фоновом режиме. Используйте /balance для проверки статуса."
        )

    # 5. Start Scheduler & Polling
    scheduler_task = asyncio.create_task(scheduler_loop(bot, session_factory))
    
    logger.info("Bot started...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await scheduler_task
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")