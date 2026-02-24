    """
Форматирование данных для красивого отображения в сообщениях бота.
Превращает числа и даты в удобный для чтения вид.
"""

from datetime import datetime, date


# форматирует денежную сумму с пробелами между разрядами
# 1000000 → "1 000 000 ₽"
def format_money(value: float) -> str:
    if value is None:
        return "0 ₽"
    # если число целое — убираем дробную часть
    if value == int(value):
        formatted = f"{int(value):,}".replace(",", " ")
    else:
        formatted = f"{value:,.2f}".replace(",", " ")
    return f"{formatted} ₽"


# форматирует процент изменения — со знаком плюс или минус
# 8.5 → "+8.5%", -3.2 → "-3.2%"
def format_percent(value: float, with_sign: bool = True) -> str:
    if value is None:
        return "0%"
    if with_sign:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.1f}%"
    return f"{value:.1f}%"


# форматирует дату в красивый русский вид
# "2024-01-15" → "15 января 2024"
def format_date(d) -> str:
    # названия месяцев на русском в родительном падеже
    months = {
        1: "января", 2: "февраля", 3: "марта",
        4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября",
        10: "октября", 11: "ноября", 12: "декабря"
    }

    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()

    if isinstance(d, datetime):
        d = d.date()

    return f"{d.day} {months[d.month]} {d.year}"


# форматирует значение метрики с единицей измерения
# для денег — с пробелами, для остальных — просто число + единица
def format_value(value: float, unit: str) -> str:
    if value is None:
        return f"0 {unit}"
    if unit == "₽":
        return format_money(value)
    if value == int(value):
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


# возвращает название дня недели на русском по его номеру (0 = понедельник)
def weekday_name(weekday_num: int) -> str:
    days = ["Понедельник", "Вторник", "Среда", "Четверг",
            "Пятница", "Суббота", "Воскресенье"]
    return days[weekday_num] if 0 <= weekday_num <= 6 else "Неизвестно"
