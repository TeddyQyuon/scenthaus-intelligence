from datetime import date, timedelta
import numpy as np

HOLIDAYS = {
    2024: [date(2024, 2, 10), date(2024, 4, 10), date(2024, 10, 31)],
    2025: [date(2025, 1, 29), date(2025, 3, 31), date(2025, 10, 20)],
    2026: [date(2026, 2, 17), date(2026, 3, 21), date(2026, 11, 8)],
}


def features(day):
    day = day.date() if hasattr(day, "date") else day
    if day.year not in HOLIDAYS:
        raise ValueError(
            f"Verify Singapore holiday dates for {day.year} before forecasting"
        )
    mothers = date(day.year, 5, 1)
    mothers += timedelta(days=(6 - mothers.weekday()) % 7 + 7)
    holidays = [float(-6 <= (h - day).days <= 14) for h in HOLIDAYS[day.year]]
    promo = float(any(0 <= (date(day.year, m, m) - day).days <= 6 for m in [9, 11, 12]))
    week = day.isocalendar().week
    return [
        np.sin(2 * np.pi * week / 52),
        np.cos(2 * np.pi * week / 52),
        *holidays,
        float(-6 <= (mothers - day).days <= 14),
        promo,
        float(day.month == 12),
        (day - date(2024, 9, 30)).days / 728,
    ]
