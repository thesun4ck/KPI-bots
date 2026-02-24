"""
Главное меню бота — кнопки, которые видит пользователь внизу экрана.
"""

from telegram import ReplyKeyboardMarkup, KeyboardButton


# создаёт главное меню с основными кнопками бота
def get_main_menu():
    keyboard = [
        [KeyboardButton("📊 Внести данные за сегодня")],
        [KeyboardButton("📈 Мой отчёт"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
