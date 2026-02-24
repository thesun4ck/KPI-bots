"""
Настройки пользователя — название бизнеса, управление метриками,
цели и расписание напоминаний.
"""

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)
from database.queries import (
    get_user_by_telegram_id, update_business_name,
    get_user_metrics, update_reminder_time, deactivate_metric,
    create_metric, get_metric_by_id, update_metric, set_goal
)
from bot.keyboards.settings_menu import (
    get_settings_menu, get_metrics_menu, get_metric_actions,
    get_goals_metrics_menu, get_goal_period_menu
)
from bot.services.scheduler import add_user_job
from bot.utils.validators import validate_time, validate_number


# Главное меню настроек
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
        await message.edit_text("⚙️ Настройки:", reply_markup=get_settings_menu())
    else:
        await update.message.reply_text("⚙️ Настройки:", reply_markup=get_settings_menu())

# Возврат на предыдущие меню в настройках
async def settings_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # просто удаляем предыдущее сообщение (если нельзя вернуться кнопкой)
    await update.callback_query.message.delete()

async def settings_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_settings(update, context)


# ==================== НАЗВАНИЕ БИЗНЕСА ====================
EDIT_BIZ_NAME = 1

async def edit_business_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "Введи новое название твоего бизнеса:\n\n(напиши /cancel для отмены)"
    )
    return EDIT_BIZ_NAME

async def edit_business_name_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    user = await get_user_by_telegram_id(update.effective_user.id)

    await update_business_name(user["id"], new_name)
    await update.message.reply_text(f"✅ Название изменено на «{new_name}»")
    return ConversationHandler.END


# ==================== УПРАВЛЕНИЕ МЕТРИКАМИ ====================
ADD_METRIC_NAME, ADD_METRIC_UNIT = 1, 2
EDIT_METRIC_NAME, EDIT_METRIC_UNIT = 1, 2

# Показывает список всех активных метрик
async def show_metrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user_by_telegram_id(update.effective_user.id)
    metrics = await get_user_metrics(user["id"])

    await update.callback_query.message.edit_text(
        "📊 Твои метрики. Нажми на метрику для редактирования:",
        reply_markup=get_metrics_menu(metrics)
    )

# Показывает действия для одной выбранной метрики (Редактировать / Отключить)
async def view_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    metric_id = int(update.callback_query.data.split("_")[2])
    metric = await get_metric_by_id(metric_id)

    if not metric:
        return

    text = f"Метрика: {metric['metric_label']}\nЕдиница: {metric['unit']}"
    await update.callback_query.message.edit_text(
        text, reply_markup=get_metric_actions(metric_id)
    )

# Отключает метрику (она больше не запрашивается)
async def handle_deactivate_metric(update: Update, context: ContextTypes.DEFAULT_TYPE):
    metric_id = int(update.callback_query.data.split("_")[2])
    await deactivate_metric(metric_id)
    await update.callback_query.answer("Метрика отключена!")
    await show_metrics(update, context)

# --- ДОБАВЛЕНИЕ МЕТРИКИ ---
async def add_metric_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введи название новой метрики (например: Списания):")
    return ADD_METRIC_NAME

async def add_metric_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_metric_name"] = update.message.text.strip()
    await update.message.reply_text("В чём она измеряется? (например: ₽, шт, %):")
    return ADD_METRIC_UNIT

async def add_metric_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    unit = update.message.text.strip()
    label = context.user_data["new_metric_name"]
    user = await get_user_by_telegram_id(update.effective_user.id)

    # системное имя метрики делаем английским по-простому
    sys_name = "custom_" + str(len(label))

    await create_metric(user["id"], sys_name, label, unit)
    await update.message.reply_text(f"✅ Добавлена метрика «{label}» ({unit})")
    context.user_data.clear()
    return ConversationHandler.END

# --- РЕДАКТИРОВАНИЕ МЕТРИКИ ---
async def edit_metric_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    metric_id = int(update.callback_query.data.split("_")[2])
    context.user_data["edit_metric_id"] = metric_id
    await update.callback_query.message.reply_text("Введи новое название метрики:")
    return EDIT_METRIC_NAME

async def edit_metric_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_metric_name"] = update.message.text.strip()
    await update.message.reply_text("В чём она измеряется? (например: ₽, шт):")
    return EDIT_METRIC_UNIT

async def edit_metric_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    unit = update.message.text.strip()
    label = context.user_data["edit_metric_name"]
    metric_id = context.user_data["edit_metric_id"]

    await update_metric(metric_id, label, unit)
    await update.message.reply_text(f"✅ Метрика обновлена: «{label}» ({unit})")
    context.user_data.clear()
    return ConversationHandler.END


# ==================== УСТАНОВКА ЦЕЛЕЙ ====================
GOAL_VALUE = 1

async def show_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user_by_telegram_id(update.effective_user.id)
    metrics = await get_user_metrics(user["id"])
    await update.callback_query.message.edit_text(
        "Выбери метрику, для которой хочешь установить цель:",
        reply_markup=get_goals_metrics_menu(metrics)
    )

async def select_goal_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    metric_id = int(update.callback_query.data.split("_")[2])
    await update.callback_query.message.edit_text(
        "На какой период ставим цель?",
        reply_markup=get_goal_period_menu(metric_id)
    )

async def enter_goal_value_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # data выглядит как "goal_period_week_15"
    parts = update.callback_query.data.split("_")
    period = parts[2]
    metric_id = int(parts[3])

    context.user_data["goal_period"] = period
    context.user_data["goal_metric_id"] = metric_id

    metric = await get_metric_by_id(metric_id)
    period_str = "неделю" if period == "week" else "месяц"

    await update.callback_query.message.reply_text(
        f"Введи целевое значение для «{metric['metric_label']}» на {period_str}:\n\n(только число)"
    )
    return GOAL_VALUE

async def enter_goal_value_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = validate_number(update.message.text)
    if val is None:
        await update.message.reply_text("Нужно ввести число. Попробуй ещё раз:")
        return GOAL_VALUE

    user = await get_user_by_telegram_id(update.effective_user.id)
    metric_id = context.user_data["goal_metric_id"]
    period = context.user_data["goal_period"]

    await set_goal(user["id"], metric_id, val, period)
    period_str = "неделю" if period == "week" else "месяц"
    await update.message.reply_text(f"🎯 Отлично! Цель на {period_str} сохранена.")
    context.user_data.clear()
    return ConversationHandler.END


# ==================== ВРЕМЯ НАПОМИНАНИЯ ====================
EDIT_REMINDER = 1

async def edit_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user_by_telegram_id(update.effective_user.id)
    current = user.get("reminder_time", "21:00")
    await update.callback_query.message.reply_text(
        f"Текущее время: {current}\n\nВведи новое время (ЧЧ:ММ):"
    )
    return EDIT_REMINDER

async def edit_reminder_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip()
    validated_time = validate_time(time_text)

    if not validated_time:
        await update.message.reply_text("Неверный формат. Нужно ЧЧ:ММ, например 20:30.")
        return EDIT_REMINDER

    user = await get_user_by_telegram_id(update.effective_user.id)
    await update_reminder_time(user["id"], validated_time)

    # обновляем задачу в планировщике, чтобы напоминание приходило в новое время
    add_user_job(context.application, user["id"], update.effective_user.id, validated_time)

    await update.message.reply_text(f"✅ Время обновлено! Буду напоминать в {validated_time}.")
    return ConversationHandler.END


# универсальная отмена любого диалога настроек
async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# --- СБОРЩИКИ CONVERSATION HANDLERS ---

def get_business_name_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_business_name_start, pattern="^settings_business_name$")],
        states={EDIT_BIZ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_business_name_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_settings)]
    )

def get_add_metric_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_metric_start, pattern="^metric_add$")],
        states={
            ADD_METRIC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_metric_name)],
            ADD_METRIC_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_metric_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel_settings)]
    )

def get_edit_metric_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_metric_start, pattern=r"^metric_edit_\d+$")],
        states={
            EDIT_METRIC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_metric_name)],
            EDIT_METRIC_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_metric_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel_settings)]
    )

def get_goals_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(enter_goal_value_start, pattern=r"^goal_period_(week|month)_\d+$")],
        states={GOAL_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_goal_value_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_settings)]
    )

def get_reminder_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_reminder_start, pattern="^settings_reminder$")],
        states={EDIT_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_reminder_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_settings)]
    )
