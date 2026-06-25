"""Core pipeline: resolve a manager, parse the two most recent 13F filings,
enrich with tickers + live prices, and compute the quarter-over-quarter diff.

This module has no FastAPI dependency so it can be unit-tested directly with
mocked EDGAR/FIGI/price inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .edgar import EdgarClient, Filing, FilingHoldings, Holding, aggregate_by_security
from .figi import FigiMapper
from .prices import Quote, fetch_prices

# Activity classifications for the QoQ diff.
NEW = "NEW"
ADD = "ADD"
REDUCE = "REDUCE"
UNCHANGED = "UNCHANGED"
CLOSED = "CLOSED"


@dataclass
class PositionRow:
    cusip: str
    ticker: str
    name: str
    title_of_class: str
    put_call: str

    shares: float
    value_usd: float  # value as reported in the 13F (whole dollars)

    price: Optional[float]  # current market price
    implied_value: Optional[float]  # price * shares (current market value)
    reported_price: Optional[float]  # 13F value / shares (price at period end)
    price_change_pct: Optional[float]  # current vs reported, percent

    activity: str
    shares_delta: float  # vs prior quarter (negative = reduced)
    prev_shares: float
    pct_of_portfolio: float  # by reported value


@dataclass
class Contribution:
    """One position's contribution to the estimated since-filing return."""

    ticker: str
    name: str
    weight_pct: float  # share of the priced book, by reported value
    price_change_pct: float  # current price vs reported quarter-end price
    contribution_pct: float  # weight x return; these sum to estimated_return_pct


@dataclass
class Performance:
    """Estimated mark-to-market performance of the reported book since the
    filing's quarter-end. Price-only: 13F omits cash, shorts, and intra-quarter
    trades, so this is the return of the disclosed long book, not the fund's."""

    period: str
    estimated_return_pct: float
    coverage_pct: float  # fraction of portfolio value that has a live price
    reported_value_priced: float
    implied_value_priced: float
    contributors: list[Contribution] = field(default_factory=list)
    detractors: list[Contribution] = field(default_factory=list)


@dataclass
class PortfolioReport:
    cik: str
    manager_name: str
    period: str  # e.g. "2024Q4"
    filing_date: str
    prev_period: Optional[str]
    total_value_usd: float
    positions: list[PositionRow] = field(default_factory=list)
    closed_positions: list[PositionRow] = field(default_factory=list)
    performance: Optional[Performance] = None

    @property
    def num_positions(self) -> int:
        return len(self.positions)

    @property
    def num_closed(self) -> int:
        return len(self.closed_positions)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["num_positions"] = self.num_positions
        d["num_closed"] = self.num_closed
        return d


def _classify(curr: float, prev: float) -> str:
    if prev <= 0 < curr:
        return NEW
    if curr <= 0 < prev:
        return CLOSED
    if curr > prev:
        return ADD
    if curr < prev:
        return REDUCE
    return UNCHANGED


def build_report(
    current: FilingHoldings,
    previous: Optional[FilingHoldings],
    figi_map: dict,
    quotes: dict[str, Quote],
    cik: str,
    manager_name: str,
) -> PortfolioReport:
    """Pure assembly step — all network I/O already resolved by the caller."""
    curr_by_key = aggregate_by_security(current.holdings)
    prev_by_key = aggregate_by_security(previous.holdings) if previous else {}

    total_value = sum(h.value_usd for h in curr_by_key.values())

    positions: list[PositionRow] = []
    for key, h in curr_by_key.items():
        prev_h = prev_by_key.get(key)
        prev_shares = prev_h.shares if prev_h else 0.0
        row = _make_row(h, figi_map, quotes, total_value, prev_shares)
        positions.append(row)

    # Closed: present last quarter, gone this quarter.
    closed: list[PositionRow] = []
    for key, h in prev_by_key.items():
        if key in curr_by_key:
            continue
        closed.append(_make_closed_row(h, figi_map, quotes))

    positions.sort(key=lambda r: r.value_usd, reverse=True)
    closed.sort(key=lambda r: r.prev_shares, reverse=True)

    performance = compute_performance(positions, current.filing.quarter_label, total_value)

    return PortfolioReport(
        cik=cik,
        manager_name=manager_name,
        period=current.filing.quarter_label,
        filing_date=current.filing.filing_date.isoformat(),
        prev_period=previous.filing.quarter_label if previous else None,
        total_value_usd=total_value,
        positions=positions,
        closed_positions=closed,
        performance=performance,
    )


def compute_performance(
    positions: list[PositionRow], period: str, total_value: float, top_n: int = 8
) -> Performance:
    """Estimate the reported book's mark-to-market return since quarter-end.

    Only positions with a live price participate. Weights are normalized over
    that priced subset, so per-position contributions sum exactly to the headline
    estimated return. ``coverage_pct`` says how much of the book is measured.
    """
    priced = [
        p
        for p in positions
        if p.price is not None and p.implied_value is not None and p.value_usd > 0
    ]
    reported_priced = sum(p.value_usd for p in priced)
    implied_priced = sum(p.implied_value for p in priced)

    if not priced or reported_priced <= 0:
        return Performance(
            period=period,
            estimated_return_pct=0.0,
            coverage_pct=0.0,
            reported_value_priced=0.0,
            implied_value_priced=0.0,
        )

    est_return = (implied_priced / reported_priced - 1.0) * 100.0
    contribs: list[Contribution] = []
    for p in priced:
        # contribution reconciles to est_return: sum_i (implied_i - reported_i)/reported_priced
        contribution = (p.implied_value - p.value_usd) / reported_priced * 100.0
        contribs.append(
            Contribution(
                ticker=p.ticker or p.cusip,
                name=p.name,
                weight_pct=p.value_usd / reported_priced * 100.0,
                price_change_pct=p.price_change_pct or 0.0,
                contribution_pct=contribution,
            )
        )

    contribs.sort(key=lambda c: c.contribution_pct, reverse=True)
    contributors = [c for c in contribs if c.contribution_pct > 0][:top_n]
    detractors = [c for c in reversed(contribs) if c.contribution_pct < 0][:top_n]

    return Performance(
        period=period,
        estimated_return_pct=est_return,
        coverage_pct=(reported_priced / total_value * 100.0) if total_value else 0.0,
        reported_value_priced=reported_priced,
        implied_value_priced=implied_priced,
        contributors=contributors,
        detractors=detractors,
    )


def _ticker_for(h: Holding, figi_map: dict) -> tuple[str, str]:
    res = figi_map.get(h.cusip)
    ticker = res.ticker if res and res.resolved else ""
    name = (res.name if res and res.name else "") or h.name_of_issuer
    return ticker, name


def _make_row(
    h: Holding,
    figi_map: dict,
    quotes: dict[str, Quote],
    total_value: float,
    prev_shares: float,
) -> PositionRow:
    ticker, name = _ticker_for(h, figi_map)
    quote = quotes.get(ticker.upper()) if ticker else None
    price = quote.price if quote else None

    implied_value = price * h.shares if price is not None else None
    reported_price = (h.value_usd / h.shares) if h.shares else None
    price_change = None
    if price is not None and reported_price:
        price_change = (price - reported_price) / reported_price * 100.0

    return PositionRow(
        cusip=h.cusip,
        ticker=ticker,
        name=name,
        title_of_class=h.title_of_class,
        put_call=h.put_call,
        shares=h.shares,
        value_usd=h.value_usd,
        price=price,
        implied_value=implied_value,
        reported_price=reported_price,
        price_change_pct=price_change,
        activity=_classify(h.shares, prev_shares),
        shares_delta=h.shares - prev_shares,
        prev_shares=prev_shares,
        pct_of_portfolio=(h.value_usd / total_value * 100.0) if total_value else 0.0,
    )


def _make_closed_row(h: Holding, figi_map: dict, quotes: dict[str, Quote]) -> PositionRow:
    ticker, name = _ticker_for(h, figi_map)
    quote = quotes.get(ticker.upper()) if ticker else None
    price = quote.price if quote else None
    return PositionRow(
        cusip=h.cusip,
        ticker=ticker,
        name=name,
        title_of_class=h.title_of_class,
        put_call=h.put_call,
        shares=0.0,
        value_usd=0.0,
        price=price,
        implied_value=None,
        reported_price=None,
        price_change_pct=None,
        activity=CLOSED,
        shares_delta=-h.shares,
        prev_shares=h.shares,
        pct_of_portfolio=0.0,
    )


def run_pipeline(
    identifier: str,
    edgar: Optional[EdgarClient] = None,
    figi: Optional[FigiMapper] = None,
    price_fetcher=fetch_prices,
) -> PortfolioReport:
    """End-to-end: identifier -> enriched, diffed portfolio report."""
    own_edgar = edgar is None
    own_figi = figi is None
    edgar = edgar or EdgarClient()
    figi = figi or FigiMapper()
    try:
        cik = edgar.resolve_cik(identifier)
        manager = edgar.manager_name(cik)
        filings = edgar.list_13f_filings(cik, limit=2)
        if not filings:
            raise ValueError(f"No 13F-HR filings found for {identifier!r} (CIK {cik}).")

        current = edgar.get_holdings(cik, filings[0])
        previous = edgar.get_holdings(cik, filings[1]) if len(filings) > 1 else None

        all_cusips = [h.cusip for h in current.holdings]
        if previous:
            all_cusips += [h.cusip for h in previous.holdings]
        figi_map = figi.map_cusips(all_cusips)

        tickers = [r.ticker for r in figi_map.values() if r.resolved]
        quotes = price_fetcher(tickers)

        return build_report(current, previous, figi_map, quotes, cik, manager)
    finally:
        if own_figi:
            figi.close()
        if own_edgar:
            edgar.close()
