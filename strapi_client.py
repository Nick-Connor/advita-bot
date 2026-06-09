import httpx
import os
from typing import List, Dict, Any, Optional, Union, TypedDict, cast
from dotenv import load_dotenv
import datetime

load_dotenv()

STRAPI_URL = os.getenv("STRAPI_URL")
STRAPI_API_TOKEN = os.getenv("STRAPI_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {STRAPI_API_TOKEN}",
    "Content-Type": "application/json"
}


# ========== Типизация ==========

class StrapiDataResponse(TypedDict):
    """Стандартный ответ Strapi с обёрткой data"""
    data: List[Dict[str, Any]]
    meta: Dict[str, Any]


class StrapiSingleResponse(TypedDict):
    """Ответ Strapi для одного элемента"""
    data: Dict[str, Any]
    meta: Dict[str, Any]


class AdventCellItem(TypedDict, total=False):
    """Тип для ячейки адвент-календаря"""
    id: int
    day_number: int
    cell_type: str
    title: str
    text_content: Union[str, List[Dict[str, Any]]]
    image_url: Optional[str]
    quiz_options: List[str]
    quiz_correct_answer: int
    sticker_file_id: Optional[str]


class FaqItem(TypedDict, total=False):
    """Тип для FAQ"""
    id: int
    question: str
    answer: str
    image_url: Optional[str]


class TelegramUserItem(TypedDict, total=False):
    """Тип для пользователя Telegram"""
    id: int
    documentId: str
    telegram_id: int
    username: str
    consent_given: bool
    registered_at: str
    last_notification_date: Optional[str]
    new_year_congrat_sent: bool


class UserProgressItem(TypedDict, total=False):
    """Тип для прогресса пользователя"""
    id: int
    user: Dict[str, Any]
    cell: Dict[str, Any]
    opened_at: str
    reward_received: bool


class UserQuestionItem(TypedDict, total=False):
    """Тип для вопроса пользователя"""
    id: int
    telegram_id: str
    question_text: str
    state: str
    created_at: str


class StatsEventItem(TypedDict, total=False):
    """Тип для события статистики"""
    id: int
    event_type: str
    event_value: str
    telegram_id: str
    timestamp: str


# ========== Исключения ==========

class StrapiAPIError(Exception):
    """Базовое исключение для ошибок Strapi API"""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class UserNotFoundError(StrapiAPIError):
    """Пользователь не найден"""
    pass


class CellNotFoundError(StrapiAPIError):
    """Ячейка не найдена"""
    pass


class ProgressSaveError(StrapiAPIError):
    """Ошибка сохранения прогресса"""
    pass


class StatsEventError(StrapiAPIError):
    """Ошибка записи статистики"""
    pass


# ========== Вспомогательные функции ==========

def _extract_items(response_data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Универсальное извлечение items из ответа Strapi.
    Поддерживает форматы:
    - прямой список: [...]
    - объект с data: {"data": [...], "meta": {...}}
    - объект с results: {"results": [...]}
    """
    if isinstance(response_data, list):
        return response_data
    if isinstance(response_data, dict):
        if 'data' in response_data and isinstance(response_data['data'], list):
            return response_data['data']
        if 'results' in response_data and isinstance(response_data['results'], list):
            return response_data['results']
    return []


def _extract_single_item(response_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Извлечение одного элемента из ответа Strapi"""
    items = _extract_items(response_data)
    if items and len(items) > 0:
        return items[0]
    return None


def _build_attributes(item: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение атрибутов из item (с учётом вложенности или без)"""
    if 'attributes' in item:
        return item['attributes']
    return item


def _handle_response(response: httpx.Response, context: str = "") -> Dict[str, Any]:
    """
    Обработка HTTP-ответа с проверкой ошибок.

    Args:
        response: HTTP-ответ от Strapi
        context: Контекст вызова для логирования

    Returns:
        Dict[str, Any]: Распарсенный JSON-ответ

    Raises:
        StrapiAPIError: При ошибке HTTP или отсутствии данных
    """
    if response.status_code >= 500:
        error_msg = f"Сервер Strapi вернул ошибку {response.status_code} ({context})"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg, status_code=response.status_code)

    if response.status_code >= 400:
        error_msg = f"Ошибка запроса к Strapi: {response.status_code} ({context})"
        try:
            error_data = response.json()
            if 'error' in error_data:
                error_msg += f" - {error_data['error'].get('message', '')}"
        except:
            pass
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg, status_code=response.status_code,
                             details=error_data if 'error_data' in locals() else None)

    try:
        return response.json()
    except Exception as e:
        error_msg = f"Ошибка парсинга JSON ответа Strapi ({context}): {e}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)


# ========== Пользователи (коллекция Telegram User) ==========

async def get_user_by_telegram_id(telegram_id: int) -> Optional[TelegramUserItem]:
    """
    Найти пользователя в кастомной коллекции TelegramUser по telegram_id.

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        Optional[TelegramUserItem]: Данные пользователя или None, если не найден

    Raises:
        StrapiAPIError: При ошибке соединения или некорректном ответе
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/telegram-users?filters[telegram_id][$eq]={telegram_id}"
            print(f"🔍 [get_user_by_telegram_id] Запрос: {url}")

            response = await client.get(url, headers=HEADERS)

            if response.status_code == 404:
                print(f"⚠️ [get_user_by_telegram_id] Пользователь с telegram_id={telegram_id} не найден")
                return None

            if response.status_code >= 400:
                _handle_response(response, f"get_user_by_telegram_id({telegram_id})")

            data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
            item: Optional[Dict[str, Any]] = _extract_single_item(data)

            if not item:
                print(f"⚠️ [get_user_by_telegram_id] Пользователь с telegram_id={telegram_id} не найден")
                return None

            attrs: Dict[str, Any] = _build_attributes(item)

            result: TelegramUserItem = {
                'id': item.get('id'),
                'documentId': item.get('documentId'),
                'telegram_id': attrs.get('telegram_id'),
                'username': attrs.get('username'),
                'consent_given': attrs.get('consent_given', False),
                'registered_at': attrs.get('registered_at'),
                'last_notification_date': attrs.get('last_notification_date'),
                'new_year_congrat_sent': attrs.get('new_year_congrat_sent', False)
            }
            print(f"✅ [get_user_by_telegram_id] Пользователь найден: id={result.get('id')}, documentId={result.get('documentId')}")
            return result

    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при получении пользователя {telegram_id}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except httpx.ConnectError:
        error_msg = f"Ошибка подключения к Strapi при получении пользователя {telegram_id}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except Exception as e:
        error_msg = f"Неизвестная ошибка при получении пользователя {telegram_id}: {e}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)


async def create_user(telegram_id: int, username: str = None, consent_given: bool = False) -> Optional[TelegramUserItem]:
    """
    Создать пользователя в кастомной коллекции TelegramUser.

    Args:
        telegram_id: Telegram ID пользователя
        username: Имя пользователя (опционально)
        consent_given: Согласие на обработку данных

    Returns:
        Optional[TelegramUserItem]: Созданный пользователь или None

    Raises:
        StrapiAPIError: При ошибке создания пользователя
    """
    print(f"🔍 [create_user] Начало: telegram_id={telegram_id}, username={username}, consent_given={consent_given}")

    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/telegram-users"

            payload: Dict[str, Any] = {
                "data": {
                    "telegram_id": telegram_id,
                    "username": username or "",
                    "consent_given": consent_given,
                    "registered_at": datetime.datetime.now().isoformat()
                }
            }

            print(f"🔍 [create_user] URL: {url}")
            print(f"🔍 [create_user] PAYLOAD: {payload}")

            response = await client.post(url, json=payload, headers=HEADERS)

            if response.status_code >= 400:
                _handle_response(response, f"create_user({telegram_id})")

            data: Dict[str, Any] = response.json()

            if 'data' in data:
                item: Dict[str, Any] = cast(Dict[str, Any], data['data'])
                attrs: Dict[str, Any] = _build_attributes(item)
                result: TelegramUserItem = {
                    'id': item.get('id'),
                    'documentId': item.get('documentId'),
                    'telegram_id': attrs.get('telegram_id'),
                    'username': attrs.get('username'),
                    'consent_given': attrs.get('consent_given', False),
                    'registered_at': attrs.get('registered_at'),
                    'last_notification_date': attrs.get('last_notification_date'),
                    'new_year_congrat_sent': attrs.get('new_year_congrat_sent', False)
                }
                print(f"✅ [create_user] Пользователь создан: id={result.get('id')}")
                return result
            else:
                attrs = _build_attributes(data)
                result = {
                    'id': data.get('id'),
                    'documentId': data.get('documentId'),
                    'telegram_id': attrs.get('telegram_id'),
                    'username': attrs.get('username'),
                    'consent_given': attrs.get('consent_given', False),
                    'registered_at': attrs.get('registered_at'),
                    'last_notification_date': attrs.get('last_notification_date'),
                    'new_year_congrat_sent': attrs.get('new_year_congrat_sent', False)
                }
                print(f"✅ [create_user] Пользователь создан: id={result.get('id')}")
                return result

    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при создании пользователя {telegram_id}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except httpx.ConnectError:
        error_msg = f"Ошибка подключения к Strapi при создании пользователя {telegram_id}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except Exception as e:
        error_msg = f"Неизвестная ошибка при создании пользователя {telegram_id}: {e}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)


async def set_consent(telegram_id: int, consent: bool) -> bool:
    """
    Обновить поле consent_given у пользователя.

    Args:
        telegram_id: Telegram ID пользователя
        consent: Новое значение согласия

    Returns:
        bool: True при успешном обновлении

    Raises:
        UserNotFoundError: Если пользователь не найден
        StrapiAPIError: При других ошибках
    """
    try:
        user: Optional[TelegramUserItem] = await get_user_by_telegram_id(telegram_id)
        if not user:
            error_msg = f"Пользователь {telegram_id} не найден"
            print(f"❌ [set_consent] {error_msg}")
            raise UserNotFoundError(error_msg)

        user_identifier = user.get('documentId') or user.get('id')
        if not user_identifier:
            error_msg = f"Не удалось получить идентификатор пользователя {telegram_id}"
            print(f"❌ [set_consent] {error_msg}")
            raise StrapiAPIError(error_msg)

        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/telegram-users/{user_identifier}"
            payload: Dict[str, Any] = {"data": {"consent_given": consent}}

            print(f"🔍 [set_consent] URL: {url}")
            print(f"🔍 [set_consent] PAYLOAD: {payload}")
            print(f"🔍 [set_consent] Используемый идентификатор: {user_identifier} (тип: {type(user_identifier)})")

            response = await client.put(url, json=payload, headers=HEADERS)

            if response.status_code >= 400:
                _handle_response(response, f"set_consent({telegram_id})")

            if response.status_code == 200:
                print(f"✅ [set_consent] consent_given обновлён на {consent}")
                return True
            else:
                error_msg = f"Неожиданный статус ответа: {response.status_code}"
                print(f"❌ [set_consent] {error_msg}")
                return False

    except UserNotFoundError:
        raise
    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при обновлении согласия пользователя {telegram_id}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except Exception as e:
        error_msg = f"Неизвестная ошибка при обновлении согласия пользователя {telegram_id}: {e}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)


async def update_user_new_year_flag(telegram_id: int, telegram_user_id: int) -> bool:
    """Обновить флаг новогоднего поздравления у пользователя"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/telegram-users/{telegram_user_id}"
            payload: Dict[str, Any] = {"data": {"new_year_congrat_sent": True}}
            response = await client.put(url, json=payload, headers=HEADERS)

            if response.status_code >= 400:
                _handle_response(response, f"update_user_new_year_flag({telegram_id})")

            return response.status_code == 200
    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при обновлении новогоднего флага пользователя {telegram_id}"
        print(f"❌ {error_msg}")
        return False
    except Exception as e:
        error_msg = f"Ошибка при обновлении новогоднего флага пользователя {telegram_id}: {e}"
        print(f"❌ {error_msg}")
        return False


# ========== Прогресс пользователя ==========

async def is_cell_opened(user_id: int, cell_id: int) -> bool:
    """
    Проверить, открывал ли пользователь эту ячейку.

    Args:
        user_id: ID пользователя в Strapi
        cell_id: ID ячейки в Strapi

    Returns:
        bool: True если ячейка уже открыта, False если нет
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/user-progresses?filters[user][id][$eq]={user_id}&filters[cell][id][$eq]={cell_id}"
            response = await client.get(url, headers=HEADERS)

            if response.status_code == 404:
                return False

            if response.status_code >= 400:
                _handle_response(response, f"is_cell_opened({user_id}, {cell_id})")

            data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
            items: List[Dict[str, Any]] = _extract_items(data)
            return len(items) > 0

    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при проверке открытия ячейки (user={user_id}, cell={cell_id})"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except Exception as e:
        error_msg = f"Неизвестная ошибка при проверке открытия ячейки: {e}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)


async def save_user_progress(user_id: int, cell_id: int) -> bool:
    """
    Сохранить факт открытия ячейки.

    Args:
        user_id: ID пользователя в Strapi
        cell_id: ID ячейки в Strapi

    Returns:
        bool: True при успешном сохранении
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/user-progresses"
            payload: Dict[str, Any] = {
                "data": {
                    "user": user_id,
                    "cell": cell_id,
                    "reward_received": True,
                    "opened_at": datetime.datetime.now().isoformat()
                }
            }
            response = await client.post(url, json=payload, headers=HEADERS)

            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ Прогресс сохранён: user={user_id}, cell={cell_id}")
                return True
            else:
                print(f"❌ Ошибка сохранения прогресса: {response.status_code} - {response.text[:200]}")
                return False

    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при сохранении прогресса (user={user_id}, cell={cell_id})"
        print(f"❌ {error_msg}")
        return False
    except Exception as e:
        error_msg = f"Неизвестная ошибка при сохранении прогресса: {e}"
        print(f"❌ {error_msg}")
        return False


async def get_opened_days(user_id: int) -> set:
    """
    Получить список номеров дней, которые уже открыл пользователь.

    Args:
        user_id: ID пользователя в Strapi

    Returns:
        set: Множество номеров открытых дней
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/user-progresses?filters[user][id][$eq]={user_id}&populate=cell"

            print(f"🔍 [get_opened_days] Запрос: {url}")
            response = await client.get(url, headers=HEADERS)

            if response.status_code >= 400:
                _handle_response(response, f"get_opened_days({user_id})")

            opened_days: set = set()

            if response.status_code == 200:
                data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
                items: List[Dict[str, Any]] = _extract_items(data)
                print(f"🔍 [get_opened_days] Найдено записей прогресса: {len(items)}")

                for item in items:
                    attrs: Dict[str, Any] = _build_attributes(item)
                    cell_data: Dict[str, Any] = attrs.get('cell', {})
                    day_number: Optional[int] = None

                    if isinstance(cell_data, dict):
                        if 'day_number' in cell_data:
                            day_number = cell_data.get('day_number')
                        elif 'data' in cell_data and cell_data['data']:
                            cell_inner: Dict[str, Any] = cell_data['data']
                            if isinstance(cell_inner, dict):
                                if 'attributes' in cell_inner:
                                    day_number = cell_inner['attributes'].get('day_number')
                                else:
                                    day_number = cell_inner.get('day_number')
                        elif 'attributes' in cell_data:
                            day_number = cell_data['attributes'].get('day_number')

                    if day_number:
                        opened_days.add(day_number)
                        print(f"🔍 [get_opened_days] Добавлен день: {day_number}")

            print(f"🔍 [get_opened_days] Итоговые открытые дни: {opened_days}")
            return opened_days

    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при получении открытых дней (user={user_id})"
        print(f"❌ {error_msg}")
        return set()
    except Exception as e:
        error_msg = f"Ошибка при получении открытых дней: {e}"
        print(f"❌ {error_msg}")
        return set()


# ========== Статистика ==========

async def log_stat_event(event_type: str, telegram_id: int, event_value: str = None, username: str = None) -> bool:
    """
    Записать событие в статистику Strapi (коллекция Stats event).

    Args:
        event_type: Тип события (cell_opened, faq_clicked, etc.)
        telegram_id: Telegram ID пользователя
        event_value: Дополнительное значение события
        username: Имя пользователя (опционально)

    Returns:
        bool: True при успешной записи
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/stats-events"
            payload: Dict[str, Any] = {
                "data": {
                    "event_type": event_type,
                    "event_value": event_value or "",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "telegram_id": str(telegram_id)
                }
            }
            response = await client.post(url, json=payload, headers=HEADERS)

            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ Событие {event_type} записано в статистику Strapi")
                return True
            else:
                print(f"⚠️ Не удалось записать событие: {response.status_code} - {response.text[:200]}")
                return False

    except httpx.TimeoutException:
        print(f"❌ Таймаут соединения при записи события {event_type}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при записи события {event_type}: {e}")
        return False


# ========== Адвент-календарь ==========

async def get_cell_by_day(day: int) -> Optional[AdventCellItem]:
    """
    Получить ячейку календаря по номеру дня.

    Args:
        day: Номер дня (1-31)

    Returns:
        Optional[AdventCellItem]: Данные ячейки или None, если не найдена
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/advent-cells?filters[day_number][$eq]={day}&populate=image"
            response = await client.get(url, headers=HEADERS)

            if response.status_code == 404:
                print(f"⚠️ Ячейка для дня {day} не найдена в Strapi")
                return None

            if response.status_code >= 400:
                _handle_response(response, f"get_cell_by_day({day})")

            data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
            items: List[Dict[str, Any]] = _extract_items(data)

            if not items:
                print(f"⚠️ Ячейка для дня {day} не найдена в Strapi")
                return None

            item: Dict[str, Any] = items[0]
            attrs: Dict[str, Any] = _build_attributes(item)

            image_url: Optional[str] = None
            image_data = attrs.get('image')

            if image_data:
                if isinstance(image_data, dict):
                    if image_data.get('url'):
                        image_url = image_data['url']
                    elif image_data.get('data'):
                        img_inner: Dict[str, Any] = image_data['data']
                        if isinstance(img_inner, dict):
                            if img_inner.get('url'):
                                image_url = img_inner['url']
                            elif img_inner.get('attributes', {}).get('url'):
                                image_url = img_inner['attributes']['url']
                elif isinstance(image_data, str) and image_data.startswith('http'):
                    image_url = image_data

            if image_url and not image_url.startswith('http'):
                base_url: str = STRAPI_URL.replace('/api', '').replace('/admin', '')
                image_url = f"{base_url}{image_url}"

            result: AdventCellItem = {
                'id': item.get('id'),
                'day_number': attrs.get('day_number'),
                'cell_type': attrs.get('cell_type'),
                'title': attrs.get('title'),
                'text_content': attrs.get('text_content'),
                'image_url': image_url,
                'quiz_options': attrs.get('quiz_options', []),
                'quiz_correct_answer': attrs.get('quiz_correct_answer'),
                'sticker_file_id': attrs.get('sticker_file_id'),
            }
            return result

    except httpx.TimeoutException:
        error_msg = f"Таймаут соединения при получении ячейки {day}"
        print(f"❌ {error_msg}")
        raise StrapiAPIError(error_msg)
    except Exception as e:
        error_msg = f"Ошибка при получении ячейки {day}: {e}"
        print(f"❌ {error_msg}")
        return None


# ========== FAQ ==========

async def get_faq_categories() -> List[str]:
    """
    Получить список уникальных категорий FAQ.

    Returns:
        List[str]: Список категорий или пустой список при ошибке
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/faqs"

            # ========== ОТЛАДКА ==========
            print(f"🔍 [get_faq_categories] ========== НАЧАЛО ОТЛАДКИ ==========")
            print(f"🔍 [get_faq_categories] URL: {url}")
            print(f"🔍 [get_faq_categories] STRAPI_URL: {STRAPI_URL}")
            print(
                f"🔍 [get_faq_categories] TOKEN (первые 20 символов): {STRAPI_API_TOKEN[:20] if STRAPI_API_TOKEN else 'None'}...")
            print(f"🔍 [get_faq_categories] HEADERS: {HEADERS}")
            # ========== КОНЕЦ ОТЛАДКИ ==========

            response = await client.get(url, headers=HEADERS)

            # ========== ОТЛАДКА ==========
            print(f"🔍 [get_faq_categories] RESPONSE STATUS: {response.status_code}")
            print(f"🔍 [get_faq_categories] RESPONSE HEADERS: {dict(response.headers)}")
            print(f"🔍 [get_faq_categories] RESPONSE TEXT (первые 500 символов): {response.text[:500]}")
            # ========== КОНЕЦ ОТЛАДКИ ==========

            if response.status_code >= 400:
                _handle_response(response, "get_faq_categories")

            if response.status_code == 200:
                data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
                items: List[Dict[str, Any]] = _extract_items(data)

                # ========== ОТЛАДКА ==========
                print(f"🔍 [get_faq_categories] Найдено элементов: {len(items)}")
                # ========== КОНЕЦ ОТЛАДКИ ==========

                categories: set = set()
                for item in items:
                    attrs: Dict[str, Any] = _build_attributes(item)
                    cat: Optional[str] = attrs.get('category')
                    if cat:
                        categories.add(cat)

                # ========== ОТЛАДКА ==========
                print(f"🔍 [get_faq_categories] Найдено категорий: {categories}")
                print(f"🔍 [get_faq_categories] ========== КОНЕЦ ОТЛАДКИ ==========")
                # ========== КОНЕЦ ОТЛАДКИ ==========

                return sorted(list(categories))

            # ========== ОТЛАДКА ==========
            print(f"🔍 [get_faq_categories] Статус не 200, возвращаем пустой список")
            print(f"🔍 [get_faq_categories] ========== КОНЕЦ ОТЛАДКИ ==========")
            # ========== КОНЕЦ ОТЛАДКИ ==========

            return []

    except Exception as e:
        print(f"❌ Ошибка при получении категорий FAQ: {e}")
        print(f"❌ [get_faq_categories] Тип ошибки: {type(e).__name__}")
        print(f"❌ [get_faq_categories] Полная ошибка: {e}")
        return []


async def get_faq_by_category(category: str) -> List[FaqItem]:
    """
    Получить вопросы и ответы по категории.

    Args:
        category: Название категории

    Returns:
        List[FaqItem]: Список вопросов или пустой список при ошибке
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/faqs?filters[category][$eq]={category}&sort=order_index:asc"

            # ========== ОТЛАДКА ==========
            print(f"🔍 [get_faq_by_category] ========== НАЧАЛО ОТЛАДКИ ==========")
            print(f"🔍 [get_faq_by_category] URL: {url}")
            print(f"🔍 [get_faq_by_category] STRAPI_URL: {STRAPI_URL}")
            print(f"🔍 [get_faq_by_category] category: {category}")
            print(
                f"🔍 [get_faq_by_category] TOKEN (первые 20 символов): {STRAPI_API_TOKEN[:20] if STRAPI_API_TOKEN else 'None'}...")
            print(f"🔍 [get_faq_by_category] HEADERS: {HEADERS}")
            # ========== КОНЕЦ ОТЛАДКИ ==========

            response = await client.get(url, headers=HEADERS)

            # ========== ОТЛАДКА ==========
            print(f"🔍 [get_faq_by_category] RESPONSE STATUS: {response.status_code}")
            print(f"🔍 [get_faq_by_category] RESPONSE HEADERS: {dict(response.headers)}")
            print(f"🔍 [get_faq_by_category] RESPONSE TEXT (первые 500 символов): {response.text[:500]}")
            # ========== КОНЕЦ ОТЛАДКИ ==========

            if response.status_code >= 400:
                _handle_response(response, f"get_faq_by_category({category})")

            result: List[FaqItem] = []
            if response.status_code == 200:
                data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
                items: List[Dict[str, Any]] = _extract_items(data)

                # ========== ОТЛАДКА ==========
                print(f"🔍 [get_faq_by_category] Найдено элементов: {len(items)}")
                # ========== КОНЕЦ ОТЛАДКИ ==========

                for item in items:
                    attrs: Dict[str, Any] = _build_attributes(item)

                    faq_item: FaqItem = {
                        'id': item.get('id'),
                        'question': attrs.get('question'),
                        'answer': attrs.get('answer'),
                        'image_url': attrs.get('image', {}).get('url') if isinstance(attrs.get('image'), dict) else None
                    }
                    result.append(faq_item)

            # ========== ОТЛАДКА ==========
            print(f"🔍 [get_faq_by_category] Результат: {len(result)} вопросов")
            print(f"🔍 [get_faq_by_category] ========== КОНЕЦ ОТЛАДКИ ==========")
            # ========== КОНЕЦ ОТЛАДКИ ==========

            return result

    except Exception as e:
        print(f"❌ Ошибка при получении FAQ по категории {category}: {e}")
        print(f"❌ [get_faq_by_category] Тип ошибки: {type(e).__name__}")
        print(f"❌ [get_faq_by_category] Полная ошибка: {e}")
        return []


# ========== Вопросы пользователей ==========

async def send_user_question(telegram_id: int, question: str, email: str = None) -> bool:
    """
    Сохранить вопрос от пользователя в Strapi.

    Args:
        telegram_id: Telegram ID пользователя
        question: Текст вопроса
        email: Email пользователя (опционально)

    Returns:
        bool: True при успешном сохранении
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/user-questions"
            payload: Dict[str, Any] = {
                "data": {
                    "question_text": question,
                    "email": email or "",
                    "state": "new",
                    "telegram_id": str(telegram_id)
                }
            }
            response = await client.post(url, json=payload, headers=HEADERS)

            if response.status_code >= 400:
                _handle_response(response, f"send_user_question({telegram_id})")

            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ Вопрос сохранён в Strapi: {question[:50]}...")
                await log_stat_event("question_sent", telegram_id, question[:50])
                return True
            else:
                print(f"❌ Ошибка сохранения вопроса: {response.status_code} - {response.text[:200]}")
                return False

    except httpx.TimeoutException:
        print(f"❌ Таймаут соединения при сохранении вопроса от {telegram_id}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при сохранении вопроса: {e}")
        return False


# ========== Статистика (чтение) ==========

async def get_user_questions() -> List[UserQuestionItem]:
    """
    Получить все вопросы пользователей из Strapi.

    Returns:
        List[UserQuestionItem]: Список вопросов или пустой список при ошибке
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/user-questions?sort=createdAt:desc"
            response = await client.get(url, headers=HEADERS)

            if response.status_code >= 400:
                _handle_response(response, "get_user_questions")

            result: List[UserQuestionItem] = []
            if response.status_code == 200:
                data: Union[List[Dict[str, Any]], Dict[str, Any]] = response.json()
                items: List[Dict[str, Any]] = _extract_items(data)

                for item in items:
                    attrs: Dict[str, Any] = _build_attributes(item)

                    question_item: UserQuestionItem = {
                        'id': item.get('id'),
                        'telegram_id': attrs.get('telegram_id'),
                        'question_text': attrs.get('question_text'),
                        'state': attrs.get('state'),
                        'created_at': attrs.get('createdAt')
                    }
                    result.append(question_item)
            return result

    except Exception as e:
        print(f"❌ Ошибка при получении вопросов пользователей: {e}")
        return []


async def get_stats() -> Dict[str, int]:
    """
    Собрать базовую статистику из Strapi.

    Returns:
        Dict[str, int]: Статистика (количество пользователей, открытых ячеек)
    """
    try:
        async with httpx.AsyncClient() as client:
            users_count: int = 0
            try:
                users_resp = await client.get(f"{STRAPI_URL}/telegram-users", headers=HEADERS)
                if users_resp.status_code == 200:
                    users_data: Union[List[Dict[str, Any]], Dict[str, Any]] = users_resp.json()
                    users_items: List[Dict[str, Any]] = _extract_items(users_data)
                    users_count = len(users_items)
                else:
                    print(f"⚠️ Не удалось получить количество пользователей: {users_resp.status_code}")
            except Exception as e:
                print(f"⚠️ Ошибка при получении количества пользователей: {e}")

            cells_opened: int = 0
            try:
                progress_resp = await client.get(f"{STRAPI_URL}/user-progresses", headers=HEADERS)
                if progress_resp.status_code == 200:
                    progress_data: Union[List[Dict[str, Any]], Dict[str, Any]] = progress_resp.json()
                    progress_items: List[Dict[str, Any]] = _extract_items(progress_data)
                    cells_opened = len(progress_items)
                else:
                    print(f"⚠️ Не удалось получить количество открытых ячеек: {progress_resp.status_code}")
            except Exception as e:
                print(f"⚠️ Ошибка при получении количества открытых ячеек: {e}")

            return {
                'users_count': users_count,
                'cells_opened': cells_opened,
                'questions_count': 0
            }

    except Exception as e:
        print(f"❌ Ошибка при сборе статистики: {e}")
        return {
            'users_count': 0,
            'cells_opened': 0,
            'questions_count': 0
        }