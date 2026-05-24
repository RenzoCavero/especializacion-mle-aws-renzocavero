from __future__ import annotations


CURRENCY_TO_PEN = {
    "PEN": 1.0,
    "USD": 3.75,
    "EUR": 4.05,
}


def parse_amount(value: str | int | float) -> float:
    try:
        amount = float(str(value).replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"amount invalido: {value!r}") from exc
    if amount < 0:
        raise ValueError("amount no puede ser negativo.")
    return amount


def normalize_currency(value: str) -> str:
    currency = str(value).strip().upper()
    return currency or "PEN"


def amount_to_pen(amount: float, currency: str) -> float:
    return round(float(amount) * CURRENCY_TO_PEN.get(currency.upper(), 1.0), 4)


def normalize_category(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_") or "unknown"


def normalize_channel(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_") or "unknown"


def parse_location(value: str) -> tuple[str, str]:
    raw = str(value).strip()
    if "|" in raw:
        city, country = raw.split("|", 1)
    elif "," in raw:
        city, country = raw.split(",", 1)
    else:
        city, country = raw, "PE"
    return city.strip().title(), country.strip().upper()

