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


def fetch_prices(tickers: Iterable[str]) -> dict[str, Quote]:
    """Return a ticker -> :class:`Quote` map. Missing prices yield ``price=None``."""
    symbols = sorted({t.upper() for t in tickers if t})
    if not symbols:
        return {}

    try:
        import yfinance as yf
    except ImportError:  # pragma: no cover - exercised only without the dep
        return {t: Quote(ticker=t) for t in symbols}

    out: dict[str, Quote] = {t: Quote(ticker=t) for t in symbols}
    try:
        data = yf.Tickers(" ".join(symbols))
    except Exception:
        return out

    for sym in symbols:
        try:
            tk = data.tickers.get(sym)
            if tk is None:
                continue
            price = _extract_price(tk)
            if price is not None:
                out[sym] = Quote(ticker=sym, price=price)
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
