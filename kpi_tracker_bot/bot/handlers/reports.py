"""
Построение и отправка отчётов с графиками.
Отчёты за неделю, месяц, выгрузка в CSV и показ алертов.
"""

import os
import csv
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.queries import get_user_by_telegram_id, get_user_metrics, get_records_for_period, get_metric_records
from bot.services.analytics import get_period_stats, compare_periods, get_best_worst_days
from bot.services.charts import revenue_line_chart, comparison_chart
from bot.utils.formatters import format_percent, format_value


# показывает стартовое меню отчётов по нажатию "Мой отчёт"
async def show_report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 За неделю", callback_data="report_week")],
        [InlineKeyboardButton("📆 За месяц", callback_data="report_month")],
        [InlineKeyboardButton("📥 Выгрузить в CSV", callback_data="report_csv")],
        [InlineKeyboardButton("🔙 Назад", callback_data="report_back")],
    ])
    await update.message.reply_text("Какой отчёт подготовить?", reply_markup=keyboard)


# возврат из меню отчётов — просто удаляем сообщение
async def report_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.delete()


# генерирует отчёт за последние 7 дней с графиками
async def report_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Собираю данные за 7 дней...")

    user = await get_user_by_telegram_id(query.from_user.id)
    if not user:
        return

    # получаем статистику за неделю
    stats = await get_period_stats(user["id"], 7)

    if not stats:
        await query.message.reply_text("Нет данных за последние 7 дней.")
        return

    text_lines = [f"📊 Итоги недели, {user['name']}!\n"]
    # первая метрика будет нарисована на графике
    first_metric_id = None
    first_metric_name = None

    # проходим по каждой метрике и добавляем строчку в отчёт
    metrics = await get_user_metrics(user["id"])
    for m in metrics:
        if first_metric_id is None:
            first_metric_id = m['id']
            first_metric_name = m['metric_label']

        m_name = m["metric_name"]
        if m_name in stats:
            s = stats[m_name]
            val_str = format_value(s["sum"], s["unit"])

            # сравниваем с предыдущей неделей
            comp = await compare_periods(user["id"], m["id"], 7)
            if comp and comp["previous_sum"] > 0:
                pct = format_percent(comp["percent_change"])
                status = "✅" if comp["percent_change"] >= 0 else "⚠️"
                text_lines.append(f"• {s['label']}: {val_str} ({pct} к прошлой неделе) {status}")
            else:
                text_lines.append(f"• {s['label']}: {val_str}")

            # находим лучший и худший день для главной метрики
            if m["id"] == first_metric_id:
                bw = await get_best_worst_days(user["id"], m["id"], 7)
                if bw:
                    best_val = format_value(bw["best_value"], s["unit"])
                    worst_val = format_value(bw["worst_value"], s["unit"])
                    text_lines.append(f"\n🏆 Лучший день — {bw['best_date']} ({best_val})")
                    text_lines.append(f"📉 Слабый день — {bw['worst_date']} ({worst_val})")

    report_text = "\n".join(text_lines)

    # если нашли хоть одну метрику — строим график динамики
    chart_buf = None
    if first_metric_id:
        records = await get_metric_records(user["id"], first_metric_id, 7)
        if len(records) > 0:
            dates = [r["date"] for r in records]
            values = [r["value"] for r in records]
            chart_buf = await revenue_line_chart(dates, values, f"Динамика: {first_metric_name}")

    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 К отчётам", callback_data="report_back_to_menu")]
    ])

    # отправляем сообщение: если есть график — отправляем фотку + текст
    if chart_buf:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart_buf,
            caption=report_text,
            reply_markup=back_keyboard
        )
    else:
        await query.message.reply_text(report_text, reply_markup=back_keyboard)


# отправляет отчёт (коллбэк от кнопки после ввода данных)
async def show_report_after_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # удаляем клавиатуру с вопросом "Хочешь посмотреть отчёт?"
    await update.callback_query.message.edit_reply_markup(reply_markup=None)
    # запускаем генерацию отчёта за неделю
    await report_week(update, context)


# генерирует отчёт за последние 30 дней аналогично недельному
async def report_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Собираю данные за месяц...")

    user = await get_user_by_telegram_id(query.from_user.id)
    stats = await get_period_stats(user["id"], 30)

    if not stats:
        await query.message.reply_text("Нет данных за последний месяц.")
        return

    text_lines = [f"📊 Итоги месяца (30 дней)!\n"]
    first_metric_id = None
    first_metric_name = None

    metrics = await get_user_metrics(user["id"])
    for m in metrics:
        if first_metric_id is None:
            first_metric_id = m['id']
            first_metric_name = m['metric_label']

        m_name = m["metric_name"]
        if m_name in stats:
            s = stats[m_name]
            val_str = format_value(s["sum"], s["unit"])

            comp = await compare_periods(user["id"], m["id"], 30)
            if comp and comp["previous_sum"] > 0:
                pct = format_percent(comp["percent_change"])
                status = "✅" if comp["percent_change"] >= 0 else "⚠️"
                text_lines.append(f"• {s['label']}: {val_str} ({pct} к прошлому месяцу) {status}")
            else:
                text_lines.append(f"• {s['label']}: {val_str}")

    report_text = "\n".join(text_lines)

    chart_buf = None
    if first_metric_id:
        records = await get_metric_records(user["id"], first_metric_id, 30)
        if len(records) > 0:
            dates = [r["date"] for r in records]
            values = [r["value"] for r in records]
            chart_buf = await revenue_line_chart(dates, values, f"Месяц: {first_metric_name}")

    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 К отчётам", callback_data="report_back_to_menu")]
    ])

    if chart_buf:
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=chart_buf, caption=report_text, reply_markup=back_keyboard)
    else:
        await query.message.reply_text(report_text, reply_markup=back_keyboard)


# экспортирует все записи пользователя в CSV файл
async def report_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Готовлю файл...")

    user = await get_user_by_telegram_id(query.from_user.id)
    records = await get_records_for_period(user["id"], 365) # берём за последний год

    if not records:
        await query.message.reply_text("У вас пока нет данных для выгрузки.")
        return

    # создаём временный CSV файл
    filename = f"kpi_export_{user['telegram_id']}_{date.today().isoformat()}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Дата', 'Метрика', 'Значение', 'Единица'])
        for r in records:
            writer.writerow([r['date'], r['metric_label'], r['value'], r['unit']])

    # отправляем файл пользователю
    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 К отчётам", callback_data="report_back_to_menu")]
    ])
    with open(filename, 'rb') as f:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=f,
            filename=f"kpi_data_{date.today().isoformat()}.csv",
            reply_markup=back_keyboard
        )

    # удаляем временный файл с диска
    os.remove(filename)


# возврат к меню отчётов
async def report_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 За неделю", callback_data="report_week")],
        [InlineKeyboardButton("📆 За месяц", callback_data="report_month")],
        [InlineKeyboardButton("📥 Выгрузить в CSV", callback_data="report_csv")],
        [InlineKeyboardButton("🔙 Назад", callback_data="report_back")],
    ])
    await update.callback_query.message.reply_text("Какой отчёт подготовить?", reply_markup=keyboard)


# строит график сравнения для алерта, когда пользователь нажимает "Посмотреть динамику"
async def show_alert_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Рисую график...")

    user = await get_user_by_telegram_id(query.from_user.id)
    # достаём ID метрики из данных кнопки: alert_chart_15
    metric_id = int(query.data.split("_")[2])

    metrics = await get_user_metrics(user["id"])
    metric_name = "Метрика"
    for m in metrics:
        if m["id"] == metric_id:
            metric_name = m["metric_label"]
            break

    # достаём данные за 14 дней
    records = await get_metric_records(user["id"], metric_id, 14)

    if not records:
        await query.message.reply_text("Не удалось загрузить данные для графика.")
        return

    dates = [r["date"] for r in records]
    values = [r["value"] for r in records]

    # строим линейный график
    chart_buf = await revenue_line_chart(dates, values, f"Динамика за 14 дней: {metric_name}")

    if chart_buf:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart_buf,
            caption="Вот как выглядят данные за последние 2 недели. Спад видно на графике."
        )
