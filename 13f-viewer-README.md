# 13F Viewer

A fast, deterministic viewer for SEC Form 13F-HR filings. Enter a manager
(ticker or CIK) and see their latest reported equity portfolio, enriched with
live tickers and prices, and **diffed quarter-over-quarter** so you can see what
was added, reduced, opened, and closed.

No LLM in the data path — every number traces back to EDGAR, OpenFIGI, or a
market quote.

## Architecture

```
backend/                  FastAPI service (the real work)
  app/edgar.py            CIK resolution + 13F info-table XML parsing
  app/figi.py             CUSIP -> ticker via OpenFIGI, cached in SQLite
  app/prices.py           live quotes via yfinance (failures are non-fatal)
  app/pipeline.py         ties it together + computes the QoQ activity diff
  app/main.py             HTTP API
  tests/                  offline tests (mocked upstreams)
frontend/                 Vite + React UI
  src/components/HoldingsTable.jsx   sortable/filterable table + activity badges
  src/components/CompareView.jsx     two-manager overlap view
  src/csv.js                         CSV export
```

### How the data layer works

- **`edgar.py`** resolves a ticker or CIK against EDGAR's `company_tickers.json`,
  pulls the filer's submission history, picks the two most recent `13F-HR`
  filings, locates each filing's information-table XML, and parses it. It handles
  the **value-units quirk**: filings made before 2023-01-03 report holding value
  in *thousands* of dollars; later filings report *whole* dollars. Everything is
  normalized to whole dollars so the QoQ diff is apples-to-apples.
- **`figi.py`** maps CUSIP → ticker through OpenFIGI and persists every result
  (hits *and* misses) in a local SQLite cache, so repeat quarters resolve
  instantly and don't burn the rate limit.
- **`prices.py`** batch-fetches current quotes. A single bad ticker yields a
  `None` price rather than failing the whole request.
- **`pipeline.py`** aggregates duplicate lines per security, classifies each
  position as **New / Added / Reduced / Held / Closed**, and computes implied
  market value (`price × shares`), the reported per-share price at quarter-end,
  and the price change since the filing period.

## Running it

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# EDGAR rejects requests without a descriptive User-Agent.
export SEC_USER_AGENT="Your Name <your-email>"
# Optional but recommended — 10x faster CUSIP mapping and a higher rate limit.
export OPENFIGI_API_KEY="your-key"   # free at https://www.openfigi.com/api

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

### Tests

```bash
cd backend && source .venv/bin/activate && pytest -q
```

The tests run fully offline with mocked EDGAR/FIGI/price inputs and pin down the
value-unit normalization and the QoQ diff classification.

## API

| Endpoint | Description |
|---|---|
| `GET /api/health` | liveness probe |
| `GET /api/search?q=<name>` | find 13F filers by name → `[{cik, name}]` (for funds with no ticker) |
| `GET /api/manager/{identifier}` | latest portfolio + QoQ diff (`?refresh=true` to bust the cache) |
| `GET /api/compare?a=<id>&b=<id>` | overlapping holdings between two managers |

`identifier` accepts a ticker, a bare CIK, or a zero-padded `CIK##########`.

### Finding a fund by name

Most hedge funds have no ticker, so the UI search box queries EDGAR's full-text
search (`efts.sec.gov`) by name and shows matching filers with their CIK — type
"Pershing Square", pick the result, and it loads. Pure-digit input is treated as
a CIK and tickers still resolve directly, so all three entry styles work.

## Notes & caveats

- 13F covers **long US equity positions** (and some options) of institutional
  managers over the reporting threshold — it is *not* a complete portfolio
  (no shorts, no non-US listings, no cash).
- Filings appear up to **45 days after quarter-end**, so the data is delayed by
  design.
- This is informational tooling, **not investment advice**.

## Possible extensions

- A "diff my watchlist of managers each quarter" cron that flags new/closed
  positions across a set of CIKs.
- Historical multi-quarter trend per position (the parser already supports
  pulling more than two filings — raise the `limit`).
