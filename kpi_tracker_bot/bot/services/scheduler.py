"""
Планировщик задач — отправляет ежедневные напоминания пользователям в нужное время.
Использует APScheduler для планирования задач.
"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.queries import get_all_users, get_user_by_telegram_id

logger = logging.getLogger(__name__)

# глобальный объект планировщика — один на всё приложение
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


# отправляет одному пользователю напоминание о вводе данных за день
async def send_reminder(app, telegram_id: int):
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user or not user.get("is_active") or user.get("is_blocked"):
            return

        name = user.get("name", "")

        text = (
            f"📋 Привет, {name}! Время внести данные за сегодня.\n\n"
            f"Это займёт меньше минуты. Поехали 👇"
        )

        # кнопка для быстрого начала ввода данных
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📊 Внести данные",
                callback_data="start_daily_input"
            )]
        ])

        await app.bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания для {telegram_id}: {e}")


# добавляет задачу напоминания для конкретного пользователя на его время
def add_user_job(app, user_id: int, telegram_id: int, reminder_time: str):
    job_id = f"reminder_{user_id}"

    # если задача для этого пользователя уже есть — удаляем старую
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    # разбиваем время на часы и минуты
    try:
        hour, minute = reminder_time.split(":")
    except ValueError:
        hour, minute = "21", "00"

    # создаём задачу, которая срабатывает каждый день в указанное время
    scheduler.add_job(
        send_reminder,
        CronTrigger(hour=int(hour), minute=int(minute)),
        id=job_id,
        args=[app, telegram_id],
        replace_existing=True,
    )
    logger.info(f"Добавлено напоминание для пользователя {user_id} на {reminder_time}")


# удаляет задачу напоминания для пользователя (если он отключился или удалён)
def remove_user_job(user_id: int):
    job_id = f"reminder_{user_id}"
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)
        logger.info(f"Удалено напоминание для пользователя {user_id}")


# загружает всех активных пользователей и создаёт для каждого задачу напоминания
async def setup_all_jobs(app):
    users = await get_all_users()

    # проходим по каждому зарегистрированному пользователю
    for user in users:
        if user.get("is_active") and not user.get("is_blocked"):
            add_user_job(
                app,
                user["id"],
                user["telegram_id"],
                user.get("reminder_time", "21:00")
            )

    logger.info(f"Загружено {len(users)} задач напоминания")


# запускает планировщик — вызывается при старте бота
def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик запущен")


# останавливает планировщик — вызывается при выключении бота
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Планировщик остановлен")
