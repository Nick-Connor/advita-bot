import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# Импортируем роутеры из модулей handlers
from handlers.start import router as start_router
from handlers.calendar import router as calendar_router
from handlers.faq import router as faq_router

# from handlers.admin import router as admin_router

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Главное меню"),
        BotCommand(command="/revoke_consent", description="Отозвать согласие на обработку данных"),
        # BotCommand(command="/admin", description="Админ-панель (для сотрудников)"),
        BotCommand(command="/skip", description="Пропустить email при вопросе"),
    ]
    await bot.set_my_commands(commands)


async def send_daily_reminder(bot: Bot):
    """Отправляет напоминание всем пользователям каждый день в 10:00 в декабре"""
    now = datetime.now()

    # Только в декабре
    if now.month != 12:
        return

    # Отправляем в 10:00 (можно изменить на нужное время)
    if now.hour != 10:
        return

    current_day = now.day

    # Получаем всех пользователей из файлов пользователей
    users = set()
    for filename in os.listdir("."):
        if filename.startswith("user_") and filename.endswith(".json"):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    if user_data.get('consent_given'):
                        users.add(user_data.get('telegram_id'))
            except:
                pass

    # Получаем пользователей из файлов прогресса
    for f in os.listdir("."):
        if f.startswith("user_progress_") and f.endswith(".txt"):
            try:
                user_id = int(f.replace("user_progress_", "").replace(".txt", ""))
                users.add(user_id)
            except:
                pass

    # Отправляем напоминания
    for user_id in users:
        try:
            # Проверяем, не открыл ли пользователь уже сегодняшнюю ячейку
            progress_file = f"user_progress_{user_id}.txt"
            already_opened = False
            if os.path.exists(progress_file):
                with open(progress_file, "r") as f:
                    opened = [int(line.strip()) for line in f if line.strip().isdigit()]
                    if current_day in opened:
                        already_opened = True

            if not already_opened:
                await bot.send_message(
                    user_id,
                    f"🎄 **Напоминание!**\n\nСегодня {current_day} декабря.\n"
                    f"Не забудьте открыть ячейку в адвент-календаре!\n\n"
                    f"Откройте бота и нажмите «📅 Адвент-календарь».",
                    parse_mode="Markdown"
                )
                print(f"Напоминание отправлено пользователю {user_id}")
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")


async def send_new_year_congrat(bot: Bot):
    """Отправляет новогоднее поздравление 1 января в 00:10"""
    now = datetime.now()

    # Только 1 января
    if now.month != 1 or now.day != 1:
        return

    # Отправляем в 00:10 (чтобы не создавать нагрузку ровно в полночь)
    if now.hour != 0 or now.minute > 15:
        return

    # Получаем всех пользователей из файлов
    users = []
    for filename in os.listdir("."):
        if filename.startswith("user_") and filename.endswith(".json"):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    if user_data.get('consent_given'):
                        # Проверяем, не отправляли ли уже поздравление
                        if not user_data.get('new_year_congrat_sent', False):
                            users.append(user_data)
            except:
                pass

    for user_data in users:
        user_id = user_data.get('telegram_id')
        try:
            text = (
                "🎄 **С Новым годом!** 🎄\n\n"
                "Поздравляем вас с наступлением 2027 года!\n\n"
                "Спасибо, что были с нами весь декабрь.\n"
                "Благодаря вам и другим участникам акции\n"
                "**«Первое дело Нового года»**\n"
                "мы собрали средства на помощь подопечным фонда AdVita.\n\n"
                "✨ Ваше первое доброе дело в новом году уже сделано! ✨\n\n"
                "Пусть этот год принесёт здоровье, радость и много тёплых моментов.\n\n"
                "Спасибо, что вы с нами! 💝"
            )
            await bot.send_message(user_id, text, parse_mode="Markdown")

            # Отмечаем, что поздравление отправлено
            user_data['new_year_congrat_sent'] = True
            with open(f"user_{user_id}.json", "w", encoding="utf-8") as f:
                json.dump(user_data, f)

            # Небольшая задержка, чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Ошибка отправки поздравления пользователю {user_id}: {e}")


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_routers(
        start_router,
        calendar_router,
        faq_router,
        # admin_router,
    )

    await set_commands(bot)

    # Запускаем планировщик для ежедневных напоминаний
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_reminder,
        'interval',
        hours=1,
        args=[bot],
        id='daily_reminder'
    )

    # Добавляем задачу для новогоднего поздравления (запускается 1 января в 00:10)
    scheduler.add_job(
        send_new_year_congrat,
        'interval',
        hours=1,
        args=[bot],
        id='new_year_congrat'
    )

    scheduler.start()
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())