import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.menu import calendar_inline_keyboard
from strapi_client import get_cell_by_day, get_user_by_telegram_id, save_user_progress, is_cell_opened, get_opened_days, \
    create_user, log_stat_event

router = Router()

# Для тестового режима (если не декабрь) -  True
TEST_MODE = True  # При тестировании = True, в декабре измените на False
TEST_DAY = 15  # Какой день декабря тестируем

# Словарь для хранения сообщений с календарём (для автоматического обновления)
user_calendar_messages = {}


def rich_text_to_string(rich_text):
    """Преобразует Rich Text из Strapi в обычную строку"""
    if isinstance(rich_text, str):
        return rich_text
    if isinstance(rich_text, list):
        result = []
        for element in rich_text:
            if element.get('type') == 'paragraph':
                for child in element.get('children', []):
                    result.append(child.get('text', ''))
                result.append('\n')
            elif element.get('type') == 'list':
                for item in element.get('children', []):
                    prefix = "• " if element.get('format') == 'unordered' else "1. "
                    for child in item.get('children', []):
                        result.append(f"{prefix}{child.get('text', '')}\n")
                result.append('\n')
        return ''.join(result).strip()
    return str(rich_text)


def is_valid_image_url(url):
    """Проверяет, является ли URL корректным для отправки фото"""
    if not url:
        return False
    if not isinstance(url, str):
        return False
    if not url.startswith('http'):
        return False
    if url.strip() == "":
        return False
    return True


@router.message(F.text == "📅 Адвент-календарь")
async def show_calendar(message: Message):
    if TEST_MODE:
        current_day = TEST_DAY
    else:
        now = datetime.datetime.now()
        if now.month != 12:
            await message.answer("❄️ Календарь доступен только в декабре. Загляните сюда 1 декабря!")
            return
        current_day = now.day

    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        user = await create_user(message.from_user.id, message.from_user.username)

    if not user:
        opened_days = set()
    else:
        opened_days = await get_opened_days(user['id'])

    keyboard = calendar_inline_keyboard(current_day, opened_days)

    # Сохраняем сообщение для последующего обновления
    if TEST_MODE:
        sent_msg = await message.answer(f"📆 **ТЕСТОВЫЙ РЕЖИМ**: сегодня {current_day} декабря. Выберите день:",
                                        reply_markup=keyboard, parse_mode="Markdown")
    else:
        sent_msg = await message.answer(f"📆 Сегодня {current_day} декабря. Выберите день:", reply_markup=keyboard)

    # Сохраняем ID сообщения и данные пользователя
    user_calendar_messages[message.from_user.id] = {
        'message_id': sent_msg.message_id,
        'chat_id': message.chat.id,
        'current_day': current_day,
        'opened_days': opened_days
    }


@router.callback_query(F.data.startswith("cell_"))
async def open_cell(callback: CallbackQuery):
    day = int(callback.data.split("_")[1])

    if TEST_MODE:
        current_day = TEST_DAY
    else:
        now = datetime.datetime.now()
        if now.month != 12:
            await callback.answer("Календарь доступен только в декабре.", show_alert=True)
            return
        current_day = now.day

    # 🔍 ОТЛАДКА 1: начало открытия ячейки
    print(f"🔍 [open_cell] Начало: day={day}, current_day={current_day}, TEST_MODE={TEST_MODE}")

    if day > current_day:
        await callback.answer(f"🔒 Ячейка {day} декабря откроется {day}.12.", show_alert=True)
        return

    # ✅ Получаем ячейку ОДИН РАЗ и сохраняем в переменную
    cell = await get_cell_by_day(day)
    if not cell:
        print(f"❌ [open_cell] Ячейка {day} не найдена в Strapi")
        await callback.answer("Контент для этой ячейки не найден.", show_alert=True)
        return

    # 🔍 ОТЛАДКА 2: информация о ячейке
    print(
        f"🔍 [open_cell] Ячейка получена: id={cell.get('id')}, day_number={cell.get('day_number')}, type={cell.get('cell_type')}")

    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        user = await create_user(callback.from_user.id, callback.from_user.username)
        print(f"🔍 [open_cell] Создан новый пользователь: {user.get('id') if user else 'None'}")
    else:
        print(
            f"🔍 [open_cell] Найден пользователь: id={user.get('id')}, telegram_id={user.get('telegram_id')}, consent={user.get('consent_given')}")

    # 🔍 ОТЛАДКА 3: проверка user
    if not user:
        print(f"❌ [open_cell] Пользователь не найден и не создан")
        already_opened = False
    else:
        cell_id = cell['id']  # внутренний ID ячейки в Strapi
        print(f"🔍 [open_cell] Проверка прогресса: user_id={user['id']}, cell_id={cell_id}")

        already_opened = await is_cell_opened(user['id'], cell_id)
        print(f"🔍 [open_cell] already_opened = {already_opened}")

        if not already_opened:
            # Сохраняем прогресс
            print(f"🔍 [open_cell] Сохранение прогресса...")
            save_result = await save_user_progress(user['id'], cell_id)
            print(f"🔍 [open_cell] Результат save_user_progress: {save_result}")

            # Записываем событие в статистику
            await log_stat_event("cell_opened", callback.from_user.id, str(day), callback.from_user.username)
            print(f"✅ Прогресс сохранён: пользователь {user['id']}, ячейка {day} (ID={cell_id})")

            # 🔍 ОТЛАДКА 4: проверка после сохранения
            check_again = await is_cell_opened(user['id'], cell_id)
            print(f"🔍 [open_cell] После сохранения: is_cell_opened = {check_again}")
        else:
            print(f"ℹ️ Ячейка {day} уже была открыта ранее")

    # ✅ Отправляем контент (используем сохранённую cell)
    text_content = rich_text_to_string(cell['text_content'])

    # Отправляем контент в зависимости от типа
    if cell['cell_type'] == 'quiz':
        quiz_question = rich_text_to_string(cell['text_content'])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"quiz_{day}_{idx}")]
            for idx, opt in enumerate(cell['quiz_options'])
        ])
        await callback.message.answer(
            f"*{cell['title']}*\n\n{quiz_question}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    elif cell['cell_type'] == 'sticker':
        if text_content:
            await callback.message.answer(text_content)
        if cell.get('sticker_file_id'):
            await callback.bot.send_sticker(callback.message.chat.id, cell['sticker_file_id'])
    else:
        text = f"*{cell['title']}*\n\n{text_content}"
        await callback.message.answer(text, parse_mode="Markdown")

        if is_valid_image_url(cell.get('image_url')):
            try:
                await callback.bot.send_photo(callback.message.chat.id, cell['image_url'])
            except Exception as e:
                print(f"Ошибка отправки фото: {e}")

    # ✅ Обновляем отображение календаря
    if user:
        opened_days = await get_opened_days(user['id'])
        print(f"🔍 [open_cell] Обновление календаря: opened_days={opened_days}")

        keyboard = calendar_inline_keyboard(current_day, opened_days)

        calendar_data = user_calendar_messages.get(callback.from_user.id)
        if calendar_data:
            try:
                if TEST_MODE:
                    await callback.bot.edit_message_text(
                        chat_id=calendar_data['chat_id'],
                        message_id=calendar_data['message_id'],
                        text=f"📆 **ТЕСТОВЫЙ РЕЖИМ**: сегодня {current_day} декабря. Выберите день:",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                else:
                    await callback.bot.edit_message_text(
                        chat_id=calendar_data['chat_id'],
                        message_id=calendar_data['message_id'],
                        text=f"📆 Сегодня {current_day} декабря. Выберите день:",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                # Обновляем сохранённые данные
                calendar_data['opened_days'] = opened_days
                calendar_data['current_day'] = current_day
                print(f"🔍 [open_cell] Календарь обновлён, открыто дней: {len(opened_days)}")
            except Exception as e:
                print(f"❌ Ошибка обновления календаря: {e}")

    await callback.answer(f"Ячейка {day} декабря открыта!")
    print(f"🔍 [open_cell] Завершение обработки ячейки {day}")


@router.callback_query(F.data.startswith("quiz_"))
async def check_quiz(callback: CallbackQuery):
    parts = callback.data.split("_")
    day = int(parts[1])
    answer_idx = int(parts[2])

    print(f"🔍 [check_quiz] Ответ на викторину: day={day}, answer_idx={answer_idx}")

    cell = await get_cell_by_day(day)
    if cell and cell.get('quiz_correct_answer') == answer_idx:
        print(f"✅ [check_quiz] Правильный ответ!")
        await callback.message.answer("🎉 Правильно! Молодец!")

        # ✅ Сохраняем прогресс при правильном ответе на викторину
        user = await get_user_by_telegram_id(callback.from_user.id)
        if user:
            cell_id = cell['id']
            print(f"🔍 [check_quiz] Проверка прогресса: user_id={user['id']}, cell_id={cell_id}")

            already_opened = await is_cell_opened(user['id'], cell_id)
            print(f"🔍 [check_quiz] already_opened = {already_opened}")

            if not already_opened:
                save_result = await save_user_progress(user['id'], cell_id)
                print(f"🔍 [check_quiz] save_user_progress result: {save_result}")

                await log_stat_event("cell_opened", callback.from_user.id, str(day), callback.from_user.username)
                print(f"✅ Прогресс сохранён (викторина): пользователь {user['id']}, ячейка {day}")

                # Проверка после сохранения
                check_again = await is_cell_opened(user['id'], cell_id)
                print(f"🔍 [check_quiz] После сохранения: is_cell_opened = {check_again}")

            # Обновляем отображение календаря
            opened_days = await get_opened_days(user['id'])
            print(f"🔍 [check_quiz] opened_days после обновления: {opened_days}")

            current_day = TEST_DAY if TEST_MODE else datetime.datetime.now().day
            keyboard = calendar_inline_keyboard(current_day, opened_days)

            calendar_data = user_calendar_messages.get(callback.from_user.id)
            if calendar_data:
                try:
                    if TEST_MODE:
                        await callback.bot.edit_message_text(
                            chat_id=calendar_data['chat_id'],
                            message_id=calendar_data['message_id'],
                            text=f"📆 **ТЕСТОВЫЙ РЕЖИМ**: сегодня {current_day} декабря. Выберите день:",
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                    else:
                        await callback.bot.edit_message_text(
                            chat_id=calendar_data['chat_id'],
                            message_id=calendar_data['message_id'],
                            text=f"📆 Сегодня {current_day} декабря. Выберите день:",
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                    print(f"🔍 [check_quiz] Календарь обновлён")
                except Exception as e:
                    print(f"❌ Ошибка обновления календаря: {e}")
        else:
            print(f"⚠️ [check_quiz] Пользователь не найден")
    else:
        print(
            f"❌ [check_quiz] Неправильный ответ! Ожидалось: {cell.get('quiz_correct_answer') if cell else 'None'}, получено: {answer_idx}")
        await callback.message.answer("❌ Неправильно. Попробуйте другой вариант!")
    await callback.answer()