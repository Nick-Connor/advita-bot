from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    """Главное меню (reply-клавиатура)"""
    buttons = [
        [KeyboardButton(text="📅 Адвент-календарь")],
        [KeyboardButton(text="❓ Часто задаваемые вопросы")],
        [KeyboardButton(text="🎁 Принять участие")],
        [KeyboardButton(text="ℹ️ О фонде")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def back_to_main_keyboard():
    """Кнопка возврата в главное меню (inline)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ])


def calendar_inline_keyboard(current_day: int, opened_days: set):
    """
    Сетка дней декабря с дизайном (inline-клавиатура)
    Для 2026 года: 1 декабря 2026 года - вторник
    На каждой строке по 6 ячеек, 31 декабря отдельно
    """
    keyboard = []

    # Заголовок календаря
    keyboard.append([InlineKeyboardButton(text="🎄 ДЕКАБРЬ 2026 🎄", callback_data="ignore")])

    # 1 декабря 2026 года - вторник
    row = []

    # Добавляем дни с 1 по 30 декабря (по 6 ячеек в строке)
    for day in range(1, 31):
        if day in opened_days:
            text = f"✅{day}"
        elif day < current_day:
            text = f"🗒{day}"
        elif day == current_day:
            text = f"🎁{day}"
        else:
            text = f"🔒{day}"

        row.append(InlineKeyboardButton(text=text, callback_data=f"cell_{day}"))

        # Каждые 6 ячеек добавляем строку
        if len(row) == 6:
            keyboard.append(row)
            row = []

    # Добавляем оставшиеся ячейки (если есть)
    if row:
        keyboard.append(row)

    # 31 декабря — отдельная большая ячейка на всю строку
    day = 31
    if day in opened_days:
        text = f"✅ 31 декабря — НОВЫЙ ГОД! 🎄"
    elif day < current_day:
        text = f"📅 31 декабря (пропущен) 🎄"
    elif day == current_day:
        text = f"🎁 31 декабря — НОВЫЙ ГОД! 🎄"
    else:
        text = f"🔒 31 декабря — НОВЫЙ ГОД! 🎄"

    keyboard.append([InlineKeyboardButton(text=text, callback_data=f"cell_31")])

    # Прогресс-бар
    progress = len(opened_days)
    bar_length = 10
    filled = int(progress / 31 * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    keyboard.append([InlineKeyboardButton(text=f"🎅🏻 Твой прогресс: {progress}/31 {bar}", callback_data="ignore")])

    keyboard.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def faq_categories_keyboard(categories: list):
    """Клавиатура с категориями FAQ (inline)"""
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat, callback_data=f"faq_cat_{cat}")])
    buttons.append([InlineKeyboardButton(text="📝 Задать свой вопрос", callback_data="ask_question")])
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def faq_questions_keyboard(questions: list):
    """Клавиатура со списком вопросов FAQ (inline)"""
    buttons = []
    for q in questions:
        buttons.append([InlineKeyboardButton(text=q['question'][:50], callback_data=f"faq_q_{q['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_faq_cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
