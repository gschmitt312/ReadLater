"""CUSIP -> ticker resolution via the OpenFIGI mapping API.

Results are cached in a local SQLite file so repeat lookups (the common case
quarter-over-quarter) are instant and don't burn the API rate limit. Set
``OPENFIGI_API_KEY`` for the higher rate limit and larger batch size.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import httpx

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

DEFAULT_CACHE = Path(os.environ.get("FIGI_CACHE", Path(__file__).parent / "figi_cache.sqlite"))


# OpenFIGI exchange codes for the US composite / primary listings, in order of
# preference. 13F CUSIPs are US securities, so we want the US ticker (CVX, not a
# foreign cross-listing) for Yahoo price lookups.
_US_EXCH_PREFERENCE = ("US", "UN", "UW", "UQ", "UA", "UP", "UR", "UV")


def _pick_listing(data: list[dict]) -> dict:
    """Choose the best OpenFIGI listing for a CUSIP, preferring the US ticker."""
    by_exch = {d.get("exchCode", ""): d for d in data}
    for code in _US_EXCH_PREFERENCE:
        if code in by_exch:
            return by_exch[code]
    return data[0]


@dataclass
class FigiResult:
    cusip: str
    ticker: str = ""
    name: str = ""
    exchange: str = ""
    figi: str = ""

    @property
    def resolved(self) -> bool:
        return bool(self.ticker)


class FigiCache:
    def __init__(self, path: Path = DEFAULT_CACHE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS figi_map (
                cusip TEXT PRIMARY KEY,
                ticker TEXT,
                name TEXT,
                exchange TEXT,
                figi TEXT
            )
            """
        )
        self._conn.commit()

    def get_many(self, cusips: Iterable[str]) -> dict[str, FigiResult]:
        cusips = list({c for c in cusips if c})
        out: dict[str, FigiResult] = {}
        if not cusips:
            return out
        # SQLite caps variables per statement; chunk to stay safe.
        for i in range(0, len(cusips), 500):
            chunk = cusips[i : i + 500]
            qs = ",".join("?" * len(chunk))
            rows = self._conn.execute(
                f"SELECT cusip, ticker, name, exchange, figi FROM figi_map WHERE cusip IN ({qs})",
                chunk,
            ).fetchall()
            for cusip, ticker, name, exchange, figi in rows:
                out[cusip] = FigiResult(cusip, ticker or "", name or "", exchange or "", figi or "")
        return out

    def put_many(self, results: Iterable[FigiResult]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO figi_map (cusip, ticker, name, exchange, figi) "
            "VALUES (?, ?, ?, ?, ?)",
            [(r.cusip, r.ticker, r.name, r.exchange, r.figi) for r in results],
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class FigiMapper:
    def __init__(
        self,
        cache: Optional[FigiCache] = None,
        client: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
    ):
        self.cache = cache or FigiCache()
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None
        self.api_key = api_key or os.environ.get("OPENFIGI_API_KEY", "")
        # With a key: 100/batch, ~25 req/s. Without: 10/batch, ~5 req/min.
        self._batch = 100 if self.api_key else 10

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
        self.cache.close()

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-OPENFIGI-APIKEY"] = self.api_key
        return h

    def _request_batch(self, cusips: list[str]) -> dict[str, FigiResult]:
        jobs = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]
        resp = self._client.post(OPENFIGI_URL, json=jobs, headers=self._headers())
        if resp.status_code == 429:
            # Rate limited: back off and let the caller retry the chunk.
            time.sleep(2.0 if self.api_key else 15.0)
            resp = self._client.post(OPENFIGI_URL, json=jobs, headers=self._headers())
        resp.raise_for_status()
        payload = resp.json()

        out: dict[str, FigiResult] = {}
        for cusip, entry in zip(cusips, payload):
            data = entry.get("data") if isinstance(entry, dict) else None
            if data:
                best = _pick_listing(data)
                out[cusip] = FigiResult(
                    cusip=cusip,
                    ticker=best.get("ticker", "") or "",
                    name=best.get("name", "") or "",
                    exchange=best.get("exchCode", "") or "",
                    figi=best.get("figi", "") or "",
                )
            else:
                # Cache the miss too, so we don't re-query unmappable CUSIPs.
                out[cusip] = FigiResult(cusip=cusip)
        return out

    def map_cusips(self, cusips: Iterable[str]) -> dict[str, FigiResult]:
        wanted = list({c.upper() for c in cusips if c})
        results = self.cache.get_many(wanted)
        missing = [c for c in wanted if c not in results]

        for i in range(0, len(missing), self._batch):
            chunk = missing[i : i + self._batch]
            fetched = self._request_batch(chunk)
            self.cache.put_many(fetched.values())
            results.update(fetched)
            if not self.api_key and i + self._batch < len(missing):
                # Stay under the keyless ~5 req/min ceiling.
                time.sleep(13.0)
        return results
