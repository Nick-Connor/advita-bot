from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.menu import main_menu_keyboard
from strapi_client import get_user_by_telegram_id, create_user, set_consent, log_stat_event, StrapiAPIError

router = Router()


def consent_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для запроса согласия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, я согласен", callback_data="consent_yes"),
            InlineKeyboardButton(text="❌ Нет, я отказываюсь", callback_data="consent_no")
        ]
    ])


@router.message(Command("revoke_consent"))
async def revoke_consent(message: Message) -> None:
    """Отозвать согласие на обработку персональных данных"""
    try:
        user = await get_user_by_telegram_id(message.from_user.id)

        if not user:
            await message.answer(
                "❌ Вы ещё не зарегистрированы в боте.\n"
                "Отправьте /start для начала работы."
            )
            return

        if not user.get('consent_given'):
            await message.answer(
                "❌ Вы уже отозвали согласие или не давали его.\n"
                "Если передумаете, отправьте /start и согласитесь заново."
            )
            return

        await set_consent(message.from_user.id, False)

        await message.answer(
            "✅ **Вы отозвали согласие на обработку персональных данных.**\n\n"
            "Ваш прогресс сохранён, но новые ячейки открывать нельзя.\n"
            "Доступные функции:\n"
            "• ❓ Часто задаваемые вопросы\n"
            "• 🎁 Принять участие\n"
            "• ℹ️ О фонде\n\n"
            "Если передумаете, отправьте /start и согласитесь заново.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

        await log_stat_event("consent_revoked", message.from_user.id, message.from_user.username)

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в revoke_consent: {e}")
        await message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в revoke_consent: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start — приветствие и запрос согласия"""
    try:
        user = await get_user_by_telegram_id(message.from_user.id)

        if not user:
            await message.answer(
                "🎄 **Добро пожаловать в бот, который посвящен акции Первое дело Нового года!**\n\n"
                "Для участия в акции и получения доступа к адвент-календарю "
                "мне нужно сохранить ваш Telegram ID и информацию о прогрессе.\n\n"
                "Это ваша \"ёлочная игрушка\" — метка, отличающая вас от других участников.\n\n"
                "**Вы согласны на обработку персональных данных?**",
                reply_markup=consent_keyboard(),
                parse_mode="Markdown"
            )
        else:
            if user.get('consent_given'):
                await message.answer(
                    "🎄 Добро пожаловать!\n\n"
                    "С 1 по 31 декабря каждый день вас ждёт новая ячейка календаря.\n"
                    "Выберите действие:",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await message.answer(
                    "🎄 **Добро пожаловать в бот, который посвящен акции Первое дело Нового года!**\n\n"
                    "Для участия в акции и получения доступа к адвент-календарю "
                    "мне нужно сохранить ваш Telegram ID и информацию о прогрессе.\n\n"
                    "**Вы согласны на обработку персональных данных?**",
                    reply_markup=consent_keyboard(),
                    parse_mode="Markdown"
                )
    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в cmd_start: {e}")
        await message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в cmd_start: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery) -> None:
    """Обработчик согласия на обработку персональных данных"""
    try:
        user = await get_user_by_telegram_id(callback.from_user.id)

        if user:
            await set_consent(callback.from_user.id, True)
            await callback.message.edit_text(
                "✅ **Спасибо!**\n\n"
                "Ваше согласие принято. Теперь вам доступны все функции бота.\n\n"
                "🎄 Вы можете открывать ячейки календаря, получать награды и участвовать в акции.",
                parse_mode="Markdown"
            )
            await callback.message.answer(
                "🎄 Добро пожаловать!\n\n"
                "С 1 по 31 декабря каждый день вас ждёт новая ячейка календаря.\n"
                "Выберите действие:",
                reply_markup=main_menu_keyboard()
            )
        else:
            await create_user(callback.from_user.id, callback.from_user.username, consent_given=True)
            await callback.message.edit_text(
                "✅ **Спасибо!**\n\n"
                "Ваше согласие принято. Теперь вам доступны все функции бота.\n\n"
                "🎄 Вы можете открывать ячейки календаря, получать награды и участвовать в акции.",
                parse_mode="Markdown"
            )
            await callback.message.answer(
                "🎄 Добро пожаловать!\n\n"
                "С 1 по 31 декабря каждый день вас ждёт новая ячейка календаря.\n"
                "Выберите действие:",
                reply_markup=main_menu_keyboard()
            )

        await log_stat_event("user_registered", callback.from_user.id, callback.from_user.username)
        await callback.answer()

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в consent_yes: {e}")
        await callback.message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
        await callback.answer()
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в consent_yes: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
        await callback.answer()


@router.callback_query(F.data == "consent_no")
async def consent_no(callback: CallbackQuery) -> None:
    """Обработчик отказа от обработки персональных данных"""
    try:
        user = await get_user_by_telegram_id(callback.from_user.id)

        if not user:
            await create_user(callback.from_user.id, callback.from_user.username, consent_given=False)
        else:
            await set_consent(callback.from_user.id, False)

        await callback.message.edit_text(
            "❌ **Вы отказались от обработки персональных данных.**\n\n"
            "К сожалению, без этого вы не можете участвовать в акции и использовать адвент-календарь.\n\n"
            "Вы можете:\n"
            "• просматривать информацию о фонде\n"
            "• читать FAQ\n\n"
            "Если передумаете, отправьте команду /start заново.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        await callback.answer()

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в consent_no: {e}")
        await callback.message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
        await callback.answer()
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в consent_no: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
        await callback.answer()


@router.message(F.text == "ℹ️ О фонде")
async def about_fund(message: Message) -> None:
    """Показать информацию о благотворительном фонде AdVita"""
    await message.answer(
        "ℹ️ **Благотворительный фонд AdVita**\n\n"
        "Основан в 2002 году в Санкт-Петербурге. Помогает взрослым и детям "
        "с онкологическими, гематологическими и иммунологическими заболеваниями.\n\n"
        "**Основные направления:**\n"
        "• оплата лекарств и операций\n"
        "• поиск доноров костного мозга\n"
        "• диагностика и реабилитация\n"
        "• психологическая поддержка\n\n"
        "📎 Подробнее: https://advita.ru\n"
        "📍 Адрес: 192029, Санкт-Петербург, улица Ольминского, д. 6, лит. А, пом. 4-H\n"
        "📱 Телефон: 8-812-337-27-33\n"
        "📧 Email: info@advita.ru\n"
        "📝 Для запросов СМИ: pr@advita.ru\n"
        "🤝 По вопросам сотрудничества: partners@advita.ru",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


@router.message(F.text == "🎁 Принять участие")
async def participate(message: Message) -> None:
    """Отправить ссылку на сайт акции для оформления пожертвования"""
    await message.answer(
        "🎁 Оформить отложенное пожертвование можно на сайте:\n"
        "https://1delo.advita.ru\n\n"
        "Сумма спишется автоматически 1 января в 00:00.",
        reply_markup=main_menu_keyboard()
    )

    try:
        user = await get_user_by_telegram_id(message.from_user.id)
        if user:
            await log_stat_event("donation_click", message.from_user.id, message.from_user.username)
    except StrapiAPIError as e:
        print(f"⚠️ Не удалось записать событие donation_click: {e}")
    except Exception as e:
        print(f"⚠️ Ошибка при записи donation_click: {e}")


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery) -> None:
    """Вернуться в главное меню"""
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()