import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
import httpx
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

from strapi_client import STRAPI_URL, HEADERS, _extract_items

load_dotenv()
BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")


async def set_commands(bot: Bot) -> None:
    """Установить команды бота в Telegram"""
    commands: List[BotCommand] = [
        BotCommand(command="/start", description="Главное меню"),
        BotCommand(command="/revoke_consent", description="Отозвать согласие на обработку данных"),
        BotCommand(command="/skip", description="Пропустить email при вопросе"),
    ]
    await bot.set_my_commands(commands)


async def get_all_users_from_strapi() -> List[Dict[str, Any]]:
    """
    Получить всех пользователей из TelegramUser с согласием.

    Returns:
        List[Dict[str, Any]]: Список пользователей или пустой список при ошибке
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/telegram-users?filters[consent_given][$eq]=true"
            response = await client.get(url, headers=HEADERS)

            if response.status_code == 200:
                data: Dict[str, Any] = response.json()
                items: List[Dict[str, Any]] = _extract_items(data)
                # Преобразуем в плоский формат
                result: List[Dict[str, Any]] = []
                for item in items:
                    if 'attributes' in item:
                        result.append(item['attributes'])
                    else:
                        result.append(item)
                return result
            return []

    except httpx.TimeoutException:
        print(f"❌ Таймаут при получении пользователей из Strapi")
        return []
    except httpx.ConnectError:
        print(f"❌ Ошибка подключения к Strapi при получении пользователей")
        return []
    except Exception as e:
        print(f"❌ Неизвестная ошибка при получении пользователей: {e}")
        return []


async def is_cell_opened_today(telegram_user_id: int, current_day: int) -> bool:
    """
    Проверить, открыл ли пользователь сегодняшнюю ячейку.

    Args:
        telegram_user_id: ID пользователя в Strapi
        current_day: Текущий день декабря

    Returns:
        bool: True если ячейка уже открыта, False в противном случае
    """
    try:
        async with httpx.AsyncClient() as client:
            # Получаем ID ячейки по номеру дня
            cell_url = f"{STRAPI_URL}/advent-cells?filters[day_number][$eq]={current_day}"
            cell_response = await client.get(cell_url, headers=HEADERS)

            if cell_response.status_code != 200:
                return False

            cell_data: Dict[str, Any] = cell_response.json()
            cell_items: List[Dict[str, Any]] = _extract_items(cell_data)
            if not cell_items:
                return False

            cell_id: Optional[int] = cell_items[0].get('id')
            if not cell_id:
                return False

            # Проверяем, есть ли запись о прогрессе
            progress_url = f"{STRAPI_URL}/user-progresses?filters[user][id][$eq]={telegram_user_id}&filters[cell][id][$eq]={cell_id}"
            progress_response = await client.get(progress_url, headers=HEADERS)

            if progress_response.status_code == 200:
                progress_data: Dict[str, Any] = progress_response.json()
                progress_items: List[Dict[str, Any]] = _extract_items(progress_data)
                return len(progress_items) > 0

            return False

    except httpx.TimeoutException:
        print(f"❌ Таймаут при проверке открытия ячейки {current_day}")
        return False
    except httpx.ConnectError:
        print(f"❌ Ошибка подключения к Strapi при проверке ячейки {current_day}")
        return False
    except Exception as e:
        print(f"❌ Неизвестная ошибка при проверке ячейки {current_day}: {e}")
        return False


async def update_user_new_year_flag(telegram_id: int) -> bool:
    """
    Обновить флаг отправки новогоднего поздравления.

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        bool: True при успешном обновлении, False в противном случае
    """
    try:
        async with httpx.AsyncClient() as client:
            user_url = f"{STRAPI_URL}/telegram-users?filters[telegram_id][$eq]={telegram_id}"
            user_response = await client.get(user_url, headers=HEADERS)

            if user_response.status_code == 200:
                user_data: Dict[str, Any] = user_response.json()
                user_items: List[Dict[str, Any]] = _extract_items(user_data)
                if user_items:
                    user_info: Dict[str, Any] = user_items[0]
                    if 'attributes' in user_info:
                        telegram_user_id: Optional[int] = user_info['attributes'].get('id')
                    else:
                        telegram_user_id = user_info.get('id')

                    if telegram_user_id:
                        update_url = f"{STRAPI_URL}/telegram-users/{telegram_user_id}"
                        update_payload: Dict[str, Any] = {
                            "data": {
                                "new_year_congrat_sent": True
                            }
                        }
                        await client.put(update_url, json=update_payload, headers=HEADERS)
                        return True
            return False

    except httpx.TimeoutException:
        print(f"❌ Таймаут при обновлении новогоднего флага для {telegram_id}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при обновлении новогоднего флага для {telegram_id}: {e}")
        return False


async def send_daily_reminder(bot: Bot) -> None:
    """Отправляет напоминание всем пользователям каждый день в 10:00 в декабре"""
    now: datetime = datetime.now()

    # Только в декабре
    if now.month != 12:
        return

    # Отправляем в 10:00
    if now.hour != 10:
        return

    current_day: int = now.day
    users: List[Dict[str, Any]] = await get_all_users_from_strapi()
    print(f"📢 Отправка напоминаний на {current_day} декабря. Найдено пользователей: {len(users)}")

    for user in users:
        try:
            telegram_user_id: Optional[int] = user.get('id')
            telegram_id: Optional[int] = user.get('telegram_id')

            if not telegram_id:
                continue

            already_opened: bool = await is_cell_opened_today(telegram_user_id, current_day)

            if not already_opened:
                await bot.send_message(
                    telegram_id,
                    f"🎄 **Напоминание!**\n\nСегодня {current_day} декабря.\n"
                    f"Не забудьте открыть ячейку в адвент-календаре!\n\n"
                    f"Откройте бота и нажмите «📅 Адвент-календарь».",
                    parse_mode="Markdown"
                )
                print(f"✅ Напоминание отправлено пользователю {telegram_id}")
            else:
                print(f"⏭️ Пользователь {telegram_id} уже открыл ячейку {current_day}")
        except Exception as e:
            print(f"❌ Ошибка отправки пользователю {user.get('telegram_id')}: {e}")


async def send_new_year_congrat(bot: Bot) -> None:
    """Отправляет новогоднее поздравление 1 января"""
    now: datetime = datetime.now()

    # Только 1 января
    if now.month != 1 or now.day != 1:
        return

    # Отправляем в первый час после полуночи
    if now.hour != 0:
        return

    users: List[Dict[str, Any]] = await get_all_users_from_strapi()
    print(f"🎄 Отправка новогодних поздравлений. Найдено пользователей: {len(users)}")

    for user in users:
        telegram_id: Optional[int] = user.get('telegram_id')
        new_year_sent: bool = user.get('new_year_congrat_sent', False)

        if not telegram_id:
            continue
        if new_year_sent:
            print(f"⏭️ Пользователю {telegram_id} поздравление уже отправлено")
            continue

        try:
            text: str = (
                "🎄 **С Новым годом!** 🎄\n\n"
                "Поздравляем вас с наступлением 2027 года!\n\n"
                "Спасибо, что были с нами весь декабрь.\n"
                "Благодаря вам и другим участникам акции\n"
                "\"Первое дело Нового года\"\n"
                "мы собрали средства на помощь подопечным фонда AdVita.\n\n"
                "✨ Ваше первое доброе дело в новом году уже сделано! ✨\n\n"
                "Пусть этот год принесёт здоровье, радость и много тёплых моментов.\n\n"
                "Спасибо, что вы с нами! 💝"
            )
            await bot.send_message(telegram_id, text, parse_mode="Markdown")
            await update_user_new_year_flag(telegram_id)
            print(f"✅ Поздравление отправлено пользователю {telegram_id}")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Ошибка отправки поздравления пользователю {telegram_id}: {e}")


async def main() -> None:
    """Главная функция запуска бота"""
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения")
        return

    bot: Bot = Bot(token=BOT_TOKEN)
    dp: Dispatcher = Dispatcher(storage=MemoryStorage())

    dp.include_routers(start_router, calendar_router, faq_router)
    await set_commands(bot)

    scheduler: AsyncIOScheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_reminder, 'interval', hours=1, args=[bot], id='daily_reminder')
    scheduler.add_job(send_new_year_congrat, 'interval', hours=1, args=[bot], id='new_year_congrat')
    scheduler.start()

    print("🤖 Бот запущен. Strapi API:", STRAPI_URL)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())