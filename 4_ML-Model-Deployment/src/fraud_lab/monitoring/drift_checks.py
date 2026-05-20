from __future__ import annotations


def simple_amount_shift_warning(current_amount: float, baseline_average: float = 100.0) -> str:
    if baseline_average <= 0:
        return ""
    ratio = current_amount / baseline_average
    if ratio >= 5:
        return "amount_distribution_shift_candidate"
    return ""

