"""
Главная точка входа бота — здесь всё собирается вместе:
создаётся приложение, подключаются все обработчики команд, запускается бот.
"""

import logging
import sys
import os

# добавляем корневую папку проекта в пути импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from config import BOT_TOKEN
from database.db import init_db
from bot.handlers.start import get_start_handler
from bot.handlers.daily_input import get_daily_input_handler, dismiss_report
from bot.handlers.reports import (
    show_report_menu, report_week, report_month, report_csv,
    show_alert_chart, show_report_after_input,
    report_back, report_back_to_menu
)
from bot.handlers.settings import (
    show_settings, show_metrics, view_metric,
    handle_deactivate_metric, show_goals, select_goal_period,
    settings_back, settings_back_main,
    get_business_name_handler, get_add_metric_handler,
    get_edit_metric_handler, get_goals_handler, get_reminder_handler
)
from bot.handlers.admin import (
    admin_command, admin_users, admin_users_page,
    admin_stats, admin_system, admin_backup,
    admin_excel_export, admin_logs, admin_back, admin_exit
)
from bot.keyboards.main_menu import get_main_menu
from bot.services.scheduler import setup_all_jobs, start_scheduler, stop_scheduler
from database.queries import get_user_by_telegram_id

# настраиваем журнал событий — все сообщения бота записываются сюда
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# обработчик кнопки "Помощь" — показывает инструкцию пользователю
async def help_command(update: Update, context):
    user = await get_user_by_telegram_id(update.effective_user.id)
    reminder_time = user.get("reminder_time", "21:00") if user else "21:00"

    await update.message.reply_text(
        "❓ Как пользоваться ботом:\n\n"
        "📊 Внести данные — каждый вечер вноси цифры за день\n"
        "📈 Мой отчёт — смотри статистику за неделю или месяц\n"
        "⚙️ Настройки — управляй метриками, целями и временем напоминания\n\n"
        f"Также я сам напомню тебе каждый день в {reminder_time} "
        f"и пришлю еженедельный отчёт по воскресеньям.\n\n"
        "Если что-то пошло не так — напиши @your_support_username",
        reply_markup=get_main_menu()
    )


# эта функция вызывается при запуске бота — создаёт таблицы и запускает планировщик
async def post_init(application):
    # создаём таблицы в базе данных, если их ещё нет
    await init_db()
    logger.info("База данных инициализирована")

    # запускаем планировщик напоминаний
    start_scheduler()

    # загружаем расписание напоминаний для всех пользователей
    await setup_all_jobs(application)
    logger.info("Планировщик задач запущен")


# эта функция вызывается при остановке бота — останавливает планировщик
async def post_shutdown(application):
    stop_scheduler()
    logger.info("Бот остановлен")


# главная функция — собирает всё вместе и запускает бота
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан! Создай файл .env с токеном бота.")
        sys.exit(1)

    # создаём приложение бота
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # --- Регистрируем обработчики команд ---

    # диалог регистрации (онбординг)
    application.add_handler(get_start_handler())

    # диалог ежедневного ввода данных
    application.add_handler(get_daily_input_handler())

    # диалоги настроек (каждый — отдельный ConversationHandler)
    application.add_handler(get_business_name_handler())
    application.add_handler(get_add_metric_handler())
    application.add_handler(get_edit_metric_handler())
    application.add_handler(get_goals_handler())
    application.add_handler(get_reminder_handler())

    # кнопка "Мой отчёт" — показывает меню отчётов
    application.add_handler(
        MessageHandler(filters.Regex("^📈 Мой отчёт$"), show_report_menu)
    )

    # кнопка "Настройки" — показывает меню настроек
    application.add_handler(
        MessageHandler(filters.Regex("^⚙️ Настройки$"), show_settings)
    )

    # кнопка "Помощь" — показывает инструкцию
    application.add_handler(
        MessageHandler(filters.Regex("^❓ Помощь$"), help_command)
    )

    # команда /admin — открывает панель администратора
    application.add_handler(CommandHandler("admin", admin_command))

    # --- Обработчики кнопок (CallbackQuery) ---

    # кнопки отчётов
    application.add_handler(CallbackQueryHandler(report_week, pattern="^report_week$"))
    application.add_handler(CallbackQueryHandler(report_month, pattern="^report_month$"))
    application.add_handler(CallbackQueryHandler(report_csv, pattern="^report_csv$"))
    application.add_handler(CallbackQueryHandler(report_back, pattern="^report_back$"))
    application.add_handler(CallbackQueryHandler(report_back_to_menu, pattern="^report_back_to_menu$"))
    application.add_handler(CallbackQueryHandler(show_report_after_input, pattern="^show_report_week$"))
    application.add_handler(CallbackQueryHandler(dismiss_report, pattern="^dismiss_report$"))
    application.add_handler(CallbackQueryHandler(show_alert_chart, pattern=r"^alert_chart_\d+$"))

    # кнопки настроек
    application.add_handler(CallbackQueryHandler(show_metrics, pattern="^settings_metrics$"))
    application.add_handler(CallbackQueryHandler(view_metric, pattern=r"^metric_view_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_deactivate_metric, pattern=r"^metric_deactivate_\d+$"))
    application.add_handler(CallbackQueryHandler(show_goals, pattern="^settings_goals$"))
    application.add_handler(CallbackQueryHandler(select_goal_period, pattern=r"^goal_set_\d+$"))
    application.add_handler(CallbackQueryHandler(settings_back, pattern="^settings_back$"))
    application.add_handler(CallbackQueryHandler(settings_back_main, pattern="^settings_back_main$"))

    # кнопки админки
    application.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    application.add_handler(CallbackQueryHandler(admin_users_page, pattern=r"^page_\d+$"))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_system, pattern="^admin_system$"))
    application.add_handler(CallbackQueryHandler(admin_backup, pattern="^admin_backup$"))
    application.add_handler(CallbackQueryHandler(admin_excel_export, pattern="^admin_excel$"))
    application.add_handler(CallbackQueryHandler(admin_logs, pattern="^admin_logs$"))
    application.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    application.add_handler(CallbackQueryHandler(admin_exit, pattern="^admin_exit$"))

    # запускаем бота — он будет ждать сообщений от пользователей
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# если файл запущен напрямую — запускаем бота
if __name__ == "__main__":
    main()
