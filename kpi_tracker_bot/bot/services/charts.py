"""
Построение графиков для отчётов и админки.
Все графики строятся в памяти и возвращаются как BytesIO для отправки в Telegram.
Стиль: тёмный фон, голубой основной цвет, оранжевый акцентный.
"""

import matplotlib
matplotlib.use('Agg')  # используем режим без окна, чтобы работало на серверах без монитора
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import seaborn as sns
from io import BytesIO
from datetime import datetime


# основной цвет для графиков — голубой
PRIMARY_COLOR = "#4FC3F7"
# акцентный цвет (для сравнения) — оранжевый
ACCENT_COLOR = "#FF7043"
# цвет подписей осей — серый
LABEL_COLOR = "#AAAAAA"
# цвет сетки — тёмно-серый
GRID_COLOR = "#555555"


# подготавливает стандартный стиль для всех графиков
def _setup_style():
    plt.style.use('dark_background')
    sns.set_theme(style="darkgrid", rc={
        "axes.facecolor": "#1a1a2e",
        "figure.facecolor": "#1a1a2e",
        "grid.color": GRID_COLOR,
        "grid.alpha": 0.2,
    })


# убирает рамку вокруг графика, оставляя только сетку
def _clean_spines(ax):
    # проходим по каждой стороне рамки и убираем её
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', alpha=0.2, color=GRID_COLOR)


# строит линейный график изменения метрики по дням
# используется в отчётах за неделю и месяц
async def revenue_line_chart(dates: list, values: list, title: str) -> BytesIO:
    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    # преобразуем строки дат в объекты datetime
    if dates and isinstance(dates[0], str):
        dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]

    # рисуем линию с точками на каждом значении
    ax.plot(dates, values, color=PRIMARY_COLOR, linewidth=2.5, marker='o', markersize=5)
    # заливка под линией для красоты
    ax.fill_between(dates, values, alpha=0.15, color=PRIMARY_COLOR)

    ax.set_title(title, fontsize=16, pad=15, color='white')
    ax.set_xlabel('Дата', color=LABEL_COLOR)
    ax.set_ylabel('Значение', color=LABEL_COLOR)

    # форматируем числа на оси Y с пробелами между разрядами: 1000000 → 1 000 000
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', ' '))
    )

    # поворачиваем даты на оси X под углом, чтобы не наезжали друг на друга
    plt.xticks(rotation=45, ha='right', color=LABEL_COLOR)
    plt.yticks(color=LABEL_COLOR)

    _clean_spines(ax)
    plt.tight_layout()

    # сохраняем график в память (не в файл на диске)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


# строит столбчатую диаграмму по дням недели
# показывает, в какие дни бизнес работает лучше
async def weekly_bar_chart(days: list, values: list, title: str) -> BytesIO:
    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    # рисуем столбцы с закруглёнными краями
    bars = ax.bar(days, values, color=PRIMARY_COLOR, width=0.6,
                  edgecolor='none', alpha=0.85)

    # подписываем значения над каждым столбцом
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                f'{int(val):,}'.replace(',', ' '),
                ha='center', va='bottom', color='white', fontsize=10)

    ax.set_title(title, fontsize=16, pad=15, color='white')
    ax.set_xlabel('День недели', color=LABEL_COLOR)
    ax.set_ylabel('Значение', color=LABEL_COLOR)

    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', ' '))
    )

    plt.xticks(color=LABEL_COLOR)
    plt.yticks(color=LABEL_COLOR)

    _clean_spines(ax)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


# строит график сравнения двух периодов — два набора столбцов рядом
# используется для сравнения "эта неделя" vs "прошлая неделя"
async def comparison_chart(values1: list, values2: list, labels: list, title: str) -> BytesIO:
    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    import numpy as np
    x = np.arange(len(labels))
    width = 0.35

    # первый набор столбцов — текущий период (голубой)
    bars1 = ax.bar(x - width / 2, values1, width, label='Текущий период',
                   color=PRIMARY_COLOR, alpha=0.85)
    # второй набор столбцов — предыдущий период (оранжевый)
    bars2 = ax.bar(x + width / 2, values2, width, label='Предыдущий период',
                   color=ACCENT_COLOR, alpha=0.85)

    ax.set_title(title, fontsize=16, pad=15, color='white')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=LABEL_COLOR)
    ax.legend(facecolor='#2a2a3e', edgecolor='#555555', labelcolor='white')

    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', ' '))
    )

    plt.yticks(color=LABEL_COLOR)

    _clean_spines(ax)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf


# строит график роста числа пользователей по дням — для админки
async def admin_users_growth_chart(dates: list, counts: list) -> BytesIO:
    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    if dates and isinstance(dates[0], str):
        dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]

    # считаем накопительную сумму — показываем общее количество пользователей
    cumulative = []
    total = 0
    # проходим по каждому дню и суммируем количество новых пользователей
    for c in counts:
        total += c
        cumulative.append(total)

    ax.plot(dates, cumulative, color=PRIMARY_COLOR, linewidth=2.5, marker='o', markersize=5)
    ax.fill_between(dates, cumulative, alpha=0.15, color=PRIMARY_COLOR)

    ax.set_title('📈 Рост пользователей', fontsize=16, pad=15, color='white')
    ax.set_xlabel('Дата', color=LABEL_COLOR)
    ax.set_ylabel('Всего пользователей', color=LABEL_COLOR)

    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', ' '))
    )

    plt.xticks(rotation=45, ha='right', color=LABEL_COLOR)
    plt.yticks(color=LABEL_COLOR)

    _clean_spines(ax)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf
