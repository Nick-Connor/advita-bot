import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

STRAPI_URL = os.getenv("STRAPI_URL")
STRAPI_API_TOKEN = os.getenv("STRAPI_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {STRAPI_API_TOKEN}",
    "Content-Type": "application/json"
}


def _extract_items(response_data):
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


# ---------- Пользователи (кастомная коллекция Telegram User) ----------
async def get_user_by_telegram_id(telegram_id: int):
    """Найти пользователя в кастомной коллекции TelegramUser по telegram_id"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/telegram-users?filters[telegram_id][$eq]={telegram_id}"
        response = await client.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)
            if items and len(items) > 0:
                return items[0]
    return None


async def create_user(telegram_id: int, username: str = None, consent_given: bool = False):
    """Создать пользователя в кастомной коллекции TelegramUser"""
    import datetime

    print(f"🔍 [create_user] Начало: telegram_id={telegram_id}, username={username}, consent_given={consent_given}")

    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/telegram-users"

        payload = {
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

        print(f"🔍 [create_user] STATUS: {response.status_code}")
        print(f"🔍 [create_user] RESPONSE: {response.text[:500]}")

        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            if isinstance(data, dict) and 'data' in data:
                return data.get('data')
            return data

    print(f"❌ [create_user] Создание пользователя не удалось")
    return None


async def set_consent(telegram_id: int, consent: bool):
    """Обновить поле consent_given у пользователя"""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        print(f"❌ [set_consent] Пользователь {telegram_id} не найден")
        return False

    user_id = user.get('id')
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/telegram-users/{user_id}"
        payload = {"data": {"consent_given": consent}}

        print(f"🔍 [set_consent] URL: {url}")
        print(f"🔍 [set_consent] PAYLOAD: {payload}")

        response = await client.put(url, json=payload, headers=HEADERS)

        print(f"🔍 [set_consent] STATUS: {response.status_code}")

        if response.status_code == 200:
            print(f"✅ [set_consent] consent_given обновлён на {consent}")
            return True
        else:
            print(f"❌ [set_consent] Ошибка: {response.text[:200]}")
            return False


async def update_user_new_year_flag(telegram_id: int, telegram_user_id: int):
    """Обновить флаг новогоднего поздравления у пользователя"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/telegram-users/{telegram_user_id}"
        payload = {"data": {"new_year_congrat_sent": True}}
        response = await client.put(url, json=payload, headers=HEADERS)
        return response.status_code == 200


# ---------- Прогресс пользователя (в Strapi) ----------
async def is_cell_opened(user_id: int, cell_id: int):
    """Проверить, открывал ли пользователь эту ячейку"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/user-progresses?filters[user][id][$eq]={user_id}&filters[cell][id][$eq]={cell_id}"
        response = await client.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)
            return len(items) > 0
    return False


async def save_user_progress(user_id: int, cell_id: int):
    """Сохранить факт открытия ячейки"""
    import datetime
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/user-progresses"
        payload = {
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


async def get_opened_days(user_id: int):
    """Получить список номеров дней, которые уже открыл пользователь"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/user-progresses?filters[user][id][$eq]={user_id}&populate=cell"

        print(f"🔍 [get_opened_days] Запрос: {url}")
        response = await client.get(url, headers=HEADERS)
        opened_days = set()

        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)
            print(f"🔍 [get_opened_days] Найдено записей прогресса: {len(items)}")

            for item in items:
                if 'attributes' in item:
                    attrs = item['attributes']
                else:
                    attrs = item

                # Получаем данные о ячейке из связи
                cell_data = attrs.get('cell', {})

                # Извлекаем day_number напрямую из cell_data (без дополнительного запроса!)
                day_number = None

                if isinstance(cell_data, dict):
                    # Прямое извлечение day_number (самый простой вариант)
                    if 'day_number' in cell_data:
                        day_number = cell_data.get('day_number')
                    # Если есть вложенная структура data
                    elif 'data' in cell_data and cell_data['data']:
                        cell_inner = cell_data['data']
                        if isinstance(cell_inner, dict):
                            if 'attributes' in cell_inner:
                                day_number = cell_inner['attributes'].get('day_number')
                            else:
                                day_number = cell_inner.get('day_number')
                    # Если есть attributes напрямую
                    elif 'attributes' in cell_data:
                        day_number = cell_data['attributes'].get('day_number')

                if day_number:
                    opened_days.add(day_number)
                    print(f"🔍 [get_opened_days] Добавлен день: {day_number}")
                else:
                    print(f"🔍 [get_opened_days] Не удалось получить day_number из cell_data, keys: {cell_data.keys() if isinstance(cell_data, dict) else 'not a dict'}")

        print(f"🔍 [get_opened_days] Итоговые открытые дни: {opened_days}")
        return opened_days


# ---------- Статистика в Strapi ----------
async def log_stat_event(event_type: str, telegram_id: int, event_value: str = None, username: str = None):
    """Записать событие в статистику Strapi (коллекция Stats event)"""
    import datetime
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/stats-events"
            payload = {
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
    except Exception as e:
        print(f"❌ Ошибка при записи статистики: {e}")
        return False


# ---------- Адвент-календарь (чтение из Strapi) ----------
async def get_cell_by_day(day: int):
    """Получить ячейку календаря по номеру дня"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/advent-cells?filters[day_number][$eq]={day}&populate=image"
        response = await client.get(url, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)

            if not items:
                print(f"⚠️ Ячейка для дня {day} не найдена в Strapi")
                return None

            item = items[0]

            if 'attributes' in item:
                attrs = item['attributes']
            else:
                attrs = item

            # Обработка изображения
            image_url = None
            image_data = attrs.get('image')

            if image_data:
                if isinstance(image_data, dict):
                    if image_data.get('url'):
                        image_url = image_data['url']
                    elif image_data.get('data'):
                        img_inner = image_data['data']
                        if isinstance(img_inner, dict):
                            if img_inner.get('url'):
                                image_url = img_inner['url']
                            elif img_inner.get('attributes', {}).get('url'):
                                image_url = img_inner['attributes']['url']
                elif isinstance(image_data, str) and image_data.startswith('http'):
                    image_url = image_data

            if image_url and not image_url.startswith('http'):
                base_url = STRAPI_URL.replace('/api', '').replace('/admin', '')
                image_url = f"{base_url}{image_url}"

            return {
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

        print(f"❌ Ошибка получения ячейки {day}: HTTP {response.status_code}")
        return None


# ---------- FAQ (чтение из Strapi) ----------
async def get_faq_categories():
    """Получить список уникальных категорий FAQ"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/faqs"
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)

            categories = set()
            for item in items:
                if 'attributes' in item:
                    cat = item['attributes'].get('category')
                else:
                    cat = item.get('category')
                if cat:
                    categories.add(cat)
            return sorted(list(categories))
        return []


async def get_faq_by_category(category: str):
    """Получить вопросы и ответы по категории"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/faqs?filters[category][$eq]={category}&sort=order_index:asc"
        response = await client.get(url)
        result = []
        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)

            for item in items:
                if 'attributes' in item:
                    attrs = item['attributes']
                else:
                    attrs = item

                result.append({
                    'id': item.get('id'),
                    'question': attrs.get('question'),
                    'answer': attrs.get('answer'),
                    'image_url': attrs.get('image', {}).get('url') if isinstance(attrs.get('image'), dict) else None
                })
        return result


# ---------- Вопросы пользователей (сохранение в Strapi) ----------
async def send_user_question(telegram_id: int, question: str, email: str = None):
    """Сохранить вопрос от пользователя в Strapi"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{STRAPI_URL}/user-questions"
            payload = {
                "data": {
                    "question_text": question,
                    "email": email or "",
                    "state": "new",
                    "telegram_id": str(telegram_id)
                }
            }
            response = await client.post(url, json=payload, headers=HEADERS)
            if response.status_code == 200 or response.status_code == 201:
                print(f"✅ Вопрос сохранён в Strapi: {question[:50]}...")
                await log_stat_event("question_sent", telegram_id, question[:50])
                return True
            else:
                print(f"❌ Ошибка сохранения вопроса: {response.status_code} - {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


# ---------- Статистика (чтение) ----------
async def get_user_questions():
    """Получить все вопросы пользователей из Strapi"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/user-questions?sort=createdAt:desc"
        response = await client.get(url, headers=HEADERS)
        result = []
        if response.status_code == 200:
            data = response.json()
            items = _extract_items(data)
            for item in items:
                if 'attributes' in item:
                    attrs = item['attributes']
                else:
                    attrs = item
                result.append({
                    'id': item.get('id'),
                    'telegram_id': attrs.get('telegram_id'),
                    'question_text': attrs.get('question_text'),
                    'state': attrs.get('state'),
                    'created_at': attrs.get('createdAt')
                })
        return result


async def get_stats():
    """Собрать базовую статистику из Strapi"""
    async with httpx.AsyncClient() as client:
        # Количество пользователей (из кастомной коллекции)
        users_resp = await client.get(f"{STRAPI_URL}/telegram-users", headers=HEADERS)
        users_count = 0
        if users_resp.status_code == 200:
            users_data = users_resp.json()
            users_items = _extract_items(users_data)
            users_count = len(users_items)

        # Количество открытых ячеек
        progress_resp = await client.get(f"{STRAPI_URL}/user-progresses", headers=HEADERS)
        cells_opened = 0
        if progress_resp.status_code == 200:
            progress_data = progress_resp.json()
            progress_items = _extract_items(progress_data)
            cells_opened = len(progress_items)

        return {
            'users_count': users_count,
            'cells_opened': cells_opened,
            'questions_count': 0
        }