"""Checkout totals."""

from src.settings import TAX_RATE


def total(subtotal):
    return round(subtotal + TAX_RATE, 2)
