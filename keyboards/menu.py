from typing import List, Set, Dict, Any
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Главное меню (reply-клавиатура).

    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопками:
        - 📅 Адвент-календарь
        - ❓ Часто задаваемые вопросы
        - 🎁 Принять участие
        - ℹ️ О фонде
    """
    buttons: List[List[KeyboardButton]] = [
        [KeyboardButton(text="📅 Адвент-календарь")],
        [KeyboardButton(text="❓ Часто задаваемые вопросы")],
        [KeyboardButton(text="🎁 Принять участие")],
        [KeyboardButton(text="ℹ️ О фонде")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка возврата в главное меню (inline).

    Returns:
        InlineKeyboardMarkup: Клавиатура с одной кнопкой "🔙 В главное меню"
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ])


def calendar_inline_keyboard(current_day: int, opened_days: Set[int]) -> InlineKeyboardMarkup:
    """
    Сетка дней декабря с дизайном (inline-клавиатура).

    Для 2026 года: 1 декабря 2026 года - вторник.
    На каждой строке по 6 ячеек, 31 декабря отдельно.

    Args:
        current_day: Текущий день декабря (1-31)
        opened_days: Множество номеров дней, которые уже открыты

    Returns:
        InlineKeyboardMarkup: Клавиатура-календарь с:
        - Заголовком "🎄 ДЕКАБРЬ 2026 🎄"
        - Сеткой дней (по 6 в строке)
        - Отдельной ячейкой для 31 декабря
        - Прогресс-баром (🎅🏻 Твой прогресс: X/31 ███...)
        - Кнопкой возврата в главное меню
    """
    keyboard: List[List[InlineKeyboardButton]] = []

    # Заголовок календаря
    keyboard.append([InlineKeyboardButton(text="🎄 ДЕКАБРЬ 2026 🎄", callback_data="ignore")])

    row: List[InlineKeyboardButton] = []

    # Добавляем дни с 1 по 30 декабря (по 6 ячеек в строке)
    for day in range(1, 31):
        if day in opened_days:
            text: str = f"✅{day}"
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
    day_31: int = 31
    if day_31 in opened_days:
        text_31: str = f"✅ 31 декабря — НОВЫЙ ГОД! 🎄"
    elif day_31 < current_day:
        text_31 = f"📅 31 декабря (пропущен) 🎄"
    elif day_31 == current_day:
        text_31 = f"🎁 31 декабря — НОВЫЙ ГОД! 🎄"
    else:
        text_31 = f"🔒 31 декабря — НОВЫЙ ГОД! 🎄"

    keyboard.append([InlineKeyboardButton(text=text_31, callback_data="cell_31")])

    # Прогресс-бар
    progress: int = len(opened_days)
    bar_length: int = 10
    filled: int = int(progress / 31 * bar_length)
    bar: str = "█" * filled + "░" * (bar_length - filled)
    keyboard.append([InlineKeyboardButton(text=f"🎅🏻 Твой прогресс: {progress}/31 {bar}", callback_data="ignore")])

    keyboard.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def faq_categories_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура с категориями FAQ (inline).

    Args:
        categories: Список категорий вопросов

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками категорий,
        кнопкой "📝 Задать свой вопрос" и кнопкой возврата в главное меню
    """
    buttons: List[List[InlineKeyboardButton]] = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat, callback_data=f"faq_cat_{cat}")])
    buttons.append([InlineKeyboardButton(text="📝 Задать свой вопрос", callback_data="ask_question")])
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def faq_questions_keyboard(questions: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком вопросов FAQ (inline).

    Args:
        questions: Список словарей с вопросами, каждый содержит:
            - id: идентификатор вопроса
            - question: текст вопроса

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками вопросов
        (текст обрезается до 50 символов) и кнопкой возврата к категориям
    """
    buttons: List[List[InlineKeyboardButton]] = []
    for q in questions:
        # Обрезаем текст вопроса до 50 символов для компактности
        question_text: str = q['question'][:50]
        buttons.append([InlineKeyboardButton(text=question_text, callback_data=f"faq_q_{q['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_faq_cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)