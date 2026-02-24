"""
Меню настроек — кнопки для управления параметрами пользователя.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# создаёт главное меню настроек пользователя
def get_settings_menu():
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить название бизнеса", callback_data="settings_business_name")],
        [InlineKeyboardButton("📊 Мои метрики", callback_data="settings_metrics")],
        [InlineKeyboardButton("🎯 Установить цели", callback_data="settings_goals")],
        [InlineKeyboardButton("🕐 Время напоминания", callback_data="settings_reminder")],
        [InlineKeyboardButton("🔙 Назад", callback_data="settings_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


# создаёт меню управления метриками: список метрик и кнопки для действий
def get_metrics_menu(metrics: list):
    keyboard = []
    # показываем каждую метрику как кнопку
    for m in metrics:
        keyboard.append([
            InlineKeyboardButton(
                f"{m['metric_label']} ({m['unit']})",
                callback_data=f"metric_view_{m['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("➕ Добавить метрику", callback_data="metric_add")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="settings_back_main")])
    return InlineKeyboardMarkup(keyboard)


# создаёт кнопки действий для конкретной метрики
def get_metric_actions(metric_id: int):
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"metric_edit_{metric_id}")],
        [InlineKeyboardButton("🚫 Отключить", callback_data=f"metric_deactivate_{metric_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="settings_metrics")],
    ]
    return InlineKeyboardMarkup(keyboard)


# создаёт меню для выбора метрик при установке целей
def get_goals_metrics_menu(metrics: list):
    keyboard = []
    # показываем каждую метрику для установки цели
    for m in metrics:
        keyboard.append([
            InlineKeyboardButton(
                f"🎯 {m['metric_label']}",
                callback_data=f"goal_set_{m['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="settings_back_main")])
    return InlineKeyboardMarkup(keyboard)


# создаёт кнопки выбора периода для цели (неделя или месяц)
def get_goal_period_menu(metric_id: int):
    keyboard = [
        [
            InlineKeyboardButton("📅 Неделя", callback_data=f"goal_period_week_{metric_id}"),
            InlineKeyboardButton("📆 Месяц", callback_data=f"goal_period_month_{metric_id}"),
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="settings_goals")],
    ]
    return InlineKeyboardMarkup(keyboard)
