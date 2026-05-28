from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.menu import main_menu_keyboard, back_to_main_keyboard
from strapi_client import get_user_by_telegram_id, create_user, set_consent, log_stat_event

router = Router()


def consent_keyboard():
    """Клавиатура для запроса согласия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, я согласен", callback_data="consent_yes"),
            InlineKeyboardButton(text="❌ Нет, я отказываюсь", callback_data="consent_no")
        ]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)

    if not user:
        # Новый пользователь — запрашиваем согласие
        await message.answer(
            "🎄 **Добро пожаловать в бот, который посвящен акции Первое дело Нового года!**\n\n"
            "Для участия в акции и получения доступа к адвент-календарю "
            "мне нужно сохранить ваш Telegram ID и информацию о прогрессе.\n\n"
            "Это ваша «ёлочная игрушка» — метка, отличающая вас от других участников.\n\n"
            "**Вы согласны на обработку персональных данных?**",
            reply_markup=consent_keyboard(),
            parse_mode="Markdown"
        )
    else:
        # Пользователь уже есть
        if user.get('consent_given'):
            await message.answer(
                "🎄 Добро пожаловать!\n\n"
                "С 1 по 31 декабря каждый день вас ждёт новая ячейка календаря.\n"
                "Выберите действие:",
                reply_markup=main_menu_keyboard()
            )
        else:
            # Пользователь есть, но согласие не дано — запрашиваем снова
            await message.answer(
                "🎄 **Добро пожаловать в бот, который посвящен акции Первое дело Нового года!**\n\n"
                "Для участия в акции и получения доступа к адвент-календарю "
                "мне нужно сохранить ваш Telegram ID и информацию о прогрессе.\n\n"
                "**Вы согласны на обработку персональных данных?**",
                reply_markup=consent_keyboard(),
                parse_mode="Markdown"
            )


@router.callback_query(F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery):
    # Обновляем согласие пользователя
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
        # Если пользователя нет, создаём с согласием
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

    # Записываем событие регистрации в статистику
    await log_stat_event("user_registered", callback.from_user.id, callback.from_user.username)

    await callback.answer()


@router.callback_query(F.data == "consent_no")
async def consent_no(callback: CallbackQuery):
    # Создаём пользователя без согласия или обновляем существующего
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


@router.message(F.text == "ℹ️ О фонде")
async def about_fund(message: Message):
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
async def participate(message: Message):
    # Без проверки согласия — сразу отправляем ссылку
    await message.answer(
        "🎁 Оформить отложенное пожертвование можно на сайте:\n"
        "https://1delo.advita.ru\n\n"
        "Сумма спишется автоматически 1 января в 00:00.",
        reply_markup=main_menu_keyboard()
    )

    # Записываем событие перехода на сайт в статистику
    user = await get_user_by_telegram_id(message.from_user.id)
    if user:
        await log_stat_event("donation_click", message.from_user.id, message.from_user.username)


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()