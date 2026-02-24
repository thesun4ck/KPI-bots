"""
Панель администратора.
Доступна только тем пользователям, чей Telegram ID указан в config.ADMIN_IDS.
Здесь можно смотреть список пользователей, статистику бота, скачивать бэкапы БД.
"""

import os
import io
import shutil
from datetime import date
import pandas as pd
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS, DATABASE_PATH
from bot.keyboards.admin_menu import get_admin_menu, get_system_menu, get_users_pagination
from database.queries import (
    get_all_users, get_users_stats, get_users_growth,
    get_system_logs, get_all_data_for_export
)
from bot.services.charts import admin_users_growth_chart


# декоратор (надстройка) для проверки прав администратора
# если айди пользователя нет в ADMIN_IDS — функция прерывается и бот молчит
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            return  # игнорируем обычных пользователей
        return await func(update, context, *args, **kwargs)
    return wrapper


# команда /admin — открывает главное меню админки
@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍💻 Панель управления KPI Tracker",
        reply_markup=get_admin_menu()
    )


# показывает список всех пользователей (первая страница)
@admin_only
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_users_page(update, context, page=0)


# показывает конкретную страницу пользователей
@admin_only
async def admin_users_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = int(update.callback_query.data.split("_")[1])
    await _show_users_page(update, context, page)


# вспомогательная функция для отображения пользователей (пагинация по 10 штук)
async def _show_users_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    query = update.callback_query
    await query.answer()

    # получаем всех пользователей
    users = await get_all_users()
    total_users = len(users)
    per_page = 10
    total_pages = (total_users + per_page - 1) // per_page

    if total_users == 0:
        await query.message.edit_text("Пользователей пока нет.", reply_markup=get_admin_menu())
        return

    # отбираем 10 пользователей для нужной страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]

    text = f"👥 Пользователи (стр. {page + 1}/{total_pages}):\n\n"
    # формируем текст про каждого пользователя
    for u in page_users:
        status = "🔴 Блок" if u.get("is_blocked") else "✅ Активен"
        text += f"ID: {u['telegram_id']} | {u['name']} [{u['business_name']}]\n"
        text += f"Тип: {u['business_type']} | {status}\n---\n"

    await query.message.edit_text(
        text,
        reply_markup=get_users_pagination(page, total_pages)
    )


# показывает общую текстовую статистику и график роста пользователей
@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Сбор статистики...")

    # получаем цифры: сколько всего, сколько активных
    stats = await get_users_stats()

    text = (
        f"📊 Статистика KPI Tracker:\n\n"
        f"Всего пользователей: {stats['total']}\n"
        f"Новых за 7 дней: {stats['new_users']}\n"
        f"Активных за 7 дней: {stats['active']}\n\n"
        f"Записей сегодня: {stats['records_today']}\n"
        f"Записей за 7 дней: {stats['records_week']}\n"
        f"Всего записей в базе: {stats['records_total']}"
    )

    # строим графит роста "пользователи по дням"
    growth_data = await get_users_growth()
    if growth_data:
        dates = [r["reg_date"] for r in growth_data]
        counts = [r["cnt"] for r in growth_data]
        chart_buf = await admin_users_growth_chart(dates, counts)

        # отправляем картинку с текстом поверх
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart_buf,
            caption=text
        )
    else:
        await query.message.reply_text(text)


# открывает системное меню (бэкапы, логи)
@admin_only
async def admin_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        "⚙️ Управление системой:",
        reply_markup=get_system_menu()
    )


# создаёт и отправляет файл бэкапа базы данных (.sqlite)
@admin_only
async def admin_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Создаю бэкап...")

    # проверяем что файл базы данных существует
    if not os.path.exists(DATABASE_PATH):
        await query.message.reply_text("Файл базы данных не найден!")
        return

    # копируем файл во временный, чтобы не заблокировать БД во время отправки
    backup_path = DATABASE_PATH + ".backup"
    shutil.copy2(DATABASE_PATH, backup_path)

    try:
        with open(backup_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=f"kpi_backup_{date.today().isoformat()}.sqlite"
            )
    finally:
        # удаляем временный бэкап с диска после отправки
        if os.path.exists(backup_path):
            os.remove(backup_path)


# экспортирует все таблицы из базы данных в один Excel файл (.xlsx) на разные листы
@admin_only
async def admin_excel_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Выгружаю в Excel...")

    # получаем данные всех таблиц
    all_data = await get_all_data_for_export()
    output = io.BytesIO()

    # используем pandas и openpyxl для создания экселя прямо в оперативной памяти
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for table_name, data in all_data.items():
            df = pd.DataFrame(data["rows"], columns=data["columns"])
            # каждый лист называется так же, как таблица в БД
            df.to_excel(writer, sheet_name=table_name, index=False)

    output.seek(0)
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=output,
        filename=f"kpi_full_export_{date.today().isoformat()}.xlsx"
    )


# показывает последние перехваченные ошибки и отправленные предупреждения
@admin_only
async def admin_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    logs = await get_system_logs(20)

    if not logs:
        await query.message.reply_text("Логов пока нет.")
        return

    text = "📋 Последние 20 логов алертов:\n\n"
    for log in logs:
        user_info = log.get("name", "Unknown") if log.get("name") else str(log.get("user_id"))
        metric_info = log.get("metric_label", "Unknown")
        text += f"[{log['sent_at']}]\nЮзер: {user_info}\nМетрика: {metric_info}\nТип: {log['alert_type']}\n---\n"

    # Telegram режет длинные сообщения, берём только первые 4000 символов
    if len(text) > 4000:
        text = text[:4000] + "\n...обрезано"

    await query.message.reply_text(text)


# возврат в главное меню админки
@admin_only
async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "👨‍💻 Панель управления KPI Tracker",
        reply_markup=get_admin_menu()
    )


# выход из панели администратора (удаляем сообщение с кнопками)
@admin_only
async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
