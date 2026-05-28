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


# ---------- Пользователи (локально) ----------
async def get_user_by_telegram_id(telegram_id: int):
    """Найти пользователя из локального файла"""
    user_file = f"user_{telegram_id}.json"
    if os.path.exists(user_file):
        try:
            with open(user_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None


async def create_user(telegram_id: int, username: str = None, consent_given: bool = False):
    """Создать локального пользователя"""
    import datetime

    user_data = {
        'id': telegram_id,
        'telegram_id': telegram_id,
        'username': username or "",
        'consent_given': consent_given,
        'registered_at': datetime.datetime.now().isoformat()
    }

    user_file = f"user_{telegram_id}.json"
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump(user_data, f)

    print(f"👤 Создан локальный пользователь: {telegram_id}, consent_given={consent_given}")
    return user_data


async def set_consent(telegram_id: int, consent: bool):
    """Обновить поле consent_given у пользователя"""
    user = await get_user_by_telegram_id(telegram_id)
    if user:
        user['consent_given'] = consent
        user_file = f"user_{telegram_id}.json"
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user, f)
        print(f"📝 Обновлено consent_given для {telegram_id}: {consent}")
        return True
    return False


# ---------- Прогресс пользователя (локально) ----------
async def is_cell_opened(user_id: int, cell_id: int):
    """Проверить, открывал ли пользователь эту ячейку"""
    progress_file = f"user_progress_{user_id}.txt"
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            opened_cells = [int(line.strip()) for line in f if line.strip().isdigit()]
            return cell_id in opened_cells
    return False


async def save_user_progress(user_id: int, cell_id: int):
    """Сохранить факт открытия ячейки в локальный файл"""
    progress_file = f"user_progress_{user_id}.txt"
    with open(progress_file, "a") as f:
        f.write(f"{cell_id}\n")
    print(f"📝 Сохранён прогресс: пользователь {user_id}, ячейка {cell_id}")
    return True


async def get_opened_days(user_id: int):
    """Получить список открытых дней из локального файла"""
    opened_days = set()
    progress_file = f"user_progress_{user_id}.txt"
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            for line in f:
                try:
                    opened_days.add(int(line.strip()))
                except:
                    pass
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
                    "telegram_id": str(telegram_id),
                    "username": username or ""
                }
            }
            response = await client.post(url, json=payload, headers=HEADERS)
            if response.status_code == 201:
                print(f"✅ Событие {event_type} записано в статистику Strapi")
                return True
            else:
                print(f"⚠️ Не удалось записать событие: {response.status_code}")
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

            items = []
            if 'data' in data and isinstance(data['data'], list):
                items = data['data']
            elif isinstance(data, list):
                items = data

            if not items:
                return None

            item = items[0]

            if 'attributes' in item:
                attrs = item['attributes']
            else:
                attrs = item

            image_url = None
            if attrs.get('image'):
                if isinstance(attrs['image'], dict):
                    if 'url' in attrs['image']:
                        image_url = attrs['image']['url']
                    elif 'data' in attrs['image'] and attrs['image']['data']:
                        img_data = attrs['image']['data']
                        if isinstance(img_data, dict):
                            if 'url' in img_data:
                                image_url = img_data['url']
                            elif 'attributes' in img_data and img_data['attributes'].get('url'):
                                image_url = img_data['attributes']['url']

            if image_url and not image_url.startswith('http'):
                base_url = STRAPI_URL.replace('/api', '')
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
    return None


# ---------- FAQ (чтение из Strapi) ----------
async def get_faq_categories():
    """Получить список уникальных категорий FAQ"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/faqs"
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            categories = set()

            items = []
            if 'data' in data and isinstance(data['data'], list):
                items = data['data']
            elif isinstance(data, list):
                items = data

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

            items = []
            if 'data' in data and isinstance(data['data'], list):
                items = data['data']
            elif isinstance(data, list):
                items = data

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
            if response.status_code == 201:
                print(f"✅ Вопрос сохранён в Strapi: {question[:50]}...")
                await log_stat_event("question_sent", telegram_id, question[:50])
                return True
            else:
                print(f"❌ Ошибка сохранения вопроса: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


# ---------- Статистика ----------
async def get_user_questions():
    """Получить все вопросы пользователей из Strapi"""
    async with httpx.AsyncClient() as client:
        url = f"{STRAPI_URL}/user-questions?sort=createdAt:desc"
        response = await client.get(url, headers=HEADERS)
        result = []
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', [])
            for item in items:
                attrs = item.get('attributes', {})
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
        # Получаем все события
        response = await client.get(f"{STRAPI_URL}/stats-events", headers=HEADERS)
        users_count = 0
        cells_opened = 0
        questions_count = 0

        if response.status_code == 200:
            data = response.json()
            items = data.get('data', [])
            for item in items:
                attrs = item.get('attributes', {})
                event_type = attrs.get('event_type')
                if event_type == 'user_registered':
                    users_count += 1
                elif event_type == 'cell_opened':
                    cells_opened += 1
                elif event_type == 'question_sent':
                    questions_count += 1

        return {
            'users_count': users_count,
            'cells_opened': cells_opened,
            'questions_count': questions_count
        }