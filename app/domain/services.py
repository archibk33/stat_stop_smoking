from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(slots=True)
class MetricsResult:
    days: int
    saved_money: float


def calculate_metrics(quit_date: Optional[date], pack_price: Optional[float]) -> MetricsResult:
    if quit_date is None:
        return MetricsResult(days=0, saved_money=0.0)
    today = date.today()
    days = max((today - quit_date).days, 0)
    if pack_price is None:
        return MetricsResult(days=days, saved_money=0.0)
    # Упрощенно: 1 пачка в день
    saved_money = float(days) * float(pack_price)
    return MetricsResult(days=days, saved_money=saved_money)


def generate_admin_title(days: int) -> str:
    # 0–16 символов, без эмодзи. Короткий формат.
    if days <= 0:
        return "0д"
    text = f"{days}д"
    return text[:16]


def rank_text(days: int) -> str:
    months = days / 30
    if months < 6:
        return "🥉 Бронза"
    if months < 12:
        return "🥈 Серебро"
    if months < 24:
        return "🥇 Золото"
    return "💎 Платина"
