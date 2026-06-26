"""Live price layer.

Batch-fetches current quotes for a set of tickers via yfinance. Failures for a
single ticker never abort the batch — they just produce a ``None`` price so the
pipeline can still render the row (value/shares come from EDGAR regardless).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass
class Quote:
    ticker: str
    price: Optional[float] = None
    currency: str = "USD"


def yahoo_symbol(ticker: str) -> str:
    """Translate a 13F/OpenFIGI ticker into the symbol Yahoo expects.

    Share classes use a slash on EDGAR/OpenFIGI (``BRK/B``, ``LEN/B``) but a
    dash on Yahoo (``BRK-B``).
    """
    return ticker.upper().strip().replace("/", "-")


def fetch_prices(tickers: Iterable[str]) -> dict[str, Quote]:
    """Return a ticker -> :class:`Quote` map, keyed by the original (13F) ticker.

    Missing prices yield ``price=None`` so the row still renders.
    """
    originals = sorted({t.upper() for t in tickers if t})
    if not originals:
        return {}

    out: dict[str, Quote] = {t: Quote(ticker=t) for t in originals}

    try:
        import logging

        import yfinance as yf

        # yfinance logs noisy per-ticker "possibly delisted" lines straight to
        # the console; a single missing quote is expected and handled, so quiet it.
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    except ImportError:  # pragma: no cover - exercised only without the dep
        return out

    # First Yahoo symbol wins if two originals collapse to the same one.
    sym_to_original: dict[str, str] = {}
    for t in originals:
        sym_to_original.setdefault(yahoo_symbol(t), t)

    try:
        data = yf.Tickers(" ".join(sym_to_original))
    except Exception:
        return out

    for ysym, original in sym_to_original.items():
        try:
            tk = data.tickers.get(ysym)
            if tk is None:
                continue
            price = _extract_price(tk)
            if price is not None:
                out[original] = Quote(ticker=original, price=price)
        except Exception:
            continue
    return out


def _extract_price(tk) -> Optional[float]:
    # fast_info is cheap and avoids the heavier .info network round-trip.
    for attr in ("last_price", "last_close", "previous_close"):
        try:
            fi = getattr(tk, "fast_info", None)
            if fi is not None:
                val = fi.get(attr) if hasattr(fi, "get") else getattr(fi, attr, None)
                if val:
                    return float(val)
        except Exception:
            pass
    # Fall back to a 1-day history close.
    try:
        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None
