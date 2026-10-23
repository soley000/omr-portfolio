"""Periodes nommees : les conventions de dates de ChargeDesk, codees une seule fois.

Toutes sont relatives au soir courant E (inclus) :
- last_7_days       : E-6 a E              - previous_7_days  : E-13 a E-7
- last_28_days      : E-27 a E             - previous_28_days : E-55 a E-28
- month_to_date     : 1er du mois a E      - previous_month   : mois precedent complet
- year_to_date      : 1er janvier a E      - previous_year    : annee precedente complete
- custom            : start et end donnes explicitement
years_back decale la periode de n annees (ex. memes dates l'an dernier).
Aucune date apres le soir courant ni avant le 1er janvier 2020.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

PeriodName = Literal["last_7_days", "previous_7_days", "last_28_days", "previous_28_days",
                     "month_to_date", "previous_month", "year_to_date", "previous_year", "custom"]
DATA_START = date(2020, 1, 1)


class PeriodError(ValueError):
    pass


def _shift_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year - n)
    except ValueError:            # 29 fevrier
        return d.replace(year=d.year - n, day=28)


def resolve_period(evening: date, period: PeriodName, start: date | None = None,
                   end: date | None = None, years_back: int = 0) -> tuple[date, date]:
    e = evening
    if period == "last_7_days":
        a, b = e - timedelta(6), e
    elif period == "previous_7_days":
        a, b = e - timedelta(13), e - timedelta(7)
    elif period == "last_28_days":
        a, b = e - timedelta(27), e
    elif period == "previous_28_days":
        a, b = e - timedelta(55), e - timedelta(28)
    elif period == "month_to_date":
        a, b = e.replace(day=1), e
    elif period == "previous_month":
        b = e.replace(day=1) - timedelta(1)
        a = b.replace(day=1)
    elif period == "year_to_date":
        a, b = e.replace(month=1, day=1), e
    elif period == "previous_year":
        a, b = date(e.year - 1, 1, 1), date(e.year - 1, 12, 31)
    elif period == "custom":
        if start is None or end is None:
            raise PeriodError("period=custom demande start et end (AAAA-MM-JJ)")
        a, b = start, end
    else:
        raise PeriodError(f"periode inconnue : {period}")
    if years_back:
        a, b = _shift_years(a, years_back), _shift_years(b, years_back)
    if a > b:
        raise PeriodError(f"la periode commence ({a}) apres sa fin ({b})")
    if b > e:
        raise PeriodError(f"la periode finit le {b}, apres le soir courant {e} : le futur n'est pas connu")
    if a < DATA_START:
        raise PeriodError(f"les donnees commencent le {DATA_START}")
    return a, b
