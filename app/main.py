import asyncio
import logging

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from app.config import get_settings
from app.containers import Docker
from app.handlers import router
from app.monitor import monitor_loop, notify


class AdminOnly(BaseMiddleware):

    def __init__(self, admin_ids: list[int]):
        self.ids = set(admin_ids)

    async def __call__(self, handler, event: Update, data):
        user = data.get("event_from_user")
        if user is None or user.id not in self.ids:
            return None
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    bot = Bot(s.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    ops = Docker(s)
    dp.workflow_data.update(settings=s, ops=ops)
    dp.update.outer_middleware(AdminOnly(s.admin_ids))
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    task = asyncio.create_task(monitor_loop(bot, ops, s))
    await notify(bot, s.admin_ids, "🟢 Админ-бот запущен. /menu")
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
