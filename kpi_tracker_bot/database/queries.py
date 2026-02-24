"""
Все запросы к базе данных собраны здесь.
Каждая функция делает одну конкретную операцию с данными.
"""

from datetime import datetime, date, timedelta
from database.db import get_db


# ==================== ПОЛЬЗОВАТЕЛИ ====================

# находит пользователя по его Telegram ID (уникальный номер в Telegram)
async def get_user_by_telegram_id(telegram_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        await db.close()


# создаёт нового пользователя в базе данных при регистрации
async def create_user(telegram_id: int, name: str, business_name: str,
                      business_type: str, timezone: str = "Europe/Moscow",
                      reminder_time: str = "21:00"):
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO users (telegram_id, name, business_name, business_type, 
               timezone, reminder_time) VALUES (?, ?, ?, ?, ?, ?)""",
            (telegram_id, name, business_name, business_type, timezone, reminder_time)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


# обновляет название бизнеса у пользователя
async def update_business_name(user_id: int, business_name: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET business_name = ? WHERE id = ?",
            (business_name, user_id)
        )
        await db.commit()
    finally:
        await db.close()


# обновляет время ежедневного напоминания у пользователя
async def update_reminder_time(user_id: int, reminder_time: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET reminder_time = ? WHERE id = ?",
            (reminder_time, user_id)
        )
        await db.commit()
    finally:
        await db.close()


# ==================== МЕТРИКИ ====================

# получает список всех активных метрик пользователя (выручка, чеки и т.д.)
async def get_user_metrics(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM metrics_config WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# получает одну конкретную метрику по её номеру
async def get_metric_by_id(metric_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM metrics_config WHERE id = ?", (metric_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        await db.close()


# добавляет новую метрику для отслеживания пользователем
async def create_metric(user_id: int, metric_name: str, metric_label: str,
                        unit: str, alert_threshold: float = 30.0):
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO metrics_config (user_id, metric_name, metric_label, unit, 
               alert_threshold) VALUES (?, ?, ?, ?, ?)""",
            (user_id, metric_name, metric_label, unit, alert_threshold)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


# отключает метрику — она больше не будет запрашиваться у пользователя
async def deactivate_metric(metric_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE metrics_config SET is_active = 0 WHERE id = ?", (metric_id,)
        )
        await db.commit()
    finally:
        await db.close()


# обновляет название и единицу измерения метрики
async def update_metric(metric_id: int, metric_label: str, unit: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE metrics_config SET metric_label = ?, unit = ? WHERE id = ?",
            (metric_label, unit, metric_id)
        )
        await db.commit()
    finally:
        await db.close()


# ==================== ЕЖЕДНЕВНЫЕ ЗАПИСИ ====================

# сохраняет значение метрики за конкретный день
async def save_daily_record(user_id: int, metric_id: int, value: float,
                            record_date: str = None):
    if record_date is None:
        record_date = date.today().isoformat()
    db = await get_db()
    try:
        # проверяем, есть ли уже запись за этот день для этой метрики
        cursor = await db.execute(
            """SELECT id FROM daily_records 
               WHERE user_id = ? AND metric_id = ? AND date = ?""",
            (user_id, metric_id, record_date)
        )
        existing = await cursor.fetchone()

        if existing:
            # если запись уже есть — обновляем значение
            await db.execute(
                "UPDATE daily_records SET value = ? WHERE id = ?",
                (value, existing["id"])
            )
        else:
            # если записи нет — создаём новую
            await db.execute(
                """INSERT INTO daily_records (user_id, metric_id, value, date) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, metric_id, value, record_date)
            )
        await db.commit()
    finally:
        await db.close()


# получает все записи пользователя за указанное количество дней
async def get_records_for_period(user_id: int, days: int):
    start_date = (date.today() - timedelta(days=days)).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT dr.*, mc.metric_name, mc.metric_label, mc.unit
               FROM daily_records dr
               JOIN metrics_config mc ON dr.metric_id = mc.id
               WHERE dr.user_id = ? AND dr.date >= ?
               ORDER BY dr.date ASC""",
            (user_id, start_date)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# получает записи для конкретной метрики за указанное количество дней
async def get_metric_records(user_id: int, metric_id: int, days: int):
    start_date = (date.today() - timedelta(days=days)).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM daily_records 
               WHERE user_id = ? AND metric_id = ? AND date >= ?
               ORDER BY date ASC""",
            (user_id, metric_id, start_date)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# проверяет, вносил ли пользователь данные сегодня
async def has_today_records(user_id: int):
    today = date.today().isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM daily_records WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        row = await cursor.fetchone()
        return row["cnt"] > 0
    finally:
        await db.close()


# получает все записи пользователя за конкретную дату
async def get_records_by_date(user_id: int, record_date: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT dr.*, mc.metric_label, mc.unit
               FROM daily_records dr
               JOIN metrics_config mc ON dr.metric_id = mc.id
               WHERE dr.user_id = ? AND dr.date = ?""",
            (user_id, record_date)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ==================== ЦЕЛИ ====================

# устанавливает цель по метрике на период (неделя или месяц)
async def set_goal(user_id: int, metric_id: int, target_value: float, period: str):
    db = await get_db()
    try:
        # удаляем старую цель на этот же период, если была
        await db.execute(
            """DELETE FROM goals 
               WHERE user_id = ? AND metric_id = ? AND period = ?""",
            (user_id, metric_id, period)
        )
        # создаём новую цель
        await db.execute(
            """INSERT INTO goals (user_id, metric_id, target_value, period) 
               VALUES (?, ?, ?, ?)""",
            (user_id, metric_id, target_value, period)
        )
        await db.commit()
    finally:
        await db.close()


# получает все цели пользователя
async def get_user_goals(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT g.*, mc.metric_label, mc.unit
               FROM goals g
               JOIN metrics_config mc ON g.metric_id = mc.id
               WHERE g.user_id = ?""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ==================== ПРЕДУПРЕЖДЕНИЯ (АЛЕРТЫ) ====================

# записывает в лог отправленное предупреждение, чтобы не дублировать
async def log_alert(user_id: int, metric_id: int, alert_type: str, message: str = ""):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO alerts_log (user_id, metric_id, alert_type, message) 
               VALUES (?, ?, ?, ?)""",
            (user_id, metric_id, alert_type, message)
        )
        await db.commit()
    finally:
        await db.close()


# проверяет, отправлялось ли уже такое предупреждение сегодня
async def alert_sent_today(user_id: int, metric_id: int, alert_type: str):
    today = date.today().isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT COUNT(*) as cnt FROM alerts_log 
               WHERE user_id = ? AND metric_id = ? AND alert_type = ? 
               AND DATE(sent_at) = ?""",
            (user_id, metric_id, alert_type, today)
        )
        row = await cursor.fetchone()
        return row["cnt"] > 0
    finally:
        await db.close()


# ==================== АДМИНКА ====================

# получает список всех зарегистрированных пользователей
async def get_all_users():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# получает общую статистику бота: сколько пользователей, активных, новых
async def get_users_stats():
    db = await get_db()
    try:
        # общее количество пользователей
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
        total = (await cursor.fetchone())["cnt"]

        # пользователи, которые вводили данные за последние 7 дней
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        cursor = await db.execute(
            """SELECT COUNT(DISTINCT user_id) as cnt FROM daily_records 
               WHERE date >= ?""",
            (week_ago,)
        )
        active = (await cursor.fetchone())["cnt"]

        # новые пользователи за последние 7 дней
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE DATE(created_at) >= ?",
            (week_ago,)
        )
        new_users = (await cursor.fetchone())["cnt"]

        # записей за сегодня
        today = date.today().isoformat()
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM daily_records WHERE date = ?",
            (today,)
        )
        records_today = (await cursor.fetchone())["cnt"]

        # записей за неделю
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM daily_records WHERE date >= ?",
            (week_ago,)
        )
        records_week = (await cursor.fetchone())["cnt"]

        # всего записей за всё время
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM daily_records"
        )
        records_total = (await cursor.fetchone())["cnt"]

        return {
            "total": total,
            "active": active,
            "new_users": new_users,
            "records_today": records_today,
            "records_week": records_week,
            "records_total": records_total,
        }
    finally:
        await db.close()


# получает данные о росте количества пользователей по дням (для графика в админке)
async def get_users_growth():
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT DATE(created_at) as reg_date, COUNT(*) as cnt 
               FROM users GROUP BY DATE(created_at) ORDER BY reg_date ASC"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# получает последние записи из лога предупреждений (для админки)
async def get_system_logs(limit: int = 20):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT al.*, u.name, u.telegram_id, mc.metric_label
               FROM alerts_log al
               LEFT JOIN users u ON al.user_id = u.id
               LEFT JOIN metrics_config mc ON al.metric_id = mc.id
               ORDER BY al.sent_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# блокирует пользователя — бот перестанет с ним взаимодействовать
async def block_user(user_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET is_blocked = 1 WHERE id = ?", (user_id,)
        )
        await db.commit()
    finally:
        await db.close()


# удаляет все данные пользователя из базы (метрики, записи, цели, алерты, профиль)
async def delete_user_data(user_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM daily_records WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM goals WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM alerts_log WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM metrics_config WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
    finally:
        await db.close()


# получает все данные из всех таблиц для экспорта в Excel
async def get_all_data_for_export():
    db = await get_db()
    try:
        result = {}

        # собираем данные из каждой таблицы по очереди
        for table_name in ["users", "metrics_config", "daily_records", "goals", "alerts_log"]:
            cursor = await db.execute(f"SELECT * FROM {table_name}")
            columns = [description[0] for description in cursor.description]
            rows = await cursor.fetchall()
            result[table_name] = {
                "columns": columns,
                "rows": [list(row) for row in rows]
            }

        return result
    finally:
        await db.close()


# считает дату последней активности пользователя (последний ввод данных)
async def get_user_last_activity(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT MAX(date) as last_date FROM daily_records 
               WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row and row["last_date"]:
            return row["last_date"]
        return None
    finally:
        await db.close()
