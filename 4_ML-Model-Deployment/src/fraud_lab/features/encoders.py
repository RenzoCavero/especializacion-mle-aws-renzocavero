from __future__ import annotations


KNOWN_CATEGORIES = ("electronics", "travel", "grocery")
KNOWN_CHANNELS = ("mobile", "web")


def encode_category(category: str) -> tuple[dict[str, int], list[str]]:
    normalized = str(category).lower()
    warnings: list[str] = []
    encoded = {f"category_{name}": 1 if normalized == name else 0 for name in KNOWN_CATEGORIES}
    if normalized not in KNOWN_CATEGORIES:
        warnings.append(
            f"Categoria desconocida {category!r}; no se crea columna dinamica en produccion."
        )
    return encoded, warnings


def encode_channel(channel: str) -> tuple[dict[str, int], list[str]]:
    normalized = str(channel).lower()
    warnings: list[str] = []
    encoded = {f"channel_{name}": 1 if normalized == name else 0 for name in KNOWN_CHANNELS}
    if normalized not in KNOWN_CHANNELS:
        warnings.append(f"Canal desconocido {channel!r}; se usan columnas conocidas en cero.")
    return encoded, warnings

