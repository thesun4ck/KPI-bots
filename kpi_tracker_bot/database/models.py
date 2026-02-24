"""
Описание всех таблиц базы данных. 
Каждая таблица описана как SQL-команда на создание.
"""

# таблица пользователей — хранит информацию о каждом зарегистрированном человеке
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    name TEXT,
    business_name TEXT,
    business_type TEXT,
    timezone TEXT DEFAULT 'Europe/Moscow',
    reminder_time TEXT DEFAULT '21:00',
    is_active INTEGER DEFAULT 1,
    is_blocked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# таблица метрик — какие показатели отслеживает каждый пользователь
# например: выручка, количество чеков, средний чек
CREATE_METRICS_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS metrics_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    metric_name TEXT,
    metric_label TEXT,
    unit TEXT,
    alert_threshold REAL DEFAULT 30.0,
    is_active INTEGER DEFAULT 1
)
"""

# таблица ежедневных записей — сюда попадают все цифры, которые вводит пользователь
CREATE_DAILY_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    metric_id INTEGER REFERENCES metrics_config(id),
    value REAL,
    date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# таблица целей — пользователь может поставить цель по метрике на неделю или месяц
CREATE_GOALS_TABLE = """
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    metric_id INTEGER REFERENCES metrics_config(id),
    target_value REAL,
    period TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# таблица логов предупреждений — чтобы не отправлять одно и то же предупреждение дважды
CREATE_ALERTS_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    metric_id INTEGER REFERENCES metrics_config(id),
    alert_type TEXT,
    message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# список всех команд создания таблиц — чтобы запускать их по очереди
ALL_TABLES = [
    CREATE_USERS_TABLE,
    CREATE_METRICS_CONFIG_TABLE,
    CREATE_DAILY_RECORDS_TABLE,
    CREATE_GOALS_TABLE,
    CREATE_ALERTS_LOG_TABLE,
]
