from typing import List, Dict, Any, Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from strapi_client import (
    get_faq_categories, get_faq_by_category, send_user_question,
    log_stat_event, StrapiAPIError
)

router = Router()


# ---- Состояния для FSM (для вопроса сотруднику) ----
class QuestionStates(StatesGroup):
    waiting_for_question: State = State()
    waiting_for_email: State = State()


# ---- Клавиатуры ----
def categories_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    """Клавиатура с категориями"""
    buttons: List[List[InlineKeyboardButton]] = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat, callback_data=f"faq_cat_{cat}")])
    buttons.append([InlineKeyboardButton(text="📝 Задать свой вопрос", callback_data="ask_question")])
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def questions_keyboard(category: str, questions: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура с вопросами выбранной категории"""
    buttons: List[List[InlineKeyboardButton]] = []
    for q in questions:
        buttons.append([InlineKeyboardButton(
            text=q['question'][:50],
            callback_data=f"faq_q_{category}_{q['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_faq_cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_cats_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата к категориям"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_faq_cats")]
    ])


# ---- Обработчики FAQ ----
@router.message(F.text == "❓ Часто задаваемые вопросы")
async def show_categories(message: Message) -> None:
    """Показать категории вопросов FAQ"""
    try:
        categories: List[str] = await get_faq_categories()
        if not categories:
            await message.answer("📭 Пока нет категорий. Загляните позже!")
            return

        # Записываем событие просмотра FAQ в статистику
        await log_stat_event("faq_clicked", message.from_user.id, message.from_user.username)

        await message.answer("❓ Выберите категорию вопроса:", reply_markup=categories_keyboard(categories))

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в show_categories: {e}")
        await message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в show_categories: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")


@router.callback_query(F.data.startswith("faq_cat_"))
async def show_questions(callback: CallbackQuery) -> None:
    """Показать вопросы выбранной категории"""
    try:
        category: str = callback.data.split("_", 2)[2]
        questions: List[Dict[str, Any]] = await get_faq_by_category(category)

        if not questions:
            await callback.answer("В этой категории пока нет вопросов.", show_alert=True)
            return

        await callback.message.edit_text(
            f"📌 Категория: {category}\n\nВыберите вопрос:",
            reply_markup=questions_keyboard(category, questions)
        )
        await callback.answer()

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в show_questions: {e}")
        await callback.answer("⚠️ Сервис временно недоступен. Попробуйте позже.", show_alert=True)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в show_questions: {e}")
        await callback.answer("⚠️ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("faq_q_"))
async def show_answer(callback: CallbackQuery) -> None:
    """Показать ответ на выбранный вопрос"""
    try:
        parts: List[str] = callback.data.split("_")
        category: str = parts[2]
        qid: int = int(parts[3])

        questions: List[Dict[str, Any]] = await get_faq_by_category(category)
        answer_text: Optional[str] = None

        for q in questions:
            if q['id'] == qid:
                answer_text = q['answer']
                break

        if answer_text:
            await callback.message.answer(
                f"📝 *Ответ:*\n\n{answer_text}",
                parse_mode="Markdown",
                reply_markup=back_to_cats_keyboard()
            )
        else:
            await callback.message.answer("❌ Ответ не найден.", reply_markup=back_to_cats_keyboard())
        await callback.answer()

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в show_answer: {e}")
        await callback.answer("⚠️ Сервис временно недоступен. Попробуйте позже.", show_alert=True)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в show_answer: {e}")
        await callback.answer("⚠️ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_faq_cats")
async def back_to_categories(callback: CallbackQuery) -> None:
    """Вернуться к списку категорий"""
    try:
        categories: List[str] = await get_faq_categories()
        await callback.message.edit_text(
            "❓ Выберите категорию вопроса:",
            reply_markup=categories_keyboard(categories)
        )
        await callback.answer()

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в back_to_categories: {e}")
        await callback.answer("⚠️ Сервис временно недоступен. Попробуйте позже.", show_alert=True)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в back_to_categories: {e}")
        await callback.answer("⚠️ Произошла ошибка. Попробуйте позже.", show_alert=True)


# ---- Обработчики для отправки своего вопроса ----
@router.callback_query(F.data == "ask_question")
async def ask_question_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс отправки вопроса сотруднику"""
    await callback.message.answer(
        "📝 Напишите ваш вопрос текстом.\n\n"
        "Сотрудник фонда ответит вам в ближайшее время.\n\n"
        "Если хотите получить ответ на email, укажите его в следующем сообщении после вопроса."
    )
    await state.set_state(QuestionStates.waiting_for_question)
    await callback.answer()


@router.message(QuestionStates.waiting_for_question)
async def process_question(message: Message, state: FSMContext) -> None:
    """Получить вопрос от пользователя"""
    question: str = message.text
    await state.update_data(question=question)
    await message.answer(
        "✉️ Укажите ваш email для ответа (или отправьте /skip, чтобы пропустить):"
    )
    await state.set_state(QuestionStates.waiting_for_email)


@router.message(QuestionStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext) -> None:
    """Получить email и отправить вопрос в Strapi"""
    email: Optional[str] = None

    if message.text == "/skip":
        email = None
    else:
        email = message.text
        # Простая валидация email
        if "@" not in email or "." not in email:
            await message.answer(
                "❌ Неверный формат email. Пожалуйста, введите корректный email или нажмите /skip."
            )
            return

    data: Dict[str, Any] = await state.get_data()
    question: Optional[str] = data.get('question')

    if not question:
        await message.answer("❌ Произошла ошибка: вопрос не найден. Попробуйте заново.")
        await state.clear()
        return

    try:
        # Отправляем вопрос в Strapi (функция сама запишет событие question_sent)
        success: bool = await send_user_question(message.from_user.id, question, email)

        if success:
            await message.answer(
                "✅ Ваш вопрос отправлен! Сотрудник фонда ответит вам в ближайшее время.\n\n"
                "Вернуться в главное меню: /start"
            )
        else:
            await message.answer(
                "❌ Произошла ошибка при отправке вопроса. Пожалуйста, попробуйте позже."
            )

    except StrapiAPIError as e:
        print(f"❌ Ошибка Strapi в process_email: {e}")
        await message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка в process_email: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

    await state.clear()


@router.message(Command("skip"))
async def skip_email(message: Message, state: FSMContext) -> None:
    """Обработчик команды /skip для пропуска email"""
    current_state: Optional[str] = await state.get_state()
    if current_state == QuestionStates.waiting_for_email:
        await process_email(message, state)
    else:
        await message.answer("Сейчас не нужно пропускать email.")