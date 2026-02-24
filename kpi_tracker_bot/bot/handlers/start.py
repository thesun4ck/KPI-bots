"""
Онбординг нового пользователя — пошаговая регистрация через диалог с ботом.
Бот спрашивает имя, название бизнеса, тип бизнеса и время напоминания.
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters
)
from database.queries import get_user_by_telegram_id, create_user, create_metric
from bot.keyboards.main_menu import get_main_menu
from bot.utils.validators import validate_time
from bot.services.scheduler import add_user_job
from config import DEFAULT_REMINDER_TIME

logger = logging.getLogger(__name__)

# состояния диалога регистрации — по ним бот понимает, на каком шаге находится пользователь
NAME, BUSINESS_NAME, BUSINESS_TYPE, REMINDER_TIME = range(4)

# какие метрики создаются автоматически для каждого типа бизнеса
DEFAULT_METRICS = {
    "retail": [
        ("revenue", "💰 Выручка", "₽"),
        ("checks", "🧾 Количество чеков", "шт"),
        ("avg_check", "💳 Средний чек", "₽"),
    ],
    "cafe": [
        ("revenue", "💰 Выручка", "₽"),
        ("checks", "🧾 Количество чеков", "шт"),
        ("avg_check", "💳 Средний чек", "₽"),
        ("write_offs", "🗑 Списания", "₽"),
    ],
    "online": [
        ("leads", "📩 Заявки", "шт"),
        ("sales", "🛒 Продажи", "шт"),
        ("revenue", "💰 Выручка", "₽"),
        ("conversion", "📊 Конверсия", "%"),
    ],
    "services": [
        ("revenue", "💰 Выручка", "₽"),
        ("bookings", "📋 Записей", "шт"),
        ("attendance", "✅ Явка", "шт"),
        ("avg_check", "💳 Средний чек", "₽"),
    ],
    "other": [
        ("revenue", "💰 Выручка", "₽"),
        ("clients", "👥 Клиентов", "шт"),
    ],
}

# кнопки выбора типа бизнеса при регистрации
BUSINESS_TYPE_BUTTONS = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛒 Розничный магазин"), KeyboardButton("☕ Кафе или ресторан")],
        [KeyboardButton("💻 Онлайн-бизнес"), KeyboardButton("🛠 Услуги")],
        [KeyboardButton("📦 Другое")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# соответствие текста кнопки → внутренний код типа бизнеса
BUSINESS_TYPES_MAP = {
    "🛒 Розничный магазин": "retail",
    "☕ Кафе или ресторан": "cafe",
    "💻 Онлайн-бизнес": "online",
    "🛠 Услуги": "services",
    "📦 Другое": "other",
}


# первый шаг — пользователь нажал /start, бот приветствует и спрашивает имя
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # проверяем, зарегистрирован ли пользователь уже
    user = await get_user_by_telegram_id(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"С возвращением, {user['name']}! 👋",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Привет! Я помогаю предпринимателям отслеживать ключевые метрики "
        "бизнеса прямо в Telegram.\n\n"
        "Никаких Excel-таблиц — просто отвечай на мои вопросы каждый вечер, "
        "а я буду строить аналитику и сигнализировать если что-то пошло не так.\n\n"
        "Для начала — как тебя зовут?",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME


# второй шаг — пользователь написал имя, бот спрашивает название бизнеса
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or len(name) > 100:
        await update.message.reply_text("Пожалуйста, введи своё имя (до 100 символов):")
        return NAME

    # сохраняем имя во временное хранилище диалога
    context.user_data["name"] = name

    await update.message.reply_text(
        f"Отлично, {name}! Как называется твой бизнес?"
    )
    return BUSINESS_NAME


# третий шаг — пользователь написал название бизнеса, бот показывает типы
async def get_business_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    business_name = update.message.text.strip()
    if not business_name or len(business_name) > 200:
        await update.message.reply_text(
            "Пожалуйста, введи название бизнеса (до 200 символов):"
        )
        return BUSINESS_NAME

    context.user_data["business_name"] = business_name

    await update.message.reply_text(
        "Хорошо! Теперь выбери тип бизнеса — это поможет мне предложить "
        "подходящие метрики:",
        reply_markup=BUSINESS_TYPE_BUTTONS
    )
    return BUSINESS_TYPE


# четвёртый шаг — пользователь выбрал тип бизнеса, бот показывает метрики и просит время
async def get_business_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    type_text = update.message.text.strip()

    if type_text not in BUSINESS_TYPES_MAP:
        await update.message.reply_text(
            "Пожалуйста, выбери тип бизнеса из предложенных кнопок:",
            reply_markup=BUSINESS_TYPE_BUTTONS
        )
        return BUSINESS_TYPE

    business_type = BUSINESS_TYPES_MAP[type_text]
    context.user_data["business_type"] = business_type

    # формируем список метрик для показа пользователю
    metrics = DEFAULT_METRICS.get(business_type, DEFAULT_METRICS["other"])
    metrics_text = "\n".join([f"  • {label} ({unit})" for _, label, unit in metrics])

    await update.message.reply_text(
        f'Отлично! Я настроил базовые метрики для "{context.user_data["business_name"]}":\n'
        f"{metrics_text}\n\n"
        f"Можешь добавить свои или изменить их в настройках в любой момент.\n\n"
        f"В котором часу тебе присылать напоминание внести данные за день?\n"
        f"Напиши в формате ЧЧ:ММ, например: 21:00",
        reply_markup=ReplyKeyboardRemove()
    )
    return REMINDER_TIME


# пятый шаг — пользователь указал время, бот завершает регистрацию
async def get_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip()
    validated_time = validate_time(time_text)

    if not validated_time:
        await update.message.reply_text(
            "Неправильный формат времени. Напиши в формате ЧЧ:ММ, например: 21:00"
        )
        return REMINDER_TIME

    try:
        # создаём пользователя в базе данных
        user_id = await create_user(
            telegram_id=update.effective_user.id,
            name=context.user_data["name"],
            business_name=context.user_data["business_name"],
            business_type=context.user_data["business_type"],
            reminder_time=validated_time,
        )

        # создаём метрики по умолчанию для выбранного типа бизнеса
        business_type = context.user_data["business_type"]
        metrics = DEFAULT_METRICS.get(business_type, DEFAULT_METRICS["other"])
        # проходим по каждой метрике и сохраняем её в базе
        for metric_name, metric_label, unit in metrics:
            await create_metric(user_id, metric_name, metric_label, unit)

        # создаём задачу напоминания для этого пользователя
        add_user_job(
            context.application,
            user_id,
            update.effective_user.id,
            validated_time
        )

        await update.message.reply_text(
            f"✅ Всё готово, {context.user_data['name']}!\n\n"
            f"Каждый день в {validated_time} я буду напоминать тебе внести данные.\n"
            f"Раз в неделю ты будешь получать сводный отчёт с графиками.\n\n"
            f"Удачи в бизнесе 🚀",
            reply_markup=get_main_menu()
        )

    except Exception as e:
        logger.error(f"Ошибка при регистрации: {e}")
        await update.message.reply_text(
            "Произошла ошибка при регистрации. Попробуй ещё раз: /start"
        )

    # очищаем временные данные диалога
    context.user_data.clear()
    return ConversationHandler.END


# если пользователь написал /cancel — отменяем регистрацию
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Регистрация отменена. Чтобы начать заново — нажми /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# собираем все шаги в один ConversationHandler для регистрации
def get_start_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BUSINESS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_business_name)],
            BUSINESS_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_business_type)],
            REMINDER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_reminder_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="onboarding",
        persistent=False,
    )
