"""
Ежедневный ввод данных — бот спрашивает у пользователя значения всех активных метрик за сегодня.
Каждая метрика запрашивается по очереди.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)
from database.queries import (
    get_user_by_telegram_id, get_user_metrics, save_daily_record,
    has_today_records, get_records_by_date
)
from bot.utils.validators import validate_number, validate_positive
from bot.services.analytics import compare_periods, check_alerts
from bot.utils.formatters import format_percent, format_value
from datetime import date

# состояния для ConversationHandler: INPUT_METRIC — процесс ввода значений
INPUT_METRIC = 1


# первый шаг — пользователь нажал кнопку "Внести данные" или ответил на напоминание
async def start_daily_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # определяем, откуда пришёл запрос: сообщение или нажатие на inline-кнопку
    if update.callback_query:
        await update.callback_query.answer()
        user_id_tg = update.callback_query.from_user.id
        message = update.callback_query.message
    else:
        user_id_tg = update.message.from_user.id
        message = update.message

    # ищем пользователя в базе
    user = await get_user_by_telegram_id(user_id_tg)
    if not user:
        await message.reply_text("Сначала нужно зарегистрироваться: /start")
        return ConversationHandler.END

    # проверяем, не вводил ли он уже сегодня данные
    has_records = await has_today_records(user["id"])
    if has_records and not context.user_data.get("force_update"):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Обновить", callback_data="force_update_daily")],
            [InlineKeyboardButton("Нет", callback_data="cancel_daily")]
        ])
        await message.reply_text(
            "Ты уже вносил данные сегодня.\n\nХочешь обновить?",
            reply_markup=keyboard
        )
        return ConversationHandler.END

    # получаем все активные метрики пользователя
    metrics = await get_user_metrics(user["id"])
    if not metrics:
        await message.reply_text("У тебя нет активных метрик. Настрой их в меню ⚙️ Настройки.")
        return ConversationHandler.END

    # сохраняем метрики во временное хранилище, чтобы спрашивать по одной
    context.user_data["user_id"] = user["id"]
    context.user_data["metrics_to_ask"] = metrics
    context.user_data["current_metric_index"] = 0
    context.user_data["results"] = []

    # задаём первый вопрос (про первую метрику в списке)
    first_metric = metrics[0]
    await message.reply_text(
        f"💰 {first_metric['metric_label']}? ({first_metric['unit']})",
        reply_markup=ReplyKeyboardRemove()
    )

    return INPUT_METRIC


# второй шаг — пользователь отправил число
async def handle_metric_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # проверяем, что введено правильное число
    value = validate_number(text)

    if value is None or not validate_positive(value):
        await update.message.reply_text("Пожалуйста, введи положительное число.")
        return INPUT_METRIC

    # берём текущую метрику из хранилища
    metrics = context.user_data["metrics_to_ask"]
    idx = context.user_data["current_metric_index"]
    current_metric = metrics[idx]

    # сохраняем введённое значение
    context.user_data["results"].append({
        "metric_id": current_metric["id"],
        "value": value,
        "label": current_metric["metric_label"],
        "unit": current_metric["unit"]
    })

    # переходим к следующей метрике
    idx += 1
    context.user_data["current_metric_index"] = idx

    # если остались ещё вопросы — задаём следующий
    if idx < len(metrics):
        next_metric = metrics[idx]
        await update.message.reply_text(
            f"💰 {next_metric['metric_label']}? ({next_metric['unit']})"
        )
        return INPUT_METRIC

    # если метрики закончились — сохраняем всё в базу данных
    user_id = context.user_data["user_id"]
    results = context.user_data["results"]

    summary_lines = []

    for res in results:
        # сохраняем значение в таблицу daily_records
        await save_daily_record(user_id, res["metric_id"], res["value"])

        # сравниваем с прошлой неделей (за 7 дней)
        comparison = await compare_periods(user_id, res["metric_id"], 7)
        if comparison and comparison["previous_sum"] > 0:
            percent = format_percent(comparison["percent_change"])
        else:
            percent = "нет данных"

        val_str = format_value(res["value"], res["unit"])
        summary_lines.append(f"{res['label']}: {val_str} ({percent} к прошлой неделе)")

    summary_text = "\n".join(summary_lines)

    # предлагаем сразу посмотреть отчёт за неделю
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Посмотреть", callback_data="show_report_week")],
        [InlineKeyboardButton("Не сейчас", callback_data="dismiss_report")]
    ])

    await update.message.reply_text(
        f"✅ Готово, всё записал!\n\n{summary_text}\n\nХочешь посмотреть подробный отчёт?",
        reply_markup=keyboard
    )

    # после ввода данных проверяем, не нужно ли отправить предупреждение об отклонении
    try:
        from bot.services.alerts import check_and_send_alerts
        # запускаем проверку алертов без ожидания ответа
        import asyncio
        asyncio.create_task(check_and_send_alerts(context.application))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Ошибка вызова алертов: {e}")

    # очищаем временные данные
    context.user_data.clear()
    return ConversationHandler.END


# если пользователь нажал "Обновить" — запускаем ввод заново
async def handle_force_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["force_update"] = True
    return await start_daily_input(update, context)


# если пользователь нажал "Нет" при вопросе об обновлении
async def handle_cancel_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("Понял, оставляем всё как есть.")
    return ConversationHandler.END


# если пользователь ввёл команду отмены в процессе
async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Ввод данных отменён.")
    return ConversationHandler.END


# если пользователь нажал "Не сейчас" в конце ввода
async def dismiss_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        update.callback_query.message.text + "\n\nОтчёт можно посмотреть в меню «📈 Мой отчёт»."
    )


# собираем все шаги в один ConversationHandler для ежедневного ввода
def get_daily_input_handler():
    # регулярное выражение для перехвата кнопки "Внести данные"
    btn_regex = "^📊 Внести данные за сегодня$"

    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(btn_regex), start_daily_input),
            CallbackQueryHandler(start_daily_input, pattern="^start_daily_input$"),
            CallbackQueryHandler(handle_force_update, pattern="^force_update_daily$"),
        ],
        states={
            INPUT_METRIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_metric_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_input),
            CallbackQueryHandler(handle_cancel_daily, pattern="^cancel_daily$")
        ],
        name="daily_input",
        persistent=False,
    )
