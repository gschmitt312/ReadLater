"""Pipeline + parser tests with fully mocked EDGAR/FIGI/price inputs.

These run offline (the sandbox can't reach data.sec.gov) and pin down the parts
most likely to break silently: the value-unit era quirk and the QoQ diff math.
"""

from datetime import date

from app.edgar import (
    Filing,
    FilingHoldings,
    Holding,
    aggregate_by_security,
    parse_info_table,
)
from app.figi import FigiResult
from app.pipeline import ADD, CLOSED, NEW, REDUCE, UNCHANGED, build_report
from app.prices import Quote


INFO_TABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>MICRON TECHNOLOGY INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>595112103</cusip>
    <value>562542</value>
    <shrsOrPrnAmt>
      <sshPrnamt>18300000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <votingAuthority><Sole>18300000</Sole><Shared>0</Shared><None>0</None></votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>AMAZON COM INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>023135106</cusip>
    <value>1000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>6000000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <votingAuthority><Sole>6000000</Sole><Shared>0</Shared><None>0</None></votingAuthority>
  </infoTable>
</informationTable>
"""


def test_parse_info_table_pre_2023_scales_thousands():
    holdings = parse_info_table(INFO_TABLE_XML, in_dollars=False)
    assert len(holdings) == 2
    mu = holdings[0]
    assert mu.cusip == "595112103"
    assert mu.shares == 18_300_000
    # Pre-2023 reported value is in thousands -> scaled to dollars.
    assert mu.value_usd == 562_542 * 1000


def test_parse_info_table_post_2023_keeps_dollars():
    holdings = parse_info_table(INFO_TABLE_XML, in_dollars=True)
    assert holdings[0].value_usd == 562_542


def test_aggregate_merges_duplicate_lines():
    h = [
        Holding("X", "COM", "111", 100.0, 10, "SH"),
        Holding("X", "COM", "111", 50.0, 5, "SH"),
    ]
    merged = aggregate_by_security(h)
    assert len(merged) == 1
    only = next(iter(merged.values()))
    assert only.shares == 15
    assert only.value_usd == 150.0


def _filing(period: date, filed: date) -> Filing:
    return Filing(
        accession="0000000000-00-000000",
        form="13F-HR",
        filing_date=filed,
        report_date=period,
        primary_doc="primary_doc.xml",
    )


def test_qoq_diff_classifies_and_computes():
    current = parse_info_table(INFO_TABLE_XML, in_dollars=True)
    curr_fh = FilingHoldings(_filing(date(2024, 12, 31), date(2025, 2, 14)), current)

    # Previous quarter: MU 165k fewer shares (-> ADD this qtr), AMZN absent
    # (-> NEW this qtr), plus a TSLA position that disappears (-> CLOSED).
    prev = [
        Holding("MICRON TECHNOLOGY INC", "COM", "595112103", 500_000.0, 18_135_000, "SH"),
        Holding("TESLA INC", "COM", "88160R101", 250_000.0, 1_000, "SH"),
    ]
    prev_fh = FilingHoldings(_filing(date(2024, 9, 30), date(2024, 11, 14)), prev)

    figi_map = {
        "595112103": FigiResult("595112103", ticker="MU", name="Micron Technology Inc"),
        "023135106": FigiResult("023135106", ticker="AMZN", name="Amazon.com Inc"),
        "88160R101": FigiResult("88160R101", ticker="TSLA", name="Tesla Inc"),
    }
    quotes = {
        # Reported price for MU = 562542 / 18.3M = $0.030740...; pick a current
        # price that yields a clean +254.9% move and a tidy implied value.
        "MU": Quote("MU", price=0.109094),
        "AMZN": Quote("AMZN", price=200.0),
    }

    report = build_report(curr_fh, prev_fh, figi_map, quotes, cik="0001067983", manager_name="TEST")

    rows = {r.ticker: r for r in report.positions}
    assert set(rows) == {"MU", "AMZN"}

    mu = rows["MU"]
    assert mu.activity == ADD
    assert mu.shares_delta == 165_000  # 18,300,000 - 18,135,000

    amzn = rows["AMZN"]
    assert amzn.activity == NEW
    assert amzn.shares_delta == 6_000_000
    assert amzn.implied_value == 6_000_000 * 200.0  # 1.2B implied

    # MU implied value = price * shares
    assert round(mu.implied_value) == round(0.109094 * 18_300_000)
    # MU price change: reported price was 562542/18.3M; current is ~3.549x.
    assert mu.reported_price == 562_542 / 18_300_000
    assert mu.price_change_pct is not None and mu.price_change_pct > 0

    # Closed positions: TSLA was held last quarter, gone now.
    closed = {r.ticker: r for r in report.closed_positions}
    assert "TSLA" in closed
    assert closed["TSLA"].activity == CLOSED
    assert closed["TSLA"].shares_delta == -1_000
    assert report.num_closed == 1


def test_unchanged_and_reduce_classification():
    curr = [Holding("A", "COM", "111", 100.0, 100, "SH"),
            Holding("B", "COM", "222", 100.0, 50, "SH")]
    prev = [Holding("A", "COM", "111", 100.0, 100, "SH"),
            Holding("B", "COM", "222", 200.0, 80, "SH")]
    cf = FilingHoldings(_filing(date(2024, 12, 31), date(2025, 2, 1)), curr)
    pf = FilingHoldings(_filing(date(2024, 9, 30), date(2024, 11, 1)), prev)
    report = build_report(cf, pf, {}, {}, cik="1", manager_name="T")
    rows = {r.cusip: r for r in report.positions}
    assert rows["111"].activity == UNCHANGED
    assert rows["222"].activity == REDUCE
    assert rows["222"].shares_delta == -30
