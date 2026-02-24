"""
Система предупреждений — проверяет метрики пользователей и отправляет уведомления
если значения сильно отклоняются от обычных.
"""

import logging
from datetime import date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.queries import get_all_users, get_user_metrics, alert_sent_today, log_alert
from bot.services.analytics import check_alerts

logger = logging.getLogger(__name__)


# проверяет метрики всех активных пользователей и отправляет предупреждения
# вызывается планировщиком после ввода данных
async def check_and_send_alerts(app):
    try:
        users = await get_all_users()

        # проходим по каждому пользователю
        for user in users:
            if not user.get("is_active") or user.get("is_blocked"):
                continue

            try:
                # проверяем все метрики пользователя на отклонения
                alerts = await check_alerts(user["id"])

                # отправляем предупреждение по каждому отклонению
                for alert in alerts:
                    alert_type = f"deviation_{alert['direction']}"

                    # проверяем, не отправляли ли уже такое предупреждение сегодня
                    already_sent = await alert_sent_today(
                        user["id"], alert["metric_id"], alert_type
                    )
                    if already_sent:
                        continue

                    # формируем текст предупреждения
                    text = (
                        f"⚠️ {alert['metric_label']} сегодня "
                        f"на {alert['deviation']}% {alert['direction']} "
                        f"твоего среднего за 2 недели.\n\n"
                        f"Среднее: {alert['avg_value']} {alert['unit']}\n"
                        f"Сегодня: {alert['today_value']} {alert['unit']}\n\n"
                        f"Это разовый провал или начало тренда?"
                    )

                    # кнопка для просмотра динамики
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "📈 Посмотреть динамику",
                            callback_data=f"alert_chart_{alert['metric_id']}"
                        )]
                    ])

                    # отправляем предупреждение пользователю
                    await app.bot.send_message(
                        chat_id=user["telegram_id"],
                        text=text,
                        reply_markup=keyboard
                    )

                    # записываем в лог, чтобы не отправлять повторно
                    await log_alert(
                        user["id"], alert["metric_id"],
                        alert_type, text
                    )

            except Exception as e:
                logger.error(f"Ошибка проверки алертов для пользователя {user['id']}: {e}")

    except Exception as e:
        logger.error(f"Ошибка в check_and_send_alerts: {e}")
