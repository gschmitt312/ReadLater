import { activityLabel } from "./format.js";

function cell(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function positionsToCSV(report) {
  const header = [
    "Ticker",
    "Name",
    "CUSIP",
    "Class",
    "PutCall",
    "Shares",
    "ReportedValueUSD",
    "PctOfPortfolio",
    "Price",
    "ImpliedValueUSD",
    "PriceChangePct",
    "Activity",
    "SharesDelta",
    "PrevShares",
  ];
  const rows = [...report.positions, ...report.closed_positions].map((p) => [
    p.ticker,
    p.name,
    p.cusip,
    p.title_of_class,
    p.put_call,
    p.shares,
    p.value_usd,
    p.pct_of_portfolio?.toFixed(2),
    p.price ?? "",
    p.implied_value ?? "",
    p.price_change_pct?.toFixed(2) ?? "",
    activityLabel(p.activity),
    p.shares_delta,
    p.prev_shares,
  ]);
  return [header, ...rows].map((r) => r.map(cell).join(",")).join("\n");
}

export function downloadCSV(filename, text) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
