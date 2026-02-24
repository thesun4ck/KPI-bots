"""
Меню администратора — кнопки для управления ботом.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# создаёт меню администратора с основными разделами управления
def get_admin_menu():
    keyboard = [
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("⚙️ Система", callback_data="admin_system"),
        ],
        [
            InlineKeyboardButton("🔙 Выйти", callback_data="admin_exit"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# создаёт кнопки для раздела "Система" в админке
def get_system_menu():
    keyboard = [
        [InlineKeyboardButton("💾 Бэкап БД", callback_data="admin_backup")],
        [InlineKeyboardButton("📥 Выгрузить в Excel", callback_data="admin_excel")],
        [InlineKeyboardButton("📋 Логи", callback_data="admin_logs")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


# создаёт кнопки пагинации для списка пользователей в админке
def get_users_pagination(current_page: int, total_pages: int):
    buttons = []
    if current_page > 0:
        buttons.append(
            InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{current_page - 1}")
        )
    if current_page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton("➡️ Далее", callback_data=f"page_{current_page + 1}")
        )

    keyboard = []
    if buttons:
        keyboard.append(buttons)
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)
