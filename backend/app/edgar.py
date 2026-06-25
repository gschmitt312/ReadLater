"""EDGAR access layer.

Resolves a manager identifier (CIK or ticker) to a CIK, lists that filer's
13F-HR filings, and parses the information-table XML into normalized holdings.

All network access goes through ``data.sec.gov`` / ``www.sec.gov`` which require
a descriptive User-Agent (set ``SEC_USER_AGENT``), or EDGAR returns HTTP 403.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Optional
from xml.etree import ElementTree as ET

import httpx

EDGAR_DATA = "https://data.sec.gov"
EDGAR_WWW = "https://www.sec.gov"

# SEC amended Form 13F so that, for filings made on/after this date, the holding
# value is reported in whole dollars instead of thousands of dollars.
DOLLARS_RULE_DATE = date(2023, 1, 3)

_DEFAULT_UA = "13F-Viewer/1.0 (contact: set SEC_USER_AGENT env var)"


def _user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", _DEFAULT_UA)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": _user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Host": None,  # filled per-request by httpx
    }


@dataclass
class Holding:
    """A single normalized line from a 13F information table."""

    name_of_issuer: str
    title_of_class: str
    cusip: str
    # Value normalized to whole US dollars regardless of the filing-era units.
    value_usd: float
    shares: float
    sh_prn_type: str  # "SH" (shares) or "PRN" (principal)
    put_call: str = ""  # "Put", "Call", or "" for long stock
    investment_discretion: str = ""

    @property
    def key(self) -> str:
        """Identity for QoQ diffing: same security + same option type."""
        return f"{self.cusip}|{self.put_call}"


@dataclass
class Filing:
    accession: str
    form: str
    filing_date: date
    report_date: date  # the quarter-end the 13F covers
    primary_doc: str

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")

    @property
    def quarter_label(self) -> str:
        q = (self.report_date.month - 1) // 3 + 1
        return f"{self.report_date.year}Q{q}"


@dataclass
class FilingHoldings:
    filing: Filing
    holdings: list[Holding] = field(default_factory=list)


class EdgarError(RuntimeError):
    pass


class EdgarClient:
    def __init__(self, client: Optional[httpx.Client] = None, throttle: float = 0.12):
        # EDGAR fair-access is ~10 req/s; default throttle keeps us well under.
        self._client = client or httpx.Client(timeout=30.0, follow_redirects=True)
        self._owns_client = client is None
        self._throttle = throttle
        self._last_request = 0.0
        self._ticker_map: Optional[dict[str, str]] = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "EdgarClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- low level ---------------------------------------------------------
    def _get(self, url: str) -> httpx.Response:
        wait = self._throttle - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"}
        resp = self._client.get(url, headers=headers)
        self._last_request = time.monotonic()
        if resp.status_code == 403:
            raise EdgarError(
                "EDGAR returned 403. Set a descriptive SEC_USER_AGENT "
                "(e.g. 'Name <email>')."
            )
        resp.raise_for_status()
        return resp

    # -- identifier resolution --------------------------------------------
    def _load_ticker_map(self) -> dict[str, str]:
        if self._ticker_map is None:
            data = self._get(f"{EDGAR_WWW}/files/company_tickers.json").json()
            # Shape: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": ...}}
            self._ticker_map = {
                row["ticker"].upper(): str(row["cik_str"]).zfill(10)
                for row in data.values()
            }
        return self._ticker_map

    def resolve_cik(self, identifier: str) -> str:
        """Accept a 10-digit CIK, a bare integer CIK, or a ticker symbol."""
        ident = identifier.strip()
        digits = re.sub(r"\D", "", ident)
        if digits and (ident.upper().startswith("CIK") or digits == ident):
            return digits.zfill(10)
        cik = self._load_ticker_map().get(ident.upper())
        if cik:
            return cik
        if digits:
            return digits.zfill(10)
        raise EdgarError(f"Could not resolve identifier to a CIK: {identifier!r}")

    # -- submissions / filings --------------------------------------------
    def get_submissions(self, cik: str) -> dict:
        cik = cik.zfill(10)
        return self._get(f"{EDGAR_DATA}/submissions/CIK{cik}.json").json()

    def list_13f_filings(self, cik: str, limit: int = 12) -> list[Filing]:
        cik = cik.zfill(10)
        subs = self.get_submissions(cik)
        recent = subs.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accns = recent.get("accessionNumber", [])
        fdates = recent.get("filingDate", [])
        rdates = recent.get("reportDate", [])
        pdocs = recent.get("primaryDocument", [])

        out: list[Filing] = []
        for i, form in enumerate(forms):
            if form not in ("13F-HR", "13F-HR/A"):
                continue
            try:
                out.append(
                    Filing(
                        accession=accns[i],
                        form=form,
                        filing_date=_parse_date(fdates[i]),
                        report_date=_parse_date(rdates[i]),
                        primary_doc=pdocs[i] if i < len(pdocs) else "",
                    )
                )
            except (IndexError, ValueError):
                continue
            if len(out) >= limit:
                break
        # Newest report period first.
        out.sort(key=lambda f: f.report_date, reverse=True)
        return out

    def manager_name(self, cik: str) -> str:
        subs = self.get_submissions(cik)
        return subs.get("name", "") or ""

    # -- information table -------------------------------------------------
    def _filing_dir(self, cik: str, filing: Filing) -> str:
        return f"{EDGAR_WWW}/Archives/edgar/data/{int(cik)}/{filing.accession_nodash}"

    def _find_infotable_url(self, cik: str, filing: Filing) -> str:
        base = self._filing_dir(cik, filing)
        index = self._get(f"{base}/index.json").json()
        items = index.get("directory", {}).get("item", [])
        candidates = [it["name"] for it in items if it.get("name", "").endswith(".xml")]
        # Prefer files whose name looks like an info table.
        for name in candidates:
            low = name.lower()
            if "infotable" in low or "information_table" in low or "form13f" in low:
                if "primary_doc" not in low:  # primary_doc.xml is the cover page
                    return f"{base}/{name}"
        # Fall back: probe each xml for the informationTable root element.
        for name in candidates:
            if "primary_doc" in name.lower():
                continue
            text = self._get(f"{base}/{name}").text
            if "informationTable" in text or "infoTable" in text:
                return f"{base}/{name}"
        raise EdgarError(f"No information table found for {filing.accession}")

    def get_holdings(self, cik: str, filing: Filing) -> FilingHoldings:
        url = self._find_infotable_url(cik, filing)
        xml = self._get(url).text
        holdings = parse_info_table(xml, in_dollars=filing.filing_date >= DOLLARS_RULE_DATE)
        return FilingHoldings(filing=filing, holdings=holdings)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def _find(parent: ET.Element, name: str) -> Optional[ET.Element]:
    for child in parent.iter():
        if _localname(child.tag) == name:
            return child
    return None


def parse_info_table(xml: str, in_dollars: bool) -> list[Holding]:
    """Parse 13F information-table XML into normalized :class:`Holding` rows.

    ``in_dollars`` selects the value-unit convention: post-2023 filings already
    report whole dollars; earlier filings report thousands and are scaled up.
    """
    # Strip a leading BOM / stray prolog whitespace that trips ElementTree.
    xml = xml.lstrip("﻿").strip()
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise EdgarError(f"Could not parse information table XML: {exc}") from exc

    holdings: list[Holding] = []
    for node in root.iter():
        if _localname(node.tag) != "infoTable":
            continue
        children = {_localname(c.tag): c for c in node}

        shrs = children.get("shrsOrPrnAmt")
        shares_txt = put_type = ""
        if shrs is not None:
            shares_txt = _text(_find(shrs, "sshPrnamt"))
            put_type = _text(_find(shrs, "sshPrnamtType"))

        raw_value = _to_float(_text(children.get("value")))
        value_usd = raw_value if in_dollars else raw_value * 1000.0

        holdings.append(
            Holding(
                name_of_issuer=_text(children.get("nameOfIssuer")),
                title_of_class=_text(children.get("titleOfClass")),
                cusip=_text(children.get("cusip")).upper(),
                value_usd=value_usd,
                shares=_to_float(shares_txt),
                sh_prn_type=put_type or "SH",
                put_call=_text(children.get("putCall")),
                investment_discretion=_text(children.get("investmentDiscretion")),
            )
        )
    return holdings


def _to_float(value: str) -> float:
    if not value:
        return 0.0
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return 0.0


def aggregate_by_security(holdings: Iterable[Holding]) -> dict[str, Holding]:
    """Collapse duplicate lines (same CUSIP + put/call) by summing.

    Managers sometimes report a security across multiple lines (e.g. different
    investment-discretion buckets); the diff layer wants one row per security.
    """
    merged: dict[str, Holding] = {}
    for h in holdings:
        if h.key in merged:
            existing = merged[h.key]
            existing.value_usd += h.value_usd
            existing.shares += h.shares
        else:
            merged[h.key] = Holding(**{**h.__dict__})
    return merged
