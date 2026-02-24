"""
Аналитика бизнес-метрик — подсчёт статистики, сравнение периодов, прогнозы.
Использует pandas для работы с данными.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from database.queries import get_records_for_period, get_metric_records, get_user_metrics


# считает статистику по всем метрикам пользователя за указанный период
# возвращает сумму, среднее, минимум и максимум для каждой метрики
async def get_period_stats(user_id: int, days: int):
    records = await get_records_for_period(user_id, days)

    if not records:
        return {}

    # превращаем список записей в таблицу для удобной обработки
    df = pd.DataFrame(records)

    result = {}
    # считаем статистику отдельно для каждой метрики
    for metric_name in df["metric_name"].unique():
        metric_data = df[df["metric_name"] == metric_name]
        result[metric_name] = {
            "label": metric_data["metric_label"].iloc[0],
            "unit": metric_data["unit"].iloc[0],
            "sum": float(metric_data["value"].sum()),
            "avg": float(metric_data["value"].mean()),
            "min": float(metric_data["value"].min()),
            "max": float(metric_data["value"].max()),
            "count": len(metric_data),
        }

    return result


# сравнивает текущий период с предыдущим таким же периодом
# например: последние 7 дней vs предыдущие 7 дней
# возвращает процент изменения
async def compare_periods(user_id: int, metric_id: int, days: int):
    # получаем данные за двойной период
    records = await get_metric_records(user_id, metric_id, days * 2)

    if not records:
        return None

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])

    today = pd.Timestamp(date.today())
    period_start = today - pd.Timedelta(days=days)
    prev_start = period_start - pd.Timedelta(days=days)

    # разделяем данные на текущий и предыдущий периоды
    current = df[(df["date"] > period_start) & (df["date"] <= today)]
    previous = df[(df["date"] > prev_start) & (df["date"] <= period_start)]

    current_sum = float(current["value"].sum()) if len(current) > 0 else 0
    previous_sum = float(previous["value"].sum()) if len(previous) > 0 else 0

    # считаем процент изменения
    if previous_sum == 0:
        if current_sum == 0:
            percent_change = 0
        else:
            percent_change = 100.0
    else:
        percent_change = ((current_sum - previous_sum) / previous_sum) * 100

    return {
        "current_sum": current_sum,
        "previous_sum": previous_sum,
        "percent_change": round(percent_change, 1),
    }


# находит лучший и худший дни за указанный период для конкретной метрики
async def get_best_worst_days(user_id: int, metric_id: int, days: int):
    records = await get_metric_records(user_id, metric_id, days)

    if not records:
        return None

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])

    # находим строку с максимальным и минимальным значением
    best_idx = df["value"].idxmax()
    worst_idx = df["value"].idxmin()

    return {
        "best_date": df.loc[best_idx, "date"].strftime("%Y-%m-%d"),
        "best_value": float(df.loc[best_idx, "value"]),
        "worst_date": df.loc[worst_idx, "date"].strftime("%Y-%m-%d"),
        "worst_value": float(df.loc[worst_idx, "value"]),
    }


# прогнозирует значение метрики на конец текущего месяца
# считает по среднедневному темпу за имеющиеся дни месяца
async def forecast_month_end(user_id: int, metric_id: int):
    today = date.today()
    # начало текущего месяца
    month_start_days = today.day - 1

    if month_start_days == 0:
        return None

    records = await get_metric_records(user_id, metric_id, month_start_days)

    if not records:
        return None

    df = pd.DataFrame(records)
    total_so_far = float(df["value"].sum())
    daily_avg = total_so_far / month_start_days

    # сколько всего дней в текущем месяце
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    days_in_month = (next_month - date(today.year, today.month, 1)).days

    # прогноз = среднее за день × количество дней в месяце
    forecast = daily_avg * days_in_month

    return {
        "days_passed": month_start_days,
        "days_in_month": days_in_month,
        "total_so_far": total_so_far,
        "daily_avg": round(daily_avg, 2),
        "forecast": round(forecast, 2),
    }


# проверяет все метрики пользователя на резкие отклонения от среднего
# если значение сегодня сильно отличается от среднего за 14 дней — возвращает предупреждение
async def check_alerts(user_id: int):
    metrics = await get_user_metrics(user_id)
    alerts = []

    # проверяем каждую метрику по очереди
    for metric in metrics:
        records = await get_metric_records(user_id, metric["id"], 14)

        if len(records) < 3:
            # слишком мало данных для анализа
            continue

        df = pd.DataFrame(records)
        today_str = date.today().isoformat()

        # ищем запись за сегодня
        today_records = df[df["date"] == today_str]
        if today_records.empty:
            continue

        today_value = float(today_records["value"].iloc[0])

        # среднее за предыдущие дни (без сегодняшнего)
        previous = df[df["date"] != today_str]
        if previous.empty:
            continue

        avg_value = float(previous["value"].mean())

        if avg_value == 0:
            continue

        # считаем процент отклонения от среднего
        deviation = ((today_value - avg_value) / avg_value) * 100
        threshold = metric.get("alert_threshold", 30.0)

        # если отклонение больше порога — добавляем предупреждение
        if abs(deviation) >= threshold:
            direction = "ниже" if deviation < 0 else "выше"
            alerts.append({
                "metric_id": metric["id"],
                "metric_label": metric["metric_label"],
                "unit": metric["unit"],
                "today_value": today_value,
                "avg_value": round(avg_value, 2),
                "deviation": round(abs(deviation), 1),
                "direction": direction,
            })

    return alerts
