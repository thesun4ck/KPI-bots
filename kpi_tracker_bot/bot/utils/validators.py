"""
Проверка данных, которые вводит пользователь.
Убеждаемся что пришло число, что время в правильном формате и т.д.
"""

import re


# проверяет, что пользователь ввёл число, и возвращает его как дробное число
# если текст — не число, возвращает None
def validate_number(text: str):
    try:
        # убираем пробелы и заменяем запятую на точку (для русской раскладки)
        cleaned = text.strip().replace(",", ".").replace(" ", "")
        value = float(cleaned)
        return value
    except (ValueError, AttributeError):
        return None


# проверяет, что время написано в формате ЧЧ:ММ (например, 21:00)
# возвращает строку времени или None если формат неправильный
def validate_time(text: str):
    text = text.strip()
    # проверяем формат: две цифры, двоеточие, две цифры
    pattern = r'^([01]?\d|2[0-3]):([0-5]\d)$'
    match = re.match(pattern, text)
    if match:
        # нормализуем формат — добавляем ведущий ноль если нужно
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return f"{hours:02d}:{minutes:02d}"
    return None


# проверяет, что число не отрицательное (ноль допускается)
def validate_positive(value: float):
    return value is not None and value >= 0
