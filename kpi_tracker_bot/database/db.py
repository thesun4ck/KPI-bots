"""
Подключение к базе данных и её начальная настройка.
"""

import aiosqlite
from config import DATABASE_PATH
from database.models import ALL_TABLES


# эта функция создаёт все нужные таблицы в базе данных при первом запуске бота
async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # проходим по списку всех таблиц и создаём каждую, если её ещё нет
        for table_sql in ALL_TABLES:
            await db.execute(table_sql)
        await db.commit()


# эта функция возвращает подключение к базе данных для выполнения запросов
async def get_db():
    db = await aiosqlite.connect(DATABASE_PATH)
    # включаем режим, при котором результаты запросов можно получать по именам колонок
    db.row_factory = aiosqlite.Row
    return db
