"""FastAPI surface for the 13F Viewer.

Endpoints:
  GET /api/health                 - liveness
  GET /api/manager/{identifier}   - latest portfolio + QoQ diff for one manager
  GET /api/compare                - side-by-side overlap of two managers
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .edgar import EdgarClient, EdgarError
from .pipeline import PortfolioReport, run_pipeline

app = FastAPI(title="13F Viewer", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _report(identifier: str) -> PortfolioReport:
    try:
        return run_pipeline(identifier)
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Cache assembled reports for a short period within a process run. EDGAR data is
# quarterly and prices move slowly enough that this is a sane default; restart to
# clear, or wire a TTL if you need freshness guarantees.
@lru_cache(maxsize=64)
def _cached_report(identifier: str) -> PortfolioReport:
    return _report(identifier)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/search")
def search(q: str = Query(..., min_length=2, description="Fund name to search")) -> dict:
    try:
        with EdgarClient() as ec:
            return {"results": ec.search_filers(q)}
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/manager/{identifier}")
def manager(identifier: str, refresh: bool = Query(False)) -> dict:
    if refresh:
        _cached_report.cache_clear()
    return _cached_report(identifier).to_dict()


@app.get("/api/compare")
def compare(
    a: str = Query(..., description="First manager (ticker or CIK)"),
    b: str = Query(..., description="Second manager (ticker or CIK)"),
) -> dict:
    report_a = _cached_report(a)
    report_b = _cached_report(b)

    by_cusip_b = {p.cusip: p for p in report_b.positions}
    overlap = []
    for pa in report_a.positions:
        pb = by_cusip_b.get(pa.cusip)
        if not pb:
            continue
        overlap.append(
            {
                "cusip": pa.cusip,
                "ticker": pa.ticker or pb.ticker,
                "name": pa.name or pb.name,
                "a_shares": pa.shares,
                "b_shares": pb.shares,
                "a_value_usd": pa.value_usd,
                "b_value_usd": pb.value_usd,
                "a_pct_of_portfolio": pa.pct_of_portfolio,
                "b_pct_of_portfolio": pb.pct_of_portfolio,
            }
        )
    overlap.sort(key=lambda r: r["a_value_usd"] + r["b_value_usd"], reverse=True)

    a_only = sorted(
        (p.cusip for p in report_a.positions if p.cusip not in by_cusip_b)
    )
    by_cusip_a = {p.cusip for p in report_a.positions}
    b_only = sorted(p.cusip for p in report_b.positions if p.cusip not in by_cusip_a)

    return {
        "a": {"cik": report_a.cik, "name": report_a.manager_name, "period": report_a.period},
        "b": {"cik": report_b.cik, "name": report_b.manager_name, "period": report_b.period},
        "overlap": overlap,
        "a_only_count": len(a_only),
        "b_only_count": len(b_only),
        "overlap_count": len(overlap),
    }
